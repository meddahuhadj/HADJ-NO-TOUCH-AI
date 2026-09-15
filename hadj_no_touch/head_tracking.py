"""HADJ Head Control.

A real, measured head-direction controller built on the existing FaceMesh
landmarks: the nose tip position relative to the face bounding box decides
"turned left / right", "lifted up / down". Direction must be held steadily
for ``hold_ms`` before an event fires; a cooldown prevents machine-gunning.

Intent mapping depends on the active context (presentation, media, pdf...).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from hadj_no_touch.ai import intent_engine as ie

HEAD_LEFT = "HEAD_LEFT"
HEAD_RIGHT = "HEAD_RIGHT"
HEAD_UP = "HEAD_UP"
HEAD_DOWN = "HEAD_DOWN"


@dataclass
class HeadEvent:
    direction: str
    confidence: float
    ts: float = field(default_factory=time.monotonic)

    def describe(self) -> str:
        return f"Head {self.direction}"


# gesture-style actions available for a given context category
HEAD_ACTIONS: dict[str, dict[str, str]] = {
    "presentation": {HEAD_LEFT: ie.PREV_SLIDE, HEAD_RIGHT: ie.NEXT_SLIDE},
    "media": {
        HEAD_LEFT: ie.PREV_TRACK, HEAD_RIGHT: ie.NEXT_TRACK,
        HEAD_UP: ie.VOLUME_UP, HEAD_DOWN: ie.VOLUME_DOWN,
    },
    "pdf": {
        HEAD_LEFT: ie.PREV_PAGE, HEAD_RIGHT: ie.NEXT_PAGE,
        HEAD_UP: ie.ZOOM_IN, HEAD_DOWN: ie.ZOOM_OUT,
    },
    "office": {
        HEAD_LEFT: ie.PREV_PAGE, HEAD_RIGHT: ie.NEXT_PAGE,
        HEAD_UP: ie.ZOOM_IN, HEAD_DOWN: ie.ZOOM_OUT,
    },
    "imaging": {
        HEAD_LEFT: ie.PREV_DIAGNOSTIC, HEAD_RIGHT: ie.NEXT_DIAGNOSTIC,
        HEAD_UP: ie.ZOOM_IN, HEAD_DOWN: ie.ZOOM_OUT,
    },
    "browser": {
        HEAD_LEFT: ie.GO_BACK, HEAD_RIGHT: ie.GO_FORWARD,
        HEAD_UP: ie.NEXT_TAB, HEAD_DOWN: ie.PREV_TAB,
    },
    "other": {
        HEAD_LEFT: ie.PREV_PAGE, HEAD_RIGHT: ie.NEXT_PAGE,
        HEAD_UP: ie.SCROLL, HEAD_DOWN: ie.SCROLL,
    },
}


def head_action_for(context_category: str, direction: str) -> str | None:
    mapping = HEAD_ACTIONS.get(context_category, HEAD_ACTIONS["other"])
    return mapping.get(direction)


def estimate_direction(landmarks_norm, sensitivity: float = 0.12) -> tuple[str, float]:
    """Return (direction, confidence) from normalised FaceMesh landmarks.

    Nose landmark (index 1) offset from the face bbox centre, normalised by
    the bbox size, so it is scale invariant. Confidence decays with distance
    from the sensitivity threshold.
    """
    try:
        import numpy as np
    except ImportError:
        return "NEUTRAL", 0.0
    if landmarks_norm is None:
        return "NEUTRAL", 0.0
    pts = np.asarray(landmarks_norm, dtype=np.float32)
    if pts.ndim != 2 or pts.shape[0] < 2 or pts.shape[1] < 2:
        return "NEUTRAL", 0.0
    xs, ys = pts[:, 0], pts[:, 1]
    x1, x2 = float(xs.min()), float(xs.max())
    y1, y2 = float(ys.min()), float(ys.max())
    w = max(x2 - x1, 1e-6)
    h = max(y2 - y1, 1e-6)
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    nose = pts[1]  # MediaPipe nose tip
    nx = (float(nose[0]) - cx) / w
    ny = (float(nose[1]) - cy) / h
    # The larger the offset the more confident we are (clipped at 0..1)
    conf = lambda v: max(0.0, min(1.0, abs(v) / max(sensitivity * 2.5, 1e-6)))
    if abs(nx) >= sensitivity * 1.5 and abs(nx) >= abs(ny):
        return (HEAD_LEFT if nx < 0 else HEAD_RIGHT), round(conf(nx), 3)
    if abs(ny) >= sensitivity * 1.5 and abs(ny) > abs(nx):
        return (HEAD_UP if ny < 0 else HEAD_DOWN), round(conf(ny), 3)
    return "NEUTRAL", 0.0


class HeadController:
    """Debounced + hold-gated consumer of face landmarks."""

    def __init__(self, sensitivity: float = 0.12,
                 hold_ms: int = 300, cooldown_ms: int = 900):
        self.sensitivity = float(sensitivity)
        self.hold_ms = int(hold_ms)
        self.cooldown_ms = int(cooldown_ms)
        self._current: str = "NEUTRAL"
        self._since: float = time.monotonic()
        self._last_event: float = 0.0
        self._last_conf: float = 0.0
        self.frames_seen = 0

    def update(self, landmarks_norm) -> HeadEvent | None:
        """Feed each processed frame's landmarks; fire a held direction once."""
        now = time.monotonic()
        direction, conf = estimate_direction(landmarks_norm, self.sensitivity)
        self.frames_seen += 1
        if direction == self._current:
            held = (now - self._since) * 1000.0
            if (now - self._last_event) * 1000.0 >= self.cooldown_ms \
                    and held >= self.hold_ms and direction != "NEUTRAL":
                self._last_event = now
                return HeadEvent(direction=direction, confidence=conf)
        else:
            self._current = direction
            self._since = now
        self._last_conf = conf
        return None