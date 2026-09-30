import os
import sys
import winreg

APP_NAME = "HADJ_NoTouch_AI"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def enable_startup(executable_or_script_path: str) -> bool:
    """Configures HADJ to automatically run on Windows logon."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{executable_or_script_path}" --minimized')
        winreg.CloseKey(key)
        print(f"[HADJ Startup] Enabled auto-start for: {executable_or_script_path}")
        return True
    except Exception as e:
        print(f"[HADJ Startup] Error configuring startup: {e}")
        return False


def disable_startup() -> bool:
    """Removes HADJ from Windows startup."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print("[HADJ Startup] Disabled auto-start.")
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        print(f"[HADJ Startup] Error disabling startup: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--disable":
        disable_startup()
    else:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bat_path = os.path.join(root, "launch.bat")
        enable_startup(bat_path)
