"""الملفات الشخصية السياقية (المطبخ، العروض التقديمية، البث، تصفح الويب…).

الملف الشخصي = تبديلات للإيماءات + أوامر صوتية إضافية تخصّه. ملفات مدمجة للقراءة فقط في
config/profiles/، وملفات المستخدم في user_data/profiles/ (يُنشأ المجلد عند أول حفظ فقط).

قواعد أمان لا يتجاوزها أي ملف (حتى المستورد من شخص آخر):
- القبضة تبقى دائماً الإيقاف الطارئ (fist_hold = app.pause).
- لا يستبدل أمراً أساسياً: أوامر الملف تُسمّى "<id الملف>.<id الأمر>".
- لا أمر بخاصية always (العمل دون كلمة التنبيه حكر على أمر الإيقاف الطارئ).
- الإيماءة لا تُربط بأمر خطِر (الإيماءات تُنفَّذ دون سؤال "نعم/لا").
- إجراءات غير معروفة تُرفض، وحجم الملف المستورد محدود.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from core import paths

log = logging.getLogger(__name__)

STANDARD = "standard"
LANGS = ("ar", "fr", "en")
SUFFIX = ".hadjprofile"
MAX_IMPORT_BYTES = 256 * 1024
MAX_COMMANDS = 100
PROTECTED_BINDINGS = {"fist_hold": "app.pause"}
GESTURES = ("pinch_tap", "middle_pinch_tap", "fist_hold", "palm_hold_long", "two_scroll",
            "swipe_right", "swipe_left", "zoom_in", "zoom_out")
# إجراءات تُنفَّذ داخل عملية الرؤية (ليست في سجل الإجراءات)
VISION_ACTIONS = {"none", "click", "double_click", "right_click", "middle_click", "scroll",
                  "zoom_in", "zoom_out"}
CMD_PREFIX = "cmd:"
# كلمة التبديل الصوتي: "profil cuisine" / "profile kitchen" / "وضع المطبخ"
SWITCH_WORDS = {"ar": ["وضع"], "fr": ["profil"], "en": ["profile"]}


class ProfileError(ValueError):
    """ملف شخصي غير صالح؛ key مفتاح ترجمة للواجهة."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(f"{key}: {detail}")
        self.key, self.detail = key, detail


@dataclass
class Profile:
    id: str
    name: dict[str, str]
    description: dict[str, str] = field(default_factory=dict)
    phrases: dict[str, list[str]] = field(default_factory=dict)   # عبارات تبديل إضافية
    bindings: dict[str, str] = field(default_factory=dict)        # تبديلات فقط (ما لم يُذكر يبقى)
    commands: list[dict] = field(default_factory=list)            # بمعرّفات "<id>.<cmd>"
    builtin: bool = False
    path: Path | None = None

    def label(self, lang: str) -> str:
        return self.name.get(lang) or next(iter(self.name.values()), self.id)

    def to_dict(self) -> dict:
        """الشكل المحفوظ/المصدَّر: معرّفات الأوامر دون البادئة."""
        pre = self.id + "."

        def strip(ref: str) -> str:
            if ref.startswith(CMD_PREFIX + pre):
                return CMD_PREFIX + ref[len(CMD_PREFIX + pre):]
            return ref
        cmds = []
        for c in self.commands:
            c = dict(c)
            c["id"] = c["id"][len(pre):] if c["id"].startswith(pre) else c["id"]
            cmds.append(c)
        out: dict = {"id": self.id, "name": dict(self.name)}
        if self.description:
            out["description"] = dict(self.description)
        if self.phrases:
            out["phrases"] = {k: list(v) for k, v in self.phrases.items()}
        if self.bindings:
            out["bindings"] = {g: strip(a) for g, a in self.bindings.items()}
        if cmds:
            out["commands"] = cmds
        return out


# ---------------------------------------------------------------- مسارات
def builtin_dir() -> Path:
    return paths.resource_dir() / "config" / "profiles"


def user_profiles_dir(user_dir: Path | None = None) -> Path:
    return (user_dir or paths.user_dir()) / "profiles"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9_]+", "-", text.lower()).strip("-_")
    return s[:40] or "profile"


# ---------------------------------------------------------------- التحقق
def _known_actions() -> set[str]:
    from commands.actions import REGISTRY
    return set(REGISTRY) | VISION_ACTIONS


