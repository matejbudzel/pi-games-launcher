import unittest
from unittest.mock import patch

from launcher import smoke


class AudioSmokeTests(unittest.TestCase):
    def test_audio_uses_stereo_hdmi_tone(self):
        with patch("launcher.smoke.subprocess.run") as run:
            run.return_value.returncode = 0
            with patch("launcher.smoke._wait"):
                smoke.audio()
        self.assertEqual(run.call_args.args[0], ["speaker-test", "-t", "sine", "-f", "440", "-c", "2", "-l", "1"])
