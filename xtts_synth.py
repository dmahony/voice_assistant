from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate TTS audio with Coqui XTTS")
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--speaker-wav", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--gpu", action="store_true")
    args = parser.parse_args()

    text = sys.stdin.read().strip()
    if not text:
        raise SystemExit("No input text received on stdin")

    speaker_wav = Path(args.speaker_wav)
    if not speaker_wav.exists():
        raise SystemExit(f"Speaker wav not found: {speaker_wav}")

    try:
        from TTS.api import TTS
    except Exception as exc:
        raise SystemExit(f"Coqui TTS is not installed in this environment: {exc}") from exc

    tts = TTS(model_name=args.model_name, progress_bar=False, gpu=args.gpu)
    tts.tts_to_file(
        text=text,
        speaker_wav=str(speaker_wav),
        language=args.language,
        file_path=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
