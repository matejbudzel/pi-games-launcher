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

    def test_audio_configuration_uses_the_detected_hdmi_card(self):
        source = (ROOT / "scripts" / "configure-appliance-audio.sh").read_text()
        self.assertIn("modprobe snd_bcm2835", source)
        self.assertIn("bcm2835 HDMI", source)
        self.assertIn('pcm.!default {', source)
        self.assertIn('slave.pcm \\"hw:$card,0\\"', source)

    def test_guest_handoff_inherits_the_appliance_sdl_workaround(self):
        service = (ROOT / "systemd" / "pi-games-launcher.service.in").read_text()
        self.assertIn("Environment=SDL_FB_BROKEN_MODES=1", service)

    def test_menu_has_diagnostics_shutdown_and_ctrl_c_escape(self):
        source = (ROOT / "launcher" / "main.py").read_text()
        for item in ("Test obrazu framebufferu", "Test HDMI zvuku", '"Koniec"', 'key == "CTRL_C"', "confirm_shutdown"):
            self.assertIn(item, source)

    def test_provider_problems_stay_out_of_the_menu_and_logs_use_journal(self):
        source = (ROOT / "launcher" / "main.py").read_text()
        service = (ROOT / "systemd" / "pi-games-launcher.service.in").read_text()
        self.assertNotIn("lines += [(problem", source)
        self.assertIn("StandardError=journal", service)

    def test_ctrl_c_hands_tty1_to_getty(self):
        source = (ROOT / "launcher" / "main.py").read_text()
        service = (ROOT / "systemd" / "pi-games-launcher.service.in").read_text()
        self.assertIn("MAINTENANCE_EXIT = 42", source)
        self.assertIn("SuccessExitStatus=42", service)
        self.assertIn("ExecStopPost=+/bin/sh", service)
        self.assertIn("systemctl --no-block start getty@tty1.service", service)

    def test_startup_splash_and_provider_warmup_are_present(self):
        source = (ROOT / "launcher" / "main.py").read_text()
        self.assertIn("KOCKOVANÉ HRY", source)
        self.assertIn("SPLASH_SECONDS = 4.0", source)
        self.assertIn("initial_catalog = executor.submit(collect, settings.providers)", source)
        self.assertLess(source.index("initial_catalog = executor.submit"), source.index("terminal.splash()"))

    def test_launcher_has_volume_and_network_controls(self):
        source = (ROOT / "launcher" / "main.py").read_text()
        for item in ("volume_status(volume)", 'key in ("LEFT", "RIGHT")', "save_launcher_value", 'key == "F1"', "network_address()"):
            self.assertIn(item, source)

    def test_f2_refreshes_provider_content_from_both_menus(self):
        source = (ROOT / "launcher" / "main.py").read_text()
        for item in ('b"\\x1bOQ":"F2"', 'elif key == "F2":', "Obnovujem obsah…", "F2 - obnoviť"):
            self.assertIn(item, source)

    def test_framebuffer_profiles_include_the_custom_854x480_timing(self):
        profile = (ROOT / "scripts" / "set-framebuffer-profile.sh").read_text()
        framebuffer = (ROOT / "scripts" / "configure-legacy-framebuffer.sh").read_text()
        for item in ("640x480|854x480|720p", "framebuffer_hdmi_mode 87", "854 480 60 3 0 0 0"):
            self.assertIn(item, profile)
        for item in ("echo 'hdmi_drive=2'", 'echo "hdmi_cvt=$cvt"'):
            self.assertIn(item, framebuffer)
