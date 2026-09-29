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
    def set_language(self, lang: str) -> None: ...
    def set_continuous(self, value: bool) -> None: ...
    def refresh_apps(self) -> None: ...
    def start_dictation(self) -> None: ...
    def stop_dictation(self) -> None: ...
    def show_grid(self) -> None: ...
    def start_calibration(self) -> None: ...
    def open_settings(self) -> None: ...


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
@action("media_play_pause")
def _media_play(ctx, a):
    ctx.os.hotkey("playpause")


@action("media_next")
def _media_next(ctx, a):
    ctx.os.hotkey("nexttrack")


@action("media_prev")
def _media_prev(ctx, a):
    ctx.os.hotkey("prevtrack")


@action("snap_left")
def _snap_left(ctx, a):
    ctx.os.hotkey("win", "left")


@action("snap_right")
def _snap_right(ctx, a):
    ctx.os.hotkey("win", "right")


@action("snap_up")
def _snap_up(ctx, a):
    ctx.os.hotkey("win", "up")


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
    ctx.app.set_language(a["lang"])


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
