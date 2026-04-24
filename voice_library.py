from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VOICE_LIBRARY_DIRNAME = "voices"
VOICE_INDEX_FILENAME = "index.json"
VOICE_REFERENCE_FILENAME = "reference.wav"
DEFAULT_LIBRARY: dict[str, Any] = {"active_voice_id": None, "voices": []}


def normalize_voice_name(name: str) -> str:
    return " ".join(name.strip().split())


def slugify_voice_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_voice_name(name).lower()).strip("-")
    return slug or "voice"


def voice_library_dir(base_dir: Path) -> Path:
    return base_dir / VOICE_LIBRARY_DIRNAME


def voice_index_path(base_dir: Path) -> Path:
    return voice_library_dir(base_dir) / VOICE_INDEX_FILENAME


def voice_profile_dir(base_dir: Path, voice_id: str) -> Path:
    return voice_library_dir(base_dir) / voice_id


def voice_reference_path(base_dir: Path, voice_id: str) -> Path:
    return voice_profile_dir(base_dir, voice_id) / VOICE_REFERENCE_FILENAME


def _default_library() -> dict[str, Any]:
    return {"active_voice_id": None, "voices": []}


def _coerce_library(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return _default_library()
    voices = data.get("voices", [])
    if not isinstance(voices, list):
        voices = []
    active_voice_id = data.get("active_voice_id")
    if active_voice_id is not None and not isinstance(active_voice_id, str):
        active_voice_id = None
    return {"active_voice_id": active_voice_id, "voices": voices}


def load_voice_library(base_dir: Path) -> dict[str, Any]:
    index = voice_index_path(base_dir)
    if not index.exists():
        return _default_library()
    try:
        return _coerce_library(json.loads(index.read_text(encoding="utf-8")))
    except Exception:
        return _default_library()


def save_voice_library(base_dir: Path, library: dict[str, Any]) -> None:
    library_dir = voice_library_dir(base_dir)
    library_dir.mkdir(parents=True, exist_ok=True)
    index = voice_index_path(base_dir)
    index.write_text(json.dumps(_coerce_library(library), indent=2, sort_keys=True), encoding="utf-8")


def _voice_exists(base_dir: Path, voice_id: str) -> bool:
    return any(profile["id"] == voice_id for profile in load_voice_library(base_dir)["voices"])


def list_voice_profiles(base_dir: Path) -> list[dict[str, Any]]:
    library = load_voice_library(base_dir)
    active_voice_id = library.get("active_voice_id")
    voices: list[dict[str, Any]] = []
    for profile in library.get("voices", []):
        if not isinstance(profile, dict):
            continue
        item = dict(profile)
        item["selected"] = item.get("id") == active_voice_id
        item["wav_exists"] = Path(item.get("wav_path", "")).exists()
        voices.append(item)
    return voices


def convert_audio_to_voice_wav(source_path: Path, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-ac",
        "1",
        "-ar",
        "24000",
        "-sample_fmt",
        "s16",
        "-vn",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


def create_voice_profile(base_dir: Path, name: str, source_path: Path) -> dict[str, Any]:
    normalized_name = normalize_voice_name(name)
    if not normalized_name:
        raise ValueError("Voice name is required")
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    library = load_voice_library(base_dir)
    voice_id = f"{slugify_voice_name(normalized_name)}-{uuid.uuid4().hex[:8]}"
    reference_path = voice_reference_path(base_dir, voice_id)
    convert_audio_to_voice_wav(source_path, reference_path)

    profile = {
        "id": voice_id,
        "name": normalized_name,
        "slug": slugify_voice_name(normalized_name),
        "wav_path": str(reference_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    library.setdefault("voices", []).append(profile)
    library["active_voice_id"] = voice_id
    save_voice_library(base_dir, library)
    return profile


def get_voice_profile(base_dir: Path, voice_id: str) -> dict[str, Any] | None:
    for profile in load_voice_library(base_dir)["voices"]:
        if isinstance(profile, dict) and profile.get("id") == voice_id:
            item = dict(profile)
            item["selected"] = True
            item["wav_exists"] = Path(item.get("wav_path", "")).exists()
            return item
    return None


def select_voice_profile(base_dir: Path, voice_id: str) -> dict[str, Any]:
    library = load_voice_library(base_dir)
    if not _voice_exists(base_dir, voice_id):
        raise KeyError(voice_id)
    library["active_voice_id"] = voice_id
    save_voice_library(base_dir, library)
    profile = get_voice_profile(base_dir, voice_id)
    if profile is None:
        raise KeyError(voice_id)
    return profile


def delete_voice_profile(base_dir: Path, voice_id: str) -> None:
    library = load_voice_library(base_dir)
    voices = [profile for profile in library.get("voices", []) if isinstance(profile, dict) and profile.get("id") != voice_id]
    if len(voices) == len(library.get("voices", [])):
        raise KeyError(voice_id)

    profile_dir = voice_profile_dir(base_dir, voice_id)
    if profile_dir.exists():
        shutil.rmtree(profile_dir)

    library["voices"] = voices
    if library.get("active_voice_id") == voice_id:
        library["active_voice_id"] = voices[0]["id"] if voices else None
    save_voice_library(base_dir, library)


def resolve_xtts_speaker_wav(base_dir: Path, default_wav: Path) -> Path:
    library = load_voice_library(base_dir)
    active_voice_id = library.get("active_voice_id")
    if active_voice_id:
        profile = get_voice_profile(base_dir, active_voice_id)
        if profile is not None:
            wav_path = Path(profile["wav_path"])
            if wav_path.exists():
                return wav_path
    return default_wav
