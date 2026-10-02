import time
import psutil
from enum import Enum
from typing import Dict, Any, Optional
from core.event_bus import EventBus, EventType
from config.settings_manager import SettingsManager


class PerformanceProfile(Enum):
    ECO = "ECO"
    BALANCED = "BALANCED"
    PERFORMANCE = "PERFORMANCE"
    AI_MAX = "AI_MAX"


class ProfileManager:
    """Manages resource profiles, throttling FPS and monitoring system metrics."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ProfileManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, event_bus: Optional[EventBus] = None):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.event_bus = event_bus or EventBus()
        self.settings = SettingsManager()

        current_prof_str = self.settings.get("performance.profile", "BALANCED")
        self.current_profile = PerformanceProfile[current_prof_str]

        self.fps_targets = {
            PerformanceProfile.ECO: 15,
            PerformanceProfile.BALANCED: 22,
            PerformanceProfile.PERFORMANCE: 30,
            PerformanceProfile.AI_MAX: 30,
        }

        self.last_frame_time = time.time()
        self.frame_count = 0
        self.current_fps = 0.0
        self.camera_latency_ms = 0.0
        self.voice_latency_ms = 0.0

    def set_profile(self, profile: PerformanceProfile) -> None:
        self.current_profile = profile
        self.settings.set("performance.profile", profile.name)
        self.event_bus.publish(EventType.PROFILE_CHANGED, {"profile": profile.name})

    @property
    def target_fps(self) -> int:
        return self.fps_targets.get(self.current_profile, 22)

    @property
    def frame_interval(self) -> float:
        return 1.0 / max(1, self.target_fps)

    def record_frame(self, latency_ms: float = 0.0) -> None:
        self.frame_count += 1
        now = time.time()
        self.camera_latency_ms = latency_ms
        elapsed = now - self.last_frame_time
        if elapsed >= 1.0:
            self.current_fps = round(self.frame_count / elapsed, 1)
            self.frame_count = 0
            self.last_frame_time = now

    def record_voice_latency(self, latency_ms: float) -> None:
        self.voice_latency_ms = round(latency_ms, 1)

    def check_cpu_throttle(self) -> bool:
        """
        If auto_eco is enabled (default True) and CPU exceeds 80%, throttles down to ECO.
        Returns True if a throttling switch occurred.
        """
        if self.settings.get("performance.auto_eco", True):
            try:
                cpu = psutil.cpu_percent(interval=None)
                if cpu > 80.0 and self.current_profile != PerformanceProfile.ECO:
                    self.set_profile(PerformanceProfile.ECO)
                    return True
            except Exception:
                pass
        return False

    def get_system_stats(self) -> Dict[str, Any]:
        """Collects live CPU, RAM, FPS, and latency metrics."""
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        return {
            "profile": self.current_profile.name,
            "fps": self.current_fps,
            "target_fps": self.target_fps,
            "camera_latency_ms": round(self.camera_latency_ms, 1),
            "voice_latency_ms": round(self.voice_latency_ms, 1),
            "cpu_percent": cpu,
            "ram_percent": ram
        }
