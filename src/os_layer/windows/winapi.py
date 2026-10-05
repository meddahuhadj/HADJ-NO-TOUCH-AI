"""واجهات ctypes لإدارة النوافذ والشاشات في Windows (بلا مكتبات وسيطة).

كل ما هنا منخفض المستوى: يستدعيه `backend.py` فقط. الاستدعاءات معرَّفة بأنواعها
(.argtypes/.restype) لأن ctypes الافتراضي يفسد المؤشرات على 64 بت.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from os_layer.geometry import snap_rect  # noqa: F401 - مشترك بين الأنظمة

user32 = ctypes.WinDLL("user32", use_last_error=True)

# ---- ثوابت ----
SW_HIDE, SW_SHOWNORMAL, SW_SHOWMINIMIZED, SW_MAXIMIZE, SW_RESTORE = 0, 1, 2, 3, 9
SW_SHOW, SW_MINIMIZE = 5, 6

GWL_EXSTYLE = -20
WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOREDIRECTIONBITMAP = 0x8, 0x80, 0x200000
WS_EX_APPWINDOW = 0x40000
WS_EX_NOACTIVATE = 0x08000000

HWND_TOP, HWND_BOTTOM, HWND_TOPMOST, HWND_NOTOPMOST = 0, 1, -1, -2
HWND_BROADCAST = 0xFFFF

SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER = 0x0001, 0x0002, 0x0004
SWP_NOACTIVATE, SWP_SHOWWINDOW, SWP_FRAMECHANGED = 0x0010, 0x0040, 0x0020

WM_SYSCOMMAND = 0x0112
WM_APPCOMMAND = 0x0319
SC_MONITORPOWER = 0xF170
MONITORPOWER_OFF, MONITORPOWER_ON = 2, -1

# أوامر WM_APPCOMMAND (تُمرَّر مُزاحة 16 بت داخل lParam)
APPCOMMAND_MICROPHONE_VOLUME_MUTE = 24 << 16
APPCOMMAND_MICROPHONE_VOLUME_UP = 25 << 16
APPCOMMAND_MICROPHONE_VOLUME_DOWN = 26 << 16

GA_ROOT = 2
MONITORINFOF_PRIMARY = 0x00000001
CCHDEVICENAME = 32

GA_PARENT = 1
GW_OWNER = 4


class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    def as_tuple(self) -> tuple[int, int, int, int]:
        """(left, top, width, height)"""
        return self.left, self.top, self.right - self.left, self.bottom - self.top


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * CCHDEVICENAME)]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("DeviceName", wintypes.WCHAR * 32),
                ("DeviceString", wintypes.WCHAR * 128), ("StateFlags", wintypes.DWORD),
                ("DeviceID", wintypes.WCHAR * 128), ("DeviceKey", wintypes.WCHAR * 128)]


WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                     ctypes.POINTER(RECT), wintypes.LPARAM)

# ---- تعريفات الاستدعاء ----
user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(RECT))
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(RECT))
user32.MoveWindow.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, wintypes.BOOL)
user32.MoveWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT)
user32.SetWindowPos.restype = wintypes.BOOL
user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.LONG)
user32.SetWindowLongW.restype = wintypes.LONG
user32.IsWindowVisible.argtypes = (wintypes.HWND,)
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = (wintypes.HWND,)
user32.IsIconic.restype = wintypes.BOOL
user32.IsWindow.argtypes = (wintypes.HWND,)
user32.IsWindow.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = (wintypes.HWND,)
user32.BringWindowToTop.restype = wintypes.BOOL
user32.SwitchToThisWindow.argtypes = (wintypes.HWND, wintypes.BOOL)
user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetAncestor.restype = wintypes.HWND
user32.GetWindow.argtypes = (wintypes.HWND, wintypes.UINT)
user32.GetWindow.restype = wintypes.HWND
user32.GetShellWindow.argtypes = ()
user32.GetShellWindow.restype = wintypes.HWND
user32.GetDesktopWindow.argtypes = ()
user32.GetDesktopWindow.restype = wintypes.HWND
user32.AllowSetForegroundWindow.argtypes = (wintypes.DWORD,)
user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.SendMessageW.restype = wintypes.LPARAM
user32.EnumWindows.argtypes = (WNDENUMPROC, wintypes.LPARAM)
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumDisplayMonitors.argtypes = (wintypes.HDC, ctypes.POINTER(RECT),
                                       MONITORENUMPROC, wintypes.LPARAM)
user32.EnumDisplayMonitors.restype = wintypes.BOOL
user32.GetMonitorInfoW.argtypes = (wintypes.HMONITOR, ctypes.POINTER(MONITORINFOEXW))
user32.GetMonitorInfoW.restype = wintypes.BOOL
user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
user32.MonitorFromWindow.restype = wintypes.HMONITOR
user32.MonitorFromPoint.argtypes = (wintypes.POINT, wintypes.DWORD)
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.EnumDisplayDevicesW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.POINTER(DISPLAY_DEVICEW), wintypes.DWORD)
user32.EnumDisplayDevicesW.restype = wintypes.BOOL
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)

# نداءات تستخدمها الخلفية فقط (argtypes معرَّفة فيها)
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetForegroundWindow.restype = wintypes.HWND

# ---- أدوات ----
MONITOR_DEFAULTTONEAREST = 2
MONITOR_DEFAULTTOPRIMARY = 1

# أصناف النوافذ التي لا نريد عرضها كنوافذ قابلة للتبديل
SYSTEM_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Shell_Surface",
    "Windows.UI.Core.CoreWindow", "ApplicationFrameWindow_Watchdog", "Button",
    "SysShadow", "ForegroundStaging", "MultitaskingViewFrame", "Xaml_WindowedPopupClass",
    "TaskManagerWindow", "ForegroundStagingClass", "EdgeUiInputTopWndClass",
    "Chrome_WidgetWin_0",  # نوافذ Bing/Metalimit (شريط بحث ويندوز)
}


def window_rect(hwnd) -> tuple[int, int, int, int] | None:
    r = RECT()
    if user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return r.as_tuple()
    return None


def window_title(hwnd) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def is_alt_tab_candidate(hwnd) -> bool:
    """هل تُعرض هذه النافذة في Alt+Tab؟ (نفس قاعدة Windows في شريط المهام)."""
    if not user32.IsWindowVisible(hwnd):
        return False
    if user32.GetAncestor(hwnd, GA_ROOT) != hwnd:
        return False   # نافذة تابعة (قائمة منسدلة، نافذة أداة)
    if class_name(hwnd) in SYSTEM_CLASSES:
        return False
    if not window_title(hwnd).strip():
        return False
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if ex & WS_EX_TOOLWINDOW:
        return False
    if user32.GetWindow(hwnd, GW_OWNER):
        return False
    return True


def enumerate_windows():
    """يعدّد مقابض النوافذ المرئية صالحة للتبديل."""
    found: list = []

    def cb(hwnd, _lparam):
        if is_alt_tab_candidate(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


def enumerate_monitors() -> list[tuple[object, MONITORINFOEXW]]:
    """قائمة (المقبض، معلومات الشاشة) بكل الشاشات المفعّلة."""
    out: list[tuple[object, MONITORINFOEXW]] = []

    def cb(handle, _hdc, _rect, _lparam):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(handle, ctypes.byref(mi)):
            out.append((handle, mi))
        return True

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    return out


def friendly_monitor_name(device: str) -> str:
    """اسم مقروء للشاشة من اسم محوّل الرسوميات (وإلا اسم الجهاز كما هو)."""
    dd = DISPLAY_DEVICEW()
    dd.cb = ctypes.sizeof(DISPLAY_DEVICEW)
    if user32.EnumDisplayDevicesW(device, 0, ctypes.byref(dd), 0):
        name = dd.DeviceString.strip()
        if name:
            return name
    return device.replace("\\", "").replace(".", "")


def monitor_handle_at(x: int, y: int):
    return user32.MonitorFromPoint(wintypes.POINT(int(x), int(y)), MONITOR_DEFAULTTOPRIMARY)


def monitor_index_of(hwnd) -> int:
    """ترتيب الشاشة في قائمة enumerate_monitors، أو 0 عند الفشل."""
    h = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    for i, (handle, _mi) in enumerate(enumerate_monitors()):
        if handle == h:
            return i
    return 0


def bring_to_front(hwnd) -> bool:
    """يجلب نافذة إلى الأمام. نربط خيوط الإدخال لأن العملية الحالية
    ليست مالك النافذة (قد يرفض Windows SetForegroundWindow دون إذن)."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    else:
        user32.ShowWindow(hwnd, SW_SHOW)
    try:
        user32.AllowSetForegroundWindow(-1)   # ASFW_ANY: نسمح بأي عملية
    except OSError:
        pass

    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
    attached = False
    if target_thread and target_thread != current_thread:
        attached = bool(user32.AttachThreadInput(current_thread, target_thread, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        user32.SwitchToThisWindow(hwnd, True)
        # حيلة موثوقة: إعادة الترتيب بلا حجم/موضع
        user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    finally:
        if attached:
            user32.AttachThreadInput(current_thread, target_thread, False)
    # نتحقّق فعلياً بدل افتراض النجاح: قد يرفض Windows SetForegroundWindow
    # عند التشغيل الصوتي (لا يوجد حدث إدخال يمنحنا إذن المقدمة).
    return user32.GetForegroundWindow() == hwnd


def set_always_on_top(hwnd, enabled: bool) -> bool:
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex = (ex | WS_EX_TOPMOST) if enabled else (ex & ~WS_EX_TOPMOST)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
    # إعادة تطبيق سريعة لتفادي كلفة تغيير النمط
    return bool(user32.SetWindowPos(hwnd, HWND_TOPMOST if enabled else HWND_NOTOPMOST,
                                    0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE))


def monitor_power(on: bool) -> bool:
    """يطفي/يشغّل كل الشاشات. أي حركة فأرة أو ضغطة مفتاح تُوقظها."""
    return bool(user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER,
                                    MONITORPOWER_ON if on else MONITORPOWER_OFF))


def send_appcommand(command: int) -> bool:
    """يأمر النظام بأمر تطبيق عام (مثل كتم الميكروفون).

    يُرسَل إلى كل النوافذ لأن النافذة النشطة قد لا تستقبله. القيمة تُمرَّر
    مُزاحة 16 بت كما يتطلّب WM_APPCOMMAND.

    ملاحظة: البثّ يعني أننا نُبلغ «أُرسل الأمر» لا «غيّر الصوت فعلاً»؛
    التبديل حتم والجهاز هو من ينفّذه، وقد لا يتوفّر فيه ميكروفون أصلاً.
    """
    try:
        user32.SendMessageW(HWND_BROADCAST, WM_APPCOMMAND, 0, command)
    except OSError:
        return False
    return True
