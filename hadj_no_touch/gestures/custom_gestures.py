"""Custom / user-taught gestures ("TEACH MY GESTURE").

A no-histograms feature descriptor: the normalized landmark trajectory of a
movement, compared with Dynamic-Time-Warping-like fixed-length distance.
Templates are stored in the local database; nothing is uploaded.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field

import numpy as np

from ..logging_setup import get_logger

log = get_logger("gestures.custom")

TEMPLATE_LEN = 24
MATCH_THRESHOLD = 6.5


def hand_feature(landmarks_norm: np.ndarray) -> np.ndarray:
    """Relative landmark positions: wrist-centered, scale-normalized."""
    wrist = landmarks_norm[0]
    scale = np.linalg.norm(landmarks_norm[9] - wrist) + 1e-4
    rel = (landmarks_norm - wrist) / scale
    return rel.reshape(-1)


def resample_path(path: list[np.ndarray], n: int = TEMPLATE_LEN) -> np.ndarray:
    """Uniformly resample a variable-length motion path to n steps."""
    if not path:
        raise ValueError("empty path")
    steps = len(path)
    if steps == 1:
        return np.repeat(path[0].reshape(1, -1), n, axis=0)
    idx = np.linspace(0, steps - 1, n)
    stacked = np.stack(path, axis=0)
    out = np.empty((n, stacked.shape[1]), dtype=np.float32)
    for i, ix in enumerate(idx):
        i0 = int(np.floor(ix))
        i1 = min(i0 + 1, steps - 1)
        frac = ix - i0
        out[i] = stacked[i0] * (1 - frac) + stacked[i1] * frac
    return out


def path_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Fixed-length normalized L2 distance between two motion paths."""
    if a.shape != b.shape:
        return float("inf")
    return float(np.sqrt(np.mean((a - b) ** 2)))


@dataclass
class CustomGesture:
    name: str
    action: str = ""
    action_label: str = ""
    templates: list[np.ndarray] = field(default_factory=list)

    def match(self, probe: np.ndarray) -> tuple[float, float]:
        if not self.templates or probe is None:
            return float("inf"), 0.0
        dists = [path_distance(probe, t) for t in self.templates]
        d = min(dists)
        conf = float(np.clip(1.0 - d / MATCH_THRESHOLD, 0.0, 1.0))
        return d, conf

    def add_sample(self, path: list[np.ndarray]) -> None:
        self.templates.append(resample_path(path))

    def to_db(self):
        return {
            "name": self.name,
            "action": self.action,
            "action_label": self.action_label,
            "templates": [pickle.dumps(t) for t in self.templates],
        }

    @staticmethod
    def from_db(row) -> "CustomGesture":
        g = CustomGesture(name=row["name"], action=row.get("action", ""),
                          action_label=row.get("action_label", ""))
        for blob in row.get("templates", []):
            g.templates.append(pickle.loads(blob))
        return g


class CustomGestureRematcher:
    """Matches a sliding window of features against taught gestures."""

    def __init__(self, gestures: list[CustomGesture]):
        self.gestures = gestures
        self._buffer: list[np.ndarray] = []

    def push(self, feature: np.ndarray) -> None:
        if len(self._buffer) >= TEMPLATE_LEN * 2:
            self._buffer.pop(0)
        self._buffer.append(feature)

    def clear(self) -> None:
        self._buffer.clear()

    def match(self) -> tuple[CustomGesture | None, float, float]:
        if len(self._buffer) < 8 or not self.gestures:
            return None, 0.0, 0.0
        probe = resample_path(self._buffer)
        best_g, best_d, best_c = None, float("inf"), 0.0
        for g in self.gestures:
            d, c = g.match(probe)
            if d < best_d:
                best_d, best_c, best_g = d, c, g
        if best_g is not None and best_c >= 0.55:
            return best_g, best_d, best_c
        return None, best_d, best_c