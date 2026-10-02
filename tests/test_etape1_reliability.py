"""
Unit tests for Étape 1: Detection Reliability, Smoothing, Arming, Emergency Stop, and Diagnostics.
"""

import unittest
import time
from vision.filters import OneEuroFilter, HandLandmarksSmoother, PointFilter2D
from vision.gesture_detector import HandLandmarksData
from vision.gesture_recognizer import GestureRecognizer, HandGesture
from automation.global_hotkey import GlobalHotkeyWorker


class MockLandmark:
    def __init__(self, x, y, z=0.0):
        self.x = x
        self.y = y
        self.z = z


class MockRawLandmarks:
    def __init__(self, points):
        self.landmark = [MockLandmark(x, y, z) for x, y, z in points]


def make_landmarks_fixture(hand_span=0.35, is_open_palm=False, is_point=False, is_pinch=False):
    # 21 points
    pts = [(0.5, 0.7, 0.0)] * 21 # Wrist at 0.5, 0.7
    pts[0] = (0.5, 0.7, 0.0) # Wrist
    
    if is_open_palm:
        pts[4] = (0.2, 0.3, 0.0)  # Thumb
        pts[8] = (0.4, 0.2, 0.0)  # Index
        pts[12] = (0.5, 0.2, 0.0) # Middle
        pts[16] = (0.6, 0.2, 0.0) # Ring
        pts[20] = (0.7, 0.3, 0.0) # Pinky
        pts[3] = (0.3, 0.5, 0.0)
        pts[6] = (0.4, 0.45, 0.0)
        pts[10] = (0.5, 0.45, 0.0)
        pts[14] = (0.6, 0.45, 0.0)
        pts[18] = (0.7, 0.5, 0.0)
    elif is_point:
        pts[4] = (0.45, 0.6, 0.0) # Thumb folded
        pts[8] = (0.5, 0.2, 0.0)  # Index extended
        pts[6] = (0.5, 0.45, 0.0)
        pts[12] = (0.55, 0.6, 0.0) # Middle folded
        pts[10] = (0.55, 0.5, 0.0)
        pts[16] = (0.6, 0.6, 0.0)  # Ring folded
        pts[14] = (0.6, 0.5, 0.0)
        pts[20] = (0.65, 0.6, 0.0) # Pinky folded
        pts[18] = (0.65, 0.5, 0.0)
        pts[3] = (0.45, 0.55, 0.0)
    elif is_pinch:
        pts[4] = (0.50, 0.30, 0.0) # Thumb tip touching index
        pts[8] = (0.51, 0.30, 0.0) # Index tip touching thumb
        pts[6] = (0.50, 0.45, 0.0)
        pts[12] = (0.55, 0.6, 0.0)
        pts[10] = (0.55, 0.5, 0.0)
        pts[16] = (0.6, 0.6, 0.0)
        pts[14] = (0.6, 0.5, 0.0)
        pts[20] = (0.65, 0.6, 0.0)
        pts[18] = (0.65, 0.5, 0.0)
        pts[3] = (0.48, 0.45, 0.0)

    raw = MockRawLandmarks(pts)
    return HandLandmarksData(raw, 640, 480)


class TestOneEuroFilter(unittest.TestCase):
    def test_filter_reduces_noise(self):
        f = OneEuroFilter(min_cutoff=1.0, beta=0.007)
        t = 1.0
        # Constant signal with jitter
        val1 = f.filter(10.0, timestamp=t)
        self.assertEqual(val1, 10.0)

        # Add small jitter at next time step
        val2 = f.filter(10.2, timestamp=t + 0.033)
        # Should be smoothed closer to 10.0 than 10.2
        self.assertLess(val2, 10.2)
        self.assertGreater(val2, 10.0)

    def test_landmarks_smoother_preserves_shape(self):
        smoother = HandLandmarksSmoother()
        pts = [(float(i) * 0.04, float(i) * 0.04, 0.0) for i in range(21)]
        smoothed = smoother.smooth(pts, timestamp=1.0)
        self.assertEqual(len(smoothed), 21)
        self.assertAlmostEqual(smoothed[0][0], pts[0][0], places=3)


class TestArmingAndHysteresis(unittest.TestCase):
    def setUp(self):
        self.recognizer = GestureRecognizer()
        self.recognizer.gesture_hold_delay = 0.20 # 200 ms for fast testing
        self.recognizer.arm_hold_duration = 0.30 # 300 ms for fast testing

    def test_arming_requires_hold_duration(self):
        data = make_landmarks_fixture(is_open_palm=True)
        t0 = time.time()
        
        # Frame 1: classified as OPEN_PALM, arm_progress starts
        g, _ = self.recognizer.classify(data)
        self.assertEqual(g, HandGesture.OPEN_PALM)
        self.assertFalse(self.recognizer.consume_arm_toggle())
        self.assertGreaterEqual(self.recognizer.get_arm_progress(), 0.0)

        # Simulate 0.35s later (past arm_hold_duration)
        time.sleep(0.35)
        g, _ = self.recognizer.classify(data)
        self.assertEqual(g, HandGesture.OPEN_PALM)
        # Now consume_arm_toggle should be True!
        self.assertTrue(self.recognizer.consume_arm_toggle())
        # Subsequent call should return False (consumed)
        self.assertFalse(self.recognizer.consume_arm_toggle())

    def test_gesture_hysteresis_commit(self):
        data = make_landmarks_fixture(is_pinch=True)
        
        # Frame 1: Classified as PINCH
        g, _ = self.recognizer.classify(data)
        self.assertEqual(g, HandGesture.PINCH)
        # Not committed yet because hold delay has not passed
        self.assertFalse(self.recognizer.is_gesture_committed(HandGesture.PINCH))

        # Sleep past hold delay
        time.sleep(0.25)
        g, _ = self.recognizer.classify(data)
        self.assertEqual(g, HandGesture.PINCH)
        # Now committed
        self.assertTrue(self.recognizer.is_gesture_committed(HandGesture.PINCH))


class TestGlobalHotkey(unittest.TestCase):
    def test_worker_instantiation(self):
        worker = GlobalHotkeyWorker()
        self.assertEqual(worker.key_id, 101)
        self.assertEqual(worker.vk_code, 0x1B) # Escape


if __name__ == "__main__":
    unittest.main()
