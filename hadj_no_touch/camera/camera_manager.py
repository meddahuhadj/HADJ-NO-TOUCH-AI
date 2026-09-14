"""Threaded webcam acquisition on a background thread with frame skipping.

Frames are grabbed in a loop and the latest one is made available to
consumers. The frame is never stored or uploaded.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..config import CameraSettings, SETTINGS
from ..logging_setup import get_logger

log = get_logger("camera.manager")

try:
    import cv2
    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False

# Brightness (mean pixel value, 0-255) below which a captured frame is
# considered black/useless (privacy shutter, broken driver mode, ...).
_DARK_FRAME_THRESHOLD = 8.0


class CameraError(RuntimeError):
    pass


@dataclass
class Frame:
    bgr: np.ndarray
    grabbed_at: float
    index: int = 0


class CameraManager:
    """Owns a cv2.VideoCapture and reads frames on a dedicated thread."""

    def __init__(self, settings: CameraSettings | None = None):
        self.settings = settings or SETTINGS.camera
        self._cap = None
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._lock = threading.Lock()
        self._frame: Optional[Frame] = None
        self._last_read = 0.0
        self._frame_counter = 0
        self._fps = 0.0
        self.error: Optional[str] = None
        self.callback = None  # callable(Frame) invoked per delivered frame

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def is_running(self) -> bool:
        return self._running.is_set() and self._cap is not None

    # ---- lifecycle ---------------------------------------------------------
    @staticmethod
    def _default_backends() -> list[int]:
        """Prefer MediaFoundation on Windows (most compatible with modern webcams)."""
        if os.name == "nt":
            return [cv2.CAP_MSMF, cv2.CAP_DSHOW]
        return [cv2.CAP_MSMF, 0]

    def _try_open(self, index: int, first: int | None = None) -> Optional[object]:
        backends = self._default_backends()
        if first is not None:
            backends = [first] + [b for b in backends if b != first]
        for backend in backends:
            try:
                cap = cv2.VideoCapture(index, backend)
            except Exception:
                continue
            if cap is not None and cap.isOpened():
                return cap
        return None

    @staticmethod
    def _probe_brightness(cap, frames: int = 6) -> float:
        """Average mean-brightness of a few freshly read frames (0-255)."""
        total, count = 0.0, 0
        for _ in range(frames):
            ok, frame = cap.read()
            if ok and frame is not None:
                total += float(frame.mean())
                count += 1
            else:
                time.sleep(0.05)
        return total / count if count else 0.0

    @staticmethod
    def _apply_exposure(cap) -> None:
        """Best-effort exposure / brightness boost for dark webcams."""
        try:
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
            cap.set(cv2.CAP_PROP_AUTO_WB, 1.0)
            cap.set(cv2.CAP_PROP_GAIN, 200)
            cap.set(cv2.CAP_PROP_BRIGHTNESS, 150)
        except Exception:
            pass

    def open(self, index: int | None = None) -> bool:
        if not HAVE_CV2:
            self.error = "OpenCV not installed"
            return False
        idx = self.settings.index if index is None else index

        cap = self._try_open(idx)
        if cap is None:
            self.error = f"Camera {idx} could not be opened. Is it in use elsewhere?"
            return False

        # Apply requested resolution (if any) on MediaFoundation first; some
        # cameras deliver pure black frames when a low resolution is forced.
        requested = self.settings.width > 0 and self.settings.height > 0
        if requested:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.height)
        cap.set(cv2.CAP_PROP_FPS, self.settings.target_fps)
        self._apply_exposure(cap)

        # Self-heal: if the forced resolution yields dark frames, reopen at the
        # camera's native resolution.
        if requested and self._probe_brightness(cap) < _DARK_FRAME_THRESHOLD:
            native = self._try_open(idx)
            if native is not None:
                native.set(cv2.CAP_PROP_FPS, self.settings.target_fps)
                self._apply_exposure(native)
                if self._probe_brightness(native) >= _DARK_FRAME_THRESHOLD:
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = native
                else:
                    try:
                        native.release()
                    except Exception:
                        pass

        self._cap = cap
        self.error = None
        return True

    def start(self, index: int | None = None) -> bool:
        if not self.open(index):
            return False
        self._running.set()
        self._thread = threading.Thread(target=self._run, name="camera-capture", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running.clear()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None

    def read(self) -> Optional[Frame]:
        """Return the most recent frame, or None."""
        with self._lock:
            return self._frame

    # ---- internals ---------------------------------------------------------
    def _run(self) -> None:
        frame_interval = 1.0 / max(1, self.settings.target_fps)
        next_t = time.monotonic()
        fail_streak = 0
        idx = self.settings.index
        while self._running.is_set():
            now = time.monotonic()
            if now < next_t - 0.001:
                time.sleep(max(0.0, next_t - now - 0.001))
            t0 = time.monotonic()
            ok, frame = self._cap.read()
            if not ok or frame is None:
                self.handle_read_error()
                fail_streak += 1
                if fail_streak >= 30:  # ~4 s of continuous failures
                    fail_streak = 0
                    log.warning("camera stuck: reopening capture device %s", idx)
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                    try:
                        self._cap = self._try_open(idx)
                    except Exception:
                        self._cap = None
                    if self._cap is not None:
                        self._apply_exposure(self._cap)
                continue
            fail_streak = 0
            frame = cv2.flip(frame, 1)
            with self._lock:
                self._frame = Frame(bgr=frame, grabbed_at=t0, index=self._frame_counter)
                self._frame_counter += 1
                prev = self._last_read
                self._last_read = t0
                if prev:
                    self._fps = 0.9 * self._fps + 0.1 * (1.0 / max(0.001, t0 - prev))
            if self.callback:
                try:
                    self.callback(self._frame)
                except Exception as e:
                    log.warning("camera callback error: %s", e)
            next_t = t0 + frame_interval

    def handle_read_error(self) -> None:
        self.error = "Failed to read frame from camera"
        log.warning(self.error)
        time.sleep(0.1)