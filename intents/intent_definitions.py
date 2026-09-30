from enum import Enum, auto
from dataclasses import dataclass
from typing import Any, Dict, Optional, List


class IntentType(Enum):
    UNKNOWN = auto()

    # Application & Window Control
    LAUNCH_APP = auto()
    CLOSE_WINDOW = auto()
    MINIMIZE_WINDOW = auto()
    MAXIMIZE_WINDOW = auto()
    RESTORE_WINDOW = auto()
    SWITCH_APP = auto()
    SHOW_DESKTOP = auto()

    # File and Folder Control
    OPEN_FOLDER = auto()
    CREATE_FOLDER = auto()
    DELETE_FILE = auto()
    DELETE_FOLDER = auto()
    SEARCH_FILES = auto()
    OPEN_RECENT_FILE = auto()

    # Browser Navigation
    BROWSER_NEW_TAB = auto()
    BROWSER_CLOSE_TAB = auto()
    BROWSER_NEXT_TAB = auto()
    BROWSER_PREV_TAB = auto()
    BROWSER_SEARCH = auto()
    NAVIGATE_BACK = auto()
    NAVIGATE_FORWARD = auto()
    NAVIGATE_REFRESH = auto()
    TOGGLE_FULLSCREEN = auto()

    # System & Media Controls
    VOLUME_UP = auto()
    VOLUME_DOWN = auto()
    VOLUME_MUTE = auto()
    VOLUME_SET = auto()
    MEDIA_PLAY_PAUSE = auto()
    MEDIA_NEXT = auto()
    MEDIA_PREVIOUS = auto()
    BRIGHTNESS_UP = auto()
    BRIGHTNESS_DOWN = auto()
    BRIGHTNESS_SET = auto()
    SCREENSHOT = auto()

    # Clipboard & Editing
    CLIPBOARD_COPY = auto()
    CLIPBOARD_PASTE = auto()
    CLIPBOARD_CUT = auto()
    SELECT_ALL = auto()
    UNDO = auto()
    DICTATION = auto()

    # Scrolling & Motion
    SCROLL_UP = auto()
    SCROLL_DOWN = auto()

    # Window Snapping & Desktops
    SNAP_WINDOW_LEFT = auto()
    SNAP_WINDOW_RIGHT = auto()
    TASK_VIEW = auto()
    NEW_DESKTOP = auto()
    CLOSE_DESKTOP = auto()
    NEXT_DESKTOP = auto()
    PREV_DESKTOP = auto()
    OPEN_TASK_MANAGER = auto()
    EMPTY_RECYCLE_BIN = auto()
    ZOOM_IN = auto()
    ZOOM_OUT = auto()
    ZOOM_RESET = auto()
    REFRESH_SCREEN = auto()
    TOGGLE_KEYBOARD_HUD = auto()

    # Power Management
    SYSTEM_LOCK = auto()
    SYSTEM_RESTART = auto()
    SYSTEM_SHUTDOWN = auto()
    SYSTEM_SLEEP = auto()

    # Vision & Multimodal
    FIND_ELEMENT = auto()
    MULTIMODAL_CLICK_TARGET = auto()
    MULTIMODAL_OPEN_TARGET = auto()

    # Macros & Sequences
    EXECUTE_MACRO = auto()
    COMPOUND_PLAN = auto()


@dataclass
class IntentResult:
    intent_type: IntentType
    target: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    original_text: str = ""
    sub_intents: Optional[List['IntentResult']] = None
