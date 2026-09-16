"""Tests for the v2.0 subsystems: Safety, Demo, History, Performance,
Macro Studio, AI Planner, Custom Commands, Head Control and Test Lab,
plus their wiring inside AppCore.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from hadj_no_touch.database.database import Database
from hadj_no_touch.config import GestureSettings


class TestSafety:
    def test_registry_predefined(self) -> None:
        from hadj_no_touch.safety import ActionRegistry, RISK_CONFIRM, RISK_CRITICAL
        reg = ActionRegistry()
        assert reg.known("LEFT_CLICK")
        assert reg.known("CLOSE_WINDOW")
        assert reg.known("SHUTDOWN")
        assert reg.risk("CLOSE_WINDOW") == RISK_CONFIRM
        assert reg.risk("SHUTDOWN") == RISK_CRITICAL
        assert reg.risk("LEFT_CLICK") == "safe"

    def test_smart_level_confirms_sensitive(self) -> None:
        from hadj_no_touch.safety import SafetyEngine
        eng = SafetyEngine(confirmation_level="smart")
        assert eng.decide("CLOSE_WINDOW").requires_confirmation
        assert not eng.decide("LEFT_CLICK").requires_confirmation
        assert eng.decide("SHUTDOWN").requires_confirmation

    def test_none_level_still_confirms_critical(self) -> None:
        from hadj_no_touch.safety import SafetyEngine
        eng = SafetyEngine(confirmation_level="none")
        assert not eng.decide("CLOSE_WINDOW").requires_confirmation
        assert eng.decide("SHUTDOWN").requires_confirmation

    def test_all_level_confirms_except_safety_toggles(self) -> None:
        from hadj_no_touch.safety import SafetyEngine
        eng = SafetyEngine(confirmation_level="all")
        assert eng.decide("LEFT_CLICK").requires_confirmation
        assert not eng.decide("EMERGENCY_STOP").requires_confirmation
        assert not eng.decide("PAUSE_CONTROL").requires_confirmation

    def test_unknown_action_denied_by_default(self) -> None:
        from hadj_no_touch.safety import SafetyEngine
        d = SafetyEngine().decide("TOTALLY_UNKNOWN_XYZ")
        assert not d.allowed
        assert d.reason

    def test_allowlist_restricts_and_clears(self) -> None:
        from hadj_no_touch.safety import SafetyEngine
        eng = SafetyEngine(allowed_actions=["LEFT_CLICK"])
        assert eng.decide("LEFT_CLICK").allowed
        assert not eng.decide("NEXT_SLIDE").allowed
        eng.set_allowed_actions(None)
        assert eng.decide("NEXT_SLIDE").allowed

    def test_laser_pointer_registered_safe(self) -> None:
        from hadj_no_touch.safety import ActionRegistry
        reg = ActionRegistry()
        assert reg.known("LASER_POINTER")
        assert reg.risk("LASER_POINTER") == "safe"

    def test_audit_ring(self) -> None:
        from hadj_no_touch.safety import SafetyEngine
        eng = SafetyEngine()
        eng.audit("LEFT_CLICK", "OK")
        assert eng.recent_audit()[0]["action"] == "LEFT_CLICK"


class TestDemo:
    def test_toggle_cycles(self) -> None:
        from hadj_no_touch.demo import DemoMode
        d = DemoMode(False)
        assert not d.enabled
        d.set_enabled(True)
        assert d.enabled
        assert d.toggle() is False

    def test_simulate_marks_text(self) -> None:
        from hadj_no_touch.demo import DemoMode
        assert "DEMO" in DemoMode(True).simulate("VOLUME_UP")


class TestHistory:
    def test_record_and_recent(self) -> None:
        from hadj_no_touch.history import ActionHistory, STATUS_SIMULATED
        h = ActionHistory()
        h.record("gesture", "LEFT_CLICK")
        h.record("voice", "VOLUME_UP", status=STATUS_SIMULATED, simulated=True)
        recent = h.recent()
        assert len(recent) == 2
        assert recent[-1]["simulated"] is True

    def test_analytics_counts(self) -> None:
        from hadj_no_touch.history import ActionHistory
        h = ActionHistory()
        h.record("voice", "LEFT_CLICK")
        h.record("gesture", "LEFT_CLICK")
        a = h.analytics()
        assert a["actions"] == 2
        assert a["by_action"] == {"LEFT_CLICK": 2}
        assert a["by_source"] == {"voice": 1, "gesture": 1}

    def test_analytics_empty(self) -> None:
        from hadj_no_touch.history import ActionHistory
        a = ActionHistory().analytics()
        assert a["actions"] == 0
        assert a["accuracy"] == 1.0


class TestPerformance:
    def test_fps_and_commands(self) -> None:
        from hadj_no_touch.performance import PerformanceMonitor
        p = PerformanceMonitor()
        p.note_frame(16.0)
        p.note_frame(20.0)
        p.note_command()
        snap = p.snapshot()
        assert snap["frame_ms"] == 18.0
        assert snap["fps"] == pytest.approx(1000.0 / 18.0, rel=0.1)
        assert snap["commands_per_minute"] == 1.0

    def test_environment_quality_dark_frame(self) -> None:
        from hadj_no_touch.performance import EnvironmentQuality
        try:
            import cv2
        except ImportError:
            pytest.skip("opencv not installed")
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        rep = EnvironmentQuality().estimate(frame)
        assert rep is not None
        assert rep.lighting == "dark"
        assert rep.brightness == pytest.approx(0.0, abs=0.01)


class TestMacroRunner:
    def test_add_duplicate(self) -> None:
        from hadj_no_touch.macros import MacroRunner, Macro
        mr = MacroRunner()
        mr.add(Macro("m", "voice", "hello", [{"action": "HELP"}]))
        err = mr.add(Macro("m", "voice", "bye", [{"action": "HELP"}]))
        assert err is not None

    def test_voice_match_substring(self) -> None:
        from hadj_no_touch.macros import MacroRunner, Macro
        calls = []
        mr = MacroRunner(executor=lambda i: (calls.append(i.action), True)[1])
        mr.add(Macro("w", "voice", "open work mode",
                     [{"action": "PROFILE_SWITCH", "params": {"profile": "developer"}}]))
        m = mr.find_voice("please open work mode now")
        assert m is not None
        assert mr.run(m)
        assert calls == ["PROFILE_SWITCH"]

    def test_gesture_trigger(self) -> None:
        from hadj_no_touch.macros import MacroRunner, Macro
        mr = MacroRunner()
        mr.add(Macro("lock", "gesture", "FIST_LOCK", [{"action": "HELP"}]))
        assert mr.find_gesture("FIST_LOCK") is not None
        assert mr.find_gesture("CIRCLE_CW") is None

    def test_serialization_roundtrip(self) -> None:
        from hadj_no_touch.macros import MacroRunner, Macro
        mr = MacroRunner()
        mr.add(Macro("w", "voice", "go work",
                     [{"action": "OPEN_APP", "params": {"app": "chrome"}}],
                     description="d", enabled=True))
        mr2 = MacroRunner()
        mr2.load_list(mr.to_list())
        assert mr2.get("w").actions[0]["params"] == {"app": "chrome"}

    def test_missing_executor_returns_false(self) -> None:
        from hadj_no_touch.macros import MacroRunner, Macro
        mr = MacroRunner()
        mr.add(Macro("w", "voice", "x", [{"action": "HELP"}]))
        assert not mr.run(mr.get("w"))


class TestPlanner:
    def _planner(self):
        from hadj_no_touch.planner import ActionPlanner
        return ActionPlanner()

    def test_presentation_plan(self) -> None:
        actions = [s.action for s in self._planner().plan("prepare my presentation").steps]
        assert "PROFILE_SWITCH" in actions
        assert "START_PRESENTATION" in actions

    def test_work_plan(self) -> None:
        actions = [s.action for s in self._planner().plan("take me to work setup").steps]
        assert "PROFILE_SWITCH" in actions

    def test_unknown_text_empty(self) -> None:
        plan = self._planner().plan("asdfgh completely gibberish")
        assert plan.is_empty()

    def test_french_and_arabic_plans(self) -> None:
        fr = [s.action for s in self._planner().plan("prépare ma présentation").steps]
        assert "START_PRESENTATION" in fr
        ar = [s.action for s in self._planner().plan("تجهيز عرض تقديمي").steps]
        assert "START_PRESENTATION" in ar
        work_ar = [s.action for s in self._planner().plan("بيئة عمل").steps]
        assert "PROFILE_SWITCH" in work_ar


class TestCustomCommands:
    def test_add_match_delete(self) -> None:
        from hadj_no_touch.custom_commands import CustomCommandRegistry, CustomCommand
        reg = CustomCommandRegistry()
        assert reg.add(CustomCommand(phrase="boost volume", action="VOLUME_UP")) is None
        assert reg.add(CustomCommand(phrase="boost volume", action="MUTE")) is not None
        got = reg.match("please boost volume", language="en")
        assert got is not None and got.action == "VOLUME_UP"
        assert reg.remove("boost volume")
        assert reg.match("boost volume") is None

    def test_language_filter(self) -> None:
        from hadj_no_touch.custom_commands import CustomCommandRegistry, CustomCommand
        reg = CustomCommandRegistry()
        reg.add(CustomCommand(phrase="ouvrir", action="OPEN_APP",
                             params={"app": "chrome"}, language="fr"))
        assert reg.match("ouvrir", "fr") is not None
        assert reg.match("ouvrir", "en") is None


class TestHeadControl:
    def test_estimate_direction(self) -> None:
        from hadj_no_touch.head_tracking import estimate_direction
        pts = np.full((468, 2), 0.5, dtype=np.float32)
        pts[1] = (0.8, 0.5)
        direction, conf = estimate_direction(pts, sensitivity=0.12)
        assert direction == "HEAD_RIGHT"
        assert 0 < conf <= 1.0

    def test_neutral_on_aligned_nose(self) -> None:
        from hadj_no_touch.head_tracking import estimate_direction
        pts = np.full((468, 2), 0.5, dtype=np.float32)
        direction, _ = estimate_direction(pts, sensitivity=0.5)
        assert direction == "NEUTRAL"

    def test_context_mapping(self) -> None:
        from hadj_no_touch.head_tracking import head_action_for, HEAD_RIGHT, HEAD_UP
        assert head_action_for("media", HEAD_RIGHT) == "NEXT_TRACK"
        assert head_action_for("presentation", HEAD_RIGHT) == "NEXT_SLIDE"
        assert head_action_for("unknown_ctx", HEAD_UP) == "SCROLL"


class TestTestLab:
    def test_software_tests_pass(self) -> None:
        from hadj_no_touch.test_lab import TestLab
        rows = TestLab().run_all()
        failed = [r for r in rows if r.ok is False]
        assert not failed, [f"{r.name}: {r.detail}" for r in failed]


class TestAppIntegration:
    def _core(self):
        from PySide6.QtCore import QCoreApplication
        _ = QCoreApplication.instance() or QCoreApplication([])
        from hadj_no_touch.core.app import AppCore
        return AppCore()

    def test_safety_gate_requests_confirmation_at_all_level(self) -> None:
        core = self._core()
        core.safety.set_confirmation_level("all")
        confirms: list = []
        toasts: list = []
        core.request_confirmation.connect(confirms.append)
        core.toasts.connect(toasts.append)
        from hadj_no_touch.ai.intent_engine import Intent
        core._route_intent(Intent(action="HELP", source="test"))
        assert len(confirms) == 1
        core.confirm_pending()
        assert confirms and any("open chrome" in t for t in toasts)
        assert core.history.recent()[0]["status"] in ("OK", "CONFIRMED")

    def test_demo_mode_simulates_actions(self) -> None:
        core = self._core()
        core.demo.set_enabled(True)
        toasts: list = []
        core.toasts.connect(toasts.append)
        from hadj_no_touch.ai.intent_engine import Intent
        core._route_intent(Intent(action="VOLUME_UP", source="test"))
        assert any("[DEMO]" in t for t in toasts)
        rec = core.history.recent()
        assert rec and rec[0]["simulated"] is True
        core.demo.set_enabled(False)

    def test_demo_exempt_safety_toggles(self) -> None:
        core = self._core()
        core.demo.set_enabled(True)
        from hadj_no_touch.ai.intent_engine import Intent
        core._route_intent(Intent(action="EMERGENCY_STOP", source="test"))
        assert core.privacy.emergency_stopped, "emergency stop must stay real in demo"
        core.demo.set_enabled(False)
        core.resume_from_emergency()

    def test_macro_gesture_trigger_routes(self) -> None:
        core = self._core()
        from hadj_no_touch.macros import Macro
        core.macros.add(Macro("lock", "gesture", "CIRCLE_CW",
                              [{"action": "HELP", "params": {}}]))
        toasts: list = []
        core.toasts.connect(toasts.append)
        from hadj_no_touch.gestures import gesture_engine as ge
        core._dispatch_gesture_event(ge.GestureEvent(kind=ge.CIRCLE_CW))
        assert any("macro 'lock'" in t.lower() for t in toasts)

    def test_custom_command_voice_fallback(self) -> None:
        core = self._core()
        from hadj_no_touch.custom_commands import CustomCommand
        core.custom_commands.add(CustomCommand(phrase="boost it", action="HELP"))
        toasts: list = []
        core.toasts.connect(toasts.append)
        core._voice_fallback("please boost it now", "en")
        assert any("open chrome" in t for t in toasts)

    def test_plan_preview_and_demo_execution(self) -> None:
        core = self._core()
        previews: list = []
        core.plan_preview.connect(previews.append)
        plan = core.plan_request("prepare my presentation")
        assert previews and not plan.is_empty()
        core.demo.set_enabled(True)
        assert core.execute_plan(plan)
        sims = [r for r in core.history.recent(30) if r["simulated"]]
        assert sims
        core.demo.set_enabled(False)

    def test_macro_crud_persistence(self) -> None:
        core = self._core()
        from hadj_no_touch.macros import Macro
        assert core.add_macro(Macro("persisted", "voice", "hey",
                                    [{"action": "HELP"}]).to_dict()) is None
        assert core.macros.get("persisted") is not None
        core._save_macros()
        core.macros.clear()
        core._load_macros()
        assert core.macros.get("persisted") is not None
        assert core.delete_macro("persisted")
        core._save_macros()

    def test_mouse_event_demo_gate(self) -> None:
        core = self._core()
        core.demo.set_enabled(True)
        toasts: list = []
        core.toasts.connect(toasts.append)
        from hadj_no_touch.gestures import gesture_engine as ge
        core._execute_mouse_event(ge.GestureEvent(kind=ge.LEFT_CLICK, x=10, y=20))
        assert any("[DEMO]" in t for t in toasts)
        core.demo.set_enabled(False)

    def test_unknown_action_blocked_by_safety_gate(self) -> None:
        """Register-only execution: an unregistered action can never run."""
        from hadj_no_touch.core.app import OUT_BLOCKED
        core = self._core()
        warns: list = []
        core.event_logged.connect(lambda kind, msg: warns.append(msg)
                                  if kind == "WARN" else None)
        from hadj_no_touch.ai.intent_engine import Intent
        result = core._route_intent(Intent(action="TOTALLY_UNKNOWN_XYZ",
                                           source="test"))
        assert result == OUT_BLOCKED
        assert warns and any("blocked" in w.lower() for w in warns)
        rec = core.history.recent()
        assert rec and rec[0]["status"] == "FAILED"

    def test_custom_gesture_name_goes_through_safety(self) -> None:
        """A custom gesture firing an unregistered action must be blocked,
        not executed via the raw bypass."""
        from hadj_no_touch.gestures.custom_gestures import CustomGesture
        core = self._core()
        warns: list = []
        core.event_logged.connect(lambda kind, msg: warns.append(msg)
                                  if kind == "WARN" else None)
        core._fire_custom_gesture(CustomGesture(
            name="pinky_tap", action="TOTALLY_UNKNOWN_XYZ", action_label=""))
        assert warns and any("blocked" in w.lower() for w in warns)
        rec = core.history.recent()
        assert rec and rec[0]["status"] == "FAILED"

    def test_laser_pointer_toggles_really(self) -> None:
        core = self._core()
        toasts: list = []
        core.toasts.connect(toasts.append)
        from hadj_no_touch.ai.intent_engine import Intent
        core._route_intent(Intent(action="LASER_POINTER", source="test"))
        assert core._laser_mode is True
        core._route_intent(Intent(action="LASER_POINTER", source="test"))
        assert core._laser_mode is False

    def test_hand_present_goes_stale(self) -> None:
        """hand_present must expire once the hand is no longer seen."""
        core = self._core()
        core._last_hand_detected = True
        core._last_hand_detected_at = time.monotonic() - 5.0
        assert core._last_hand_seen() is False
        core._emit_status(snapshot_time=time.monotonic())
        assert core._status.hand_present is False
        core._last_hand_detected_at = time.monotonic()
        core._emit_status(snapshot_time=time.monotonic())
        assert core._status.hand_present is True

    def test_macro_halts_on_confirmation_step(self) -> None:
        """A macro must stop at a step that asks for confirmation instead of
        racing ahead of the prompt (e.g. closing a window, then next slide)."""
        core = self._core()
        core.safety.set_confirmation_level("smart")
        from hadj_no_touch.macros import Macro
        core.macros.add(Macro(name="risky", trigger="button", trigger_value="risky",
                              actions=[{"action": "CLOSE_WINDOW"},
                                       {"action": "NEXT_SLIDE"}]))
        toasts: list = []
        core.toasts.connect(toasts.append)
        ok = core.macros.run_by_name("risky")
        assert ok is False, "macro must halt at the confirmation step"
        assert core._pending_confirm is not None
        assert core._pending_confirm.action == "CLOSE_WINDOW"
        assert not core.history.recent(30) or \
            all(r["action"] != "Next slide" for r in core.history.recent(30))

    def test_macro_continues_through_demo(self) -> None:
        """In demo every non-exempt step is simulated, so the whole sequence
        still runs (that is the point of a demo)."""
        core = self._core()
        core.demo.set_enabled(True)
        from hadj_no_touch.macros import Macro
        core.macros.add(Macro(name="fluo", trigger="button", trigger_value="fluo",
                              actions=[{"action": "NEXT_SLIDE"},
                                       {"action": "OPEN_APP",
                                        "params": {"app": "chrome"}}]))
        assert core.macros.run_by_name("fluo") is True
        toasts: list = []
        core.toasts.connect(toasts.append)
        core.demo.set_enabled(False)
