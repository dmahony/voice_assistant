from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import voice_library as vl


def _fake_ffmpeg_run_factory(output_bytes: bytes = b'RIFFTEST'):
    def _fake_run(cmd, check, stdout=None, stderr=None):
        out_path = Path(cmd[-1])
        out_path.write_bytes(output_bytes)
        return None

    return _fake_run


class VoiceLibraryTests(unittest.TestCase):
    def test_create_voice_profile_saves_reference_and_selects_first_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src = base / 'sample.webm'
            src.write_bytes(b'not-a-real-webm-but-good-enough-for-a-mocked-test')

            with mock.patch.object(vl.subprocess, 'run', side_effect=_fake_ffmpeg_run_factory()):
                profile = vl.create_voice_profile(base, ' Colonel  Voice ', src)

            self.assertEqual(profile['name'], 'Colonel Voice')
            self.assertTrue(profile['id'].startswith('colonel-voice-'))
            self.assertTrue(profile['wav_path'].endswith('reference.wav'))
            self.assertTrue(Path(profile['wav_path']).exists())
            self.assertEqual(Path(profile['wav_path']).read_bytes(), b'RIFFTEST')

            library = vl.load_voice_library(base)
            self.assertEqual(library['active_voice_id'], profile['id'])
            self.assertEqual(len(library['voices']), 1)
            self.assertEqual(library['voices'][0]['name'], 'Colonel Voice')

    def test_select_voice_profile_switches_active_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            src1 = base / 'one.webm'
            src2 = base / 'two.webm'
            src1.write_bytes(b'1')
            src2.write_bytes(b'2')

            with mock.patch.object(vl.subprocess, 'run', side_effect=_fake_ffmpeg_run_factory()):
                first = vl.create_voice_profile(base, 'Alpha', src1)
                second = vl.create_voice_profile(base, 'Bravo', src2)

            vl.select_voice_profile(base, second['id'])
            library = vl.load_voice_library(base)
            self.assertEqual(library['active_voice_id'], second['id'])
            self.assertEqual(vl.resolve_xtts_speaker_wav(base, Path('/tmp/default.wav')), Path(second['wav_path']))
            self.assertEqual(vl.list_voice_profiles(base)[0]['name'], 'Alpha')
            self.assertEqual(first['name'], 'Alpha')

    def test_resolve_xtts_speaker_wav_falls_back_when_no_active_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            default = Path('/tmp/default.wav')
            self.assertEqual(vl.resolve_xtts_speaker_wav(Path(tmp), default), default)

    def test_convert_audio_to_voice_wav_surfaces_ffmpeg_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / 'sample.mp3'
            source.write_bytes(b'not-an-mp3-but-good-enough-for-a-failing-test')
            output = base / 'out.wav'

            exc = vl.subprocess.CalledProcessError(1, ['ffmpeg'], stderr=b'invalid input format')
            with mock.patch.object(vl.subprocess, 'run', side_effect=exc):
                with self.assertRaisesRegex(RuntimeError, 'invalid input format'):
                    vl.convert_audio_to_voice_wav(source, output)


if __name__ == '__main__':
    unittest.main()
