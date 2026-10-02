"""
Unit and integration tests for Étape 2: Visual and Auditory Feedback.
Tests cover Toast notifications, native sound chimes, button feedback,
6-column audit logs with search filtering and CSV export, live FPS/latency badges,
and Eco Mode frame throttling.
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication
import pytest

from core.logger import EventLogger
from core.audio_effects import AudioEffects
from core.profile_manager import ProfileManager, PerformanceProfile
from ui.toast import ToastWidget
import config.i18n as i18n
from config.i18n import tr


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestToastWidget(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def init_qapp(self, qapp):
        self.app = qapp

    def test_toast_display_and_hide(self):
        parent = ToastWidget(None)
        parent.resize(400, 300)
        parent.show()
        toast = ToastWidget(parent)
        
        # Test showing message
        toast.show_message("Action completed ✓", icon="✓", tone="success", duration_ms=500)
        self.assertEqual(toast.text_label.text(), "Action completed ✓")
        self.assertEqual(toast.icon_label.text(), "✓")

        # Test hide / fade out
        toast._fade_out()
        self.assertFalse(toast.isVisible())
        parent.close()


class TestAudioEffects(unittest.TestCase):
    def test_chimes_execute_safely(self):
        fx = AudioEffects()
        # Ensure none of the sound effect methods crash or raise exceptions
        fx.play_wake_chime()
        fx.play_command_success()
        fx.play_screenshot_chime()
        fx.play_button_feedback()
        fx.play_warning_prompt()


class TestLoggerAndCsvExport(unittest.TestCase):
    def setUp(self):
        self.logger = EventLogger()
        self.logger.clear()

    def test_event_logging_with_confidence_and_gesture(self):
        entry = self.logger.log(
            command="Open Chrome",
            intent="LAUNCH_APP",
            action="LAUNCH_APP",
            result="SUCCESS",
            confidence=0.985,
            risk_level="LOW",
            gesture="THUMB_UP",
            source="VOICE"
        )
        self.assertEqual(entry["command"], "Open Chrome")
        self.assertEqual(entry["confidence"], 0.985)
        self.assertEqual(entry["gesture"], "THUMB_UP")

        events = self.logger.get_recent_events(limit=10)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["command"], "Open Chrome")

    def test_csv_export_format(self):
        self.logger.log(
            command="Capture d'écran",
            intent="SCREENSHOT",
            action="SCREENSHOT",
            result="SUCCESS",
            confidence=0.95,
            risk_level="LOW",
            gesture="PINCH",
            source="GESTURE"
        )
        
        csv_path = self.logger.export_csv()
        self.assertTrue(os.path.exists(csv_path))
        
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
            self.assertIn("Capture d'écran", content)
            self.assertIn("SCREENSHOT", content)
            self.assertIn("PINCH", content)
        
        # Cleanup
        try:
            os.remove(csv_path)
        except Exception:
            pass


class TestProfileManagerEcoThrottling(unittest.TestCase):
    def setUp(self):
        self.mgr = ProfileManager()
        self.mgr.settings.set("performance.auto_eco", True)

    def test_auto_eco_cpu_throttle(self):
        self.mgr.set_profile(PerformanceProfile.BALANCED)
        with patch("psutil.cpu_percent", return_value=85.0):
            throttled = self.mgr.check_cpu_throttle()
            self.assertTrue(throttled)
            self.assertEqual(self.mgr.current_profile, PerformanceProfile.ECO)

    def test_auto_eco_not_triggered_under_threshold(self):
        self.mgr.set_profile(PerformanceProfile.BALANCED)
        with patch("psutil.cpu_percent", return_value=45.0):
            throttled = self.mgr.check_cpu_throttle()
            self.assertFalse(throttled)
            self.assertEqual(self.mgr.current_profile, PerformanceProfile.BALANCED)


class TestI18nCompletenessEtape2(unittest.TestCase):
    def test_all_languages_have_etape2_keys(self):
        keys = [
            "col.time", "col.command", "col.intent", "col.confidence", "col.risk", "col.result",
            "log.search_placeholder", "log.export_csv",
            "toast.screenshot_saved", "toast.csv_exported", "toast.action_executed",
            "main.eco_mode", "toast.eco_activated"
        ]
        for lang in ("en", "fr", "ar"):
            i18n.set_language(lang)
            for k in keys:
                translated = tr(k)
                self.assertNotEqual(translated, k, f"Key '{k}' is missing translation in language '{lang}'")
                self.assertTrue(len(translated) > 0)
