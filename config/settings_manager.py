import json
import os
import copy
import threading
from typing import Any, Dict, Callable, List

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "default_config.json")
USER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "user_settings.json")


class SettingsManager:
    """Manages application settings, persistence, and reactive updates."""

    _instance = None
    AUTOSAVE_DELAY: float = 0.75

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._config: Dict[str, Any] = self._load_defaults()
        # Batched writes. Applying a calibration report touches a dozen keys in
        # a row, and one JSON dump per key meant a dozen disk writes for a single
        # user action. Writes are now coalesced and flushed by flush() or by
        # save(), so nothing is lost on an orderly shutdown.
        self._dirty: bool = False
        self._autosave_timer = threading.Timer(self.AUTOSAVE_DELAY, self._autosave_flush)
        self._autosave_timer.daemon = True
        self.load()

    def _load_defaults(self) -> Dict[str, Any]:
        if os.path.exists(DEFAULT_CONFIG_PATH):
            with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def load(self) -> Dict[str, Any]:
        """Loads user settings merged on top of defaults."""
        self._config = self._load_defaults()
        if os.path.exists(USER_CONFIG_PATH):
            try:
                with open(USER_CONFIG_PATH, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                    self._deep_merge(self._config, user_data)
            except Exception as e:
                print(f"[SettingsManager] Error loading user settings: {e}")
        return self._config

    def save(self) -> bool:
        """Persists current configuration to user_settings.json immediately."""
        try:
            with open(USER_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            self._dirty = False
            self._notify_listeners()
            return True
        except Exception as e:
            print(f"[SettingsManager] Error saving user settings: {e}")
            return False

    def flush(self) -> bool:
        """
        Writes only if something changed since the last save.

        Call this on shutdown: set() defers its disk write, so without an
        explicit flush a setting changed in the last fraction of a second
        before exit would be lost.
        """
        if not self._dirty:
            return True
        return self.save()

    def _autosave_flush(self) -> None:
        """Timer callback that performs the deferred write."""
        try:
            if self._dirty:
                self.save()
        except Exception as e:
            print(f"[SettingsManager] Deferred save failed: {e}")

    def _schedule_autosave(self) -> None:
        """Restarts the coalescing timer on every write."""
        self._dirty = True
        if self._autosave_timer.is_alive():
            self._autosave_timer.cancel()
        self._autosave_timer = threading.Timer(self.AUTOSAVE_DELAY, self._autosave_flush)
        self._autosave_timer.daemon = True
        self._autosave_timer.start()

    def get(self, key_path: str, default: Any = None) -> Any:
        """Retrieves a nested setting value using dot notation (e.g. 'gestures.cursor_speed')."""
        keys = key_path.split(".")
        val = self._config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key_path: str, value: Any, auto_save: bool = True) -> None:
        """Sets a nested setting value using dot notation."""
        keys = key_path.split(".")
        d = self._config
        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
        if auto_save:
            self._schedule_autosave()

    def reset_to_defaults(self) -> None:
        """Resets all configuration values to factory defaults."""
        self._config = self._load_defaults()
        if self._autosave_timer.is_alive():
            self._autosave_timer.cancel()
        self._dirty = False
        if os.path.exists(USER_CONFIG_PATH):
            try:
                os.remove(USER_CONFIG_PATH)
            except Exception:
                pass
        self._notify_listeners()

    def add_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self) -> None:
        cfg_copy = copy.deepcopy(self._config)
        for cb in self._listeners:
            try:
                cb(cfg_copy)
            except Exception as e:
                print(f"[SettingsManager] Listener error: {e}")

    def _deep_merge(self, base: dict, overlay: dict) -> None:
        for k, v in overlay.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v

    @property
    def config(self) -> Dict[str, Any]:
        return self._config
