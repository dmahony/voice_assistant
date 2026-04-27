# Voice Assistant - Windows Setup Guide

This guide explains how to set up and run the Voice Assistant on Windows.

## Quick Start

### Option 1: Run from Source (Recommended for Development)

1. **Install Python 3.10+**
   - Download from https://www.python.org/downloads/
   - During installation, check "Add Python to PATH"

2. **Clone and Setup**
   ```cmd
   git clone https://github.com/dmahony/voice_assistant.git
   cd voice_assistant
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Download Binaries**
   Create the directory structure:
   ```
   voice_assistant\
   └── bin\
       └── windows\
   ```

   Download and place these executables in `bin\windows\`:
   - **ffmpeg.exe**: https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z
     - Extract and copy `ffmpeg.exe` to `bin\windows\`
   - **llama-server.exe**: https://github.com/ggerganov/llama.cpp/releases
     - Download the latest Windows release
     - Copy `llama-server.exe` to `bin\windows\`
   - **piper.exe**: https://github.com/rhasspy/piper/releases
     - Download the latest Windows release
     - Copy `piper.exe` to `bin\windows\`

4. **Download Models**

   **LLM Model (for text generation):**
   - Download a GGUF model from Hugging Face: https://huggingface.co/models?search=gguf
   - Recommended models (CPU-friendly):
     - `Phi-3-mini-4k-instruct-q4.gguf` (~2GB)
     - `Llama-3.2-3B-Instruct-q4.gguf` (~2GB)
     - `Mistral-7B-Instruct-v0.3-q4.gguf` (~4GB)
   - Place in `models\llm\`

   **Piper Voice Model (for text-to-speech):**
   - Download from https://huggingface.co/rhasspy/piper-voices/tree/main/en
   - Recommended: `en-us-lessac-medium.onnx` (~50MB)
   - Place in `models\piper\`

5. **Run**
   ```cmd
   python windows\run_windows.py
   ```

   The app will:
   - Start llama-server.exe (if found)
   - Start the FastAPI backend on http://127.0.0.1:8000
   - Open your browser automatically

### Option 2: Run as Packaged Executable

1. **Build the executable**
   ```cmd
   cd voice_assistant
   pip install pyinstaller
   powershell -ExecutionPolicy Bypass -File windows\build_pyinstaller.ps1
   ```

2. **Download Binaries**
   - Navigate to `dist\voice_assistant\bin\windows\`
   - Download and place the same binaries as above (ffmpeg.exe, llama-server.exe, piper.exe)

3. **Download Models**
   - Place LLM models in `dist\voice_assistant\models\llm\`
   - Place Piper models in `dist\voice_assistant\models\piper\`

4. **Run**
   - Double-click `start.bat` or `voice_assistant.exe`

## Directory Structure

After setup, your directory should look like this:

```
voice_assistant/                    # or dist/voice_assistant/
├── voice_assistant.exe             # Main executable (packaged only)
├── start.bat                       # Quick launcher (packaged only)
├── bin/
│   └── windows/
│       ├── ffmpeg.exe              # Audio conversion
│       ├── llama-server.exe        # LLM inference server
│       └── piper.exe               # Text-to-speech
├── models/
│   ├── llm/
│   │   └── your-model.gguf         # LLM model file
│   └── piper/
│       └── en-us-lessac-medium.onnx  # TTS voice model
├── templates/                     # HTML templates
├── static/                        # Static assets
├── voices/                        # Voice profiles
├── tts_out/                       # Generated audio (auto-created)
├── tts_cache/                     # TTS cache (auto-created)
└── temp/                          # Temporary files (auto-created)
```

## Configuration

You can configure the app through the web UI at http://127.0.0.1:8000/settings

Key settings:
- **LLM Model**: Path to your GGUF model (e.g., `models\llm\your-model.gguf`)
- **Whisper Model**: Speech recognition model (default: `base.en`)
- **TTS Backend**: Choose `piper` for best quality
- **Piper Voice Model**: Path to your ONNX voice model

Or edit `config.local.json` directly:

```json
{
  "llama_model": "models/llm/your-model.gguf",
  "piper_voice_model": "models/piper/en-us-lessac-medium.onnx",
  "whisper_model": "base.en",
  "whisper_device": "cpu",
  "tts_backend": "piper"
}
```

## Troubleshooting

### "ffmpeg.exe not found"
- Ensure `ffmpeg.exe` is in `bin\windows\`
- The app will still work without it, but audio conversion may fail

### "llama-server.exe not found"
- Ensure `llama-server.exe` is in `bin\windows\`
- LLM features won't work without it, but TTS and STT will still function

### "piper.exe not found"
- Ensure `piper.exe` is in `bin\windows\`
- The app will fall back to `espeak` if available, or show no TTS

### "Model not found"
- Check that model paths in settings are correct
- Use forward slashes in paths: `models/llm/model.gguf` (not backslashes)

### Browser doesn't open automatically
- Manually navigate to http://127.0.0.1:8000
- Check that the server started successfully (look for "Uvicorn running" in the console)

### Microphone not working
- Ensure you're using http://127.0.0.1:8000 (localhost)
- Browsers block microphone access on non-localhost HTTP
- Check browser permissions for microphone access

### Slow performance
- Use a smaller LLM model (Phi-3-mini is fast on CPU)
- Use a smaller Whisper model (`tiny.en` instead of `base.en`)
- Close other applications to free up CPU

## CPU-Only Mode (No GPU)

The app is configured to run on CPU by default. This works on any Windows machine.

To enable GPU acceleration (if you have an NVIDIA GPU):
1. Install CUDA Toolkit: https://developer.nvidia.com/cuda-downloads
2. Edit `config.local.json`:
   ```json
   {
     "whisper_device": "cuda",
     "whisper_compute_type": "float16"
   }
   ```
3. For llama-server, add `--n-gpu-layers 35` to the command line (requires editing the launcher)

## Advanced: Custom llama-server Arguments

If you need to pass custom arguments to llama-server, edit `windows/run_windows.py`:

Find this section:
```python
cmd = [
    str(LLAMA_SERVER_EXE),
    "--host", "127.0.0.1",
    "--port", "8080",
    "--model-path", str(models_dir),
    "--ctx-size", "2048",
    "--n-gpu-layers", "0",
]
```

Add or modify arguments as needed. See llama-server documentation for all options.

## Security Notes

- The app runs locally on 127.0.0.1:8000
- No data is sent to external servers (except for initial model downloads)
- All audio processing happens on your machine
- Session data is stored locally in SQLite

## Support

For issues or questions:
- Check the debug page: http://127.0.0.1:8000/debug
- Review console output for error messages
- Open an issue on GitHub: https://github.com/dmahony/voice_assistant/issues

## License

See LICENSE file in the repository.
