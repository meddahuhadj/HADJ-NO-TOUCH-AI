"""Real Windows window / application control (pywin32 + ctypes)."""

from __future__ import annotations

import os
import shutil
import subprocess
import time

from ..logging_setup import get_logger

log = get_logger("windows.window")

try:
    import win32con
    import win32gui
    import win32process
    HAVE_PYWIN32 = True
except Exception:  # pragma: no cover
    win32con = win32gui = None
    HAVE_PYWIN32 = False

user32 = None
if not HAVE_PYWIN32:
    import ctypes
    user32 = ctypes.windll.user32


def foreground_window_info() -> tuple[str, str]:
    """Return (title, exe_name) of the foreground window."""
    if HAVE_PYWIN32:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            exe = _process_name(pid)
        except Exception:
            exe = ""
        return title or "", exe
    return "", ""


def _process_name(pid: int) -> str:
    try:
        import win32api
        import win32con as _c
        h = win32api.OpenProcess(_c.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            name = win32process.GetModuleFileNameEx(h, 0)
            return os.path.basename(name).lower()
        finally:
            win32api.CloseHandle(h)
    except Exception:
        return ""


def active_application_name() -> str:
    _, exe = foreground_window_info()
    return exe or ""


def active_window_title() -> str:
    title, _ = foreground_window_info()
    return title or ""


def set_foreground(hwnd: int) -> None:
    if HAVE_PYWIN32:
        win32gui.SetForegroundWindow(hwnd)


def close_active_window() -> None:
    if HAVE_PYWIN32:
        hwnd = win32gui.GetForegroundWindow()
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)


def minimize_active() -> None:
    if HAVE_PYWIN32:
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)


def maximize_active() -> None:
    if HAVE_PYWIN32:
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    else:
        _send_keys_minimize_maximize()


def restore_active() -> None:
    if HAVE_PYWIN32:
        hwnd = win32gui.GetForegroundWindow()
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)


def switch_window() -> None:
    from . import keyboard_control
    keyboard_control.tap("TAB", ["ALT"])


def _send_keys_minimize_maximize() -> None:
    log.warning("pywin32 unavailable; window control limited.")


# Application launch --------------------------------------------------------
_KNOWN_APPS = {
    "chrome": ["C:/Program Files/Google/Chrome/Application/chrome.exe",
               "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"],
    "firefox": ["C:/Program Files/Mozilla Firefox/firefox.exe",
                "C:/Program Files (x86)/Mozilla Firefox/firefox.exe"],
    "edge": ["C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"],
    "explorer": ["C:/Windows/explorer.exe"],
    "notepad": ["C:/Windows/system32/notepad.exe", "C:/Windows/notepad.exe"],
    "calculator": ["C:/Windows/system32/calc.exe", "C:/Windows/SystemApps/Microsoft.WindowsCalculator_8wekyb3d8bbwe/CalculatorApp.exe"],
    "cmd": ["C:/Windows/system32/cmd.exe"],
    "powershell": ["C:/Windows/system32/WindowsPowerShell/v1.0/powershell.exe"],
    "paint": ["C:/Windows/system32/mspaint.exe"],
}

_BROWSER_EXES = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "msedge.exe"}
_MEDIA_EXES = {"vlc.exe", "wmplayer.exe", "potplayer.exe", "mpc-hc.exe", "yt music", "spotify.exe",
               "chrome.exe", "msedge.exe", "firefox.exe"}
_PDF_EXES = {"acrord32.exe", "acrobat.exe", "mspdf.exe", "foxitreader.exe", "sumatrapdf.exe", "adobe acrobat.exe"}
_PRESENTATION_EXES = {"powerpnt.exe", "wps.exe", "soffice.bin", "libreoffice.exe"}
_OFFICE_EXES = {"winword.exe", "excel.exe", "powerpnt.exe", "onenote.exe", "wps.exe"}
_TERMINAL_EXES = {"cmd.exe", "powershell.exe", "windowsterminal.exe", "pwsh.exe"}
_FILEMANAGER_EXES = {"explorer.exe"}


def context_category(exe: str | None = None) -> str:
    """Categorize an application exe name (defaults to the foreground window):
    browser / media / pdf / presentation / editor / terminal / files / office /
    imaging / other."""
    if not exe:
        _, exe = foreground_window_info()
    exe = (exe or "").lower()
    if exe in _BROWSER_EXES:
        return "browser"
    if exe in _PRESENTATION_EXES:
        return "presentation"
    if exe in _PDF_EXES:
        return "pdf"
    if exe in _MEDIA_EXES:
        return "media"
    if exe in _TERMINAL_EXES:
        return "terminal"
    if exe in _FILEMANAGER_EXES:
        return "files"
    if exe in _OFFICE_EXES:
        return "office"
    if exe in ("mricrogl.dll",) or "dicom" in exe or "slicer" in exe:
        return "imaging"
    return "other"


def launch_app(name: str) -> bool:
    name = name.strip().lower()
    target = _KNOWN_APPS.get(name)
    if target:
        for p in target:
            if os.path.isfile(p):
                return _start(p)
        return False
    if name in ("app", "setting", "settings", "windows settings"):
        return _start("ms-settings:")
    if name in ("control panel",):
        return _start("control")
    found = shutil.which(name)
    if found:
        return _start(found)
    # Fallback: search Start Menu and known roots.
    candidate = _search_start_menu(name)
    if candidate:
        return _start(candidate)
    return False


def _start(cmd: str) -> bool:
    try:
        if cmd.startswith("ms-settings:") or cmd in ("control",):
            subprocess.Popen(["explorer.exe", cmd])
        elif cmd.lower().endswith(".url"):
            subprocess.Popen(["cmd.exe", "/c", "start", "", cmd], shell=False)
        else:
            subprocess.Popen([cmd]) if os.path.isfile(cmd) else subprocess.Popen(["start", cmd], shell=True)
        return True
    except Exception as e:
        log.error("launch failed: %s", e)
        return False


def _search_start_menu(name: str):
    import glob
    roots = [
        os.environ.get("PROGRAMDATA", "C:/ProgramData") + "/Microsoft/Windows/Start Menu/Programs",
        os.environ.get("APPDATA", "") + "/Microsoft/Windows/Start Menu/Programs",
    ]
    for root in roots:
        for exe in glob.glob(f"{root}/**/*.lnk", recursive=True):
            base = os.path.splitext(os.path.basename(exe))[0].lower()
            if name in base or base in name:
                try:
                    import win32com.client
                    shell = win32com.client.Dispatch("WScript.Shell")
                    lnk = shell.CreateShortcut(exe)
                    return lnk.TargetPath
                except Exception:
                    return None
    return None