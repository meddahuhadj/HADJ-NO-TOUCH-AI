"""
Unit tests for the gesture classifier and the virtual cursor filter.

These are the two components that decide whether a click lands where the user
aimed, so the cases here are written around the failure modes that matter in
practice: a false fist trigger, a double-click firing on a slow single pinch, a
swipe never being reachable, and cursor drift across the screen edges.

Timing is injected rather than slept on. The recogniser's temporal filters all
depend on wall-clock deltas, and a test that sleeps would both be slow and be
the first thing to fail on a loaded CI box.
"""

import os
import sys
import types
import unittest
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import vision.gesture_recognizer as gesture_recognizer_module
from vision.gesture_recognizer import GestureRecognizer, HandGesture
from vision.virtual_cursor import VirtualCursor


class FakeClock:
    """Stand-in for the time module, advancing by a fixed step per read."""

    def __init__(self, start=1000.0, step=0.04):
        self.now = float(start)
        self.step = float(step)

    def time(self):
        self.now += self.step
        return self.now

    def sleep(self, seconds):  # pragma: no cover - nothing sleeps in these tests
        self.now += float(seconds)

    def advance(self, seconds):
        self.now += float(seconds)


def make_landmarks(**overrides):
    """
    Builds a minimal stand-in for HandLandmarksData.

    The classifier only reads a flat set of booleans and tuples, so a stub is
    enough and keeps these tests independent of MediaPipe.
    """
    data = {
        "index_extended": False,
        "middle_extended": False,
        "ring_extended": False,
        "pinky_extended": False,
        "thumb_extended": False,
        "pinch_distance": 0.5,
        "index_tip": (0.5, 0.5),
        "middle_tip": (0.5, 0.5),
        "thumb_tip": (0.6, 0.6),
        "thumb_ip": (0.6, 0.5),
        "wrist": (0.5, 0.8),
    }
    data.update(overrides)
    return types.SimpleNamespace(**data)


FIST = make_landmarks()
POINT = dict(index_extended=True)
PINCH = dict(index_extended=True, pinch_distance=0.01)
TWO_FINGERS = dict(index_extended=True, middle_extended=True)
OPEN_HAND = dict(
    thumb_extended=True, index_extended=True, middle_extended=True,
    ring_extended=True, pinky_extended=True,
)


