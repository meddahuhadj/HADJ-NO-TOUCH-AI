"""Context-aware AI intent engine.

Fuses gesture primitives + voice intents + the active application context
into deliberate, real actions. This is the layer that gives the product its
"understands what you want" behaviour -- e.g. "swipe while watching a video
= next video", "point at a window and say close this = close it".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..gestures import gesture_engine as ge
from ..voice import voice_commands as vc
from ..logging_setup import get_logger
from .context_engine import ApplicationContext

log = get_logger("ai.intent")

# ---- action names ----------------------------------------------------------
MOUSE_MOVE = "MOUSE_MOVE"
LEFT_CLICK = "LEFT_CLICK"
RIGHT_CLICK = "RIGHT_CLICK"
DOUBLE_CLICK = "DOUBLE_CLICK"
DRAG = "DRAG"
SCROLL = "SCROLL"
NEXT_SLIDE = "NEXT_SLIDE"
PREV_SLIDE = "PREV_SLIDE"
START_PRESENTATION = "START_PRESENTATION"
END_PRESENTATION = "END_PRESENTATION"
BLACK_SCREEN = "BLACK_SCREEN"
NEXT_PAGE = "NEXT_PAGE"
PREV_PAGE = "PREV_PAGE"
GO_BACK = "GO_BACK"
GO_FORWARD = "GO_FORWARD"
ZOOM_IN = "ZOOM_IN"
ZOOM_OUT = "ZOOM_OUT"
NEXT_TRACK = "NEXT_TRACK"
PREV_TRACK = "PREV_TRACK"
PLAY_PAUSE = "PLAY_PAUSE"
STOP_MEDIA = "STOP_MEDIA"
VOLUME_UP = "VOLUME_UP"
VOLUME_DOWN = "VOLUME_DOWN"
VOLUME_SET = "VOLUME_SET"
MUTE = "MUTE"
UNMUTE = "UNMUTE"
COPY = "COPY"
PASTE = "PASTE"
CUT = "CUT"
UNDO = "UNDO"
SELECT_ALL = "SELECT_ALL"
SCREENSHOT = "SCREENSHOT"
PRESS_ENTER = "PRESS_ENTER"
TAB_KEY = "TAB_KEY"
TYPE_TEXT = "TYPE_TEXT"
OPEN_APP = "OPEN_APP"
CLOSE_WINDOW = "CLOSE_WINDOW"
MINIMIZE = "MINIMIZE"
MAXIMIZE = "MAXIMIZE"
SWITCH_WINDOW = "SWITCH_WINDOW"
SHOW_DESKTOP = "SHOW_DESKTOP"
NEXT_TAB = "NEXT_TAB"
PREV_TAB = "PREV_TAB"
CLOSE_TAB = "CLOSE_TAB"
NEW_TAB = "NEW_TAB"
REFRESH = "REFRESH"
FIND = "FIND"
OPEN_SETTINGS = "OPEN_SETTINGS"
PAUSE_CONTROL = "PAUSE_CONTROL"
RESUME_CONTROL = "RESUME_CONTROL"
EMERGENCY_STOP = "EMERGENCY_STOP"
HANDS_BUSY_ON = "HANDS_BUSY_ON"
HANDS_BUSY_OFF = "HANDS_BUSY_OFF"
CALIBRATE = "CALIBRATE"
TOGGLE_KEYBOARD = "TOGGLE_KEYBOARD"
SHOW_UI = "SHOW_UI"
HIDE_UI = "HIDE_UI"
HELP = "HELP"
PROFILE_SWITCH = "PROFILE_SWITCH"
COPILOT = "COPILOT"
ROTATE_3D = "ROTATE_3D"
NEXT_IMAGE = "NEXT_IMAGE"
PREV_IMAGE = "PREV_IMAGE"
NEXT_DIAGNOSTIC = "NEXT_DIAGNOSTIC"
PREV_DIAGNOSTIC = "PREV_DIAGNOSTIC"
PAUSE_INTERACTION = "PAUSE_INTERACTION"
FIST_LOCK = "FIST_LOCK"
LASER_POINTER = "LASER_POINTER"
LIGHT_CONTROL = "LIGHT_CONTROL"  # reserved for future smart-home

SENSITIVE_ACTIONS = {CLOSE_WINDOW, CLOSE_TAB, EMERGENCY_STOP}


@dataclass
class Intent:
    action: str
    params: dict = field(default_factory=dict)
    confidence: float = 1.0
    source: str = "context"
    description: str = ""
    needs_confirmation: bool = False

    def describe(self) -> str:
        if self.description:
            return self.description
        return self.action


# Mapping: symbolic gesture -> (context category -> action)
GESTURE_ACTIONS: dict[str, dict[str, str]] = {
    ge.SWIPE_LEFT: {
        "presentation": NEXT_SLIDE,
        "pdf": NEXT_PAGE,
        "office": NEXT_PAGE,
        "media": NEXT_TRACK,
        "browser": GO_FORWARD,
        "imaging": NEXT_DIAGNOSTIC,
        "other": NEXT_PAGE,
    },
    ge.SWIPE_RIGHT: {
        "presentation": PREV_SLIDE,
        "pdf": PREV_PAGE,
        "office": PREV_PAGE,
        "media": PREV_TRACK,
        "browser": GO_BACK,
        "imaging": PREV_DIAGNOSTIC,
        "other": PREV_PAGE,
    },
    ge.SWIPE_UP: {
        "presentation": PREV_SLIDE,
        "pdf": PREV_PAGE,
        "media": VOLUME_UP,
        "browser": NEXT_TAB,
        "imaging": ZOOM_IN,
        "other": SCROLL,
    },
    ge.SWIPE_DOWN: {
        "presentation": NEXT_SLIDE,
        "pdf": NEXT_PAGE,
        "media": VOLUME_DOWN,
        "browser": PREV_TAB,
        "imaging": ZOOM_OUT,
        "other": SCROLL,
    },
    ge.CIRCLE_CW: {
        "media": VOLUME_UP,
        "imaging": ROTATE_3D,
        "pdf": ZOOM_IN,
        "presentation": "LASER_POINTER",
        "other": ZOOM_IN,
    },
    ge.CIRCLE_CCW: {
        "media": VOLUME_DOWN,
        "imaging": ROTATE_3D,
        "pdf": ZOOM_OUT,
        "presentation": "LASER_POINTER",
        "other": ZOOM_OUT,
    },
    ge.PALM_HOLD: {
        "presentation": "PAUSE_PRESENTATION",
        "other": PAUSE_INTERACTION,
    },
}


# Voice intent -> action (1:1 with context-free mapping)
VOICE_ACTIONS: dict[str, str] = {
    vc.OPEN_APP: OPEN_APP,
    vc.CLOSE_WINDOW: CLOSE_WINDOW,
    vc.MINIMIZE: MINIMIZE,
    vc.MAXIMIZE: MAXIMIZE,
    vc.SWITCH_APP: SWITCH_WINDOW,
    vc.SHOW_DESKTOP: SHOW_DESKTOP,
    vc.SCROLL_UP: SCROLL,
    vc.SCROLL_DOWN: SCROLL,
    vc.VOLUME_UP: VOLUME_UP,
    vc.VOLUME_DOWN: VOLUME_DOWN,
    vc.VOLUME_SET: VOLUME_SET,
    vc.MUTE: MUTE,
    vc.UNMUTE: UNMUTE,
    vc.PLAY_PAUSE: PLAY_PAUSE,
    vc.NEXT_TRACK: NEXT_TRACK,
    vc.PREV_TRACK: PREV_TRACK,
    vc.STOP_MEDIA: STOP_MEDIA,
    vc.NEXT_SLIDE: NEXT_SLIDE,
    vc.PREV_SLIDE: PREV_SLIDE,
    vc.START_PRESENTATION: START_PRESENTATION,
    vc.END_PRESENTATION: END_PRESENTATION,
    vc.BLACK_SCREEN: BLACK_SCREEN,
    vc.NEXT_PAGE: NEXT_PAGE,
    vc.PREV_PAGE: PREV_PAGE,
    vc.GO_BACK: GO_BACK,
    vc.GO_FORWARD: GO_FORWARD,
    vc.ZOOM_IN: ZOOM_IN,
    vc.ZOOM_OUT: ZOOM_OUT,
    vc.COPY: COPY,
    vc.PASTE: PASTE,
    vc.CUT: CUT,
    vc.UNDO: UNDO,
    vc.SELECT_ALL: SELECT_ALL,
    vc.PRESS_ENTER: PRESS_ENTER,
    vc.TAB_KEY: TAB_KEY,
    vc.TYPE_TEXT: TYPE_TEXT,
    vc.SCREENSHOT: SCREENSHOT,
    vc.NEXT_TAB: NEXT_TAB,
    vc.PREV_TAB: PREV_TAB,
    vc.CLOSE_TAB: CLOSE_TAB,
    vc.NEW_TAB: NEW_TAB,
    vc.REFRESH: REFRESH,
    vc.FIND: FIND,
    vc.OPEN_SETTINGS: OPEN_SETTINGS,
    vc.PAUSE_CONTROL: PAUSE_CONTROL,
    vc.RESUME_CONTROL: RESUME_CONTROL,
    vc.EMERGENCY_STOP: EMERGENCY_STOP,
    vc.HANDS_BUSY_ON: HANDS_BUSY_ON,
    vc.HANDS_BUSY_OFF: HANDS_BUSY_OFF,
    vc.CALIBRATE: CALIBRATE,
    vc.TOGGLE_KEYBOARD: TOGGLE_KEYBOARD,
    vc.SHOW_UI: SHOW_UI,
    vc.HIDE_UI: HIDE_UI,
    vc.HELP: HELP,
    vc.PROFILE: PROFILE_SWITCH,
    vc.COPILOT: COPILOT,
}

# Voice scroll direction parameter
VOICE_SCROLL_DIRECTION = {"up": -1, "down": 1}


class IntentEngine:
    def __init__(self):
        self.last: Optional[Intent] = None

    # ---- gesture → intent ---------------------------------------------------
    def from_gesture(self, event: ge.GestureEvent,
                     context: ApplicationContext) -> Optional[Intent]:
        mapping = GESTURE_ACTIONS.get(event.kind)
        if not mapping:
            return None
        action = mapping.get(context.category, mapping.get("other"))
        if action is None or action == "NOOP":
            return None
        self.last = Intent(
            action=action,
            params={"event": event.kind, "x": event.x, "y": event.y,
                    "amount": event.amount},
            confidence=min(1.0, 0.6 + event.confidence),
            source="gesture",
            description=f"{event.gesture} → {action} (context: {context.description})",
        )
        return self.last

    # ---- voice → intent -------------------------------------------------------
    def from_voice(self, vi: vc.VoiceIntent, context: ApplicationContext) -> Optional[Intent]:
        if vi.intent == vc.NONE_INTENT:
            return None
        action = VOICE_ACTIONS.get(vi.intent)
        if action is None:
            return None
        params = dict(vi.params)
        if vi.intent == vc.SCROLL_UP:
            params["direction"] = -1
        elif vi.intent == vc.SCROLL_DOWN:
            params["direction"] = 1
        params["language"] = vi.language
        self.last = Intent(
            action=action,
            params=params,
            confidence=vi.confidence,
            source="voice",
            description=f"Voice: {vi.raw_text!r} → {action}",
            # Voice-close actions ask first. Emergency touches safety paths in
            # the app core that force confirmation off; this flag only marks.
            needs_confirmation=action in SENSITIVE_ACTIONS,
        )
        return self.last

    # ---- profile-based remap ------------------------------------------------
    def remap_for_profile(self, intent: Intent, profile_gesture_map: dict[str, str] | None) -> Intent:
        """Let a profile override the context mapping for a gesture intent."""
        if profile_gesture_map and intent.source == "gesture":
            key = intent.params.get("event")
            override = profile_gesture_map.get(key)
            if override:
                intent.action = override
                intent.description = f"Profile override: {key} → {override}"
        return intent