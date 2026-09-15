"""Static gesture classification from a hand landmarks array.

Produces a named gesture plus a confidence. Thresholds come from config so
algorithms can be tuned without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..config import GestureSettings, SETTINGS
from ..vision.hand_tracking import HandData
from ..vision.hand_tracking import (
    LM_WRIST, LM_THUMB_TIP, LM_INDEX_TIP, LM_INDEX_PIP, LM_MIDDLE_TIP,
    LM_MIDDLE_PIP, LM_RING_TIP, LM_RING_PIP, LM_PINKY_TIP, LM_PINKY_PIP,
    LM_MIDDLE_MCP,
)

# Named gesture constants shared across modules.
POINT = "POINT"
PINCH = "PINCH"
RIGHT_PINCH = "RIGHT_PINCH"
OPEN_PALM = "OPEN_PALM"
FIST = "FIST"
TWO_FINGER = "TWO_FINGER"
THREE_FINGER = "THREE_FINGER"
FOUR_FINGER = "FOUR_FINGER"
VICTORY = "VICTORY"
REST = "REST"
UNKNOWN = "UNKNOWN"


@dataclass
class GestureResult:
    name: str = UNKNOWN
    confidence: float = 0.0
    position_px: Optional[tuple[float, float]] = None
    position_norm: Optional[tuple[float, float]] = None
    fingers_extended: tuple[bool, bool, bool, bool, bool] = (False, False, False, False, False)
    pinch_index_dist_ratio: float = 1.0
    pinch_middle_dist_ratio: float = 1.0
    recognized: bool = False


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


class GestureClassifier:
    def __init__(self, settings: GestureSettings = SETTINGS.gestures):
        self.settings = settings

    def fingers_extended(self, hand: HandData) -> tuple[bool, bool, bool, bool, bool]:
        """thumb, index, middle, ring, pinky."""
        p = hand.landmarks_norm
        wrist = p[LM_WRIST]
        thumb = _dist(p[LM_THUMB_TIP], wrist) > _dist(p[LM_MIDDLE_MCP], wrist) * 0.55
        index = _dist(p[LM_INDEX_TIP], wrist) > _dist(p[LM_INDEX_PIP], wrist) * 1.02
        middle = _dist(p[LM_MIDDLE_TIP], wrist) > _dist(p[LM_MIDDLE_PIP], wrist) * 1.02
        ring = _dist(p[LM_RING_TIP], wrist) > _dist(p[LM_RING_PIP], wrist) * 1.02
        pinky = _dist(p[LM_PINKY_TIP], wrist) > _dist(p[LM_PINKY_PIP], wrist) * 1.02
        return (thumb, index, middle, ring, pinky)

    def classify(self, hand: HandData,
                 settings: GestureSettings | None = None) -> GestureResult:
        cfg = settings or self.settings
        if not hand.tracked:
            return GestureResult(name=REST, confidence=0.0, recognized=False)

        p = hand.landmarks_norm
        wrist = p[LM_WRIST]
        scale = max(_dist(wrist, p[LM_MIDDLE_MCP]), 1e-4)

        thumb_tip, index_tip, middle_tip = p[LM_THUMB_TIP], p[LM_INDEX_TIP], p[LM_MIDDLE_TIP]

        d_thumb_index = _dist(thumb_tip, index_tip) / scale
        d_thumb_middle = _dist(thumb_tip, middle_tip) / scale

        fe = self.fingers_extended(hand)
        thumb, index, middle, ring, pinky = fe

        index_px = (float(index_tip[0]), float(index_tip[1])) if index_tip.size == 2 else None
        norm = (float(hand.landmarks_norm[LM_INDEX_TIP][0]),
                float(hand.landmarks_norm[LM_INDEX_TIP][1]))

        pinched = d_thumb_index < cfg.pinch_distance_ratio
        pinched_middle = d_thumb_middle < cfg.pinch_middle_distance_ratio

        # Confidence for pinch: how far under the threshold it is.
        pinch_conf = float(np.clip(1.0 - d_thumb_index / max(cfg.pinch_distance_ratio, 1e-4), 0.0, 1.0))
        pinch_conf = float(np.clip(pinch_conf * 1.4, 0.0, 1.0))

        if pinched_middle and not pinched:
            return self._res(RIGHT_PINCH, pinch_conf, index_px, norm, fe,
                             d_thumb_index, d_thumb_middle)
        if pinched:
            return self._res(PINCH, pinch_conf, index_px, norm, fe,
                             d_thumb_index, d_thumb_middle)

        n_extended = sum(fe[1:])
        if n_extended <= 0 and not thumb:
            return self._res(FIST, 0.8 if not thumb else 0.6, index_px, norm, fe,
                             d_thumb_index, d_thumb_middle)
        if n_extended >= 4:
            return self._res(OPEN_PALM, 0.7 + 0.1 * n_extended, index_px, norm, fe,
                             d_thumb_index, d_thumb_middle)
        if fe[1] and not fe[2] and not fe[3] and not fe[4]:
            return self._res(POINT, 0.75, index_px, norm, fe,
                             d_thumb_index, d_thumb_middle)
        if fe[1] and fe[2] and not fe[3] and not fe[4]:
            return self._res(TWO_FINGER, 0.65, index_px, norm, fe,
                             d_thumb_index, d_thumb_middle)
        if fe[1] and fe[2] and fe[3] and not fe[4]:
            return self._res(THREE_FINGER, 0.6, index_px, norm, fe,
                             d_thumb_index, d_thumb_middle)
        if fe[1] and fe[2] and not fe[3] and fe[4] and not thumb:
            return self._res(VICTORY, 0.6, index_px, norm, fe,
                             d_thumb_index, d_thumb_middle)
        if fe[1] and fe[2] and fe[3] and fe[4]:
            return self._res(FOUR_FINGER, 0.6, index_px, norm, fe,
                             d_thumb_index, d_thumb_middle)
        return GestureResult(name=UNKNOWN, confidence=0.3, position_px=index_px,
                             position_norm=norm, fingers_extended=fe,
                             pinch_index_dist_ratio=d_thumb_index,
                             pinch_middle_dist_ratio=d_thumb_middle,
                             recognized=False)

    @staticmethod
    def _res(name, conf, pos_px, pos_norm, fe, dti, dtm):
        return GestureResult(name=name, confidence=conf, position_px=pos_px,
                             position_norm=pos_norm, fingers_extended=fe,
                             pinch_index_dist_ratio=dti, pinch_middle_dist_ratio=dtm,
                             recognized=True)