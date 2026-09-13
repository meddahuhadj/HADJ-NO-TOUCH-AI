"""Tests for gesture classification and the gesture engine."""

from __future__ import annotations

import time

import numpy as np

from hadj_no_touch.vision.hand_tracking import HandData
from hadj_no_touch.gestures.gesture_classifier import (
    GestureClassifier, POINT, PINCH, OPEN_PALM, FIST, TWO_FINGER,
)
from hadj_no_touch.gestures import gesture_engine as ge


def _landmarks(fingers: dict) -> np.ndarray:
    """Build a (21,2) normalized landmark array.

    ``fingers`` maps the medial 5 indices to 'straight' or 'curled':
    index=8, middle=12, ring=16, pinky=20, thumb=4.
    """
    pts = np.zeros((21, 2), dtype=np.float32)
    wrist = np.array([0.5, 0.5], dtype=np.float32)
    pts[0] = wrist
    # fan-out directions so fingers do not overlap
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
    # thumb: curled toward palm by default
    t = np.array([-0.6, 0.35])
    t = t / np.linalg.norm(t)
    pts[1] = wrist + 0.02 * t
    pts[2] = wrist + 0.05 * t
    pts[3] = wrist + 0.08 * t
    if fingers.get(4, "curled") == "straight":
        pts[4] = wrist + 0.20 * t
    else:
        pts[4] = wrist + 0.02 * t
    return pts


def _hand(fingers: dict, confidence: float = 0.9) -> HandData:
    return HandData(landmarks_norm=_landmarks(fingers),
                    landmarks_px=_landmarks(fingers) * 640,
                    handedness="Right", confidence=confidence, tracked=True)


class TestClassifier:
    def test_open_palm(self) -> None:
        h = _hand({4: "straight", 8: "straight", 12: "straight",
                   16: "straight", 20: "straight"})
        r = GestureClassifier().classify(h)
        assert r.name == OPEN_PALM
        assert r.recognized

    def test_point(self) -> None:
        h = _hand({8: "straight"})
        r = GestureClassifier().classify(h)
        assert r.name == POINT

    def test_two_finger(self) -> None:
        h = _hand({8: "straight", 12: "straight"})
        r = GestureClassifier().classify(h)
        assert r.name == TWO_FINGER

    def test_fist(self) -> None:
        h = _hand({})
        r = GestureClassifier().classify(h)
        assert r.name == FIST

    def test_pinch(self) -> None:
        lm = _landmarks({8: "straight"})
        # thumb tip pulled onto index tip = perfect pinch
        lm[4] = lm[8].copy()
        h = HandData(landmarks_norm=lm, landmarks_px=lm * 640,
                     handedness="Right", confidence=0.9, tracked=True)
        r = GestureClassifier().classify(h)
        assert r.name == PINCH
        assert r.confidence >= 0.9


class TestGestureEngine:
    def _engine(self):
        cfg = ge.SETTINGS.gestures
        cfg.pinch_dwell_click_ms = 200
        cfg.gesture_confidence = 0.5
        return ge.GestureEngine(cfg)

    def test_pinch_release_fires_left_click(self) -> None:
        eng = self._engine()
        pinch_hand = _hand({})
        pinch_hand.landmarks_norm[4] = pinch_hand.landmarks_norm[8].copy()
        pinch_hand.landmarks_norm[4] = pinch_hand.landmarks_norm[8].copy()

        evs = eng.update([pinch_hand], (0.5, 0.5), 640, 480)
        assert eng.raw_gesture == PINCH

        time.sleep(0.25)
        rest_hand = _hand({4: "straight"})
        release_evs = eng.update([rest_hand], (0.5, 0.5), 640, 480)
        kinds = [e.kind for e in release_evs]
        assert ge.LEFT_CLICK in kinds, kinds

    def test_pointer_move_requires_allowable_pose(self) -> None:
        eng = self._engine()
        point_hand = _hand({8: "straight"})
        evs = eng.update([point_hand], (0.3, 0.4), 640, 480)
        assert any(e.kind == ge.MOVE for e in evs)

    def test_cooldown_blocks_double(self) -> None:
        eng = self._engine()
        pinch_hand = _hand({})
        pinch_hand.landmarks_norm[4] = pinch_hand.landmarks_norm[8].copy()
        clicks = 0
        for _ in range(20):
            eng.update([pinch_hand], (0.5, 0.5), 640, 480)
            time.sleep(0.02)
            # release then pinch repeatedly
            evs = eng.update([_hand({})], (0.5, 0.5), 640, 480)
            clicks += sum(1 for e in evs
                          if e.kind in (ge.LEFT_CLICK, ge.DOUBLE_CLICK))
            time.sleep(0.02)
        # click events are rate-limited by the 300ms cooldown:
        # in ~0.8s we can never exceed a handful of real clicks
        assert clicks <= 6, clicks