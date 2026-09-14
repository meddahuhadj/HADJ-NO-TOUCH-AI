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
    "BACK": 0x08, "BACKSPACE": 0x08, "BS": 0x08,
    "TAB": 0x09, "CLEAR": 0x0C,
    "ENTER": 0x0D, "RETURN": 0x0D,
    "SHIFT": 0x10, "LSHIFT": 0xA0, "RSHIFT": 0xA1,
    "CTRL": 0x11, "CONTROL": 0x11, "LCTRL": 0xA2, "RCTRL": 0xA3,
    "ALT": 0x12, "OPTION": 0x12, "LALT": 0xA4, "RALT": 0xA5, "ALTGR": 0xA5,
    "ESC": 0x1B, "ESCAPE": 0x1B,
    "SPACE": 0x20,
    "PAGEUP": 0x21, "PGUP": 0x21, "PAGE_UP": 0x21, "PRIOR": 0x21,
    "PAGEDOWN": 0x22, "PGDN": 0x22, "PGDOWN": 0x22, "PAGE_DOWN": 0x22, "NEXT": 0x22,
    "END": 0x23, "HOME": 0x24,
    "LEFT": 0x25, "UP": 0x26, "RIGHT": 0x27, "DOWN": 0x28,
    "PRINTSCREEN": 0x2C, "PRTSCN": 0x2C,
    "INSERT": 0x2D, "INS": 0x2D,
    "DELETE": 0x2E, "DEL": 0x2E,
    "WIN": 0x5B, "LWIN": 0x5B, "RWIN": 0x5C, "CMD": 0x5B, "COMMAND": 0x5B, "SUPER": 0x5B, "MENU": 0x5D,
    "CAPSLOCK": 0x14, "NUMLOCK": 0x90, "SCROLLLOCK": 0x91,
    "PAUSE": 0x13, "BREAK": 0x13,
    "BACKSLASH": 0xDC, "\\": 0xDC,
    "SLASH": 0xBF, "/": 0xBF,
    "SEMICOLON": 0xBA, ";": 0xBA,
    "QUOTE": 0xDE, "'": 0xDE,
    "COMMA": 0xBC, ",": 0xBC,
    "PERIOD": 0xBE, ".": 0xBE,
    "MINUS": 0xBD, "-": 0xBD, "_": 0xBD,
    "EQUAL": 0xBB, "=": 0xBB, "+": 0xBB,
    "TILDE": 0xC0, "`": 0xC0, "~": 0xC0,
    "OPENBRACKET": 0xDB, "[": 0xDB, "{": 0xDB,
    "CLOSEBRACKET": 0xDD, "]": 0xDD, "}": 0xDD,
}

for _i in range(1, 25):
    VK[f"F{_i}"] = 0x70 + (_i - 1)


def _vk(name: str) -> int:
    if name in VK:
        return VK[name]
    n = name.upper().replace(" ", "").replace("_", "")
    if n in VK:
        return VK[n]
    if len(n) == 1 and n.isalpha():
        return ord(n.upper())
    if len(n) == 1 and n.isdigit():
        return ord(n)
    if len(n) == 1:
        return ord(n)
    log.warning("Unknown key name: %r", name)
    return 0


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
    vk = _vk(name)
    if not vk:
        log.warning("Cannot tap unknown key: %r", name)
        return
    mods = [("LCTRL" if m.upper() in ("CTRL", "CONTROL") else m.upper()) for m in (modifiers or [])]
    mod_vks = []
    for m in mods:
        mvk = _vk(m)
        if mvk:
            _send_key(mvk, False, extended=(m == "WIN"))
            mod_vks.append((m, mvk))
    single = len(name) == 1
    scan = ord(name) if single else 0
    for _ in range(max(1, repeat)):
        _send_key(vk, False, scan=scan)
        _send_key(vk, True, scan=scan)
    for m, mvk in reversed(mod_vks):
        _send_key(mvk, True, extended=(m == "WIN"))


def press(name: str, hold_ms: int = 500) -> None:
    vk = _vk(name)
    if not vk:
        log.warning("Cannot press unknown key: %r", name)
        return
    _send_key(vk, False)
    time.sleep(hold_ms / 1000.0)
    _send_key(vk, True)


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