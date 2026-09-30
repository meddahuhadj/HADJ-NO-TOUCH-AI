import os
import random
import sys
import threading
import time
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.auto_calibration import (
    AdaptiveTuner, CalibrationPhase, CalibrationReport, CalibrationSession,
    DistanceCluster, HandSample, MIN_PINCH_SEPARATION, PINCH_BOUNDS,
    clamp, pinch_threshold_from_clusters, percentile, split_distance_clusters,
)
from vision.gesture_recognizer import GestureRecognizer
from vision.virtual_cursor import VirtualCursor


CLOSED_MEAN, OPEN_MEAN = 0.018, 0.075


def bimodal(n=200, duty=0.5, closed=CLOSED_MEAN, opened=OPEN_MEAN, seed=3):
    """A synthetic pinch-distance trace with a controllable duty cycle."""
    rng = random.Random(seed)
    n_open = int(n * duty)
    return [rng.gauss(closed, 0.003) for _ in range(n - n_open)] + [
        rng.gauss(opened, 0.005) for _ in range(n_open)
    ]


class FakeSettings:
    """Minimal SettingsManager stand-in that records writes."""

    def __init__(self, **data):
        self.data = dict(data)
        self.writes = 0

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value, auto_save=True):
        self.data[key] = value
        self.writes += 1


class FakeLandmarks:
    """Carries only the geometry GestureRecognizer.classify() reads."""

    def __init__(self, **kwargs):
        self.thumb_tip = (0.0, 0.0)
        self.index_tip = (0.0, 0.0)
        self.thumb_ip = (0.0, 0.0)
        self.wrist = (0.0, 0.0)
        self.pinch_distance = 1.0
        self.index_extended = False
        self.middle_extended = False
        self.ring_extended = False
        self.pinky_extended = False
        self.thumb_extended = False
        self.__dict__.update(kwargs)


# --------------------------------------------------------------------------- #
# Primitives
# --------------------------------------------------------------------------- #

class TestPrimitives(unittest.TestCase):

    def test_percentile_endpoints_and_interpolation(self):
        self.assertEqual(percentile([5.0], 0.9), 5.0)
        self.assertEqual(percentile([0.0, 10.0], 0.0), 0.0)
        self.assertEqual(percentile([0.0, 10.0], 1.0), 10.0)
        self.assertAlmostEqual(percentile([0.0, 10.0], 0.5), 5.0)
        self.assertEqual(percentile([3.0, 1.0, 2.0], 0.5), 2.0)

    def test_percentile_rejects_empty(self):
        with self.assertRaises(ValueError):
            percentile([], 0.5)

    def test_clamp(self):
        self.assertEqual(clamp(5.0, (0.0, 1.0)), 1.0)
        self.assertEqual(clamp(-5.0, (0.0, 1.0)), 0.0)
        self.assertEqual(clamp(0.5, (0.0, 1.0)), 0.5)


# --------------------------------------------------------------------------- #
# Cluster splitting
# --------------------------------------------------------------------------- #

