from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from voice_library import (
    create_voice_profile,
    delete_voice_profile,
    list_voice_profiles,
    resolve_xtts_speaker_wav,
    select_voice_profile,
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
TEMP_DIR = BASE_DIR / "temp"
TTS_DIR = BASE_DIR / "tts_out"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
TTS_DIR.mkdir(parents=True, exist_ok=True)

LLAMA_CHAT_URL = os.environ.get("LLAMA_CHAT_URL", "http://127.0.0.1:8080/v1/chat/completions")
LLAMA_HEALTH_URL = os.environ.get("LLAMA_HEALTH_URL", "http://127.0.0.1:8080/health")
LLAMA_MODEL = os.environ.get("LLAMA_MODEL", "")
SYSTEM_PROMPT = os.environ.get(
    "VOICE_ASSISTANT_SYSTEM_PROMPT",
    "You are a concise offline voice assistant. Reply conversationally, naturally, and briefly.",
)
WHISPER_MODEL_NAME = os.environ.get("WHISPER_MODEL", "base.en")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_DOWNLOAD_ROOT = os.environ.get("WHISPER_DOWNLOAD_ROOT")
PIPER_BIN = os.environ.get("PIPER_BIN", "/home/dan/voice_assistant_app/home/dan/voice_assistant/venv/bin/piper")
PIPER_VOICE_MODEL = os.environ.get("PIPER_VOICE_MODEL", "")
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_HISTORY_MESSAGES", "12"))
HTTP_TIMEOUT = float(os.environ.get("LLAMA_TIMEOUT", "120"))
TTS_BACKEND = os.environ.get("TTS_BACKEND", "xtts").strip().lower()
XTTS_MODEL_NAME = os.environ.get(
    "XTTS_MODEL_NAME",
    "tts_models/multilingual/multi-dataset/xtts_v2",
)
XTTS_LANGUAGE = os.environ.get("XTTS_LANGUAGE", "en")
XTTS_SPEAKER_WAV = os.environ.get("XTTS_SPEAKER_WAV", "/tmp/other-way.wav")
XTTS_DEVICE = os.environ.get("XTTS_DEVICE", "cpu")
XTTS_PYTHON = os.environ.get("XTTS_PYTHON", str(BASE_DIR / "xtts-venv" / "bin" / "python"))
XTTS_HELPER = os.environ.get("XTTS_HELPER", str(BASE_DIR / "xtts_synth.py"))
SSL_CERTFILE = os.environ.get("SSL_CERTFILE", str(BASE_DIR / "tls" / "voice_assistant.crt"))
SSL_KEYFILE = os.environ.get("SSL_KEYFILE", str(BASE_DIR / "tls" / "voice_assistant.key"))

app = FastAPI(title="Offline Voice Assistant", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost", "http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/audio", StaticFiles(directory=str(TTS_DIR)), name="audio")

_session_lock = threading.Lock()
_sessions: dict[str, dict[str, Any]] = {}
_whisper_lock = threading.Lock()
_whisper_model = None


def _new_session_id() -> str:
    return secrets.token_urlsafe(18)


def _get_or_create_session_id(request: Request) -> tuple[str, bool]:
    sid = request.cookies.get("voice_session_id")
    if sid:
        return sid, False
    return _new_session_id(), True


def _ensure_session(session_id: str) -> dict[str, Any]:
    with _session_lock:
        if session_id not in _sessions:
            _sessions[session_id] = {
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
                "created_at": time.time(),
                "last_seen": time.time(),
            }
        _sessions[session_id]["last_seen"] = time.time()
        return _sessions[session_id]


def _trim_history(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    if not messages:
        return [{"role": "system", "content": SYSTEM_PROMPT}]
    system = messages[0]
    tail = messages[1:]
    if len(tail) <= MAX_HISTORY_MESSAGES:
        return [system] + tail
    return [system] + tail[-MAX_HISTORY_MESSAGES:]


def _load_whisper_model():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model
        from faster_whisper import WhisperModel

        kwargs: dict[str, Any] = {
            "device": WHISPER_DEVICE,
            "compute_type": WHISPER_COMPUTE_TYPE,
        }
        if WHISPER_DOWNLOAD_ROOT:
            kwargs["download_root"] = WHISPER_DOWNLOAD_ROOT
        _whisper_model = WhisperModel(WHISPER_MODEL_NAME, **kwargs)
        return _whisper_model


def _convert_to_wav(input_path: Path) -> Path:
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
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


def _transcribe_audio(audio_path: Path) -> str:
    wav_path = _convert_to_wav(audio_path)
    model = _load_whisper_model()
    segments, info = model.transcribe(
        str(wav_path),
        language="en",
        vad_filter=True,
        beam_size=1,
    )
    text_parts: list[str] = []
    for segment in segments:
        piece = (segment.text or "").strip()
        if piece:
            text_parts.append(piece)
    transcript = " ".join(text_parts).strip()
    return transcript


def _call_llama_server(messages: list[dict[str, str]]) -> str:
    payload: dict[str, Any] = {
        "messages": messages,
        "temperature": 0.4,
        "stream": False,
    }
    if LLAMA_MODEL:
        payload["model"] = LLAMA_MODEL
    response = requests.post(LLAMA_CHAT_URL, json=payload, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"llama-server returned no choices: {json.dumps(data)[:500]}")
    message = choices[0].get("message", {})
    reply = (message.get("content") or "").strip()
    if not reply:
        raise RuntimeError("llama-server returned an empty assistant reply")
    return reply


def _current_xtts_speaker_wav() -> Path:
    default_wav = Path(XTTS_SPEAKER_WAV)
    return resolve_xtts_speaker_wav(BASE_DIR, default_wav)


def _xtts_ready() -> bool:
    python_ok = Path(XTTS_PYTHON).exists() or shutil.which(XTTS_PYTHON) is not None
    return python_ok and Path(XTTS_HELPER).exists() and _current_xtts_speaker_wav().exists()


def _available_tts_backends() -> list[str]:
    backends: list[str] = []
    if TTS_BACKEND in {"xtts", "auto"} and _xtts_ready():
        backends.append("xtts")
    if bool(PIPER_VOICE_MODEL) and shutil.which(PIPER_BIN) is not None and Path(PIPER_VOICE_MODEL).exists():
        backends.append("piper")
    if shutil.which("espeak-ng"):
        backends.append("espeak-ng")
    if shutil.which("espeak"):
        backends.append("espeak")
    return backends


def _find_tts_backend() -> str | None:
    backends = _available_tts_backends()
    return backends[0] if backends else None


def _synthesize_speech(text: str, session_id: str) -> Path:
    out_file = TTS_DIR / f"{session_id}_{uuid.uuid4().hex}.wav"
    backends = _available_tts_backends()
    if not backends:
        raise RuntimeError("No offline TTS backend found. Install Coqui XTTS, Piper, or espeak/espeak-ng.")

    errors: list[str] = []
    for backend in backends:
        try:
            if backend == "xtts":
                gpu_flag = [] if XTTS_DEVICE.lower() in {"cpu", "false", "0", "no"} else ["--gpu"]
                cmd = [
                    XTTS_PYTHON,
                    XTTS_HELPER,
                    "--model-name",
                    XTTS_MODEL_NAME,
                    "--speaker-wav",
                    str(_current_xtts_speaker_wav()),
                    "--language",
                    XTTS_LANGUAGE,
                    "--output",
                    str(out_file),
                ] + gpu_flag
                env = os.environ.copy()
                env["COQUI_TOS_AGREED"] = "1"
                subprocess.run(
                    cmd,
                    input=text.encode("utf-8"),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    timeout=600,
                )
                return out_file
            if backend == "piper":
                cmd = [PIPER_BIN, "--model", PIPER_VOICE_MODEL, "--output_file", str(out_file)]
                subprocess.run(
                    cmd,
                    input=text.encode("utf-8"),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120,
                )
                return out_file
            cmd = [backend, "-w", str(out_file), text]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            return out_file
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace").strip()
            details = stderr or stdout or str(exc)
            errors.append(f"{backend}: {details}")

    raise RuntimeError("All offline TTS backends failed: " + " | ".join(errors))


def _chat_with_session(session_id: str, transcript: str) -> dict[str, str | None]:
    session = _ensure_session(session_id)
    messages = list(session["messages"])
    messages.append({"role": "user", "content": transcript})
    messages = _trim_history(messages)
    assistant_reply = _call_llama_server(messages)
    messages.append({"role": "assistant", "content": assistant_reply})
    with _session_lock:
        session["messages"] = messages
    audio_path = _synthesize_speech(assistant_reply, session_id)
    return {
        "transcript": transcript,
        "assistant_reply": assistant_reply,
        "audio_url": f"/audio/{audio_path.name}",
        "session_id": session_id,
    }


@app.get("/")
def index(request: Request):
    file_path = TEMPLATES_DIR / "index.html"
    response = FileResponse(str(file_path), media_type="text/html")
    session_id, is_new = _get_or_create_session_id(request)
    _ensure_session(session_id)
    if is_new:
        response.set_cookie(
            key="voice_session_id",
            value=session_id,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )
    return response


@app.get("/api/health")
def health():
    llama_status = {
        "ok": False,
        "error": None,
    }
    try:
        r = requests.get(LLAMA_HEALTH_URL, timeout=5)
        llama_status["ok"] = r.ok
        if not r.ok:
            llama_status["error"] = f"HTTP {r.status_code}"
    except Exception as exc:
        llama_status["error"] = str(exc)
    return {
        "ok": True,
        "llama_server": llama_status,
        "whisper_model": WHISPER_MODEL_NAME,
        "tts_backend": _find_tts_backend(),
        "xtts_model": XTTS_MODEL_NAME,
        "active_voice_wav": str(_current_xtts_speaker_wav()),
        "voice_count": len(list_voice_profiles(BASE_DIR)),
    }


@app.post("/api/chat")
async def api_chat(request: Request, audio: UploadFile = File(...)):
    session_id, is_new = _get_or_create_session_id(request)
    _ensure_session(session_id)

    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    input_path = TEMP_DIR / f"{session_id}_{uuid.uuid4().hex}{suffix}"
    with input_path.open("wb") as f:
        f.write(await audio.read())

    try:
        transcript = _transcribe_audio(input_path)
        if not transcript:
            return JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "No speech detected. Try again with a louder recording.",
                    "session_id": session_id,
                },
            )
        result = _chat_with_session(session_id, transcript)
        payload = {
            "ok": True,
            "transcript": result["transcript"],
            "assistant_reply": result["assistant_reply"],
            "audio_url": result["audio_url"],
            "session_id": result["session_id"],
        }
        response = JSONResponse(payload)
        if is_new:
            response.set_cookie(
                key="voice_session_id",
                value=session_id,
                httponly=True,
                samesite="lax",
                max_age=60 * 60 * 24 * 30,
            )
        return response
    except subprocess.CalledProcessError as exc:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": f"Audio conversion or TTS failed: {exc}",
                "session_id": session_id,
            },
        )
    except requests.HTTPError as exc:
        return JSONResponse(
            status_code=502,
            content={
                "ok": False,
                "error": f"llama-server error: {exc}",
                "session_id": session_id,
            },
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={
                "ok": False,
                "error": str(exc),
                "session_id": session_id,
            },
        )
    finally:
        for path in (input_path, input_path.with_suffix(".wav")):
            try:
                if path.exists():
                    path.unlink()
            except Exception:
                pass


