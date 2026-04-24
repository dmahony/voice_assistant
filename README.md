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

- Preferred: Coqui XTTS v2.
- The app uses `/tmp/other-way.wav` as the default speaker reference for XTTS.
- To use your own voice, set `XTTS_SPEAKER_WAV` to a clean mono WAV sample of your voice.
- XTTS can run in two modes:
  - direct subprocess mode via `xtts_synth.py`
  - persistent server mode via `xtts_server.py` for faster replies
- XTTS runs in a separate Python 3.11 helper environment at `xtts-venv/`; install `TTS` there.
- First XTTS use downloads the model automatically and can take a while.
- The app sets `COQUI_TOS_AGREED=1` for the helper process so the model download does not prompt interactively.
- If XTTS is unavailable, the app falls back to Piper, then `espeak-ng` or `espeak`.
- Saved voices are stored under `voices/` and can be selected from the Voice clone panel.
- You can also upload a voice file in the Voice clone panel; non-WAV audio is converted to WAV automatically.

STT:

- Defaults to `faster-whisper` with `base.en`.
- If the model is not already cached locally, pre-download it once before going fully offline.

## Run

```bash
cd /home/dan/voice_assistant
source .venv/bin/activate
python app.py
```

Optional faster XTTS server:

```bash
cd /home/dan/voice_assistant
source xtts-venv/bin/activate
uvicorn xtts_server:app --host 127.0.0.1 --port 8020
```

Run the main app against the server:

```bash
export XTTS_SERVER_URL=http://127.0.0.1:8020/api/tts
python app.py
```

If `tls/voice_assistant.crt` and `tls/voice_assistant.key` exist, the app serves HTTPS on port 8000 automatically.

The certificate is self-signed. On another computer, you must either trust/import `tls/voice_assistant.crt` or use the browser's Advanced/Proceed flow once.

For Android LAN use, install the local CA certificate at `tls/voice_assistant-ca.crt` on the phone first. The browser will then trust `https://172.16.0.200:8000/` and microphone access will work normally.

Recommended flow:

1. Copy `tls/voice_assistant-ca.crt` to the phone.
2. Android Settings → Security → Encryption & credentials → Install a certificate → CA certificate.
3. Install the certificate.
4. Open `https://172.16.0.200:8000/` in Chrome.

For an Android phone connected over USB, plain HTTP on localhost is the simplest option:

```bash
DISABLE_TLS=1 python app.py
adb reverse tcp:8000 tcp:8000
```

Then open `http://127.0.0.1:8000` on the phone. `localhost` counts as a secure context, so microphone access works without certificate warnings.

If you want LAN access over Wi‑Fi instead, keep HTTPS enabled and open `https://<this-machine-LAN-IP>:8000`.

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
- `TTS_BACKEND` – default `xtts`
- `XTTS_MODEL_NAME` – default `tts_models/multilingual/multi-dataset/xtts_v2`
- `XTTS_LANGUAGE` – default `en`
- `XTTS_SPEAKER_WAV` – default `/tmp/other-way.wav`
- `XTTS_DEVICE` – default `cpu`
- `XTTS_PYTHON` – default `xtts-venv/bin/python`
- `XTTS_HELPER` – default `xtts_synth.py`
- `XTTS_SERVER_URL` – default empty; when set, the app uses the persistent XTTS server first
- `XTTS_SERVER_TIMEOUT` – default `600` seconds
- `PIPER_BIN` – default `piper`
- `PIPER_VOICE_MODEL` – path to a Piper voice `.onnx`
- `DISABLE_TLS` – set to `1`/`true` to serve plain HTTP instead of HTTPS

## Browser test flow

1. Open `https://127.0.0.1:8000` on the same machine, or `https://<this-machine-LAN-IP>:8000` from another computer on the network.
2. Trust the self-signed certificate if your browser asks.
3. Use the Voice clone panel to record a sample and give it a name.
4. Click `Start recording`.
5. Allow microphone access.
6. Speak.
7. Click `Stop`.
8. The app uploads audio, transcribes it, sends it to llama-server, and plays the synthesized response.

## Notes

- The app keeps per-session conversation state in memory using a cookie-backed session id.
- Generated TTS audio is written to `tts_out/` and served from `/audio/<filename>`.
- If `llama-server` is not running on port 8080, `/api/health` will report it as unavailable.
