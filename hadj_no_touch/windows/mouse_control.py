"""Real Windows mouse control (ctypes / SendInput)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time

from ..logging_setup import get_logger

log = get_logger("windows.mouse")

user32 = ctypes.windll.user32

# Structures for SendInput
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000
MOUSEEVENTF_ABSOLUTE = 0x8000


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG),
        ("dy", wt.LONG),
        ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wt.DWORD),
        ("wParamL", wt.WORD),
        ("wParamH", wt.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("union", _INPUTUNION)]


def _send_mouse(dx: int, dy: int, flags: int, data: int = 0) -> None:
    extra = wt.ULONG(0)
    inp = _INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi.dx = int(dx)
    inp.union.mi.dy = int(dy)
    inp.union.mi.mouseData = int(data)
    inp.union.mi.dwFlags = int(flags)
    inp.union.mi.time = 0
    inp.union.mi.dwExtraInfo = ctypes.cast(ctypes.byref(extra), ctypes.POINTER(ctypes.c_ulong))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def get_position() -> tuple[int, int]:
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def move_to(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def move_by(dx: int, dy: int, relative: bool = False) -> None:
    if relative:
        _send_mouse(int(dx), int(dy), MOUSEEVENTF_MOVE)
    else:
        move_to(dx, dy)


def _left_click_down() -> None:
    _send_mouse(0, 0, MOUSEEVENTF_LEFTDOWN)


def _left_click_up() -> None:
    _send_mouse(0, 0, MOUSEEVENTF_LEFTUP)


def click_left(x: int | None = None, y: int | None = None) -> None:
    if x is not None and y is not None:
        move_to(x, y)
    _send_mouse(0, 0, MOUSEEVENTF_LEFTDOWN)
    _send_mouse(0, 0, MOUSEEVENTF_LEFTUP)


def click_right(x: int | None = None, y: int | None = None) -> None:
    if x is not None and y is not None:
        move_to(x, y)
    _send_mouse(0, 0, MOUSEEVENTF_RIGHTDOWN)
    _send_mouse(0, 0, MOUSEEVENTF_RIGHTUP)


def click_middle(x: int | None = None, y: int | None = None) -> None:
    if x is not None and y is not None:
        move_to(x, y)
    _send_mouse(0, 0, MOUSEEVENTF_MIDDLEDOWN)
    _send_mouse(0, 0, MOUSEEVENTF_MIDDLEUP)


def double_click(x: int | None = None, y: int | None = None) -> None:
    if x is not None and y is not None:
        move_to(x, y)
    click_left()
    time.sleep(0.03)
    click_left()


def scroll(amount: int, horizontal: bool = False) -> None:
    flags = MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL
    data = int(amount * 120)
    _send_mouse(0, 0, flags, data)


def drag(from_xy: tuple[int, int], to_xy: tuple[int, int], steps: int = 12) -> None:
    move_to(*from_xy)
    time.sleep(0.02)
    _send_mouse(0, 0, MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.02)
    x0, y0 = from_xy
    x1, y1 = to_xy
    for i in range(1, steps + 1):
        t = i / steps
        move_to(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t))
        time.sleep(0.008)
    time.sleep(0.02)
    _send_mouse(0, 0, MOUSEEVENTF_LEFTUP)


class HoldingClick:
    """Context manager that holds the left button (for real-time drag)."""

    def __init__(self) -> None:
        self._active = False

    def start(self) -> None:
        if not self._active:
            _send_mouse(0, 0, MOUSEEVENTF_LEFTDOWN)
            self._active = True

    def update(self, x: int, y: int) -> None:
        if self._active:
            move_to(x, y)

    def stop(self) -> None:
        if self._active:
            _send_mouse(0, 0, MOUSEEVENTF_LEFTUP)
            self._active = False

    @property
    def active(self) -> bool:
        return self._active


def screen_size() -> tuple[int, int]:
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return int(w), int(h)