"""تشخيص: ارتفاع الأزرار وعلامة الصح داخل مربّع الاختيار."""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
app.setStyle("Fusion")
from ui.control_panel import ControlPanel  # noqa: E402
from ui.i18n import Tr  # noqa: E402
from ui.theme import get_app_stylesheet  # noqa: E402

app.setLayoutDirection(Qt.RightToLeft)
app.setStyleSheet(get_app_stylesheet(1.0, False))
p = ControlPanel(Tr("ar"), 1.0, False)
p.resize(p.sizeHint())
p.show()
app.processEvents()
print("panel size", p.size(), "hint", p.sizeHint(), "minHint", p.minimumSizeHint())
for k, b in p.buttons.items():
    print(f"  {k:11s} h={b.height():4d} minH={b.minimumHeight()} hintH={b.sizeHint().height()}"
          f" policy={b.sizePolicy().verticalPolicy()}")
print("body", p._body.size(), "layout min size", p.layout().minimumSize())
inner = p._body.layout()
print("inner layout min", inner.minimumSize(), "sizeHint", inner.sizeHint())
print("body minimumSizeHint", p._body.minimumSizeHint())

# ---- checkbox ----
from ui.theme import theme  # noqa: E402
from ui.widgets import chip_qss  # noqa: E402
from PySide6.QtWidgets import QCheckBox, QWidget, QVBoxLayout  # noqa: E402

th = theme(1.0, False)
host = QWidget()
lay = QVBoxLayout(host)
cb = QCheckBox("اختبار", host)
cb.setChecked(True)
lay.addWidget(cb)
host.setStyleSheet(get_app_stylesheet(1.0, False))
host.resize(300, 80)
host.show()
app.processEvents()
img = host.grab().toImage()
ipos = cb.mapTo(host, cb.rect().topLeft())
print("checkbox at", ipos.x(), ipos.y(), cb.size())
whites = []
for y in range(ipos.y(), ipos.y() + cb.height()):
    for x in range(ipos.x(), ipos.x() + cb.width()):
        c = QColor(img.pixel(x, y))
        if c.lightness() > 235:
            whites.append((x - ipos.x(), y - ipos.y(), c.name()))
print("white pixels near indicator:", whites[:12], "count", len(whites))
# اطبع الصف الأول داخل المؤشّر
ind = 20
for y in range(0, 24, 2):
    row = " ".join(QColor(img.pixel(ipos.x() + x, ipos.y() + y)).name()[1:] for x in range(0, 26, 2))
    print(f"  y+{y:2d}: {row}")
