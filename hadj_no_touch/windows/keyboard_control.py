"""Real Windows keyboard control (keybd_event / key codes + Unicode SendInput)."""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time

from ..logging_setup import get_logger

log = get_logger("windows.keyboard")

user32 = ctypes.windll.user32

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_EXTENDEDKEY = 0x0001

VK = {
    "BACK": 0x08, "BACKSPACE": 0x08, "TAB": 0x09, "CLEAR": 0x0C,
    "ENTER": 0x0D, "RETURN": 0x0D, "SHIFT": 0x10, "CTRL": 0x11,
    "LCTRL": 0xA2, "RCTRL": 0xA3, "LSHIFT": 0xA0, "RSHIFT": 0xA1,
    "ALT": 0x12, "LALT": 0xA4, "RALT": 0xA5, "ESC": 0x1B, "ESCAPE": 0x1B,
    "SPACE": 0x20, "PAGEUP": 0x21, "PAGEDOWN": 0x22, "END": 0x23,
    "HOME": 0x24, "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "PRINTSCREEN": 0x2C, "INSERT": 0x2D, "DELETE": 0x2E,
    "WIN": 0x5B, "LWIN": 0x5B, "RWIN": 0x5C, "MENU": 0x5D,
    "CAPSLOCK": 0x14, "NUMLOCK": 0x90, "SCROLLLOCK": 0x91,
    "PAUSE": 0x13, "BREAK": 0x13, "BACKSLASH": 0xDC, "SLASH": 0xBF,
    "SEMICOLON": 0xBA, "QUOTE": 0xDE, "COMMA": 0xBC, "PERIOD": 0xBE,
    "MINUS": 0xBD, "EQUAL": 0xBB, "TILDE": 0xC0, "OPENBRACKET": 0xDB,
    "CLOSEBRACKET": 0xDD,
}

for _i in range(1, 25):
    VK[f"F{_i}"] = 0x70 + (_i - 1)


def _vk(name: str) -> int:
    n = name.upper().replace(" ", "")
    if len(n) == 1 and n.isalpha():
        return ord(n.upper())
    if len(n) == 1 and n.isdigit():
        return ord(n)
    if n in VK:
        return VK[n]
    return ord(n)  # assume 'A'-'Z'


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


def _send_key(vk: int, up: bool, scan: int = 0, is_unicode: bool = False, extended: bool = False) -> None:
    extra = wt.ULONG(0)
    ki = _KEYBDINPUT()
    ki.wVk = vk & 0xFFFF
    ki.wScan = scan
    ki.dwFlags = int(up)
    if is_unicode:
        ki.dwFlags |= KEYEVENTF_UNICODE
    if extended:
        ki.dwFlags |= KEYEVENTF_EXTENDEDKEY
    ki.time = 0
    ki.dwExtraInfo = ctypes.cast(ctypes.byref(extra), ctypes.POINTER(ctypes.c_ulong))

    class _INPT(ctypes.Structure):
        _fields_ = [("type", wt.DWORD), ("ki", _KEYBDINPUT)]

    inp = _INPT()
    inp.type = 1
    inp.ki = ki
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPT))


def tap(name: str, modifiers: list[str] | None = None, repeat: int = 1) -> None:
    mods = [("LCTRL" if m.upper() in ("CTRL", "CONTROL") else m.upper()) for m in (modifiers or [])]
    for m in mods:
        _send_key(_vk(m), False, extended=(m == "WIN"))
    single = len(name) == 1
    vk = _vk(name)
    scan = ord(name) if single else 0
    for _ in range(max(1, repeat)):
        _send_key(vk, False, scan=scan)
        _send_key(vk, True, scan=scan)
    for m in reversed(mods):
        _send_key(_vk(m), True, extended=(m == "WIN"))


def press(name: str, hold_ms: int = 500) -> None:
    _send_key(_vk(name), False)
    time.sleep(hold_ms / 1000.0)
    _send_key(_vk(name), True)


def type_text(text: str) -> None:
    """Type arbitrary text (Unicode) by sending KEYEVENTF_UNICODE events."""
    for ch in text:
        code = ord(ch)
        _send_key(0, False, scan=code, is_unicode=True)
        _send_key(0, True, scan=code, is_unicode=True)


def hotkey(*names: str) -> None:
    name = names[-1]
    mods = list(names[:-1])
    tap(name, mods)