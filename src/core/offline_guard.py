"""حارس عدم الاتصال: يمنع أي اتصال شبكي خارج الجهاز من داخل عملية التطبيق.

يُفعَّل في كل عملية (الرئيسية والفرعية) عند بدئها. الاتصالات المحلية (loopback)
مسموحة لأن بعض المكتبات تستخدمها داخلياً.
"""
from __future__ import annotations

import ipaddress
import socket

_installed = False


class OfflineViolation(ConnectionError):
    pass


def _is_local(address) -> bool:
    if isinstance(address, (str, bytes)):  # AF_UNIX
        return True
    host = address[0] if isinstance(address, tuple) and address else address
    if isinstance(host, bytes):
        host = host.decode(errors="ignore")
    if host in ("localhost", "", None):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False  # اسم نطاق خارجي


def install() -> None:
    global _installed
    if _installed:
        return
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex
    orig_getaddrinfo = socket.getaddrinfo

    def connect(self, address):
        if not _is_local(address):
            raise OfflineViolation(f"blocked network connection to {address!r}")
        return orig_connect(self, address)

    def connect_ex(self, address):
        if not _is_local(address):
            raise OfflineViolation(f"blocked network connection to {address!r}")
        return orig_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_local((host,)):
            raise OfflineViolation(f"blocked DNS lookup for {host!r}")
        return orig_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo
    _installed = True


def is_installed() -> bool:
    return _installed
