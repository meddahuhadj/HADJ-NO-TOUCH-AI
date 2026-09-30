"""أوضاع الموزّع الخاصة: الإملاء والشبكة الصوتية.

في الوضع النشط لا تلزم كلمة التنبيه. الإيقاف الطارئ و"نعم/لا" للتأكيد يُعالجان قبل الوضع دائماً.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from commands.dictation import DictationSession, classify_command
from commands.grid import GridState, parse_grid_command, parse_number
from commands.wake import strip_wake
from core.events import DictationEvent

if TYPE_CHECKING:
    from commands.dispatcher import Dispatcher

log = logging.getLogger(__name__)


class Mode:
    name = "mode"

    def __init__(self, disp: "Dispatcher"):
        self.d = disp

    def enter(self) -> None: ...
    def exit(self) -> None: ...

    def handle_speech(self, seg_id: int, cands: list[str], heard: str, lang: str) -> bool:
        """True = العبارة استُهلكت في هذا الوضع."""
        return False

    def tick(self, now: float) -> None: ...


class DictationMode(Mode):
    name = "dictation"

    def __init__(self, disp: "Dispatcher", lang: str):
        super().__init__(disp)
        self.session = DictationSession(lang)
        self.pending: set[int] = set()      # عبارات تنتظر نصها
        self.consumed: set[int] = set()     # عبارات كانت أوامر (لا تُكتب)
        self.active = False

    def enter(self) -> None:
        self.active = True
        self.d.notify("mode", name=self.name, active=True)

    def exit(self) -> None:
        self.active = False
        self.d.notify("mode", name=self.name, active=False, pending=len(self.pending))

    def handle_speech(self, seg_id, cands, heard, lang) -> bool:
        if not self.active:
            return False
        body = []
        woke = False
        for c in cands:
            found, rest = strip_wake(c, self.d.gate.wake_words)
            woke |= found
            body.append(rest if found else c)
        for b in body:
            cmd = classify_command(b, lang)
            if cmd == "stop":
                self.consumed.add(seg_id)
                self.d.notify("heard", text=heard, accepted=True)
                self.d.exit_mode()
                return True
            if cmd == "undo":
                self.consumed.add(seg_id)
                n = self.session.undo()
                if n:
                    self.d.ctx.os.key("backspace", n)
                self.d.notify("heard", text=heard, accepted=True)
                return True
        if woke:
            # "حاسوب احفظ" أثناء الإملاء: أمر عادي، لا يُكتب
            self.consumed.add(seg_id)
            return False
        self.pending.add(seg_id)
        self.d.notify("dictation_pending", count=len(self.pending))
        return True

    def on_text(self, ev: DictationEvent) -> bool:
        """يرجع True إذا بقيت عبارات معلقة."""
        if ev.seg_id in self.consumed:
            self.consumed.discard(ev.seg_id)
            return bool(self.pending)
        if ev.seg_id not in self.pending:
            return bool(self.pending)
        self.pending.discard(ev.seg_id)
        typed = self.session.render(ev.text)
        if typed and not self.d.paused.is_set():
            try:
                self.d.ctx.os.type_text(typed)
                self.session.commit(typed)
            except Exception:  # noqa: BLE001
                log.exception("فشل كتابة نص الإملاء")
        self.d.notify("dictation_typed", text=typed.strip(), pending=len(self.pending),
                      seconds=ev.seconds)
        return bool(self.pending)


class GridMode(Mode):
    name = "grid"

    def __init__(self, disp: "Dispatcher", timeout_s: float = 30.0):
        super().__init__(disp)
        self.state = GridState(disp.ctx.os.screen_rect())
        self.timeout_s = timeout_s
        self._last = disp.clock()

    def _show(self) -> None:
        self.d.notify("grid", rect=self.state.rect, screen=self.state.screen,
                      level=self.state.level, can_split=self.state.can_split)

    def enter(self) -> None:
        self._last = self.d.clock()
        self.d.notify("mode", name=self.name, active=True)
        self._show()

    def exit(self) -> None:
        self.d.notify("mode", name=self.name, active=False)

    def handle_speech(self, seg_id, cands, heard, lang) -> bool:
        self._last = self.d.clock()
        woke = False
        for c in cands:
            found, rest = strip_wake(c, self.d.gate.wake_words)
            woke |= found
            text = rest if found else c
            n = parse_number(text, lang)
            if n is not None:
                if self.state.can_split and self.state.select(n):
                    self.d.ctx.os.mouse_move(*self.state.target)
                self.d.notify("heard", text=heard, accepted=True)
                self._show()
                return True
            cmd = parse_grid_command(text, lang)
            if cmd is None:
                continue
            self.d.notify("heard", text=heard, accepted=True)
            os_ = self.d.ctx.os
            if cmd == "back":
                self.state.back()
                self._show()
                return True
            if cmd == "close":
                self.d.exit_mode()
                return True
            # إخفاء الشبكة أولاً حتى لا تعترض النقرة، ثم التحريك والنقر
            self.d.exit_mode()
            os_.mouse_move(*self.state.target)
            if cmd == "click":
                os_.mouse_button("left", "click", 1)
            elif cmd == "double_click":
                os_.mouse_button("left", "click", 2)
            elif cmd == "right_click":
                os_.mouse_button("right", "click", 1)
            self.d.notify("result", ok=True, command=f"grid_{cmd}", key="done", values={}, heard=heard)
            return True
        if woke:
            # أمر عادي بكلمة التنبيه: أغلق الشبكة ودعه يُعالج كالمعتاد
            self.d.exit_mode()
            return False
        self.d.notify("heard", text=heard, accepted=False)
        return True

    def tick(self, now: float) -> None:
        if now - self._last > self.timeout_s:
            self.d.exit_mode()
