import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.local.json"

DEFAULT_CONFIG = {
    "llama_chat_url": "http://127.0.0.1:8080/v1/chat/completions",
    "llama_health_url": "http://127.0.0.1:8080/health",
    "llama_model": "",
    "llama_stream": os.environ.get("LLAMA_STREAM", "1") == "1",
    "system_prompt": "You are a concise offline voice assistant. Reply conversationally, naturally, and briefly.",
    "whisper_model": "base.en",
    "whisper_device": "cpu",
    "whisper_compute_type": "int8",
    "piper_bin": "piper",
    "piper_voice_model": "",
    "tts_backend": "auto",  # auto, piper, espeak-ng, espeak
    "xtts_server_url": "http://127.0.0.1:8020",
    "max_history_messages": 12,
    "hands_free_mode": False,
    "wake_phrase": "computer",
    "push_to_talk_key": " ",
    "http_timeout": 120,
    "port": 8000
}

class Config:
    def __init__(self):
        self._config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        # 1. Load from file if exists
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    file_config = json.load(f)
                    self._config.update(file_config)
            except Exception as e:
                print(f"Error loading config file: {e}")

        # 2. Override with env vars
        # Map env vars to config keys
        env_map = {
            "LLAMA_CHAT_URL": "llama_chat_url",
            "LLAMA_HEALTH_URL": "llama_health_url",
            "LLAMA_MODEL": "llama_model",
            "LLAMA_STREAM": "llama_stream",
            "VOICE_ASSISTANT_SYSTEM_PROMPT": "system_prompt",
            "WHISPER_MODEL": "whisper_model",
            "WHISPER_DEVICE": "whisper_device",
            "WHISPER_COMPUTE_TYPE": "whisper_compute_type",
            "PIPER_BIN": "piper_bin",
            "PIPER_VOICE_MODEL": "piper_voice_model",
            "MAX_HISTORY_MESSAGES": "max_history_messages",
            "LLAMA_TIMEOUT": "http_timeout",
            "PORT": "port"
        }

        for env_key, config_key in env_map.items():
            val = os.environ.get(env_key)
            if val is not None:
                if isinstance(self._config[config_key], bool):
                    self._config[config_key] = val.lower() in ("true", "1", "yes")
                elif isinstance(self._config[config_key], int):
                    self._config[config_key] = int(val)
                elif isinstance(self._config[config_key], float):
                    self._config[config_key] = float(val)
                else:
                    self._config[config_key] = val

    def save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key, default=None):
        return self._config.get(key, default)

    def set(self, key, value):
        self._config[key] = value
        self.save()

    def to_dict(self):
        return self._config.copy()

config = Config()