class TestClusterSplitting(unittest.TestCase):

    def test_finds_the_gap_at_any_duty_cycle(self):
        """The split must not assume the user pinched half the time."""
        for duty in (0.2, 0.35, 0.5, 0.65, 0.8):
            with self.subTest(duty=duty):
                closed, opened = split_distance_clusters(bimodal(duty=duty))
                self.assertAlmostEqual(closed.centre, CLOSED_MEAN, delta=0.008)
                self.assertAlmostEqual(opened.centre, OPEN_MEAN, delta=0.008)

    def test_rejects_too_few_samples(self):
        self.assertIsNone(split_distance_clusters([0.1, 0.2, 0.3]))

    def test_uniform_samples_are_rejected(self):
        """A hand that never pinches produces no usable threshold."""
        rng = random.Random(5)
        flat = [rng.gauss(0.045, 0.002) for _ in range(200)]
        split = split_distance_clusters(flat)
        self.assertIsNotNone(split)
        self.assertLess(split[1].centre - split[0].centre, MIN_PINCH_SEPARATION)
        self.assertIsNone(pinch_threshold_from_clusters(*split))

    def test_threshold_lands_between_the_clusters(self):
        closed, opened = split_distance_clusters(bimodal())
        threshold, separation, confidence = pinch_threshold_from_clusters(closed, opened)
        self.assertGreater(threshold, closed.high)
        self.assertLess(threshold, opened.centre)
        self.assertAlmostEqual(separation, OPEN_MEAN - CLOSED_MEAN, delta=0.01)
        self.assertGreater(confidence, 0.5)

    def test_overlapping_clusters_still_produce_a_threshold(self):
        """Heavy overlap must degrade gracefully instead of returning None."""
        closed = DistanceCluster(centre=0.030, low=0.025, high=0.040, count=80)
        opened = DistanceCluster(centre=0.050, low=0.042, high=0.060, count=80)
        derived = pinch_threshold_from_clusters(closed, opened)
        self.assertIsNotNone(derived)
        threshold, _separation, _confidence = derived
        self.assertGreater(threshold, closed.centre)
        self.assertLessEqual(threshold, opened.centre)

    def test_outliers_do_not_move_the_threshold(self):
        """A couple of overshoot frames must not drag the value."""
        clean = pinch_threshold_from_clusters(*split_distance_clusters(bimodal()))
        polluted = pinch_threshold_from_clusters(
            *split_distance_clusters(
                bimodal() + [0.043, 0.044, 0.042]
            )
        )
        self.assertAlmostEqual(clean[0], polluted[0], delta=0.004)

    def test_threshold_is_clamped_to_the_supported_range(self):
        closed = DistanceCluster(centre=0.0, low=0.0, high=0.0, count=90)
        opened = DistanceCluster(centre=0.9, low=0.9, high=0.9, count=90)
        threshold, _s, _c = pinch_threshold_from_clusters(closed, opened)
        self.assertGreaterEqual(threshold, PINCH_BOUNDS[0])
        self.assertLessEqual(threshold, PINCH_BOUNDS[1])


# --------------------------------------------------------------------------- #
# Guided session
# --------------------------------------------------------------------------- #

def run_pinch_phase(session, cycles=3, frames_per_state=10, start=0.0, seed=7):
    """
    Feeds a realistic routine: ``cycles`` closed blocks each followed by a
    release, so exactly ``cycles`` close->open transitions are recorded.
    """
    rng = random.Random(seed)
    t = start
    for _ in range(cycles):
        for is_open in (False, True):
            for _ in range(frames_per_state):
                t += 1.0 / 30.0
                distance = (
                    rng.gauss(OPEN_MEAN, 0.005)
                    if is_open
                    else rng.gauss(CLOSED_MEAN, 0.003)
                )
                session.feed(HandSample((0.5, 0.5), distance, t))
    return t


