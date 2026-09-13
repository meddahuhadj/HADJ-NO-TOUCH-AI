"""Media / volume control for Windows (virtual key codes + optional pycaw)."""

from __future__ import annotations

import time

from ..logging_setup import get_logger
from . import keyboard_control

log = get_logger("windows.media")

KEY_MEDIA_NEXT_TRACK = 0xB0
KEY_MEDIA_PREV_TRACK = 0xB1
KEY_MEDIA_STOP = 0xB2
KEY_MEDIA_PLAY_PAUSE = 0xB3
KEY_VOLUME_MUTE = 0xAD
KEY_VOLUME_DOWN = 0xAE
KEY_VOLUME_UP = 0xAF

try:
    from ctypes import POINTER, cast, windll
    from comtypes import CLSCTX_ALL  # type: ignore
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore
    _HAVE_PYCAW = True
except Exception:
    _HAVE_PYCAW = False


def play_pause() -> None:
    keyboard_control._send_key(KEY_MEDIA_PLAY_PAUSE, False)
    keyboard_control._send_key(KEY_MEDIA_PLAY_PAUSE, True)


def next_track() -> None:
    keyboard_control._send_key(KEY_MEDIA_NEXT_TRACK, False)
    keyboard_control._send_key(KEY_MEDIA_NEXT_TRACK, True)


def prev_track() -> None:
    keyboard_control._send_key(KEY_MEDIA_PREV_TRACK, False)
    keyboard_control._send_key(KEY_MEDIA_PREV_TRACK, True)


def stop_media() -> None:
    keyboard_control._send_key(KEY_MEDIA_STOP, False)
    keyboard_control._send_key(KEY_MEDIA_STOP, True)


def volume_up(steps: int = 1) -> None:
    for _ in range(max(1, steps)):
        keyboard_control._send_key(KEY_VOLUME_UP, False)
        keyboard_control._send_key(KEY_VOLUME_UP, True)
        time.sleep(0.01)


def volume_down(steps: int = 1) -> None:
    for _ in range(max(1, steps)):
        keyboard_control._send_key(KEY_VOLUME_DOWN, False)
        keyboard_control._send_key(KEY_VOLUME_DOWN, True)
        time.sleep(0.01)


def mute() -> None:
    keyboard_control._send_key(KEY_VOLUME_MUTE, False)
    keyboard_control._send_key(KEY_VOLUME_MUTE, True)


def _get_endpoint():
    if not _HAVE_PYCAW:
        return None
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception:
        return None


def set_volume_percent(percent: float) -> None:
    """Set system master volume to ``percent`` (0..100). Real when pycaw is
    available; otherwise approximated with repeated volume key taps."""
    percent = max(0.0, min(100.0, float(percent)))
    vol = _get_endpoint()
    if vol is not None:
        try:
            vol.SetMasterVolumeLevelScalar(percent / 100.0, None)
            return
        except Exception:
            pass
    # Fallback: key taps. Use the current scalar if pycaw can read it.
    vol = _get_endpoint()
    if vol is not None:
        try:
            current = vol.GetMasterVolumeLevelScalar() * 100.0
            delta = int(round((percent - current) / 2.0))
            if delta > 0:
                volume_up(delta)
            elif delta < 0:
                volume_down(-delta)
            return
        except Exception:
            pass
    volume_fallback_ratio(percent)


def volume_fallback_ratio(percent: float) -> None:
    """Nudge volume toward a target using key taps (no API available)."""
    percent = max(0.0, min(100.0, float(percent)))
    # Repeated taps approximate absolute set.
    for _ in range(int(percent // 2)):
        keyboard_control._send_key(KEY_VOLUME_UP, False)
        keyboard_control._send_key(KEY_VOLUME_UP, True)


def volume_status() -> str:
    vol = _get_endpoint()
    if vol is not None:
        try:
            pct = int(round(vol.GetMasterVolumeLevelScalar() * 100.0))
            return f"{pct}%"
        except Exception:
            return "?"
    return "n/a (pycaw missing)"