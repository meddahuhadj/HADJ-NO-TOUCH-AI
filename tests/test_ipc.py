"""اختبار الاتصال بين العمليات عبر الأنبوب المسمّى، بعملية فرعية حقيقية."""
import multiprocessing as mp
import queue
import time

from core.events import ControlMessage, StatusEvent
from core.ipc import Hub, Link


def child(address, authkey, name):
    link = Link(address, authkey, name)
    link.send(StatusEvent(name, "ready"))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            msgs = link.poll_control()
        except EOFError:
            return
        for m in msgs:
            if m.kind == "echo":
                link.send(StatusEvent(name, "echo", m.payload["text"]))
            elif m.kind == "shutdown":
                link.send(StatusEvent(name, "bye"))
                return
        time.sleep(0.01)


def get(events, n, timeout=15):
    out = []
    end = time.monotonic() + timeout
    while len(out) < n and time.monotonic() < end:
        try:
            out.append(events.get(timeout=0.2))
        except queue.Empty:
            pass
    return out


def test_hub_roundtrip_with_real_process():
    events: queue.Queue = queue.Queue()
    hub = Hub(events)
    hub.set_initial("w", [ControlMessage("echo", {"text": "initial"})])
    ctx = mp.get_context("spawn")
    p = ctx.Process(target=child, args=(hub.address, hub.authkey, "w"), daemon=True)
    p.start()
    try:
        got = get(events, 2)
        assert [(e.state, e.detail) for e in got] == [("ready", ""), ("echo", "initial")]
        assert hub.connected("w")
        assert hub.send("w", ControlMessage("echo", {"text": "مرحبا"}))
        assert get(events, 1)[0].detail == "مرحبا"
        hub.send("w", ControlMessage("shutdown"))
        assert get(events, 1)[0].state == "bye"
        p.join(10)
        assert p.exitcode == 0
    finally:
        hub.close()
        if p.is_alive():
            p.terminate()


def test_child_exits_when_parent_hub_closes():
    events: queue.Queue = queue.Queue()
    hub = Hub(events)
    ctx = mp.get_context("spawn")
    p = ctx.Process(target=child, args=(hub.address, hub.authkey, "w"), daemon=True)
    p.start()
    assert get(events, 1)[0].state == "ready"
    hub.close()
    p.join(8)
    assert p.exitcode == 0      # EOFError ← خروج نظيف دون انتظار المهلة


def test_wrong_key_is_rejected():
    import pytest
    from multiprocessing import AuthenticationError
    hub = Hub(queue.Queue())
    try:
        with pytest.raises((AuthenticationError, EOFError, OSError)):
            Link(hub.address, b"wrong-key" * 4, "intruder")
        assert not hub.connected("intruder")
        # الاستقبال يستمر بعد المحاولة المرفوضة
        ok = Link(hub.address, hub.authkey, "legit")
        end = time.monotonic() + 5
        while not hub.connected("legit") and time.monotonic() < end:
            time.sleep(0.05)
        assert hub.connected("legit")
        ok.close()
    finally:
        hub.close()


def test_send_to_missing_worker_is_false():
    hub = Hub(queue.Queue())
    try:
        assert hub.send("nobody", ControlMessage("x")) is False
    finally:
        hub.close()
