import os
import glob
import subprocess
import shutil
from typing import Optional, List

USER_HOME = os.path.expanduser("~")

STANDARD_FOLDERS = {
    "downloads": os.path.join(USER_HOME, "Downloads"),
    "التنزيلات": os.path.join(USER_HOME, "Downloads"),
    "التحميلات": os.path.join(USER_HOME, "Downloads"),
    "téléchargements": os.path.join(USER_HOME, "Downloads"),
    "documents": os.path.join(USER_HOME, "Documents"),
    "المستندات": os.path.join(USER_HOME, "Documents"),
    "ملفاتي": os.path.join(USER_HOME, "Documents"),
    "mes documents": os.path.join(USER_HOME, "Documents"),
    "desktop": os.path.join(USER_HOME, "Desktop"),
    "سطح المكتب": os.path.join(USER_HOME, "Desktop"),
    "bureau": os.path.join(USER_HOME, "Desktop"),
    "pictures": os.path.join(USER_HOME, "Pictures"),
    "الصور": os.path.join(USER_HOME, "Pictures"),
    "images": os.path.join(USER_HOME, "Pictures"),
    "music": os.path.join(USER_HOME, "Music"),
    "الموسيقى": os.path.join(USER_HOME, "Music"),
    "videos": os.path.join(USER_HOME, "Videos"),
    "الفيديو": os.path.join(USER_HOME, "Videos"),
    "vividéos": os.path.join(USER_HOME, "Videos"),
    "c drive": "C:\\",
    "القرص c": "C:\\",
    "disque c": "C:\\",
}


class FileManager:
    """Manages file and folder automation, browsing, and safe operations."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FileManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.last_accessed_dir = STANDARD_FOLDERS["downloads"]

    def open_folder(self, folder_alias: str) -> bool:
        """Opens folder in Windows Explorer by alias or path."""
        alias = folder_alias.strip().lower()
        target_path = STANDARD_FOLDERS.get(alias)

        if not target_path:
            if os.path.isdir(folder_alias):
                target_path = folder_alias
            else:
                # check subfolders in last accessed dir or home
                cand = os.path.join(self.last_accessed_dir, folder_alias)
                if os.path.isdir(cand):
                    target_path = cand

        if target_path and os.path.exists(target_path):
            self.last_accessed_dir = target_path
            try:
                os.startfile(target_path)
                return True
            except Exception as e:
                print(f"[FileManager] Error opening folder: {e}")
                return False
        return False

    def create_folder(self, name: str, parent_dir: Optional[str] = None) -> bool:
        """Creates a new directory inside target parent (or Desktop by default)."""
        base_dir = parent_dir or STANDARD_FOLDERS["desktop"]
        target = os.path.join(base_dir, name)
        try:
            os.makedirs(target, exist_ok=True)
            self.open_folder(target)
            return True
        except Exception as e:
            print(f"[FileManager] Error creating folder {target}: {e}")
            return False

    def open_recent_download(self) -> bool:
        """Finds the most recently modified file in Downloads and opens it."""
        dl_dir = STANDARD_FOLDERS["downloads"]
        if not os.path.exists(dl_dir):
            return False

        files = glob.glob(os.path.join(dl_dir, "*"))
        if not files:
            return False

        latest_file = max(files, key=os.path.getmtime)
        try:
            os.startfile(latest_file)
            return True
        except Exception as e:
            print(f"[FileManager] Error opening recent download: {e}")
            return False

    def search_files(self, keyword: str, directory: Optional[str] = None) -> List[str]:
        """Searches for files matching keyword in directory."""
        search_root = directory or self.last_accessed_dir
        matches = []
        try:
            for root, _, files in os.walk(search_root):
                for f in files:
                    if keyword.lower() in f.lower():
                        matches.append(os.path.join(root, f))
                        if len(matches) >= 10:
                            break
                if len(matches) >= 10:
                    break
        except Exception:
            pass
        return matches

    def delete_path(self, path: str) -> bool:
        """Safely removes file or folder."""
        if not os.path.exists(path):
            return False
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return True
        except Exception as e:
            print(f"[FileManager] Error deleting {path}: {e}")
            return False
