from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

XTTS_MODEL_NAME = os.environ.get(
    "XTTS_MODEL_NAME",
    "tts_models/multilingual/multi-dataset/xtts_v2",
)
XTTS_LANGUAGE = os.environ.get("XTTS_LANGUAGE", "en")
XTTS_DEVICE = os.environ.get("XTTS_DEVICE", "cpu")

app = FastAPI(title="XTTS Server", version="1.0.0")

_model_lock = threading.Lock()
_xtts_model = None


class TTSRequest(BaseModel):
    text: str
    speaker_wav: str
    language: str
    output_path: str


def _load_xtts_model():
    global _xtts_model
    if _xtts_model is not None:
        return _xtts_model
    with _model_lock:
        if _xtts_model is not None:
            return _xtts_model
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        try:
            from TTS.api import TTS
        except Exception as exc:
            raise RuntimeError(f"Coqui TTS is not installed in this environment: {exc}") from exc

        gpu = XTTS_DEVICE.lower() not in {"cpu", "false", "0", "no"}
        _xtts_model = TTS(model_name=XTTS_MODEL_NAME, progress_bar=False, gpu=gpu)
        return _xtts_model


@app.on_event("startup")
def _startup() -> None:
    _load_xtts_model()


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "model": XTTS_MODEL_NAME}


@app.post("/api/tts")
def api_tts(payload: TTSRequest) -> dict[str, object]:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    speaker_wav = Path(payload.speaker_wav)
    if not speaker_wav.exists():
        raise HTTPException(status_code=400, detail=f"speaker_wav not found: {speaker_wav}")

    output_path = Path(payload.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        model = _load_xtts_model()
        model.tts_to_file(
            text=text,
            speaker_wav=str(speaker_wav),
            language=payload.language or XTTS_LANGUAGE,
            file_path=str(output_path),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"ok": True, "output_path": str(output_path)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("xtts_server:app", host="127.0.0.1", port=8020, reload=False)
