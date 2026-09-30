"""اتصال العمليات الفرعية بالرئيسية عبر أنبوب مسمّى (named pipe) يُفتح بعد تهيئة الأجهزة.

لماذا لا نستخدم multiprocessing.Queue/Event الموروثة؟
على بعض الأجهزة، تهيئة برامج تشغيل الصوت أو الكاميرا (عبر PortAudio أو DirectShow)
تغلق أو تحرر مقابض (handles) لا تخصها. المقابض الموروثة لحظة إنشاء العملية تكون الضحية،
فتفشل الطوابير بشكل متقطع (PermissionError، "semaphore released too many times").
الحل: العملية الفرعية لا ترث أي مقبض؛ تهيئ جهازها أولاً ثم تتصل بالرئيسية باتصال جديد.

الاتصال محلي فقط (AF_PIPE، لا شبكة) ومحمي بمفتاح عشوائي لكل تشغيل.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
from multiprocessing.connection import Client, Connection, Listener

from core.events import ControlMessage

log = logging.getLogger(__name__)
FAMILY = "AF_PIPE" if os.name == "nt" else "AF_UNIX"


class Hub:
    """في العملية الرئيسية: يستقبل اتصالات العمليات الفرعية ويجمع أحداثها في طابور واحد."""

    def __init__(self, events: "queue.Queue"):
        self.events = events
        self.authkey = os.urandom(32)
        self.listener = Listener(family=FAMILY, authkey=self.authkey)
        self.address = self.listener.address
        self._conns: dict[str, Connection] = {}
        self._lock = threading.Lock()
        self._on_connect: dict[str, list[ControlMessage]] = {}
        self._closed = False
        threading.Thread(target=self._accept_loop, daemon=True, name="ipc-accept").start()

    def set_initial(self, name: str, messages: list[ControlMessage]) -> None:
        """رسائل تُرسل فور اتصال العامل (مثل حالة الإيقاف الحالية)."""
        self._on_connect[name] = messages

    def _accept_loop(self) -> None:
        while not self._closed:
            try:
                conn = self.listener.accept()
            except Exception:  # noqa: BLE001 - مفتاح خاطئ أو اتصال مقطوع: لا يجب أن يوقف الاستقبال
                if self._closed:
                    return
                log.warning("رُفض اتصال عامل", exc_info=True)
                continue
            try:
                name = conn.recv()
            except (OSError, EOFError):
                conn.close()
                continue
            with self._lock:
                old = self._conns.pop(name, None)
                if old is not None:
                    old.close()
                self._conns[name] = conn
            for msg in self._on_connect.get(name, []):
                self._send_conn(conn, msg)
            threading.Thread(target=self._reader, args=(name, conn), daemon=True,
                             name=f"ipc-{name}").start()

    def _reader(self, name: str, conn: Connection) -> None:
        while True:
            try:
                self.events.put(conn.recv())
            except (EOFError, OSError):
                break
        with self._lock:
            if self._conns.get(name) is conn:
                del self._conns[name]

    @staticmethod
    def _send_conn(conn: Connection, msg: ControlMessage) -> bool:
        try:
            conn.send(msg)
            return True
        except (OSError, EOFError, ValueError):
            return False

    def send(self, name: str, msg: ControlMessage) -> bool:
        with self._lock:
            conn = self._conns.get(name)
        return conn is not None and self._send_conn(conn, msg)

    def connected(self, name: str) -> bool:
        with self._lock:
            return name in self._conns

    def close(self) -> None:
        self._closed = True
        with self._lock:
            conns = list(self._conns.values())
            self._conns.clear()
        for c in conns:
            c.close()
        try:
            self.listener.close()
        except OSError:
            pass


class Link:
    """في العملية الفرعية: الاتصال بالرئيسية (يُنشأ بعد تهيئة الأجهزة)."""

    def __init__(self, address, authkey: bytes, name: str):
        self.conn = Client(address, family=FAMILY, authkey=authkey)
        self.conn.send(name)
        self._lock = threading.Lock()

    def send(self, obj) -> None:
        with self._lock:
            self.conn.send(obj)

    def poll_control(self) -> list[ControlMessage]:
        """رسائل التحكم المتاحة الآن. يرفع EOFError إذا أُغلقت الرئيسية."""
        out = []
        try:
            while self.conn.poll():
                out.append(self.conn.recv())
        except OSError as e:  # على Windows: BrokenPipeError عند إغلاق الطرف الآخر
            raise EOFError(str(e)) from e
        return out

    def close(self) -> None:
        try:
            self.conn.close()
        except OSError:
            pass
