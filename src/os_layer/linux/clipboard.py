"""حافظة X11 (CLIPBOARD): كتابة نص أي لغة باللصق حين يتعذر إرسال محارفه مفتاحاً مفتاحاً.

تحت XWayland لا نعيد ربط المفاتيح (قد يقطع اتصال X)، فنضع النص في الحافظة ونرسل Ctrl+V،
ثم نخدم طلبات التطبيق الذي يلصق. بعدها تُعاد الحافظة كما كانت، أو تُفرَّغ إن كانت فارغة:
النص المُملى لا يبقى في الحافظة (خصوصية).

اتصال X خاص وخيط خاص لخدمة الطلبات (المالك يجب أن يجيب ما دام مالكاً).

برامج أخرى تطلب الحافظة فور تغيّرها (جسر حافظة WSLg، سجلّات الحافظة): لذلك ننتظر طلب
التطبيق الذي يملك التركيز تحديداً (يُعرف بقاعدة معرّفات موارده في X) قبل إعادة الحافظة،
وإلا لصق التطبيقُ المحتوى القديم. ونعلن النص "سرياً" (x-kde-passwordManagerHint) لكي لا تحفظه
سجلات الحافظة التي تحترم هذا العرف (Klipper، CopyQ…).
"""
from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger(__name__)

TEXT_TARGETS = ("UTF8_STRING", "text/plain;charset=utf-8", "TEXT", "STRING")
SECRET_HINT = "x-kde-passwordManagerHint"


class ClipboardOwner:
    def __init__(self, display_name: str | None = None):
        from Xlib import X, display
        self.X = X
        self.d = display.Display(display_name)
        self.win = self.d.screen().root.create_window(0, 0, 1, 1, 0, X.CopyFromParent, X.InputOnly,
                                                      X.CopyFromParent,
                                                      event_mask=X.PropertyChangeMask)
        self.atoms = {n: self.d.intern_atom(n) for n in
                      ("CLIPBOARD", "TARGETS", "ATOM", "HADJ_CLIP", SECRET_HINT, *TEXT_TARGETS)}
        self._text: str | None = None
        self._mask = self.d.display.info.resource_id_mask
        self._served_by: set[int] = set()     # قواعد معرّفات العملاء الذين طلبوا النص
        self._cond = threading.Condition()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------ القراءة
    def owned(self) -> bool:
        with self._lock:
            return self.d.get_selection_owner(self.atoms["CLIPBOARD"]) == self.win

    def get_text(self, timeout: float = 0.5) -> str | None:
        """نص الحافظة الحالي (من مالكها، أياً كان)، أو None إن كانت فارغة أو بلا نص."""
        X = self.X
        if self._text is not None and self.owned():
            return self._text
        self._stop_serving()
        with self._lock:
            if self.d.get_selection_owner(self.atoms["CLIPBOARD"]) == X.NONE:
                return None
            self.win.convert_selection(self.atoms["CLIPBOARD"], self.atoms["UTF8_STRING"],
                                       self.atoms["HADJ_CLIP"], X.CurrentTime)
            self.d.flush()
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                if not self.d.pending_events():
                    time.sleep(0.01)
                    continue
                ev = self.d.next_event()
                if ev.type == X.SelectionNotify:
                    if ev.property == X.NONE:
                        return None
                    prop = self.win.get_full_property(self.atoms["HADJ_CLIP"], X.AnyPropertyType)
                    self.win.delete_property(self.atoms["HADJ_CLIP"])
                    if prop is None:
                        return None
                    v = prop.value
                    return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)
        return None

    # ------------------------------------------------------------------ الامتلاك والخدمة
    def set_text(self, text: str) -> bool:
        X = self.X
        with self._lock:
            self._text = text
            with self._cond:
                self._served_by.clear()
            self.win.set_selection_owner(self.atoms["CLIPBOARD"], X.CurrentTime)
            self.d.sync()
            if not self.owned():
                return False
        self._start_serving()
        return True

    def clear(self) -> None:
        """تفريغ الحافظة إن كنا مالكيها (لا نمس حافظة برنامج آخر)."""
        X = self.X
        self._stop_serving()
        with self._lock:
            if self.d.get_selection_owner(self.atoms["CLIPBOARD"]) == self.win:
                from Xlib.protocol import request
                request.SetSelectionOwner(display=self.d.display, window=X.NONE,
                                          selection=self.atoms["CLIPBOARD"], time=X.CurrentTime)
                self.d.sync()
            self._text = None

    def client_base(self, window_id: int) -> int:
        """كل موارد عميل X تتشارك هذه القاعدة (البتات خارج resource_id_mask)."""
        return int(window_id) & ~self._mask

    def wait_served(self, timeout: float, client: int | None = None) -> bool:
        """هل طلب العميلُ client (قاعدة معرّفاته) النصَّ خلال المهلة؟ client=None: أي عميل."""
        end = time.monotonic() + timeout
        with self._cond:
            while True:
                if (client is None and self._served_by) or (client is not None and client in self._served_by):
                    return True
                left = end - time.monotonic()
                if left <= 0:
                    return False
                self._cond.wait(left)

    def _start_serving(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, daemon=True, name="clipboard")
        self._thread.start()

    def _stop_serving(self) -> None:
        if self._thread is not None:
            self._stop.set()
            self._thread.join(1.0)
            self._thread = None

    def _serve(self) -> None:
        X = self.X
        while not self._stop.is_set():
            with self._lock:
                ev = self.d.next_event() if self.d.pending_events() else None
                if ev is not None:
                    if ev.type == X.SelectionRequest:
                        self._answer(ev)
                    elif ev.type == X.SelectionClear:
                        self._text = None      # برنامج آخر أخذ الحافظة: انتهت مهمتنا
                        return
            if ev is None:
                time.sleep(0.01)

    def _answer(self, req) -> None:
        from Xlib import Xatom
        from Xlib.protocol import event
        X = self.X
        a = self.atoms
        prop = req.property if req.property != X.NONE else req.target
        text = self._text or ""
        served = False
        try:
            if req.target == a["TARGETS"]:
                req.requestor.change_property(prop, Xatom.ATOM, 32,
                                              [a["TARGETS"], a[SECRET_HINT], *(a[t] for t in TEXT_TARGETS)])
            elif req.target == a[SECRET_HINT]:
                req.requestor.change_property(prop, a["UTF8_STRING"], 8, b"secret")
            elif req.target in (a["UTF8_STRING"], a["text/plain;charset=utf-8"], a["TEXT"]):
                target = a["UTF8_STRING"] if req.target == a["TEXT"] else req.target
                req.requestor.change_property(prop, target, 8, text.encode("utf-8"))
                served = True
            elif req.target == a["STRING"]:
                req.requestor.change_property(prop, Xatom.STRING, 8, text.encode("latin-1", "replace"))
                served = True
            else:
                prop = X.NONE
        except Exception:  # noqa: BLE001 - نافذة الطالب أُغلقت
            prop = X.NONE
        ev = event.SelectionNotify(time=req.time, requestor=req.requestor, selection=req.selection,
                                   target=req.target, property=prop)
        req.requestor.send_event(ev)
        self.d.flush()
        if served:
            with self._cond:
                self._served_by.add(self.client_base(req.requestor.id))
                self._cond.notify_all()

    def close(self) -> None:
        self._stop_serving()
        try:
            self.d.close()
        except Exception:  # noqa: BLE001
            pass
