import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class ApplianceTests(unittest.TestCase):
    def test_installer_updates_clean_clone_and_latest_sdl(self):
        source = (ROOT / "scripts" / "install-dietpi.sh").read_text()
        self.assertIn('git -C "$repo" pull --ff-only', source)
        self.assertIn('install-sdl12-fbcon-release.sh', source)
        self.assertIn('pi-286-games.service', source)

    def test_boot_setup_reboots_after_panic_and_keeps_console_quiet(self):
        source = (ROOT / "scripts" / "configure-appliance-boot.sh").read_text()
        for setting in ("quiet", "logo.nologo", "loglevel=3", "panic=10"):
            self.assertIn(setting, source)

    def test_menu_has_diagnostics_shutdown_and_ctrl_c_escape(self):
        source = (ROOT / "launcher" / "main.py").read_text()
        for item in ("Test obrazu framebufferu", "Test HDMI zvuku", '"Koniec"', 'key == "CTRL_C"'):
            self.assertIn(item, source)
