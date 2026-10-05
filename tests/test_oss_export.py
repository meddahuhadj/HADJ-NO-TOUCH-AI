"""تصدير طبقة النظام كمكتبة مفتوحة المصدر: مستقلة عن التطبيق، وتدقيق أمني يرفض ما لا يجوز."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT

spec = importlib.util.spec_from_file_location("export_oss", ROOT / "scripts" / "export_oss.py")
export_oss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export_oss)


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    return export_oss.export(tmp_path_factory.mktemp("oss") / "hadj-input", "9.9.9")


def test_current_code_passes_the_audit(exported):
    files = {p.relative_to(exported).as_posix() for p in exported.rglob("*") if p.is_file()}
    assert {"LICENSE", "SECURITY.md", "docs/THREAT_MODEL.md", "src/hadj_input/windows/input.py",
            "tests/test_public_api.py"} <= files
    assert not any("apps_index" in f for f in files)              # منطق التطبيق لا يُفتح
    assert 'version = "9.9.9"' in (exported / "pyproject.toml").read_text(encoding="utf-8")
    text = "".join(p.read_text(encoding="utf-8") for p in (exported / "src").rglob("*.py"))
    assert "os_layer" not in text


def test_exported_package_runs_alone(exported):
    """عملية معزولة (-I): المكتبة تعمل دون أي وحدة من التطبيق."""
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import hadj_input; "
            "b = hadj_input.create_backend(); b.play_sound('ok'); "
            "bad = [m for m in sys.modules if m.split('.')[0] in "
            "('core','commands','config','ui','vision','audio','os_layer')]; print(bad)")
    out = subprocess.run([sys.executable, "-I", "-c", code, str(exported / "src")],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "[]"


def test_exported_tests_pass(exported):
    out = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                          "-c", "pyproject.toml", "--rootdir", ".", "tests"],
                         cwd=exported, capture_output=True, text=True, timeout=120,
                         env={**__import__("os").environ, "PYTHONPATH": str(exported / "src")})
    assert out.returncode == 0, out.stdout + out.stderr


@pytest.mark.parametrize("snippet,why", [
    ("import socket\n", "network module"),
    ("from urllib.request import urlopen\n", "network module"),
    ("from core import paths\n", "app import"),
    ("user32.SetWindowsHookExW(13, cb, None, 0)\n", "forbidden call SetWindowsHookEx"),
    ("state = user32.GetKeyboardState(buf)\n", "forbidden call GetKeyboardState"),
    ("if user32.GetAsyncKeyState(0x41): pass\n", "GetAsyncKeyState outside"),
])
def test_audit_refuses(snippet, why):
    problems = export_oss.audit(Path("x.py"), "import ctypes\n" + snippet)
    assert any(why in p for p in problems), problems


def test_mouse_button_release_is_the_only_allowed_key_state_read():
    import re
    text = (ROOT / "src" / "os_layer" / "windows" / "backend.py").read_text(encoding="utf-8")
    text = re.sub(r"\bos_layer\b", export_oss.PACKAGE, text)   # كما يفعل التصدير
    assert export_oss.audit(Path("backend.py"), text) == []


def test_app_backend_still_has_its_sounds(tmp_path, monkeypatch):
    from core import paths
    from os_layer.factory import create_backend
    monkeypatch.setattr(paths, "user_dir", lambda: tmp_path)
    b = create_backend()
    assert b._sound_provider is not None
    sounds = b._sound_provider(70)
    assert sounds["ok"].exists() and sounds["ok"].parent == tmp_path / "sounds" / "v70"
