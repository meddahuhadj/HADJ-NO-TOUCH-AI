"""تعداد التطبيقات المثبتة في Windows (قائمة ابدأ: برامج سطح المكتب + تطبيقات المتجر)."""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

from os_layer.base import AppEntry

log = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000
_PS = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
       "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress")
_SKIP_WORDS = ("uninstall", "إلغاء التثبيت", "readme", "help", "documentation", "website")


def _from_start_apps() -> list[AppEntry]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS],
        capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW,
    )
    data = json.loads(out.stdout.decode("utf-8-sig") or "[]")
    if isinstance(data, dict):
        data = [data]
    return [AppEntry(name=d["Name"], target=d["AppID"], kind="appid")
            for d in data if d.get("Name") and d.get("AppID")]


def _from_start_menu_links() -> list[AppEntry]:
    roots = [Path(os.environ.get("ProgramData", r"C:\ProgramData")),
             Path(os.environ.get("APPDATA", ""))]
    entries = []
    for r in roots:
        base = r / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if base.exists():
            for p in base.rglob("*"):
                if p.suffix.lower() in (".lnk", ".url", ".appref-ms"):
                    entries.append(AppEntry(name=p.stem, target=str(p), kind="path"))
    return entries


def list_installed_apps() -> list[AppEntry]:
    try:
        entries = _from_start_apps()
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        log.warning("فشل Get-StartApps (%s)، سيتم مسح اختصارات قائمة ابدأ", e)
        entries = []
    if not entries:
        entries = _from_start_menu_links()
    seen, result = set(), []
    for e in entries:
        key = e.name.lower()
        if key in seen or any(w in key for w in _SKIP_WORDS):
            continue
        seen.add(key)
        result.append(e)
    return result
