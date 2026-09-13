"""Gesture engine: temporal state machine that turns classified gestures
into concrete, debounced interaction events with confidence, cooldowns,
minimum durations and accidental-gesture rejection.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from ..config import GestureSettings, SETTINGS
from ..vision.hand_tracking import HandData, LM_WRIST, LM_MIDDLE_MCP
from .gesture_classifier import (
    GestureClassifier, GestureResult, POINT, PINCH, RIGHT_PINCH,
    OPEN_PALM, FIST, TWO_FINGER,
)

# ---- event kinds ----------------------------------------------------------
REST = "REST"
MOVE = "MOVE"
LEFT_CLICK = "LEFT_CLICK"
RIGHT_CLICK = "RIGHT_CLICK"
DOUBLE_CLICK = "DOUBLE_CLICK"
DRAG_START = "DRAG_START"
DRAG_UPDATE = "DRAG_UPDATE"
DRAG_END = "DRAG_END"
SCROLL_V = "SCROLL_V"
SCROLL_H = "SCROLL_H"
SWIPE_LEFT = "SWIPE_LEFT"
SWIPE_RIGHT = "SWIPE_RIGHT"
SWIPE_UP = "SWIPE_UP"
SWIPE_DOWN = "SWIPE_DOWN"
PALM_HOLD = "PALM_HOLD"
FIST_LOCK = "FIST_LOCK"
CIRCLE_CW = "CIRCLE_CW"
CIRCLE_CCW = "CIRCLE_CCW"

CLICK_EVENT_KINDS = {LEFT_CLICK, RIGHT_CLICK, DOUBLE_CLICK, DRAG_START, DRAG_END}


@dataclass
class GestureEvent:
    kind: str
    x: float = 0.0
    y: float = 0.0
    amount: int = 0
    confidence: float = 0.0
    gesture: str = ""
    ts: float = 0.0


def _wrap_angle(a: float) -> float:
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


class GestureEngine:
    """Produces GestureEvents from per-frame hand data."""

    def __init__(self, settings: GestureSettings | None = None,
                 on_event: Optional[Callable[[GestureEvent], None]] = None):
        self.settings = settings or SETTINGS.gestures
        self.on_event = on_event
        self.classifier = GestureClassifier(self.settings)
        self._history: deque[tuple[float, str]] = deque(maxlen=14)
        self.raw_gesture = ""
        self.raw_confidence = 0.0
        self.confirmed_gesture = REST
        self.last_event_time: dict[str, float] = {}
        self.locked = False
        self.paused = False
        self.last_event = GestureEvent(kind=REST)
        self._last_swipe_direction = "right"

        # motion history entries: (t_monotonic, x_norm, y_norm); x<0 => no hand
        self._positions: deque[tuple[float, float, float]] = deque(maxlen=20)
        self._angles: deque[tuple[float, float]] = deque(maxlen=30)

        self._pinch_active = False
        self._pinch_entry = 0.0
        self._pinch_anchor: Optional[tuple[float, float]] = None
        self._right_pinch_active = False
        self._right_pinch_entry = 0.0
        self._drag_on = False
        self._last_click_time = 0.0
        self._palm_open_since = 0.0
        self._fist_since = 0.0

    # ---- helpers -----------------------------------------------------------
    def _can_fire(self, kind: str, cooldown_ms: int) -> bool:
        now = time.monotonic()
        if now - self.last_event_time.get(kind, 0.0) < (cooldown_ms / 1000.0):
            return False
        self.last_event_time[kind] = now
        return True

    def _cast(self, ev: GestureEvent) -> GestureEvent:
        ev.ts = time.monotonic()
        ev.gesture = self.confirmed_gesture
        self.last_event = ev
        return ev

    def _emit(self, ev: GestureEvent) -> None:
        if self.on_event:
            try:
                self.on_event(ev)
            except Exception:
                pass

    # ---- main update -------------------------------------------------------
    def update(self, hands: list[HandData], pointer: Optional[tuple[float, float]],
               frame_w: int, frame_h: int) -> list[GestureEvent]:
        events: list[GestureEvent] = []
        if self.paused:
            return events

        cfg = self.settings
        now = time.monotonic()

        if self.locked:
            if hands:
                res = self.classifier.classify(hands[0])
                if res.name == FIST and res.confidence > cfg.gesture_confidence:
                    if self._fist_since == 0:
                        self._fist_since = now
                    elif now - self._fist_since > cfg.fist_lock_ms / 1000.0:
                        if self._can_fire(FIST_LOCK, cfg.gesture_cooldown_ms):
                            self.locked = False
                            self._fist_since = 0.0
                            events.append(self._cast(GestureEvent(kind=FIST_LOCK,
                                                                  confidence=res.confidence)))
                else:
                    self._fist_since = 0.0
            self.confirmed_gesture = FIST if self.locked else self.confirmed_gesture
            return events

        if not hands:
            self._reset_states()
            self.confirmed_gesture = REST
            self._positions.clear()
            return events

        primary = hands[0]
        res = self.classifier.classify(primary)
        self.raw_gesture = res.name
        self.raw_confidence = res.confidence

        g = self._confirm(res, now)
        self.confirmed_gesture = g

        idx_norm = primary.landmarks_norm[8]
        self._positions.append((now, float(idx_norm[0]), float(idx_norm[1])))
        if not self._movement_allowed(g):
            self._positions.append((now, -1.0, -1.0))

        # ---- circular gestures ---------------------------------------------
        if g in (OPEN_PALM, POINT, TWO_FINGER) and res.confidence > cfg.gesture_confidence:
            evt = self._track_angle(primary, res, now)
            if evt:
                events.append(self._cast(evt))

        # ---- swipes ---------------------------------------------------------
        events.extend(self._check_swipe(res))

        # ---- pinch -> left click / double / drag ----------------------------
        if g == PINCH:
            if not self._pinch_active and res.confidence > cfg.gesture_confidence:
                self._pinch_active = True
                self._pinch_entry = now
                self._pinch_anchor = pointer or res.position_px or None
        elif self._pinch_active:
            events.extend(self._finish_pinch(pointer, res, now))

        # ---- thumb+middle -> right click ------------------------------------
        if g == RIGHT_PINCH:
            if not self._right_pinch_active and res.confidence > cfg.gesture_confidence:
                self._right_pinch_active = True
                self._right_pinch_entry = now
        elif self._right_pinch_active:
            held = (now - self._right_pinch_entry) * 1000.0
            self._right_pinch_active = False
            if held >= cfg.pinch_dwell_click_ms:
                if self._can_fire(RIGHT_CLICK, cfg.gesture_cooldown_ms):
                    x, y = self._pos_or(pointer, res, 0, 0)
                    events.append(self._cast(GestureEvent(kind=RIGHT_CLICK, x=x, y=y,
                                                          confidence=res.confidence)))

        # ---- open palm: scroll + hold-pause ---------------------------------
        if g == OPEN_PALM:
            if self._palm_open_since == 0:
                self._palm_open_since = now
            scroll_ev = self._scroll_from_motion()
            if scroll_ev:
                events.append(self._cast(scroll_ev))
            elif now - self._palm_open_since >= cfg.palm_hold_ms / 1000.0:
                if self._can_fire(PALM_HOLD, cfg.gesture_cooldown_ms):
                    events.append(self._cast(GestureEvent(kind=PALM_HOLD,
                                                          confidence=res.confidence)))
        else:
            self._palm_open_since = 0.0

        # ---- fist: interaction lock -----------------------------------------
        if g == FIST:
            if self._fist_since == 0:
                self._fist_since = now
            elif now - self._fist_since >= cfg.fist_lock_ms / 1000.0:
                if self._can_fire(FIST_LOCK, cfg.gesture_cooldown_ms):
                    self.locked = True
                    self._reset_states()
                    events.clear()
                    events.append(self._cast(GestureEvent(kind=FIST_LOCK,
                                                          confidence=res.confidence)))
                    return events
        else:
            self._fist_since = 0.0

        # ---- cursor movement --------------------------------------------------
        if pointer is not None and self._movement_allowed(g):
            if self._drag_on:
                events.append(self._cast(GestureEvent(kind=DRAG_UPDATE, x=pointer[0],
                                                      y=pointer[1])))
            else:
                events.append(self._cast(GestureEvent(kind=MOVE, x=pointer[0],
                                                      y=pointer[1], confidence=res.confidence)))

        return events

    # ---- internals ----------------------------------------------------------
    def _movement_allowed(self, g: str) -> bool:
        return g in (POINT, PINCH, RIGHT_PINCH, TWO_FINGER) and not self.locked

    def _pos_or(self, pointer, res, dx=0.0, dy=0.0) -> tuple[float, float]:
        p = pointer or (res.position_px if res and res.position_px else (0, 0))
        return (p[0] + dx, p[1] + dy)

    def _confirm(self, res: GestureResult, now: float) -> str:
        name = res.name if res.recognized else REST
        self._history.append((now, name))
        window_t = now - 0.3
        counts: dict[str, int] = {}
        for t, g in self._history:
            if t >= window_t:
                counts[g] = counts.get(g, 0) + 1
        if not counts:
            return REST
        best = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
        if best != REST and counts[best] / len(counts) >= 0.5:
            return best
        return REST

    def _check_swipe(self, res: GestureResult) -> list[GestureEvent]:
        cfg = self.settings
        now = time.monotonic()
        recent = [p for p in self._positions if p[1] >= 0 and now - p[0] <= 0.45]
        if len(recent) < 6:
            return []
        x0, y0 = recent[0][1], recent[0][2]
        x1, y1 = recent[-1][1], recent[-1][2]
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy)
        if dist < cfg.swipe_distance:
            return []
        if abs(dx) > abs(dy) and abs(dy) / max(abs(dx), 1e-6) > 0.9:
            return []
        if abs(dy) >= abs(dx) and abs(dx) / max(abs(dy), 1e-6) > 0.9:
            return []
        direction = "left" if dx < 0 else "right" if abs(dx) > abs(dy) else ("up" if dy < 0 else "down")
        kind = {"left": SWIPE_LEFT, "right": SWIPE_RIGHT,
                "up": SWIPE_UP, "down": SWIPE_DOWN}[direction]
        if not self._can_fire(kind, 900):
            return []
        self._positions.clear()
        return [GestureEvent(kind=kind, confidence=res.confidence,
                             gesture=self.confirmed_gesture)]

    def _scroll_from_motion(self):
        cfg = self.settings
        now = time.monotonic()
        recent = [p for p in self._positions if p[1] >= 0 and now - p[0] <= 0.25]
        if len(recent) < 4:
            return None
        y0 = recent[0][2]
        y1 = recent[-1][2]
        dy = y1 - y0
        thr = cfg.scroll_velocity_threshold
        if abs(dy) < thr:
            return None
        if not self._can_fire(SCROLL_V, cfg.scroll_gesture_cooldown_ms):
            return None
        amount = int(float(np.clip(dy / thr, -12.0, 12.0)))
        return GestureEvent(kind=SCROLL_V, amount=amount)

    def _track_angle(self, primary: HandData, res: GestureResult, now: float):
        wrist = primary.landmarks_norm[LM_WRIST]
        mcp = primary.landmarks_norm[LM_MIDDLE_MCP]
        center = (wrist + mcp) / 2.0
        idx = primary.landmarks_norm[8]
        angle = math.atan2(float(idx[1] - center[1]), float(idx[0] - center[0]))
        self._angles.append((angle, now))
        while self._angles and now - self._angles[0][1] > 0.9:
            self._angles.popleft()
        if len(self._angles) < 6:
            return None
        total = 0.0
        prev = self._angles[0][0]
        for a, _ in self._angles:
            total += _wrap_angle(a - prev)
            prev = a
        if abs(total) >= math.tau:
            kind = CIRCLE_CW if total > 0 else CIRCLE_CCW
            if self._can_fire(kind, 1200):
                self._angles.clear()
                self._positions.clear()
                return GestureEvent(kind=kind, confidence=res.confidence)
        return None

    def _finish_pinch(self, pointer, res, now) -> list[GestureEvent]:
        """On pinch release: click, double click, or start drag."""
        events: list[GestureEvent] = []
        cfg = self.settings
        held = (now - self._pinch_entry) * 1000.0
        p = self._pos_or(pointer, res)
        if self._pinch_anchor is not None:
            moved = math.hypot(p[0] - self._pinch_anchor[0], p[1] - self._pinch_anchor[1])
        else:
            moved = 0.0

        if self._drag_on:
            # drag in progress finishes with this release
            self._drag_on = False
            events.append(self._cast(GestureEvent(kind=DRAG_END, x=p[0], y=p[1],
                                                  confidence=res.confidence)))
        elif held >= cfg.pinch_dwell_click_ms:
            click_window = cfg.pinch_double_click_window_ms / 1000.0
            if self._last_click_time and now - self._last_click_time < click_window:
                if self._can_fire(DOUBLE_CLICK, cfg.gesture_cooldown_ms):
                    self._last_click_time = 0.0
                    events.append(self._cast(GestureEvent(kind=DOUBLE_CLICK, x=p[0], y=p[1],
                                                          confidence=res.confidence)))
            else:
                if self._can_fire(LEFT_CLICK, cfg.gesture_cooldown_ms):
                    if moved > 12:
                        # dragged without crossing drag threshold: treat as drag
                        self._drag_on = True
                    else:
                        self._last_click_time = now
                        events.append(self._cast(GestureEvent(kind=LEFT_CLICK, x=p[0], y=p[1],
                                                              confidence=res.confidence)))
        self._pinch_active = False
        self._pinch_entry = 0.0
        self._pinch_anchor = None
        return events

    def _reset_states(self) -> None:
        self._pinch_active = False
        self._pinch_entry = 0.0
        self._pinch_anchor = None
        self._right_pinch_active = False
        self._right_pinch_entry = 0.0
        self._drag_on = False
        self._palm_open_since = 0.0
        self._fist_since = 0.0
        self._angles.clear()

    # ---- public ------------------------------------------------------------
    def pause(self) -> None:
        self.paused = True
        self._reset_states()

    def resume(self) -> None:
        self.paused = False

    def reset_buffer(self) -> None:
        self._positions.clear()
        self._history.clear()
        self._angles.clear()
        self._reset_states()