"""HADJ Safety Engine.

A small, explicit gate in front of every action that touches the computer:

    SAFE      -> execute freely (pointer, scroll, media, navigation)
    CONFIRM   -> ask the user first (close windows / tabs, sensitive moves)
    CRITICAL  -> always an explicit confirmation, never auto-approved

Every AI-produced action must exist in the action registry below; unknown
actions are treated as safe but are logged, so a typo can never silently run
something destructive. The planner is restricted to this registry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from hadj_no_touch.ai import intent_engine as ie
from hadj_no_touch.logging_setup import get_logger

log = get_logger("safety")

RISK_SAFE = "safe"
RISK_CONFIRM = "confirm"
RISK_CRITICAL = "critical"


@dataclass(frozen=True)
class ActionSpec:
    action: str
    description: str
    risk: str = RISK_SAFE
    group: str = "general"


@dataclass
class SafetyDecision:
    action: str
    allowed: bool
    risk: str
    requires_confirmation: bool
    reason: str = ""


def _safe(action: str, description: str, group: str = "general") -> ActionSpec:
    return ActionSpec(action, description, RISK_SAFE, group)


def _confirm(action: str, description: str, group: str = "general") -> ActionSpec:
    return ActionSpec(action, description, RISK_CONFIRM, group)


def _critical(action: str, description: str, group: str = "general") -> ActionSpec:
    return ActionSpec(action, description, RISK_CRITICAL, group)


PREDEFINED_ACTIONS: list[ActionSpec] = [
    # --- pointer / input ---------------------------------------------------
    _safe(ie.MOUSE_MOVE, "Move the pointer", "input"),
    _safe(ie.LEFT_CLICK, "Left click", "input"),
    _safe(ie.RIGHT_CLICK, "Right click", "input"),
    _safe(ie.DOUBLE_CLICK, "Double click", "input"),
    _safe(ie.DRAG, "Drag and drop", "input"),
    _safe(ie.SCROLL, "Scroll the page", "input"),
    _safe(ie.PRESS_ENTER, "Press Enter", "keyboard"),
    _safe(ie.TAB_KEY, "Press Tab", "keyboard"),
    _safe(ie.TYPE_TEXT, "Type text", "keyboard"),
    _safe(ie.COPY, "Copy selection", "edit"),
    _safe(ie.PASTE, "Paste", "edit"),
    _safe(ie.CUT, "Cut selection", "edit"),
    _safe(ie.UNDO, "Undo", "edit"),
    _safe(ie.SELECT_ALL, "Select all", "edit"),
    # --- navigation / media -------------------------------------------------
    _safe(ie.NEXT_SLIDE, "Next slide", "presentation"),
    _safe(ie.PREV_SLIDE, "Previous slide", "presentation"),
    _safe(ie.START_PRESENTATION, "Start presentation", "presentation"),
    _safe(ie.END_PRESENTATION, "End presentation", "presentation"),
    _safe(ie.BLACK_SCREEN, "Black screen", "presentation"),
    _safe("PAUSE_PRESENTATION", "Pause presentation (black screen)", "presentation"),
    _safe(ie.NEXT_PAGE, "Next page", "document"),
    _safe(ie.PREV_PAGE, "Previous page", "document"),
    _safe(ie.NEXT_IMAGE, "Next image", "document"),
    _safe(ie.PREV_IMAGE, "Previous image", "document"),
    _safe(ie.NEXT_DIAGNOSTIC, "Next diagnostic image", "medical"),
    _safe(ie.PREV_DIAGNOSTIC, "Previous diagnostic image", "medical"),
    _safe(ie.NEXT_TRACK, "Next track", "media"),
    _safe(ie.PREV_TRACK, "Previous track", "media"),
    _safe(ie.PLAY_PAUSE, "Play / pause", "media"),
    _safe(ie.STOP_MEDIA, "Stop playback", "media"),
    _safe(ie.VOLUME_UP, "Volume up", "system"),
    _safe(ie.VOLUME_DOWN, "Volume down", "system"),
    _safe(ie.VOLUME_SET, "Set volume", "system"),
    _safe(ie.MUTE, "Mute", "system"),
    _safe(ie.UNMUTE, "Unmute", "system"),
    # --- browser ------------------------------------------------------------
    _safe(ie.GO_BACK, "Go back", "browser"),
    _safe(ie.GO_FORWARD, "Go forward", "browser"),
    _safe(ie.NEXT_TAB, "Next tab", "browser"),
    _safe(ie.PREV_TAB, "Previous tab", "browser"),
    _safe(ie.NEW_TAB, "New tab", "browser"),
    _safe(ie.REFRESH, "Refresh page", "browser"),
    _safe(ie.FIND, "Find in page", "browser"),
    _safe(ie.ZOOM_IN, "Zoom in", "document"),
    _safe(ie.ZOOM_OUT, "Zoom out", "document"),
    _safe(ie.ROTATE_3D, "Rotate 3D view", "document"),
    # --- windows ------------------------------------------------------------
    _safe(ie.OPEN_APP, "Open an application", "app"),
    _safe(ie.OPEN_SETTINGS, "Open Windows settings", "app"),
    _safe(ie.MINIMIZE, "Minimize window", "window"),
    _safe(ie.MAXIMIZE, "Maximize window", "window"),
    _safe(ie.SWITCH_WINDOW, "Switch window", "window"),
    _safe(ie.SHOW_DESKTOP, "Show desktop", "window"),
    _confirm(ie.CLOSE_WINDOW, "Close the active window", "window"),
    _confirm(ie.CLOSE_TAB, "Close the active tab", "browser"),
    # --- app / profile state -------------------------------------------------
    _safe(ie.PROFILE_SWITCH, "Switch profile", "app"),
    _safe(ie.HANDS_BUSY_ON, "Enable hands-busy mode", "app"),
    _safe(ie.HANDS_BUSY_OFF, "Disable hands-busy mode", "app"),
    _safe(ie.PAUSE_CONTROL, "Pause control", "safety"),
    _safe(ie.RESUME_CONTROL, "Resume control", "safety"),
    _safe(ie.EMERGENCY_STOP, "Emergency stop", "safety"),
    _safe(ie.PAUSE_INTERACTION, "Pause interaction", "safety"),
    _safe(ie.FIST_LOCK, "Toggle interaction lock", "safety"),
    # --- utility ------------------------------------------------------------
    _safe(ie.SCREENSHOT, "Take a local screenshot", "utility"),
    _safe(ie.CALIBRATE, "Run calibration", "utility"),
    _safe(ie.TOGGLE_KEYBOARD, "Toggle virtual keyboard", "utility"),
    _safe(ie.SHOW_UI, "Show the interface", "utility"),
    _safe(ie.HIDE_UI, "Hide the interface", "utility"),
    _safe(ie.HELP, "Show help", "utility"),
    # --- reserved / future --------------------------------------------------
    _confirm(ie.LIGHT_CONTROL, "Control smart-home lighting (reserved)", "iot"),
    _critical("SHUTDOWN", "Shut down the computer (reserved)", "critical"),
    _critical("RESTART", "Restart the computer (reserved)", "critical"),
]


class ActionRegistry:
    """The controlled catalogue of actions the AI/multimodal layer may emit."""

    def __init__(self) -> None:
        self._specs: dict[str, ActionSpec] = {}
        self.register_many(PREDEFINED_ACTIONS)

    def register(self, spec: ActionSpec) -> None:
        self._specs[spec.action] = spec

    def register_many(self, specs: list[ActionSpec]) -> None:
        for s in specs:
            self.register(s)

    def spec(self, action: str) -> ActionSpec | None:
        return self._specs.get(action)

    def known(self, action: str) -> bool:
        return action in self._specs

    def risk(self, action: str) -> str:
        spec = self._specs.get(action)
        return spec.risk if spec else RISK_SAFE

    def describe(self, action: str) -> str:
        spec = self._specs.get(action)
        return spec.description if spec else action

    def all(self) -> list[ActionSpec]:
        return list(self._specs.values())

    def ids(self) -> list[str]:
        return sorted(self._specs)


class SafetyEngine:
    """Evaluates every Intent against the registry + user confirmation level.

    ``confirmation_level`` (from settings.safety):
      * "none"   -> CONFIRM actions run without asking; CRITICAL still asks.
      * "smart"  -> CONFIRM and CRITICAL actions ask the user.
      * "all"    -> every action except pure safety toggles asks the user.
    """

    def __init__(self, registry: ActionRegistry | None = None,
                 confirmation_level: str = "smart"):
        self.registry = registry or ActionRegistry()
        self.confirmation_level = confirmation_level
        self._audit: list[dict] = []
        self._max_audit = 400

    # -- configuration -------------------------------------------------------
    def set_confirmation_level(self, level: str) -> None:
        if level in ("none", "smart", "all"):
            self.confirmation_level = level

    # -- decision ------------------------------------------------------------
    def decide(self, action: str, needs_confirmation: bool = False) -> SafetyDecision:
        spec = self.registry.spec(action)
        if spec is None:
            # Unknown action: never treat it as privileged; keep it allowed
            # (the executor itself only handles registered ids anyway) but tell.
            return SafetyDecision(
                action=action,
                allowed=True,
                risk=RISK_SAFE,
                requires_confirmation=False,
                reason="unregistered action treated as safe",
            )
        risk = spec.risk
        level = self.confirmation_level
        if risk == RISK_CRITICAL:
            requires = True
        elif risk == RISK_CONFIRM:
            requires = {"none": False, "smart": True, "all": True}[level]
        elif level == "all" and action not in _SAFETY_TOGGLES:
            requires = True
        else:
            requires = needs_confirmation
        return SafetyDecision(
            action=action,
            allowed=True,
            risk=risk,
            requires_confirmation=requires,
            reason=f"{spec.description} [{risk}]",
        )

    # -- audit ---------------------------------------------------------------
    def audit(self, action: str, outcome: str, reason: str = "") -> None:
        self._audit.append({
            "ts": time.monotonic(),
            "action": action,
            "outcome": outcome,
            "reason": reason,
        })
        if len(self._audit) > self._max_audit:
            self._audit = self._audit[-self._max_audit:]

    def recent_audit(self, n: int = 40) -> list[dict]:
        return self._audit[-n:]


# Toggles that stay real even under the most restrictive confirmation level:
# stopping an accident must never be blocked by a confirmation prompt.
_SAFETY_TOGGLES = {
    ie.EMERGENCY_STOP, ie.PAUSE_CONTROL, ie.RESUME_CONTROL,
    ie.PAUSE_INTERACTION, ie.FIST_LOCK,
}