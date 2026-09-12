import unittest

from launcher.webmat import PAGE, VirtualDanceMat


class VirtualDanceMatTests(unittest.TestCase):
    def test_input_is_ignored_outside_the_launcher_menu(self):
        mat = VirtualDanceMat(0)
        mat.feed("START")
        self.assertIsNone(mat.action())

    def test_diagonal_and_button_events_are_queued(self):
        mat = VirtualDanceMat(0)
        mat.set_active(True)
        mat.feed("UP_LEFT")
        mat.feed("SELECT")
        self.assertEqual([mat.action(), mat.action(), mat.action()], ["UP", "LEFT", "SELECT"])

    def test_page_has_the_full_dance_mat(self):
        for action in ("UP_LEFT", "UP", "UP_RIGHT", "LEFT", "RIGHT", "DOWN_LEFT", "DOWN", "DOWN_RIGHT", "START", "SELECT"):
            self.assertIn('data-action="%s"' % action, PAGE)
