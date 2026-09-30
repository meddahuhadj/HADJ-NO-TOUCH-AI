"""لوحة التحكّم السريع: نافذة عائمة للتحكّم بالنوافذ والشاشات والصوت.

فصلها عن `ControlPanel` مقصود: تلك بطاقة صغيرة **لا تقبل التركيز** كي يبقى
المؤشر في التطبيق الذي تكتب فيه، ووجهتها الإيماءات. وهذه تقبل التركيز لأنها
تحوي مزلاجاً وقائمة نافذة، فجعلها خلايا داخل تلك البطاقة يخلط الغرضين.

كل نداءات النظام هنا تمرّ عبر خيط مساعد: قراءة السطوع وحدها تستغرق نحو ثلاث
ثوانٍ عبر WMI، وتجميد الواجهة ثلاث ثوانٍ غير مقبول.
"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QRect, QRectF, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication, QKeyEvent, QPainter
from PySide6.QtWidgets import (QCheckBox, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QVBoxLayout, QWidget)

from os_layer.base import OSBackend
from ui.i18n import Tr
from ui.icons import app_icon
from ui.theme import theme
from ui.widgets import Card, Rule, make_transparent, paint_card

log = logging.getLogger(__name__)

# خلايا شبكة الترتيب: (الصف، العمود، الإجراء، التسمية، هي الوسطى؟)
SNAP_TILES: tuple[tuple[int, int, str, str, bool], ...] = (
    (0, 0, "topleft", "qp_tl", False),
    (0, 1, "top", "qp_top", False),
    (0, 2, "topright", "qp_tr", False),
    (1, 0, "left", "qp_left", False),
    (1, 1, "center_window", "qp_center", True),
    (1, 2, "right", "qp_right", False),
    (2, 0, "bottomleft", "qp_bl", False),
    (2, 1, "bottom", "qp_bottom", False),
    (2, 2, "bottomright", "qp_br", False),
)

DISPLAY_MODES = (("extend", "qp_extend"), ("duplicate", "qp_duplicate"),
                 ("next", "qp_next_display"))

DESKTOP_OPS = (("prev", "qp_desktop_prev"), ("new", "qp_desktop_new"),
               ("next", "qp_desktop_next"), ("close", "qp_desktop_close"))


class _Bridge(QObject):
    """يعيد نتيجة نداء النظام إلى خيط الواجهة (إشارة آمنة بين الخيوط)."""

    done = Signal(int, bool)   # id, ok


class QuickPanel(QWidget):
    """تحكّم سريع بالنوافذ/الشاشات/العرض. تُنشأ مرة وتُخفى بدل إغلاقها."""

    closed = Signal()

    def __init__(self, tr: Tr, os_backend: OSBackend,
                 font_scale: float = 1.0, high_contrast: bool = False) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        make_transparent(self)
        self.tr = tr
        self.os = os_backend
        self.th = theme(font_scale, high_contrast)
        t = self.th
        self.setWindowTitle(tr("qp_title"))
        self.setWindowIcon(app_icon(64, high_contrast))
        self.setLayoutDirection(Qt.RightToLeft if tr.rtl else Qt.LeftToRight)
        self.setStyleSheet(t.qss())
        self._margin = t.px(10)

        # حالة معرّفة - مبدأ: None = غير معروف بعد (لا نفترض قيمة)
        self._dark_on: bool | None = None
        self._screen_on: bool = True
        self._ontop: bool = False

        self._lock = threading.Lock()
        self._seq = 0
        self._pending: dict[int, tuple] = {}
        self._busy = 0

        self.bridge = _Bridge(self)
        self.bridge.done.connect(self._on_done)

        body = QWidget(self)
        body.setStyleSheet("background: transparent;")
        self._build(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self._margin, self._margin, self._margin, self._margin)
        outer.addWidget(body)
        self.setMinimumWidth(t.px(430))

    # ================= البناء =================
    def _build(self, body: QWidget) -> None:
        t, tr = self.th, self.tr

        # ---- الترويسة ----
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(t.px(12))
        title = QLabel(tr("qp_title"))
        title.setProperty("role", "title")
        head.addWidget(title, 1)
        self.status = QLabel("")
        self.status.setProperty("role", "faint")
        head.addWidget(self.status, 0)
        close_btn = QPushButton("")
        close_btn.setObjectName("iconButton")
        close_btn.setToolTip(tr("qp_close"))
        close_btn.setFocusPolicy(Qt.NoFocus)
        close_btn.setFixedSize(t.px(38), t.px(38))
        close_btn.clicked.connect(self.hide_panel)
        head.addWidget(close_btn, 0, Qt.AlignTop)

        lay = QVBoxLayout(body)
        lay.setContentsMargins(t.px(22), t.px(20), t.px(22), t.px(18))
        lay.setSpacing(t.px(13))
        lay.addLayout(head)
        lay.addWidget(Rule(body))

        # ---- النوافذ ----
        windows = self._section(body, tr("qp_windows"))
        snap = QGridLayout()
        snap.setSpacing(t.px(5))
        for row, col, action, key, is_main in SNAP_TILES:
            btn = QPushButton(tr(key))
            btn.setObjectName("snapTile")
            if is_main:
                btn.setProperty("tileMain", True)
            btn.setProperty("action", action)
            btn.setToolTip(tr("qp_active_window"))
            btn.clicked.connect(self._on_tile)
            snap.addWidget(btn, row, col)
        snap_wrap = QWidget(windows)
        snap_wrap.setStyleSheet("background: transparent;")
        snap_wrap.setLayout(snap)
        snap_wrap.setMaximumWidth(t.px(300))
        windows.layout().addWidget(snap_wrap, 0, Qt.AlignHCenter)

        row = QHBoxLayout()
        row.setSpacing(t.px(8))
        self.ontop = QCheckBox(tr("qp_always_on_top"))
        self.ontop.toggled.connect(self._on_ontop)
        row.addWidget(self.ontop)
        row.addStretch(1)
        restore = QPushButton(tr("qp_restore"))
        restore.setObjectName("ghostButton")
        restore.clicked.connect(lambda: self._call(self.os.snap_window, "restore"))
        row.addWidget(restore)
        windows.layout().addLayout(row)
        lay.addWidget(windows)

        # ---- قائمة النوافذ ----
        wins = self._section(body, tr("qp_open_windows"))
        refresh = QPushButton(tr("qp_refresh"))
        refresh.setObjectName("ghostButton")
        refresh.setFocusPolicy(Qt.NoFocus)
        refresh.clicked.connect(self.refresh)
        wins.layout().addWidget(refresh, 0, Qt.AlignLeft)

        self.window_list = QWidget()
        self.window_list.setStyleSheet("background: transparent;")
        self.window_list_layout = QVBoxLayout(self.window_list)
        self.window_list_layout.setContentsMargins(0, 0, 0, 0)
        self.window_list_layout.setSpacing(t.px(5))
        scroll = QScrollArea()
        scroll.setWidget(self.window_list)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll.setMinimumHeight(t.px(92))
        scroll.setMaximumHeight(t.px(180))
        wins.layout().addWidget(scroll, 1)
        lay.addWidget(wins)

        # ---- الشاشات ----
        screens = self._section(body, tr("qp_screens"))
        self.monitor_row = QHBoxLayout()
        self.monitor_row.setSpacing(t.px(8))
        screens.layout().addLayout(self.monitor_row)

        modes = QHBoxLayout()
        modes.setSpacing(t.px(8))
        for action, key in DISPLAY_MODES:
            btn = QPushButton(tr(key))
            btn.setObjectName("ghostButton")
            btn.clicked.connect(lambda _c=False, a=action: self._call(self.os.set_display_mode, a))
            modes.addWidget(btn)
        screens.layout().addLayout(modes)

        desks = QHBoxLayout()
        desks.setSpacing(t.px(8))
        for op, key in DESKTOP_OPS:
            btn = QPushButton(tr(key))
            btn.setObjectName("ghostButton")
            btn.clicked.connect(lambda _c=False, o=op: self._call(self._desktop_fn(o)))
            desks.addWidget(btn)
        screens.layout().addLayout(desks)
        lay.addWidget(screens)

        # ---- العرض والصوت ----
        display = self._section(body, tr("qp_display_audio"))

        bright = QHBoxLayout()
        bright.setSpacing(t.px(10))
        blabel = QLabel(tr("qp_brightness"))
        blabel.setProperty("role", "dim")
        bright.addWidget(blabel, 0)
        self.bright_value = QLabel("--")
        self.bright_value.setProperty("role", "accent")
        self.bright_value.setMinimumWidth(t.px(48))
        self.bright_value.setAlignment(Qt.AlignCenter)
        bright.addWidget(self.bright_value, 0)
        self.bright = QSlider(Qt.Horizontal)
        self.bright.setRange(0, 100)
        self.bright.setEnabled(False)
        self.bright.valueChanged.connect(self._on_bright_moved)
        self.bright.sliderReleased.connect(self._on_bright_released)
        bright.addWidget(self.bright, 1)
        display.layout().addLayout(bright)

        self.bright_note = QLabel(tr("qp_no_brightness"))
        self.bright_note.setProperty("role", "faint")
        self.bright_note.setVisible(False)
        display.layout().addWidget(self.bright_note)

        toggles = QHBoxLayout()
        toggles.setSpacing(t.px(8))
        self.dark = QPushButton(tr("qp_dark_mode"))
        self.dark.setObjectName("toggleButton")
        self.dark.clicked.connect(self._on_dark)
        toggles.addWidget(self.dark, 1)
        self.screen = QPushButton(tr("qp_screen_off"))
        self.screen.setObjectName("toggleButton")
        self.screen.clicked.connect(self._on_screen)
        toggles.addWidget(self.screen, 1)
        display.layout().addLayout(toggles)

        mic_row = QHBoxLayout()
        mic_row.setSpacing(t.px(8))
        self.mic = QPushButton(tr("qp_mic_toggle"))
        self.mic.setObjectName("toggleButton")
        self.mic.setToolTip(tr("qp_mic_hint"))
        self.mic.clicked.connect(lambda: self._call(self.os.toggle_microphone_mute))
        mic_row.addWidget(self.mic, 1)
        mic_note = QLabel(tr("qp_mic_hint"))
        mic_note.setProperty("role", "faint")
        mic_note.setWordWrap(True)
        mic_note.setMaximumWidth(t.px(200))
        mic_row.addWidget(mic_note, 0)
        display.layout().addLayout(mic_row)
        lay.addWidget(display)

    def _section(self, parent: QWidget, title: str) -> Card:
        card = Card(parent)
        box = QVBoxLayout(card)
        box.setContentsMargins(self.th.px(16), self.th.px(13),
                               self.th.px(16), self.th.px(13))
        box.setSpacing(self.th.px(9))
        head = QLabel(title)
        head.setProperty("role", "caption")
        box.addWidget(head)
        return card

    # ================= نداء النظام خارج خيط الواجهة =================
    def _call(self, fn, *args, on_ok=None, on_fail=None) -> None:
        """يشغّل fn في خيط مساعد ويسلّم نتيجته إلى خيط الواجهة."""
        with self._lock:
            self._seq += 1
            sid = self._seq
            self._pending[sid] = (on_ok, on_fail)

        def run():
            try:
                ok = bool(fn(*args))
            except Exception as exc:           # noqa: BLE001 - لا نُسقط الواجهة
                log.debug("فشل نداء النظام من اللوحة: %s", exc)
                ok = False
            self.bridge.done.emit(sid, ok)

        threading.Thread(target=run, daemon=True, name="quickpanel").start()

    @Slot(int, bool)
    def _on_done(self, sid: int, ok: bool) -> None:
        with self._lock:
            on_ok, on_fail = self._pending.pop(sid, (None, None))
        self._busy = max(0, self._busy - 1)
        self._set_status(self.tr("qp_done") if ok else self.tr("qp_failed"))
        try:
            if ok and on_ok:
                on_ok()
            elif not ok and on_fail:
                on_fail()
        except Exception as exc:               # noqa: BLE001
            log.debug("فشل تحديث اللوحة: %s", exc)

    def _begin(self) -> None:
        self._busy += 1
        self._set_status(self.tr("qp_busy"))

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    # ================= معالجات =================
    def _desktop_fn(self, op: str):
        return {"prev": lambda: self.os.switch_virtual_desktop("left"),
                "next": lambda: self.os.switch_virtual_desktop("right"),
                "new": self.os.new_virtual_desktop,
                "close": self.os.close_virtual_desktop}[op]

    def _on_tile(self) -> None:
        action = self.sender().property("action")
        if action == "center_window":
            self._begin()
            self._call(self.os.center_window)
        else:
            self._begin()
            self._call(self.os.snap_window, action)

    def _on_ontop(self, on: bool) -> None:
        # نثبّت ما طلبه المستخدم فقط عند نجاح Windows
        self._begin()
        self._call(self.os.set_always_on_top, on,
                   on_ok=lambda: self._set_check(self.ontop, True),
                   on_fail=lambda: self._set_check(self.ontop, self._ontop))

    def _on_bright_moved(self, value: int) -> None:
        self.bright_value.setText(f"{value}%")

    def _on_bright_released(self) -> None:
        want = self.bright.value()
        self._begin()
        self._call(self.os.set_brightness, want)

    def _on_dark(self) -> None:
        want = True if self._dark_on is None else not self._dark_on
        self._begin()
        self._call(self.os.set_dark_mode, want,
                   on_ok=lambda: self._set_dark(want),
                   on_fail=lambda: self._set_dark(self._dark_on))

    def _on_screen(self) -> None:
        want = not self._screen_on
        self._begin()
        self._call(self.os.monitor_power, want,
                   on_ok=lambda: self._set_screen(want),
                   on_fail=lambda: self._set_screen(self._screen_on))

    def _on_mic(self) -> None:
        # لا حالة نقرأها، فلا نغيّر شيئاً: الزر ينفّذ فقط ويعرض «تم».
        self._begin()
        self._call(self.os.toggle_microphone_mute)

    # ================= تحديث الحالة =================
    def _set_dark(self, on: bool | None) -> None:
        self._dark_on = on
        self.dark.setProperty("on", on is True)
        self._repolish(self.dark)
        self.dark.setText(self.tr("qp_dark_mode_on") if on else self.tr("qp_dark_mode_off"))

    def _set_screen(self, on: bool) -> None:
        self._screen_on = on
        self.screen.setProperty("on", not on)      # "مطفأة" = الحالة النشطة
        self._repolish(self.screen)
        self.screen.setText(self.tr("qp_screen_off") if on else self.tr("qp_screen_on"))

    def _set_check(self, box: QCheckBox, on: bool) -> None:
        self._ontop = on
        box.blockSignals(True)
        box.setChecked(on)
        box.blockSignals(False)

    @staticmethod
    def _repolish(w: QWidget) -> None:
        """إعادة تطبيق QSS بعد تغيّر خاصية (مثل on)."""
        w.style().unpolish(w)
        w.style().polish(w)

    def refresh(self) -> None:
        self.refresh_windows()
        self._begin()
        self._call(self._read_brightness)
        self._begin()
        self._call(self._read_dark)
        self._begin()
        self._call(self._read_monitors)

    def refresh_windows(self) -> None:
        while self.window_list_layout.count():
            item = self.window_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        try:
            windows = self.os.list_windows()
        except Exception as exc:               # noqa: BLE001
            log.debug("تعذّر سرد النوافذ: %s", exc)
            windows = []
        windows = [w for w in windows if w.title.strip()][:40]
        if not windows:
            note = QLabel(self.tr("qp_no_windows"))
            note.setProperty("role", "faint")
            self.window_list_layout.addWidget(note)
            return
        for w in windows:
            title = w.title.strip()
            label = ("▫ " + title) if w.minimized else title   # ▫ = مصغّرة
            btn = QPushButton(label)
            btn.setObjectName("ghostButton")
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setToolTip(title)
            btn.clicked.connect(lambda _c=False, q=title: self._focus(q))
            self.window_list_layout.addWidget(btn)

    def _focus(self, query: str) -> None:
        self._begin()
        self._call(self.os.focus_window, query, on_ok=self.refresh_windows)

    def _read_brightness(self) -> bool:
        value = self.os.current_brightness()
        if value is None:
            self.bright.setEnabled(False)
            self.bright_value.setText("--")
            self.bright_note.setVisible(True)
            return False
        self.bright.blockSignals(True)
        self.bright.setValue(max(0, min(100, int(value))))
        self.bright.blockSignals(False)
        self.bright_value.setText(f"{self.bright.value()}%")
        self.bright.setEnabled(True)
        self.bright_note.setVisible(False)
        return True

    def _read_dark(self) -> bool:
        value = self.os.dark_mode_enabled()
        if value is None:
            return False
        self._set_dark(bool(value))
        return True

    def _read_monitors(self) -> bool:
        monitors = self.os.list_monitors()
        self._rebuild_monitors(monitors)
        return bool(monitors)

    def _rebuild_monitors(self, monitors) -> None:
        tr, t = self.tr, self.th
        while self.monitor_row.count():
            item = self.monitor_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not monitors:
            note = QLabel(tr("qp_no_monitor"))
            note.setProperty("role", "faint")
            self.monitor_row.addWidget(note)
            return
        for m in monitors:
            name = tr("qp_monitor_n", n=m.index + 1)
            if getattr(m, "primary", False):
                name += f" · {tr('qp_primary')}"
            btn = QPushButton(name)
            btn.setObjectName("ghostButton")
            btn.setToolTip(getattr(m, "name", "") or name)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(
                lambda _c=False, i=m.index: self._move_to_monitor(i))
            self.monitor_row.addWidget(btn, 1)

    def _move_to_monitor(self, index: int) -> None:
        self._begin()
        self._call(self.os.move_window_to_monitor, index)

    # ================= الرسم والموضع =================
    def _card_rect(self) -> QRectF:
        m = self._margin
        return QRectF(m, m, max(1, self.width() - 2 * m), max(1, self.height() - 2 * m))

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        paint_card(p, self._card_rect(), self.th)
        p.end()

    def popup_near(self, anchor: QRect | None = None) -> None:
        """يظهر اللوحة قرب مرساة (لوحة التحكم) أو في زاوية الشاشة."""
        self.adjustSize()
        self.show()
        self.raise_()
        self.activateWindow()
        self.refresh()
        screen = (QGuiApplication.screenAt(anchor.center())
                  if anchor is not None and anchor.isValid()
                  else QGuiApplication.primaryScreen())
        if screen is None:
            return
        area = screen.availableGeometry()
        w, h = self.width(), self.height()
        if anchor is not None and anchor.isValid():
            x, y = anchor.left() + self._margin, anchor.bottom() + self._margin
        else:
            x, y = area.right() - w - self._margin, area.top() + self._margin
        self.move(max(area.left(), min(x, area.right() - w)),
                  max(area.top(), min(y, area.bottom() - h)))

    def hide_panel(self) -> None:
        self.hide()
        self.closed.emit()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key_Escape:
            self.hide_panel()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e) -> None:
        # نخفي بدل الإتلاف: اللوحة تُعاد كل مرة تفتح فيها
        self.hide()
        self.closed.emit()
        e.ignore()
