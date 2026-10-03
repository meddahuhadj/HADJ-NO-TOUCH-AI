import os
import sys

def get_project_root() -> str:
    """
    Returns the absolute base path of the project.
    Works seamlessly in standard Python mode and PyInstaller frozen mode (sys._MEIPASS).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return str(getattr(sys, "_MEIPASS"))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_path(relative_path: str) -> str:
    """
    Resolves a relative path (e.g., 'web/index.html', 'config/user_settings.json')
    to an absolute filesystem path safe for both source code and PyInstaller executable.
    """
    base = get_project_root()
    return os.path.normpath(os.path.join(base, relative_path))
