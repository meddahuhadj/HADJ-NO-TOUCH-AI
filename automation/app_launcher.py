import os
import sys
import subprocess
import glob
from typing import Dict, List, Optional
import webbrowser

try:
    import win32gui
    import win32con
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class AppLauncher:
    """Manages application launching, switching, and window focus across Windows."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AppLauncher, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        # Common application aliases and standard executable commands
        self.known_apps = {
            "chrome": ["chrome", "google-chrome"],
            "google chrome": ["chrome"],
            "edge": ["msedge"],
            "microsoft edge": ["msedge"],
            "firefox": ["firefox"],
            "notepad": ["notepad"],
            "المفكرة": ["notepad"],
            "bloc-notes": ["notepad"],
            "calculator": ["calc"],
            "حاسبة": ["calc"],
            "آلة حاسبة": ["calc"],
            "calculatrice": ["calc"],
            "word": ["winword", "start winword"],
            "excel": ["excel", "start excel"],
            "powerpoint": ["powerpnt"],
            "vs code": ["code"],
            "vscode": ["code"],
            "code": ["code"],
            "terminal": ["wt", "cmd"],
            "cmd": ["cmd"],
            "powershell": ["powershell"],
            "spotify": ["spotify"],
            "paint": ["mspaint"],
            "settings": ["start ms-settings:"],
            "الإعدادات": ["start ms-settings:"],
            "paramètres": ["start ms-settings:"],
            "explorer": ["explorer"],
            "task manager": ["taskmgr"],
            "مدير المهام": ["taskmgr"],
        }

        # URL aliases
        self.url_shortcuts = {
            "youtube": "https://www.youtube.com",
            "يوتيوب": "https://www.youtube.com",
            "google": "https://www.google.com",
            "جوجل": "https://www.google.com",
            "github": "https://www.github.com",
            "wikipedia": "https://www.wikipedia.org",
            "ويكيبيديا": "https://ar.wikipedia.org",
        }

        self.installed_apps_cache: Dict[str, str] = {}
        self._index_installed_apps()

    def _index_installed_apps(self):
        """Indexes shortcuts from Windows Start Menu programs."""
        paths = [
            os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        ]
        for p in paths:
            if os.path.exists(p):
                for root, _, files in os.walk(p):
                    for file in files:
                        if file.lower().endswith(".lnk"):
                            app_name = os.path.splitext(file)[0].lower()
                            full_path = os.path.join(root, file)
                            self.installed_apps_cache[app_name] = full_path

    def launch(self, target: str) -> bool:
        """Launches an application or website by name."""
        clean_target = target.strip().lower()

        # Check URL shortcut
        if clean_target in self.url_shortcuts:
            webbrowser.open(self.url_shortcuts[clean_target])
            return True

        if clean_target.startswith("http://") or clean_target.startswith("https://"):
            webbrowser.open(clean_target)
            return True

        # Check known apps
        if clean_target in ("chrome", "google chrome", "browser", "المتصفح", "navigateur"):
            try:
                webbrowser.open("https://www.google.com")
                return True
            except Exception:
                pass

        if clean_target in self.known_apps:
            exec_cmds = self.known_apps[clean_target]
            for cmd in exec_cmds:
                try:
                    if cmd.startswith("start "):
                        os.system(cmd)
                        return True
                    else:
                        os.system(f'start "" "{cmd}"')
                        return True
                except Exception:
                    continue

        # Check indexed start menu shortcuts
        for name, lnk_path in self.installed_apps_cache.items():
            if clean_target in name or name in clean_target:
                try:
                    os.startfile(lnk_path)
                    return True
                except Exception:
                    pass

        # Try generic shell open
        try:
            subprocess.Popen(clean_target, shell=True)
            return True
        except Exception as e:
            print(f"[AppLauncher] Error launching {target}: {e}")
            return False

    def close_app_by_name(self, app_name: str) -> bool:
        """Closes application process by name."""
        clean_name = app_name.strip().lower()
        if not clean_name.endswith(".exe"):
            # check map
            if clean_name in self.known_apps:
                clean_name = self.known_apps[clean_name][0] + ".exe"
            else:
                clean_name = clean_name + ".exe"

        try:
            res = subprocess.run(["taskkill", "/F", "/IM", clean_name], capture_output=True, text=True)
            return res.returncode == 0
        except Exception as e:
            print(f"[AppLauncher] Error terminating {clean_name}: {e}")
            return False

    def switch_to_window(self, window_title_keyword: str) -> bool:
        """Finds and brings a window matching keyword to the foreground."""
        if not HAS_WIN32:
            return False

        keyword = window_title_keyword.lower()
        found_hwnd = None

        def _enum_handler(hwnd, _):
            nonlocal found_hwnd
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                if keyword in title:
                    found_hwnd = hwnd

        win32gui.EnumWindows(_enum_handler, None)

        if found_hwnd:
            try:
                win32gui.ShowWindow(found_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(found_hwnd)
                return True
            except Exception as e:
                print(f"[AppLauncher] Error focusing window {found_hwnd}: {e}")
        return False
