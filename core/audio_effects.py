import sys
import threading
import time

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

from config.settings_manager import SettingsManager


class AudioEffects:
    """Provides instant native auditory feedback chimes for touchless interactions without external sound files."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AudioEffects, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.settings = SettingsManager()

    def play_wake_chime(self):
        """Play ascending dual-tone chime when Wake Word is recognized."""
        if not self._is_enabled():
            return

        def _run():
            if HAS_WINSOUND:
                try:
                    winsound.Beep(587, 80)   # D5
                    time.sleep(0.02)
                    winsound.Beep(880, 120)  # A5
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    def play_command_success(self):
        """Play crisp confirmation chime when an action completes successfully."""
        if not self._is_enabled():
            return

        def _run():
            if HAS_WINSOUND:
                try:
                    winsound.Beep(1046, 70)  # C6
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    def play_screenshot_chime(self):
        """Play double shutter chime on screen capture."""
        if not self._is_enabled():
            return

        def _run():
            if HAS_WINSOUND:
                try:
                    winsound.Beep(1200, 45)
                    time.sleep(0.03)
                    winsound.Beep(1400, 60)
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    def play_button_feedback(self):
        """Play discreet micro-click tone on button touch."""
        if not self._is_enabled():
            return

        def _run():
            if HAS_WINSOUND:
                try:
                    winsound.Beep(1350, 25)
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    def play_warning_prompt(self):
        """Play warning tone for security confirmation gates."""
        if not self._is_enabled():
            return

        def _run():
            if HAS_WINSOUND:
                try:
                    winsound.Beep(440, 100)  # A4
                    time.sleep(0.04)
                    winsound.Beep(349, 140)  # F4
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    def play_emergency_chime(self):
        """Play alert buzz when Emergency Stop is activated."""
        if not self._is_enabled():
            return

        def _run():
            if HAS_WINSOUND:
                try:
                    for _ in range(2):
                        winsound.Beep(300, 120)
                        time.sleep(0.05)
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    def _is_enabled(self) -> bool:
        return self.settings.get("system.notification_sounds", True)
