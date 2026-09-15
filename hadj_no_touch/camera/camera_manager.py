"""Threaded webcam acquisition on a background thread with frame skipping.

Frames are grabbed in a loop and the latest one is made available to
consumers. The frame is never stored or uploaded.

Camera selection is resolved at open-time by probing indices until one
actually delivers usable frames (see :mod:`.camera_config`), so a broken
device is skipped instead of showing a black preview.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..config import CameraSettings, SETTINGS
from ..logging_setup import get_logger
from .camera_config import (
    apply_exposure,
    bounded_call,
    is_frame_usable,
    resolve_camera,
    OPEN_TIMEOUT_REAL,
    READ_TIMEOUT,
    _bounded_open,
    _bounded_read,
    _bounded_read_ex,
    _safe_release,
)

log = get_logger("camera.manager")

try:
    import cv2
    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False


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
        self._latest_frame_at = 0.0
        self.error: Optional[str] = None
        self.callback = None  # callable(Frame) invoked per delivered frame

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def is_running(self) -> bool:
        return self._running.is_set() and self._cap is not None

    @property
    def is_healthy(self) -> bool:
        # Green only while frames keep arriving; a camera that stalled (right
        # after a single frame) reads as red so the user sees the truth.
        return (self.is_running
                and self._frame_counter > 0
                and self.error is None
                and (time.monotonic() - self._latest_frame_at) < 2.0)

    # ---- lifecycle ---------------------------------------------------------
    def _configure_cap(self, cap) -> None:
        if cap is None:
            return

        def _do() -> None:
            try:
                if self.settings.width > 0 and self.settings.height > 0:
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.width)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.height)
                cap.set(cv2.CAP_PROP_FPS, self.settings.target_fps)
            except Exception as e:
                log.debug("configure cap properties: %s", e)

        bounded_call(_do, 3.0)

    def _open_with_backend(self, index: int,
                           backend: Optional[int]) -> Optional[object]:
        cap = _bounded_open(index, backend if backend is not None else 0,
                            OPEN_TIMEOUT_REAL)
        if cap is None:
            return None
        self._configure_cap(cap)
        apply_exposure(cap)
        return cap

    def _warm_up(self, cap) -> bool:
        """Confirm the capture delivers usable frames (time-bounded)."""
        if cap is None:
            return False
        apply_exposure(cap)
        for _ in range(4):
            ok, frame = _bounded_read(cap, timeout=READ_TIMEOUT)
            if ok and is_frame_usable(frame):
                return True
            time.sleep(0.1)
        return False

    def open(self, index: int | None = None) -> bool:
        if not HAVE_CV2:
            self.error = "OpenCV not installed"
            return False

        requested = self.settings.index if index is None else index
        resolved, backend = resolve_camera(requested, use_cache=True)
        if resolved < 0:
            self.error = ("No camera detected. Check that the webcam is "
                          "connected and not already in use by another app.")
            return False

        cap = self._open_with_backend(resolved, backend)
        if cap is None:
            self.error = f"Camera {resolved} could not be opened. Is it in use elsewhere?"
            return False

        if not self._warm_up(cap):
            # Some webcams go black only at the forced resolution: reopen at
            # the camera's native resolution before giving up.
            if self.settings.width > 0 or self.settings.height > 0:
                saved_w, saved_h = self.settings.width, self.settings.height
                self.settings.width = self.settings.height = 0
                _safe_release(cap)
                cap = self._open_with_backend(resolved, backend)
                self.settings.width, self.settings.height = saved_w, saved_h
                if cap is not None and self._warm_up(cap):
                    log.info("camera %s: forced resolution rejected, using native", resolved)
                else:
                    _safe_release(cap)
                    cap = None
            else:
                _safe_release(cap)
                cap = None

        if cap is None:
            self.error = (f"Camera {resolved} delivers no usable frames — "
                          "check the privacy shutter and that no other app "
                          "is using the webcam.")
            return False

        self.settings.index = resolved
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
            _safe_release(self._cap)
            self._cap = None

    def read(self) -> Optional[Frame]:
        """Return the most recent frame, or None."""
        with self._lock:
            return self._frame

    # ---- internals ---------------------------------------------------------
    def _reopen(self) -> bool:
        """Re-discover a working camera and swap the capture device.

        Returns True when a new usable capture is in place.
        """
        old = self._cap
        self._cap = None
        _safe_release(old)
        try:
            resolved, backend = resolve_camera(self.settings.index, use_cache=False)
        except Exception as e:
            log.debug("reopen discovery failed: %s", e)
            return False
        if resolved < 0:
            self.error = "Camera unavailable: reconnect the webcam or restart the app."
            return False
        cap = self._open_with_backend(resolved, backend)
        if cap is None or not self._warm_up(cap):
            _safe_release(cap)
            self.error = f"Camera {resolved} could not be reopened."
            return False
        self.settings.index = resolved
        self._cap = cap
        self.error = None
        log.warning("camera reopened on index %s", resolved)
        return True

    def _run(self) -> None:
        frame_interval = 1.0 / max(1, self.settings.target_fps)
        next_t = time.monotonic()
        fail_streak = 0
        last_useful = time.monotonic()
        pending_reader = None
        while self._running.is_set():
            now = time.monotonic()
            if now < next_t - 0.001:
                time.sleep(max(0.0, next_t - now - 0.001))
            t0 = time.monotonic()

            if self._cap is None:
                if not self._reopen():
                    time.sleep(1.0)
                continue

            if pending_reader is not None:
                if pending_reader.is_alive():
                    # The previous read never returned: the driver is wedged.
                    # Reading again on the same capture would overlap and only
                    # makes OpenCV hang harder — reopen from scratch instead.
                    pending_reader = None
                    _safe_release(self._cap)
                    self._cap = None
                    self.error = ("Camera driver stalled while reading — "
                                  "reopening the capture device.")
                    log.warning("camera read stalled; reopening device")
                    if not self._reopen():
                        time.sleep(1.0)
                    continue
                pending_reader = None

            ok, frame, pending_reader = _bounded_read_ex(self._cap, timeout=READ_TIMEOUT)
            if not ok or frame is None:
                self.handle_read_error()
                fail_streak += 1
                if fail_streak >= 30 or t0 - last_useful > 10.0:
                    fail_streak = 0
                    if not self._reopen():
                        time.sleep(1.0)
                continue

            fail_streak = 0
            if is_frame_usable(frame):
                last_useful = t0
            frame = cv2.flip(frame, 1).copy()
            with self._lock:
                self._frame = Frame(bgr=frame, grabbed_at=t0, index=self._frame_counter)
                self._frame_counter += 1
                self._latest_frame_at = t0
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
        now = time.monotonic()
        if not hasattr(self, "_last_error_log") or now - self._last_error_log > 3.0:
            log.warning(self.error)
            self._last_error_log = now
        time.sleep(0.1)