class TestGestureRecognizer(unittest.TestCase):

    def setUp(self):
        self.clock = FakeClock()
        patcher = mock.patch.object(gesture_recognizer_module, "time", self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.recognizer = GestureRecognizer()
        # Pinch threshold high enough that contact fixtures read as a pinch.
        self.recognizer.pinch_threshold = 0.05
        self.recognizer.fist_debounce = 0.0

    # ------------------------------------------------------------------ #
    # Static poses
    # ------------------------------------------------------------------ #

    def test_closed_fist_is_detected(self):
        gesture, conf = self.recognizer.classify(FIST)
        self.assertEqual(gesture, HandGesture.FIST)
        self.assertGreater(conf, 0.5)

    def test_thumb_up_is_detected_and_is_not_a_fist(self):
        data = make_landmarks(
            thumb_extended=True,
            thumb_tip=(0.5, 0.2),
            thumb_ip=(0.5, 0.5),
            wrist=(0.5, 0.8),
        )
        gesture, _ = self.recognizer.classify(data)
        self.assertEqual(gesture, HandGesture.THUMB_UP)

    def test_open_palm_is_detected(self):
        gesture, _ = self.recognizer.classify(make_landmarks(**OPEN_HAND))
        self.assertEqual(gesture, HandGesture.OPEN_PALM)

    def test_index_point_is_detected(self):
        gesture, _ = self.recognizer.classify(make_landmarks(**POINT))
        self.assertEqual(gesture, HandGesture.INDEX_POINT)

    def test_neither_gesture_does_not_match_a_known_pose(self):
        gesture, conf = self.recognizer.classify(make_landmarks())
        self.assertIn(gesture, (HandGesture.NONE, HandGesture.FIST))
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 1.0)

    # ------------------------------------------------------------------ #
    # Pinch state machine
    # ------------------------------------------------------------------ #

    def test_pinch_then_hold_then_release(self):
        pinched = make_landmarks(**PINCH)

        gesture, _ = self.recognizer.classify(pinched)
        self.assertEqual(gesture, HandGesture.PINCH)

        # Holding past the drag delay promotes the pose to a drag.
        self.recognizer.pinch_start_time = self.clock.now - (
            self.recognizer.drag_hold_delay + 0.1
        )
        gesture, _ = self.recognizer.classify(pinched)
        self.assertEqual(gesture, HandGesture.PINCH_HOLD)
        self.assertTrue(self.recognizer.in_drag_mode)

        # Releasing ends the drag and arms the double-pinch window.
        gesture, _ = self.recognizer.classify(make_landmarks(**POINT))
        self.assertNotEqual(gesture, HandGesture.PINCH_HOLD)
        self.assertFalse(self.recognizer.in_drag_mode)
        self.assertGreater(self.recognizer.last_pinch_release_time, 0.0)

    def test_two_fast_pinches_produce_a_double_click(self):
        pinched = make_landmarks(**PINCH)
        open_hand = make_landmarks(**POINT)

        self.assertEqual(self.recognizer.classify(pinched)[0], HandGesture.PINCH)

        # Release, then pinch again inside the double-pinch window.
        self.recognizer.classify(open_hand)
        self.assertEqual(
            self.recognizer.classify(pinched)[0], HandGesture.DOUBLE_PINCH
        )

    def test_slow_second_pinch_is_not_a_double_click(self):
        pinched = make_landmarks(**PINCH)
        open_hand = make_landmarks(**POINT)

        self.recognizer.classify(pinched)
        self.recognizer.classify(open_hand)

        # Push the release far enough back that the window has expired.
        self.recognizer.last_pinch_release_time = self.clock.now - (
            self.recognizer.double_pinch_window + 0.2
        )
        self.assertEqual(self.recognizer.classify(pinched)[0], HandGesture.PINCH)

    def test_pinch_takes_priority_over_pointing(self):
        """Thumb and index together is a click, not a cursor move."""
        gesture, _ = self.recognizer.classify(make_landmarks(**PINCH))
        self.assertEqual(gesture, HandGesture.PINCH)

    # ------------------------------------------------------------------ #
    # Fist debounce — the emergency stop depends on this
    # ------------------------------------------------------------------ #

    def test_brief_fist_does_not_start_the_hold_timer(self):
        self.recognizer.fist_debounce = 0.20

        self.recognizer.classify(FIST)
        # Still inside the debounce window: no hold has been recorded.
        self.assertIsNone(self.recognizer.fist_start_time)
        self.assertEqual(self.recognizer.get_fist_hold_duration(), 0.0)

    def test_sustained_fist_starts_and_keeps_the_hold_timer(self):
        self.recognizer.fist_debounce = 0.10

        self.recognizer.classify(FIST)
        self.clock.advance(0.30)

        gesture, _ = self.recognizer.classify(FIST)
        self.assertEqual(gesture, HandGesture.FIST)
        self.assertIsNotNone(self.recognizer.fist_start_time)
        # The clock advances on each read, so allow a frame of slack.
        self.assertGreaterEqual(self.recognizer.get_fist_hold_duration(), 0.30)

    def test_a_single_noisy_frame_cannot_reset_an_established_fist(self):
        self.recognizer.fist_debounce = 0.10
        self.recognizer.classify(FIST)
        self.clock.advance(0.30)
        self.recognizer.classify(FIST)

        started = self.recognizer.fist_start_time
        self.assertIsNotNone(started)

        # One frame of tracking loss, then the fist comes back. The hold must
        # survive, otherwise an unreliable tracker makes the emergency stop
        # unreachable precisely when it is needed.
        self.recognizer.classify(make_landmarks(**POINT))
        self.assertIsNotNone(self.recognizer.fist_start_time)

        self.clock.advance(0.10)
        self.recognizer.classify(FIST)
        self.assertEqual(self.recognizer.fist_start_time, started)
        self.assertGreater(self.recognizer.get_fist_hold_duration(), 0.30)

    def test_a_long_release_does_discard_the_fist_hold(self):
        self.recognizer.fist_debounce = 0.10
        self.recognizer.classify(FIST)
        self.clock.advance(0.30)
        self.recognizer.classify(FIST)
        self.assertIsNotNone(self.recognizer.fist_start_time)

        # Hand genuinely lowered for longer than the dropout tolerance.
        self.recognizer.classify(make_landmarks(**POINT))
        self.clock.advance(0.40)
        self.recognizer.classify(make_landmarks(**POINT))
        self.assertIsNone(self.recognizer.fist_start_time)
        self.assertEqual(self.recognizer.get_fist_hold_duration(), 0.0)

    def test_dropout_tolerance_is_configurable(self):
        self.recognizer.fist_dropout_tolerance = 0.5
        self.recognizer.fist_debounce = 0.10
        self.recognizer.classify(FIST)
        self.clock.advance(0.30)
        self.recognizer.classify(FIST)

        self.recognizer.classify(make_landmarks(**POINT))
        self.clock.advance(0.40)
        self.recognizer.classify(make_landmarks(**POINT))
        self.assertIsNotNone(self.recognizer.fist_start_time)

    def test_long_enough_fist_reaches_the_emergency_stop_threshold(self):
        """The UI threshold is 2 s; make sure the pipeline can actually reach it."""
        self.recognizer.fist_debounce = 0.12
        self.recognizer.classify(FIST)
        self.clock.advance(2.5)
        self.recognizer.classify(FIST)
        self.assertGreaterEqual(self.recognizer.get_fist_hold_duration(), 2.0)

    def test_fist_hold_survives_intermittent_dropout_over_two_seconds(self):
        """The realistic worst case: an unreliable tracker, hand held down."""
        self.recognizer.fist_debounce = 0.12
        reached = False
        for _ in range(120):  # ~5 s at the 0.04 s frame budget
            self.recognizer.classify(FIST)
            self.clock.advance(0.04)
            if self.recognizer.get_fist_hold_duration() >= 2.0:
                reached = True
                break
            # Drop a frame now and then, as a real tracker does.
            self.recognizer.classify(make_landmarks(**POINT))
            self.clock.advance(0.04)
        self.assertTrue(reached, "fist hold never reached the emergency stop")

    # ------------------------------------------------------------------ #
    # Swipe — previously unreachable whenever two fingers were raised
    # ------------------------------------------------------------------ #

    def test_single_finger_swipe_is_detected(self):
        self.recognizer.swipe_velocity_threshold = 1.5
        point = dict(index_extended=True)

        self.recognizer.classify(
            make_landmarks(index_tip=(0.30, 0.5), **point)
        )
        self.recognizer.classify(
            make_landmarks(index_tip=(0.35, 0.5), **point)
        )
        gesture, _ = self.recognizer.classify(
            make_landmarks(index_tip=(0.85, 0.5), **point)
        )
        self.assertEqual(gesture, HandGesture.SWIPE_RIGHT)

    def test_swipe_direction_is_reported_correctly(self):
        self.recognizer.swipe_velocity_threshold = 1.5
        point = dict(index_extended=True)

        gestures = []
        for x in (0.80, 0.65, 0.20):
            gesture, _ = self.recognizer.classify(
                make_landmarks(index_tip=(x, 0.5), **point)
            )
            gestures.append(gesture)
        self.assertIn(HandGesture.SWIPE_LEFT, gestures)

    def test_two_finger_swipe_is_not_swallowed_by_the_scroll_branch(self):
        """A two-finger horizontal sweep must be able to reach the swipe test."""
        self.recognizer.swipe_velocity_threshold = 1.0
        self.recognizer.scroll_dead_band = 0.015

        gestures = []
        for x in (0.30, 0.45, 0.65, 0.85):
            gesture, _ = self.recognizer.classify(
                make_landmarks(index_tip=(x, 0.5), middle_tip=(x, 0.5), **TWO_FINGERS)
            )
            gestures.append(gesture)

        self.assertIn(HandGesture.SWIPE_RIGHT, gestures)
        self.assertNotIn(HandGesture.TWO_FINGER_SCROLL_UP, gestures)
        self.assertNotIn(HandGesture.TWO_FINGER_SCROLL_DOWN, gestures)

    def test_swipe_is_rate_limited(self):
        self.recognizer.swipe_velocity_threshold = 1.0
        point = dict(index_extended=True)

        for x in (0.30, 0.45, 0.65, 0.85):
            self.recognizer.classify(
                make_landmarks(index_tip=(x, 0.5), **point)
            )
        triggered = self.recognizer.last_swipe_trigger_time
        self.assertGreater(triggered, 0.0)

        # A second fast sweep inside the cooldown must be swallowed.
        for x in (0.20, 0.35, 0.55, 0.75):
            gesture, _ = self.recognizer.classify(
                make_landmarks(index_tip=(x, 0.5), **point)
            )
            self.assertNotEqual(gesture, HandGesture.SWIPE_RIGHT)
        self.assertEqual(self.recognizer.last_swipe_trigger_time, triggered)

        # Past the cooldown the same sweep fires again.
        self.clock.advance(0.8)
        gestures = []
        for x in (0.25, 0.40, 0.60, 0.80):
            gesture, _ = self.recognizer.classify(
                make_landmarks(index_tip=(x, 0.5), **point)
            )
            gestures.append(gesture)
        self.assertIn(HandGesture.SWIPE_RIGHT, gestures)

    def test_slow_drift_is_not_a_swipe(self):
        self.recognizer.swipe_velocity_threshold = 2.0
        for x in (0.30, 0.32, 0.34, 0.36):
            gesture, _ = self.recognizer.classify(
                make_landmarks(index_tip=(x, 0.5), **POINT)
            )
            self.assertNotIn(gesture, (HandGesture.SWIPE_LEFT, HandGesture.SWIPE_RIGHT))

    def test_history_outside_the_window_is_discarded(self):
        self.recognizer.swipe_history = [
            (self.clock.now - 5.0, 0.10),
            (self.clock.now - 5.0, 0.20),
            (self.clock.now - 5.0, 0.30),
            (self.clock.now, 0.95),
        ]
        self.recognizer._detect_swipe(self.clock.now, 0.95)
        self.assertTrue(
            all(abs(t - self.clock.now) < 1.0 for t, _ in self.recognizer.swipe_history)
        )

    def test_same_instant_samples_do_not_look_like_infinite_velocity(self):
        """Three frames with dt ~ 0 are a burst, not a fling."""
        self.recognizer.swipe_velocity_threshold = 1.0
        frozen = FakeClock(step=0.0)
        with mock.patch.object(gesture_recognizer_module, "time", frozen):
            self.recognizer.swipe_history = []
            for x in (0.10, 0.50, 0.90):
                self.assertIsNone(self.recognizer._detect_swipe(frozen.now, x))

    # ------------------------------------------------------------------ #
    # Two-finger scroll
    # ------------------------------------------------------------------ #

    def test_two_finger_vertical_motion_scrolls(self):
        self.recognizer.scroll_dead_band = 0.015

        self.recognizer.classify(
            make_landmarks(index_tip=(0.5, 0.50), middle_tip=(0.5, 0.50), **TWO_FINGERS)
        )
        gesture, _ = self.recognizer.classify(
            make_landmarks(index_tip=(0.5, 0.30), middle_tip=(0.5, 0.30), **TWO_FINGERS)
        )
        self.assertEqual(gesture, HandGesture.TWO_FINGER_SCROLL_UP)

        gesture, _ = self.recognizer.classify(
            make_landmarks(index_tip=(0.5, 0.70), middle_tip=(0.5, 0.70), **TWO_FINGERS)
        )
        self.assertEqual(gesture, HandGesture.TWO_FINGER_SCROLL_DOWN)

    def test_stationary_two_finger_pose_does_not_scroll(self):
        self.recognizer.scroll_dead_band = 0.015
        last = None
        for _ in range(3):
            last, _ = self.recognizer.classify(
                make_landmarks(index_tip=(0.5, 0.50), middle_tip=(0.5, 0.50), **TWO_FINGERS)
            )
        self.assertNotIn(last, (HandGesture.TWO_FINGER_SCROLL_UP,
                               HandGesture.TWO_FINGER_SCROLL_DOWN))

    def test_scroll_reference_resets_when_the_pose_changes(self):
        """Leaving the two-finger pose must not make the next pose scroll."""
        self.recognizer.scroll_dead_band = 0.015
        self.recognizer.classify(
            make_landmarks(index_tip=(0.5, 0.50), middle_tip=(0.5, 0.50), **TWO_FINGERS)
        )
        self.assertIsNotNone(self.recognizer.prev_scroll_y)

        self.recognizer.classify(FIST)
        self.assertIsNone(self.recognizer.prev_scroll_y)

    # ------------------------------------------------------------------ #
    # Reset
    # ------------------------------------------------------------------ #

    def test_reset_clears_every_temporal_filter(self):
        pinched = make_landmarks(**PINCH)
        self.recognizer.classify(pinched)
        self.recognizer.classify(make_landmarks(**POINT))
        self.recognizer.fist_start_time = self.clock.now

        self.recognizer.reset()

        self.assertFalse(self.recognizer.is_pinching)
        self.assertFalse(self.recognizer.in_drag_mode)
        self.assertEqual(self.recognizer.pinch_start_time, 0.0)
        self.assertEqual(self.recognizer.last_pinch_release_time, 0.0)
        self.assertIsNone(self.recognizer.fist_start_time)
        self.assertIsNone(self.recognizer.fist_candidate_since)
        self.assertIsNone(self.recognizer.fist_lost_since)
        self.assertIsNone(self.recognizer.prev_scroll_y)
        self.assertEqual(self.recognizer.swipe_history, [])
        self.assertEqual(self.recognizer.last_swipe_trigger_time, 0.0)

    def test_first_frame_after_reset_is_a_single_click_not_a_double(self):
        """Re-entering the frame must not replay the previous release."""
        pinched = make_landmarks(**PINCH)
        self.recognizer.classify(pinched)
        self.recognizer.classify(make_landmarks(**POINT))
        self.recognizer.reset()

        gesture, _ = self.recognizer.classify(pinched)
        self.assertEqual(gesture, HandGesture.PINCH)


