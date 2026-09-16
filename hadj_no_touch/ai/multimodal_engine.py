"""Multimodal engine: fuses gaze + pointing + pinch + voice + context.

Used for the "AI Copilot" behaviour and for gaze-confirmed pointer actions
(e.g. pinch a button only when you are also looking at it).
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from ..logging_setup import get_logger
from .context_engine import ApplicationContext
from .intent_engine import Intent
from ..gestures import gesture_engine as ge
from ..voice import voice_commands as vc

log = get_logger("ai.multimodal")

GAZE_MATCH_RADIUS = 0.25  # normalized screen distance for gaze/pointer agreement


@dataclass
class MultimodalState:
    gaze_xy: tuple[float, float] = (0.5, 0.5)
    gaze_active: bool = False
    pointer_xy: tuple[float, float] = (0.5, 0.5)
    pointer_active: bool = False
    pinch_confidence: float = 0.0
    last_gesture_event: str = ""
    last_voice: str = ""
    last_context: str = ""
    last_intent: str = ""
    gaze_pointer_match: float = 1.0
    copilot_hint: str = ""
    agents: dict = field(default_factory=dict)


class MultimodalEngine:
    def __init__(self):
        self.state = MultimodalState()
        self._gaze_recent: deque[tuple[float, float, float]] = deque()

    # ---- inputs ---------------------------------------------------
    def set_gaze(self, gx: float, gy: float, active: bool) -> None:
        """Record a gaze estimate in *screen-normalized* [0,1] space, i.e. the
        same coordinate space as the pointer, so gaze/pointer matching is
        meaningful. The caller is responsible for converting raw tracker
        output into [0,1] before calling this."""
        self.state.gaze_xy = (float(gx), float(gy))
        self.state.gaze_active = active
        now = time.monotonic()
        self._gaze_recent.append((float(gx), float(gy), now))
        while self._gaze_recent and now - self._gaze_recent[0][2] > 0.8:
            self._gaze_recent.popleft()

    def set_pointer(self, px: float, py: float, active: bool) -> None:
        self.state.pointer_xy = (float(px), float(py))
        self.state.pointer_active = active
        self._update_match()

    def on_gesture(self, event: ge.GestureEvent) -> None:
        self.state.last_gesture_event = event.kind

    def on_voice(self, vi: vc.VoiceIntent) -> None:
        self.state.last_voice = vi.raw_text

    def on_intent(self, intent: Intent) -> None:
        self.state.last_intent = intent.describe()

    def set_context(self, ctx: ApplicationContext) -> None:
        self.state.last_context = ctx.description

    def set_copilot_hint(self, hint: str) -> None:
        self.state.copilot_hint = hint

    # ---- reasoning -------------------------------------------------
    def _update_match(self) -> None:
        g = self.state.gaze_xy
        p = self.state.pointer_xy
        if not self.state.gaze_active:
            self.state.gaze_pointer_match = 1.0
            return
        d = ((g[0] - p[0]) ** 2 + (g[1] - p[1]) ** 2) ** 0.5
        match = max(0.0, 1.0 - d / GAZE_MATCH_RADIUS)
        self.state.gaze_pointer_match = match

    def gaze_confirms_pointer(self, pinch_confidence: float) -> bool:
        """A pinch at the pointer position is trusted if gaze agrees."""
        if not self.state.gaze_active:
            return pinch_confidence >= 0.55
        return pinch_confidence >= 0.35 and self.state.gaze_pointer_match >= 0.5

    def average_gaze(self) -> tuple[float, float]:
        if not self._gaze_recent:
            return self.state.gaze_xy
        n = len(self._gaze_recent)
        return (sum(p[0] for p in self._gaze_recent) / n,
                sum(p[1] for p in self._gaze_recent) / n)

    # ---- copilot -----------------------------------------------------------
    def copilot_assess(self, vi: vc.VoiceIntent, ctx: ApplicationContext,
                       pending_intent: Intent | None) -> Intent | None:
        """Run in Copilot mode: confirm/enrich an ambiguous command."""
        if vi.intent != vc.COPILOT:
            if pending_intent and pending_intent.action in ("CLOSE_WINDOW", "CLOSE_TAB"):
                # Ask a lightweight confirmation before destructive closing.
                pending_intent.needs_confirmation = True
            return pending_intent
        # Ambiguous copilot request: produce a reasoned intent from context.
        hint = self._copilot_hint_for(vi, ctx)
        self.set_copilot_hint(hint)
        return Intent(action="COPILOT", params={"hint": hint}, confidence=0.5,
                      source="copilot", description=hint, needs_confirmation=True)

    @staticmethod
    def _copilot_hint_for(vi: vc.VoiceIntent, ctx: ApplicationContext) -> str:
        text = vi.raw_text.lower()
        if "settings" in text or "configuration" in text or "param" in text:
            return f"Open Settings (active app: {ctx.description})"
        if "lights" in text or "lum" in text:
            return "Control smart lights — requires smart-home extension (Coming Soon)"
        if ctx.category == "presentation" and ("slide" in text or "page" in text):
            return "Navigate slides (use swipe or say 'next slide')"
        if ctx.category == "pdf" and ("manual" in text or "doc" in text or "page" in text):
            return "Navigate the open document (say 'next page' or 'previous page')"
        if ctx.is_media_like and "volume" in text:
            return "Set volume (say 'volume 50 percent')"
        return f"Ambiguous request; suggest: context-aware navigation in {ctx.description}"

    def snapshot(self) -> MultimodalState:
        return self.state