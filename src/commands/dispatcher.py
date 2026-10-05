"""الموزّع: يستقبل أحداث الكلام، يمررها عبر بوابة التنبيه والمحلل، ويطلب التأكيد
للأوامر الخطرة، ثم ينفّذ. لا يعتمد على Qt لكي يُختبر بسهولة.

الإشعارات للواجهة تمر عبر notify(kind, **data):
    heard(text, accepted) | wake | result(ok, command, key, values, heard)
    confirm(command, heard) | confirm_cleared(executed) | state(...)
    voice(active, level) | hand(points, pose)   ← لمؤشر الحالة فقط
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable

from commands.actions import ActionContext, ActionError, run_steps
from commands.modes import DictationMode, Mode
from commands.parser import CommandParser, Match, is_no, is_yes
from commands.wake import WakeGate, strip_wake
from core.events import (CalibrationSample, DictationEvent, GestureEvent, HandPreviewEvent,
                         PartialSpeechEvent, SpeechEvent, StatusEvent, VoiceActivityEvent)

log = logging.getLogger(__name__)

Notify = Callable[..., None]
_NO_FOLLOWUP = {"app.sleep", "app.pause"}


class Dispatcher:
    def __init__(self, ctx: ActionContext, parser: CommandParser, gate: WakeGate,
                 notify: Notify, paused: threading.Event,
                 clock: Callable[[], float] = time.monotonic):
        self.ctx = ctx
        self.parser = parser
        self.gate = gate
        self.notify = notify
        self.paused = paused
        self.clock = clock
        self._pending: tuple[Match, float, str] | None = None
        self._lock = threading.RLock()
        self.mode: Mode | None = None
        self._draining: DictationMode | None = None   # إملاء انتهى وما زال ينتظر نصوصاً
        # يُستدعى عند الخروج من وضع (name, abort): المتحكم يوقف Whisper مثلاً
        self.on_mode_exit: Callable[[str, bool], None] | None = None

    @property
    def lang(self) -> str:
        return self.ctx.config.speech.language

    @property
    def pending(self) -> Match | None:
        return self._pending[0] if self._pending else None

    # ------------------------------------------------------------------
    def handle(self, ev) -> None:
        if isinstance(ev, SpeechEvent):
            self.handle_speech(ev)
        elif isinstance(ev, PartialSpeechEvent):
            self.notify("partial", text=ev.text)
        elif isinstance(ev, StatusEvent):
            self.notify("status", source=ev.source, state=ev.state, detail=ev.detail)
        elif isinstance(ev, GestureEvent):
            self.handle_gesture(ev)
        elif isinstance(ev, DictationEvent):
            with self._lock:
                self.handle_dictation(ev)
        elif isinstance(ev, CalibrationSample):
            self.notify("calib_sample", sample=ev)
        elif isinstance(ev, VoiceActivityEvent):
            self.notify("voice", active=ev.active, level=ev.level)
        elif isinstance(ev, HandPreviewEvent):
            self.notify("hand", points=ev.points, pose=ev.pose)

    # ---------------- الأوضاع ----------------
    def enter_mode(self, mode: Mode) -> None:
        with self._lock:
            self.exit_mode()
            self.mode = mode
            mode.enter()

    def exit_mode(self, abort: bool = False) -> None:
        """abort=True (إيقاف طارئ): لا يُكتب أي نص إملاء معلق."""
        with self._lock:
            m, self.mode = self.mode, None
            if m is None:
                return
            m.exit()
            if isinstance(m, DictationMode):
                self._draining = None if abort or not m.pending else m
            if self.on_mode_exit is not None:
                self.on_mode_exit(m.name, abort)

    def handle_dictation(self, ev: DictationEvent) -> None:
        target = self.mode if isinstance(self.mode, DictationMode) else self._draining
        if target is None:
            return
        still_pending = target.on_text(ev)
        if target is self._draining and not still_pending:
            self._draining = None

    def handle_gesture(self, ev: GestureEvent) -> None:
        """إجراءات الإيماءات غير المتعلقة بالفأرة (الفأرة تُنفَّذ في عملية الرؤية)."""
        action = ev.data.get("action", "")
        if ev.name == "dwell_progress":   # تقدّم النقر بالتحويم: للواجهة فقط، ليس إجراءً
            try:
                self.notify("dwell", progress=float(action))
            except ValueError:
                pass
            return
        if action == "app.pause":
            # عملية الرؤية أوقفت التحكم فوراً؛ هنا الإشعار والصوت وإلغاء التأكيد المعلق
            self.ctx.app.pause()
        elif action == "app.resume":
            self.ctx.app.resume()
        elif action.startswith("cmd:"):
            self._gesture_command(action[4:], ev.name)
        elif action:
            self.execute_steps([{"action": action}], ev.name)
        self.notify("gesture", name=ev.name, action=action)

    def _gesture_command(self, cid: str, gesture: str) -> None:
        """إيماءة مربوطة بأمر (ملف شخصي). الأوامر الخطرة تبقى للصوت فقط: الإيماءة لا تُسأل "نعم/لا"."""
        spec = next((s for s in self.parser.specs if s.id == cid), None)
        if spec is None or spec.dangerous:
            key = "unknown_action" if spec is None else "gesture_needs_voice"
            self.notify("result", ok=False, command=gesture, key=key, values={"name": cid}, heard="")
            self._sound("error")
            return
        self.execute_steps(spec.steps, gesture)

    def handle_speech(self, ev: SpeechEvent) -> None:
        with self._lock:
            self._handle_speech(ev)

    def _handle_speech(self, ev: SpeechEvent) -> None:
        lang = ev.lang or self.lang
        cands = [t for t in dict.fromkeys([ev.text, ev.free_text]) if t and t.strip()
                 and t.strip() != "[unk]"]
        if not cands:
            return
        heard = ev.free_text or ev.text

        # 1) الإيقاف الطارئ: دائماً، بلا كلمة تنبيه ولا تأكيد
        for c in cands:
            _, rest = strip_wake(c, self.gate.wake_words)
            m = self.parser.parse(rest or c, lang, only_always=True)
            if m:
                self.notify("heard", text=heard, accepted=True)
                self._cancel_pending(notify=True)
                self._execute(m, heard)
                return

        # 2) انتظار تأكيد أمر خطر
        if self._pending:
            self.tick()
        if self._pending:
            body = [strip_wake(c, self.gate.wake_words)[1] or c for c in cands]
            if any(is_yes(b, lang) for b in body):
                match, _, h = self._pending
                self._pending = None
                self.notify("heard", text=heard, accepted=True)
                self.notify("confirm_cleared", executed=True)
                self._execute(match, h)
            elif any(is_no(b, lang) for b in body):
                self.notify("heard", text=heard, accepted=True)
                self._cancel_pending(notify=True)
                self._sound("ok")
            else:
                self.notify("heard", text=heard, accepted=False)
            return

        # 3) وضع خاص نشط (إملاء/شبكة): بلا كلمة تنبيه
        if self.mode is not None and not self.paused.is_set():
            if self.mode.handle_speech(ev.seg_id, cands, heard, lang):
                return

        # 4) بوابة كلمة التنبيه
        results = [self.gate.process(c) for c in cands]
        woke = any(w for _, w in results)
        texts = [t for t, _ in results if t]
        if not texts:
            if woke:
                self.notify("wake")
                self._sound("wake")
            else:
                self.notify("heard", text=heard, accepted=False)
            return

        # 4) التحليل: القيد بالقواعد أولاً، والنص الحر لقيم الخانات
        match = self._best_match(texts, lang)
        if match is None:
            self.notify("heard", text=heard, accepted=False)
            if woke:
                self.notify("result", ok=False, command=None, key="not_understood",
                            values={}, heard=heard)
                self._sound("error")
            return

        # 5) أثناء الإيقاف المؤقت: فقط أمر الاستئناف
        if self.paused.is_set() and not any(s.get("action") == "app.resume" for s in match.spec.steps):
            self.notify("heard", text=heard, accepted=False)
            self.notify("result", ok=False, command=match.id, key="paused", values={}, heard=heard)
            return

        self.notify("heard", text=heard, accepted=True)
        if match.spec.dangerous and self.ctx.config.safety.confirm_dangerous:
            deadline = self.clock() + self.ctx.config.safety.confirm_timeout_s
            self._pending = (match, deadline, heard)
            self.notify("confirm", command=match.id, heard=heard)
            self._sound("confirm")
            return
        self._execute(match, heard)

    def _best_match(self, texts: list[str], lang: str) -> Match | None:
        matches = [self.parser.parse(t, lang) for t in texts]
        primary = matches[0]
        alt = matches[1] if len(matches) > 1 else None
        # [unk] في نتيجة القواعد = كلام خارج الأوامر؛ لا يُقبل إلا كقيمة خانة
        if primary and not primary.slots and "[unk]" in texts[0]:
            primary = None
        if primary and primary.slots:
            # قيمة الخانة من النص الحر أدق (التعرف المقيّد لا يعرف الكلمات الحرة)
            if alt and alt.id == primary.id:
                return alt
            if any("[unk]" in v for v in primary.slots.values()):
                return alt
            return primary
        if primary and alt:
            return primary if primary.score >= alt.score else alt
        return primary or alt

    # ------------------------------------------------------------------
    def execute_steps(self, steps: list[dict], label: str) -> bool:
        """تنفيذ مباشر (للإيماءات والواجهة). يرجع True عند النجاح."""
        with self._lock:
            if self.paused.is_set() and not any(s.get("action") == "app.resume" for s in steps):
                return False
            try:
                run_steps(self.ctx, steps)
                self.notify("result", ok=True, command=label, key="done", values={}, heard="")
                return True
            except ActionError as e:
                self.notify("result", ok=False, command=label, key=e.key, values=e.values, heard="")
            except Exception:  # noqa: BLE001
                log.exception("فشل تنفيذ %s", label)
                self.notify("result", ok=False, command=label, key="action_failed", values={}, heard="")
            return False

    def _execute(self, match: Match, heard: str) -> None:
        actions = {s.get("action") for s in match.spec.steps}
        try:
            run_steps(self.ctx, match.spec.steps, match.slots)
        except ActionError as e:
            self.notify("result", ok=False, command=match.id, key=e.key, values=e.values, heard=heard)
            self._sound("error")
            return
        except Exception:  # noqa: BLE001 - لا يجب أن يسقط الموزّع بسبب إجراء
            log.exception("فشل تنفيذ الأمر %s", match.id)
            self.notify("result", ok=False, command=match.id, key="action_failed", values={}, heard=heard)
            self._sound("error")
            return
        self.notify("result", ok=True, command=match.id, key="done", values=match.slots, heard=heard)
        if not actions & _NO_FOLLOWUP:
            self.gate.after_command()
            self._sound("ok")

    def _cancel_pending(self, notify: bool) -> None:
        if self._pending:
            self._pending = None
            if notify:
                self.notify("confirm_cleared", executed=False)

    def cancel_pending(self) -> None:
        with self._lock:
            self._cancel_pending(notify=True)

    def confirm_pending(self) -> None:
        """تأكيد من زر الواجهة."""
        with self._lock:
            if self._pending:
                match, _, heard = self._pending
                self._pending = None
                self.notify("confirm_cleared", executed=True)
                self._execute(match, heard)

    def tick(self) -> None:
        if self._pending and self.clock() > self._pending[1]:
            self._cancel_pending(notify=True)
        if self.mode is not None:
            self.mode.tick(self.clock())

    def _sound(self, kind: str) -> None:
        fb = self.ctx.config.feedback
        if fb.sounds:
            try:
                self.ctx.os.play_sound(kind, fb.sound_volume)
            except Exception:  # noqa: BLE001
                log.debug("تعذر تشغيل الصوت", exc_info=True)

    # ------------------------------------------------------------------
    def run(self, events: "queue.Queue | object", stop: threading.Event) -> None:
        """حلقة الخيط: تقرأ من طابور الأحداث حتى يُطلب الإيقاف."""
        while not stop.is_set():
            try:
                ev = events.get(timeout=0.2)
            except queue.Empty:
                with self._lock:
                    self.tick()
                continue
            except (EOFError, OSError):
                break
            try:
                self.handle(ev)
            except Exception:  # noqa: BLE001
                log.exception("خطأ في معالجة الحدث %r", ev)
