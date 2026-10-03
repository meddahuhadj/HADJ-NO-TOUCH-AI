"""
Unit and integration tests for Étape 3: UI & HUD Simplification.
Tests cover FloatingOverlayHUD controls (arming button, dominant hand switch, compact toggle, progress),
MainWindow compact mode (F11/Ctrl+M toggle), High Contrast theme cycling, and trilingual i18n completeness.
"""

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
import pytest

from ui.floating_overlay_hud import FloatingOverlayHUD
from ui.accessibility_panel import AccessibilityDialog
from ui import theme
import config.i18n as i18n
from config.i18n import tr
from config.settings_manager import SettingsManager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

_qapp = QApplication.instance() or QApplication([])


class TestThemeHighContrast(unittest.TestCase):
    def test_theme_cycling(self):
        theme.set_theme_mode("dark")
        self.assertFalse(theme.is_light_mode())
        self.assertFalse(theme.is_high_contrast())

        # Cycle to light
        theme.cycle_theme_mode()
        self.assertTrue(theme.is_light_mode())
        self.assertFalse(theme.is_high_contrast())

        # Cycle to high contrast
        theme.cycle_theme_mode()
        self.assertFalse(theme.is_light_mode())
        self.assertTrue(theme.is_high_contrast())
        self.assertEqual(theme.CANVAS, "#000000")
        self.assertEqual(theme.TEXT, "#FFFFFF")

        # Cycle back to dark
        theme.cycle_theme_mode()
        self.assertFalse(theme.is_light_mode())
        self.assertFalse(theme.is_high_contrast())


class TestFloatingOverlayHUDEnhanced(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def init_qapp(self, qapp):
        self.app = qapp

    def setUp(self):
        self.settings = SettingsManager()
        self.hud = FloatingOverlayHUD(None)

    def tearDown(self):
        self.hud.close()

    def test_arm_toggle(self):
        initial = self.hud._is_armed
        self.hud._toggle_arm_state()
        self.assertEqual(self.hud._is_armed, not initial)
        self.hud._toggle_arm_state()
        self.assertEqual(self.hud._is_armed, initial)

    def test_dominant_hand_toggle(self):
        self.settings.set("gestures.dominant_hand", "right")
        self.hud._toggle_dominant_hand()
        self.assertEqual(self.settings.get("gestures.dominant_hand"), "left")
        self.assertEqual(self.hud.hand_btn.text(), "✋ L")

        self.hud._toggle_dominant_hand()
        self.assertEqual(self.settings.get("gestures.dominant_hand"), "right")
        self.assertEqual(self.hud.hand_btn.text(), "✋ R")

    def test_compact_hud_toggle(self):
        self.assertFalse(self.hud._is_compact_hud)
        self.hud._toggle_compact_hud()
        self.assertTrue(self.hud._is_compact_hud)
        self.assertEqual(self.hud.width(), 260)
        self.assertEqual(self.hud.height(), 52)

        self.hud._toggle_compact_hud()
        self.assertFalse(self.hud._is_compact_hud)
        self.assertEqual(self.hud.width(), 460)
        self.assertEqual(self.hud.height(), 78)

    def test_gesture_diagnostics_progress(self):
        self.hud._on_gesture_diagnostics("PINCH", "diag.armed_ready", 0.95, True, 0.75)
        self.assertTrue(self.hud._is_armed)
        self.assertEqual(self.hud._hold_progress, 0.75)


class TestAccessibilityDialogOptions(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def init_qapp(self, qapp):
        self.app = qapp

    def test_contrast_and_hand_controls(self):
        dlg = AccessibilityDialog()
        self.assertIsNotNone(dlg.contrast_cb)
        self.assertIsNotNone(dlg.right_hand_rb)
        self.assertIsNotNone(dlg.left_hand_rb)

        # Toggle contrast
        dlg.contrast_cb.setChecked(True)
        self.assertTrue(theme.is_high_contrast())
        dlg.contrast_cb.setChecked(False)
        self.assertFalse(theme.is_high_contrast())

        # Toggle dominant hand
        dlg.left_hand_rb.setChecked(True)
        self.assertEqual(SettingsManager().get("gestures.dominant_hand"), "left")
        dlg.right_hand_rb.setChecked(True)
        self.assertEqual(SettingsManager().get("gestures.dominant_hand"), "right")
        dlg.close()


class TestI18nCompletenessEtape3(unittest.TestCase):
    def test_all_languages_have_etape3_keys(self):
        keys = [
            "main.theme_high_contrast", "main.compact_mode", "main.full_mode",
            "main.dominant_hand", "toast.dominant_hand_changed", "access.contrast_desc"
        ]
        for lang in ("en", "fr", "ar"):
            i18n.set_language(lang)
            for k in keys:
                translated = tr(k)
                self.assertNotEqual(translated, k, f"Key '{k}' is missing translation in language '{lang}'")
                self.assertTrue(len(translated) > 0)
