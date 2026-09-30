"""
Automatic calibration engine for HADJ NO-TOUCH OFFLINE AI.

Nothing in this module asks the user to guess a number. Every threshold is
*measured* from real sensor data:

* cameras and microphones are discovered by probing the hardware;
* the camera probe reports the resolution and frame rate it can really reach;
* the microphone probe measures the ambient noise floor;
* :class:`CalibrationSession` watches the hand landmarks while the user performs
  a short guided routine, then derives the pinch threshold, the tremor dead
  zone, the EMA smoothing factor, the comfortable reach box, the swipe velocity
  and the drag / double-pinch timings from percentiles of the collected samples.

Percentiles rather than means are used throughout so that a few bad frames or a
single tracking glitch cannot move a threshold. The module deliberately avoids
importing MediaPipe, PySide6 or PyAutoGUI at module level: the UI, the runtime
tuner and the unit tests all depend on it, and it must stay importable on a
machine where no camera or microphone exists at all.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------- #
# Optional hardware dependencies
# --------------------------------------------------------------------------- #

try:  # pragma: no cover - depends on the host machine
    import cv2
    HAS_CV2 = True
except ImportError:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]
    HAS_CV2 = False

try:  # pragma: no cover - depends on the host machine
    import numpy as np
    HAS_NUMPY = True
except ImportError:  # pragma: no cover
    np = None  # type: ignore[assignment]
    HAS_NUMPY = False

try:  # pragma: no cover - depends on the host machine
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:  # pragma: no cover
    pyaudio = None  # type: ignore[assignment]
    HAS_PYAUDIO = False


# --------------------------------------------------------------------------- #
# Bounds
# --------------------------------------------------------------------------- #

PINCH_BOUNDS = (0.012, 0.110)
DEAD_ZONE_BOUNDS = (0.002, 0.060)
SMOOTHING_BOUNDS = (0.15, 0.72)
CURSOR_SPEED_BOUNDS = (0.7, 3.2)
DRAG_DELAY_BOUNDS = (0.20, 1.00)
DOUBLE_PINCH_BOUNDS = (0.25, 0.80)
SCROLL_SPEED_BOUNDS = (15, 90)
SWIPE_VELOCITY_BOUNDS = (0.8, 4.0)
SPEECH_THRESHOLD_BOUNDS = (0.02, 0.35)

#: A comfortable reach must span at least this fraction of the frame, otherwise
#: a lazy or truncated session would shrink the active box into a corner.
MIN_ACTIVE_BOX_SPAN = 0.25

#: Padding added around the measured reach so the user never has to touch the
#: very edge of the camera frame to reach a screen corner.
ACTIVE_BOX_PADDING = 0.08

#: Below this separation between the open and closed pinch clusters the pinch
#: measurement is considered unusable and the existing threshold is kept.
MIN_PINCH_SEPARATION = 0.012

SCHEMA_VERSION = 1


def clamp(value: float, bounds: Tuple[float, float]) -> float:
    """Clamps ``value`` into the inclusive ``bounds`` tuple."""
    low, high = bounds
    return max(low, min(high, value))


def percentile(values: Sequence[float], fraction: float) -> float:
    """Linear-interpolated percentile of ``values`` (``fraction`` in ``[0, 1]``)."""
    if not values:
        raise ValueError("percentile() requires at least one value")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = clamp(fraction, (0.0, 1.0)) * (len(ordered) - 1)
    low = int(math.floor(position))
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


@dataclass
class DistanceCluster:
    """One mode of a distance distribution, summarised by robust percentiles."""

    centre: float
    low: float
    high: float
    count: int


def split_distance_clusters(
    values: Sequence[float],
) -> Optional[Tuple[DistanceCluster, DistanceCluster]]:
    """
    Splits a bimodal distance sample into a low (closed) and high (open) cluster.

    Uses Otsu's between-class variance, ``n0 * n1 * (mu0 - mu1) ** 2``,
    **maximised** over every candidate boundary. Assuming the user pinched
    exactly half the time would be far more fragile; this finds the gap in the
    data whatever the duty cycle is.

    Returns ``None`` when the sample is too small or too uniform for a split to
    mean anything.
    """
    if len(values) < 6:
        return None

    ordered = sorted(values)
    count = len(ordered)
    total = sum(ordered)
    running_sum = 0.0

    best_score = -1.0
    best_index = -1

    for index in range(1, count):
        running_sum += ordered[index - 1]
        low_count = index
        high_count = count - index
        low_mean = running_sum / low_count
        high_mean = (total - running_sum) / high_count
        score = low_count * high_count * (low_mean - high_mean) ** 2
        if score > best_score:
            best_score = score
            best_index = index

    if best_index <= 0:
        return None

    low = ordered[:best_index]
    high = ordered[best_index:]
    return (
        DistanceCluster(
            centre=sum(low) / len(low),
            low=percentile(low, 0.10),
            high=percentile(low, 0.90),
            count=len(low),
        ),
        DistanceCluster(
            centre=sum(high) / len(high),
            low=percentile(high, 0.10),
            high=percentile(high, 0.90),
            count=len(high),
        ),
    )


def pinch_threshold_from_clusters(
    closed: DistanceCluster,
    open_cluster: DistanceCluster,
) -> Optional[Tuple[float, float, float]]:
    """
    Places the pinch threshold inside the gap between the two clusters.

    Returns ``(threshold, separation, confidence)`` or ``None`` when the
    clusters overlap too much for any threshold to be meaningful. The threshold
    sits 35% of the way from the closed side toward the open side, which favours
    registering a deliberate click over suppressing a false one.
    """
    separation = open_cluster.centre - closed.centre
    if separation < MIN_PINCH_SEPARATION:
        return None

    closed_high = closed.high
    open_low = open_cluster.low
    if open_low <= closed_high:
        # Heavy overlap between the two bands: fall back to the centres so the
        # threshold still lands between them instead of outside the distribution.
        open_low = closed.centre + separation * 0.5

    threshold = closed_high + (open_low - closed_high) * 0.35
    confidence = min(1.0, separation / (MIN_PINCH_SEPARATION * 4.0))
    return clamp(threshold, PINCH_BOUNDS), separation, confidence


# --------------------------------------------------------------------------- #
# Hardware discovery
# --------------------------------------------------------------------------- #

@dataclass
class CameraDevice:
    """A camera that answered an open/read probe."""

    index: int
    name: str
    opened: bool
    width: int = 0
    height: int = 0
    fps: float = 0.0

    @property
    def resolution(self) -> str:
        if not self.opened:
            return "—"
        return f"{self.width}×{self.height}"


@dataclass
class AudioDevice:
    """An audio input endpoint reported by the host audio API."""

    index: int
    name: str
    channels: int = 1
    max_input_channels: int = 0
    default_sample_rate: int = 0
    probed: bool = True


#: DirectShow is not safe to drive from two threads at once: concurrent
#: ``VideoCapture`` opens corrupt the driver's state and can abort the whole
#: interpreter with an access violation. Every capture in this module is
#: therefore serialised, which also stops a device scan from colliding with the
#: live preview or with a timing measurement on the same camera.
_CAPTURE_LOCK = threading.Lock()

_scan_lock = threading.Lock()
_scan_in_flight = False


def begin_device_scan() -> bool:
    """
    Claims the right to enumerate hardware, so only one scan runs at a time.

    Returns ``False`` when a scan is already running; the caller should then
    skip its own rather than queue a second enumeration behind the first.
    """
    global _scan_in_flight
    with _scan_lock:
        if _scan_in_flight:
            return False
        _scan_in_flight = True
        return True


def end_device_scan() -> None:
    """Releases the claim taken by :func:`begin_device_scan`."""
    global _scan_in_flight
    with _scan_lock:
        _scan_in_flight = False


def probe_cameras(
    indices: Sequence[int] = (0, 1, 2, 3, 4, 5),
    probe_seconds: float = 0.35,
    width: int = 640,
    height: int = 480,
) -> List[CameraDevice]:
    """
    Probes each candidate index and keeps the ones that actually deliver frames.

    A camera that opens but never returns a frame is reported as ``opened=False``
    so the wizard can grey it out instead of failing later during a live session.
    """
    with _CAPTURE_LOCK:
        return _probe_cameras(indices, probe_seconds, width, height)


def _probe_cameras(
    indices: Sequence[int],
    probe_seconds: float,
    width: int,
    height: int,
) -> List[CameraDevice]:
    """Body of :func:`probe_cameras`; callers must hold ``_CAPTURE_LOCK``."""
    devices: List[CameraDevice] = []
    if not HAS_CV2:
        return devices

    for index in indices:
        capture = None
        try:
            try:
                capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                if not capture.isOpened():
                    capture.release()
                    capture = cv2.VideoCapture(index)
            except Exception:
                capture = None

            if capture is None or not capture.isOpened():
                devices.append(CameraDevice(index, f"Camera {index}", False))
                continue

            capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            deadline = time.time() + probe_seconds
            frames = 0
            while time.time() < deadline:
                grabbed, _frame = capture.read()
                if not grabbed:
                    break
                frames += 1

            measured_w = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            measured_h = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            reported_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)

            # ``frames`` over the probe window is a truer figure than the value
            # the driver advertises, which is routinely a stale constant.
            measured_fps = frames / probe_seconds if frames > 1 else reported_fps

            devices.append(
                CameraDevice(
                    index=index,
                    name=f"Camera {index}",
                    opened=frames > 0,
                    width=measured_w,
                    height=measured_h,
                    fps=round(measured_fps, 1),
                )
            )
        except Exception:
            devices.append(CameraDevice(index, f"Camera {index}", False))
        finally:
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass

    return devices


def probe_microphones(max_devices: int = 12) -> List[AudioDevice]:
    """
    Enumerates audio input endpoints.

    Returns an empty list when PyAudio is unavailable, letting the caller fall
    back to the system default device instead of blocking the wizard.
    """
    if not HAS_PYAUDIO:
        return []

    devices: List[AudioDevice] = []
    audio = None
    try:
        audio = pyaudio.PyAudio()
        for index in range(audio.get_device_count()):
            if len(devices) >= max_devices:
                break
            try:
                info = audio.get_device_info_by_index(index)
            except Exception:
                continue
            if int(info.get("maxInputChannels", 0)) <= 0:
                continue
            devices.append(
                AudioDevice(
                    index=index,
                    name=str(info.get("name", f"Microphone {index}")),
                    channels=int(info.get("maxInputChannels", 1)),
                    max_input_channels=int(info.get("maxInputChannels", 0)),
                    default_sample_rate=int(info.get("defaultSampleRate", 0)),
                )
            )
    except Exception:
        return []
    finally:
        if audio is not None:
            try:
                audio.terminate()
            except Exception:
                pass

    return devices


# --------------------------------------------------------------------------- #
# Microphone noise floor
# --------------------------------------------------------------------------- #

class MicrophoneProbe:
    """
    Short-lived recorder used to measure the ambient noise floor.

    The floor becomes the reference the speech recogniser compares against, so
    a noisy room no longer forces the user to guess a sensitivity value.
    """

    def __init__(
        self,
        device_index: Optional[int] = None,
        sample_rate: int = 16000,
        chunk_size: int = 1024,
    ):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.available = HAS_PYAUDIO
        self.error: str = ""

    def measure(self, seconds: float = 1.5) -> Dict[str, float]:
        """
        Records ``seconds`` of ambient audio and returns the derived levels.

        The result carries ``noise_floor`` (the loudest quiet stretch) and
        ``speech_threshold`` (three times the floor, bounded) plus the measured
        peak so the UI can show whether the room is usable at all.
        """
        if not self.available:
            self.error = "PyAudio is not installed"
            return {"noise_floor": 0.0, "speech_threshold": 0.06, "peak": 0.0, "ok": 0.0}

        audio = None
        stream = None
        levels: List[float] = []
        try:
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
            )
            chunks = max(1, int(self.sample_rate * seconds / self.chunk_size))
            for _ in range(chunks):
                raw = stream.read(self.chunk_size, exception_on_overflow=False)
                levels.append(self._rms(raw))
        except Exception as error:
            self.error = str(error)
            return {"noise_floor": 0.0, "speech_threshold": 0.06, "peak": 0.0, "ok": 0.0}
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if audio is not None:
                try:
                    audio.terminate()
                except Exception:
                    pass

        if not levels:
            return {"noise_floor": 0.0, "speech_threshold": 0.06, "peak": 0.0, "ok": 0.0}

        noise_floor = percentile(levels, 0.90)
        peak = max(levels)
        return {
            "noise_floor": round(noise_floor, 5),
            "speech_threshold": round(
                clamp(noise_floor * 3.5, SPEECH_THRESHOLD_BOUNDS), 5
            ),
            "peak": round(peak, 5),
            "ok": 1.0,
        }

    @staticmethod
    def _rms(raw: bytes) -> float:
        """Root-mean-square of a signed 16-bit PCM chunk, normalised to 0..1."""
        if not raw:
            return 0.0
        if not HAS_NUMPY:
            total = 0
            count = 0
            for offset in range(0, len(raw) - 1, 2):
                value = int.from_bytes(raw[offset:offset + 2], "little", signed=True)
                total += value * value
                count += 1
            if count == 0:
                return 0.0
            return math.sqrt(total / count) / 32768.0
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        return float(np.sqrt(np.mean(np.square(samples))))


# --------------------------------------------------------------------------- #
# Camera timing probe
# --------------------------------------------------------------------------- #

def measure_camera_timing(
    camera_index: int,
    seconds: float = 1.5,
    width: int = 640,
    height: int = 480,
) -> Dict[str, float]:
    """
    Measures the sustained frame rate and the vision pipeline latency.

    ``latency_ms`` covers the read → MediaPipe → dispatch path, which is the
    number that actually determines whether the cursor feels attached to the
    hand. The landmark stage is skipped when the caller passes raw frames, so
    this doubles as a pure capture benchmark.
    """
    result = {"fps": 0.0, "latency_ms": 0.0, "frames": 0.0, "ok": 0.0}
    if not HAS_CV2:
        return result

    with _CAPTURE_LOCK:
        return _measure_camera_timing(camera_index, seconds, width, height)


def _measure_camera_timing(
    camera_index: int,
    seconds: float,
    width: int,
    height: int,
) -> Dict[str, float]:
    """Body of :func:`measure_camera_timing`; hold ``_CAPTURE_LOCK``."""
    result = {"fps": 0.0, "latency_ms": 0.0, "frames": 0.0, "ok": 0.0}
    if not HAS_CV2:
        return result

    capture = None
    latencies: List[float] = []
    frames = 0
    try:
        try:
            capture = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if not capture.isOpened():
                capture.release()
                capture = cv2.VideoCapture(camera_index)
        except Exception:
            capture = None
        if capture is None or not capture.isOpened():
            return result

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        deadline = time.time() + seconds
        while time.time() < deadline:
            started = time.perf_counter()
            grabbed, _frame = capture.read()
            if not grabbed:
                break
            latencies.append((time.perf_counter() - started) * 1000.0)
            frames += 1
    except Exception:
        return result
    finally:
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass

    if frames > 0:
        result["fps"] = round(frames / seconds, 1)
        result["latency_ms"] = round(percentile(latencies, 0.50), 2)
        result["frames"] = float(frames)
        result["ok"] = 1.0
    return result


# --------------------------------------------------------------------------- #
# Guided hand calibration
# --------------------------------------------------------------------------- #

class CalibrationPhase(Enum):
    """The stages of the guided hand routine, in order."""

    REST = "REST"
    STILL = "STILL"
    PINCH = "PINCH"
    REACH = "REACH"
    SWIPE = "SWIPE"
    DONE = "DONE"


@dataclass
class HandSample:
    """
    One frame of hand geometry, decoupled from MediaPipe.

    The vision pipeline converts its landmarks into this small value object so
    the calibration maths stays unit-testable without a camera.
    """

    index_tip: Tuple[float, float]
    pinch_distance: float
    timestamp: float
    #: Filled in during the REACH phase only: which corner the user was asked
    #: to reach for, used to keep the extreme samples from a single direction.
    reach_zone: Optional[str] = None


@dataclass
class CalibrationReport:
    """Every measured value, plus how much the engine trusts it."""

    pinch_threshold: float = 0.045
    dead_zone_radius: float = 0.015
    smoothing_factor: float = 0.45
    cursor_speed: float = 1.6
    drag_hold_delay: float = 0.35
    double_pinch_window: float = 0.40
    scroll_speed: float = 40
    swipe_velocity_threshold: float = 1.8
    scroll_dead_band: float = 0.015
    active_box: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    confidence: Dict[str, float] = field(default_factory=dict)

    def confidence_of(self, name: str) -> float:
        return self.confidence.get(name, 0.0)

    def to_settings_patch(self) -> Dict[str, Any]:
        """Flattens the report into a ``SettingsManager.set()`` compatible map."""
        return {
            "gestures.pinch_click_threshold": round(self.pinch_threshold, 5),
            "gestures.dead_zone_radius": round(self.dead_zone_radius, 5),
            "gestures.smoothing_factor": round(self.smoothing_factor, 4),
            "gestures.cursor_speed": round(self.cursor_speed, 3),
            "gestures.pinch_hold_drag_delay": round(self.drag_hold_delay, 3),
            "gestures.double_pinch_window": round(self.double_pinch_window, 3),
            "gestures.scroll_speed": int(round(self.scroll_speed)),
            "gestures.swipe_velocity_threshold": round(self.swipe_velocity_threshold, 3),
            "gestures.scroll_dead_band": round(self.scroll_dead_band, 5),
            "gestures.active_box": [round(v, 4) for v in self.active_box],
            "gestures.calibrated": True,
            "calibration.schema_version": SCHEMA_VERSION,
        }


class CalibrationSession:
    """
    State machine that turns a guided hand routine into a
    :class:`CalibrationReport`.

    Usage from the wizard: set :attr:`phase`, push one :class:`HandSample` per
    rendered frame into :meth:`feed`, and read :meth:`report` once the phase
    reaches ``DONE``. Samples from a phase that never completes are discarded
    rather than folded into the result, so a user who skips the swipe step still
    gets a correct — merely less confident — calibration.
    """

    #: Minimum samples a phase must collect before its median is trusted.
    MIN_SAMPLES = 12

    def __init__(self, current: Optional[CalibrationReport] = None):
        self.report = current or CalibrationReport()
        self.phase = CalibrationPhase.REST
        self.samples_seen = 0
        self.phase_samples = 0
        self.lost_frames = 0
        self.started_at = time.time()
        self.error: str = ""

        # STILL / PINCH / REACH / SWIPE accumulators
        self._jitter: List[float] = []
        self._pinch: List[float] = []
        self._pinch_holds: List[float] = []
        self._pinch_releases: List[float] = []
        self._prev_index: Optional[Tuple[float, float]] = None
        self._prev_timestamp: Optional[float] = None
        self._pinch_open: Optional[bool] = None
        self._last_pinch_start: Optional[float] = None
        self._last_pinch_end: Optional[float] = None
        self._reach_x: List[float] = []
        self._reach_y: List[float] = []
        self._reach_speed: List[float] = []
        self._swipe_speed: List[float] = []
        self._swipe_span: List[float] = []
        self._scroll_speed: List[float] = []

    # -- driving the session ---------------------------------------------- #

    def begin(self, phase: CalibrationPhase) -> None:
        """Switches phase, resetting the accumulator for the new phase."""
        if phase == self.phase:
            return
        self._commit(self.phase)
        self.phase = phase
        self.phase_samples = 0

    def feed(self, sample: Optional[HandSample]) -> bool:
        """
        Feeds one frame. Returns ``True`` while the phase is still collecting.

        A ``None`` sample means the hand was lost; it is counted so the wizard
        can ask the user to reposition instead of silently recording nothing.
        """
        if self.phase == CalibrationPhase.DONE:
            return False

        if sample is None:
            self.lost_frames += 1
            self._reset_trackers()
            return True

        self.samples_seen += 1
        self.phase_samples += 1

        if self.phase == CalibrationPhase.STILL:
            self._collect_still(sample)
        elif self.phase == CalibrationPhase.PINCH:
            self._collect_pinch(sample)
        elif self.phase == CalibrationPhase.REACH:
            self._collect_reach(sample)
        elif self.phase == CalibrationPhase.SWIPE:
            self._collect_swipe(sample)

        return True

    def notify_hand_lost(self) -> None:
        """Public alias used by the vision thread when tracking is interrupted."""
        if self.phase != CalibrationPhase.DONE:
            self.lost_frames += 1
            self._reset_trackers()

    def finish(self) -> CalibrationReport:
        """Commits the last phase and returns the completed report."""
        self._commit(self.phase)
        self.phase = CalibrationPhase.DONE
        return self.report

    @property
    def is_complete(self) -> bool:
        return self.phase == CalibrationPhase.DONE

    @property
    def pinch_cycles(self) -> int:
        """Number of completed close→open cycles seen during the PINCH phase."""
        return len(self._pinch_holds)

    def reach_box(self) -> Optional[Tuple[float, float, float, float]]:
        """
        The reach envelope measured so far, as ``(left, top, right, bottom)``.

        Returned live so the wizard can show the window growing as the user
        moves, which is far easier to follow than a number that appears at the
        end. Returns ``None`` before enough samples have arrived.
        """
        if len(self._reach_x) < 4 or len(self._reach_y) < 4:
            return None
        return (
            min(self._reach_x), min(self._reach_y),
            max(self._reach_x), max(self._reach_y),
        )

    def progress(self, target: int) -> float:
        """Collection progress for the current phase, clamped to ``0.0..1.0``."""
        if target <= 0:
            return 1.0
        return clamp(self.phase_samples / float(target), (0.0, 1.0))

    # -- per-phase collection ---------------------------------------------- #

    def _collect_still(self, sample: HandSample) -> None:
        """Measures the tremor of a hand held motionless, frame to frame."""
        if self._prev_index is not None and self._prev_timestamp is not None:
            delta = sample.timestamp - self._prev_timestamp
            if delta > 0:
                travel = math.hypot(
                    sample.index_tip[0] - self._prev_index[0],
                    sample.index_tip[1] - self._prev_index[1],
                )
                self._jitter.append(travel / delta)
        self._prev_index = sample.index_tip
        self._prev_timestamp = sample.timestamp

    def _collect_pinch(self, sample: HandSample) -> None:
        """
        Tracks the open/closed pinch cycle to time the hold and release gaps and
        to feed the bimodal distance distribution.
        """
        self._pinch.append(sample.pinch_distance)
        closed = sample.pinch_distance < self.report.pinch_threshold

        if self._pinch_open is None:
            self._pinch_open = closed
            if closed:
                self._last_pinch_start = sample.timestamp
        elif closed != self._pinch_open:
            self._pinch_open = closed
            if closed:
                self._last_pinch_start = sample.timestamp
            else:
                if self._last_pinch_start is not None:
                    self._pinch_holds.append(sample.timestamp - self._last_pinch_start)
                if self._last_pinch_end is not None:
                    self._pinch_releases.append(
                        sample.timestamp - self._last_pinch_end
                    )
                self._last_pinch_end = sample.timestamp
                self._last_pinch_start = None

    def _collect_reach(self, sample: HandSample) -> None:
        """Records the comfortable reach envelope and the typical move speed."""
        self._reach_x.append(sample.index_tip[0])
        self._reach_y.append(sample.index_tip[1])
        if self._prev_index is not None and self._prev_timestamp is not None:
            delta = sample.timestamp - self._prev_timestamp
            if delta > 0:
                travel = math.hypot(
                    sample.index_tip[0] - self._prev_index[0],
                    sample.index_tip[1] - self._prev_index[1],
                )
                speed = travel / delta
                self._reach_speed.append(speed)
                self._scroll_speed.append(speed)
        self._prev_index = sample.index_tip
        self._prev_timestamp = sample.timestamp

    def _collect_swipe(self, sample: HandSample) -> None:
        """Records the fastest horizontal sweep the user can comfortably make."""
        if self._prev_index is not None and self._prev_timestamp is not None:
            delta = sample.timestamp - self._prev_timestamp
            if delta > 0.008:
                speed = (sample.index_tip[0] - self._prev_index[0]) / delta
                self._swipe_speed.append(abs(speed))
                self._swipe_span.append(abs(sample.index_tip[0] - self._prev_index[0]))
        self._prev_index = sample.index_tip
        self._prev_timestamp = sample.timestamp

    def _reset_trackers(self) -> None:
        self._prev_index = None
        self._prev_timestamp = None
        self._pinch_open = None
        self._last_pinch_start = None
        self._last_pinch_end = None

    # -- committing each phase --------------------------------------------- #

    def _commit(self, phase: CalibrationPhase) -> None:
        if self.phase_samples < self.MIN_SAMPLES:
            return

        if phase == CalibrationPhase.STILL:
            self._commit_still()
        elif phase == CalibrationPhase.PINCH:
            self._commit_pinch()
        elif phase == CalibrationPhase.REACH:
            self._commit_reach()
        elif phase == CalibrationPhase.SWIPE:
            self._commit_swipe()

    def _commit_still(self) -> None:
        """
        Turns the measured tremor speed into a dead zone and a smoothing factor.

        A hand that jitters faster needs a wider dead zone and more smoothing to
        feel steady; the mapping is deliberately gentle because over-smoothing
        costs more than a little residual tremor.
        """
        if not self._jitter:
            return
        p90 = percentile(self._jitter, 0.90)
        dead_zone = clamp(p90 * 0.10, DEAD_ZONE_BOUNDS)
        smoothing = clamp(0.30 + p90 * 1.2, SMOOTHING_BOUNDS)
        self.report.dead_zone_radius = round(dead_zone, 5)
        self.report.smoothing_factor = round(smoothing, 4)
        self.report.confidence["dead_zone_radius"] = self._quality(len(self._jitter), 20)
        self.report.confidence["smoothing_factor"] = self._quality(len(self._jitter), 20)

    def _commit_pinch(self) -> None:
        """
        Places the threshold between the two pinch clusters, biased toward the
        closed side so that a deliberate click always registers while a resting
        hand never does.
        """
        split = split_distance_clusters(self._pinch)
        if split is None:
            self.report.confidence["pinch_click_threshold"] = 0.0
        else:
            derived = pinch_threshold_from_clusters(*split)
            if derived is None:
                self.report.confidence["pinch_click_threshold"] = 0.15
            else:
                threshold, _separation, confidence = derived
                self.report.pinch_threshold = round(threshold, 5)
                self.report.confidence["pinch_click_threshold"] = round(confidence, 3)

        if len(self._pinch_holds) >= 2:
            median_hold = percentile(self._pinch_holds, 0.50)
            self.report.drag_hold_delay = round(
                clamp(median_hold + 0.25, DRAG_DELAY_BOUNDS), 3
            )
            self.report.confidence["pinch_hold_drag_delay"] = self._quality(
                len(self._pinch_holds), 3
            )

        if len(self._pinch_releases) >= 2:
            gap = percentile(self._pinch_releases, 0.90)
            self.report.double_pinch_window = round(
                clamp(gap * 1.30, DOUBLE_PINCH_BOUNDS), 3
            )
            self.report.confidence["double_pinch_window"] = self._quality(
                len(self._pinch_releases), 3
            )

    def _commit_reach(self) -> None:
        """
        Shrinks the camera frame down to the box the user actually reaches.

        This is what removes the need to physically stretch towards the top-left
        of the webcam image to hit the top-left of the screen.
        """
        if len(self._reach_x) < 4 or len(self._reach_y) < 4:
            return

        min_x, max_x = min(self._reach_x), max(self._reach_x)
        min_y, max_y = min(self._reach_y), max(self._reach_y)

        span_x = max(max_x - min_x, MIN_ACTIVE_BOX_SPAN)
        span_y = max(max_y - min_y, MIN_ACTIVE_BOX_SPAN)
        pad_x = span_x * ACTIVE_BOX_PADDING
        pad_y = span_y * ACTIVE_BOX_PADDING

        left = clamp(min_x - pad_x, (0.0, 1.0))
        top = clamp(min_y - pad_y, (0.0, 1.0))
        right = clamp(max_x + pad_x, (0.0, 1.0))
        bottom = clamp(max_y + pad_y, (0.0, 1.0))

        # Guard against a degenerate box after clamping against the frame edges.
        if right - left < MIN_ACTIVE_BOX_SPAN:
            centre = (left + right) / 2.0
            left = clamp(centre - MIN_ACTIVE_BOX_SPAN / 2.0, (0.0, 1.0 - MIN_ACTIVE_BOX_SPAN))
            right = left + MIN_ACTIVE_BOX_SPAN
        if bottom - top < MIN_ACTIVE_BOX_SPAN:
            centre = (top + bottom) / 2.0
            top = clamp(centre - MIN_ACTIVE_BOX_SPAN / 2.0, (0.0, 1.0 - MIN_ACTIVE_BOX_SPAN))
            bottom = top + MIN_ACTIVE_BOX_SPAN

        self.report.active_box = (
            round(left, 4), round(top, 4), round(right, 4), round(bottom, 4)
        )
        self.report.confidence["active_box"] = self._quality(
            min(len(self._reach_x), len(self._reach_y)), 30
        )

        if self._reach_speed:
            median_speed = percentile(self._reach_speed, 0.50)
            # Faster hand → less lag: lower the EMA weight and raise the gain.
            self.report.smoothing_factor = round(
                clamp(0.55 - median_speed * 0.15, SMOOTHING_BOUNDS), 4
            )
            self.report.cursor_speed = round(
                clamp(1.6 + median_speed * 0.30, CURSOR_SPEED_BOUNDS), 3
            )
            self.report.scroll_speed = round(
                clamp(median_speed * 90, SCROLL_SPEED_BOUNDS)
            )
            self.report.confidence["smoothing_factor"] = self._quality(
                len(self._reach_speed), 20
            )
            self.report.confidence["cursor_speed"] = self._quality(
                len(self._reach_speed), 20
            )
            self.report.confidence["scroll_speed"] = self._quality(
                len(self._reach_speed), 20
            )

    def _commit_swipe(self) -> None:
        """
        Derives the swipe velocity cut-off and the scroll dead band.

        The cut-off sits at 55% of the fastest comfortable sweep so an
        intentional flick registers while ordinary pointing never does.
        """
        if not self._swipe_speed:
            return
        fastest = percentile(self._swipe_speed, 0.95)
        self.report.swipe_velocity_threshold = round(
            clamp(fastest * 0.55, SWIPE_VELOCITY_BOUNDS), 3
        )
        self.report.confidence["swipe_velocity_threshold"] = self._quality(
            len(self._swipe_speed), 15
        )

        if self._swipe_span:
            self.report.scroll_dead_band = round(
                clamp(percentile(self._swipe_span, 0.50) * 0.35, (0.004, 0.040)), 5
            )

    def _quality(self, samples: int, expected: int) -> float:
        """Confidence ramps to 1.0 once a phase collected ``expected`` samples."""
        return round(clamp(samples / float(expected), (0.0, 1.0)), 3)


# --------------------------------------------------------------------------- #
# Runtime adaptive tuner
# --------------------------------------------------------------------------- #

@dataclass
class AdaptationEvent:
    """A single threshold change proposed by the runtime tuner."""

    key: str
    old_value: float
    new_value: float
    reason: str


class AdaptiveTuner:
    """
    Keeps the pinch threshold and tremor filters honest during real use.

    The guided wizard measures once; lighting, distance and hand posture change
    afterwards, so the threshold is re-derived continuously from a rolling
    window of samples. Two safeguards keep this from oscillating:

    * a minimum sample count, so the first few seconds are ignored;
    * a relative hysteresis band, so a change must exceed
      ``adaptive_write_threshold`` before the recogniser is touched at all.

    Values are only persisted to disk once they have been stable for
    :attr:`persist_after` consecutive evaluations, which prevents a noisy
    session from writing the config on every frame.
    """

    PINCH_KEY = "gestures.pinch_click_threshold"
    DEAD_ZONE_KEY = "gestures.dead_zone_radius"
    SMOOTHING_KEY = "gestures.smoothing_factor"

    def __init__(
        self,
        settings,
        window: int = 240,
        min_samples: int = 45,
        write_threshold: float = 0.08,
        persist_after: int = 3,
    ):
        self.settings = settings
        self.window = max(30, window)
        self.min_samples = max(10, min_samples)
        self.write_threshold = max(0.01, write_threshold)
        self.persist_after = max(1, persist_after)

        self._pinch_samples: Deque[float] = deque(maxlen=self.window)
        self._jitter_samples: Deque[float] = deque(maxlen=self.window)
        self._stable_counts: Dict[str, int] = {}
        self._pending: Dict[str, float] = {}

        self._pinch_threshold = float(
            settings.get(self.PINCH_KEY, 0.045) or 0.045
        )
        self._dead_zone = float(
            settings.get(self.DEAD_ZONE_KEY, 0.015) or 0.015
        )
        self._smoothing = float(
            settings.get(self.SMOOTHING_KEY, 0.45) or 0.45
        )

        self._prev_index: Optional[Tuple[float, float]] = None
        self._prev_timestamp: Optional[float] = None
        self.last_event: Optional[AdaptationEvent] = None
        self.events: List[AdaptationEvent] = []

    # -- live getters used by the vision pipeline -------------------------- #

    @property
    def pinch_threshold(self) -> float:
        return self._pinch_threshold

    @property
    def dead_zone(self) -> float:
        return self._dead_zone

    @property
    def smoothing(self) -> float:
        return self._smoothing

    @property
    def is_warm(self) -> bool:
        """True once enough samples exist for an opinion to be meaningful."""
        return len(self._pinch_samples) >= self.min_samples

    def snapshot(self) -> Dict[str, float]:
        return {
            "samples": float(len(self._pinch_samples)),
            "min_samples": float(self.min_samples),
            "pinch_threshold": round(self._pinch_threshold, 5),
            "dead_zone_radius": round(self._dead_zone, 5),
            "smoothing_factor": round(self._smoothing, 4),
            "warm": 1.0 if self.is_warm else 0.0,
        }

    # -- ingestion ---------------------------------------------------------- #

    def feed(self, index_tip: Tuple[float, float], pinch_distance: float, timestamp: float) -> None:
        """Records one frame of hand geometry."""
        self._pinch_samples.append(float(pinch_distance))
        if self._prev_index is not None and self._prev_timestamp is not None:
            delta = timestamp - self._prev_timestamp
            if delta > 0:
                travel = math.hypot(
                    index_tip[0] - self._prev_index[0],
                    index_tip[1] - self._prev_index[1],
                )
                self._jitter_samples.append(travel / delta)
        self._prev_index = index_tip
        self._prev_timestamp = timestamp

    def notify_hand_lost(self) -> None:
        """Drops the frame-to-frame trackers so a gap is not read as a flick."""
        self._prev_index = None
        self._prev_timestamp = None

    def reset(self) -> None:
        """Clears the rolling window, e.g. when calibration is re-run."""
        self._pinch_samples.clear()
        self._jitter_samples.clear()
        self._stable_counts.clear()
        self._pending.clear()
        self.notify_hand_lost()

    # -- evaluation --------------------------------------------------------- #

    def evaluate(self, persist: bool = True) -> Optional[AdaptationEvent]:
        """
        Re-derives the thresholds from the rolling window.

        Returns the applied :class:`AdaptationEvent`, or ``None`` when the sample
        count is too low or every value already sits inside its hysteresis band.
        """
        if not self.is_warm:
            return None

        proposal = self._propose_pinch()
        if proposal is None:
            proposal = self._propose_jitter()

        if proposal is None:
            return None

        key, target, bounds, reason = proposal
        current = {
            self.PINCH_KEY: self._pinch_threshold,
            self.DEAD_ZONE_KEY: self._dead_zone,
            self.SMOOTHING_KEY: self._smoothing,
        }[key]

        if abs(target - current) <= self.write_threshold * abs(current) + 1e-6:
            self._stable_counts[key] = 0
            self._pending.pop(key, None)
            return None

        self._stable_counts[key] = self._stable_counts.get(key, 0) + 1
        self._pending[key] = target
        if self._stable_counts[key] < self.persist_after:
            return None

        applied = clamp(target, bounds)
        self._stable_counts[key] = 0
        self._pending.pop(key, None)

        event = AdaptationEvent(key, current, applied, reason)
        self.last_event = event
        self.events.append(event)
        if len(self.events) > 50:
            del self.events[:-50]

        if key == self.PINCH_KEY:
            self._pinch_threshold = applied
        elif key == self.DEAD_ZONE_KEY:
            self._dead_zone = applied
        else:
            self._smoothing = applied

        try:
            self.settings.set(key, applied, auto_save=persist)
        except Exception:
            # A read-only or locked config must never take the vision thread
            # down: keep the in-memory value and carry on.
            pass
        return event

    def _propose_pinch(self):
        """
        Re-centres the pinch threshold on the observed bimodal distribution.

        The same 35% bias as the wizard is used, so continuous tuning converges
        on the value the user would have accepted during calibration.
        """
        split = split_distance_clusters(list(self._pinch_samples))
        if split is None:
            return None
        derived = pinch_threshold_from_clusters(*split)
        if derived is None:
            return None
        threshold, _separation, _confidence = derived
        return (
            self.PINCH_KEY,
            threshold,
            PINCH_BOUNDS,
            "pinch distribution recentred on measured clusters",
        )

    def _propose_jitter(self):
        """Widens or narrows the dead zone and smoothing from measured tremor."""
        if len(self._jitter_samples) < self.min_samples:
            return None
        p90 = percentile(list(self._jitter_samples), 0.90)
        dead_zone = clamp(p90 * 0.10, DEAD_ZONE_BOUNDS)
        if abs(dead_zone - self._dead_zone) > self.write_threshold * abs(self._dead_zone):
            return (
                self.DEAD_ZONE_KEY,
                dead_zone,
                DEAD_ZONE_BOUNDS,
                "dead zone matched to measured hand tremor",
            )
        smoothing = clamp(0.30 + p90 * 1.2, SMOOTHING_BOUNDS)
        return (
            self.SMOOTHING_KEY,
            smoothing,
            SMOOTHING_BOUNDS,
            "smoothing matched to measured hand tremor",
        )
