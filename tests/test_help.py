"""صفحة المساعدة المحلية: متزامنة مع الأوامر، كاملة باللغات الثلاث، وبلا أي اتصال خارجي."""
import json
import re
import xml.etree.ElementTree as ET

import pytest
import yaml

from conftest import ROOT

HELP = ROOT / "src" / "help"


@pytest.fixture(scope="module")
def gen():
    from help import generate
    return generate


def load_data_js() -> dict:
    text = (HELP / "data.js").read_text(encoding="utf-8")
    return json.loads(text[text.index("=") + 1:].strip().rstrip(";"))


def test_generated_files_are_up_to_date(gen, tmp_path):
    """من يعدّل default_commands.yaml عليه تشغيل generate.py: وإلا تكذب المساعدة."""
    gen.write_all(tmp_path)
    for p in tmp_path.rglob("*"):
        if p.is_file():
            committed = HELP / p.relative_to(tmp_path)
            assert committed.exists(), f"{committed} مفقود: شغّل python src/help/generate.py"
            assert committed.read_bytes() == p.read_bytes(), \
                f"{committed.name} قديم: شغّل python src/help/generate.py"


def test_every_command_is_documented_once(gen):
    spec_ids = [c["id"] for c in yaml.safe_load(gen.COMMANDS_YAML.read_text(encoding="utf-8"))["commands"]]
    doc_ids = [c["id"] for s in load_data_js()["sections"] for c in s["commands"]]
    assert sorted(doc_ids) == sorted(spec_ids)


def test_every_section_title_is_translated(gen):
    for s in load_data_js()["sections"]:
        assert s["title"]["ar"] != s["title"]["fr"], f"قسم بلا ترجمة: {s['title']['ar']}"


def test_ui_strings_complete_in_three_languages(gen):
    for key, tr in gen.UI.items():
        assert set(tr) == {"ar", "fr", "en"}, key
        assert all(v.strip() for v in tr.values()), key
    for _gid, _fn, title, how in gen.GESTURES:
        assert set(title) == set(how) == {"ar", "fr", "en"}


def test_page_uses_every_ui_key(gen):
    html = (HELP / "index.html").read_text(encoding="utf-8")
    used = set(re.findall(r'data-t="([a-z_0-9]+)"', html))
    used |= set(re.findall(r'"(nav_[a-z]+)"', html)) | set(re.findall(r"(ind_[a-z]+):", html))
    used |= {f"tr_{k}_{qa}" for k in ("cam", "mic", "slow", "lang", "stuck") for qa in ("q", "a")}
    used |= {"cmd_search", "cmd_danger", "cmd_always", "cmd_none", "wake"}
    assert used <= set(gen.UI), used - set(gen.UI)
    assert set(gen.UI) <= used, f"نصوص غير مستخدمة: {set(gen.UI) - used}"


@pytest.mark.parametrize("name", [g[0] for g in __import__("help.generate", fromlist=["GESTURES"]).GESTURES])
def test_gesture_svgs_are_valid_and_animated(name):
    root = ET.fromstring((HELP / "gestures" / f"{name}.svg").read_text(encoding="utf-8"))
    ns = "{http://www.w3.org/2000/svg}"
    assert root.tag == ns + "svg" and root.get("aria-label")
    anims = root.findall(f".//{ns}animate") + root.findall(f".//{ns}animateTransform")
    assert anims, "رسم بلا حركة"
    for a in anims:
        if a.get("keyTimes"):
            kt = [float(v) for v in a.get("keyTimes").split(";")]
            assert kt[0] == 0 and abs(kt[-1] - 1) < 1e-6 and kt == sorted(kt)
            assert len(kt) == len(a.get("values").split(";"))


def test_help_is_fully_offline():
    """لا خط ولا سكربت ولا صورة من الإنترنت، وسياسة CSP تمنع أي اتصال."""
    for p in [HELP / "index.html", HELP / "data.js", *HELP.glob("gestures/*.svg")]:
        text = p.read_text(encoding="utf-8")
        urls = re.findall(r"https?://[^\s\"'<>\\]+", text)
        assert all(u == "http://www.w3.org/2000/svg" for u in urls), (p.name, urls)
    html = (HELP / "index.html").read_text(encoding="utf-8")
    assert "default-src 'none'" in html
    assert "fetch(" not in html and "XMLHttpRequest" not in html


def test_language_entry_points():
    for lang in ("ar", "fr", "en"):
        assert f"index.html#{lang}" in (HELP / f"{lang}.html").read_text(encoding="utf-8")


def test_help_dir_found():
    from core import paths
    assert (paths.help_dir() / "index.html").exists()


@pytest.mark.parametrize("lang,phrase", [("ar", "مساعدة"), ("fr", "aide"), ("en", "help")])
def test_voice_help_command(env, lang, phrase):
    env.config.speech.language = lang
    m = env.disp.parser.parse(phrase, lang)
    assert m is not None and m.spec.id == "help"
    from commands.actions import run_steps
    run_steps(env.disp.ctx, m.spec.steps, m.slots)
    assert "open_help" in env.app.calls
