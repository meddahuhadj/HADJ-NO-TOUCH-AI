import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from commands.actions import ActionContext  # noqa: E402
from commands.dispatcher import Dispatcher  # noqa: E402
from commands.parser import CommandParser  # noqa: E402
from commands.wake import WakeGate  # noqa: E402
from config.loader import load_command_specs  # noqa: E402
from config.schema import AppConfig  # noqa: E402
from os_layer.apps_index import AppIndex  # noqa: E402
from os_layer.base import AppEntry, MonitorInfo, OSBackend, WindowInfo  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"


class FakeOS(OSBackend):
    """يسجل كل استدعاء بدل تنفيذه على النظام."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.pos = (0, 0)
        self.window = True

    def _rec(self, *call):
        self.calls.append(call)

    def key(self, key, times=1): self._rec("key", key, times)
    def hotkey(self, *keys): self._rec("hotkey", *keys)
    def type_text(self, text): self._rec("type_text", text)
    def mouse_position(self): return self.pos
    def mouse_move(self, x, y): self.pos = (x, y); self._rec("move", x, y)
    def mouse_button(self, button="left", action="click", count=1): self._rec("mouse", button, action, count)
    def scroll(self, notches, horizontal=False, ctrl=False):
        self._rec(*(("zoom", notches) if ctrl else ("scroll", notches, horizontal)))
    def screen_rect(self): return (0, 0, 1920, 1080)
    def release_all(self): self._rec("release_all")
    def close_window(self): self._rec("close_window"); return self.window
    def minimize_window(self): self._rec("minimize_window"); return self.window
    def maximize_window(self): self._rec("maximize_window"); return self.window
    def switch_window(self): self._rec("switch_window")
    def show_desktop(self): self._rec("show_desktop")
    def active_window_title(self): return "fake"
    def volume(self, change, steps=1): self._rec("volume", change, steps)
    def lock_screen(self): self._rec("lock_screen")
    def screenshot(self): self._rec("screenshot")
    def power(self, action): self._rec("power", action)
    def open_search(self): self._rec("open_search")
    def launch(self, entry): self._rec("launch", entry.target)
    def list_apps(self):
        return [AppEntry("Google Chrome", "Chrome", "appid"),
                AppEntry("Microsoft Word", "Word.exe", "appid"),
                AppEntry("Visual Studio Code", "Code", "appid"),
                AppEntry("VLC media player", "vlc", "appid")]

    # ---- النوافذ والشاشات والعرض ----
    def list_windows(self):
        return [WindowInfo(hwnd=1, title="Google Chrome", pid=10)]

    def focus_window(self, query):
        self._rec("focus_window", query)
        return self.window
    def center_window(self): self._rec("center_window"); return self.window
    def move_window(self, dx, dy): self._rec("move_window", dx, dy); return self.window
    def resize_window(self, dw, dh): self._rec("resize_window", dw, dh); return self.window
    def set_window_rect(self, x, y, w, h):
        self._rec("set_window_rect", x, y, w, h); return True
    def snap_window(self, position):
        self._rec("snap_window", position); return position != "sideways"
    def set_always_on_top(self, enabled):
        self._rec("always_on_top", enabled); return self.window

    def list_monitors(self):
        return [MonitorInfo(index=0, name="Fake", rect=(0, 0, 1920, 1080), primary=True)]
    def move_window_to_monitor(self, index):
        self._rec("move_to_monitor", index); return index == 0
    def set_display_mode(self, mode):
        self._rec("display_mode", mode); return mode != "sideways"
    def switch_virtual_desktop(self, direction):
        self._rec("vdesktop", direction); return direction in ("left", "right")
    def new_virtual_desktop(self): self._rec("vdesktop", "new"); return True
    def close_virtual_desktop(self): self._rec("vdesktop", "close"); return True

    def brightness(self, change, steps=10):
        self._rec("brightness", change, steps); return self.window
    def set_brightness(self, percent):
        self._rec("set_brightness", percent); return self.window
    def monitor_power(self, on): self._rec("monitor_power", on); return True
    def set_dark_mode(self, enabled): self._rec("dark_mode", enabled); return True
    def toggle_microphone_mute(self): self._rec("mic_mute"); return True


class FakeApp:
    """AppControl مبسط للاختبار."""

    def __init__(self):
        self.paused = threading.Event()
        self.calls = []
        self.gate = None

    def pause(self): self.paused.set(); self.calls.append("pause")
    def resume(self): self.paused.clear(); self.calls.append("resume")
    def sleep(self): self.calls.append("sleep"); self.gate and self.gate.disarm()
    def toggle_language(self): self.calls.append("toggle_language")
    def set_language(self, lang): self.calls.append(("set_language", lang))
    def set_continuous(self, value): self.calls.append(("continuous", value))
    def refresh_apps(self): self.calls.append("refresh_apps")

    def start_dictation(self):
        from commands.modes import DictationMode
        self.calls.append("start_dictation")
        self.disp.enter_mode(DictationMode(self.disp, "ar"))

    def stop_dictation(self):
        from commands.modes import DictationMode
        if isinstance(self.disp.mode, DictationMode):
            self.disp.exit_mode()

    def start_calibration(self):
        self.calls.append("start_calibration")

    def open_settings(self):
        self.calls.append("open_settings")

    def show_grid(self):
        from commands.modes import GridMode
        self.calls.append("show_grid")
        self.disp.enter_mode(GridMode(self.disp, 30))


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


@pytest.fixture
def specs():
    return load_command_specs(FIXTURES / "no_user_dir")


@pytest.fixture
def parser(specs):
    return CommandParser(specs, threshold=80)


@pytest.fixture
def env(parser):
    """بيئة موزّع كاملة بمكونات وهمية."""
    config = AppConfig()
    config.feedback.sounds = False
    config.app_aliases = {"المفكرة": "notepad.exe", "كروم": "Google Chrome", "notepad": "notepad.exe"}
    fake_os = FakeOS()
    app = FakeApp()
    clock = Clock()
    apps = AppIndex(fake_os.list_apps, config.app_aliases)
    apps.refresh()
    gate = WakeGate(["حاسوب"], continuous=False, timeout_s=5, followup_s=6, clock=clock)
    app.gate = gate
    ctx = ActionContext(os=fake_os, apps=apps, app=app, config=config)
    notes: list[tuple[str, dict]] = []
    disp = Dispatcher(ctx, parser, gate, lambda k, **d: notes.append((k, d)), app.paused, clock=clock)
    app.disp = disp
    mode_exits: list[tuple[str, bool]] = []
    disp.on_mode_exit = lambda name, abort: mode_exits.append((name, abort))

    class Env:
        pass
    e = Env()
    e.os, e.app, e.clock, e.gate, e.disp, e.notes, e.config = fake_os, app, clock, gate, disp, notes, config
    e.mode_exits = mode_exits
    return e
