"""Hand tracking with MediaPipe Hands (local processing only)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from ..config import SETTINGS
from ..logging_setup import get_logger

log = get_logger("vision.hand")

RETRY_COOLDOWN_S = 5.0

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
    landmarks_norm: "np.ndarray"  # (21, 2) normalized [0..1]
    landmarks_px: "np.ndarray"    # (21, 2) pixel coords
    handedness: str = "Right"
    confidence: float = 0.0
    tracked: bool = False

    def landmark(self, idx: int) -> "np.ndarray":
        import numpy as np
        return self.landmarks_px[idx]


class HandTracker:
    """Thin wrapper around MediaPipe Hands (model loaded lazily on first frame)."""

    def __init__(self, settings=None):
        self.settings = settings or SETTINGS.tracking
        self._hands = None
        self._lock = threading.RLock()
        self.error: Optional[str] = None
        self._last_try_time = 0.0
        self._mp = None
        self._cv2 = None
        self._np = None

    def _load_deps(self) -> bool:
        """Lazy-load mediapipe, cv2 and numpy on first use (~2.2s cached once)."""
        if self._np is not None:
            return True
        try:
            import numpy as np
            import cv2
            import mediapipe as mp
            self._np = np
            self._cv2 = cv2
            self._mp = mp
            return True
        except ImportError as e:
            self.error = f"Dependency missing: {e}"
            return False

    def _ensure_model(self) -> bool:
        """Lazily load the MediaPipe Hands model on first use.

        Failed loads are retried after a cooldown so a transient failure
        (e.g. model file still being downloaded) does not disable the
        feature permanently.
        """
        if self._hands is not None:
            return True
        now = time.monotonic()
        with self._lock:
            if self._hands is not None:
                return True
            if now - self._last_try_time < RETRY_COOLDOWN_S:
                return False
            self._last_try_time = now
        if not self._load_deps():
            return False
        try:
            self._hands = self._mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=self.settings.max_hands,
                model_complexity=self.settings.model_complexity,
                min_detection_confidence=self.settings.min_detection_confidence,
                min_tracking_confidence=self.settings.min_tracking_confidence,
            )
            return True
        except Exception as e:
            self.error = str(e)
            log.error("HandTracker init failed: %s", e)
            return False

    @property
    def available(self) -> bool:
        return self._hands is not None

    def detect(self, bgr_frame: "np.ndarray", frame_w: int, frame_h: int) -> list[HandData]:
        if not self._ensure_model():
            return []
        np, cv2 = self._np, self._cv2
        try:
            rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            with self._lock:
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
