# Offline Voice Assistant

A local browser-based voice chat app that records microphone audio in the browser, transcribes it locally, sends the text to a local llama-server, synthesizes a spoken reply locally, and plays the response in the browser.

## Files

- `app.py` – FastAPI backend
- `requirements.txt` – Python dependencies
- `templates/index.html` – main page
- `static/app.js` – browser recording / upload / playback logic
- `static/style.css` – minimal UI styling

## Install

```bash
cd /home/dan/voice_assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

System packages:

```bash
sudo apt install ffmpeg
```

TTS:

- Preferred: install Piper and set `PIPER_VOICE_MODEL` to a local `.onnx` voice file.
- Fallback: if Piper is unavailable, the app will try `espeak-ng` or `espeak`.

STT:

- Defaults to `faster-whisper` with `base.en`.
- If the model is not already cached locally, pre-download it once before going fully offline.

## Run

```bash
cd /home/dan/voice_assistant
source .venv/bin/activate
uvicorn app:app --host 127.0.0.1 --port 8000
```

If port 8000 is busy, use another port:

```bash
PORT=8001 uvicorn app:app --host 127.0.0.1 --port 8001
```

## Environment variables

- `LLAMA_CHAT_URL` – default `http://127.0.0.1:8080/v1/chat/completions`
- `LLAMA_HEALTH_URL` – default `http://127.0.0.1:8080/health`
- `LLAMA_MODEL` – optional model name to send to llama-server
- `WHISPER_MODEL` – default `base.en`
- `WHISPER_DEVICE` – default `cpu`
- `WHISPER_COMPUTE_TYPE` – default `int8`
- `PIPER_BIN` – default `piper`
- `PIPER_VOICE_MODEL` – path to a Piper voice `.onnx`

## Browser test flow

1. Open `http://127.0.0.1:8000` or whichever port you launched.
2. Click `Start recording`.
3. Allow microphone access.
4. Speak.
5. Click `Stop`.
6. The app uploads audio, transcribes it, sends it to llama-server, and plays the synthesized response.

## Notes

- The app keeps per-session conversation state in memory using a cookie-backed session id.
- Generated TTS audio is written to `tts_out/` and served from `/audio/<filename>`.
- If `llama-server` is not running on port 8080, `/api/health` will report it as unavailable.