class TestCalibrationSession(unittest.TestCase):

    def test_measured_pinch_threshold_lands_in_the_gap(self):
        session = CalibrationSession()
        session.begin(CalibrationPhase.PINCH)
        run_pinch_phase(session, cycles=4)
        report = session.finish()

        self.assertGreater(report.pinch_threshold, CLOSED_MEAN)
        self.assertLess(report.pinch_threshold, OPEN_MEAN)
        self.assertGreater(report.confidence_of("pinch_click_threshold"), 0.5)

    def test_pinch_cycles_are_counted(self):
        session = CalibrationSession()
        session.begin(CalibrationPhase.PINCH)
        run_pinch_phase(session, cycles=3)
        self.assertEqual(session.pinch_cycles, 3)
        session.finish()

    def test_drag_delay_and_double_pinch_come_from_real_timings(self):
        session = CalibrationSession()
        session.begin(CalibrationPhase.PINCH)
        # 10 frames per state at 30 FPS is a ~0.33 s hold, so the drag delay must
        # land well above it and the double-pinch window well below it.
        run_pinch_phase(session, cycles=4, frames_per_state=10)
        report = session.finish()

        self.assertGreater(report.drag_hold_delay, 0.30)
        self.assertLessEqual(report.drag_hold_delay, 1.0)
        self.assertGreaterEqual(report.double_pinch_window, 0.25)
        self.assertLessEqual(report.double_pinch_window, 0.80)

    def test_incomplete_phase_is_discarded(self):
        """Skipping a step must leave the existing value untouched."""
        session = CalibrationSession()
        original = session.report.pinch_threshold
        session.begin(CalibrationPhase.PINCH)
        run_pinch_phase(session, cycles=1, frames_per_state=3)  # far too few
        report = session.finish()
        self.assertEqual(report.pinch_threshold, original)

    def test_still_phase_measures_tremor(self):
        rng = random.Random(11)
        session = CalibrationSession()
        session.begin(CalibrationPhase.STILL)
        t = 0.0
        for _ in range(80):
            t += 1.0 / 30.0
            session.feed(HandSample(
                (0.5 + rng.gauss(0, 0.006), 0.5 + rng.gauss(0, 0.006)),
                0.09, t,
            ))
        report = session.finish()
        self.assertGreater(report.dead_zone_radius, 0.0)
        self.assertGreater(report.smoothing_factor, 0.0)
        self.assertLessEqual(report.smoothing_factor, 0.72)
        self.assertGreaterEqual(report.confidence_of("dead_zone_radius"), 0.9)

    def test_reach_phase_produces_a_padded_box(self):
        session = CalibrationSession()
        session.begin(CalibrationPhase.REACH)
        t = 0.0
        for i in range(80):
            t += 1.0 / 30.0
            session.feed(HandSample((0.3 + 0.4 * i / 79, 0.35), 0.09, t))
        live = session.reach_box()
        self.assertIsNotNone(live)
        report = session.finish()

        left, top, right, bottom = report.active_box
        self.assertLess(left, 0.3, "box must be padded beyond the measured reach")
        self.assertGreater(right, 0.7)
        self.assertGreaterEqual(left, 0.0)
        self.assertLessEqual(bottom, 1.0)
        self.assertGreater(right - left, 0.25)

    def test_lost_hand_is_counted_and_does_not_crash(self):
        session = CalibrationSession()
        session.begin(CalibrationPhase.PINCH)
        for _ in range(5):
            session.feed(None)
        run_pinch_phase(session, cycles=3)
        session.finish()
        self.assertGreater(session.lost_frames, 0)

    def test_reach_box_is_none_before_enough_samples(self):
        session = CalibrationSession()
        session.begin(CalibrationPhase.REACH)
        session.feed(HandSample((0.5, 0.5), 0.09, 0.0))
        self.assertIsNone(session.reach_box())

    def test_swipe_threshold_tracks_the_measured_flick(self):
        session = CalibrationSession()
        session.begin(CalibrationPhase.SWIPE)
        t = 0.0
        for i in range(40):
            t += 1.0 / 30.0
            x = 0.5 + (0.30 if i % 2 == 0 else -0.30)
            session.feed(HandSample((x, 0.5), 0.09, t))
        report = session.finish()
        # 0.60 units in 1/30 s is 18 units/s, far above the cap.
        self.assertGreaterEqual(report.swipe_velocity_threshold, 0.8)
        self.assertLessEqual(report.swipe_velocity_threshold, 4.0)

    def test_report_patch_covers_every_calibrated_gesture(self):
        patch = CalibrationReport().to_settings_patch()
        for key in (
            "gestures.pinch_click_threshold",
            "gestures.dead_zone_radius",
            "gestures.smoothing_factor",
            "gestures.cursor_speed",
            "gestures.active_box",
            "gestures.swipe_velocity_threshold",
            "gestures.calibrated",
        ):
            self.assertIn(key, patch)
        self.assertEqual(len(patch["gestures.active_box"]), 4)
        self.assertIs(patch["gestures.calibrated"], True)

    def test_session_can_resume_from_an_existing_report(self):
        report = CalibrationReport()
        report.pinch_threshold = 0.031
        session = CalibrationSession(report)
        self.assertIs(session.report, report)
        self.assertEqual(session.report.pinch_threshold, 0.031)


