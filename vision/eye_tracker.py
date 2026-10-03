"""
HADJ NO-TOUCH AI — Lightweight Eye Tracker (MediaPipe Face Mesh)
Module Specification & Implementation Stub for gaze-guided cursor control.
"""

import time
from typing import Tuple, Optional


class EyeTracker:
    """
    Lightweight gaze tracking using MediaPipe Face Mesh iris landmarks (468-473).
    Gaze controls cursor positioning while hand pinch gesture triggers mouse click.
    """

    def __init__(self, alpha: float = 0.15):
        self.alpha = alpha  # EMA smoothing factor
        self.prev_x: Optional[float] = None
        self.prev_y: Optional[float] = None
        self.enabled: bool = False

    def enable(self, state: bool = True):
        self.enabled = state
        self.prev_x = None
        self.prev_y = None

    def process_face_mesh(self, landmarks, screen_w: int = 1920, screen_h: int = 1080) -> Optional[Tuple[int, int]]:
        """
        Calculates screen gaze coordinates from iris landmarks.
        Applies Exponential Moving Average (EMA) filtering.
        """
        if not self.enabled or not landmarks:
            return None

        # Landmarks 468 (left iris center) and 473 (right iris center)
        try:
            iris_l = landmarks[468]
            iris_r = landmarks[473]

            raw_x = (iris_l.x + iris_r.x) / 2.0 * screen_w
            raw_y = (iris_l.y + iris_r.y) / 2.0 * screen_h

            if self.prev_x is None or self.prev_y is None:
                smooth_x, smooth_y = raw_x, raw_y
            else:
                smooth_x = self.alpha * raw_x + (1 - self.alpha) * self.prev_x
                smooth_y = self.alpha * raw_y + (1 - self.alpha) * self.prev_y

            self.prev_x, self.prev_y = smooth_x, smooth_y
            return int(smooth_x), int(smooth_y)
        except Exception:
            return None
