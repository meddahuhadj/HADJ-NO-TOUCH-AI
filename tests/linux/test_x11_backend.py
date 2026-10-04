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
        pytest.skip("تحت XWayland تمر هذه المحارف باللصق: انظر test_paste_under_xwayland")
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


def _paste_target(d, w, timeout=4.0):
    """تتصرف نافذة الاختبار كتطبيق: عند Ctrl+V تطلب CLIPBOARD وتقرأ النص الملصوق."""
    from Xlib import X, XK
    clip, utf8, prop = (d.intern_atom(n) for n in ("CLIPBOARD", "UTF8_STRING", "HADJ_TEST_PASTE"))
    v = d.keysym_to_keycode(XK.string_to_keysym("v"))
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not d.pending_events():
            time.sleep(0.01)
            continue
        ev = d.next_event()
        if ev.type == X.KeyPress and ev.detail == v and ev.state & X.ControlMask:
            w.convert_selection(clip, utf8, prop, X.CurrentTime)
            d.flush()
        elif ev.type == X.SelectionNotify and ev.property != X.NONE:
            data = w.get_full_property(prop, X.AnyPropertyType)
            return data.value.decode("utf-8") if data else None
    return None


def _clipboard_text(d, w):
    """ما في الحافظة الآن (كما يراه أي تطبيق)، أو None إن كانت فارغة."""
    from Xlib import X
    clip, utf8, prop = (d.intern_atom(n) for n in ("CLIPBOARD", "UTF8_STRING", "HADJ_TEST_READ"))
    if d.get_selection_owner(clip) == X.NONE:
        return None
    w.convert_selection(clip, utf8, prop, X.CurrentTime)
    d.flush()
    ev = _wait(d, lambda e: e.type == X.SelectionNotify, 2)
    if ev is None or ev.property == X.NONE:
        return None
    data = w.get_full_property(prop, X.AnyPropertyType)
    return data.value.decode("utf-8") if data else None


def _digest(text):
    """بصمة بدل النص: حافظة WSLg هي حافظة Windows الحقيقية للمستخدم، فلا تُطبع أبداً."""
    import hashlib
    return None if text is None else hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@pytest.mark.parametrize("previous", ["avant / قبل", None])
def test_paste_under_xwayland(backend, win, previous):
    """XWayland: النص (العربية، €…) يُلصق عبر الحافظة، ثم تعود الحافظة كما كانت."""
    import threading

    from os_layer.linux.clipboard import ClipboardOwner
    if not backend.xwayland:
        pytest.skip("خادم X.org: المحارف تُكتب مفتاحاً مفتاحاً (انظر test_type_unicode_through_spare_key)")
    d, w = win
    other = None
    if previous is not None:          # تطبيق آخر يملك نصاً في الحافظة قبل الإملاء
        other = ClipboardOwner()
        assert other.set_text(previous)
    before = _digest(_clipboard_text(d, w))   # None = حافظة فارغة (أو حافظة النظام كما هي)
    errors = []

    def typing():
        try:
            backend.type_text("مرحبا 50 € ok")
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    t = threading.Thread(target=typing)
    t.start()
    pasted = _paste_target(d, w)
    t.join(5)
    try:
        assert errors == [] and pasted == "مرحبا 50 € ok"
        time.sleep(0.2)
        assert _digest(_clipboard_text(d, w)) == before   # النص المُملى لا يبقى في الحافظة
    finally:
        if other is not None:
            other.close()
        backend._clip.clear()


def test_paste_fails_loudly_when_nothing_accepts(backend, win, monkeypatch):
    """لا تطبيق يلصق: خطأ صريح، والحافظة لا تحتفظ بالنص."""
    if not backend.xwayland:
        pytest.skip("مسار XWayland فقط")
    d, w = win
    monkeypatch.setattr(type(backend), "PASTE_WAIT_S", 0.5)
    before = _digest(_clipboard_text(d, w))
    with pytest.raises(OSError):
        backend.type_text("سلام")     # نافذة الاختبار (صاحبة التركيز) لا تطلب الحافظة هنا
    assert _digest(_clipboard_text(d, w)) == before


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
