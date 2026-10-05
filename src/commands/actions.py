"""سجل الإجراءات: كل إجراء دالة (ctx, args) تنفّذ شيئاً عبر طبقة النظام.

الأوامر الصوتية والإيماءات والماكرو كلها تنتهي هنا، فإضافة إجراء جديد
تجعله متاحاً تلقائياً في ملفات الأوامر المخصصة.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from config.schema import AppConfig
from os_layer.apps_index import AppIndex
from os_layer.base import OSBackend

log = logging.getLogger(__name__)


class AppControl(Protocol):
    """تحكم في التطبيق نفسه (ينفّذه المتحكم الرئيسي)."""
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def sleep(self) -> None: ...
    def toggle_language(self) -> None: ...
    def set_language(self, lang: str) -> bool: ...
    def set_continuous(self, value: bool) -> None: ...
    def refresh_apps(self) -> None: ...
    def start_dictation(self) -> None: ...
    def stop_dictation(self) -> None: ...
    def show_grid(self) -> None: ...
    def start_calibration(self) -> None: ...
    def open_settings(self) -> None: ...
    def open_help(self) -> None: ...
    def set_profile(self, profile: str) -> bool: ...
    def wake_camera(self) -> bool: ...


@dataclass
class ActionContext:
    os: OSBackend
    apps: AppIndex
    app: AppControl
    config: AppConfig


class ActionError(Exception):
    """خطأ يُعرض للمستخدم (مفتاح نص الترجمة + قيم)."""
    def __init__(self, key: str, **values: Any):
        super().__init__(key)
        self.key = key
        self.values = values


ActionFn = Callable[[ActionContext, dict], None]
REGISTRY: dict[str, ActionFn] = {}


def action(name: str):
    def deco(fn: ActionFn) -> ActionFn:
        REGISTRY[name] = fn
        return fn
    return deco


def fill_slots(value: Any, slots: dict[str, str]) -> Any:
    if isinstance(value, str):
        for k, v in slots.items():
            value = value.replace("{" + k + "}", v)
        return value
    if isinstance(value, list):
        return [fill_slots(v, slots) for v in value]
    if isinstance(value, dict):
        return {k: fill_slots(v, slots) for k, v in value.items()}
    return value


def run_steps(ctx: ActionContext, steps: list[dict], slots: dict[str, str] | None = None) -> None:
    for step in steps:
        step = fill_slots(dict(step), slots or {})
        name = step.pop("action", None)
        fn = REGISTRY.get(name)
        if fn is None:
            raise ActionError("unknown_action", name=name)
        fn(ctx, step)


# ============================ لوحة المفاتيح ============================
@action("key")
def _key(ctx, a):
    ctx.os.key(a["key"], int(a.get("times", 1)))


@action("hotkey")
def _hotkey(ctx, a):
    keys = a["keys"]
    if isinstance(keys, str):
        keys = keys.split("+")
    ctx.os.hotkey(*keys)


@action("type_text")
def _type(ctx, a):
    ctx.os.type_text(a["text"])


@action("wait")
def _wait(ctx, a):
    time.sleep(min(float(a.get("ms", 300)), 10_000) / 1000)


# ============================ الفأرة ============================
@action("click")
def _click(ctx, a):
    ctx.os.mouse_button(a.get("button", "left"), "click", int(a.get("count", 1)))


@action("double_click")
def _dclick(ctx, a):
    ctx.os.mouse_button("left", "click", 2)


@action("right_click")
def _rclick(ctx, a):
    ctx.os.mouse_button("right", "click", 1)


@action("mouse_down")
def _mdown(ctx, a):
    ctx.os.mouse_button(a.get("button", "left"), "down")


@action("mouse_up")
def _mup(ctx, a):
    ctx.os.mouse_button(a.get("button", "left"), "up")


@action("move_mouse")
def _move(ctx, a):
    ctx.os.mouse_move(int(a["x"]), int(a["y"]))


@action("scroll")
def _scroll(ctx, a):
    n = int(a.get("amount", ctx.config.actions.scroll_amount))
    direction = a.get("direction", "down")
    horizontal = direction in ("left", "right")
    ctx.os.scroll(-n if direction in ("down", "left") else n, horizontal)


# ============================ النوافذ ============================
@action("close_window")
def _close(ctx, a):
    if not ctx.os.close_window():
        raise ActionError("no_window")


@action("minimize_window")
def _min(ctx, a):
    if not ctx.os.minimize_window():
        raise ActionError("no_window")


@action("maximize_window")
def _max(ctx, a):
    if not ctx.os.maximize_window():
        raise ActionError("no_window")


@action("switch_window")
def _switch(ctx, a):
    ctx.os.switch_window()


@action("show_desktop")
def _desktop(ctx, a):
    ctx.os.show_desktop()


@action("switch_window_prev")
def _switch_prev(ctx, a):
    ctx.os.hotkey("alt", "shift", "tab")


@action("zoom_in")
def _zoom_in(ctx, a):
    ctx.os.scroll(int(a.get("steps", 1)), ctrl=True)


@action("zoom_out")
def _zoom_out(ctx, a):
    ctx.os.scroll(-int(a.get("steps", 1)), ctrl=True)


# ============================ النظام ============================
@action("volume_up")
def _vup(ctx, a):
    ctx.os.volume("up", int(a.get("steps", ctx.config.actions.volume_step)))


@action("volume_down")
def _vdown(ctx, a):
    ctx.os.volume("down", int(a.get("steps", ctx.config.actions.volume_step)))


@action("mute")
def _mute(ctx, a):
    ctx.os.volume("mute")


@action("lock_screen")
def _lock(ctx, a):
    ctx.os.lock_screen()


@action("screenshot")
def _shot(ctx, a):
    ctx.os.screenshot()


@action("shutdown")
def _shutdown(ctx, a):
    ctx.os.power("shutdown")


@action("restart")
def _restart(ctx, a):
    ctx.os.power("restart")


@action("open_app")
def _open(ctx, a):
    entry = ctx.apps.find(a["name"])
    if entry is None:
        raise ActionError("app_not_found", name=a["name"])
    ctx.os.launch(entry)


@action("run")
def _run(ctx, a):
    from os_layer.base import AppEntry
    ctx.os.launch(AppEntry(name=a["target"], target=a["target"], kind="command"))


@action("search")
def _search(ctx, a):
    ctx.os.open_search()
    time.sleep(0.6)
    ctx.os.type_text(a["text"])


# ============================ التحكم التام بالنظام والوسائط ============================
# مفاتيح الوسائط العامة: تتحكم بالمشغّل النشط (Spotify، VLC، YouTube في المتصفح…) حتى في الخلفية،
# ولا تُدخل أي حرف في النافذة الأمامية (المسافة أو Ctrl+سهم كانت تكتب في المستند المفتوح).
@action("media_play_pause")
def _media_play(ctx, a):
    ctx.os.key("media_play_pause")


@action("media_next")
def _media_next(ctx, a):
    ctx.os.key("media_next")


@action("media_prev")
def _media_prev(ctx, a):
    ctx.os.key("media_prev")


@action("task_view")
def _task_view(ctx, a):
    ctx.os.hotkey("win", "tab")


@action("show_clipboard_history")
def _clip_hist(ctx, a):
    ctx.os.hotkey("win", "v")


@action("show_emoji_picker")
def _emoji(ctx, a):
    ctx.os.hotkey("win", ".")


@action("open_explorer")
def _explorer(ctx, a):
    ctx.os.hotkey("win", "e")


@action("open_task_manager")
def _task_mgr(ctx, a):
    ctx.os.hotkey("ctrl", "shift", "esc")


# ============================ النوافذ: التحكّم الدقيق ============================
@action("focus_window")
def _focus_window(ctx, a):
    """ينقل التركيز إلى نافذة بالاسم: «انتقل إلى المتصفح»."""
    query = str(a.get("query") or "").strip()
    if not query:
        raise ActionError("window_not_found", name="")
    if not ctx.os.focus_window(query):
        raise ActionError("window_not_found", name=query)


@action("center_window")
def _center_window(ctx, a):
    if not ctx.os.center_window():
        raise ActionError("no_window")


@action("move_window")
def _move_window(ctx, a):
    step = int(a.get("step", 80))
    if not ctx.os.move_window(int(a.get("dx", 0)) * step, int(a.get("dy", 0)) * step):
        raise ActionError("no_window")


@action("resize_window")
def _resize_window(ctx, a):
    step = int(a.get("step", 80))
    if not ctx.os.resize_window(int(a.get("dw", 0)) * step, int(a.get("dh", 0)) * step):
        raise ActionError("no_window")


@action("snap")
def _snap(ctx, a):
    position = str(a.get("position", "left"))
    if not ctx.os.snap_window(position):
        raise ActionError("bad_position", name=position)


@action("always_on_top")
def _always_on_top(ctx, a):
    if not ctx.os.set_always_on_top(bool(a.get("enabled", True))):
        raise ActionError("no_window")


# ============================ الشاشات والشاشات الافتراضية ============================
@action("move_to_monitor")
def _move_to_monitor(ctx, a):
    index = int(a.get("index", 0))
    if not ctx.os.move_window_to_monitor(index):
        raise ActionError("no_monitor", index=index)


@action("display_mode")
def _display_mode(ctx, a):
    mode = str(a.get("mode", "extend"))
    if not ctx.os.set_display_mode(mode):
        raise ActionError("bad_display_mode", name=mode)


@action("virtual_desktop")
def _virtual_desktop(ctx, a):
    """op: next | prev | new | close"""
    op = str(a.get("op", "next"))
    os_ = ctx.os
    ok = {"next": lambda: os_.switch_virtual_desktop("right"),
          "prev": lambda: os_.switch_virtual_desktop("left"),
          "new": os_.new_virtual_desktop,
          "close": os_.close_virtual_desktop}.get(op, lambda: False)()
    if not ok:
        raise ActionError("bad_virtual_desktop", name=op)


# ============================ العرض والصوت ============================
@action("brightness_up")
def _brightness_up(ctx, a):
    if not ctx.os.brightness("up", int(a.get("steps", 10))):
        raise ActionError("no_brightness")


@action("brightness_down")
def _brightness_down(ctx, a):
    if not ctx.os.brightness("down", int(a.get("steps", 10))):
        raise ActionError("no_brightness")


@action("set_brightness")
def _set_brightness(ctx, a):
    percent = max(0, min(100, int(a.get("percent", 50))))
    if not ctx.os.set_brightness(percent):
        raise ActionError("no_brightness")


@action("monitor_off")
def _monitor_off(ctx, a):
    if not ctx.os.monitor_power(False):
        raise ActionError("monitor_off_failed")


@action("monitor_on")
def _monitor_on(ctx, a):
    ctx.os.monitor_power(True)


@action("dark_mode")
def _dark_mode(ctx, a):
    if not ctx.os.set_dark_mode(bool(a.get("enabled", True))):
        raise ActionError("dark_mode_failed")


@action("toggle_mic_mute")
def _toggle_mic_mute(ctx, a):
    if not ctx.os.toggle_microphone_mute():
        raise ActionError("mic_mute_failed")


# ============================ التطبيق نفسه ============================
@action("app.pause")
def _pause(ctx, a):
    ctx.app.pause()


@action("app.resume")
def _resume(ctx, a):
    ctx.app.resume()


@action("app.sleep")
def _sleep(ctx, a):
    ctx.app.sleep()


@action("app.toggle_language")
def _lang(ctx, a):
    ctx.app.toggle_language()


@action("app.set_language")
def _set_lang(ctx, a):
    if ctx.app.set_language(a["lang"]) is False:
        raise ActionError("lang_pack_missing", lang=a["lang"])


@action("app.set_continuous")
def _cont(ctx, a):
    ctx.app.set_continuous(bool(a.get("value", True)))


@action("app.refresh_apps")
def _refresh(ctx, a):
    ctx.app.refresh_apps()


@action("app.start_dictation")
def _dict_on(ctx, a):
    ctx.app.start_dictation()


@action("app.stop_dictation")
def _dict_off(ctx, a):
    ctx.app.stop_dictation()


@action("app.show_grid")
def _grid(ctx, a):
    ctx.app.show_grid()


@action("app.calibrate")
def _calibrate(ctx, a):
    ctx.app.start_calibration()


@action("app.open_settings")
def _settings(ctx, a):
    ctx.app.open_settings()


@action("app.help")
def _help(ctx, a):
    ctx.app.open_help()


@action("app.wake_camera")
def _wake_camera(ctx, a):
    ctx.app.wake_camera()


@action("app.set_profile")
def _set_profile(ctx, a):
    if not ctx.app.set_profile(a["profile"]):
        raise ActionError("profile_unknown", name=a["profile"])


# ============================ التحكم الكامل بالمتصفح ============================
@action("browser_new_tab")
def _b_new_tab(ctx, a):
    ctx.os.hotkey("ctrl", "t")


@action("browser_close_tab")
def _b_close_tab(ctx, a):
    ctx.os.hotkey("ctrl", "w")


@action("browser_next_tab")
def _b_next_tab(ctx, a):
    ctx.os.hotkey("ctrl", "tab")


@action("browser_prev_tab")
def _b_prev_tab(ctx, a):
    ctx.os.hotkey("ctrl", "shift", "tab")


@action("browser_reopen_tab")
def _b_reopen_tab(ctx, a):
    ctx.os.hotkey("ctrl", "shift", "t")


@action("browser_back")
def _b_back(ctx, a):
    ctx.os.hotkey("alt", "left")


@action("browser_forward")
def _b_forward(ctx, a):
    ctx.os.hotkey("alt", "right")


@action("browser_refresh")
def _b_refresh(ctx, a):
    ctx.os.key("f5")


@action("browser_fullscreen")
def _b_fullscreen(ctx, a):
    ctx.os.key("f11")


@action("browser_search")
def _b_search(ctx, a):
    query = str(a.get("query") or a.get("text") or "").strip()
    ctx.os.hotkey("ctrl", "l")
    time.sleep(0.2)
    if query:
        ctx.os.type_text(query)
        time.sleep(0.05)
        ctx.os.key("enter")


# ============================ التحكم الكامل بالملفات والمجلدات ============================
import os
import glob
import subprocess

_USER_HOME = os.path.expanduser("~")
_FOLDER_MAP = {
    "downloads": os.path.join(_USER_HOME, "Downloads"),
    "téléchargements": os.path.join(_USER_HOME, "Downloads"),
    "telechargements": os.path.join(_USER_HOME, "Downloads"),
    "التحميلات": os.path.join(_USER_HOME, "Downloads"),
    "التنزيلات": os.path.join(_USER_HOME, "Downloads"),
    "documents": os.path.join(_USER_HOME, "Documents"),
    "المستندات": os.path.join(_USER_HOME, "Documents"),
    "ملفاتي": os.path.join(_USER_HOME, "Documents"),
    "desktop": os.path.join(_USER_HOME, "Desktop"),
    "bureau": os.path.join(_USER_HOME, "Desktop"),
    "سطح المكتب": os.path.join(_USER_HOME, "Desktop"),
    "pictures": os.path.join(_USER_HOME, "Pictures"),
    "images": os.path.join(_USER_HOME, "Pictures"),
    "الصور": os.path.join(_USER_HOME, "Pictures"),
    "music": os.path.join(_USER_HOME, "Music"),
    "musique": os.path.join(_USER_HOME, "Music"),
    "الموسيقى": os.path.join(_USER_HOME, "Music"),
    "videos": os.path.join(_USER_HOME, "Videos"),
    "vidéos": os.path.join(_USER_HOME, "Videos"),
    "الفيديو": os.path.join(_USER_HOME, "Videos"),
    "c_drive": "C:\\",
    "disque_c": "C:\\",
    "القرص c": "C:\\",
}


@action("open_folder")
def _open_folder(ctx, a):
    target = str(a.get("name") or a.get("folder") or "downloads").strip().lower()
    path = _FOLDER_MAP.get(target, target)
    if not os.path.exists(path):
        cand = os.path.join(_USER_HOME, target)
        if os.path.exists(cand):
            path = cand
        else:
            path = _FOLDER_MAP["downloads"]
    ctx.os.open_path(path)


@action("open_recent_download")
def _open_recent_download(ctx, a):
    dl_dir = _FOLDER_MAP["downloads"]
    if not os.path.exists(dl_dir):
        raise ActionError("action_failed")
    files = glob.glob(os.path.join(dl_dir, "*"))
    if not files:
        raise ActionError("action_failed")
    latest = max(files, key=os.path.getmtime)
    ctx.os.open_path(latest)


@action("empty_recycle_bin")
def _empty_recycle_bin(ctx, a):
    if not ctx.os.empty_recycle_bin():
        raise ActionError("action_failed")


# ============================ أدوات النظام الأساسية ============================
@action("open_windows_settings")
def _win_settings(ctx, a):
    ctx.os.hotkey("win", "i")


@action("open_run_dialog")
def _run_dlg(ctx, a):
    ctx.os.hotkey("win", "r")


@action("toggle_virtual_keyboard")
def _osk(ctx, a):
    try:
        subprocess.Popen(["osk.exe"])
    except Exception:
        ctx.os.hotkey("win", "ctrl", "o")


@action("open_action_center")
def _action_center(ctx, a):
    ctx.os.hotkey("win", "a")



# ============================ الإمكانات حسب النظام ============================
def action_needs(name: str) -> set[str]:
    """طرق OSBackend الاختيارية التي يستدعيها الإجراء (من أسماء الخصائص في الكود المترجم)."""
    from os_layer.base import OPTIONAL
    fn = REGISTRY.get(name)
    return set(fn.__code__.co_names) & set(OPTIONAL) if fn else set()


# اختصارات خاصة بـ Windows (Win+V، Win+R، osk.exe…): لا معنى لها على نظام آخر، والكشف الآلي
# لا يراها لأنها تمر عبر hotkey العام. عند نقلها إلى طرق في OSBackend تُحذف من هنا.
WINDOWS_ONLY = {"open_action_center", "open_run_dialog", "open_windows_settings", "show_clipboard_history",
                "show_emoji_picker", "task_view", "toggle_virtual_keyboard", "open_explorer",
                "open_task_manager"}


def unsupported_actions(backend, platform: str | None = None) -> set[str]:
    """الإجراءات التي لا يستطيع هذا النظام تنفيذها (فارغة على Windows)."""
    import sys
    caps = backend.capabilities()
    out = {name for name in REGISTRY if not action_needs(name) <= caps}
    if (platform or sys.platform) != "win32":
        out |= WINDOWS_ONLY & set(REGISTRY)
    return out
