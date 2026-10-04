"""طبقة Linux على خادم X11 حقيقي (WSLg أو سطح مكتب Linux): نافذة اختبار تستقبل ما يرسله الخلفي.

يُتجاهل تلقائياً على Windows أو دون DISPLAY أو دون python-xlib.
للتشغيل وحده (دون conftest الرئيسي الذي يحتاج مكتبات التطبيق كلها):
    PYTHONPATH=src pytest --confcutdir tests/linux tests/linux
"""
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

Xlib = pytest.importorskip("Xlib") if sys.platform.startswith("linux") else None
pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"),
                                reason="خادم X11 مطلوب (Linux مع DISPLAY)")


@pytest.fixture(scope="module")
def backend():
    from os_layer.linux.backend import LinuxX11Backend
    b = LinuxX11Backend()
    yield b
    b.release_all()
    b.close()


@pytest.fixture
def win():
    """نافذة X11 مرئية تملك التركيز وتسجّل أحداث المفاتيح والفأرة."""
    from Xlib import X, display
    d = display.Display()
    s = d.screen()
    w = s.root.create_window(200, 150, 400, 300, 0, s.root_depth,
                             background_pixel=s.white_pixel,
                             event_mask=X.KeyPressMask | X.ButtonPressMask | X.StructureNotifyMask
                             | X.ExposureMask | X.FocusChangeMask)
    w.set_wm_name("hadj-x11-test")
    w.map()
    d.sync()
    _wait(d, lambda ev: ev.type == X.MapNotify, 3)
    w.raise_window()
    # مدير النوافذ قد يأخذ التركيز لحظة الظهور: نعيد الطلب حتى يثبت
    focused = False
    for _ in range(20):
        w.set_input_focus(X.RevertToPointerRoot, X.CurrentTime)
        d.sync()
        time.sleep(0.05)
        if d.get_input_focus().focus == w:
            focused = True
            break
    if not focused:
        _release_focus(d)
        w.destroy()
        d.close()
        pytest.skip("مدير النوافذ في هذه البيئة يرفض منح التركيز لنافذة الاختبار")
    time.sleep(0.2)
    while d.pending_events():
        d.next_event()
    yield d, w
    # التركيز يعود لسطح المكتب: تركيز "لا شيء" يجعل X يرمي كل ضغطات المفاتيح، حتى الاختصار العام
    _release_focus(d)
    w.destroy()
    d.close()


def _release_focus(d):
    from Xlib import X
    d.set_input_focus(X.PointerRoot, X.RevertToPointerRoot, X.CurrentTime)
    d.sync()


def _wait(d, pred, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        while d.pending_events():
            ev = d.next_event()
            if pred(ev):
                return ev
        time.sleep(0.02)
    return None


def _events(d, kind, timeout=1.5):
    from Xlib import X
    out, end = [], time.monotonic() + timeout
    while time.monotonic() < end:
        while d.pending_events():
            ev = d.next_event()
            if ev.type == kind:
                out.append(ev)
        time.sleep(0.02)
    return out


def _chars(d, events):
    """أحداث KeyPress ← النص (بحسب حالة Shift)، باستخدام تخطيط لوحة المفاتيح الحالي."""
    from Xlib import X
    s = ""
    for ev in events:
        sym = d.keycode_to_keysym(ev.detail, 1 if ev.state & X.ShiftMask else 0)
        if sym in (0, ) or 0xFFE1 <= sym <= 0xFFEE:   # مفاتيح التعديل نفسها
            continue
        s += chr(sym - 0x01000000) if sym >= 0x01000000 else chr(sym)
    return s


def test_type_ascii_with_shift(backend, win):
    from Xlib import X
    d, _w = win
    backend.type_text("Hadj 2026!")
    assert _chars(d, _events(d, X.KeyPress)) == "Hadj 2026!"


@pytest.mark.parametrize("ch", ["ه", "é", "€"])
def test_type_unicode_through_spare_key(backend, win, monkeypatch, ch):
    """محرف خارج التخطيط: يُربط بمفتاح احتياطي. نُبقي الربط حتى تقرأ النافذة الحدث."""
    from Xlib import X
    from Xlib.protocol import event

    from os_layer.linux.backend import LinuxX11Backend
    from os_layer.linux.keys import char_keysym
    d, _w = win
    if d.keysym_to_keycode(char_keysym(ch)):
        pytest.skip("المحرف موجود أصلاً في التخطيط")
    if backend.xwayland:
        # تحت Wayland: رفض صريح دون كتابة أي شيء (لا نص مبتور)
        with pytest.raises(OSError, match="Wayland"):
            backend.type_text("ok " + ch)
        assert _events(d, X.KeyPress, timeout=0.8) == []
        return
    monkeypatch.setattr(backend, "_restore_spare", lambda: None)
    try:
        backend.type_text(ch)
        evs = _events(d, X.KeyPress)
        # نافذة الاختبار تقرأ التخطيط الجديد للمفتاح الاحتياطي قبل ترجمة الحدث
        d.refresh_keyboard_mapping(event.MappingNotify(request=X.MappingKeyboard,
                                                       first_keycode=backend._spare_keycode, count=1))
        assert _chars(d, evs) == ch
    finally:
        LinuxX11Backend._restore_spare(backend)   # التخطيط يعود كما كان دائماً


def test_mouse_click_and_scroll_reach_the_window(backend, win):
    from Xlib import X
    d, w = win
    g = w.get_geometry()
    t = w.translate_coords(d.screen().root, 0, 0)
    cx, cy = -t.x + g.width // 2, -t.y + g.height // 2
    backend.mouse_move(cx, cy)
    assert backend.mouse_position() == (cx, cy)
    backend.mouse_button("left", "click")
    backend.scroll(-2)
    backend.scroll(1, ctrl=True)
    presses = [ev.detail for ev in _events(d, X.ButtonPress)]
    assert presses == [1, 5, 5, 4]


def test_release_all_after_drag(backend, win):
    d, w = win
    backend.mouse_button("left", "down")
    assert backend.root.query_pointer().mask & Xlib.X.Button1Mask
    backend.release_all()
    assert not backend.root.query_pointer().mask & Xlib.X.Button1Mask


def test_emergency_hotkey_grab(backend):
    hits = []
    assert backend.register_hotkey("ctrl+alt+shift+p", lambda: hits.append(1))
    time.sleep(0.3)
    backend.hotkey("ctrl", "alt", "shift", "p")
    end = time.monotonic() + 3
    while not hits and time.monotonic() < end:
        time.sleep(0.05)
    assert hits == [1]


def test_monitors_and_capabilities(backend):
    mons = backend.list_monitors()
    assert mons and all(m.rect[2] > 0 and m.rect[3] > 0 for m in mons)
    caps = backend.capabilities()
    assert {"snap_window", "register_hotkey", "list_monitors"} <= caps
    assert "new_virtual_desktop" not in caps and "set_display_mode" not in caps