class TestVirtualCursor(unittest.TestCase):

    def setUp(self):
        self.cursor = VirtualCursor(screen_width=1920, screen_height=1080)

    def _settle(self, norm_x, norm_y, frames=40):
        """Feeds the same target until the EMA filter stops moving."""
        position = None
        for _ in range(frames):
            position = self.cursor.map_normalized_to_screen(norm_x, norm_y)
        return position

    def test_output_stays_on_screen(self):
        for nx, ny in ((0.0, 0.0), (1.0, 1.0), (1.5, -0.5), (-1.0, 2.0), (0.5, 0.5)):
            x, y = self.cursor.map_normalized_to_screen(nx, ny)
            self.assertTrue(0 <= x < 1920, (nx, ny, x))
            self.assertTrue(0 <= y < 1080, (nx, ny, y))

    def test_active_box_corners_map_to_screen_corners(self):
        self.cursor.set_active_box((0.25, 0.25, 0.75, 0.75))

        left, top = self._settle(0.25, 0.25)
        right, bottom = self._settle(0.75, 0.75)

        self.assertLess(left, 100)
        self.assertLess(top, 100)
        self.assertGreater(right, 1820)
        self.assertGreater(bottom, 980)

    def test_degenerate_active_box_is_ignored(self):
        self.cursor.set_active_box((0.5, 0.5, 0.5, 0.5))
        self.assertEqual(self.cursor.active_box, (0.0, 0.0, 1.0, 1.0))

    def test_too_narrow_active_box_is_ignored(self):
        self.cursor.set_active_box((0.50, 0.1, 0.5005, 0.9))
        self.assertEqual(self.cursor.active_box, (0.0, 0.0, 1.0, 1.0))

    def test_malformed_active_box_is_ignored(self):
        self.cursor.set_active_box((0.25, 0.25, 0.75, 0.75))
        self.cursor.set_active_box(("a", "b"))
        self.assertEqual(self.cursor.active_box, (0.25, 0.25, 0.75, 0.75))

        self.cursor.set_active_box((0.1, 0.2, 0.3))
        self.assertEqual(self.cursor.active_box, (0.25, 0.25, 0.75, 0.75))

        self.cursor.set_active_box(None)
        self.assertEqual(self.cursor.active_box, (0.0, 0.0, 1.0, 1.0))

    def test_active_box_is_clamped_to_the_frame(self):
        self.cursor.set_active_box((-0.5, -0.5, 1.5, 1.5))
        self.assertEqual(self.cursor.active_box, (0.0, 0.0, 1.0, 1.0))

    def test_remap_is_identity_for_the_uncalibrated_frame(self):
        self.assertEqual(self.cursor.remap_to_active_box(0.3, 0.7), (0.3, 0.7))

    def test_remap_stretches_the_reachable_region(self):
        self.cursor.set_active_box((0.25, 0.25, 0.75, 0.75))
        self.assertEqual(self.cursor.remap_to_active_box(0.25, 0.25), (0.0, 0.0))
        self.assertEqual(self.cursor.remap_to_active_box(0.75, 0.75), (1.0, 1.0))
        self.assertEqual(self.cursor.remap_to_active_box(0.50, 0.50), (0.5, 0.5))

    def test_tremor_inside_the_dead_zone_does_not_move_the_cursor(self):
        self.cursor.update_settings(smoothing=0.5, dead_zone=0.05, speed=1.0)
        self.cursor.reset()

        start = self.cursor.map_normalized_to_screen(0.50, 0.50)
        for _ in range(5):
            moved = self.cursor.map_normalized_to_screen(0.51, 0.51)
        self.assertEqual(moved, start)

    def test_intentional_movement_does_move_the_cursor(self):
        self.cursor.update_settings(smoothing=0.5, dead_zone=0.001, speed=1.5)
        self.cursor.reset()

        self.cursor.map_normalized_to_screen(0.20, 0.20)
        moved = self.cursor.map_normalized_to_screen(0.80, 0.80)
        start = self.cursor.map_normalized_to_screen(0.20, 0.20)
        self.assertNotEqual(moved, start)

    def test_update_settings_clamps_to_sane_ranges(self):
        self.cursor.update_settings(smoothing=99.0, dead_zone=-5.0, speed=1000.0)
        self.assertLessEqual(self.cursor.smoothing, 0.95)
        self.assertGreaterEqual(self.cursor.dead_zone, 0.001)
        self.assertLessEqual(self.cursor.speed_factor, 4.0)

        self.cursor.update_settings(smoothing=0.0, dead_zone=0.0, speed=0.0)
        self.assertGreaterEqual(self.cursor.smoothing, 0.05)
        self.assertGreaterEqual(self.cursor.dead_zone, 0.001)
        self.assertGreaterEqual(self.cursor.speed_factor, 0.5)

    def test_reset_requires_no_prior_frame(self):
        self.cursor.map_normalized_to_screen(0.30, 0.30)
        self.cursor.reset()
        self.assertIsNone(self.cursor.prev_norm_x)
        self.assertIsNone(self.cursor.prev_norm_y)
        self.assertFalse(self.cursor.is_dragging)

    def test_first_frame_is_not_a_jump(self):
        """The very first sample should land on its own target, not slide in."""
        self.cursor.set_active_box((0.2, 0.2, 0.8, 0.8))
        self.cursor.reset()
        x, y = self.cursor.map_normalized_to_screen(0.5, 0.5)
        self.assertAlmostEqual(x, 960, delta=2)
        self.assertAlmostEqual(y, 540, delta=2)

    def test_large_displacements_are_accelerated_more_than_small_ones(self):
        """Acceleration lets a short throw cross the screen without hurting aim."""
        def travel(start, end):
            cursor = VirtualCursor(screen_width=1000, screen_height=1000)
            cursor.update_settings(smoothing=0.0, dead_zone=0.001, speed=1.0)
            cursor.reset()
            cursor.map_normalized_to_screen(start, 0.5)
            x, _ = cursor.map_normalized_to_screen(end, 0.5)
            return (x / 1000.0) - start

        nudge = travel(0.50, 0.51)      # 0.01 of hand travel
        sweep = travel(0.00, 0.50)      # 0.50 of hand travel
        self.assertGreater(sweep, nudge * 2)

    def test_screen_size_falls_back_to_pyautogui_when_unspecified(self):
        with mock.patch("vision.virtual_cursor.pyautogui.size",
                        return_value=(1280, 720)):
            cursor = VirtualCursor()
        self.assertEqual((cursor.screen_width, cursor.screen_height), (1280, 720))


if __name__ == "__main__":
    unittest.main()