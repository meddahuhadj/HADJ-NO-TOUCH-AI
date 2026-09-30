"""
Regression tests for the calibration wizard.

These run against the offscreen Qt platform so no display is required, and no
camera is opened: frames are injected straight into the preview's landmark
signal, which is the same path the worker uses.
"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config.i18n as i18n
from core.auto_calibration import CalibrationPhase

_APP = None


def setUpModule():
    global _APP
    from PySide6.QtWidgets import QApplication

    _APP = QApplication.instance() or QApplication([])


def snapshot(x=0.5, y=0.5, pinch=0.09):
    from ui.calibration_preview import HandSnapshot

    return HandSnapshot((x, y), pinch, None)


class WizardTestCase(unittest.TestCase):

    def setUp(self):
        from ui.calibration_wizard import CalibrationWizardDialog

        i18n.set_language("en", persist=False)
        self.dialog = CalibrationWizardDialog()
        self.addCleanup(self.dialog.done, 0)


class TestStepLifecycle(WizardTestCase):
    """The timer that refreshes each step must actually be running."""

    def _is_ticking(self, step):
        from ui import calibration_wizard as cw

        self.dialog.current_step = step
        self.dialog._enter_step()
        return self.dialog._tick.isActive()

    def test_hand_step_refreshes_its_status(self):
        """Regression: the tick was never started on the hand step."""
        from ui import calibration_wizard as cw

        self.assertTrue(self._is_ticking(cw.STEP_HAND))
        self.assertIsNotNone(self.dialog._tick_hand)

    def test_measurement_and_adaptive_steps_tick(self):
        from ui import calibration_wizard as cw

        for step in (cw.STEP_PINCH, cw.STEP_REACH, cw.STEP_ADAPTIVE):
            with self.subTest(step=step):
                self.assertTrue(self._is_ticking(step))

    def test_passive_steps_do_not_tick(self):
        from ui import calibration_wizard as cw

        for step in (cw.STEP_DEVICES, cw.STEP_CAMERA, cw.STEP_MIC):
            with self.subTest(step=step):
                self.assertFalse(self._is_ticking(step))

    def test_summary_stops_the_timer(self):
        from ui import calibration_wizard as cw

        self._is_ticking(cw.STEP_ADAPTIVE)
        self.assertTrue(self.dialog._tick.isActive())
        self.dialog.current_step = cw.STEP_SUMMARY
        self.dialog._enter_step()
        self.assertFalse(self.dialog._tick.isActive())
        self.assertTrue(self.dialog._summary_built)


class TestFrameRateSampling(WizardTestCase):
    """Samples must be taken per frame, not on the refresh timer."""

    def _enter(self, step, phase):
        from core.auto_calibration import CalibrationSession

        self.dialog.current_step = step
        self.dialog.session = CalibrationSession(self.dialog.report)
        self.dialog.session.begin(phase)
        self.dialog._enter_step()

    def test_every_injected_frame_becomes_a_sample(self):
        """Regression: sampling used to be capped by the 90 ms timer."""
        from ui import calibration_wizard as cw

        self._enter(cw.STEP_PINCH, CalibrationPhase.PINCH)
        for i in range(80):
            # Start closed and alternate in 10-frame blocks, so the four
            # close->open transitions look like four deliberate pinches.
            self.dialog.preview.landmarks.emit(
                snapshot(pinch=0.075 if (i // 10) % 2 == 1 else 0.018)
            )
        self.assertEqual(self.dialog.session.phase_samples, 80)
        self.assertGreaterEqual(self.dialog.session.pinch_cycles, 4)

    def test_lost_hand_is_reported_per_frame(self):
        from ui import calibration_wizard as cw

        self._enter(cw.STEP_PINCH, CalibrationPhase.PINCH)
        for _ in range(5):
            self.dialog.preview.landmarks.emit(None)
        self.assertEqual(self.dialog.session.lost_frames, 5)
        self.assertEqual(self.dialog.session.phase_samples, 0)

    def test_frames_are_ignored_on_passive_steps(self):
        from ui import calibration_wizard as cw

        self.dialog.current_step = cw.STEP_DEVICES
        self.dialog._enter_step()
        self.dialog.session = None
        for _ in range(10):
            self.dialog.preview.landmarks.emit(snapshot())
        self.assertIsNone(self.dialog.session)

    def test_adaptive_step_feeds_the_live_tuner(self):
        from ui import calibration_wizard as cw

        self.dialog.current_step = cw.STEP_ADAPTIVE
        self.dialog._enter_step()
        for _ in range(12):
            self.dialog.preview.landmarks.emit(snapshot())
        self.assertEqual(self.dialog.live_tuner.snapshot()["samples"], 12.0)

    def test_reach_box_updates_while_sweeping(self):
        from ui import calibration_wizard as cw

        self._enter(cw.STEP_REACH, CalibrationPhase.REACH)
        for i in range(60):
            self.dialog.preview.landmarks.emit(
                snapshot(x=0.3 + 0.4 * i / 59, y=0.5)
            )
        box = self.dialog.session.reach_box()
        self.assertIsNotNone(box)
        # The live box is the raw extent of what was seen; the padding meant to
        # make the edges forgiving is only applied when the phase is committed.
        self.assertLessEqual(box[0], 0.3)
        self.assertGreaterEqual(box[2], 0.7)


class TestTranslations(WizardTestCase):

    def _walk_every_step(self):
        from ui.calibration_wizard import TOTAL_STEPS

        for step in range(TOTAL_STEPS):
            self.dialog.current_step = step
            self.dialog._enter_step()

    def test_every_step_resolves_in_all_languages(self):
        from ui.calibration_wizard import TOTAL_STEPS

        for lang in ("en", "fr", "ar"):
            with self.subTest(lang=lang):
                i18n.set_language(lang, persist=False)
                self._walk_every_step()
                self.assertTrue(self.dialog._summary_built)
                self.assertEqual(
                    len(self.dialog.summary_rows),
                    len(self.dialog._summary_entries()),
                )
                unresolved = [
                    binding.widget.text()
                    for page in self.dialog.pages
                    for binding in page.texts
                    if binding.widget.text().startswith("calib.")
                ]
                self.assertEqual(unresolved, [])

    def test_adaptive_widgets_follow_the_language(self):
        """Regression: these two were built outside the page bindings."""
        from ui import calibration_wizard as cw

        self.dialog.current_step = cw.STEP_ADAPTIVE
        self.dialog._enter_step()
        english = self.dialog.adaptive_check.text()

        i18n.set_language("ar", persist=False)
        self.dialog.retranslate()
        arabic = self.dialog.adaptive_check.text()

        self.assertNotEqual(english, arabic)
        self.assertFalse(arabic.startswith("calib."))
        self.assertFalse(self.dialog.adaptive_note.text().startswith("calib."))

    def test_language_switch_preserves_measured_values(self):
        from ui import calibration_wizard as cw

        self.dialog.report.pinch_threshold = 0.0312
        self.dialog.current_step = cw.STEP_SUMMARY
        self.dialog._enter_step()
        before = self.dialog.summary_rows["pinch_click_threshold"][0].text()

        i18n.set_language("ar", persist=False)
        self.dialog.retranslate()

        self.assertEqual(
            self.dialog.summary_rows["pinch_click_threshold"][0].text(), before
        )
        self.assertNotEqual(self.dialog.step_label.text(), "")
        self.assertFalse(self.dialog.step_label.text().startswith("common."))


class TestShutdown(WizardTestCase):

    def test_closing_mid_device_scan_does_not_crash(self):
        """Regression: the scan used to be a QThread and killed the process."""
        dialog = self.dialog
        dialog.done(0)
        self.assertFalse(dialog._tick.isActive())

    def test_apply_persists_the_report(self):
        from ui import calibration_wizard as cw

        self.dialog.report.pinch_threshold = 0.0295
        self.dialog.report.calibrated = True
        self.dialog.adaptive_check.setChecked(True)
        self.dialog.settings.set("calibration.adaptive_tuning", False)

        self.dialog.current_step = cw.STEP_SUMMARY
        self.dialog._enter_step()
        self.dialog._apply_and_close()

        self.assertEqual(
            self.dialog.settings.get("gestures.pinch_click_threshold"), 0.0295
        )
        self.assertIs(self.dialog.settings.get("gestures.calibrated"), True)
        self.assertIs(self.dialog.settings.get("calibration.adaptive_tuning"), True)
        self.assertEqual(
            self.dialog.settings.get("calibration.last_run") is not None, True
        )


if __name__ == "__main__":
    unittest.main()
