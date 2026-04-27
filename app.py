from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import threading
import time
import uuid
import re
from pathlib import Path
from typing import Any, AsyncGenerator

import requests
from fastapi import FastAPI, File, Request, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles

from config import config
from db import save_message, get_messages, clear_session_messages, ensure_session
from tools import call_tool
from voice_library import resolve_xtts_speaker_wav

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
TEMP_DIR = BASE_DIR / "temp"
TTS_DIR = BASE_DIR / "tts_out"
TTS_CACHE_DIR = BASE_DIR / "tts_cache"

TEMP_DIR.mkdir(parents=True, exist_ok=True)
TTS_DIR.mkdir(parents=True, exist_ok=True)
TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Offline Voice Assistant", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/audio", StaticFiles(directory=str(TTS_DIR)), name="audio")
app.mount("/cache", StaticFiles(directory=str(TTS_CACHE_DIR)), name="cache")

_whisper_lock = threading.Lock()
_whisper_model = None

# Track recent errors for health page
_recent_errors = []

def _log_error(msg):
    _recent_errors.append({"time": time.time(), "msg": msg})
    if len(_recent_errors) > 20:
        _recent_errors.pop(0)

def _new_session_id() -> str:
    return secrets.token_urlsafe(18)

def _get_or_create_session_id(request: Request) -> tuple[str, bool]:
    sid = request.cookies.get("voice_session_id")
    if sid:
        return sid, False
    return _new_session_id(), True

def _trim_history(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    max_hist = config.get("max_history_messages")
    system_prompt = config.get("system_prompt")
    if not messages:
        return [{"role": "system", "content": system_prompt}]
    system = messages[0]
    tail = messages[1:]
    if len(tail) <= max_hist:
        return [system] + tail
    return [system] + tail[-max_hist:]

def _load_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model
        from faster_whisper import WhisperModel
        try:
            _whisper_model = WhisperModel(
                config.get("whisper_model"),
                device=config.get("whisper_device"),
                compute_type=config.get("whisper_compute_type")
            )
        except Exception as e:
            _log_error(f"Whisper load failed: {e}")
            raise
        return _whisper_model

def _convert_to_wav(input_path: Path) -> Path:
    # If the upload is already a WAV, avoid writing to the same path.
    # Otherwise ffmpeg can fail when input==output.
    if input_path.suffix.lower() == ".wav":
        output_path = input_path.with_name(input_path.stem + "_16000.wav")
    else:
        output_path = input_path.with_suffix(".wav")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-vn",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        stdout = (exc.stdout or b"").decode("utf-8", errors="replace").strip()
        details = stderr or stdout or str(exc)
        raise RuntimeError(f"ffmpeg failed to convert audio: {details}") from exc

    return output_path

def _transcribe_audio(audio_path: Path) -> str:
    wav_path = _convert_to_wav(audio_path)
    model = _load_whisper_model()
    segments, _ = model.transcribe(str(wav_path), language="en", vad_filter=True, beam_size=1)
    transcript = " ".join([s.text.strip() for s in segments if s.text]).strip()
    return transcript

def _find_tts_backend() -> str | None:
    # start_voice_assistant.sh sets env var TTS_BACKEND=xtts; config.local.json defaults to 'auto'
    pref = os.environ.get("TTS_BACKEND") or config.get("tts_backend")
    if pref and pref != "auto":
        return pref

    if shutil.which(config.get("piper_bin")):
        return "piper"
    if shutil.which("espeak-ng"):
        return "espeak-ng"
    if shutil.which("espeak"):
        return "espeak"
    return None


def _synthesize_speech(text: str, session_id: str, cache: bool = False) -> Path | None:
    if not text.strip():
        return None

    # Simple caching for repeated short phrases
    clean_text = re.sub(r'[^a-z0-9]', '', text.lower())
    cache_file = TTS_CACHE_DIR / f"{clean_text[:50]}.wav"
    if cache and cache_file.exists():
        return cache_file

    out_file = TTS_DIR / f"{session_id}_{uuid.uuid4().hex}.wav"
    backend = _find_tts_backend()

    # XTTS speaker reference (prefer chosen voice profile if present)
    default_speaker_wav = Path(os.environ.get("XTTS_SPEAKER_WAV", "/tmp/other-way.wav"))
    try:
        speaker_wav = resolve_xtts_speaker_wav(BASE_DIR, default_speaker_wav)
    except Exception:
        speaker_wav = default_speaker_wav

    try:
        if backend == "piper":
            cmd = [config.get("piper_bin"), "--output_file", str(out_file)]
            model = config.get("piper_voice_model")
            if model:
                cmd.extend(["--model", model])
            # Some piper builds use --model for the ONNX path.
            # If piper fails with missing model, we still want to surface that error.
            subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                check=True,
                capture_output=True,
                timeout=120,
            )

        elif backend in {"espeak", "espeak-ng"}:
            subprocess.run([backend, "-w", str(out_file), text], check=True, capture_output=True, timeout=60)

        elif backend == "xtts":
            # Truncate to keep XTTS fast/stable, especially during long assistant replies.
            max_chars = int(config.get("xtts_max_chars", 400))
            if max_chars and len(text) > max_chars:
                text = text[:max_chars]

            xtts_model_name = os.environ.get(
                "XTTS_MODEL_NAME", "tts_models/multilingual/multi-dataset/xtts_v2"
            )
            xtts_helper = BASE_DIR / "xtts_synth.py"
            xtts_py = BASE_DIR / "xtts-venv" / "bin" / "python"
            if not xtts_helper.exists():
                raise RuntimeError(f"Missing {xtts_helper}")
            if not xtts_py.exists():
                raise RuntimeError(f"Missing XTTS venv python: {xtts_py}")
            if not speaker_wav.exists():
                raise RuntimeError(f"XTTS speaker wav not found: {speaker_wav}")

            xtts_timeout = int(config.get("xtts_timeout_seconds", 20))
            xtts_ok = False
            try:
                # xtts_synth.py reads text from stdin
                subprocess.run(
                    [
                        str(xtts_py),
                        str(xtts_helper),
                        "--model-name",
                        xtts_model_name,
                        "--speaker-wav",
                        str(speaker_wav),
                        "--language",
                        "en",
                        "--output",
                        str(out_file),
                    ],
                    input=text.encode("utf-8"),
                    check=True,
                    capture_output=True,
                    timeout=xtts_timeout,
                )
                xtts_ok = True
            except subprocess.TimeoutExpired:
                _log_error(f"XTTS synth timed out after {xtts_timeout}s")
            except Exception as exc:
                _log_error(f"XTTS synth failed: {exc}")

            if not xtts_ok:
                # Fallback so /api/chat still returns audio_url quickly.
                if shutil.which(config.get("piper_bin")):
                    alt = "piper"
                elif shutil.which("espeak-ng"):
                    alt = "espeak-ng"
                elif shutil.which("espeak"):
                    alt = "espeak"
                else:
                    return None

                if alt == "piper":
                    cmd = [config.get("piper_bin"), "--output_file", str(out_file)]
                    model = config.get("piper_voice_model")
                    if model:
                        cmd.extend(["--model", model])
                    subprocess.run(
                        cmd,
                        input=text.encode("utf-8"),
                        check=True,
                        capture_output=True,
                        timeout=60,
                    )
                else:
                    subprocess.run(
                        [alt, "-w", str(out_file), text],
                        check=True,
                        capture_output=True,
                        timeout=60,
                    )

        else:
            raise RuntimeError("No TTS backend")

        if cache:
            shutil.copy(out_file, cache_file)
        return out_file

    except Exception as e:
        _log_error(f"TTS failed: {e}")
        return None

