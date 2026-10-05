"""قائمة التطبيقات على Linux: ملفات .desktop (مواصفة freedesktop) — منطق بحت بلا X11.

الأسماء بلغة الواجهة إن وُجدت (Name[ar]، Name[fr])، وتُستبعد الإدخالات المخفية وغير التطبيقات.
التشغيل لا يمر أبداً عبر shell: سطر Exec يُقسَّم ويُنظَّف من رموز %f %u…
"""
from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DesktopApp:
    id: str          # اسم الملف دون .desktop (مثل org.gnome.Calculator)
    name: str
    exec_args: list[str]
    path: Path


def application_dirs(env: dict | None = None) -> list[Path]:
    """مجلدات applications حسب XDG: مجلد المستخدم أولاً (يطغى على نسخ النظام بنفس الاسم)."""
    env = env if env is not None else os.environ
    home = Path(env.get("XDG_DATA_HOME") or Path(env.get("HOME", "~")).expanduser() / ".local/share")
    system = (env.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    dirs = [home / "applications"] + [Path(d) / "applications" for d in system if d]
    dirs.append(Path("/var/lib/flatpak/exports/share/applications"))
    return dirs


def clean_exec(line: str) -> list[str]:
    """سطر Exec ← وسائط آمنة: إزالة رموز الحقول (%f %F %u %U %i %c %k…)، و%% ← %."""
    try:
        parts = shlex.split(line)
    except ValueError:
        return []
    out = []
    for p in parts:
        if len(p) == 2 and p[0] == "%" and p[1] != "%":
            continue
        out.append(p.replace("%%", "%"))
    return out


def parse_desktop(text: str, langs: tuple[str, ...] = ()) -> dict | None:
    """قسم [Desktop Entry] كقاموس، أو None إن لم يكن تطبيقاً ظاهراً."""
    entry: dict[str, str] = {}
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section != "Desktop Entry" or "=" not in line:
            continue
        k, v = line.split("=", 1)
        entry[k.strip()] = v.strip()
    if entry.get("Type") != "Application" or not entry.get("Exec"):
        return None
    if entry.get("NoDisplay", "").lower() == "true" or entry.get("Hidden", "").lower() == "true":
        return None
    name = next((entry[f"Name[{lang}]"] for lang in langs if f"Name[{lang}]" in entry), entry.get("Name"))
    if not name:
        return None
    entry["_name"] = name
    return entry


def list_desktop_apps(dirs: list[Path] | None = None, langs: tuple[str, ...] = ()) -> list[DesktopApp]:
    found: dict[str, DesktopApp] = {}
    decided: set[str] = set()   # المعرّف حُسم في مجلد أسبق (حتى لو كان مخفياً: Hidden=true يُخفي نسخة النظام)
    for d in dirs if dirs is not None else application_dirs():
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.desktop")):
            app_id = f.stem
            if app_id in decided:
                continue     # مجلد المستخدم يسبق النظام
            try:
                entry = parse_desktop(f.read_text(encoding="utf-8", errors="replace"), langs)
            except OSError:
                continue
            decided.add(app_id)
            if entry is None:
                continue
            args = clean_exec(entry["Exec"])
            if args:
                found[app_id] = DesktopApp(app_id, entry["_name"], args, f)
    return sorted(found.values(), key=lambda a: a.name.lower())
