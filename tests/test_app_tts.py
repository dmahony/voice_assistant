from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class AppTtsTests(unittest.TestCase):
    def test_piper_default_is_portable(self):
        env = dict(os.environ)
        env.pop("PIPER_BIN", None)
        with mock.patch.dict(os.environ, env, clear=True):
            sys.modules.pop("app", None)
            app = importlib.import_module("app")
            self.assertEqual(app.PIPER_BIN, "piper")

    def test_xtts_server_is_preferred_before_local_xtts(self):
        sys.modules.pop("app", None)
        import app

        with mock.patch.object(app, "TTS_BACKEND", "xtts"), \
             mock.patch.object(app, "XTTS_SERVER_URL", "http://127.0.0.1:8020/api/tts"), \
             mock.patch.object(app, "_xtts_ready", return_value=True):
            backends = app._available_tts_backends()

        self.assertGreaterEqual(len(backends), 2)
        self.assertEqual(backends[0], "xtts-server")
        self.assertEqual(backends[1], "xtts")

    def test_xtts_server_failure_falls_back_to_subprocess(self):
        sys.modules.pop("app", None)
        import app

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            out_file = out_dir / "session.wav"

            def fake_run(cmd, input=None, check=None, stdout=None, stderr=None, timeout=None, env=None):
                if "--output_file" in cmd:
                    Path(cmd[cmd.index("--output_file") + 1]).write_bytes(b"RIFFTEST")
                return None

            with mock.patch.object(app, "_available_tts_backends", return_value=["xtts-server", "piper"]), \
                 mock.patch.object(app, "_call_xtts_server", side_effect=RuntimeError("server down")), \
                 mock.patch.object(app.subprocess, "run", side_effect=fake_run), \
                 mock.patch.object(app, "TTS_DIR", out_dir):
                result = app._synthesize_speech("hello", "session")
                self.assertEqual(result.parent, out_dir)
                self.assertTrue(result.name.startswith("session_"))
                self.assertTrue(result.name.endswith(".wav"))
                self.assertTrue(result.exists())
                self.assertEqual(result.read_bytes(), b"RIFFTEST")


if __name__ == "__main__":
    unittest.main()
