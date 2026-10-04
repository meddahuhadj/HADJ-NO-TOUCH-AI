"""أسماء المفاتيح الموحّدة في التطبيق (كما في os_layer/windows/input.py) ← أسماء keysym في X11.

منطق بحت بلا Xlib: يُختبر على أي نظام.
"""
from __future__ import annotations

# نفس الأسماء التي تستخدمها الأوامر والماكرو على Windows
NAMED = {
    "backspace": "BackSpace", "tab": "Tab", "enter": "Return", "return": "Return",
    "shift": "Shift_L", "ctrl": "Control_L", "control": "Control_L", "alt": "Alt_L",
    "pause": "Pause", "capslock": "Caps_Lock", "esc": "Escape", "escape": "Escape",
    "space": "space", "pageup": "Prior", "pagedown": "Next", "end": "End", "home": "Home",
    "left": "Left", "up": "Up", "right": "Right", "down": "Down", "printscreen": "Print",
    "insert": "Insert", "delete": "Delete", "del": "Delete", "win": "Super_L", "lwin": "Super_L",
    "rwin": "Super_R", "apps": "Menu", "menu": "Menu",
    "volume_mute": "XF86AudioMute", "volume_down": "XF86AudioLowerVolume",
    "volume_up": "XF86AudioRaiseVolume", "media_next": "XF86AudioNext",
    "media_prev": "XF86AudioPrev", "media_stop": "XF86AudioStop",
    "media_play_pause": "XF86AudioPlay",
    "plus": "plus", "comma": "comma", "minus": "minus", "period": "period",
}
NAMED.update({f"f{i}": f"F{i}" for i in range(1, 25)})
NAMED.update({chr(c): chr(c) for c in range(ord("a"), ord("z") + 1)})
NAMED.update({str(d): str(d) for d in range(10)})

MODIFIERS = ("ctrl", "shift", "alt", "win")

# محارف لها اسم keysym مختلف عن نفسها (اللاتينية الأساسية)
_PUNCT = {
    " ": "space", "!": "exclam", '"': "quotedbl", "#": "numbersign", "$": "dollar",
    "%": "percent", "&": "ampersand", "'": "apostrophe", "(": "parenleft", ")": "parenright",
    "*": "asterisk", "+": "plus", ",": "comma", "-": "minus", ".": "period", "/": "slash",
    ":": "colon", ";": "semicolon", "<": "less", "=": "equal", ">": "greater", "?": "question",
    "@": "at", "[": "bracketleft", "\\": "backslash", "]": "bracketright", "^": "asciicircum",
    "_": "underscore", "`": "grave", "{": "braceleft", "|": "bar", "}": "braceright",
    "~": "asciitilde", "\n": "Return", "\t": "Tab",
}


def keysym_name(key: str) -> str:
    """اسم المفتاح في التطبيق ← اسم keysym. ValueError لمفتاح مجهول (كما على Windows)."""
    k = key.lower().strip()
    if k not in NAMED:
        raise ValueError(f"مفتاح غير معروف: {key!r}")
    return NAMED[k]


def char_keysym(ch: str) -> int:
    """رقم keysym لمحرف واحد. يونيكود خارج Latin-1: 0x01000000 + نقطة الترميز (معيار X11)."""
    from_named = _PUNCT.get(ch)
    if from_named is not None:
        return _STANDARD_CODES.get(from_named, ord(ch))
    cp = ord(ch)
    if 0x20 <= cp <= 0x7E or 0xA0 <= cp <= 0xFF:
        return cp                       # Latin-1: keysym = نقطة الترميز
    return 0x01000000 + cp


# قيم keysym الثابتة للأسماء التي تختلف فيها القيمة عن نقطة الترميز
_STANDARD_CODES = {"Return": 0xFF0D, "Tab": 0xFF09}
