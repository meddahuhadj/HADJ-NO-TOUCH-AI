"""إدخال لوحة المفاتيح والفأرة عبر SendInput (ctypes)، دون مكتبات وسيطة."""
from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x1, 0x2, 0x4
MOUSEEVENTF = {
    ("left", "down"): 0x0002, ("left", "up"): 0x0004,
    ("right", "down"): 0x0008, ("right", "up"): 0x0010,
    ("middle", "down"): 0x0020, ("middle", "up"): 0x0040,
}
MOUSEEVENTF_WHEEL, MOUSEEVENTF_HWHEEL = 0x0800, 0x1000
WHEEL_DELTA = 120


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT

VK = {
    "backspace": 0x08, "tab": 0x09, "enter": 0x0D, "return": 0x0D, "shift": 0x10, "ctrl": 0x11,
    "control": 0x11, "alt": 0x12, "pause": 0x13, "capslock": 0x14, "esc": 0x1B, "escape": 0x1B,
    "space": 0x20, "pageup": 0x21, "pagedown": 0x22, "end": 0x23, "home": 0x24, "left": 0x25,
    "up": 0x26, "right": 0x27, "down": 0x28, "printscreen": 0x2C, "insert": 0x2D, "delete": 0x2E,
    "del": 0x2E, "win": 0x5B, "lwin": 0x5B, "rwin": 0x5C, "apps": 0x5D, "menu": 0x5D,
    "volume_mute": 0xAD, "volume_down": 0xAE, "volume_up": 0xAF,
    "media_next": 0xB0, "media_prev": 0xB1, "media_stop": 0xB2, "media_play_pause": 0xB3,
    "plus": 0xBB, "comma": 0xBC, "minus": 0xBD, "period": 0xBE,
}
VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})
VK.update({chr(c): c - 32 for c in range(ord("a"), ord("z") + 1)})
VK.update({str(d): 0x30 + d for d in range(10)})

EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2C, 0x2D, 0x2E, 0x5B, 0x5C, 0x5D,
            0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB2, 0xB3}
MODIFIERS = ("ctrl", "shift", "alt", "win")


def vk_code(key: str) -> int:
    k = key.lower().strip()
    if k not in VK:
        raise ValueError(f"مفتاح غير معروف: {key!r}")
    return VK[k]


def _key_input(vk: int, up: bool) -> INPUT:
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED else 0)
    return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags))


def _unicode_input(code_unit: int, up: bool) -> INPUT:
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
    return INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=code_unit, dwFlags=flags))


def send(inputs: list[INPUT]) -> None:
    if not inputs:
        return
    arr = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        raise ctypes.WinError(ctypes.get_last_error())


def press_keys(keys: list[str]) -> None:
    """ضغط مجموعة مفاتيح معاً ثم تحريرها بالترتيب العكسي (مثل ctrl+c)."""
    codes = [vk_code(k) for k in keys]
    send([_key_input(c, False) for c in codes] + [_key_input(c, True) for c in reversed(codes)])


def type_unicode(text: str) -> None:
    events: list[INPUT] = []
    for ch in text:
        if ch == "\n":
            events += [_key_input(0x0D, False), _key_input(0x0D, True)]
            continue
        if ch == "\t":
            events += [_key_input(0x09, False), _key_input(0x09, True)]
            continue
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i:i + 2], "little")
            events += [_unicode_input(unit, False), _unicode_input(unit, True)]
    # دفعات صغيرة حتى لا تضيع أحرف في بعض التطبيقات
    for i in range(0, len(events), 64):
        send(events[i:i + 64])


def key_up(keys: list[str]) -> None:
    send([_key_input(vk_code(k), True) for k in keys])


def mouse_button(button: str, action: str) -> None:
    send([INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dwFlags=MOUSEEVENTF[(button, action)]))])


def mouse_wheel(notches: int, horizontal: bool = False, ctrl: bool = False) -> None:
    flag = MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL
    data = ctypes.c_uint32(notches * WHEEL_DELTA).value  # قيمة سالبة ← unsigned
    wheel = INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(mouseData=data, dwFlags=flag))
    if ctrl:  # دفعة واحدة: لا يبقى Ctrl مضغوطاً حتى لو حدث خطأ بعدها
        send([_key_input(VK["ctrl"], False), wheel, _key_input(VK["ctrl"], True)])
    else:
        send([wheel])


def set_cursor(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def get_cursor() -> tuple[int, int]:
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y
