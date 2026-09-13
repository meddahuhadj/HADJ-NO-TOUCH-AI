"""Calibration wizard state machine.

Maps webcam fingertip coordinates to the real Windows screen using a
perspective transform (homography). A standard webcam provides estimated
spatial information only -- this is a virtual/contactless interaction plane,
not a physical touch surface.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from ..logging_setup import get_logger

log = get_logger("interaction.calibration")

try:
    import cv2
    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False


# Screen anchor points as fractions of screen (slightly inset).
SCREEN_ANCHORS = [
    (0.03, 0.05),
    (0.97, 0.05),
    (0.97, 0.95),
    (0.03, 0.95),
]

CALIBRATION_SAMPLE_MS = 600
CALIBRATION_CONFIRM_DWELL_MS = 450


@dataclass
class CalibrationManager:
    """Collect 4 corner points (+ optional center verification)."""

    stage: int = 0  # 0..3 corners, 4 = center verify, 5 = done
    points_camera: list = field(default_factory=list)  # normalized camera pts
    point_samples: list = field(default_factory=list)
    sample_start: float = 0.0
    homography: np.ndarray | None = None
    calibrated: bool = False
    last_screen_pos: tuple[float, float] = (0, 0)

    @property
    def screen_anchor(self) -> tuple[float, float]:
        """Which on-screen corner/point the user should currently aim at."""
        if self.stage < len(SCREEN_ANCHORS):
            return SCREEN_ANCHORS[self.stage]
        return (0.5, 0.5)

    @property
    def total_stages(self) -> int:
        return 5  # 4 corners + center verification

    @property
    def done(self) -> bool:
        return self.stage >= 5

    def reset(self) -> None:
        self.stage = 0
        self.points_camera.clear()
        self.point_samples.clear()
        self.homography = None
        self.calibrated = False

    def start_point(self, now: float | None = None) -> None:
        self.point_samples.clear()
        self.sample_start = now or time.monotonic()

    def collect(self, fingertip_norm: tuple[float, float], pinch: bool,
                now: float | None = None) -> bool:
        """Feed live fingertip position (+ pinch state).

        Returns True when the current point has been accepted and the stage
        advanced. Used by the main loop while the calibration is running.
        """
        if self.done or fingertip_norm is None:
            return False
        now = now or time.monotonic()
        if not pinch:
            # released before completing the dwell: restart on next attempt
            self.point_samples.clear()
            return False
        if not self.point_samples:
            self.start_point(now)
        self.point_samples.append(fingertip_norm)
        if now - self.sample_start >= (CALIBRATION_CONFIRM_DWELL_MS / 1000.0):
            mean = np.mean(self.point_samples[-12:], axis=0)
            self.points_camera.append((float(mean[0]), float(mean[1])))
            self.stage += 1
            self.point_samples.clear()
            self._try_build(silent=True)
            return True
        return False

    def confirm_point(self, fingertip_norm: tuple[float, float]) -> None:
        """Explicitly accept a point (used from UI buttons as well)."""
        if self.done or fingertip_norm is None:
            return
        self.points_camera.append((float(fingertip_norm[0]), float(fingertip_norm[1])))
        self.stage += 1
        self.point_samples.clear()
        self._try_build(silent=True)

    def _try_build(self, silent: bool = False) -> None:
        if len(self.points_camera) >= 4 and self.homography is None:
            h = self._compute(self.points_camera[:4])
            if h is not None:
                self.homography = h
                self.calibrated = True
                if not silent:
                    log.info("Calibration homography computed")
            else:
                self.homography = None

    def _compute(self, src_pts) -> np.ndarray | None:
        if not HAVE_CV2:
            return None
        if len(src_pts) < 4:
            return None
        src = np.float32(src_pts[:4]).reshape(-1, 1, 2)
        dst = np.float32(SCREEN_ANCHORS).reshape(-1, 1, 2)
        try:
            h, _ = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
            if h is None:
                h = cv2.getPerspectiveTransform(src, dst)
            return h
        except Exception as e:
            log.warning("homography failed: %s", e)
            return None

    def map(self, norm: tuple[float, float]) -> tuple[float, float] | None:
        """Map a normalized camera coordinate to normalized screen coords."""
        if self.homography is None:
            return None
        try:
            p = np.float32([[norm[0], norm[1]]]).reshape(-1, 1, 2)
            out = cv2.perspectiveTransform(p, self.homography)
            x, y = float(out[0][0][0]), float(out[0][0][1])
        except Exception:
            return None
        self.last_screen_pos = (x, y)
        return (x, y)

    def verify_center_error(self, cam_center: tuple[float, float]) -> float:
        """Estimate mapping error in normalized screen units toward (0.5,0.5)."""
        m = self.map(cam_center)
        if not m:
            return float("inf")
        return float(np.hypot(m[0] - 0.5, m[1] - 0.5))