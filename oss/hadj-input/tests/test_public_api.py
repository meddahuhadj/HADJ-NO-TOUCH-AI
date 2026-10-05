"""Public API, security rules and safe release. Runs on Windows; nothing is typed or clicked for real."""
import ast
import importlib
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1] / "src" / "hadj_input"
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows backend")

NETWORK = {"socket", "urllib", "http", "requests", "ftplib", "smtplib", "ssl", "asyncio"}
FORBIDDEN = ("SetWindowsHookEx", "GetKeyboardState", "GetRawInputData", "BlockInput", "keybd_event")


def sources():
    return {p: p.read_text(encoding="utf-8") for p in PKG.rglob("*.py")}


def test_public_api():
    import hadj_input
    backend = hadj_input.create_backend()
    assert isinstance(backend, hadj_input.OSBackend)
    for name in ("key", "hotkey", "type_text", "mouse_move", "mouse_button", "scroll", "release_all"):
        assert callable(getattr(backend, name))
    backend.play_sound("ok")          # silent without a sound provider


def test_no_network_and_no_keyboard_spying():
    for path, text in sources().items():
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods = [node.module]
            else:
                continue
            assert not {m.split(".")[0] for m in mods} & NETWORK, (path.name, mods)
        for call in FORBIDDEN:
            assert call not in text, (path.name, call)


def test_release_all_releases_buttons_and_modifiers(monkeypatch):
    backend_mod = importlib.import_module("hadj_input.windows.backend")
    sent = []
    monkeypatch.setattr(backend_mod.win_input, "mouse_button", lambda b, a: sent.append((b, a)))
    monkeypatch.setattr(backend_mod.win_input, "key_up", lambda keys: sent.append(("keys_up", tuple(keys))))
    monkeypatch.setattr(backend_mod.user32, "GetAsyncKeyState", lambda vk: 0x8000 if vk == 0x02 else 0)
    b = backend_mod.WindowsBackend()
    b._held_buttons.add("left")
    b.release_all()
    assert ("left", "up") in sent and ("right", "up") in sent        # right was pressed elsewhere
    assert ("keys_up", ("ctrl", "shift", "alt", "win")) in sent
    assert not b._held_buttons
