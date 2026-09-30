"""التحكّم في العرض: السطوع والوضع الداكن وإطفاء الشاشات.

السطوع يمر عبر WMI (الطريقة الوحيدة التي تحترمها كل الأجهزة)، والوضع الداكن
عبر السجل. الاثنان يرسلان نداءً لنظام Windows حتى تعيد التطبيقات الرسم فوراً.
"""
from __future__ import annotations

import ctypes
import logging
import subprocess
import winreg
from ctypes import wintypes

from os_layer.windows.winapi import HWND_BROADCAST, user32

log = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000
PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

WM_SETTINGCHANGE = 0x001A
SMTO_ABORTIFHUNG = 0x0002

# WMI لا يقبل القيمة 0 في كل الأجهزة، فنقرّب الحد الأدنى إلى 1.
# القيم تُدرَج داخل النص (لا كوسائط) لأن `powershell -Command` لا يربط $args.
_BRIGHTNESS_HEAD = """
$b = Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness -ErrorAction SilentlyContinue
if (-not $b) { Write-Output 'NO'; exit 0 }
$m = Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue
if (-not $m) { Write-Output 'NO'; exit 0 }
$cur = [int]$b.CurrentBrightness
"""
_BRIGHTNESS_TAIL = """
if ($target -lt 0) { $target = 0 }
if ($target -gt 100) { $target = 100 }
[void]$m.WmiSetBrightness(1, $target)
Write-Output $target
"""


def _clamp_int(value: object) -> int:
    """يحوّل أي مدخل إلى عدد صحيح ضمن -100..100 (يمنع حقن نص في PowerShell)."""
    try:
        return max(-100, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _run_ps(script: str, *args: str, timeout: float = 6.0) -> str:
    """ينفّذ مقطع PowerShell بلا نافذة ويعيد مخرجاته (نص)."""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script, *args],
            capture_output=True, timeout=timeout, creationflags=CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.debug("فشل تشغيل PowerShell: %s", exc)
        return ""
    return proc.stdout.decode("utf-8", "replace").strip()


def _broadcast_setting_change(value: str) -> None:
    """يخبر التطبيقات أن إعداداً نظامياً تغيّر (بلا انتظار: مهلة قصيرة)."""
    buf = ctypes.create_unicode_buffer(value)
    user32.SendMessageTimeoutW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                           wintypes.LPCWSTR, wintypes.UINT, wintypes.UINT,
                                           ctypes.POINTER(ctypes.c_ulong))
    user32.SendMessageTimeoutW.restype = wintypes.LPARAM
    result = ctypes.c_ulong()
    try:
        user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, buf, SMTO_ABORTIFHUNG,
                                   2000, ctypes.byref(result))
    except OSError:
        log.debug("فشل بث تغيّر الإعداد", exc_info=True)


# ---------------- السطوع ----------------
def get_brightness() -> int | None:
    """السطوع الحالي 0..100، أو None إن لم تكن الشاشة تدعمه (شاشات مكتبية)."""
    out = _run_ps(
        "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness "
        "-ErrorAction SilentlyContinue).CurrentBrightness")
    try:
        return int(out)
    except (TypeError, ValueError):
        return None


def set_brightness(percent: int) -> bool:
    """يضبط السطوع على نسبة 0..100. يُرجع False إن لم يدعمه الجهاز."""
    target = _clamp_int(percent)
    out = _run_ps(_BRIGHTNESS_HEAD + f"$target = {target}" + _BRIGHTNESS_TAIL)
    return out.isdigit()


def adjust_brightness(delta: int) -> int | None:
    """يزيد/ينقص السطوع بمقدار معطى ويعيد القيمة الجديدة (أو None)."""
    step = _clamp_int(delta)
    out = _run_ps(_BRIGHTNESS_HEAD + f"$target = $cur + ({step})" + _BRIGHTNESS_TAIL)
    return int(out) if out.isdigit() else None


# ---------------- الوضع الداكن ----------------
def get_dark_mode() -> bool | None:
    """True = داكن. None إن لم يمكن القراءة."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY) as key:
            light = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
        return not bool(light)
    except OSError:
        log.debug("تعذّرت قراءة وضع الألوان", exc_info=True)
        return None


def set_dark_mode(enabled: bool) -> bool:
    """يفعّل/يعطّل الوضع الداكن لتطبيقات النظام."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD,
                              0 if enabled else 1)
    except OSError:
        log.debug("تعذّر تغيير وضع الألوان", exc_info=True)
        return False
    _broadcast_setting_change("ImmersiveColorSet")
    return True
