import unittest

from launcher.webmat import ACTIONS, PAGE


class VirtualDanceMatTests(unittest.TestCase):
    def test_diagonals_use_two_joystick_buttons(self):
        self.assertEqual(ACTIONS["UP_LEFT"], (2, 0))
        self.assertEqual(ACTIONS["DOWN_RIGHT"], (1, 3))

    def test_page_has_the_full_dance_mat(self):
        for action in ("UP_LEFT", "UP", "UP_RIGHT", "LEFT", "RIGHT", "DOWN_LEFT", "DOWN", "DOWN_RIGHT", "START", "SELECT"):
            self.assertIn('data-action="%s"' % action, PAGE)
        self.assertIn("pointerup", PAGE)
        self.assertIn("KEEPALIVE", PAGE)
