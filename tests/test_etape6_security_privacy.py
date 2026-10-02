import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.security_engine import SecurityEngine, RiskLevel
from core.logger import EventLogger
from config.settings_manager import SettingsManager
import config.i18n as i18n
from config.i18n import tr


class TestEtape6SecurityPrivacy(unittest.TestCase):
    """Test suite covering Étape 6: Sécurité, Confidentialité, Kill Switch, Confirmation, and Audit Log."""

    def setUp(self):
        self.settings = SettingsManager()
        self.security = SecurityEngine()
        self.logger = EventLogger()

    def test_01_default_confirmation_timeout_is_5_seconds(self):
        """Verify the confirmation timeout defaults to 5.0s per Étape 6 spec."""
        self.assertEqual(self.security.timeout_seconds, 5.0)

    def test_02_destructive_actions_are_high_risk_and_gated(self):
        """Verify destructive actions require confirmation."""
        destructive_intents = [
            "DELETE_FILE",
            "DELETE_FOLDER",
            "EMPTY_RECYCLE_BIN",
            "SYSTEM_SHUTDOWN",
            "SYSTEM_RESTART",
            "SYSTEM_SLEEP",
        ]
        for intent in destructive_intents:
            risk = self.security.evaluate_risk(intent)
            self.assertEqual(risk, RiskLevel.HIGH, f"{intent} must be HIGH risk")
            self.assertTrue(
                self.security.requires_confirmation(intent),
                f"{intent} must require explicit confirmation"
            )

        # Critical risk
        self.assertEqual(self.security.evaluate_risk("FORMAT_DISK"), RiskLevel.CRITICAL)
        self.assertTrue(self.security.requires_confirmation("FORMAT_DISK"))

        # Low risk benign actions do not require confirmation by default
        self.assertFalse(self.security.requires_confirmation("VOLUME_UP"))
        self.assertFalse(self.security.requires_confirmation("SCREENSHOT"))

    def test_03_confirmation_flow_confirmed(self):
        """Verify requesting confirmation and confirming executes the action."""
        action_called = False
        cancel_called = False

        def _action():
            nonlocal action_called
            action_called = True

        def _cancel():
            nonlocal cancel_called
            cancel_called = True

        # Request confirmation
        accepted = self.security.request_confirmation(
            "DELETE_FILE",
            "delete important_file.txt",
            _action,
            _cancel
        )
        self.assertTrue(accepted)
        self.assertTrue(self.security.is_waiting_confirmation())

        # Confirm via button
        success = self.security.confirm_pending("BUTTON")
        self.assertTrue(success)
        self.assertTrue(action_called, "Action must have executed upon confirmation")
        self.assertFalse(cancel_called, "Cancel handler must not have run")
        self.assertFalse(self.security.is_waiting_confirmation())

    def test_04_confirmation_flow_rejected(self):
        """Verify rejecting confirmation does not execute action and runs cancel handler."""
        action_called = False
        cancel_called = False

        def _action():
            nonlocal action_called
            action_called = True

        def _cancel():
            nonlocal cancel_called
            cancel_called = True

        accepted = self.security.request_confirmation(
            "SYSTEM_SHUTDOWN",
            "shutdown",
            _action,
            _cancel
        )
        self.assertTrue(accepted)
        self.assertTrue(self.security.is_waiting_confirmation())

        # User cancels
        self.security.cancel_pending("USER_CLICK")
        self.assertFalse(action_called, "Action must NOT execute when rejected")
        self.assertTrue(cancel_called, "Cancel handler must execute")
        self.assertFalse(self.security.is_waiting_confirmation())

    def test_05_confirmation_timeout_auto_cancels(self):
        """Verify confirmation automatically times out after duration."""
        action_called = False
        cancel_called = False

        def _action():
            nonlocal action_called
            action_called = True

        def _cancel():
            nonlocal cancel_called
            cancel_called = True

        old_timeout = self.security.timeout_seconds
        self.security.timeout_seconds = 0.05
        try:
            self.security.request_confirmation(
                "EMPTY_RECYCLE_BIN",
                "empty recycle bin",
                _action,
                _cancel
            )
            time.sleep(0.08)
            # is_waiting_confirmation checks timestamp and cancels if expired
            waiting = self.security.is_waiting_confirmation()
            self.assertFalse(waiting, "Must expire after timeout")
            self.assertFalse(action_called)
            self.assertTrue(cancel_called)
        finally:
            self.security.timeout_seconds = old_timeout

    def test_06_emergency_stop_blocks_new_actions(self):
        """Verify emergency stop completely locks out confirmation requests."""
        self.security.trigger_emergency_stop("TEST_HALT")
        try:
            self.assertTrue(self.security.is_emergency_stopped)
            res = self.security.request_confirmation(
                "DELETE_FILE", "delete file", lambda: None
            )
            self.assertFalse(res, "Request confirmation must be rejected under emergency stop")
        finally:
            self.security.reset_emergency_stop()
            self.assertFalse(self.security.is_emergency_stopped)

    def test_07_event_logger_export_csv_and_clear(self):
        """Verify EventLogger records, exports to CSV with UTF-8 BOM, and clears cleanly."""
        self.logger.clear()
        self.assertEqual(len(self.logger.get_recent_events()), 0)

        # Log actions
        self.logger.log(
            command="supprimer fichier",
            intent="DELETE_FILE",
            action="delete_file",
            result="CONFIRMED",
            confidence=0.98,
            risk_level="HIGH",
            source="VOICE"
        )
        self.logger.log(
            command="capture d'écran",
            intent="SCREENSHOT",
            action="screenshot",
            result="SUCCESS",
            confidence=1.0,
            risk_level="LOW",
            source="GESTURE"
        )

        events = self.logger.get_recent_events()
        self.assertEqual(len(events), 2)

        # Export CSV
        csv_path = self.logger.export_csv()
        self.assertTrue(os.path.exists(csv_path))
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
            self.assertIn("DELETE_FILE", content)
            self.assertIn("SCREENSHOT", content)

        # Clear audit log
        self.logger.clear()
        self.assertEqual(len(self.logger.get_recent_events()), 0)

    def test_08_i18n_security_and_privacy_keys_parity(self):
        """Verify all privacy, confirmation, and log keys exist across EN, FR, and AR."""
        required_keys = [
            "privacy.mode",
            "privacy.mode_active",
            "privacy.cam_on",
            "privacy.cam_off",
            "privacy.mic_on",
            "privacy.mic_off",
            "toast.privacy_mode_activated",
            "toast.privacy_mode_deactivated",
            "security.prompt_delete",
            "security.prompt_empty_bin",
            "security.prompt_shutdown",
            "security.prompt_restart",
            "security.prompt_close",
            "security.confirm_btn",
            "security.cancel_btn",
            "security.countdown",
            "log.clear",
            "log.clear_confirm_title",
            "log.clear_confirm_msg",
            "toast.log_cleared",
        ]

        langs = ["en", "fr", "ar"]
        for lang in langs:
            table = i18n.STRINGS.get(lang, {})
            for key in required_keys:
                self.assertIn(
                    key, table,
                    f"Missing translation key '{key}' in language '{lang}'"
                )
                val = table[key]
                self.assertTrue(len(val) > 0, f"Empty translation for '{key}' in '{lang}'")

    def test_09_i18n_format_strings(self):
        """Verify template strings format without syntax/key errors in all languages."""
        for lang in ["en", "fr", "ar"]:
            i18n.set_language(lang)
            del_prompt = tr("security.prompt_delete", target="document.pdf")
            self.assertIn("document.pdf", del_prompt)

            countdown_prompt = tr("security.countdown", seconds=4)
            self.assertIn("4", countdown_prompt)


if __name__ == "__main__":
    unittest.main()
