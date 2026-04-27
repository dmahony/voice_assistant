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

    # PyTorch 2.6+ defaults to weights_only=True in torch.load, which breaks
    # Coqui/TTS checkpoints that contain custom config objects.
    # Force weights_only=False for this process.
    try:
        import torch

        _orig_torch_load = torch.load

        def _torch_load_weights_only_false(*args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return _orig_torch_load(*args, **kwargs)

        torch.load = _torch_load_weights_only_false  # type: ignore[assignment]
    except Exception:
        pass

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

