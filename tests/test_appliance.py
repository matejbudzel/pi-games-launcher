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

    def test_audio_configuration_quotes_the_named_alsa_card(self):
        source = (ROOT / "scripts" / "configure-appliance-audio.sh").read_text()
        self.assertIn('defaults.pcm.card "snd_bcm2835"', source)
        self.assertIn('defaults.ctl.card "snd_bcm2835"', source)

    def test_menu_has_diagnostics_shutdown_and_ctrl_c_escape(self):
        source = (ROOT / "launcher" / "main.py").read_text()
        for item in ("Test obrazu framebufferu", "Test HDMI zvuku", '"Koniec"', 'key == "CTRL_C"', "confirm_shutdown"):
            self.assertIn(item, source)

    def test_provider_problems_stay_out_of_the_menu_and_logs_use_journal(self):
        source = (ROOT / "launcher" / "main.py").read_text()
        service = (ROOT / "systemd" / "pi-games-launcher.service.in").read_text()
        self.assertNotIn("lines += [(problem", source)
        self.assertIn("StandardError=journal", service)

    def test_startup_splash_and_provider_warmup_are_present(self):
        source = (ROOT / "launcher" / "main.py").read_text()
        self.assertIn("KOCKOVANÉ HRY", source)
        self.assertIn("SPLASH_SECONDS = 4.0", source)
        self.assertIn("initial_catalog = executor.submit(collect, settings.providers)", source)
        self.assertLess(source.index("initial_catalog = executor.submit"), source.index("terminal.splash()"))
