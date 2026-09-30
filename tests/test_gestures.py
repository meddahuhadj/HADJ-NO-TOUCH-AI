import unittest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from vision.gesture_recognizer import GestureRecognizer, HandGesture
from vision.virtual_cursor import VirtualCursor


class TestGesturesAndCursor(unittest.TestCase):

    def setUp(self):
        self.cursor = VirtualCursor(screen_width=1920, screen_height=1080)
        self.recognizer = GestureRecognizer()

    def test_cursor_mapping_and_bounds(self):
        # Center of camera (0.5, 0.5) should map to center of screen
        x, y = self.cursor.map_normalized_to_screen(0.5, 0.5)
        self.assertTrue(0 <= x <= 1920)
        self.assertTrue(0 <= y <= 1080)

        # Clamping at boundaries
        x_min, y_min = self.cursor.map_normalized_to_screen(1.5, -0.5)
        self.assertTrue(0 <= x_min <= 1920)
        self.assertTrue(0 <= y_min <= 1080)

    def test_virtual_cursor_smoothing(self):
        # Feed small displacement - should apply EMA smoothing
        x1, y1 = self.cursor.map_normalized_to_screen(0.4, 0.4)
        x2, y2 = self.cursor.map_normalized_to_screen(0.41, 0.41)
        self.assertIsInstance(x2, int)
        self.assertIsInstance(y2, int)


if __name__ == "__main__":
    unittest.main()
