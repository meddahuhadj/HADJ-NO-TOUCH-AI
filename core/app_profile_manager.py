import time
import threading
from enum import Enum
from typing import Optional, Dict, Any, Tuple
import psutil

from core.event_bus import EventBus, EventType
from core.qt_bridge import QtBridge

try:
    import win32gui
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class AppProfile(Enum):
    BROWSER = "browser"
    MEDIA = "media"
    DOCUMENT = "document"
    DESKTOP = "desktop"


# Known process name lists (lowercase)
BROWSER_PROCESSES = {
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
    "opera.exe", "vivaldi.exe", "arc.exe", "waterfox.exe", "tor.exe"
}

MEDIA_PROCESSES = {
    "vlc.exe", "spotify.exe", "wmplayer.exe", "mpv.exe",
    "potplayer64.exe", "potplayer.exe", "kmplayer.exe",
    "aimp.exe", "foobar2000.exe", "musicbee.exe", "itunes.exe"
}

DOCUMENT_PROCESSES = {
    "acrord32.exe", "acrobat.exe", "foxitpdf.exe", "sumatrapdf.exe",
    "winword.exe", "powerpnt.exe", "excel.exe", "soffice.bin",
    "notepad.exe", "notepad++.exe", "wordpad.exe"
}

# Media indicators in window titles (including web media like YouTube/Spotify/Netflix)
MEDIA_TITLE_KEYWORDS = [
    "youtube", "netflix", "spotify", "soundcloud", "twitch",
    "vlc media player", "disney+", "prime video", "deezer",
    "dailymotion", "podcast", "lecteur windows media"
]

# Document indicators in window titles
DOCUMENT_TITLE_KEYWORDS = [
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    "powerpoint", "word", "acrobat reader", "présentation",
    "presentation", "document", "libreoffice", "adobe acrobat"
]


class AppProfileManager:
    """
    Detects the active foreground Windows application and manages contextual profiles
    (Browser, Media Player, Document/Presentation, Desktop).
    Dispatches context-aware gestures (seek, page switch, history navigation, play/pause).
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(AppProfileManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, check_interval: float = 0.5):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self.event_bus = EventBus()
        self.qt_bridge = QtBridge()
        self.check_interval = check_interval

        self.current_profile: AppProfile = AppProfile.DESKTOP
        self.current_app_name: str = "Explorer"
        self.current_window_title: str = ""
        self.locked_profile: Optional[AppProfile] = None

        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the background active window detection loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="AppProfileMonitor")
        self._thread.start()
        print("[AppProfileManager] Active application detector started.")

    def stop(self):
        self._running = False

    def lock_profile(self, profile: Optional[AppProfile]):
        """Forces a specific profile override (or None to resume auto-detection)."""
        self.locked_profile = profile
        if profile is not None:
            self.current_profile = profile
            self._notify_profile_change()

    def get_active_profile(self) -> AppProfile:
        if self.locked_profile is not None:
            return self.locked_profile
        return self.current_profile

    def get_active_app_info(self) -> Tuple[str, str]:
        """Returns (app_name, window_title)."""
        return self.current_app_name, self.current_window_title

    def detect_foreground_app(self) -> Tuple[AppProfile, str, str]:
        """
        Queries the current active foreground window on Windows using win32 and psutil.
        Returns (AppProfile, process_name, window_title).
        """
        if not HAS_WIN32:
            return AppProfile.DESKTOP, "Desktop", ""

        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return AppProfile.DESKTOP, "Desktop", ""

            title = win32gui.GetWindowText(hwnd) or ""
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if not pid:
                return AppProfile.DESKTOP, "Desktop", title

            try:
                proc = psutil.Process(pid)
                proc_name = proc.name().lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_name = "unknown"

            profile = self._classify_profile(proc_name, title)
            return profile, proc_name, title

        except Exception as e:
            return AppProfile.DESKTOP, "Desktop", ""

    def _classify_profile(self, proc_name: str, title: str) -> AppProfile:
        title_lower = title.lower()

        # 1. Check Media title keywords (even inside browsers, e.g. YouTube in Chrome)
        if any(kw in title_lower for kw in MEDIA_TITLE_KEYWORDS):
            return AppProfile.MEDIA

        # 2. Check dedicated Media Player processes
        if proc_name in MEDIA_PROCESSES:
            return AppProfile.MEDIA

        # 3. Check Document processes & title keywords
        if proc_name in DOCUMENT_PROCESSES or any(kw in title_lower for kw in DOCUMENT_TITLE_KEYWORDS):
            return AppProfile.DOCUMENT

        # 4. Check Browser processes
        if proc_name in BROWSER_PROCESSES:
            return AppProfile.BROWSER

        # 5. Default
        return AppProfile.DESKTOP

    def _monitor_loop(self):
        while self._running:
            try:
                if self.locked_profile is None:
                    profile, proc_name, title = self.detect_foreground_app()
                    if profile != self.current_profile or proc_name != self.current_app_name:
                        self.current_profile = profile
                        self.current_app_name = proc_name
                        self.current_window_title = title
                        self._notify_profile_change()
            except Exception as e:
                pass
            time.sleep(self.check_interval)

    def _notify_profile_change(self):
        profile_str = self.current_profile.value
        display_name = self.current_app_name.replace(".exe", "").capitalize()
        # Emit to Qt GUI
        self.qt_bridge.app_profile_changed.emit(profile_str, display_name)
        # Publish to Event Bus
        self.event_bus.publish(EventType.APP_PROFILE_CHANGED, {
            "profile": profile_str,
            "app_name": self.current_app_name,
            "title": self.current_window_title
        })

    def get_contextual_action(self, gesture_name: str) -> Optional[Dict[str, Any]]:
        """
        Returns the mapped contextual action, key to press, and i18n label key
        for the given gesture and active profile.
        """
        profile = self.get_active_profile()

        if gesture_name == "SWIPE_LEFT":
            if profile == AppProfile.BROWSER:
                return {"action": "NAV_BACK", "key": "alt+left", "label_key": "profile.action.browser_back"}
            elif profile == AppProfile.MEDIA:
                return {"action": "SEEK_BACK", "key": "left", "label_key": "profile.action.media_seek_back"}
            elif profile == AppProfile.DOCUMENT:
                return {"action": "PAGE_PREV", "key": "pageup", "label_key": "profile.action.doc_page_prev"}
            else:
                return {"action": "NAV_BACK", "key": "alt+left", "label_key": "profile.action.browser_back"}

        elif gesture_name == "SWIPE_RIGHT":
            if profile == AppProfile.BROWSER:
                return {"action": "NAV_FORWARD", "key": "alt+right", "label_key": "profile.action.browser_forward"}
            elif profile == AppProfile.MEDIA:
                return {"action": "SEEK_FORWARD", "key": "right", "label_key": "profile.action.media_seek_forward"}
            elif profile == AppProfile.DOCUMENT:
                return {"action": "PAGE_NEXT", "key": "pagedown", "label_key": "profile.action.doc_page_next"}
            else:
                return {"action": "NAV_FORWARD", "key": "alt+right", "label_key": "profile.action.browser_forward"}

        elif gesture_name == "PINCH":
            if profile == AppProfile.MEDIA:
                return {"action": "PLAY_PAUSE", "key": "space", "label_key": "profile.action.media_play_pause"}
            else:
                return {"action": "CLICK", "key": "click", "label_key": "profile.action.click"}

        return None
