import json
import unittest
from unittest.mock import patch
from launcher.config import Provider, load, save_launcher_value
from launcher.manifests import collect, parse

class ManifestTests(unittest.TestCase):
    def test_parse_and_namespace_duplicate_provider_ids(self):
        one = parse("dos", json.dumps({"version":1,"games":[{"id":"same","title":"DOS","command":["dos"]}]}))[0]
        two = parse("pygame", json.dumps({"version":1,"games":[{"id":"same","title":"Py","command":["py"]}]}))[0]
        self.assertEqual((one.key, two.key), ("dos:same", "pygame:same"))
    def test_malformed_manifest_is_isolated(self):
        good = Provider("good", ("good",)); bad = Provider("bad", ("bad",))
        class Result:
            def __init__(self, text): self.returncode, self.stdout, self.stderr = 0, text, ""
        with patch("launcher.manifests.subprocess.run", side_effect=[Result('{"version":1,"games":[]}'), Result("bad")]):
            games, problems = collect((good, bad))
        self.assertEqual(games, []); self.assertEqual(len(problems), 1)
    def test_bad_command_is_rejected(self):
        with self.assertRaises(ValueError): parse("x", '{"version":1,"games":[{"id":"x","title":"X","command":[]}]}')
    def test_testing_tool_is_optional_boolean(self):
        game = parse("x", '{"version":1,"games":[{"id":"x","title":"X","command":["x"],"testing_tool":true}]}')[0]
        self.assertTrue(game.testing_tool)
        with self.assertRaises(ValueError):
            parse("x", '{"version":1,"games":[{"id":"x","title":"X","command":["x"],"testing_tool":"yes"}]}')

class ConfigTests(unittest.TestCase):
    def test_config_reads_multiple_providers(self):
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile("w") as file:
            file.write("[provider one]\nmanifest_command=one manifest\n[provider two]\nmanifest_command=two manifest\n"); file.flush()
            settings = load(file.name)
        self.assertEqual([item.id for item in settings.providers], ["one", "two"])
    def test_invalid_ini_becomes_a_configuration_error(self):
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile("w") as file:
            file.write("[launcher\nconfirm_key=SPACE\n"); file.flush()
            with self.assertRaises(ValueError): load(file.name)
    def test_volume_persists_in_launcher_section(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory) / "launcher.conf"
            path.write_text("[launcher]\nconfirm_key=SPACE\n\n[provider test]\nmanifest_command=test\n")
            save_launcher_value(path, "audio_volume_percent", 70)
            self.assertEqual(load(path).audio_volume_percent, 70)
    def test_last_selected_item_persists_in_launcher_section(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory) / "launcher.conf"
            path.write_text("[launcher]\n\n[provider test]\nmanifest_command=test\n")
            save_launcher_value(path, "last_selected_item", "dos:prince-of-persia")
            self.assertEqual(load(path).last_selected_item, "dos:prince-of-persia")
    def test_web_dance_mat_port_reads_from_launcher_section(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory) / "launcher.conf"
            path.write_text("[launcher]\nweb_dancemat_port=9090\n")
            self.assertEqual(load(path).web_dancemat_port, 9090)