def _cleanup_old_files():
    # Cleanup temp and tts_out older than 1 hour
    now = time.time()
    for d in [TEMP_DIR, TTS_DIR]:
        for f in d.iterdir():
            if f.is_file() and now - f.stat().st_mtime > 3600:
                try: f.unlink()
                except: pass

@app.get("/")
def index(request: Request):
    session_id, is_new = _get_or_create_session_id(request)
    ensure_session(session_id)
    response = FileResponse(str(TEMPLATES_DIR / "index.html"))
    if is_new:
        response.set_cookie("voice_session_id", session_id, httponly=True, max_age=2592000)
    return response

@app.get("/settings")
def settings_page():
    return FileResponse(str(TEMPLATES_DIR / "settings.html"))

@app.get("/debug")
def debug_page():
    return FileResponse(str(TEMPLATES_DIR / "debug.html"))

@app.get("/api/config")
def get_config():
    return config.to_dict()

@app.post("/api/config")
async def update_config(req: Request):
    data = await req.json()
    for k, v in data.items():
        config.set(k, v)
    return {"ok": True}

@app.get("/api/health")
def health():
    llama_status = {"ok": False, "error": None}
    try:
        r = requests.get(config.get("llama_health_url"), timeout=2)
        llama_status["ok"] = r.ok
    except Exception as e:
        llama_status["error"] = str(e)
    
    return {
        "ok": True,
        "llama": llama_status,
        "whisper": {"model": config.get("whisper_model"), "device": config.get("whisper_device")},
        "tts": {"backend": _find_tts_backend()},
        "errors": _recent_errors[-5:]
    }

@app.post("/api/clear")
def api_clear(request: Request):
    sid, _ = _get_or_create_session_id(request)
    clear_session_messages(sid)
    return {"ok": True}