def _lang_map(value, what: str) -> dict[str, str]:
    if isinstance(value, str):
        value = {lang: value for lang in LANGS}
    if not isinstance(value, dict) or not any(isinstance(v, str) and v.strip() for v in value.values()):
        raise ProfileError("profile_bad_field", what)
    out = {k: str(v).strip() for k, v in value.items() if k in LANGS and isinstance(v, str) and v.strip()}
    first = next(iter(out.values()))
    return {lang: out.get(lang, first) for lang in LANGS}


def _steps(spec: dict) -> list[dict]:
    if "steps" in spec:
        return [dict(s) for s in spec["steps"] or [] if isinstance(s, dict)]
    if "action" in spec:
        return [{"action": spec["action"], **(spec.get("args") or {})}]
    return []


def parse_profile(data: dict, base_specs: list[dict], builtin: bool = False,
                  path: Path | None = None) -> tuple[Profile, list[str]]:
    """من قاموس YAML إلى Profile صالح. يرجع (الملف، تحذيرات لما تم تجاهله)."""
    if not isinstance(data, dict):
        raise ProfileError("profile_bad_file")
    warnings: list[str] = []
    name = _lang_map(data.get("name"), "name")
    pid = slugify(str(data.get("id") or name.get("en") or name.get("fr") or ""))
    desc = _lang_map(data["description"], "description") if data.get("description") else {}
    phrases = {lang: [str(p) for p in v] for lang, v in (data.get("phrases") or {}).items()
               if lang in LANGS and isinstance(v, list)}

    known = _known_actions()
    base_ids = {s.get("id") for s in base_specs}
    dangerous_ids = {s.get("id") for s in base_specs if s.get("dangerous")}

    commands: list[dict] = []
    raw_cmds = data.get("commands") or []
    if len(raw_cmds) > MAX_COMMANDS:
        warnings.append(f"commands>{MAX_COMMANDS}")
        raw_cmds = raw_cmds[:MAX_COMMANDS]
    for i, c in enumerate(raw_cmds):
        if not isinstance(c, dict) or not isinstance(c.get("phrases"), dict):
            warnings.append(f"command#{i}")
            continue
        steps = _steps(c)
        bad = [s.get("action") for s in steps if s.get("action") not in known]
        if not steps or bad:
            warnings.append(f"{c.get('id', i)}: {bad or 'no action'}")
            continue
        cid = f"{pid}.{slugify(str(c.get('id') or f'cmd{i}'))}"
        spec = {"id": cid,
                "phrases": {lang: [str(p) for p in v] for lang, v in c["phrases"].items()
                            if lang in LANGS and isinstance(v, list)},
                "steps": steps}
        if c.get("dangerous"):
            spec["dangerous"] = True
            dangerous_ids.add(cid)
        if c.get("always"):
            warnings.append(f"{cid}: always")
        commands.append(spec)
    own_ids = {c["id"] for c in commands}

    bindings: dict[str, str] = {}
    for gesture, action in (data.get("bindings") or {}).items():
        action = str(action)
        if gesture not in GESTURES:
            warnings.append(f"gesture {gesture}")
            continue
        if gesture in PROTECTED_BINDINGS:
            warnings.append(f"{gesture}: protected")
            continue
        if action.startswith(CMD_PREFIX):
            ref = action[len(CMD_PREFIX):]
            if f"{pid}.{slugify(ref)}" in own_ids:
                ref = slugify(ref)
            if f"{pid}.{ref}" in own_ids:
                ref = f"{pid}.{ref}"
            elif ref not in base_ids and ref not in own_ids:
                warnings.append(f"{gesture}: {action}")
                continue
            if ref in dangerous_ids:
                warnings.append(f"{gesture}: dangerous {ref}")
                continue
            action = CMD_PREFIX + ref
        elif action not in known:
            warnings.append(f"{gesture}: {action}")
            continue
        bindings[gesture] = action

    for w in warnings:
        log.warning("الملف الشخصي %s: تم تجاهل %s", pid, w)
    return Profile(pid, name, desc, phrases, bindings, commands, builtin, path), warnings


# ---------------------------------------------------------------- التحميل والحفظ
def _read(path: Path) -> dict:
    if path.stat().st_size > MAX_IMPORT_BYTES:
        raise ProfileError("profile_too_big", path.name)
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, UnicodeDecodeError) as e:
        raise ProfileError("profile_bad_file", str(e)) from e


