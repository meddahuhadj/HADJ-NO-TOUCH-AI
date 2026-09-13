import os
import shutil
import string

def get_drives():
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            try:
                total, used, free = shutil.disk_usage(drive)
                drives.append({
                    "drive": drive,
                    "total_gb": round(total / (1024**3), 2),
                    "free_gb": round(free / (1024**3), 2)
                })
            except Exception:
                pass
    return drives

if __name__ == "__main__":
    for d in get_drives():
        print(f"Drive {d['drive']} - Total: {d['total_gb']} GB, Free: {d['free_gb']} GB")
