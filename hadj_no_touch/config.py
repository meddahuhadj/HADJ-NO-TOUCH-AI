"""Application configuration.

A single settings object saved as JSON in the per-user data directory.
Everything is local: no cloud processing, no network dependency.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path

APP_DIR_NAME = "HadjNoTouchAI"


def data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_config_path() -> Path:
    return data_dir() / "config.json"


@dataclass
class CameraSettings:
    index: int = 0
    width: int = 640
    height: int = 480
    target_fps: int = 30
    auto_retry: bool = True


@dataclass
class TrackingSettings:
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    max_hands: int = 2
    model_complexity: int = 1
    processing_fps: int = 30
    gaze_enabled: bool = True
    gaze_every_n_frames: int = 5


@dataclass
class GestureSettings:
    # Pinch (left click) thresholds
    pinch_distance_ratio: float = 0.42
    pinch_dwell_click_ms: int = 220
    pinch_double_click_window_ms: int = 420
    pinch_hold_drag_ms: int = 650
    # Right click (thumb + middle)
    pinch_middle_distance_ratio: float = 0.42
    # Confidence / robustness
    gesture_confidence: float = 0.55
    min_gesture_duration_ms: int = 120
    gesture_debounce_ms: int = 60
    gesture_cooldown_ms: int = 300
    scroll_gesture_cooldown_ms: int = 60
    # Movement
    scroll_velocity_threshold: float = 0.012
    swipe_distance: float = 0.18
    max_cursor_jump_ratio: float = 0.18
    # Pause / lock
    palm_hold_ms: int = 1400
    fist_lock_ms: int = 800


@dataclass
class CursorSettings:
    enabled: bool = True
    smoothing: float = 0.35
    speed: float = 1.0
    dead_zone: float = 0.015
    large_cursor: bool = False
    left_handed: bool = False
    gaze_gate_clicks: bool = False


@dataclass
class VoiceSettings:
    enabled: bool = True
    language: str = "en-US"
    engine: str = "google"
    continuous: bool = True
    push_to_talk: bool = False
    vosk_model_path: str = ""


@dataclass
class PrivacySettings:
    local_processing_only: bool = True
    record_frames: bool = False
    blur_faces: bool = False
    activity_log_enabled: bool = True


@dataclass
class HeadSettings:
    enabled: bool = False
    sensitivity: float = 0.12
    hold_ms: int = 300
    cooldown_ms: int = 900


@dataclass
class SafetySettings:
    confirmation_level: str = "smart"  # none | smart | all
    # empty = everything registered is allowed; a non-empty list restricts.
    allowed_actions: list = field(default_factory=list)


@dataclass
class DemoSettings:
    start_in_demo: bool = False
    show_demo_badge: bool = True


@dataclass
class Settings:
    camera: CameraSettings = field(default_factory=CameraSettings)
    tracking: TrackingSettings = field(default_factory=TrackingSettings)
    gestures: GestureSettings = field(default_factory=GestureSettings)
    cursor: CursorSettings = field(default_factory=CursorSettings)
    voice: VoiceSettings = field(default_factory=VoiceSettings)
    privacy: PrivacySettings = field(default_factory=PrivacySettings)
    head: HeadSettings = field(default_factory=HeadSettings)
    safety: SafetySettings = field(default_factory=SafetySettings)
    demo: DemoSettings = field(default_factory=DemoSettings)

    active_profile: str = "personal"
    auto_switch_profile: bool = True
    calibration_points: list = field(default_factory=list)

    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def load(self, path: Path | None = None) -> "Settings":
        with self._lock:
            p = path or default_config_path()
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    for key in ("camera", "tracking", "gestures", "cursor",
                                "voice", "privacy", "head", "safety", "demo"):
                        blk = type(getattr(self, key))()
                        sub = data.pop(key, {})
                        sub_data = getattr(self, key)
                        for f in sub_data.__dataclass_fields__:
                            if f in sub:
                                setattr(sub_data, f, sub[f])
                        setattr(self, key, sub_data)
                    for f in self.__dataclass_fields__:
                        if f not in ("_lock",) and f in data:
                            setattr(self, f, data[f])
                except Exception:
                    # Corrupt config: fall back to defaults.
                    pass
            return self

    def save(self, path: Path | None = None) -> None:
        with self._lock:
            p = path or default_config_path()
            p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def to_dict(self) -> dict:
        import dataclasses
        d = {}
        for f in dataclasses.fields(self):
            if f.name == "_lock":
                continue
            val = getattr(self, f.name)
            if dataclasses.is_dataclass(val):
                val = dataclasses.asdict(val)
            elif isinstance(val, list):
                val = list(val)
            d[f.name] = val
        return d


SETTINGS = Settings()