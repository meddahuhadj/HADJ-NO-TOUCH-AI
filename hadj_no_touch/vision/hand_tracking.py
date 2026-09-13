"""Hand tracking with MediaPipe Hands (local processing only)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..config import SETTINGS
from ..logging_setup import get_logger

log = get_logger("vision.hand")

try:
    import mediapipe as mp
    import cv2
    HAVE_MEDIAPIPE = True
except Exception:
    HAVE_MEDIAPIPE = False

# Human-friendly landmark names (MediaPipe Hands).
LM_WRIST = 0
LM_THUMB_CMC = 1
LM_THUMB_MCP = 2
LM_THUMB_IP = 3
LM_THUMB_TIP = 4
LM_INDEX_MCP = 5
LM_INDEX_PIP = 6
LM_INDEX_DIP = 7
LM_INDEX_TIP = 8
LM_MIDDLE_MCP = 9
LM_MIDDLE_PIP = 10
LM_MIDDLE_DIP = 11
LM_MIDDLE_TIP = 12
LM_RING_MCP = 13
LM_RING_PIP = 14
LM_RING_DIP = 15
LM_RING_TIP = 16
LM_PINKY_MCP = 17
LM_PINKY_PIP = 18
LM_PINKY_DIP = 19
LM_PINKY_TIP = 20


@dataclass
class HandData:
    landmarks_norm: np.ndarray  # (21, 2) normalized [0..1]
    landmarks_px: np.ndarray  # (21, 2) pixel coords
    handedness: str = "Right"
    confidence: float = 0.0
    tracked: bool = False

    def landmark(self, idx: int) -> np.ndarray:
        return self.landmarks_px[idx]


class HandTracker:
    """Thin wrapper around MediaPipe Hands."""

    def __init__(self, settings=None):
        self.settings = settings or SETTINGS.tracking
        self._hands = None
        self._lock = threading.RLock()
        self.error: Optional[str] = None
        if HAVE_MEDIAPIPE:
            try:
                self._hands = mp.solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=self.settings.max_hands,
                    model_complexity=self.settings.model_complexity,
                    min_detection_confidence=self.settings.min_detection_confidence,
                    min_tracking_confidence=self.settings.min_tracking_confidence,
                )
            except Exception as e:
                self.error = str(e)
                log.error("HandTracker init failed: %s", e)
        else:
            self.error = "MediaPipe is not installed"

    @property
    def available(self) -> bool:
        return self._hands is not None

    def detect(self, bgr_frame: np.ndarray, frame_w: int, frame_h: int) -> list[HandData]:
        if self._hands is None:
            return []
        try:
            rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            with self._lock:  # serialise MediaPipe inference across threads
                res = self._hands.process(rgb)
        except Exception as e:
            log.debug("hand detect error: %s", e)
            return []
        if not res.multi_hand_landmarks:
            return []
        hands: list[HandData] = []
        for lm, hnd in zip(res.multi_hand_landmarks, res.multi_handedness):
            pts = [(p.x, p.y) for p in lm.landmark]
            norm = np.array(pts, dtype=np.float32)
            px = np.array([(p.x * frame_w, p.y * frame_h) for p in lm.landmark], dtype=np.float32)
            conf = float(hnd.classification[0].score if hnd.classification else 0.0)
            label = hnd.classification[0].label if hnd.classification else "Right"
            hands.append(HandData(landmarks_norm=norm, landmarks_px=px, handedness=label, confidence=conf, tracked=True))
        return hands

    def close(self) -> None:
        if self._hands is not None:
            self._hands.close()
            self._hands = None