import unittest
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.security_engine import SecurityEngine, RiskLevel


class TestSecurityEngine(unittest.TestCase):

    def setUp(self):
        self.security = SecurityEngine()
        self.security.reset_emergency_stop()
        self.security.pending_command = None

    def test_risk_evaluation(self):
        self.assertEqual(self.security.evaluate_risk("LAUNCH_APP"), RiskLevel.LOW)
        self.assertEqual(self.security.evaluate_risk("DELETE_FILE"), RiskLevel.HIGH)
        self.assertEqual(self.security.evaluate_risk("SYSTEM_SHUTDOWN"), RiskLevel.HIGH)
        self.assertEqual(self.security.evaluate_risk("FORMAT_DISK"), RiskLevel.CRITICAL)

    def test_confirmation_lifecycle(self):
        executed = False

        def my_action():
            nonlocal executed
            executed = True

        # Request confirmation for high-risk shutdown
        self.security.request_confirmation(
            intent_name="SYSTEM_SHUTDOWN",
            command_text="أوقف تشغيل الكمبيوتر",
            action_fn=my_action
        )

        self.assertTrue(self.security.is_waiting_confirmation())
        self.assertFalse(executed)

        # Confirm via voice
        confirmed = self.security.confirm_pending(source="VOICE")
        self.assertTrue(confirmed)
        self.assertTrue(executed)
        self.assertFalse(self.security.is_waiting_confirmation())

    def test_emergency_stop(self):
        self.security.trigger_emergency_stop("TEST_TRIGGER")
        self.assertTrue(self.security.is_emergency_stopped)
        self.assertTrue(self.security.requires_confirmation("LAUNCH_APP"))

        self.security.reset_emergency_stop()
        self.assertFalse(self.security.is_emergency_stopped)


if __name__ == "__main__":
    unittest.main()
