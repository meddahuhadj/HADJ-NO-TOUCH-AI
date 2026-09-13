"""Tests for custom gesture features (path descriptor + matcher)."""

from __future__ import annotations

import numpy as np

from hadj_no_touch.gestures.custom_gestures import (
    hand_feature, resample_path, path_distance, CustomGesture,
    CustomGestureRematcher,
)

N = 32


def _circle(n: int = 20) -> list[np.ndarray]:
    t = np.linspace(0, 2 * np.pi, n)
    pts = [np.array([0.5 + 0.15 * np.cos(a), 0.5 + 0.15 * np.sin(a)],
                    dtype=np.float32) for a in t]
    base = _hand_landmarks()
    return [hand_feature(base) + p * 0.0 for p in pts]  # placeholder replaced below


def _hand_landmarks() -> np.ndarray:
    lm = np.zeros((21, 2), dtype=np.float32)
    lm[0] = (0.5, 0.6)
    lm[8] = (0.5, 0.4)
    return lm


def _motion(fn, n: int = 20) -> list[np.ndarray]:
    """A moving index-finger trajectory over a static hand base."""
    base = _hand_landmarks()
    out = []
    for f in fn(n):
        lm = base.copy()
        lm[8] = lm[0] + np.array(f, dtype=np.float32)
        out.append(hand_feature(lm))
    return out


def _horiz(n: int = 20):
    return [(i / n, 0.2) for i in range(n)]


def _vert(n: int = 20):
    return [(0.2, i / n) for i in range(n)]


class TestPathMath:
    def test_resample_constant_length(self) -> None:
        for length in (5, 20, 50):
            path = _motion(_horiz, length)
            r = resample_path(path, N)
            assert r.shape == (N, 42)

    def test_distance_symmetric(self) -> None:
        a = resample_path(_motion(_horiz), N)
        b = resample_path(_motion(_horiz), N)
        assert abs(path_distance(a, b) - path_distance(b, a)) < 1e-6

    def test_same_gesture_closer(self) -> None:
        same_a = resample_path(_motion(_horiz), N)
        same_b = resample_path(_motion(_horiz, 25), N)
        diff = resample_path(_motion(_vert), N)
        d_same = path_distance(same_a, same_b)
        d_diff = path_distance(same_a, diff)
        assert d_same < d_diff

    def test_feature_is_hand_relative(self) -> None:
        lm1 = _hand_landmarks()
        lm2 = _hand_landmarks() + 0.1  # translated hand
        f1, f2 = hand_feature(lm1), hand_feature(lm2)
        assert np.allclose(f1, f2)


class TestCustomGesture:
    def test_match_returns_confidence(self) -> None:
        g = CustomGesture(name="hello", action="launch_app:chrome")
        g.add_sample(_motion(_horiz))
        probe = np.float32(resample_path(_motion(_horiz, 23)))
        d, conf = g.match(probe)
        assert conf >= 0.5
        assert isinstance(d, float)

    def test_no_match_on_foreign_path(self) -> None:
        g = CustomGesture(name="hello", action="")
        g.add_sample(_motion(_horiz))
        _, conf = g.match(np.float32(resample_path(_motion(_vert))))
        assert 0.0 <= conf < 0.999

    def test_to_db_round_trip(self) -> None:
        g = CustomGesture(name="x", action="type_text:ok", action_label="ok")
        g.add_sample(_motion(_horiz))
        row = g.to_db()
        g2 = CustomGesture.from_db(row)
        assert g2.name == "x"
        assert g2.action == "type_text:ok"
        d, c = g2.match(np.float32(resample_path(_motion(_horiz))))
        assert c >= 0.5


class TestRematcher:
    def test_empty_no_match(self) -> None:
        r = CustomGestureRematcher([])
        r.push(hand_feature(_hand_landmarks()))
        g, d, c = r.match()
        assert g is None

    def test_matches_recorded_gesture(self) -> None:
        g = CustomGesture(name="wave", action="screenshot")
        g.add_sample(_motion(_horiz))
        r = CustomGestureRematcher([g])
        for f in _motion(_horiz):
            r.push(f)
        match, _d, conf = r.match()
        assert match is not None
        assert match.name == "wave"
        assert conf >= 0.5