def standard_profile() -> Profile:
    return Profile(STANDARD, {"ar": "عادي", "fr": "Standard", "en": "Standard"},
                   {"ar": "الإعدادات العامة دون تبديلات", "fr": "Réglages généraux, sans changement",
                    "en": "General settings, no changes"}, builtin=True)


def load_profiles(base_specs: list[dict], user_dir: Path | None = None) -> dict[str, Profile]:
    """المدمجة أولاً ثم ملفات المستخدم. ملف مستخدم يحمل معرّف ملف مدمج يُتجاهل."""
    out: dict[str, Profile] = {STANDARD: standard_profile()}
    sources = [(p, True) for p in sorted(builtin_dir().glob("*.yaml"))]
    udir = user_profiles_dir(user_dir)
    if udir.exists():
        sources += [(p, False) for p in sorted(udir.glob(f"*{SUFFIX}"))]
    for path, builtin in sources:
        try:
            prof, _ = parse_profile(_read(path), base_specs, builtin, path)
        except (ProfileError, OSError) as e:
            log.error("تعذّر تحميل الملف الشخصي %s: %s", path, e)
            continue
        if prof.id in out:
            log.warning("معرّف ملف شخصي مكرر %s (%s)؛ تم تجاهله", prof.id, path)
            continue
        out[prof.id] = prof
    return out


def unique_id(base: str, taken) -> str:
    pid, n = base, 2
    while pid in taken:
        pid, n = f"{base}-{n}", n + 1
    return pid


def save_profile(prof: Profile, user_dir: Path | None = None) -> Path:
    if prof.builtin:
        raise ProfileError("profile_builtin", prof.id)
    d = user_profiles_dir(user_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{prof.id}{SUFFIX}"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(prof.to_dict(), f, allow_unicode=True, sort_keys=False)
    prof.path = path
    return path


def export_profile(prof: Profile, dest: Path) -> Path:
    with open(dest, "w", encoding="utf-8") as f:
        yaml.safe_dump(prof.to_dict(), f, allow_unicode=True, sort_keys=False)
    return dest


def import_profile(src: Path, base_specs: list[dict], existing: dict[str, Profile],
                   user_dir: Path | None = None) -> tuple[Profile, list[str]]:
    """يتحقق من الملف، يعطيه معرّفاً فريداً، ويحفظه في user_data/profiles."""
    data = _read(src)
    prof, warnings = parse_profile(data, base_specs)
    new_id = unique_id(prof.id, existing)
    if new_id != prof.id:
        data = {**data, "id": new_id}
        prof, warnings = parse_profile(data, base_specs)
    save_profile(prof, user_dir)
    return prof, warnings


def duplicate_profile(src: Profile, name: str, existing: dict[str, Profile], base_specs: list[dict],
                      user_dir: Path | None = None) -> Profile:
    data = src.to_dict()
    data["id"] = unique_id(slugify(name) if slugify(name) != "profile" else f"{src.id}-copy", existing)
    data["name"] = {lang: name for lang in LANGS}
    prof, _ = parse_profile(data, base_specs)
    save_profile(prof, user_dir)
    return prof


def delete_profile(prof: Profile) -> None:
    if prof.builtin:
        raise ProfileError("profile_builtin", prof.id)
    if prof.path and prof.path.exists():
        prof.path.unlink()


# ---------------------------------------------------------------- التطبيق
def effective_bindings(base: dict[str, str], prof: Profile | None) -> dict[str, str]:
    out = {**base, **(prof.bindings if prof else {})}
    out.update(PROTECTED_BINDINGS)
    return out


def switch_specs(profiles: dict[str, Profile]) -> list[dict]:
    """أمر صوتي لكل ملف: "profil <الاسم>" بكل لغة + عبارات الملف الإضافية."""
    specs = []
    for p in profiles.values():
        phrases = {}
        for lang in LANGS:
            names = {p.name[lang]} | ({"normal"} if p.id == STANDARD and lang != "ar" else set())
            if p.id == STANDARD and lang == "ar":
                names.add("العادي")
            phrases[lang] = [f"{w} {n}".lower() for w in SWITCH_WORDS[lang] for n in sorted(names)]
            phrases[lang] += p.phrases.get(lang, [])
        specs.append({"id": f"profile.{p.id}", "phrases": phrases,
                      "action": "app.set_profile", "args": {"profile": p.id}})
    return specs
