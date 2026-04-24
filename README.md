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
- The app uses `test.wav` as the default speaker reference for XTTS.
- To use your own voice, set `XTTS_SPEAKER_WAV` to a clean mono WAV sample of your voice.
- XTTS runs in a separate Python 3.11 helper environment at `xtts-venv/`; install `TTS` there.
- First XTTS use downloads the model automatically and can take a while.
- The app sets `COQUI_TOS_AGREED=1` for the helper process so the model download does not prompt interactively.
- If XTTS is unavailable, the app falls back to Piper, then `espeak-ng` or `espeak`.

STT:

- Defaults to `faster-whisper` with `base.en`.
- If the model is not already cached locally, pre-download it once before going fully offline.

## Run

```bash
cd /home/dan/voice_assistant
source .venv/bin/activate
python app.py
```

If `tls/voice_assistant.crt` and `tls/voice_assistant.key` exist, the app serves HTTPS on port 8000 automatically.

The certificate is self-signed. On another computer, you must either trust/import `tls/voice_assistant.crt` or use the browser's Advanced/Proceed flow once.


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
- `XTTS_SPEAKER_WAV` – default `test.wav`
- `XTTS_DEVICE` – default `cpu`
- `XTTS_PYTHON` – default `xtts-venv/bin/python`
- `XTTS_HELPER` – default `xtts_synth.py`
- `PIPER_BIN` – default `piper`
- `PIPER_VOICE_MODEL` – path to a Piper voice `.onnx`

## Browser test flow

1. Open `http://127.0.0.1:8000` on the same machine, or `http://<this-machine-LAN-IP>:8000` from another computer on the network.
2. Click `Start recording`.
3. Allow microphone access.
4. Speak.
5. Click `Stop`.
6. The app uploads audio, transcribes it, sends it to llama-server, and plays the synthesized response.

## Notes

- The app keeps per-session conversation state in memory using a cookie-backed session id.
- Generated TTS audio is written to `tts_out/` and served from `/audio/<filename>`.
- If `llama-server` is not running on port 8080, `/api/health` will report it as unavailable.
