"""
Adaptive signal filtering for hand landmarks and virtual cursor.

Implements the 1 € Filter (One-Euro Filter):
Casiez, G., Roussel, N. and Vogel, D. (2012)
"1 € filter: a simple speed-based low-pass filter for noisy input in interactive systems"
Proceedings of ACM CHI 2012.

At low speeds, cutoff frequency is low (fc_min), eliminating jitter while the hand is steady.
At high speeds, cutoff frequency scales up with velocity (beta * speed), eliminating latency and lag.
"""

from __future__ import annotations

import math
import time
from typing import List, Optional, Tuple


class LowPassFilter:
    """First-order low-pass filter."""

    def __init__(self, alpha: float = 0.5):
        self.alpha = alpha
        self.s: Optional[float] = None

    def filter(self, value: float, alpha: Optional[float] = None) -> float:
        if alpha is not None:
            self.alpha = alpha
        if self.s is None:
            self.s = value
        else:
            self.s = self.alpha * value + (1.0 - self.alpha) * self.s
        return self.s

    def reset(self) -> None:
        self.s = None


class OneEuroFilter:
    """
    1 € Filter for 1D signal.

    Parameters:
    - min_cutoff (fc_min): Minimum cutoff frequency in Hz. Lower values reduce jitter at rest.
    - beta: Speed coefficient. Higher values reduce lag during fast movements.
    - d_cutoff: Cutoff frequency for derivative (velocity) filter in Hz.
    """

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007, d_cutoff: float = 1.0):
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)

        self.x_filter = LowPassFilter()
        self.dx_filter = LowPassFilter()
        self.last_time: Optional[float] = None

    def _alpha(self, rate: float, cutoff: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te = 1.0 / rate
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float, timestamp: Optional[float] = None) -> float:
        t = timestamp if timestamp is not None else time.time()

        if self.last_time is None:
            self.last_time = t
            return self.x_filter.filter(x, 1.0)

        dt = t - self.last_time
        self.last_time = t
        if dt <= 0.0:
            dt = 1e-4

        rate = 1.0 / dt

        # Estimate velocity
        prev_x = self.x_filter.s if self.x_filter.s is not None else x
        dx = (x - prev_x) * rate
        edx = self.dx_filter.filter(dx, self._alpha(rate, self.d_cutoff))

        # Dynamic cutoff frequency based on velocity
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self.x_filter.filter(x, self._alpha(rate, cutoff))

    def reset(self) -> None:
        self.x_filter.reset()
        self.dx_filter.reset()
        self.last_time = None


class PointFilter2D:
    """Applies OneEuroFilter independently to 2D coordinates (x, y)."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007, d_cutoff: float = 1.0):
        self.fx = OneEuroFilter(min_cutoff, beta, d_cutoff)
        self.fy = OneEuroFilter(min_cutoff, beta, d_cutoff)

    def filter(self, x: float, y: float, timestamp: Optional[float] = None) -> Tuple[float, float]:
        t = timestamp if timestamp is not None else time.time()
        return self.fx.filter(x, t), self.fy.filter(y, t)

    def reset(self) -> None:
        self.fx.reset()
        self.fy.reset()


class HandLandmarksSmoother:
    """
    Smooths all 21 hand landmarks using bank of 2D/3D OneEuroFilters.
    Prevents skeleton and pointer jitter while maintaining immediate responsiveness.
    """

    def __init__(self, min_cutoff: float = 1.2, beta: float = 0.008):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.filters: List[PointFilter2D] = [
            PointFilter2D(min_cutoff=self.min_cutoff, beta=self.beta) for _ in range(21)
        ]

    def update_parameters(self, min_cutoff: float, beta: float) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        for f in self.filters:
            f.fx.min_cutoff = min_cutoff
            f.fx.beta = beta
            f.fy.min_cutoff = min_cutoff
            f.fy.beta = beta

    def smooth(
        self, points_norm: List[Tuple[float, float, float]], timestamp: Optional[float] = None
    ) -> List[Tuple[float, float, float]]:
        """
        Smooths normalized (x, y, z) landmarks and returns smoothed tuples.
        """
        t = timestamp if timestamp is not None else time.time()
        smoothed = []
        for i, pt in enumerate(points_norm):
            if i < len(self.filters):
                sx, sy = self.filters[i].filter(pt[0], pt[1], t)
                smoothed.append((sx, sy, pt[2]))
            else:
                smoothed.append(pt)
        return smoothed

    def reset(self) -> None:
        for f in self.filters:
            f.reset()
