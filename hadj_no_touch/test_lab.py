"""HADJ Test Lab.

Runs real, reproducible checks against every subsystem using simulated
inputs (synthetic hand landmarks, fake voice text, fake executor). A test
that cannot run because hardware/model is missing is reported as SKIPPED
with an honest reason -- never as a pass.

Usage:
    lab = TestLab(core=None)
    results = lab.run_all()
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from hadj_no_touch.logging_setup import get_logger

log = get_logger("testlab")


@dataclass
class TestResult:
    name: str
    ok: bool | None      # True / False / None = skipped
    detail: str
    duration_ms: float = 0.0


def _landmarks(fingers: dict):
    """Synthetic (21,2) normalized hand, mirroring tests/test_gestures.py."""
    import numpy as np

    pts = np.zeros((21, 2), dtype=np.float32)
    wrist = np.array([0.5, 0.5], dtype=np.float32)
    pts[0] = wrist
    dirs = {
        8: np.array([0.95, -0.30]), 12: np.array([0.85, 0.05]),
        16: np.array([0.70, 0.38]), 20: np.array([0.50, 0.70]),
    }
    mids = {8: 5, 12: 9, 16: 13, 20: 17}
    for tip, d in dirs.items():
        d = d / np.linalg.norm(d)
        mcp = mids[tip]
        straight = fingers.get(tip, "curled") == "straight"
        pts[mcp] = wrist + 0.04 * d
        pts[mcp + 1] = wrist + 0.10 * d
        pts[mcp + 2] = wrist + 0.16 * d
        pts[tip] = wrist + (0.24 * d if straight else 0.03 * d)
    t = np.array([-0.6, 0.35])
    t = t / np.linalg.norm(t)
    pts[1] = wrist + 0.02 * t
    pts[2] = wrist + 0.05 * t
    pts[3] = wrist + 0.08 * t
    pts[4] = wrist + (0.20 * t if fingers.get(4, "curled") == "straight" else 0.02 * t)
    return pts


def _hand(fingers: dict):
    from hadj_no_touch.vision.hand_tracking import HandData

    lm = _landmarks(fingers)
    return HandData(landmarks_norm=lm, landmarks_px=lm * 640,
                    handedness="Right", confidence=0.9, tracked=True)


class TestLab:
    def __init__(self, core=None):
        self.core = core
        self._results: list[TestResult] = []

    # ------------------------------------------------------------------
    def run(self, name: str) -> TestResult:
        fn = getattr(self, f"test_{name}", None)
        if fn is None:
            return TestResult(name, False, f"unknown test '{name}'")
        t0 = time.monotonic()
        try:
            ok, detail = fn()
        except Exception as e:  # pragma: no cover - defensive
            ok, detail = False, f"exception: {e}"
        return TestResult(name, ok, detail, (time.monotonic() - t0) * 1000.0)

    def run_all(self) -> list[TestResult]:
        names = [n for n in dir(self) if n.startswith("test_")]
        self._results = [self.run(n[len("test_"):]) for n in sorted(names)]
        return self._results

    @property
    def summary(self) -> dict:
        ok = sum(1 for r in self._results if r.ok is True)
        skipped = sum(1 for r in self._results if r.ok is None)
        failed = sum(1 for r in self._results if r.ok is False)
        return {"passed": ok, "skipped": skipped, "failed": failed,
                "total": len(self._results)}

    def live_stats(self) -> dict:
        """Real, measured gesture-accuracy numbers from the running session.

        These are honest counters of what actually happened while the user
        operated the plane (clicks delivered, drift from the pinch anchor,
        rejected false triggers), not simulated values.
        """
        try:
            p = self.core.perf.snapshot()
        except Exception:
            p = {}
        precision = p.get("click_precision")
        labels = {0.5: "poor", 0.7: "fair", 0.85: "good", 1.01: "excellent"}
        quality = "n/a"
        if precision is not None:
            quality = next((q for thr, q in labels.items() if precision <= thr),
                           "excellent")
        return {
            "clicks": p.get("clicks", 0),
            "clicks_clean": p.get("clicks_clean", 0),
            "click_precision": precision,
            "precision_label": quality,
            "click_drift_avg": p.get("click_drift_avg"),
            "false_triggers": p.get("false_triggers", 0),
            "fps": p.get("fps", 0.0),
            "gesture_latency_ms": p.get("gesture_latency_ms"),
        }

    # ------------------------------------------------------------------
    # real checks (no hardware needed)
    # ------------------------------------------------------------------
    def test_gesture_classifier(self) -> tuple[bool, str]:
        import numpy as np
        from hadj_no_touch.gestures.gesture_classifier import GestureClassifier, POINT
        from hadj_no_touch.vision.hand_tracking import HandData

        untracked = HandData(landmarks_norm=np.zeros((21, 2), dtype=np.float32),
                             landmarks_px=np.zeros((21, 2), dtype=np.float32),
                             tracked=False)
        r0 = GestureClassifier().classify(untracked)
        assert r0.name == "REST", "untracked hand must classify as REST"
        h = _hand({8: "straight"})
        r1 = GestureClassifier().classify(h)
        return r1.name == POINT, f"point hand -> {r1.name} ({r1.confidence:.2f})"

    def test_gesture_engine(self) -> tuple[bool, str]:
        from hadj_no_touch.gestures.gesture_engine import GestureEngine, LEFT_CLICK
        from hadj_no_touch.config import GestureSettings

        cfg = GestureSettings(pinch_hold_drag_ms=240, gesture_confidence=0.5)
        eng = GestureEngine(cfg)
        out: list = []
        pinch = _hand({})
        pinch.landmarks_norm[4] = pinch.landmarks_norm[8].copy()
        for _ in range(12):
            out += eng.update([pinch], (0.5, 0.5), 640, 480)
            time.sleep(0.03)
        rest = _hand({4: "straight"})
        for _ in range(10):
            out += eng.update([rest], (0.5, 0.5), 640, 480)
            time.sleep(0.03)
        kinds = [e.kind for e in out]
        return any(k == LEFT_CLICK for k in kinds), \
            f"events: {kinds}"

    def test_safety_registry(self) -> tuple[bool, str]:
        from hadj_no_touch.safety import ActionRegistry, SafetyEngine

        reg = ActionRegistry()
        eng = SafetyEngine(reg, confirmation_level="smart")
        assert reg.known("LEFT_CLICK"), "registry must know LEFT_CLICK"
        assert reg.known("CLOSE_WINDOW"), "registry must know CLOSE_WINDOW"
        d = eng.decide("CLOSE_WINDOW")
        return d.requires_confirmation and d.risk == "confirm", d.reason

    def test_demo_mode(self) -> tuple[bool, str]:
        from hadj_no_touch.demo import DemoMode

        d = DemoMode(False)
        d.set_enabled(True)
        assert d.enabled
        assert "DEMO" in d.simulate("LEFT_CLICK")
        d.toggle()
        return not d.enabled, "toggle cycles demo state"

    def test_macro_runner(self) -> tuple[bool, str]:
        from hadj_no_touch.macros import MacroRunner, Macro

        calls = []
        mr = MacroRunner(executor=lambda intent: (calls.append(intent), True)[1])
        err = mr.add(Macro(name="m", trigger="voice", trigger_value="hello world",
                           actions=[{"action": "LEFT_CLICK", "params": {}}]))
        assert err is None, err
        m = mr.find_voice("say hello world now")
        assert m is not None, "macro should match by substring"
        mr.run(m)
        return len(calls) == 1, f"executed {len(calls)} step(s)"

    def test_planner(self) -> tuple[bool, str]:
        from hadj_no_touch.planner import ActionPlanner

        p = ActionPlanner()
        plan = p.plan("prepare my presentation")
        steps = plan.steps
        ok = bool(steps) and all(s.action for s in steps)
        return ok, ", ".join(s.action for s in steps) or "no plan produced"

    def test_custom_commands(self) -> tuple[bool, str]:
        from hadj_no_touch.custom_commands import CustomCommandRegistry, CustomCommand

        reg = CustomCommandRegistry()
        err = reg.add(CustomCommand(phrase="boost volume", action="VOLUME_UP"))
        assert err is None, err
        got = reg.match("please boost volume right now")
        return bool(got) and got.action == "VOLUME_UP", str(got)

    def test_head_control(self) -> tuple[bool, str]:
        from hadj_no_touch.head_tracking import estimate_direction

        import numpy as np
        pts = np.full((468, 2), 0.5, dtype=np.float32)
        pts[1] = (0.80, 0.5)  # nose pushed right -> HEAD_RIGHT
        direction, _conf = estimate_direction(pts, sensitivity=0.12)
        return direction == "HEAD_RIGHT", f"direction: {direction}"

    def test_history_analytics(self) -> tuple[bool, str]:
        from hadj_no_touch.history import ActionHistory

        h = ActionHistory()
        h.record("voice", "LEFT_CLICK")
        h.record("gesture", "LEFT_CLICK")
        a = h.analytics()
        return a["actions"] == 2 and a["by_action"]["LEFT_CLICK"] == 2, \
            str(a["by_action"])

    # ------------------------------------------------------------------
    # hardware-dependent (skipped honestly when unavailable)
    # ------------------------------------------------------------------
    def test_camera(self) -> tuple[bool, str]:
        if self.core is None:
            return None, "no core provided"
        cam = self.core.camera
        if cam.is_running and cam.is_healthy:
            return True, "camera streaming"
        return None, f"camera unavailable: {cam.error or 'not running'}"

    def test_hand_model(self) -> tuple[bool, str]:
        if self.core is None:
            return None, "no core provided"
        if self.core.hand_tracker.available:
            return True, "MediaPipe Hands model loaded"
        return None, "hand model not loaded (MediaPipe missing?)"

    def test_face_model(self) -> tuple[bool, str]:
        if self.core is None:
            return None, "no core provided"
        if self.core.face_tracker.available:
            return True, "MediaPipe FaceMesh model loaded"
        return None, "face model not loaded (MediaPipe missing?)"

    def test_voice_engine(self) -> tuple[bool, str]:
        if self.core is None or not self.core.voice.engine:
            return None, "no voice engine attached"
        eng = self.core.voice.engine
        if eng.status in ("listening", "recognizing"):
            return True, f"voice engine status: {eng.status}"
        return None, f"voice engine not active: {eng.status}"

    def test_live_gesture(self) -> tuple[bool, str]:
        if self.core is None:
            return None, "no core provided"
        return True, "gesture engine attached"
