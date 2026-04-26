# Offline Voice Assistant

A browser-based voice assistant that runs entirely locally.

## Features
- **Hands-free / VAD Mode**: Automatically detects speech and silence.
- **Streaming LLM Replies**: Shows text as it's generated.
- **Sentence-by-Sentence TTS**: Starts speaking the first sentence immediately while the rest is still generating.
- **Wake Word Support**: Optional wake phrase (default: "computer").
- **Push-to-Talk**: Use a keyboard shortcut (default: Spacebar) to talk.
- **Safe Local Tools**: Get time, check health, disk usage, etc.
- **Persistent Memory**: SQLite-backed session and message history.
- **Settings & Debug Pages**: Configure backend URLs, models, and monitor system health.
- **Optimized Pipeline**: TTS caching and automatic cleanup of old audio files.

## Tech Stack
- **Frontend**: Vanilla JS, Web Audio API, WebRTC MediaRecorder.
- **Backend**: FastAPI, Python 3.10+.
- **STT**: `faster-whisper`.
- **LLM**: `llama.cpp` (llama-server) or any OpenAI-compatible API.
- **TTS**: `Piper`, `espeak-ng`, or `espeak`.

## Installation

1. **Clone the repo**:
   ```bash
   git clone https://github.com/dmahony/voice_assistant.git
   cd voice_assistant
   ```

2. **Setup virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Install System Dependencies**:
   - `ffmpeg` (for audio conversion)
   - `piper` (recommended) or `espeak-ng`

4. **Run**:
   ```bash
   python app.py
   ```

## Configuration
Settings can be changed in the UI under the "Settings" page or via `config.local.json`.
Environment variables also override settings:
- `LLAMA_CHAT_URL`: Endpoint for chat completions.
- `WHISPER_MODEL`: Model size (tiny.en, base.en, etc.).
- `LLAMA_STREAM`: Set to `1` for streaming.

## Development / Debugging
Visit `/debug` to see backend health, recent errors, and status of each component.

## Troubleshooting
- **Microphone not working**: Ensure you are using HTTPS or `localhost`. Browsers block mic access on insecure non-local origins.
- **No TTS output**: Verify `piper` is in your PATH or check the TTS backend setting.
- **Slow responses**: Use a smaller Whisper model (tiny.en) or enable streaming.
