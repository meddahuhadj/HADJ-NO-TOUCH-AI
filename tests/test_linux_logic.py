"""طبقة Linux: المنطق البحت (أسماء المفاتيح، ملفات .desktop) — يعمل على أي نظام."""
import pytest

from os_layer.linux import desktop, keys


# ---------------- المفاتيح ----------------
def test_every_windows_key_name_exists_on_linux():
    """الأوامر والماكرو تستعمل أسماء Windows: كلها يجب أن تُترجم على Linux."""
    from config.macros import KEYS, MODIFIERS
    for k in [*KEYS, *MODIFIERS]:
        assert keys.keysym_name(k)


@pytest.mark.parametrize("name,sym", [("enter", "Return"), ("win", "Super_L"), ("pagedown", "Next"),
                                      ("f12", "F12"), ("volume_up", "XF86AudioRaiseVolume"),
                                      ("A", "a"), ("7", "7")])
def test_keysym_names(name, sym):
    assert keys.keysym_name(name) == sym


def test_unknown_key_rejected():
    with pytest.raises(ValueError):
        keys.keysym_name("hyper")


@pytest.mark.parametrize("ch,sym", [("a", 0x61), ("A", 0x41), ("!", 0x21), ("é", 0xE9), ("ü", 0xFC),
                                    ("ه", 0x01000647), ("€", 0x010020AC), ("😀", 0x0101F600),
                                    ("\n", 0xFF0D), ("\t", 0xFF09), (" ", 0x20)])
def test_char_keysym(ch, sym):
    assert keys.char_keysym(ch) == sym


# ---------------- ملفات .desktop ----------------
CALC = """[Desktop Entry]
Type=Application
Name=Calculator
Name[fr]=Calculatrice
Name[ar]=الآلة الحاسبة
Exec=gnome-calculator %U
Icon=calc

[Desktop Action new]
Name=Ignored action
Exec=should-not-be-used
"""


def test_localized_name_and_exec():
    e = desktop.parse_desktop(CALC, ("fr",))
    assert e["_name"] == "Calculatrice" and e["Exec"] == "gnome-calculator %U"
    assert desktop.parse_desktop(CALC, ("ar", "fr"))["_name"] == "الآلة الحاسبة"
    assert desktop.parse_desktop(CALC)["_name"] == "Calculator"


@pytest.mark.parametrize("extra", ["NoDisplay=true", "Hidden=true", "Type=Link"])
def test_hidden_entries(extra):
    text = CALC.replace("Icon=calc", extra) if extra != "Type=Link" else CALC.replace("Type=Application", extra)
    assert desktop.parse_desktop(text) is None


@pytest.mark.parametrize("line,args", [
    ("gnome-calculator %U", ["gnome-calculator"]),
    ('"/opt/My App/run" --flag %f', ["/opt/My App/run", "--flag"]),
    ("echo 100%%", ["echo", "100%"]),
    ('broken "quote', []),
])
def test_clean_exec(line, args):
    assert desktop.clean_exec(line) == args


def test_user_entries_override_and_hide_system(tmp_path):
    user, system = tmp_path / "user", tmp_path / "system"
    user.mkdir()
    system.mkdir()
    (system / "calc.desktop").write_text(CALC, encoding="utf-8")
    (system / "editor.desktop").write_text(CALC.replace("Calculator", "Editor").replace("gnome-calculator", "gedit"),
                                           encoding="utf-8")
    (user / "editor.desktop").write_text(CALC.replace("Icon=calc", "Hidden=true"), encoding="utf-8")
    apps = desktop.list_desktop_apps([user, system], ("fr",))
    assert [(a.id, a.name, a.exec_args) for a in apps] == [("calc", "Calculatrice", ["gnome-calculator"])]


def test_application_dirs_follow_xdg():
    dirs = desktop.application_dirs({"HOME": "/home/u", "XDG_DATA_DIRS": "/a:/b"})
    assert [str(d).replace("\\", "/") for d in dirs[:3]] == \
        ["/home/u/.local/share/applications", "/a/applications", "/b/applications"]


def test_factory_explains_missing_display(monkeypatch):
    import sys

    from os_layer import factory
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    with pytest.raises(NotImplementedError, match="Wayland"):
        factory.create_backend()
