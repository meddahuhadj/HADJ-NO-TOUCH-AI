"""لوحة التحكم: النافذة الرئيسية. بطاقة بلا إطار تطفو فوق الشاشة.

تعرض الحالة الحية بكرة نابضة، وآخر ما سُمع، وستة أزرار كبيرة (أهداف للإيماءات).
لا تأخذ التركيز عند النقر (WindowDoesNotAcceptFocus) حتى يبقى المؤشر في التطبيق
الذي تكتب فيه؛ إغلاقها يخفيها فقط والتطبيق يبقى في شريط النظام.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QGuiApplication, QMouseEvent, QPainter
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from ui.i18n import Tr
from ui.icons import app_icon, state_icon
from ui.theme import theme
from ui.widgets import (AudioWaveVisualizer, Card, Rule, StateOrb, Transcript,
                        make_transparent, paint_card)

BUTTONS = ("pause", "dictation", "grid", "calibrate", "settings", "quit")
BUTTON_GLYPHS = {"pause": "⏸", "dictation": "🎤", "grid": "▦",
                 "calibrate": "✋", "settings": "⚙", "quit": "✕"}


def _clear(widget: QWidget) -> QWidget:
    """شفافية صريحة: القواعد العامة تُلوّن الخلفية، وهذا يمنع طبقات معتمة فوق البطاقة."""
    widget.setStyleSheet("background: transparent;")
    return widget


class ControlPanel(QWidget):
    hidden_by_user = Signal()

    def __init__(self, tr: Tr, font_scale: float = 1.0, high_contrast: bool = False):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus | Qt.Tool)
        make_transparent(self)
        self.t = tr
        self.th = theme(font_scale, high_contrast)
        t = self.th
        self.setWindowTitle(tr("app_name"))
        self.setWindowIcon(app_icon(64, high_contrast))
        self.setLayoutDirection(Qt.RightToLeft if tr.rtl else Qt.LeftToRight)
        self.setStyleSheet(t.qss())
        self._drag: QPoint | None = None

        body = _clear(QWidget(self))
        self._body = body
        self._margin = t.px(10)          # مساحة الظل حول البطاقة

        # ---------------- الترويسة: الحالة + العنوان + زر الإخفاء ----------------
        head = _clear(QWidget(body))
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(t.px(14))

        self.orb = StateOrb(t, t.px(42), "loading", head)
        head_layout.addWidget(self.orb, 0, Qt.AlignVCenter)

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(t.px(2))
        self.app_name = _clear(QLabel(tr("app_name"), head))
        self.app_name.setStyleSheet(f"color: {t.c('text_faint')}; background: transparent; "
                                    f"font-size: {t.pt(9.5)}pt; font-weight: 700; letter-spacing: 0.5px;")
        self.status = _clear(QLabel(head))
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {t.c('text')}; background: transparent; "
                                  f"font-size: {t.pt(14)}pt; font-weight: 700;")
        self.camera = _clear(QLabel(head))
        self.camera.setWordWrap(True)
        self.camera.setStyleSheet(f"color: {t.c('text_dim')}; background: transparent; font-size: {t.pt(10)}pt;")
        titles.addWidget(self.app_name)
        titles.addWidget(self.status)
        titles.addWidget(self.camera)
        head_layout.addLayout(titles, 1)

        self.close_btn = QPushButton("", head)
        self.close_btn.setObjectName("iconButton")
        self.close_btn.setToolTip(tr("panel_hide"))
        self.close_btn.setFocusPolicy(Qt.NoFocus)
        self.close_btn.setFixedSize(t.px(44), t.px(44))
        self.close_btn.clicked.connect(self.hide_and_notify)
        head_layout.addWidget(self.close_btn, 0, Qt.AlignTop)

        # ---------------- بطاقة «آخر ما سُمع» ----------------
        heard_card = Card(body, inset=True)
        heard_layout = QHBoxLayout(heard_card)
        heard_layout.setContentsMargins(t.px(16), t.px(10), t.px(16), t.px(10))
        heard_layout.setSpacing(t.px(12))
        self.heard_icon = _clear(QLabel("🎙", heard_card))
        self.heard_icon.setAlignment(Qt.AlignCenter)
        self.heard_icon.setFixedWidth(t.px(24))
        self.heard_icon.setStyleSheet(f"font-size: {t.pt(14)}pt; background: transparent;")
        heard_layout.addWidget(self.heard_icon, 0)
        self.heard = Transcript(t, heard_card)
        heard_layout.addWidget(self.heard, 1)
        self.wave = AudioWaveVisualizer(t, heard_card)
        heard_layout.addWidget(self.wave, 0)

        # ---------------- الأزرار ----------------
        self.buttons: dict[str, QPushButton] = {}
        grid = QGridLayout()
        grid.setSpacing(t.px(11))
        for i, key in enumerate(BUTTONS):
            b = QPushButton(f"{BUTTON_GLYPHS[key]}  {tr(f'panel_{key}')}", body)
            b.setObjectName("primaryButton" if key == "dictation" else
                            ("dangerButton" if key == "quit" else ""))
            b.setProperty("role", "action")     # هدف كبير للنقر بالإيماءات
            b.setFocusPolicy(Qt.NoFocus)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.buttons[key] = b
            grid.addWidget(b, i // 2, i % 2)

        hint = _clear(QLabel(tr("panel_hint"), body))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {t.c('text_faint')}; background: transparent;"
                           f" font-size: {t.pt(9.5)}pt;")

        lay = QVBoxLayout(body)
        lay.setContentsMargins(t.px(26), t.px(24), t.px(26), t.px(22))
        lay.setSpacing(t.px(14))
        lay.addWidget(head)
        lay.addWidget(Rule(body))
        lay.addWidget(heard_card)
        lay.addLayout(grid)
        lay.addWidget(hint)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self._margin, self._margin, self._margin, self._margin)
        outer.addWidget(body)
        self.setMinimumWidth(t.px(500))

    # ---------------- الرسم ----------------
    def _card_rect(self) -> QRectF:
        m = self._margin
        return QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def _resize_body(self) -> None:
        m = self._margin
        self._body.setGeometry(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._resize_body()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        paint_card(p, self._card_rect(), self.th)
        p.end()

    # ---------------- التحريك والإغلاق ----------------
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._drag = None
        super().mouseReleaseEvent(e)

    def hide_and_notify(self) -> None:
        self.hide()
        self.hidden_by_user.emit()

    def closeEvent(self, e) -> None:   # الإغلاق = إخفاء؛ التطبيق يستمر
        e.ignore()
        self.hide_and_notify()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        self._keep_on_screen()

    def _keep_on_screen(self) -> None:
        area = QGuiApplication.primaryScreen().availableGeometry()
        x = min(max(self.x(), area.left() - 4), area.right() - self.width() + 4)
        y = min(max(self.y(), area.top() - 4), area.bottom() - self.height() + 4)
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    # ---------------- المحتوى ----------------
    def set_state(self, visual: str, status: str, camera: str, paused: bool,
                  mode: str | None) -> None:
        self.orb.set_state(visual)
        self.wave.set_active(visual in ("armed", "dictation", "ready", "grid") and not paused)
        self.status.setText(status)
        self.camera.setText(camera or " ")
        self.setWindowIcon(state_icon(visual, 64, self.th.high_contrast))

        self.buttons["pause"].setText(
            f"{'▶' if paused else '⏸'}  {self.t('panel_resume' if paused else 'panel_pause')}")
        self.buttons["dictation"].setText(
            f"{'⏹' if mode == 'dictation' else '🎤'}  "
            f"{self.t('panel_dictation_stop' if mode == 'dictation' else 'panel_dictation')}")
        # أثناء الإملاء يتحوّل الزر من "أساسي" إلى زر إيقاف عادي
        if mode == "dictation":
            self.buttons["dictation"].setObjectName("")
            self.buttons["dictation"].style().unpolish(self.buttons["dictation"])
            self.buttons["dictation"].style().polish(self.buttons["dictation"])

    def set_heard(self, text: str, ok: bool | None = None) -> None:
        self.heard.show_text(text, ok)
        self.heard_icon.setText("✓" if ok else ("✕" if ok is False else "🎙"))
        self.heard_icon.setStyleSheet(
            f"color: {self.th.c('ok') if ok else (self.th.c('err') if ok is False else self.th.c('text_dim'))};"
            " background: transparent;")
