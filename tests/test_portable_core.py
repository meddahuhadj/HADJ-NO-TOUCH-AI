"""النواة القابلة للنقل (المرحلة 0): الإمكانات حسب النظام، الكاميرا، فتح المسارات، الأصوات، والتحكم المحلي."""
import os
import sys
import types
import wave

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from commands import actions  # noqa: E402
from conftest import FakeOS  # noqa: E402
from core import instance  # noqa: E402


class MinimalOS(FakeOS):
    """نظام افتراضي لا يدير النوافذ ولا السطوع (مثل Wayland): يرث التنفيذ "غير المدعوم" من الأساس."""


for _name in ("snap_window", "brightness", "set_brightness", "set_window_rect", "move_window",
              "resize_window", "center_window", "set_always_on_top", "move_window_to_monitor",
              "list_windows", "focus_window"):
    setattr(MinimalOS, _name, getattr(actions.OSBackend if hasattr(actions, "OSBackend") else
                                      __import__("os_layer.base", fromlist=["OSBackend"]).OSBackend, _name))


# ---------------- الإمكانات ----------------
def test_windows_supports_everything():
    from os_layer.factory import create_backend
    assert actions.unsupported_actions(create_backend()) == set()


def test_missing_capabilities_hide_actions():
    caps = MinimalOS().capabilities()
    assert "snap_window" not in caps and "brightness" not in caps and "set_dark_mode" in caps
    unsupported = actions.unsupported_actions(MinimalOS(), platform="win32")
    assert "snap" in unsupported
    assert {n for n in actions.REGISTRY if "brightness" in actions.action_needs(n)} <= unsupported
    assert any("brightness" in actions.action_needs(n) for n in actions.REGISTRY)
    assert "key" not in unsupported and "app.pause" not in unsupported


def test_windows_shortcuts_hidden_elsewhere():
    assert actions.WINDOWS_ONLY <= set(actions.REGISTRY)
    linux = actions.unsupported_actions(FakeOS(), platform="linux")
    assert actions.WINDOWS_ONLY <= linux
    assert not actions.WINDOWS_ONLY & actions.unsupported_actions(FakeOS(), platform="win32")


@pytest.fixture
def limited(tmp_path, monkeypatch):
    from config import loader
    from core import paths
    from core.controller import Controller
    monkeypatch.setattr(paths, "user_dir", lambda: tmp_path)
    loader.update_user_config({"vision": {"bindings": {"palm_hold_long": "snap_left"}}}, tmp_path)
    c = Controller(MinimalOS(), lambda *a, **k: None, loader.load_config(tmp_path))
    yield c
    c.shutdown()


def test_controller_drops_unsupported_commands(limited):
    c = limited
    assert c.parser.parse("aimante la fenêtre à gauche", "fr") is None or \
        all(s.get("action") != "snap" for s in c.parser.parse("aimante la fenêtre à gauche", "fr").spec.steps)
    ids = {s.id for s in c.parser.specs}
    assert "snap_left" not in ids and "copy" in ids and "emergency_stop" in ids
    b = c.effective_bindings()
    assert b["fist_hold"] == "app.pause"


# ---------------- الكاميرا ----------------
@pytest.mark.parametrize("platform,api", [("win32", "CAP_DSHOW"), ("darwin", "CAP_AVFOUNDATION"),
                                          ("linux", "CAP_V4L2")])
def test_camera_api(platform, api):
    import cv2

    from vision.worker import camera_api
    assert camera_api(platform) == api and hasattr(cv2, api)


# ---------------- فتح المسارات والسلة ----------------
def test_open_folder_goes_through_backend(env, tmp_path):
    actions.run_steps(env.disp.ctx, [{"action": "open_folder", "folder": str(tmp_path)}])
    # الإجراء يحوّل الاسم لحروف صغيرة (مسارات Windows لا تميّز الحالة)
    assert ("open_path", str(tmp_path).lower()) in [(k, v.lower()) for k, v in env.os.calls]


def test_empty_recycle_bin_reports_failure(env, monkeypatch):
    actions.run_steps(env.disp.ctx, [{"action": "empty_recycle_bin"}])
    assert ("empty_recycle_bin",) in env.os.calls
    monkeypatch.setattr(env.os, "empty_recycle_bin", lambda: False)
    with pytest.raises(actions.ActionError):
        actions.run_steps(env.disp.ctx, [{"action": "empty_recycle_bin"}])


def test_default_open_path_uses_platform_opener(monkeypatch):
    import subprocess

    from os_layer.base import OSBackend
    seen = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, **k: seen.append(args))
    monkeypatch.setattr(sys, "platform", "linux")
    OSBackend.open_path(None, "/tmp/x")
    monkeypatch.setattr(sys, "platform", "darwin")
    OSBackend.open_path(None, "/tmp/x")
    assert seen == [["xdg-open", "/tmp/x"], ["open", "/tmp/x"]]


# ---------------- الأصوات خارج Windows ----------------
def test_posix_sound(tmp_path, monkeypatch):
    from core.sounds import ensure_sounds
    from os_layer import posix_sound
    wav = ensure_sounds(tmp_path)["ok"]
    data, rate = posix_sound.read_wav(wav)
    assert rate == 22050 and len(data) > 1000
    played = []
    fake = types.SimpleNamespace(play=lambda d, r: played.append((len(d), r)), wait=lambda: None)
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    posix_sound.play_wav(wav).join(2)
    assert played == [(len(data), 22050)]
    broken = tmp_path / "broken.wav"
    with wave.open(str(broken), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(8000)
        w.writeframes(b"\0" * 10)
    posix_sound.play_wav(broken).join(2)            # صيغة غير مدعومة: لا استثناء
    assert len(played) == 1


# ---------------- التحكم بالنسخة العاملة ----------------
def test_cli_parsing_and_names():
    assert instance.cli_command(["main.py", "--debug", "--pause"]) == "pause"
    assert instance.cli_command(["main.py", "--toggle-pause"]) == "toggle-pause"
    assert instance.cli_command(["main.py", "--format-disk"]) is None
    n = instance.server_name("alice")
    assert n == instance.server_name("alice") != instance.server_name("bob") and "alice" not in n


def test_command_roundtrip():
    """كما في الاستخدام الحقيقي: الخادم في عملية التطبيق، والعميل عملية أخرى (HADJ-NoTouch --pause)."""
    import subprocess

    from PySide6.QtWidgets import QApplication

    from conftest import ROOT
    # QApplication لا QCoreApplication: اختبارات الواجهة اللاحقة في نفس العملية تحتاجها (وإلا تنهار Qt)
    app = QApplication.instance() or QApplication([])
    name = f"hadj-test-{os.getpid()}"
    got = []
    server = instance.CommandServer(got.append, name=name)
    assert server.ok
    code = ("import sys; sys.path.insert(0, sys.argv[2]); from PySide6.QtCore import QCoreApplication; "
            "QCoreApplication([]); from core import instance; "
            "print(instance.send_command('pause', name=sys.argv[1]), instance.send_command('rm -rf', name=sys.argv[1]))")
    p = subprocess.Popen([sys.executable, "-c", code, name, str(ROOT / "src")],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    while p.poll() is None:
        app.processEvents()
    server.close()
    assert p.stdout.read().split() == ["True", "False"], p.stderr.read()
    assert got == ["pause"]                       # الأمر المجهول لم يصل للمعالج
    assert instance.send_command("pause", name=name, timeout_ms=200) is False   # لا نسخة عاملة
