"""Shared runtime status snapshot for the UI."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StatusSnapshot:
    camera_active: bool = False
    hand_tracking_active: bool = False
    tracking_paused: bool = False
    voice_ready: bool = False
    gaze_active: bool = False
    gaze_ready: bool = False
    control_enabled: bool = True
    privacy_mode: bool = False
    emergency: bool = False

    hand_present: bool = False
    hand_confidence: float = 0.0
    gesture: str = "REST"
    gesture_confidence: float = 0.0
    action: str = ""

    cursor_x: float = 0
    cursor_y: float = 0

    fps: float = 0.0
    tracking_fps: float = 0.0
    latency_ms: float = 0.0
    cpu: float = 0.0
    memory_mb: float = 0.0

    active_profile: str = "personal"
    active_app: str = ""
    active_context: str = ""

    voice_status: str = "idle"
    voice_engine: str = ""          # google | vosk | sapi | ""
    audio_online: bool = False      # True → mic audio goes to a cloud service
    last_voice: str = ""
    recognized_text: str = ""
    last_intent: str = ""

    calibration: str = "none"
    multimodal_hint: str = ""

    demo_mode: bool = False
    safety_level: str = "smart"
    head_enabled: bool = False
    laser_mode: bool = False

    lighting: str = "unknown"
    brightness: float = 0.0
    contrast: float = 0.0

    cmd_per_minute: float = 0.0
    gesture_latency_ms: float = 0.0
    voice_latency_ms: float = 0.0
    history_count: int = 0
    click_count: int = 0
    click_precision: float | None = None
    perf: dict = field(default_factory=dict)

    diag: dict = field(default_factory=dict)

    def filled(self) -> "StatusSnapshot":
        return self