async def _stream_llama(messages: list[dict[str, str]], session_id: str, transcript: str):
    # Send transcript first
    yield json.dumps({"type": "transcript", "text": transcript}) + "\n"

    payload = {
        "messages": messages,
        "temperature": 0.4,
        "stream": True,
        "model": config.get("llama_model")
    }
    
    full_response = ""
    sentence_buffer = ""
    
    try:
        r = requests.post(config.get("llama_chat_url"), json=payload, stream=True, timeout=config.get("http_timeout"))
        r.raise_for_status()
        
        for line in r.iter_lines():
            if not line: continue
            line = line.decode("utf-8")
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]": break
                try:
                    data = json.loads(data_str)
                    token = data["choices"][0]["delta"].get("content", "")
                    if token:
                        full_response += token
                        sentence_buffer += token
                        
                        # Check for sentence completion
                        if any(c in token for c in ".!?\n"):
                            sentences = re.split(r'(?<=[.!?\n])\s+', sentence_buffer)
                            if len(sentences) > 1:
                                for s in sentences[:-1]:
                                    if not s.strip():
                                        continue
                                    s2 = s.strip()
                                    if len(s2) > int(config.get("xtts_max_chars", 400)):
                                        s2 = s2[: int(config.get("xtts_max_chars", 400))]
                                    audio_path = _synthesize_speech(s2, session_id)
                                    yield json.dumps({
                                        "type": "sentence",
                                        "text": s.strip(),
                                        "audio_url": f"/audio/{audio_path.name}" if audio_path else None
                                    }) + "\n"
                                sentence_buffer = sentences[-1]
                        
                        yield json.dumps({"type": "token", "text": token}) + "\n"
                except: continue
        
        if sentence_buffer.strip():
            audio_path = _synthesize_speech(sentence_buffer.strip(), session_id)
            yield json.dumps({
                "type": "sentence", 
                "text": sentence_buffer.strip(),
                "audio_url": f"/audio/{audio_path.name}" if audio_path else None
            }) + "\n"
            
        save_message(session_id, "assistant", full_response)
        
        # Check for tool usage in full response (simple JSON detection)
        tool_match = re.search(r'\{"tool":\s*"([^"]+)"\}', full_response)
        if tool_match:
            tool_name = tool_match.group(1)
            tool_res = call_tool(tool_name)
            yield json.dumps({"type": "tool_result", "tool": tool_name, "result": tool_res}) + "\n"
            # Optionally speak tool result? Let's just send it as text for now.

    except Exception as e:
        _log_error(f"Streaming failed: {e}")
        yield json.dumps({"type": "error", "text": str(e)}) + "\n"

@app.post("/api/chat")
async def api_chat(request: Request, bg_tasks: BackgroundTasks, audio: UploadFile = File(...)):
    sid, is_new = _get_or_create_session_id(request)
    ensure_session(sid)
    bg_tasks.add_task(_cleanup_old_files)

    suffix = Path(audio.filename or "rec.webm").suffix or ".webm"
    tmp_path = TEMP_DIR / f"{sid}_{uuid.uuid4().hex}{suffix}"
    with tmp_path.open("wb") as f: f.write(await audio.read())

    try:
        transcript = _transcribe_audio(tmp_path)
        if not transcript:
            return JSONResponse({"ok": False, "error": "No speech detected"}, status_code=400)
        
        # Wake word check
        wake_phrase = config.get("wake_phrase")
        if wake_phrase:
            if not transcript.lower().strip().startswith(wake_phrase.lower()):
                return Response(status_code=204)
            else:
                # Remove wake phrase from transcript for cleaner chat
                transcript = transcript[len(wake_phrase):].strip()
                if not transcript:
                    # Just the wake word was said, maybe reply with "Yes?"
                    transcript = "Hello" # Placeholder or just return
        
        save_message(sid, "user", transcript)
        history = _trim_history(get_messages(sid))
        
        if config.get("llama_stream"):
            return StreamingResponse(_stream_llama(history, sid, transcript), media_type="text/event-stream")
        else:
            # Fallback non-streaming
            payload = {"messages": history, "temperature": 0.4, "stream": False, "model": config.get("llama_model")}
            r = requests.post(config.get("llama_chat_url"), json=payload, timeout=config.get("http_timeout"))
            r.raise_for_status()
            reply = r.json()["choices"][0]["message"]["content"].strip()
            save_message(sid, "assistant", reply)
            audio_path = _synthesize_speech(reply, sid)
            return {
                "ok": True, "transcript": transcript, "assistant_reply": reply,
                "audio_url": f"/audio/{audio_path.name}" if audio_path else None
            }
    except Exception as e:
        _log_error(f"Chat failed: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    finally:
        if tmp_path.exists(): tmp_path.unlink()
        wav = tmp_path.with_suffix(".wav")
        if wav.exists(): wav.unlink()

@app.get("/api/session")
def api_session(request: Request):
    sid, is_new = _get_or_create_session_id(request)
    ensure_session(sid)
    return {"ok": True, "session_id": sid, "messages": get_messages(sid)}

if __name__ == "__main__":
    import uvicorn

    disable_tls = os.environ.get("DISABLE_TLS", "").strip().lower() in {"1", "true", "yes", "on"}
    ssl_kwargs: dict[str, str] = {}

    # Serve HTTPS by default to satisfy browser secure-context requirements for microphone.
    if not disable_tls:
        ssl_certfile = BASE_DIR / "tls" / "voice_assistant.crt"
        ssl_keyfile = BASE_DIR / "tls" / "voice_assistant.key"
        if ssl_certfile.exists() and ssl_keyfile.exists():
            ssl_kwargs = {
                "ssl_certfile": str(ssl_certfile),
                "ssl_keyfile": str(ssl_keyfile),
            }

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=config.get("port"),
        reload=False,
        **ssl_kwargs,
    )
