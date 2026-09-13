"""Face landmark tracking (used for the optional gaze feature)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..logging_setup import get_logger

log = get_logger("vision.face")

try:
    import mediapipe as mp
    import cv2
    HAVE_MEDIAPIPE = True
except Exception:
    HAVE_MEDIAPIPE = False

# FaceMesh landmark groups (with refine_landmarks=True)
LEFT_EYE_CORNERS = [33, 133]
RIGHT_EYE_CORNERS = [362, 263]
RIGHT_IRIS = [469, 470, 471, 472]
LEFT_IRIS = [474, 475, 476, 477]


@dataclass
class FaceData:
    present: bool = False
    landmarks_norm: Optional[np.ndarray] = None
    bbox: tuple = (0, 0, 0, 0)  # x1, y1, x2, y2


class FaceTracker:
    def __init__(self, refine_landmarks: bool = True):
        self._mesh = None
        self.error: Optional[str] = None
        if HAVE_MEDIAPIPE:
            try:
                self._mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    refine_landmarks=refine_landmarks,
                    min_detection_confidence=0.5,
                )
            except Exception as e:
                self.error = str(e)
        else:
            self.error = "MediaPipe is not installed"

    @property
    def available(self) -> bool:
        return self._mesh is not None

    def detect(self, bgr_frame: np.ndarray, frame_w: int, frame_h: int) -> FaceData:
        if self._mesh is None:
            return FaceData()
        try:
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