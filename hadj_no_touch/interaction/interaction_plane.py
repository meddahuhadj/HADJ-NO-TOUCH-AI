"""Virtual interaction plane.

Wraps the calibration homography (or a fallback mapping) plus safety
constraints: dead zones, jump rejection and smoothing. This is the module
that answers "where does the fingertip map on the real screen?"
"""

from __future__ import annotations

from ..config import SETTINGS
from ..logging_setup import get_logger
from .calibration import CalibrationManager

log = get_logger("interaction.plane")


class InteractionPlane:
    def __init__(self, calibration: CalibrationManager | None = None,
                 cursor_settings=SETTINGS.cursor):
        self.calibration = calibration or CalibrationManager()
        self.cursor_settings = cursor_settings
        self.screen_w = 1920
        self.screen_h = 1080
        self._cur: tuple[float, float] | None = None
        self._last_target: tuple[float, float] | None = None
        # Number of consecutive frames a far-away target must persist before it
        # is accepted as a genuine repositioning (not a one-frame tracking glitch).
        self._jump_confirm_frames = 3
        self._jump_rejects = 0

    def set_screen_size(self, w: int, h: int) -> None:
        self.screen_w = max(1, w)
        self.screen_h = max(1, h)

    # ------------------------------------------------------------------
    def map_raw(self, norm: tuple[float, float]) -> tuple[float, float]:
        """Map camera-normalized fingertip to screen-normalized coords."""
        if self.calibration.calibrated and self.calibration.homography is not None:
            m = self.calibration.map(norm)
            if m is not None:
                return m
        return self._fallback_map(norm)

    def _fallback_map(self, norm: tuple[float, float]) -> tuple[float, float]:
        margin = 0.03
        x = 1.0 - norm[0]
        y = norm[1]
        x = margin + x * (1.0 - 2 * margin)
        y = margin + y * (1.0 - 2 * margin)
        return (float(np_clip(x)), float(np_clip(y)))

    # ------------------------------------------------------------------
    def to_pixels(self, norm: tuple[float, float]) -> tuple[float, float]:
        return (norm[0] * self.screen_w, norm[1] * self.screen_h)

    def process(self, norm: tuple[float, float]) -> tuple[float, float] | None:
        """Full pipeline: map -> dead zone -> jump rejection -> smoothing.

        Returns screen pixel coordinates (or None when rejected).
        """
        try:
            target_norm = self.map_raw(norm)
        except Exception:
            return None
        target_px = self.to_pixels(target_norm)

        cs = self.cursor_settings
        # Large jumps = tracking glitch. Use a true Manhattan distance
        # (abs(dx) + abs(dy), NOT abs(dx + dy), which lets opposite-sign
        # diagonal jumps cancel out). A far target must persist for several
        # consecutive frames before it is accepted as a genuine repositioning.
        if self._cur is not None:
            dx = target_px[0] - self._cur[0]
            dy = target_px[1] - self._cur[1]
            delta = abs(dx) + abs(dy)
            max_jump = (self.screen_w + self.screen_h) / 2 * SETTINGS.gestures.max_cursor_jump_ratio
            if delta > max_jump:
                self._jump_rejects += 1
                if self._jump_rejects < self._jump_confirm_frames:
                    self._last_target = None
                    return None
                # Persisted far target: it is a deliberate hand repositioning.
                self._jump_rejects = 0
            else:
                self._jump_rejects = 0

        # dead zone: ignore sub-pixel tremor
        if self._cur is not None and self._last_target is not None:
            dz = cs.dead_zone * (self.screen_w + self.screen_h) / 2
            mv = abs(target_px[0] - self._last_target[0]) + abs(target_px[1] - self._last_target[1])
            if mv < dz:
                return self._cur

        alpha = cs.smoothing
        if self._cur is None:
            self._cur = target_px
        else:
            # align deliberately; alpha ~= smoothing weight on target
            ax = alpha * cs.speed if cs.smoothing < 1 else 1.0
            nx = self._cur[0] + (target_px[0] - self._cur[0]) * ax
            ny = self._cur[1] + (target_px[1] - self._cur[1]) * ax
            self._cur = (nx, ny)
        self._last_target = target_px
        return (float(self._cur[0]), float(self._cur[1]))

    def reset(self) -> None:
        self._cur = None
        self._last_target = None
        self._jump_rejects = 0


def np_clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))