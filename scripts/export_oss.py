"""يصدّر طبقة النظام (src/os_layer) كمستودع مستقل مفتوح المصدر: dist/oss/hadj-input/

    python scripts/export_oss.py [--out DIR]

المصدر واحد: الكود يُنسخ من src/os_layer (لا نسخة ثانية تُصان يدوياً)، والملفات الخاصة بالمستودع
العام (الترخيص، SECURITY.md، نموذج التهديدات، الاختبارات) من oss/hadj-input/.
لا ينشر شيئاً: النشر على GitHub قرار المالك، بعد مراجعة الناتج.

يفشل التصدير إذا وُجد في الكود المصدَّر:
- استيراد من بقية التطبيق (core, commands, config, ui, vision, audio)
- وحدة شبكة (socket, urllib, http, requests…)
- خطاف لوحة مفاتيح أو قراءة لها (SetWindowsHookEx, GetKeyboardState…)
"""
from __future__ import annotations

import argparse
import ast
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "os_layer"
TEMPLATES = ROOT / "oss" / "hadj-input"
PACKAGE = "hadj_input"
# ما يُفتح: كل ما يلمس النظام. apps_index (بحث تقريبي عن التطبيقات) منطق تطبيق لا طبقة نظام.
FILES = ["base.py", "windows/__init__.py", "windows/backend.py", "windows/input.py",
         "windows/winapi.py", "windows/display.py", "windows/apps.py"]
APP_MODULES = {"core", "commands", "config", "ui", "vision", "audio", "help", "os_layer"}
NETWORK_MODULES = {"socket", "urllib", "http", "requests", "ftplib", "smtplib", "ssl", "asyncio",
                   "websocket", "websockets", "xmlrpc"}
FORBIDDEN_CALLS = ["SetWindowsHookEx", "GetKeyboardState", "GetRawInputData", "RegisterRawInputDevices",
                   "BlockInput", "keybd_event"]
# GetAsyncKeyState مسموح فقط لأزرار الفأرة (0x01، 0x02، 0x04) في release_all: يُفحص أدناه
ALLOWED_ASYNC_VK = {"0x01", "0x02", "0x04"}

FACTORY = '''"""Pick the OS backend for the current platform."""
from __future__ import annotations

import sys

from {pkg}.base import OSBackend


def create_backend(sound_provider=None) -> OSBackend:
    """sound_provider(volume) -> {{kind: Path to .wav}} (optional; without it play_sound is silent)."""
    if sys.platform == "win32":
        from {pkg}.windows.backend import WindowsBackend
        return WindowsBackend(sound_provider=sound_provider)
    raise NotImplementedError(f"{{sys.platform}} is not supported yet: implement {pkg}.base.OSBackend")
'''

INIT = '''"""hadj-input: offline keyboard, mouse, window and display control for Windows (ctypes, no hooks).

Extracted from HADJ No-Touch. See SECURITY.md and docs/THREAT_MODEL.md.
"""
from {pkg}.base import AppEntry, MonitorInfo, OSBackend, WindowInfo
from {pkg}.factory import create_backend

__all__ = ["AppEntry", "MonitorInfo", "OSBackend", "WindowInfo", "create_backend"]
__version__ = "{version}"
'''


class ExportError(RuntimeError):
    pass


def audit(path: Path, text: str) -> list[str]:
    """مشكلات الكود المصدَّر (قائمة فارغة = سليم)."""
    problems = []
    tree = ast.parse(text, str(path))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        for n in names:
            top = n.split(".")[0]
            if top in APP_MODULES - {PACKAGE}:
                problems.append(f"{path.name}: app import '{n}'")
            if top in NETWORK_MODULES:
                problems.append(f"{path.name}: network module '{n}'")
    for call in FORBIDDEN_CALLS:
        if call in text:
            problems.append(f"{path.name}: forbidden call {call}")
    for m in re.finditer(r"GetAsyncKeyState\(([^)]*)\)", text):
        arg = m.group(1).strip()
        if arg != "vk" or not re.search(r'\(\("left", 0x01\), \("right", 0x02\), \("middle", 0x04\)\)', text):
            problems.append(f"{path.name}: GetAsyncKeyState outside the mouse-button release")
    return problems


def export(out: Path, version: str = "0.1.0") -> Path:
    if out.exists():
        shutil.rmtree(out)
    pkg = out / "src" / PACKAGE
    problems: list[str] = []
    for rel in FILES:
        text = (SRC / rel).read_text(encoding="utf-8")
        text = re.sub(r"\bos_layer\b", PACKAGE, text)
        problems += audit(SRC / rel, text)
        dest = pkg / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    (pkg / "factory.py").write_text(FACTORY.format(pkg=PACKAGE), encoding="utf-8")
    (pkg / "__init__.py").write_text(INIT.format(pkg=PACKAGE, version=version), encoding="utf-8")
    for f in (pkg / "factory.py", pkg / "__init__.py"):
        problems += audit(f, f.read_text(encoding="utf-8"))
    if problems:
        shutil.rmtree(out)
        raise ExportError("export refused:\n  " + "\n  ".join(problems))
    for item in TEMPLATES.rglob("*"):
        if item.is_file():
            dest = out / item.relative_to(TEMPLATES)
            dest.parent.mkdir(parents=True, exist_ok=True)
            text = item.read_text(encoding="utf-8").replace("{{version}}", version)
            dest.write_text(text, encoding="utf-8")
    for f in pkg.rglob("*.py"):
        compile(f.read_text(encoding="utf-8"), str(f), "exec")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "dist" / "oss" / "hadj-input")
    ap.add_argument("--version", default="0.1.0")
    args = ap.parse_args()
    try:
        out = export(args.out, args.version)
    except ExportError as e:
        print(e, file=sys.stderr)
        return 1
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    print(f"{out}  ({len(files)} files)")
    for f in files:
        print("  " + f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
