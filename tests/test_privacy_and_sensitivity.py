"""Tests for privacy coherence + real-session accuracy metrics.

Covers the honesty rules added for roadmap axis 2 (privacy) and axis 1
(measurable reliability): sensitivity profiles apply real settings, click
metrics are real measurements with honest defaults, and a locally-chosen voice
engine never silently falls back to the Google cloud engine.
"""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from hadj_no_touch.config import Settings, VoiceSettings
from hadj_no_touch.gestures import gesture_engine as ge
from hadj_no_touch.gestures.gesture_engine import GestureEngine
from hadj_no_touch.vision.hand_tracking import HandData


# ---- sensitivity profile --------------------------------------------------

class TestSensitivityProfile:
    def test_medium_is_default_and_applies(self) -> None:
        s = Settings()
        assert s.sensitivity == "medium"
        s.apply_sensitivity()
        p = s.SENSITIVITY_SETS["medium"]
        assert s.cursor.smoothing == p["smoothing"]
        assert s.cursor.speed == p["speed"]
        assert s.gestures.pinch_dwell_click_ms == p["pinch_dwell_click_ms"]

    def test_low_and_high_are_real_and_opposite(self) -> None:
        s = Settings()
        s.sensitivity = "low"
        s.apply_sensitivity()
        assert s.cursor.speed < 1.0
        assert s.cursor.smoothing > s.SENSITIVITY_SETS["medium"]["smoothing"]
        assert s.gestures.pinch_dwell_click_ms > 220
        s.sensitivity = "high"
        s.apply_sensitivity()
        assert s.cursor.speed > 1.0
        assert s.cursor.smoothing < s.SENSITIVITY_SETS["medium"]["smoothing"]
        assert s.gestures.pinch_dwell_click_ms < 220

    def test_unknown_level_falls_back_to_medium(self) -> None:
        s = Settings()
        s.sensitivity = "bogus"
        s.apply_sensitivity()
        assert s.sensitivity == "medium"
        assert s.cursor.speed == 1.0

    def test_engine_choice_flag_round_trip(self, tmp_path) -> None:
        cfg = tmp_path / "config.json"
        s = Settings()
        s.voice.engine_choice_made = True
        s.voice.engine = "vosk"
        s.save(cfg)
        s2 = Settings()
        s2.load(cfg)
        assert s2.voice.engine_choice_made is True
        assert s2.voice.engine == "vosk"


# ---- click precision metrics ----------------------------------------------

class TestClickPrecision:
    def test_click_metrics_and_reset(self) -> None:
        from hadj_no_touch.performance import PerformanceMonitor
        p = PerformanceMonitor()
        snap = p.snapshot()
        assert snap["clicks"] == 0
        assert snap["click_drift_avg"] is None
        assert snap["click_precision"] is None

        p.note_click(0.05)   # clean
        p.note_click(0.11)   # clean (<= CLEAN_DRIFT 0.12)
        p.note_click(0.40)   # miss
        snap = p.snapshot()
        assert snap["clicks"] == 3
        assert snap["clicks_clean"] == 2
        assert snap["click_precision"] == pytest.approx(2 / 3, abs=0.001)
        assert snap["click_drift_avg"] == pytest.approx((0.05 + 0.11 + 0.40) / 3, abs=0.001)

        p.reset_counters()
        snap = p.snapshot()
        assert snap["clicks"] == 0
        assert snap["false_triggers"] == 0

    def test_click_drift_is_recorded_and_drained(self) -> None:
        cfg = ge.SETTINGS.gestures
        eng = GestureEngine(cfg)
        eng._norm_scale = 100.0
        eng._pinch_anchor = (100.0, 100.0)
        eng._record_click((140.0, 100.0))
        eng._record_click((130.0, 120.0))
        drifts = eng.drain_click_drifts()
        assert drifts == pytest.approx([0.40, math.hypot(30, 20) / 100.0])
        assert eng.drain_click_drifts() == []

    def test_pinch_click_cycle_wires_drift_into_engine(self) -> None:
        cfg = ge.SETTINGS.gestures
        cfg.pinch_dwell_click_ms = 200
        cfg.pinch_hold_drag_ms = 250
        cfg.gesture_confidence = 0.5
        eng = GestureEngine(cfg)

        hand = _hand({})
        hand.landmarks_norm[4] = hand.landmarks_norm[8].copy()
        for _ in range(8):
            eng.update([hand], (0.5, 0.5), 640, 480)
            time.sleep(0.05)

        kinds: list[str] = []
        rest = _hand({4: "straight"})
        for _ in range(8):
            kinds += [e.kind for e in eng.update([rest], (0.5, 0.5), 640, 480)]
            time.sleep(0.05)
        assert ge.LEFT_CLICK in kinds
        drifts = eng.drain_click_drifts()
        assert len(drifts) == 1
        assert drifts[0] == pytest.approx(0.0, abs=1e-3)


# ---- honest voice engine selection ----------------------------------------

class TestHonestVoiceEngine:
    def test_local_choice_disables_voice_instead_of_google(self, monkeypatch) -> None:
        import hadj_no_touch.voice.speech_recognition as sr
        google_constructed = {"hit": False}

        class BoomGoogle:
            def __init__(self, *a, **k):
                google_constructed["hit"] = True

            def available(self):
                return True

        monkeypatch.setattr(sr, "GoogleSpeechEngine", BoomGoogle)
        sm = sr.SpeechManager(VoiceSettings(engine="vosk"))
        fake = type("FakeUnavailable", (), {"available": lambda self: False})()
        monkeypatch.setattr(sm, "_make_engine", lambda name: fake)

        assert sm.create() is None
        assert sm.engine is None
        assert google_constructed["hit"] is False, "google must never be built"

    def test_google_unavailable_is_reported_as_none(self, monkeypatch) -> None:
        import hadj_no_touch.voice.speech_recognition as sr

        class Fake:
            def __init__(self, *a, **k):
                pass

            def available(self):
                return False

        monkeypatch.setattr(sr, "GoogleSpeechEngine", Fake)
        sm = sr.SpeechManager(VoiceSettings(engine="google"))
        assert sm.create() is None
        assert sm.engine is None

    def test_google_available_is_used(self, monkeypatch) -> None:
        import hadj_no_touch.voice.speech_recognition as sr

        class Fake:
            def __init__(self, *a, **k):
                pass

            def available(self):
                return True

        monkeypatch.setattr(sr, "GoogleSpeechEngine", Fake)
        sm = sr.SpeechManager(VoiceSettings(engine="google"))
        eng = sm.create()
        assert eng is not None
        assert sm.engine is eng


# ---- helpers --------------------------------------------------------------

def _landmarks(fingers: dict) -> np.ndarray:
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


def _hand(fingers: dict, confidence: float = 0.9) -> HandData:
    lm = _landmarks(fingers)
    return HandData(landmarks_norm=lm, landmarks_px=lm * 640,
                    handedness="Right", confidence=confidence, tracked=True)