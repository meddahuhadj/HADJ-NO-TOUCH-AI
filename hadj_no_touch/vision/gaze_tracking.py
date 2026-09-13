"""Optional eye / gaze tracking (experimental).

Estimate a normalized gaze direction from iris positions relative to the
eye corners. Runs on FaceMesh landmarks only (no images leave the device).
"""

from __future__ import annotations

import numpy as np

from ..logging_setup import get_logger
from .face_tracking import (
    FaceData,
    LEFT_EYE_CORNERS,
    RIGHT_EYE_CORNERS,
    LEFT_IRIS,
    RIGHT_IRIS,
)

log = get_logger("vision.gaze")


class GazeTracker:
    """Estimate horizontal/vertical gaze direction in [-1, 1]."""

    def __init__(self, smooth: float = 0.5):
        self.smooth = smooth
        self._gx = 0.0
        self._gy = 0.0
        self.active = False

    def update(self, face: FaceData) -> tuple[float, float]:
        """Return smoothed (gx, gy). Positive gx = looking to the right of image."""
        if not face.present or face.landmarks_norm is None:
            self._gx *= (1 - self.smooth)
            self._gy *= (1 - self.smooth)
            return self._gx, self._gy

        lm = face.landmarks_norm
        try:
            gx_l = self._eye_ratio(lm, LEFT_EYE_CORNERS, LEFT_IRIS)
            gx_r = self._eye_ratio(lm, RIGHT_EYE_CORNERS, RIGHT_IRIS)
            gy_l = self._eye_ratio(lm, LEFT_EYE_CORNERS, LEFT_IRIS, vertical=True)
            gy_r = self._eye_ratio(lm, RIGHT_EYE_CORNERS, RIGHT_IRIS, vertical=True)
            vx = (gx_l + gx_r) / 2.0
            vy = (gy_l + gy_r) / 2.0
            # Normalize to roughly [-1, 1]
            vx = float(np.clip((vx - 0.5) * 4.0, -1, 1))
            vy = float(np.clip((vy - 0.5) * 4.0, -1, 1))
        except Exception:
            vx, vy = self._gx, self._gy

        self._gx = self.smooth * vx + (1 - self.smooth) * self._gx
        self._gy = self.smooth * vy + (1 - self.smooth) * self._gy
        self.active = True
        return self._gx, self._gy

    @staticmethod
    def _eye_ratio(lm, corners, iris, vertical: bool = False) -> float:
        c0 = lm[corners[0]]
        c1 = lm[corners[1]]
        center = (lm[iris[3]] + lm[iris[2]] + lm[iris[1]] + lm[iris[0]]) / 4.0
        if vertical:
            a, b = c0[1], c1[1]
            i = center[1]
        else:
            a, b = c0[0], c1[0]
            i = center[0]
        span = abs(b - a) or 1e-6
        return float((i - min(a, b)) / span)

    def direction(self) -> tuple[float, float]:
        return self._gx, self._gy