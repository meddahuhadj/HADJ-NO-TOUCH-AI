"""Camera configuration helpers and device enumeration."""

from __future__ import annotations

from ..config import Settings, SETTINGS
from ..logging_setup import get_logger

log = get_logger("camera.config")

try:
    import cv2
    HAVE_CV2 = True
except Exception:
    HAVE_CV2 = False


def enumerate_cameras(max_index: int = 5) -> list[int]:
    """Return a list of valid camera indices by opening each one briefly."""
    if not HAVE_CV2:
        return []
    available = []
    for i in range(max_index + 1):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        ok = cap.isOpened()
        if ok:
            available.append(i)
            cap.release()
    return available


def resolve_camera_index(preferred: int = 0) -> int:
    cams = enumerate_cameras()
    if not cams:
        return -1
    if preferred in cams:
        return preferred
    return cams[0]


def apply_camera_settings(settings: Settings = SETTINGS) -> None:
    pass  # settings applied by CameraManager on open