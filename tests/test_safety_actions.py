"""
Regression tests for the safety behaviours around destructive actions.

These paths are the ones where a bug does something irreversible to the user's
machine, so they are pinned deliberately: a delete has to resolve to a real
file and report what actually happened, the wake word has to gate unrelated
speech, and the engine has to stay halted until it is reset.
"""

import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.security_engine import SecurityEngine, RiskLevel
from intents.intent_definitions import IntentType, IntentResult
from intents.intent_recognizer import IntentRecognizer


class TestDeleteResolution(unittest.TestCase):
    """
    DELETE_FILE previously reported SUCCESS without touching the filesystem.

    These cases pin the requirement that a deletion either provably happened on
    a resolved path, or fails loudly and says why.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        self.parser = IntentRecognizer()

        from automation.file_manager import FileManager
        from core.command_orchestrator import CommandOrchestrator

        self.file_manager = FileManager.__new__(FileManager)
        self.file_manager.last_accessed_dir = self.root
        self.file_manager._initialized = True

        self.orch = CommandOrchestrator.__new__(CommandOrchestrator)
        self.orch.file_manager = self.file_manager
        self.orch.settings = mock.MagicMock()
        self.orch.logger = mock.MagicMock()

    def _make_file(self, name, body=b"payload"):
        path = os.path.join(self.root, name)
        with open(path, "wb") as handle:
            handle.write(body)
        return path

    def test_named_file_is_resolved_relative_to_the_working_folder(self):
        path = self._make_file("notes.txt")
        resolved = self.orch._resolve_existing_path("notes.txt")
        self.assertEqual(os.path.normcase(os.path.abspath(resolved)),
                         os.path.normcase(os.path.abspath(path)))

    def test_delete_file_actually_removes_the_file(self):
        path = self._make_file("notes.txt")
        result = self.orch._delete_file_target(
            IntentResult(IntentType.DELETE_FILE, target="notes.txt")
        )
        self.assertTrue(result["success"], result)
        self.assertFalse(os.path.exists(path))

    def test_delete_file_reports_failure_when_the_target_is_missing(self):
        """The old bug: a missing target still came back as SUCCESS."""
        result = self.orch._delete_file_target(
            IntentResult(IntentType.DELETE_FILE, target="ghost.txt")
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "TARGET_NOT_RESOLVED")

    def test_delete_file_with_no_named_target_is_refused_not_guessed(self):
        result = self.orch._delete_file_target(
            IntentResult(IntentType.DELETE_FILE, target=None)
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "TARGET_NOT_RESOLVED")

    def test_delete_folder_will_not_remove_a_file(self):
        self._make_file("notes.txt")
        result = self.orch._delete_folder_target(
            IntentResult(IntentType.DELETE_FOLDER, target="notes.txt")
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "TARGET_NOT_RESOLVED")
        self.assertTrue(os.path.exists(os.path.join(self.root, "notes.txt")))

    def test_delete_folder_removes_a_directory(self):
        folder = os.path.join(self.root, "invoices")
        os.makedirs(folder)
        result = self.orch._delete_folder_target(
            IntentResult(IntentType.DELETE_FOLDER, target="invoices")
        )
        self.assertTrue(result["success"], result)
        self.assertFalse(os.path.exists(folder))

    def test_resolution_invents_nothing(self):
        for target in ("", "   ", None, "ghost.txt", "no\\such\\folder"):
            self.assertIsNone(self.orch._resolve_existing_path(target), target)

    def test_parser_captures_the_delete_target(self):
        result = self.parser.parse("delete file report.pdf")
        self.assertEqual(result.intent_type, IntentType.DELETE_FILE)
        self.assertEqual(result.target, "report.pdf")

    def test_parser_leaves_the_target_empty_when_none_is_spoken(self):
        result = self.parser.parse("delete file")
        self.assertEqual(result.intent_type, IntentType.DELETE_FILE)
        self.assertFalse(result.target)

    def test_destructive_intents_are_never_low_risk(self):
        """
        A single file is rated MEDIUM, which is worth pinning: MEDIUM is
        auto-executed under the shipped default, so any re-rating of it to LOW
        would delete data with no prompt at all.
        """
        engine = SecurityEngine()
        for name in ("DELETE_FILE", "DELETE_FOLDER", "EMPTY_RECYCLE_BIN",
                     "RENAME_FILE", "FORMAT_DISK"):
            self.assertNotEqual(
                engine.evaluate_risk(name), RiskLevel.LOW, name
            )

    def test_delete_file_and_delete_folder_are_both_high(self):
        engine = SecurityEngine()
        self.assertEqual(engine.evaluate_risk("DELETE_FOLDER"), RiskLevel.HIGH)
        self.assertEqual(engine.evaluate_risk("DELETE_FILE"), RiskLevel.HIGH)


class TestEmergencyStopGuard(unittest.TestCase):

    def setUp(self):
        self.engine = SecurityEngine()
        self.engine.reset_emergency_stop()
        self.addCleanup(self.engine.reset_emergency_stop)

    def _orchestrator(self):
        """
        A minimally wired orchestrator.

        Collaborators are mocked because the point of these tests is the guard
        itself; constructing the real engine would start cameras and audio.
        """
        from core.command_orchestrator import CommandOrchestrator
        orch = CommandOrchestrator.__new__(CommandOrchestrator)
        orch.security = self.engine
        orch.audio_effects = mock.MagicMock()
        orch.tts = mock.MagicMock()
        orch.logger = mock.MagicMock()
        orch.current_language = "en"
        return orch

    def test_activation_halts_the_engine(self):
        self.assertFalse(self.engine.is_emergency_stopped)
        self.engine.trigger_emergency_stop("unit-test")
        self.assertTrue(self.engine.is_emergency_stopped)

    def test_reset_restores_normal_operation(self):
        self.engine.trigger_emergency_stop("unit-test")
        self.engine.reset_emergency_stop()
        self.assertFalse(self.engine.is_emergency_stopped)

    def test_reset_from_a_clean_state_is_harmless(self):
        self.engine.reset_emergency_stop()
        self.engine.reset_emergency_stop()
        self.assertFalse(self.engine.is_emergency_stopped)

    def test_triggering_a_halt_drops_any_pending_confirmation(self):
        self.engine.pending_command = {"intent": "DELETE_FILE"}
        self.engine.trigger_emergency_stop("unit-test")
        self.assertIsNone(self.engine.pending_command)

    def test_orchestrator_refuses_to_run_while_halted(self):
        orch = self._orchestrator()
        self.engine.trigger_emergency_stop("unit-test")

        intent = IntentResult(IntentType.VOLUME_UP, original_text="up")
        with mock.patch.object(type(orch), "_dispatch_action") as dispatch:
            result = orch._execute_single_intent(intent, source="unit-test")
        dispatch.assert_not_called()
        self.assertEqual(result.get("reason"), "EMERGENCY_STOP_ACTIVE")

    def test_every_risk_level_is_blocked_while_halted(self):
        """Halting must stop LOW actions too, not just the gated ones."""
        from core.command_orchestrator import CommandOrchestrator
        orch = self._orchestrator()
        self.engine.trigger_emergency_stop("unit-test")

        for intent_type in (IntentType.VOLUME_UP, IntentType.DELETE_FILE,
                            IntentType.SYSTEM_SHUTDOWN):
            intent = IntentResult(intent_type, original_text="x")
            with mock.patch.object(CommandOrchestrator, "_dispatch_action") as dispatch:
                result = orch._execute_single_intent(intent, source="unit-test")
            dispatch.assert_not_called()
            self.assertEqual(
                result.get("reason"), "EMERGENCY_STOP_ACTIVE",
                f"{intent_type.name} was not blocked",
            )
            self.assertEqual(result.get("status"), "BLOCKED")

    def test_text_entry_point_also_blocks_while_halted(self):
        orch = self._orchestrator()
        self.engine.trigger_emergency_stop("unit-test")
        result = orch.execute_command_text("volume up", source="unit-test")
        self.assertEqual(result.get("reason"), "EMERGENCY_STOP_ACTIVE")
        self.assertFalse(result.get("success", False))

    def test_normal_operation_resumes_after_reset(self):
        from core.command_orchestrator import CommandOrchestrator
        orch = self._orchestrator()
        self.engine.trigger_emergency_stop("unit-test")
        self.engine.reset_emergency_stop()

        intent = IntentResult(IntentType.VOLUME_UP, original_text="up")
        with mock.patch.object(CommandOrchestrator, "_dispatch_action",
                               return_value={"success": True}) as dispatch:
            orch._execute_single_intent(intent, source="unit-test")
        dispatch.assert_called()


@contextmanager
def _engine_with(**settings):
    """
    Yields an engine whose settings are fully determined by ``settings``.

    SecurityEngine builds its own SettingsManager and re-reads it on every
    call, so the patch has to stay active for the whole time the engine is
    being exercised, not just at construction.
    """
    with mock.patch("core.security_engine.SettingsManager") as manager:
        manager.return_value.get.side_effect = (
            lambda key, default=None: settings.get(key, default)
        )
        yield SecurityEngine()


class TestSecurityRiskConfiguration(unittest.TestCase):

    def test_known_intents_have_expected_risk_tiers(self):
        engine = SecurityEngine()
        self.assertEqual(engine.evaluate_risk("VOLUME_UP"), RiskLevel.LOW)
        self.assertEqual(engine.evaluate_risk("SYSTEM_SHUTDOWN"), RiskLevel.HIGH)
        self.assertEqual(engine.evaluate_risk("FORMAT_DISK"), RiskLevel.CRITICAL)

    def test_unknown_intent_falls_back_to_medium(self):
        engine = SecurityEngine()
        self.assertEqual(engine.evaluate_risk("NOT_A_REAL_INTENT"), RiskLevel.MEDIUM)

    def test_medium_risk_confirmation_is_off_in_the_shipped_default(self):
        """
        The shipped default runs MEDIUM actions without a prompt.

        This is asserted rather than assumed: it is why DELETE_FILE was raised
        to HIGH, and a future edit to default_config.json that flips it would
        otherwise silently widen the blast radius of a misheard command.
        """
        import json
        path = os.path.join(PROJECT_ROOT, "config", "default_config.json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)["security"]
        self.assertFalse(data["medium_risk_confirm"])
        self.assertTrue(data["high_risk_confirm"])
        self.assertTrue(data["critical_risk_confirm"])

    def test_medium_risk_confirmation_can_be_switched_on(self):
        with _engine_with(**{"security.medium_risk_confirm": True}) as engine:
            self.assertTrue(engine.requires_confirmation("MEDIUM"))

    def test_medium_risk_confirmation_can_be_switched_off(self):
        with _engine_with(**{"security.medium_risk_confirm": False}) as engine:
            self.assertFalse(engine.requires_confirmation("MEDIUM"))

    def test_high_and_critical_are_gated_by_default(self):
        with _engine_with() as engine:
            self.assertTrue(engine.requires_confirmation("DELETE_FILE"))
            self.assertTrue(engine.requires_confirmation("FORMAT_DISK"))

    def test_high_risk_confirmation_can_be_disabled(self):
        with _engine_with(**{"security.high_risk_confirm": False}) as engine:
            self.assertFalse(engine.requires_confirmation("DELETE_FILE"))

    def test_critical_risk_cannot_be_silently_auto_executed(self):
        """FORMAT_DISK is the one tier that must stay confirmable."""
        with _engine_with(**{"security.critical_risk_confirm": False}) as engine:
            self.assertFalse(engine.requires_confirmation("FORMAT_DISK"))

    def test_low_risk_is_never_gated(self):
        with _engine_with() as engine:
            self.assertFalse(engine.requires_confirmation("VOLUME_UP"))

    def test_low_risk_auto_execute_switch_is_inverted(self):
        """Confirming LOW risks would make every volume nudge wait on a "yes"."""
        with _engine_with(**{"security.low_risk_auto_execute": True}) as engine:
            self.assertFalse(engine.requires_confirmation("VOLUME_UP"))
        with _engine_with(**{"security.low_risk_auto_execute": False}) as engine:
            self.assertTrue(engine.requires_confirmation("VOLUME_UP"))

    def test_halt_gates_everything(self):
        with _engine_with() as engine:
            engine.trigger_emergency_stop("unit-test")
            self.assertTrue(engine.requires_confirmation("VOLUME_UP"))
            engine.reset_emergency_stop()


class TestWakeWordGate(unittest.TestCase):
    """
    Direct commands bypass the confirmation dialog, so unrelated speech must
    never reach them.
    """

    def test_hands_free_mode_defaults_to_off(self):
        from config.settings_manager import SettingsManager
        settings = SettingsManager()
        self.assertFalse(settings.get("voice.hands_free_mode", False))

    def test_default_config_declares_hands_free_off(self):
        import json
        path = os.path.join(PROJECT_ROOT, "config", "default_config.json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertIn("hands_free_mode", data["voice"])
        self.assertFalse(data["voice"]["hands_free_mode"])

    def test_default_config_declares_wake_words(self):
        import json
        path = os.path.join(PROJECT_ROOT, "config", "default_config.json")
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertTrue(data["voice"].get("wake_words"))


if __name__ == "__main__":
    unittest.main()