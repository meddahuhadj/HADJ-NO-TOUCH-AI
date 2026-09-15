"""Face landmark tracking (used for the optional gaze feature)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

from ..logging_setup import get_logger

log = get_logger("vision.face")

RETRY_COOLDOWN_S = 5.0

# FaceMesh landmark groups (with refine_landmarks=True)
LEFT_EYE_CORNERS = [33, 133]
RIGHT_EYE_CORNERS = [362, 263]
RIGHT_IRIS = [469, 470, 471, 472]
LEFT_IRIS = [474, 475, 476, 477]


@dataclass
class FaceData:
    present: bool = False
    landmarks_norm: Optional["np.ndarray"] = None
    bbox: tuple = (0, 0, 0, 0)  # x1, y1, x2, y2


class FaceTracker:
    def __init__(self, refine_landmarks: bool = True):
        self._mesh = None
        self._lock = threading.RLock()
        self.error: Optional[str] = None
        self._last_try_time = 0.0
        self._refine = refine_landmarks
        self._mp = None
        self._np = None

    def _load_deps(self) -> bool:
        if self._np is not None:
            return True
        try:
            import numpy as np
            import mediapipe as mp
            self._np = np
            self._mp = mp
            return True
        except ImportError as e:
            self.error = f"Dependency missing: {e}"
            return False

    def _ensure_model(self) -> bool:
        """Lazily load the MediaPipe FaceMesh model on first use.

        Failed loads are retried after a cooldown so a transient failure
        does not disable the feature permanently.
        """
        if self._mesh is not None:
            return True
        now = time.monotonic()
        with self._lock:
            if self._mesh is not None:
                return True
            if now - self._last_try_time < RETRY_COOLDOWN_S:
                return False
            self._last_try_time = now
        if not self._load_deps():
            return False
        try:
            self._mesh = self._mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=self._refine,
                min_detection_confidence=0.5,
            )
            return True
        except Exception as e:
            self.error = str(e)
            return False

    @property
    def available(self) -> bool:
        return self._mesh is not None

    def detect(self, bgr_frame: "np.ndarray", frame_w: int, frame_h: int) -> FaceData:
        if not self._ensure_model():
            return FaceData()
        np = self._np
        try:
            import cv2
            rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            res = self._mesh.process(rgb)
        except Exception:
            return FaceData()
        if not res.multi_face_landmarks:
            return FaceData()
        lm = res.multi_face_landmarks[0]
        pts = np.array([(p.x, p.y) for p in lm.landmark], dtype=np.float32)
        xs_n = pts[:, 0] * frame_w
        ys_n = pts[:, 1] * frame_h
        x1, y1 = int(xs_n.min()), int(ys_n.min())
        x2, y2 = int(xs_n.max()), int(ys_n.max())
        return FaceData(present=True, landmarks_norm=pts, bbox=(x1, y1, x2, y2))

    def close(self) -> None:
        if self._mesh is not None:
            self._mesh.close()
            self._mesh = None
