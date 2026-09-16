"""HADJ Performance & Environment Quality.

PerformanceMonitor keeps real, measured numbers about the pipeline
(frame rate, processing latency, gesture/voice latency, commands per minute)
so the dashboard can show the actual health of the system.

EnvironmentQuality estimates lighting / contrast from the camera frame with
OpenCV -- it is an estimate, clearly labelled as such, not a marketing claim.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field


class PerformanceMonitor:
    # A click landing within this normalized distance of the pinch anchor is
    # "clean" — the practical definition of click precision used below.
    CLEAN_DRIFT = 0.12

    def __init__(self, maxlen: int = 120) -> None:
        self._frame_ms = deque(maxlen=maxlen)
        self._gesture_latency = deque(maxlen=maxlen)
        self._voice_latency = deque(maxlen=maxlen)
        self._command_times: deque[float] = deque(maxlen=400)
        self._false_triggers = 0
        self._clicks = 0
        self._clicks_clean = 0
        self._click_drift_sum = 0.0
        self._lock = threading.RLock()
        self._best_fps = 0.0

    def note_frame(self, processing_ms: float) -> None:
        with self._lock:
            self._frame_ms.append(float(processing_ms))

    def note_gesture(self, latency_ms: float) -> None:
        with self._lock:
            self._gesture_latency.append(float(latency_ms))

    def note_voice(self, latency_ms: float) -> None:
        with self._lock:
            self._voice_latency.append(float(latency_ms))

    def note_command(self) -> None:
        with self._lock:
            self._command_times.append(time.monotonic())

    def note_false_trigger(self) -> None:
        with self._lock:
            self._false_triggers += 1

    def note_click(self, drift_norm: float) -> None:
        """Record a delivered click and how far it drifted from the pinch
        anchor (0..1 normalized screen units). Drift is the honest proxy
        for click precision."""
        with self._lock:
            self._clicks += 1
            self._click_drift_sum += float(drift_norm)
            if float(drift_norm) <= self.CLEAN_DRIFT:
                self._clicks_clean += 1

    def reset_counters(self) -> None:
        with self._lock:
            self._false_triggers = 0
            self._clicks = 0
            self._clicks_clean = 0
            self._click_drift_sum = 0.0

    def _avg(self, q: deque[float]) -> float | None:
        return round(sum(q) / len(q), 1) if q else None

    def snapshot(self) -> dict:
        with self._lock:
            items = list(self._command_times)
            now = time.monotonic()
            window = [t for t in items if now - t <= 60.0]
            if self._frame_ms:
                frames = list(self._frame_ms)
                avg_ms = sum(frames) / len(frames)
                fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
                best_fps = 1000.0 / min(frames) if min(frames) > 0 else 0.0
            else:
                avg_ms = fps = best_fps = 0.0
            return {
                "fps": round(fps, 1),
                "best_fps": round(max(best_fps, self._best_fps), 1),
                "frame_ms": round(avg_ms, 1),
                "frame_samples": len(self._frame_ms),
                "gesture_latency_ms": self._avg(self._gesture_latency),
                "voice_latency_ms": self._avg(self._voice_latency),
                "commands_per_minute": round(len(window), 1),
                "false_triggers": self._false_triggers,
                "clicks": self._clicks,
                "clicks_clean": self._clicks_clean,
                "click_drift_avg":
                    round(self._click_drift_sum / self._clicks, 3) if self._clicks else None,
                "click_precision":
                    round(self._clicks_clean / self._clicks, 3) if self._clicks else None,
            }


@dataclass
class EnvironmentReport:
    brightness: float = 0.0          # 0..1 (mean gray)
    contrast: float = 0.0            # 0..1 (normalised std)
    lighting: str = "unknown"        # dark / low / good / bright
    face_visible: bool = False
    recommendation: str = ""
    estimated: bool = True           # honesty marker: always a real estimate

    def as_dict(self) -> dict:
        return {
            "brightness": round(self.brightness, 3),
            "contrast": round(self.contrast, 3),
            "lighting": self.lighting,
            "face_visible": self.face_visible,
            "recommendation": self.recommendation,
            "estimated": self.estimated,
        }


class EnvironmentQuality:
    """Estimate usable lighting/visibility from a raw camera frame (BGR)."""

    def estimate(self, frame_bgr) -> EnvironmentReport | None:
        if frame_bgr is None:
            return None
        try:
            import cv2
        except ImportError:
            return None
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        mean = float(frame_gray.mean())
        std = float(frame_gray.std())
        brightness = min(1.0, mean / 255.0)
        contrast = min(1.0, std / 128.0)
        if brightness < 0.12:
            lighting, rec = "dark", "Light is too low: move to a well-lit area."
        elif brightness < 0.3:
            lighting, rec = "low", "Lighting is dim: increase the light."
        elif brightness > 0.92:
            lighting, rec = "bright", "Very bright: reduce glare / backlight."
        else:
            lighting = "good"
            rec = "Good lighting."
        if contrast < 0.05:
            rec = "Flat frame: add contrast or face the light."
        return EnvironmentReport(
            brightness=brightness,
            contrast=contrast,
            lighting=lighting,
            recommendation=rec,
        )