@app.get("/api/session")
def api_session(request: Request):
    session_id, is_new = _get_or_create_session_id(request)
    session = _ensure_session(session_id)
    response = JSONResponse(
        {
            "ok": True,
            "session_id": session_id,
            "messages": session["messages"],
        }
    )
    if is_new:
        response.set_cookie(
            key="voice_session_id",
            value=session_id,
            httponly=True,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )
    return response


@app.get("/api/voices")
def api_voices():
    library = list_voice_profiles(BASE_DIR)
    return {
        "ok": True,
        "voices": library,
        "active_voice_id": next((voice["id"] for voice in library if voice.get("selected")), None),
        "speaker_wav": str(_current_xtts_speaker_wav()),
    }


@app.post("/api/voices")
async def api_create_voice(name: str = Form(...), audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "voice.webm").suffix or ".webm"
    input_path = TEMP_DIR / f"voice_{uuid.uuid4().hex}{suffix}"
    with input_path.open("wb") as f:
        f.write(await audio.read())

    try:
        profile = create_voice_profile(BASE_DIR, name, input_path)
        return {
            "ok": True,
            "voice": profile,
            "voices": list_voice_profiles(BASE_DIR),
            "speaker_wav": str(_current_xtts_speaker_wav()),
        }
    except Exception as exc:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})
    finally:
        try:
            if input_path.exists():
                input_path.unlink()
        except Exception:
            pass


@app.post("/api/voices/select")
def api_select_voice(voice_id: str = Form(...)):
    try:
        profile = select_voice_profile(BASE_DIR, voice_id)
        return {
            "ok": True,
            "voice": profile,
            "voices": list_voice_profiles(BASE_DIR),
            "speaker_wav": str(_current_xtts_speaker_wav()),
        }
    except KeyError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Voice not found"})


@app.delete("/api/voices/{voice_id}")
def api_delete_voice(voice_id: str):
    try:
        delete_voice_profile(BASE_DIR, voice_id)
        return {"ok": True, "voices": list_voice_profiles(BASE_DIR), "speaker_wav": str(_current_xtts_speaker_wav())}
    except KeyError:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Voice not found"})


if __name__ == "__main__":
    import uvicorn

    ssl_kwargs: dict[str, str] = {}
    if Path(SSL_CERTFILE).exists() and Path(SSL_KEYFILE).exists():
        ssl_kwargs = {
            "ssl_certfile": SSL_CERTFILE,
            "ssl_keyfile": SSL_KEYFILE,
        }

    uvicorn.run(
        "app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
        **ssl_kwargs,
    )
