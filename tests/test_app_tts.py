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

    def test_api_voices_accepts_uploaded_non_wav_file(self):
        sys.modules.pop("app", None)
        import app
        from fastapi.testclient import TestClient

        client = TestClient(app.app)

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            upload_bytes = b'fake mp3 bytes'

            def fake_create_voice_profile(base_dir, name, source_path):
                self.assertEqual(base_dir, base)
                self.assertEqual(name, 'Upload Voice')
                self.assertEqual(source_path.suffix, '.mp3')
                self.assertTrue(source_path.exists())
                self.assertEqual(source_path.read_bytes(), upload_bytes)
                return {'id': 'voice-1', 'name': name, 'wav_path': str(base / 'voices' / 'voice-1' / 'reference.wav')}

            with mock.patch.object(app, 'BASE_DIR', base), \
                 mock.patch.object(app, 'create_voice_profile', side_effect=fake_create_voice_profile), \
                 mock.patch.object(app, 'list_voice_profiles', return_value=[]):
                response = client.post(
                    '/api/voices',
                    data={'name': 'Upload Voice'},
                    files={'audio': ('sample.mp3', upload_bytes, 'audio/mpeg')},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['voice']['name'], 'Upload Voice')


if __name__ == '__main__':
    unittest.main()

