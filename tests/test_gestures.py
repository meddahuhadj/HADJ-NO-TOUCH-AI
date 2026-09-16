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


def _hand(fingers: dict, confidence: float = 0.9,
          dx: float = 0.0, dy: float = 0.0) -> HandData:
    lm = _landmarks(fingers)
    if dx or dy:
        lm = lm.copy()
        lm[:, 0] = np.clip(lm[:, 0] + dx, 0.0, 1.0)
        lm[:, 1] = np.clip(lm[:, 1] + dy, 0.0, 1.0)
    return HandData(landmarks_norm=lm,
                    landmarks_px=lm * 640,
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
        cfg.pinch_hold_drag_ms = 250
        cfg.gesture_confidence = 0.5
        cfg.swipe_distance = 0.08
        return ge.GestureEngine(cfg)

    def test_pinch_release_fires_left_click(self) -> None:
        eng = self._engine()
        pinch_hand = _hand({})
        pinch_hand.landmarks_norm[4] = pinch_hand.landmarks_norm[8].copy()

        # hold a stable pinch for several frames so it becomes confirmed
        for _ in range(8):
            eng.update([pinch_hand], (0.5, 0.5), 640, 480)
            time.sleep(0.05)
        assert eng.raw_gesture == PINCH

        # release: the confirmed gesture must leave PINCH before the release
        # is interpreted as a click (real multi-frame release)
        rest_hand = _hand({4: "straight"})
        all_kinds: list[str] = []
        for _ in range(8):
            all_kinds += [e.kind for e in eng.update([rest_hand], (0.5, 0.5), 640, 480)]
            time.sleep(0.05)
        assert ge.LEFT_CLICK in all_kinds, all_kinds

    def test_held_drifted_pinch_starts_and_stops_drag(self) -> None:
        eng = self._engine()
        pinch_hand = _hand({})
        pinch_hand.landmarks_norm[4] = pinch_hand.landmarks_norm[8].copy()

        # stable pinch held in place, pointer near the anchor
        for _ in range(8):
            eng.update([pinch_hand], (100.0, 100.0), 1920, 1080)
            time.sleep(0.05)

        assert eng._pinch_active, "pinch should be active before drag"
        # drift far enough while still pinching → DRAG_START fires
        ds_evs = eng.update([pinch_hand], (500.0, 500.0), 1920, 1080)
        assert any(e.kind == ge.DRAG_START for e in ds_evs), ds_evs
        assert eng._drag_on, "drag should be active after DRAG_START"

        # continued movement while dragging → DRAG_UPDATE
        upd_evs = eng.update([pinch_hand], (700.0, 520.0), 1920, 1080)
        assert any(e.kind == ge.DRAG_UPDATE for e in upd_evs), upd_evs

        # releasing the pinch finishes the drag (no stray click)
        rest_hand = _hand({4: "straight"})
        end_kinds: list[str] = []
        for _ in range(8):
            end_kinds += [e.kind for e in eng.update([rest_hand], (700.0, 520.0), 1920, 1080)]
            time.sleep(0.05)
        assert ge.DRAG_END in end_kinds, end_kinds
        assert ge.LEFT_CLICK not in end_kinds, end_kinds

    def test_click_requires_stable_pinch(self) -> None:
        """A single noisy pinch frame must NOT produce a click."""
        eng = self._engine()
        pinch_hand = _hand({})
        pinch_hand.landmarks_norm[4] = pinch_hand.landmarks_norm[8].copy()

        eng.update([pinch_hand], (0.5, 0.5), 640, 480)   # single glitch frame
        time.sleep(0.02)
        release_evs = eng.update([_hand({4: "straight"})], (0.5, 0.5), 640, 480)
        kinds = [e.kind for e in release_evs]
        assert ge.LEFT_CLICK not in kinds, kinds

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

    def test_no_swipe_without_pointer_pose(self) -> None:
        """Fast lateral hand movement while a FIST is confirmed must never
        count as a swipe -- only POINT/TWO_FINGER motion may."""
        eng = self._engine()
        fist_hand = _hand({})  # FIST (all fingers curled)
        for _ in range(10):
            eng.update([fist_hand], (0.1, 0.1), 640, 480)
            evs = eng.update([fist_hand], (0.9, 0.1), 640, 480)
            assert not any(e.kind in (ge.SWIPE_LEFT, ge.SWIPE_RIGHT,
                                      ge.SWIPE_UP, ge.SWIPE_DOWN) for e in evs)

    def test_swipe_from_point_pose(self) -> None:
        """Fast horizontal movement while POINT is confirmed fires a swipe."""
        eng = self._engine()
        all_evs: list[str] = []
        # Move the hand laterally across the frame at POINT confidence for the
        # whole window (motion samples are tagged with the confirmed pose).
        for i in range(10):
            evs = eng.update([_hand({8: "straight"}, dx=0.05 * i, dy=0.0)],
                             (0.1, 0.5), 640, 480)
            all_evs += [e.kind for e in evs]
            time.sleep(0.03)
        assert ge.SWIPE_RIGHT in all_evs, all_evs

    def test_raw_gesture_cleared_on_no_hands(self) -> None:
        """An empty frame must reset stale gesture state (no phantom gestures)."""
        eng = self._engine()
        eng.update([_hand({8: "straight"})], (0.5, 0.5), 640, 480)
        assert eng.raw_gesture == POINT
        eng.update([], None, 640, 480)
        assert eng.raw_gesture == ""
        assert eng.raw_confidence == 0.0
        assert eng.confirmed_gesture == ge.REST