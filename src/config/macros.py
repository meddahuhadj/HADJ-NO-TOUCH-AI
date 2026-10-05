"""الماكرو: عبارة (و/أو إيماءة) ← سلسلة خطوات بسيطة (مفاتيح، نص، انتظار، نقر، تمرير).

تُحفظ في user_data/macros.yaml وتُنشأ من الواجهة دون تعديل أي ملف يدوياً.
كل ماكرو يمر بنفس الفحص سواء جاء من الواجهة أو من ملف عُدّل يدوياً:
- خطوات معروفة فقط، بحدود (عدد الخطوات، طول النص، مدة الانتظار).
- لا يحتوي اختصار الإيقاف الطارئ (وإلا قد يستأنف التحكم بدل أن يوقفه).
- اختصارات مدمّرة (Delete، Alt+F4، Ctrl+W…) ← تأكيد "نعم/لا" إجباري لا يمكن إلغاؤه.
- الماكرو الخطِر لا يُربط بإيماءة (الإيماءة لا تسأل).
- العبارة لا تكرر عبارة أمر موجود (وإلا لن يُنفَّذ أحدهما أبداً).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from core import paths

log = logging.getLogger(__name__)

FILE = "macros.yaml"
PREFIX = "macro."
LANGS = ("ar", "fr", "en")
MAX_STEPS = 20
MAX_TEXT = 500
MAX_WAIT_MS = 5000
MODIFIERS = ("ctrl", "alt", "shift", "win")
KEYS = ([chr(c) for c in range(ord("a"), ord("z") + 1)] + [str(d) for d in range(10)]
        + [f"f{i}" for i in range(1, 13)]
        + ["enter", "tab", "escape", "space", "backspace", "delete", "insert", "home", "end",
           "pageup", "pagedown", "up", "down", "left", "right", "printscreen", "plus", "minus",
           "comma", "period", "apps"])
# أنواع الخطوات في المحرر ← إجراء مسجّل
STEP_KINDS = ("keys", "text", "wait", "click", "double_click", "right_click", "scroll_up", "scroll_down")
# اختصارات تحذف أو تغلق دون رجعة (تُقارن بعد ترتيب المفاتيح)
DESTRUCTIVE = [{"delete"}, {"shift", "delete"}, {"ctrl", "delete"}, {"ctrl", "shift", "delete"},
               {"alt", "f4"}, {"ctrl", "w"}, {"ctrl", "shift", "w"}, {"ctrl", "f4"},
               {"ctrl", "alt", "delete"}, {"win", "l"}]


class MacroError(ValueError):
    """key: مفتاح ترجمة للواجهة؛ values: قيم النص."""

    def __init__(self, key: str, **values):
        super().__init__(f"{key}: {values}")
        self.key, self.values = key, values


def parse_combo(combo: str) -> list[str]:
    keys = [k.strip().lower() for k in str(combo).replace(" ", "").split("+")]
    if not keys or any(not k for k in keys):   # "ctrl+" ناقص: لا يُقبل كـ Ctrl وحده
        raise MacroError("macro_bad_keys", keys=combo)
    *mods, main = keys
    if any(m not in MODIFIERS for m in mods) or len(set(mods)) != len(mods):
        raise MacroError("macro_bad_keys", keys=combo)
    if main not in KEYS and main not in MODIFIERS:
        raise MacroError("macro_bad_keys", keys=combo)
    order = {m: i for i, m in enumerate(MODIFIERS)}
    return sorted(mods, key=order.__getitem__) + [main]


def combo_text(keys: list[str]) -> str:
    return "+".join(keys)


def step_to_action(step: dict) -> dict:
    """خطوة المحرر ← خطوة تنفيذ (نفس شكل steps في ملف الأوامر)."""
    kind = step.get("kind")
    if kind == "keys":
        keys = parse_combo(step.get("keys", ""))
        return {"action": "hotkey", "keys": combo_text(keys)} if len(keys) > 1 else \
            {"action": "key", "key": keys[0]}
    if kind == "text":
        text = str(step.get("text", ""))
        if not text or len(text) > MAX_TEXT:
            raise MacroError("macro_bad_text", n=MAX_TEXT)
        return {"action": "type_text", "text": text}
    if kind == "wait":
        ms = int(step.get("ms", 300))
        if not 50 <= ms <= MAX_WAIT_MS:
            raise MacroError("macro_bad_wait", max=MAX_WAIT_MS)
        return {"action": "wait", "ms": ms}
    if kind in ("click", "double_click", "right_click"):
        return {"action": kind}
    if kind in ("scroll_up", "scroll_down"):
        return {"action": "scroll", "direction": kind.split("_")[1]}
    raise MacroError("macro_bad_step", kind=kind)


def action_to_step(a: dict) -> dict:
    """العكس، لعرض ماكرو محفوظ في المحرر."""
    name = a.get("action")
    if name == "hotkey":
        return {"kind": "keys", "keys": a.get("keys", "")}
    if name == "key":
        return {"kind": "keys", "keys": a.get("key", "")}
    if name == "type_text":
        return {"kind": "text", "text": a.get("text", "")}
    if name == "wait":
        return {"kind": "wait", "ms": int(a.get("ms", 300))}
    if name == "scroll":
        return {"kind": f"scroll_{a.get('direction', 'down')}"}
    if name in ("click", "double_click", "right_click"):
        return {"kind": name}
    raise MacroError("macro_bad_step", kind=name)


def is_destructive(steps: list[dict]) -> bool:
    for s in steps:
        if s.get("action") in ("key", "hotkey"):
            keys = set(parse_combo(s.get("keys") or s.get("key") or ""))
            if keys in DESTRUCTIVE:
                return True
    return False


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "_", text.lower()).strip("_")
    return s[:40] or "macro"


def build_macro(data: dict, phrase_owner: dict[tuple[str, str], str],
                emergency_hotkey: str = "", taken_ids=()) -> dict:
    """يتحقق من ماكرو (من الواجهة أو الملف) ويرجع مواصفة أمر جاهزة للمحلل.

    data: {id?, phrases: {lang: str|[str]}, steps: [خطوة محرر أو خطوة تنفيذ], dangerous?, gesture?}
    phrase_owner: (لغة، عبارة مطبّعة) ← معرّف الأمر صاحبها (لكشف التكرار).
    """
    from commands.parser import normalize
    phrases: dict[str, list[str]] = {}
    for lang, v in (data.get("phrases") or {}).items():
        if lang not in LANGS:
            continue
        items = [v] if isinstance(v, str) else list(v or [])
        items = [p.strip() for p in items if isinstance(p, str) and p.strip()]
        if items:
            phrases[lang] = items
    gesture = data.get("gesture") or ""
    if not phrases and not gesture:
        raise MacroError("macro_no_trigger")
    if gesture:
        from config.profiles import GESTURES, PROTECTED_BINDINGS
        if gesture not in GESTURES or gesture in PROTECTED_BINDINGS:
            raise MacroError("macro_bad_gesture", gesture=gesture)

    mid = data.get("id") or ""
    if not mid.startswith(PREFIX):
        first = next(iter(phrases.values()), [gesture])[0]
        base = PREFIX + slug(first if re.search(r"[a-z0-9]", first.lower()) else mid or "macro")
        mid, n = base, 2
        while mid in taken_ids:
            mid, n = f"{base}_{n}", n + 1
    for lang, items in phrases.items():
        for p in items:
            if "{" in p or "}" in p:
                raise MacroError("macro_bad_phrase", phrase=p)
            owner = phrase_owner.get((lang, normalize(p)))
            if owner and owner != mid:
                raise MacroError("macro_phrase_taken", phrase=p, owner=owner)

    raw = data.get("steps") or []
    if not raw:
        raise MacroError("macro_no_steps")
    if len(raw) > MAX_STEPS:
        raise MacroError("macro_too_many", n=MAX_STEPS)
    steps = [step_to_action(s) if "kind" in s else step_to_action(action_to_step(s)) for s in raw]

    if emergency_hotkey:
        try:
            emergency = set(parse_combo(emergency_hotkey))
        except MacroError:
            emergency = set()
        for s in steps:
            if s["action"] in ("key", "hotkey") and \
                    set(parse_combo(s.get("keys") or s.get("key"))) == emergency:
                raise MacroError("macro_emergency_key", keys=emergency_hotkey)

    dangerous = bool(data.get("dangerous")) or is_destructive(steps)
    if dangerous and gesture:
        raise MacroError("macro_gesture_dangerous")
    spec = {"id": mid, "phrases": phrases, "steps": steps}
    if dangerous:
        spec["dangerous"] = True
    if gesture:
        spec["gesture"] = gesture
    return spec


def phrase_owners(specs: list[dict]) -> dict[tuple[str, str], str]:
    from commands.parser import normalize
    out: dict[tuple[str, str], str] = {}
    for s in specs:
        for lang, items in (s.get("phrases") or {}).items():
            for p in items:
                out.setdefault((lang, normalize(p)), s.get("id", ""))
    return out


# ---------------------------------------------------------------- الملف
def macros_path(user_dir: Path | None = None) -> Path:
    return (user_dir or paths.user_dir()) / FILE


def load_macros(other_specs: list[dict], emergency_hotkey: str = "",
                user_dir: Path | None = None) -> list[dict]:
    """يقرأ الملف ويتحقق من كل ماكرو؛ غير الصالح يُتجاهل مع تسجيل السبب."""
    path = macros_path(user_dir)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            raw = (yaml.safe_load(f) or {}).get("macros", [])
    except (yaml.YAMLError, OSError, AttributeError) as e:
        log.error("ملف الماكرو غير صالح (%s): %s", path, e)
        return []
    owners = phrase_owners(other_specs)
    out: list[dict] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            spec = build_macro(item, owners, emergency_hotkey, {m["id"] for m in out})
        except (MacroError, TypeError, ValueError, AttributeError) as e:
            log.error("تم تجاهل ماكرو غير صالح %r: %s", (item or {}).get("id"), e)
            continue
        owners.update(phrase_owners([spec]))
        out.append(spec)
    return out


def save_macros(macros: list[dict], user_dir: Path | None = None) -> Path:
    path = macros_path(user_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"macros": macros}, f, allow_unicode=True, sort_keys=False)
    return path


def bindings_for(macros: list[dict]) -> dict[str, str]:
    """إيماءة ← cmd:macro.x (لا تشمل الخطرة أبداً: build_macro يمنعها)."""
    return {m["gesture"]: f"cmd:{m['id']}" for m in macros if m.get("gesture") and not m.get("dangerous")}