# --------------------------------------------------------------------------- #
# Adaptive tuner
# --------------------------------------------------------------------------- #

class TestAdaptiveTuner(unittest.TestCase):

    def _feed_cycles(self, tuner, frames=600, duty=0.5, seed=13,
                     closed=CLOSED_MEAN, opened=OPEN_MEAN, jitter=0.004):
        rng = random.Random(seed)
        t = 0.0
        block = 15
        for i in range(frames):
            t += 1.0 / 30.0
            is_open = (i // block) % 2 == 0
            distance = rng.gauss(opened if is_open else closed, 0.004)
            tuner.feed(
                (0.5 + rng.gauss(0, jitter), 0.5 + rng.gauss(0, jitter)),
                distance, t,
            )
            tuner.evaluate()

    def test_no_adaptation_before_the_window_is_warm(self):
        tuner = AdaptiveTuner(FakeSettings(), min_samples=45)
        rng = random.Random(2)
        for i in range(20):
            tuner.feed((0.5, 0.5), rng.gauss(0.02 if i % 2 else 0.08, 0.004), i / 30.0)
            self.assertIsNone(tuner.evaluate())
        self.assertFalse(tuner.is_warm)

    def test_steady_state_does_not_oscillate(self):
        """The failure mode this guards against: 0.03 <-> 0.04 every second."""
        tuner = AdaptiveTuner(FakeSettings(), persist_after=3, write_threshold=0.08)
        self._feed_cycles(tuner, frames=900)
        self.assertLessEqual(
            len(tuner.events), 3,
            "a steady hand must converge, not keep rewriting the config",
        )
        self.assertLessEqual(tuner.settings.writes, 3)
        self.assertGreater(tuner.pinch_threshold, CLOSED_MEAN)
        self.assertLess(tuner.pinch_threshold, OPEN_MEAN)

    def test_tracks_a_genuine_change_in_the_hand(self):
        tuner = AdaptiveTuner(FakeSettings(), persist_after=3, write_threshold=0.08)
        self._feed_cycles(tuner, frames=600)
        before = tuner.pinch_threshold
        self._feed_cycles(
            tuner, frames=1200, seed=21, closed=0.040, opened=0.110
        )
        after = tuner.pinch_threshold
        self.assertGreater(after, before + 0.005)
        self.assertLess(after, 0.110)

    def test_hysteresis_suppresses_changes_below_the_band(self):
        """A threshold within the band must not be rewritten at all."""
        settings = FakeSettings(**{
            AdaptiveTuner.PINCH_KEY: 0.038,
        })
        tuner = AdaptiveTuner(settings, persist_after=1, write_threshold=0.5)
        self._feed_cycles(tuner, frames=300)
        self.assertEqual(tuner.pinch_threshold, 0.038)
        self.assertEqual(settings.writes, 0)

    def test_reports_only_fire_after_persistence(self):
        tuner = AdaptiveTuner(FakeSettings(), persist_after=5, write_threshold=0.02)
        rng = random.Random(31)
        events = 0
        t = 0.0
        for i in range(400):
            t += 1.0 / 30.0
            is_open = (i // 15) % 2 == 0
            tuner.feed(
                (0.5, 0.5),
                rng.gauss(0.090 if is_open else 0.030, 0.004),
                t,
            )
            if tuner.evaluate() is not None:
                events += 1
        self.assertGreater(events, 0)
        self.assertLessEqual(tuner.settings.writes, events * 5)

    def test_hand_loss_clears_the_frame_trackers(self):
        tuner = AdaptiveTuner(FakeSettings())
        tuner.feed((0.1, 0.1), 0.05, 0.0)
        tuner.notify_hand_lost()
        # A huge jump straight after a loss must not be read as a flick.
        tuner.feed((0.9, 0.9), 0.05, 0.001)
        self.assertEqual(len(tuner._jitter_samples), 0)

    def test_reset_clears_the_window(self):
        tuner = AdaptiveTuner(FakeSettings(), min_samples=10)
        rng = random.Random(4)
        for i in range(60):
            tuner.feed((0.5, 0.5), rng.uniform(0.01, 0.09), i / 30.0)
        self.assertTrue(tuner.is_warm)
        tuner.reset()
        self.assertFalse(tuner.is_warm)
        self.assertEqual(tuner.events, [])

    def test_snapshot_exposes_the_live_values(self):
        tuner = AdaptiveTuner(FakeSettings(), min_samples=10)
        tuner.feed((0.5, 0.5), 0.04, 0.0)
        snap = tuner.snapshot()
        self.assertEqual(snap["samples"], 1.0)
        self.assertEqual(snap["warm"], 0.0)
        self.assertIn("pinch_threshold", snap)

    def test_a_failing_config_write_does_not_break_the_tuner(self):
        class LockedSettings(FakeSettings):
            def set(self, key, value, auto_save=True):
                raise OSError("read-only config")

        tuner = AdaptiveTuner(LockedSettings(), persist_after=1, write_threshold=0.02)
        rng = random.Random(9)
        t = 0.0
        for i in range(400):
            t += 1.0 / 30.0
            is_open = (i // 15) % 2 == 0
            tuner.feed((0.5, 0.5), rng.gauss(0.09 if is_open else 0.03, 0.004), t)
            tuner.evaluate()
        self.assertGreater(tuner.pinch_threshold, 0.03)


# --------------------------------------------------------------------------- #
# Hardware access safety
# --------------------------------------------------------------------------- #

class TestHardwareAccessIsSerialised(unittest.TestCase):
    """
    Concurrent DirectShow access aborts the interpreter.

    Two overlapping device scans used to take the process down with an access
    violation, which is what made the wizard crash on a repeated open.
    """

    def test_device_scan_claim_is_exclusive(self):
        from core.auto_calibration import begin_device_scan, end_device_scan

        self.addCleanup(end_device_scan)
        self.assertTrue(begin_device_scan())
        self.assertFalse(begin_device_scan())
        end_device_scan()
        self.assertTrue(begin_device_scan())

    def test_camera_probe_never_overlaps_itself(self):
        from unittest import mock

        import core.auto_calibration as ac

        active = 0
        peak = 0
        guard = threading.Lock()

        def fake_probe(indices, probe_seconds, width, height):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with guard:
                active -= 1
            return []

        threads = [
            threading.Thread(target=ac.probe_cameras, args=((0,),))
            for _ in range(8)
        ]
        with mock.patch.object(ac, "_probe_cameras", side_effect=fake_probe):
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5.0)

        self.assertEqual(peak, 1, "capture probes must not run concurrently")

    def test_timing_measurement_shares_the_same_lock(self):
        from unittest import mock

        import core.auto_calibration as ac

        active = 0
        peak = 0
        guard = threading.Lock()

        def fake_measure(camera_index, seconds, width, height):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with guard:
                active -= 1
            return {"fps": 30.0, "latency_ms": 12.0, "frames": 45.0, "ok": 1.0}

        threads = [
            threading.Thread(target=ac.measure_camera_timing, args=(0,))
            for _ in range(6)
        ]
        with mock.patch.object(ac, "_measure_camera_timing", side_effect=fake_measure):
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5.0)

        self.assertEqual(peak, 1)

    def test_a_probe_and_a_measurement_do_not_collide(self):
        """Both share one lock, so neither can hold the driver at once."""
        from unittest import mock

        import core.auto_calibration as ac

        active = 0
        peak = 0
        guard = threading.Lock()

        def body(*_args):
            nonlocal active, peak
            with guard:
                active += 1
                peak = max(peak, active)
            time.sleep(0.02)
            with guard:
                active -= 1
            return {}

        workers = [
            threading.Thread(target=ac.probe_cameras, args=((0,),)),
            threading.Thread(target=ac.measure_camera_timing, args=(0,)),
            threading.Thread(target=ac.probe_cameras, args=((1,),)),
        ]
        with mock.patch.object(ac, "_probe_cameras", side_effect=body), \
                mock.patch.object(ac, "_measure_camera_timing", side_effect=body):
            for thread in workers:
                thread.start()
            for thread in workers:
                thread.join(timeout=5.0)

        self.assertEqual(peak, 1)


class TestMicrophoneDegradesSafely(unittest.TestCase):
    """PyAudio is an optional import: the wizard must still work without it."""

    def _without_pyaudio(self):
        from unittest import mock

        import core.auto_calibration as ac

        patcher = mock.patch.object(ac, "HAS_PYAUDIO", False)
        patcher.start()
        self.addCleanup(patcher.stop)
        return ac

    def test_enumeration_returns_nothing_instead_of_raising(self):
        ac = self._without_pyaudio()
        self.assertEqual(ac.probe_microphones(), [])

    def test_measure_reports_failure_with_usable_defaults(self):
        ac = self._without_pyaudio()
        probe = ac.MicrophoneProbe(0)
        self.assertFalse(probe.available)

        levels = probe.measure(seconds=0.1)
        self.assertEqual(levels["ok"], 0.0)
        # The wizard writes these into the config, so they must be sane.
        self.assertGreater(levels["speech_threshold"], 0.0)
        self.assertLessEqual(levels["speech_threshold"], 1.0)
        self.assertEqual(levels["noise_floor"], 0.0)
        self.assertIn("pyaudio", probe.error.lower())

    def test_speech_threshold_tracks_the_measured_floor(self):
        ac = self._without_pyaudio()
        self.assertEqual(ac.MicrophoneProbe(None).device_index, None)
        low, high = ac.SPEECH_THRESHOLD_BOUNDS
        self.assertLess(low, high)
        self.assertGreaterEqual(low, 0.01)


# --------------------------------------------------------------------------- #
# Consumers of the calibration
# --------------------------------------------------------------------------- #

class TestRecognizerAdoptsTheReport(unittest.TestCase):
    """classify() reads the wall clock, so these tests drive a fake one."""

    @staticmethod
    def _pointing(x):
        """A hand that reaches the swipe branch: index only, no pinch contact."""
        return FakeLandmarks(
            index_tip=(x, 0.5),
            pinch_distance=0.09,
            index_extended=True,
            thumb_extended=True,
        )

    def _swipe_with_clock(self, threshold, xs, fps=30):
        from unittest import mock

        from vision.gesture_recognizer import HandGesture

        recognizer = GestureRecognizer()
        recognizer.update_calibration(swipe_velocity=threshold)
        clock = mock.MagicMock()
        seen = set()
        with mock.patch("vision.gesture_recognizer.time", clock):
            for frame, x in enumerate(xs):
                clock.time.return_value = 1000.0 + frame / fps
                gesture, _conf = recognizer.classify(self._pointing(x))
                seen.add(gesture)
        return seen, HandGesture

    def test_apply_report_sets_every_threshold(self):
        recognizer = GestureRecognizer()
        report = CalibrationReport()
        report.pinch_threshold = 0.028
        report.drag_hold_delay = 0.62
        report.double_pinch_window = 0.33
        report.swipe_velocity_threshold = 2.4
        report.scroll_dead_band = 0.021
        recognizer.apply_report(report)

        self.assertEqual(recognizer.pinch_threshold, 0.028)
        self.assertEqual(recognizer.drag_hold_delay, 0.62)
        self.assertEqual(recognizer.double_pinch_window, 0.33)
        self.assertEqual(recognizer.swipe_velocity_threshold, 2.4)
        self.assertEqual(recognizer.scroll_dead_band, 0.021)

    def test_slow_drift_is_not_a_swipe_at_a_high_threshold(self):
        seen, HandGesture = self._swipe_with_clock(
            6.0, [0.40 + 0.002 * i for i in range(12)]
        )
        self.assertNotIn(HandGesture.SWIPE_RIGHT, seen)
        self.assertNotIn(HandGesture.SWIPE_LEFT, seen)

    def test_a_fast_flick_still_triggers_a_swipe(self):
        seen, HandGesture = self._swipe_with_clock(
            1.8, [0.20 + 0.06 * i for i in range(12)]
        )
        self.assertIn(HandGesture.SWIPE_RIGHT, seen)

    def test_calibrated_threshold_decides_what_counts_as_a_flick(self):
        """The same motion is a swipe or not, purely on the measured value."""
        fast = [0.20 + 0.06 * i for i in range(12)]  # ~1.8 units/s

        strict_seen, HandGesture = self._swipe_with_clock(3.0, fast)
        self.assertNotIn(HandGesture.SWIPE_RIGHT, strict_seen)

        lenient_seen, _ = self._swipe_with_clock(1.5, fast)
        self.assertIn(HandGesture.SWIPE_RIGHT, lenient_seen)


class TestCursorAdoptsTheReachBox(unittest.TestCase):

    def setUp(self):
        self.cursor = VirtualCursor(screen_width=1920, screen_height=1080)

    def test_default_box_spans_the_whole_frame(self):
        self.assertEqual(self.cursor.active_box, (0.0, 0.0, 1.0, 1.0))
        self.assertEqual(
            self.cursor.remap_to_active_box(0.25, 0.75), (0.25, 0.75)
        )

    def test_reach_box_maps_its_corners_onto_the_screen(self):
        self.cursor.set_active_box((0.2, 0.2, 0.8, 0.6))
        self.assertAlmostEqual(self.cursor.remap_to_active_box(0.2, 0.2)[0], 0.0)
        self.assertAlmostEqual(self.cursor.remap_to_active_box(0.8, 0.6)[0], 1.0)
        self.assertAlmostEqual(self.cursor.remap_to_active_box(0.8, 0.6)[1], 1.0)
        self.assertAlmostEqual(self.cursor.remap_to_active_box(0.5, 0.4)[0], 0.5)

    def test_malformed_boxes_are_rejected(self):
        """A bad config value must never leave the cursor without a box."""
        for bad in ((0.5, 0.5, 0.5, 0.9), (0.0, 0.0, 0.0, 0.0), "nope", (1, 2), (0.1, 0.9)):
            with self.subTest(bad=bad):
                self.cursor.set_active_box((0.1, 0.1, 0.9, 0.9))
                self.cursor.set_active_box(bad)
                self.assertEqual(self.cursor.active_box, (0.1, 0.1, 0.9, 0.9))

    def test_clearing_the_box_returns_to_the_full_frame(self):
        """None means "never calibrated", which is the whole camera view."""
        self.cursor.set_active_box((0.1, 0.1, 0.9, 0.9))
        self.cursor.set_active_box(None)
        self.assertEqual(self.cursor.active_box, (0.0, 0.0, 1.0, 1.0))

    def test_box_coordinates_are_clamped_to_the_frame(self):
        self.cursor.set_active_box((-0.4, 0.1, 1.9, 0.9))
        left, top, right, bottom = self.cursor.active_box
        self.assertGreaterEqual(left, 0.0)
        self.assertLessEqual(right, 1.0)
        self.assertGreater(top, 0.0)

    def test_screen_position_stays_inside_the_display(self):
        """The reach corners map to exactly 0.0 and 1.0, so clamping matters."""
        self.cursor.set_active_box((0.2, 0.2, 0.8, 0.8))
        for nx, ny in ((0.2, 0.2), (0.8, 0.8), (0.5, 0.5), (0.0, 0.0), (1.0, 1.0)):
            x, y = self.cursor.map_normalized_to_screen(nx, ny)
            self.assertTrue(0 <= x < 1920, (nx, ny, x))
            self.assertTrue(0 <= y < 1080, (nx, ny, y))


if __name__ == "__main__":
    unittest.main()
