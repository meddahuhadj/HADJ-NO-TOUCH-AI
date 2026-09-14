"""Camera configuration helpers and device discovery.

Device discovery validates that a camera actually delivers usable frames
(not just ``isOpened()``), because some drivers claim a capture device by
index over MediaFoundation while ``read()`` then hangs or returns nothing.
All frame reads are time-bounded so a broken driver can never freeze startup.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Optional

from ..config import Settings, SETTINGS
from ..logging_setup import get_logger

log = get_logger("camera.config")

try:
    import cv2
    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False

# Uniform frames (privacy shutter, broken driver mode, ...) are useless.
_MIN_FRAME_STD = 1.5
# How long a single probe read may block before the candidate is abandoned.
READ_TIMEOUT = 1.5
# How long VideoCapture() may block during the quick scan.
OPEN_TIMEOUT_PROBE = 1.2
# How long VideoCapture() may block for the real open (more patient).
OPEN_TIMEOUT_REAL = 4.0
# How long a property write (cap.set) may block.
SET_TIMEOUT = 3.0
# How long the whole discovery scan may take.
SCAN_DEADLINE = 8.0
# How long a resolution is cached before the machine is re-probed.
CACHE_TTL_SECONDS = 15.0


def _backends() -> list[int]:
    """Backends tried in order when opening a camera by index.

    DirectShow is reliable for index-based capture on Windows; MediaFoundation
    is kept as a fallback (cleaner timing but it can 'open' then hang).
    """
    if os.name == "nt":
        return [cv2.CAP_DSHOW, cv2.CAP_MSMF]
    return [cv2.CAP_MSMF, 0]


def _probing_backends() -> list[int]:
    return _backends()


def is_frame_usable(frame) -> bool:
    """True when a frame has enough structure to be worth processing."""
    if frame is None or getattr(frame, "size", 0) == 0:
        return False
    try:
        return bool(float(frame.std()) > _MIN_FRAME_STD)
    except Exception:
        return False


def bounded_call(fn, timeout: float = SET_TIMEOUT):
    """Run ``fn()`` on a worker thread; return its result or ``None`` on timeout.

    Some camera drivers block indefinitely inside ``VideoCapture()`` or
    ``cap.set()`` when a device is in a bad state; we never want that to hang
    startup, so everything touching the driver is funneled through here.
    """
    box: dict = {"out": None}

    def _do() -> None:
        try:
            box["out"] = fn()
        except Exception:
            box["out"] = None

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None
    return box.get("out")


def apply_exposure(cap) -> None:
    """Best-effort exposure / brightness boost for dark webcams (guarded)."""

    def _do() -> None:
        try:
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
            cap.set(cv2.CAP_PROP_AUTO_WB, 1.0)
            cap.set(cv2.CAP_PROP_GAIN, 200)
            cap.set(cv2.CAP_PROP_BRIGHTNESS, 150)
        except Exception:
            pass

    if cap is None:
        return
    bounded_call(_do, SET_TIMEOUT)


def _safe_release(cap) -> None:
    if cap is None:
        return
    try:
        cap.release()
    except Exception:
        pass


def _bounded_read_ex(cap, timeout: float = READ_TIMEOUT):
    """Call ``cap.read()`` with a time limit.

    Returns ``(ok, frame, thread)``. ``thread`` is the worker that executed
    the read; if it is still alive after the timeout the driver is wedged and
    callers must NOT issue another read on the same capture (OpenCV
    ``VideoCapture`` is not thread-safe, overlapping reads can wedge it for
    good).
    """
    result: dict = {}

    def _do() -> None:
        try:
            ok, frame = cap.read()
            result["ok"] = ok
            result["frame"] = frame
        except Exception:
            result.setdefault("ok", False)

    t = threading.Thread(target=_do, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return False, None, t
    return bool(result.get("ok", False)), result.get("frame"), t


def _bounded_read(cap, timeout: float = READ_TIMEOUT):
    """``cap.read()`` with a time limit → ``(ok, frame)``."""
    ok, frame, _t = _bounded_read_ex(cap, timeout)
    return ok, frame


def _bounded_open(index: int, backend: int,
                  timeout: float = OPEN_TIMEOUT_PROBE):
    """``cv2.VideoCapture`` with a time limit; ``None`` if it stalls/fails."""
    cap = bounded_call(lambda: cv2.VideoCapture(index, backend), timeout)
    if cap is None or not cap.isOpened():
        _safe_release(cap)
        return None
    return cap


def _probe_index(index: int, reads: int = 4,
                 timeout: float = READ_TIMEOUT) -> Optional[tuple[int, int, float]]:
    """Score `index` across backends by usable frames and read latency.

    A stall-prone driver (slow ``read()`` with many black frames) gets a low
    score even when one lottery frame occasionally passes validation. Once a
    backend delivers two usable frames it is accepted immediately so we never
    pay a long stall on a second backend.

    Returns ``(index, backend, score)`` of the best backend, or ``None``.
    """
    best_score: Optional[float] = None
    best: Optional[tuple[int, int, float]] = None
    for backend in _probing_backends():
        cap = _bounded_open(index, backend)
        if cap is None:
            continue
        apply_exposure(cap)
        usable = 0
        total = 0.0
        done = 0
        for _ in range(reads):
            start = time.monotonic()
            ok, frame = _bounded_read(cap, timeout)
            total += time.monotonic() - start
            done += 1
            if ok and is_frame_usable(frame):
                usable += 1
                if usable >= 2:  # solid stream confirmed -> stop probing
                    break
            time.sleep(0.05)
        _safe_release(cap)
        if usable == 0:
            continue
        score = usable - (total / max(1, done))
        if best_score is None or score > best_score:
            best_score = score
            best = (index, backend, score)
        if usable >= 2:
            break  # good enough, don't pay the slot on remaining backends
    if best is not None:
        log.info("camera %s backend %s score %.2f", best[0], best[1], best[2])
    return best


# Resolution cache: request_index -> (timestamp, chosen_index, chosen_backend).
_CHOICE_CACHE: dict[int, tuple[float, int, Optional[int]]] = {}


def resolve_camera(preferred: int = 0, max_index: int = 4,
                   use_cache: bool = True) -> tuple[int, Optional[int]]:
    """Return ``(index, backend)`` of the best camera found.

    ``preferred`` is probed first, then ``0..max_index``. Each candidate is
    scored by usable-frame count minus average read latency, so a fast steady
    stream beats a slow camera that delivers the occasional good frame. The
    whole scan is bounded in wall-clock time so a bad driver can never stall
    startup beyond ~8 s.

    Returns ``(-1, None)`` when no camera delivers any usable frames at all.
    """
    if not HAVE_CV2:
        return -1, None
    now = time.monotonic()
    if use_cache:
        hit = _CHOICE_CACHE.get(preferred)
        if hit is not None and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1], hit[2]

    best: Optional[tuple[int, int, float]] = None
    deadline = time.monotonic() + SCAN_DEADLINE
    try:
        openable = set(enumerate_cameras(max_index, timeout=0.8))
    except Exception:
        openable = None
    for i in [preferred] + [n for n in range(max_index + 1) if n != preferred]:
        if time.monotonic() > deadline:
            break
        if openable is not None and i not in openable:
            continue
        result = _probe_index(i)
        if result is None:
            continue
        if best is None or result[2] > best[2]:
            best = result
        if best[2] >= 2.0:  # a solid stream is enough, stop scanning
            break

    # Hedge: if nothing opened within the short enumeration window (e.g. the
    # sole webcam is slow to initialise), still probe the preferred index.
    if best is None and openable == set():
        result = _probe_index(preferred)
        if result is not None:
            best = result

    # Accept any camera that delivered at least one usable frame during
    # the probe.  Score is only used to rank which camera is best, not to
    # reject entirely — a borderline webcam still shows *something* in the
    # preview rather than a blank screen.
    if best is not None:
        choice = (best[0], best[1])
    else:
        choice = (-1, None)
    _CHOICE_CACHE[preferred] = (time.monotonic(), choice[0], choice[1])
    return choice


def find_best_camera(preferred: int = 0, max_index: int = 4,
                     use_cache: bool = True) -> int:
    """Return the index of the first camera that delivers usable frames."""
    return resolve_camera(preferred, max_index, use_cache)[0]


def enumerate_cameras(max_index: int = 1, timeout: float = 0.8) -> list[int]:
    """Return camera indices that can be opened quickly (any backend).

    Bounded per-open by `timeout` and overall by a short wall-clock cap so a
    stalling driver on a phantom index can never slow discovery much.
    """
    if not HAVE_CV2:
        return []
    available = []
    deadline = time.monotonic() + 3.0
    for i in range(max_index + 1):
        if time.monotonic() > deadline:
            break
        for backend in _backends():
            cap = _bounded_open(i, backend, timeout)
            if cap is not None:
                available.append(i)
                _safe_release(cap)
                break
    return available


def resolve_camera_index(preferred: int = 0) -> int:
    return find_best_camera(preferred=preferred)


def apply_camera_settings(settings: Settings = SETTINGS) -> None:
    pass  # settings applied by CameraManager on open