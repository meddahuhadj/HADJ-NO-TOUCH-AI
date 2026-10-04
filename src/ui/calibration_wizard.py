"""معالج المعايرة: تحضير قصير ثم أربع خطوات (نحو 20 ثانية) تتقدم تلقائياً دون لمس.

التحضير يفحص الإضاءة وعكس الضوء والمسافة مباشرة، وينتقل وحده عندما تصبح الظروف جيدة.
لكل خطوة رسم متحرك يُري الحركة، وتلميح مباشر إن ساءت الظروف، ونغمة عند كل انتقال.

في النهاية: ملخص، ثم حفظ تلقائي بعد 5 ثوانٍ إن كانت النتيجة صالحة
(زر "إلغاء" متاح لمن يستطيع النقر).
"""
from __future__ import annotations

import time
from collections import deque
from typing import Callable

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QGuiApplication, QPainter
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QProgressBar, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from ui.calibration_art import CalibrationArt
from ui.i18n import Tr
from ui.theme import Theme, theme
from ui.widgets import StepDots, chip_qss, make_transparent, paint_card
from vision.calibration import STEPS, Calibrator, dominant_hints

AUTO_SAVE_S = 5
AUTO_CLOSE_S = 12
PREPARE_MAX_S = 6.0    # التحضير لا يطول أكثر من هذا مهما كانت الظروف
GOOD_HOLD_S = 1.2      # ظروف جيدة لهذه المدة ← البدء فوراً
HINT_WINDOW = 15       # آخر 15 عينة (~0.5 ث) لحساب التلميح المباشر


