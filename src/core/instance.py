"""التحكم بالنسخة العاملة من سطر الأوامر: HADJ-NoTouch --pause | --resume | --toggle-pause | --show

الاستخدام الأساسي: حيث يستحيل اختصار عام (Wayland مثلاً) يربط المستخدم اختصاراً من إعدادات سطح
المكتب بالأمر `--pause`، فيبقى الإيقاف الطارئ متاحاً من لوحة المفاتيح. وعلى Windows: تشغيل
التطبيق مرة ثانية يُظهر لوحته بدل رسالة "يعمل مسبقاً".

قناة محلية (QLocalServer: أنبوب مسمّى على Windows، مقبس Unix على غيره) مقصورة على المستخدم
الحالي، لا شبكة. أوامر معروفة فقط، بطول محدود.
"""
from __future__ import annotations

import getpass
import hashlib
import logging
from typing import Callable

log = logging.getLogger(__name__)

COMMANDS = ("pause", "resume", "toggle-pause", "show")
MAX_LEN = 32


def server_name(user: str | None = None) -> str:
    """اسم ثابت لكل مستخدم (مُجزّأ: لا يكشف اسم المستخدم في /tmp)."""
    u = user or getpass.getuser()
    return "hadj-notouch-" + hashlib.sha256(u.encode("utf-8")).hexdigest()[:16]


def cli_command(argv: list[str]) -> str | None:
    for arg in argv:
        if arg.startswith("--") and arg[2:] in COMMANDS:
            return arg[2:]
    return None


def send_command(command: str, name: str | None = None, timeout_ms: int = 2000) -> bool:
    """يرسل أمراً للنسخة العاملة. False إن لم تكن هناك نسخة عاملة."""
    from PySide6.QtNetwork import QLocalSocket
    if command not in COMMANDS:
        return False
    sock = QLocalSocket()
    sock.connectToServer(name or server_name())
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write((command + "\n").encode("ascii"))
    sock.flush()
    sock.waitForBytesWritten(timeout_ms)   # على Windows يرجع False إن اكتملت الكتابة: لا يُعتمد عليه
    reply = b""
    while True:
        reply += bytes(sock.readAll())   # الرد قد يكون وصل قبل الانتظار: waitForReadyRead تنتظر الجديد فقط
        if b"\n" in reply or not sock.waitForReadyRead(timeout_ms):
            break
    sock.disconnectFromServer()
    return reply.strip() == b"ok"


class CommandServer:
    """يستقبل الأوامر داخل حلقة Qt الرئيسية ويمررها إلى handler(command)."""

    def __init__(self, handler: Callable[[str], None], name: str | None = None):
        from PySide6.QtNetwork import QLocalServer
        self.handler = handler
        self.name = name or server_name()
        self.server = QLocalServer()
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        QLocalServer.removeServer(self.name)   # بقايا تشغيل سابق انهار (مقبس Unix يتيم)
        self.ok = self.server.listen(self.name)
        if not self.ok:
            log.warning("قناة الأوامر المحلية غير متاحة: %s", self.server.errorString())
        self.server.newConnection.connect(self._accept)
        self._clients: dict = {}   # المقبس ← المخزن المؤقت (مرجع قوي حتى انقطاع الاتصال)

    def _accept(self) -> None:
        while self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            self._clients[sock] = b""
            sock.readyRead.connect(lambda s=sock: self._read(s))
            sock.disconnected.connect(lambda s=sock: self._drop(s))
            if sock.bytesAvailable():   # وصل الأمر قبل ربط الإشارة: لن تُطلق readyRead مجدداً
                self._read(sock)

    def _drop(self, sock) -> None:
        self._clients.pop(sock, None)
        sock.deleteLater()

    def _read(self, sock) -> None:
        if sock not in self._clients:
            return
        buf = self._clients[sock] + bytes(sock.readAll())
        if b"\n" not in buf and len(buf) <= MAX_LEN:
            self._clients[sock] = buf   # الأمر لم يكتمل بعد (قد يصل على دفعات)
            return
        self._clients[sock] = b""
        raw = buf.split(b"\n", 1)[0][:MAX_LEN].decode("ascii", "replace").strip()
        if raw in COMMANDS:
            try:
                self.handler(raw)
                reply = b"ok\n"
            except Exception:  # noqa: BLE001
                log.exception("فشل تنفيذ الأمر المحلي %s", raw)
                reply = b"error\n"
        else:
            reply = b"unknown\n"
        sock.write(reply)
        sock.flush()
        # الكتابة في الأنبوب المسمّى غير متزامنة على Windows: ننتظر خروج الرد القصير (أجزاء من الثانية)
        sock.waitForBytesWritten(1000)

    def close(self) -> None:
        self.server.close()
