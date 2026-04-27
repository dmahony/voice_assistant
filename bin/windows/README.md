# Place Windows binaries here

Download these executables and place them in this directory:

## ffmpeg.exe
Audio conversion tool
Download: https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z
Extract and copy ffmpeg.exe here

## llama-server.exe
LLM inference server
Download: https://github.com/ggerganov/llama.cpp/releases
Download the latest Windows release and copy llama-server.exe here

## piper.exe
Text-to-speech engine
Download: https://github.com/rhasspy/piper/releases
Download the latest Windows release and copy piper.exe here

Note: These binaries are optional. The app will work without them, but features will be limited:
- Without ffmpeg.exe: Audio conversion may fail
- Without llama-server.exe: LLM features won't work
- Without piper.exe: TTS will fall back to espeak or won't work
