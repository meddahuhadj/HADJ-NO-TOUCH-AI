"""يولّد build/app.ico من أيقونة التطبيق المرسومة برمجياً (للملف التنفيذي)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from ui.icons import state_icon  # noqa: E402

if __name__ == "__main__":
    app = QGuiApplication([])
    out = ROOT / "build" / "app.ico"
    out.parent.mkdir(exist_ok=True)
    if not state_icon("ready", 256).pixmap(256, 256).save(str(out), "ICO"):
        raise SystemExit("تعذر حفظ الأيقونة")
    print(out)