class CalibrationWizard(QWidget):
    finished = Signal(object)   # dict (تغييرات الإعدادات) أو None عند الإلغاء

    def __init__(self, tr: Tr, font_scale: float = 1.0, high_contrast: bool = False,
                 cue: Callable[[str], None] | None = None):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus)
        make_transparent(self)
        self.t = tr
        self.th: Theme = theme(font_scale, high_contrast)
        t = self.th
        self.setStyleSheet(t.qss())
        self._margin = t.px(10)
        self._accent = ""

        body = QWidget(self)
        body.setStyleSheet("background: transparent;")
        self._body = body

        head = QWidget(body)
        head.setStyleSheet("background: transparent;")
        head_layout = QVBoxLayout(head)
        head_layout.setContentsMargins(0, 0, 0, 0)
        head_layout.setSpacing(t.px(2))
        self.title = QLabel(tr("calib_title"), head)
        self.title.setStyleSheet(f"color: {t.c('text_faint')}; background: transparent;"
                                 f" font-size: {t.pt(9.5)}pt; font-weight: 700;"
                                 " letter-spacing: 0.6px;")
        self.step_label = QLabel(head)
        self.step_label.setFont(QFont("Segoe UI", t.pt(20), QFont.DemiBold))
        self.step_label.setWordWrap(True)
        self.step_label.setAlignment(Qt.AlignCenter)
        self.step_label.setStyleSheet(self._step_qss())
        head_layout.addWidget(self.title)
        head_layout.addWidget(self.step_label)

        self.dots = StepDots(t, len(STEPS) + 1, body)   # +1 للتحضير
        self.art = CalibrationArt(t, body, tr.rtl, tr("calib_distance"))
        self.cue = cue or (lambda _kind: None)
        self._recent: deque = deque(maxlen=HINT_WINDOW)
        self._good_since: float | None = None
        self._hint_key = None

        self.hand = QLabel(body)
        self.hand.setAlignment(Qt.AlignCenter)
        self.hand.setWordWrap(True)
        self.hand.setMinimumHeight(t.px(26))

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(t.px(10))

        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setAlignment(Qt.AlignCenter)
        self.details.setStyleSheet(f"color: {t.c('text_dim')}; background: transparent;"
                                   f" font-size: {t.pt(10.5)}pt;")

        self.btn_save = QPushButton(tr("calib_save"), body)
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel = QPushButton(tr("calib_cancel"), body)
        self.btn_cancel.setObjectName("ghostButton")
        self.btn_cancel.clicked.connect(self._cancel)
        for b in (self.btn_save, self.btn_cancel):
            b.setProperty("role", "action")
            b.setFocusPolicy(Qt.NoFocus)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        buttons = QHBoxLayout()
        buttons.setSpacing(t.px(10))
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_cancel)

        lay = QVBoxLayout(body)
        lay.setContentsMargins(t.px(34), t.px(28), t.px(34), t.px(24))
        lay.setSpacing(t.px(12))
        lay.addWidget(head)
        lay.addWidget(self.dots)
        lay.addWidget(self.art)
        lay.addWidget(self.hand)
        lay.addWidget(self.progress)
        lay.addWidget(self.details)
        lay.addLayout(buttons)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self._margin, self._margin, self._margin, self._margin)
        outer.addWidget(body)
        self.setLayoutDirection(Qt.RightToLeft if tr.rtl else Qt.LeftToRight)
        self.setFixedWidth(t.px(680))
        self._hand_ok = True
        self._set_hand(seen=False)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self.cal: Calibrator | None = None
        self.result = None
        self._phase = "idle"          # prepare | steps | summary | idle
        self._step = 0
        self._t0 = 0.0
        self._last_hand = 0.0

    # ---- الرسم ----
    def _rect(self) -> QRectF:
        m = self._margin
        return QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def _relayout(self) -> None:
        m = self._margin
        self._body.setGeometry(m, m, self.width() - 2 * m, self.height() - 2 * m)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        paint_card(p, self._rect(), self.th, radius=self.th.px(24), accent=self._accent or None,
                   accent_side="right" if self.t.rtl else "left")
        p.end()

    def _step_qss(self, color: str | None = None) -> str:
        """التعليمة الحالية: أكبر نص في النافذة لأنها ما يجب أن يُقرأ من بعيد."""
        return (f"color: {color or self.th.c('text')}; background: transparent;"
                f" font-size: {self.th.pt(17)}pt; font-weight: 600;")

    def _set_accent(self, name: str) -> None:
        self._accent = self.th.state(name)
        self.update()

    def _set_hand(self, seen: bool) -> None:
        self._hand_ok = seen
        if seen:
            self.hand.setText(self.t("calib_hand_ok"))
            self.hand.setStyleSheet(chip_qss(self.th, self.th.c("ok")))
        else:
            self.hand.setText(self.t("calib_hand_missing"))
            self.hand.setStyleSheet(chip_qss(self.th, self.th.c("err")))

    # ------------------------------------------------------------------
    def start(self) -> None:
        self.cal = Calibrator()
        self.result = None
        self._recent.clear()
        self._good_since = None
        self._hint_key = None
        self._last_hand = 0.0
        self._phase = "prepare"
        self._step = -1
        self._t0 = time.monotonic()
        self.title.setText(f"{self.t('calib_title')} · {self.t('calib_prepare')}")
        self.step_label.setText(self.t("calib_step_prepare"))
        self.step_label.setStyleSheet(self._step_qss())
        self.dots.set_ok(True)
        self.dots.set_current(0)
        self.art.show()
        self.art.set_scene("prepare")
        self.progress.setRange(0, int(PREPARE_MAX_S * 10))
        self.progress.setValue(0)
        self.btn_save.hide()
        self.btn_cancel.show()
        self.details.setText("")
        self._show_hint([])
        self._set_accent("grid")
        self.cue("step")
        self.adjustSize()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.center() - self.rect().center())
        self.show()
        self.raise_()
        self._timer.start()

    def add_sample(self, sample) -> None:
        if self._phase not in ("prepare", "steps") or self.cal is None:
            return
        self._recent.append(sample)
        if sample.has_hand:
            self._last_hand = time.monotonic()
        if self._phase == "steps":
            name, _ = STEPS[self._step]
            self.cal.add(name, sample, time.monotonic() - self._t0)

    def live_hints(self) -> list[str]:
        return dominant_hints(list(self._recent))

    def _show_hint(self, hints: list[str]) -> None:
        """أهم مشكلة حالية، أو نصيحة الإضاءة الثابتة في التحضير."""
        key = hints[0] if hints else None
        if key == self._hint_key and self.details.text():
            return
        self._hint_key = key
        if key:
            self.details.setText(self.t(f"calib_hint_{key}"))
            self.details.setStyleSheet(f"color: {self.th.c('warn')}; background: transparent;"
                                       f" font-size: {self.th.pt(12)}pt; font-weight: 600;")
        else:
            text = self.t("calib_tip_light") if self._phase == "prepare" else ""
            self.details.setText(text)
            self.details.setStyleSheet(f"color: {self.th.c('text_dim')}; background: transparent;"
                                       f" font-size: {self.th.pt(10.5)}pt;")

    def _next_step(self) -> None:
        self._step += 1
        if self._step >= len(STEPS):
            self._show_summary()
            return
        name, dur = STEPS[self._step]
        self._phase = "steps"
        self._t0 = time.monotonic()
        self.title.setText(f"{self.t('calib_title')} · {self._step + 1}/{len(STEPS)}")
        self.step_label.setText(self.t(f"calib_step_{name}"))
        self.step_label.setStyleSheet(self._step_qss())
        self.dots.set_current(self._step + 1)
        self.art.set_scene(name)
        self.progress.setRange(0, int(dur * 10))
        self.progress.setValue(0)
        self._hint_key = "-"
        self._show_hint(self.live_hints())
        self.cue("step")

    def _tick(self) -> None:
        now = time.monotonic()
        elapsed = now - self._t0
        seen, hints = False, []
        if self._phase in ("prepare", "steps"):
            seen = now - self._last_hand < 0.5
            if seen != self._hand_ok:
                self._set_hand(seen)
                self._set_accent("grid" if seen else "error")
            hints = self.live_hints()
            self._show_hint(hints)
        if self._phase == "prepare":
            self.progress.setValue(int(min(elapsed, PREPARE_MAX_S) * 10))
            if not (seen and not hints):
                self._good_since = None
            elif self._good_since is None:
                self._good_since = now
            ready = self._good_since is not None and now - self._good_since >= GOOD_HOLD_S
            if ready or elapsed >= PREPARE_MAX_S:
                self._next_step()
        elif self._phase == "steps":
            _, dur = STEPS[self._step]
            self.progress.setValue(int(min(elapsed, dur) * 10))
            if elapsed >= dur:
                self._next_step()
        elif self._phase == "summary":
            ok = self.result is not None and self.result.ok
            limit = AUTO_SAVE_S if ok else AUTO_CLOSE_S
            left = max(0, int(limit - elapsed + 0.99))
            self.progress.setValue(int(min(elapsed, limit) * 10))
            self.hand.setText(self.t("calib_saving_in", s=left) if ok
                              else self.t("calib_closing_in", s=left))
            self.hand.setStyleSheet(chip_qss(self.th, self.th.c("ok") if ok else self.th.c("err")))
            if elapsed >= limit:
                self._save() if ok else self._cancel()

    def _show_summary(self) -> None:
        self._phase = "summary"
        self._t0 = time.monotonic()
        self.result = self.cal.result()
        r = self.result
        lines = [self.t("calib_detection", pct=int(r.detection * 100))]
        if r.pinch_enter is not None:
            lines.append(self.t("calib_pinch_ok", enter=f"{r.pinch_enter:.2f}", exit=f"{r.pinch_exit:.2f}"))
        if r.zone is not None:
            w, h = r.zone[2] - r.zone[0], r.zone[3] - r.zone[1]
            lines.append(self.t("calib_zone_ok", w=int(w * 100), h=int(h * 100)))
        lines += [self.t(f"calib_warn_{w}") for w in r.warnings]
        self.title.setText(self.t("calib_title"))
        self.step_label.setText(self.t("calib_done_ok" if r.ok else "calib_done_fail"))
        self.step_label.setStyleSheet(self._step_qss(self.th.c('ok') if r.ok else self.th.c('err')))
        self.details.setText("\n".join(lines))
        self.progress.setRange(0, (AUTO_SAVE_S if r.ok else AUTO_CLOSE_S) * 10)
        self.dots.set_current(len(STEPS) + 1)
        self.dots.set_ok(r.ok)
        self.art.set_scene("none")
        self.art.hide()
        self.details.setStyleSheet(f"color: {self.th.c('text_dim')}; background: transparent;"
                                   f" font-size: {self.th.pt(10.5)}pt;")
        self.cue("ok" if r.ok else "error")
        self._set_accent("ready" if r.ok else "error")
        self.btn_save.setVisible(r.ok)
        self.adjustSize()

    def _save(self) -> None:
        changes = self.result.config_changes() if self.result is not None else None
        self._close(changes or None)

    def _cancel(self) -> None:
        self._close(None)

    def _close(self, changes) -> None:
        if self._phase == "idle":
            return
        self._phase = "idle"
        self._timer.stop()
        self.art.set_scene("none")
        self.hide()
        self.finished.emit(changes)
