"""Tests de la langue française : analyse, mot d'éveil, grille, dictée, interface, audio réel."""
import wave

import pytest

from commands.dictation import DictationSession, apply_spoken_punctuation, classify_command
from commands.grid import parse_grid_command, parse_number
from commands.parser import is_no, is_yes
from commands.text import normalize
from commands.wake import strip_wake
from conftest import FIXTURES, ROOT
from core.events import SpeechEvent


@pytest.mark.parametrize("raw,expected", [
    ("Ferme la fenêtre", "ferme la fenetre"),
    ("Déplace ici", "deplace ici"),
    ("Ouvre l'Explorateur", "ouvre l explorateur"),
    ("Point d’interrogation", "point d interrogation"),
    ("cœur", "coeur"),
])
def test_normalize_french(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("text,cmd", [
    ("ferme la fenêtre", "close_window"), ("ferme la fenetre", "close_window"),
    ("réduis", "minimize"), ("agrandis la fenêtre", "maximize"), ("copie", "copy"), ("colle", "paste"),
    ("annule", "undo"), ("enregistre", "save"), ("sélectionne tout", "select_all"),
    ("descends", "scroll_down"), ("défile vers le haut", "scroll_up"), ("clique", "click"),
    ("double clic", "double_click"), ("clic droit", "right_click"), ("monte le son", "volume_up"),
    ("coupe le son", "mute"), ("capture d'écran", "screenshot"), ("arrête", "emergency_stop"),
    ("commence la dictée", "start_dictation"), ("affiche la grille", "show_grid"),
    ("fenêtre précédente", "previous_window"), ("zoom avant", "zoom_in"), ("calibrage", "calibrate"),
])
def test_french_commands(parser, text, cmd):
    m = parser.parse(text, "fr")
    assert m is not None and m.id == cmd


def test_french_distinct_short_commands(parser):
    # "coupe" (couper) et "coupe le son" (muet), "monte" (défiler) et "monte le son"
    assert parser.parse("coupe", "fr").id == "cut"
    assert parser.parse("coupe le son", "fr").id == "mute"
    assert parser.parse("monte", "fr").id == "scroll_up"
    assert parser.parse("monte le son", "fr").id == "volume_up"


def test_french_fuzzy_and_fillers(parser):
    assert parser.parse("fermes la fenêtre", "fr").id == "close_window"
    assert parser.parse("s'il te plaît copie", "fr").id == "copy"
    assert parser.parse("copie s'il vous plaît", "fr").id == "copy"


def test_french_slots_keep_accents(parser):
    m = parser.parse("cherche la météo de demain", "fr")
    assert m.id == "search" and m.slots == {"text": "la météo de demain"}
    m = parser.parse("écris Bonjour à tous", "fr")
    assert m.id == "type_text" and m.slots == {"text": "Bonjour à tous"}


@pytest.mark.parametrize("text,found,rest", [
    ("ordinateur copie", True, "copie"),
    ("dis ordinateur ouvre la calculatrice", True, "ouvre la calculatrice"),
    ("l'ordinateur colle", True, "colle"),
    ("ordinateur", True, ""),
    ("copie", False, "copie"),
])
def test_french_wake_word(text, found, rest):
    assert strip_wake(text, ["ordinateur"]) == (found, rest)


@pytest.mark.parametrize("text,yes,no", [
    ("oui", True, False), ("d'accord", True, False), ("confirme", True, False),
    ("non", False, True), ("annule", False, True), ("copie", False, False),
])
def test_french_yes_no(text, yes, no):
    assert is_yes(text, "fr") is yes and is_no(text, "fr") is no


@pytest.mark.parametrize("text,n", [
    ("cinq", 5), ("trois", 3), ("huit", 8), ("neuf", 9), ("sept", 7), ("numéro deux", 2), ("7", 7),
    ("bonjour", None), ("vingt", None),
])
def test_french_grid_numbers(text, n):
    assert parse_number(text, "fr") == n


@pytest.mark.parametrize("text,cmd", [
    ("clique", "click"), ("double clic", "double_click"), ("clic droit", "right_click"),
    ("retour", "back"), ("annule", "close"), ("déplace", "move"),
])
def test_french_grid_commands(text, cmd):
    assert parse_grid_command(text, "fr") == cmd


@pytest.mark.parametrize("text,expected", [
    ("bonjour virgule comment ça va point d'interrogation", "bonjour, comment ça va?"),
    ("première ligne à la ligne deuxième ligne", "première ligne\ndeuxième ligne"),
    ("note deux points fin point", "note: fin."),
])
def test_french_spoken_punctuation(text, expected):
    assert apply_spoken_punctuation(text, "fr") == expected


def test_french_dictation_capitalization_and_commands():
    s = DictationSession("fr")
    t = s.render("bonjour point comment allez-vous")
    assert t == "Bonjour. Comment allez-vous"
    assert classify_command("arrête la dictée", "fr") == "stop"
    assert classify_command("efface ça", "fr") == "undo"


def say(env, text, lang="fr", free=None):
    env.disp.handle(SpeechEvent(text=text, free_text=free if free is not None else text, lang=lang))


def test_french_dispatcher_flow(env):
    env.gate.wake_words = ["ordinateur"]
    env.config.app_aliases["calculatrice"] = "calc.exe"
    env.disp.ctx.apps.set_aliases(env.config.app_aliases)
    say(env, "copie")                                   # sans mot d'éveil → rien
    assert env.os.calls == []
    say(env, "ordinateur ouvre la calculatrice")
    assert env.os.calls == [("launch", "calc.exe")]
    say(env, "ferme la fenêtre")                        # enchaînée sans mot d'éveil
    assert env.os.calls[-1] == ("close_window",)
    say(env, "ordinateur supprime")                     # dangereux → confirmation
    say(env, "oui")
    assert env.os.calls[-1] == ("key", "delete", 1)


def test_language_commands_from_any_language(env):
    env.gate.wake_words = ["ordinateur"]
    say(env, "ordinateur arabe")
    env.gate.wake_words = ["حاسوب"]
    say(env, "حاسوب الفرنسية", lang="ar")
    env.gate.wake_words = ["computer"]
    say(env, "computer french", lang="en")
    assert env.app.calls == [("set_language", "ar"), ("set_language", "fr"), ("set_language", "fr")]


def test_controller_language_cycle(tmp_path, monkeypatch):
    from conftest import FakeOS
    from config import loader
    from core import paths
    from core.controller import Controller
    monkeypatch.setattr(paths, "user_dir", lambda: tmp_path)
    c = Controller(FakeOS(), lambda *a, **k: None, loader.load_config(tmp_path))
    sent = []
    monkeypatch.setattr(c.audio, "send", lambda kind, **p: sent.append((kind, p)))
    try:
        seq = []
        for _ in range(3):
            c.toggle_language()
            seq.append((c.config.speech.language, c.gate.wake_words[0]))
        assert seq == [("en", "computer"), ("fr", "ordinateur"), ("ar", "حاسوب")]
        c.set_language("xx")                            # inconnue → ignorée
        assert c.config.speech.language == "ar"
        assert ("reload", {"language": "fr"}) in sent
    finally:
        c.shutdown()


def test_every_ui_string_has_french():
    from ui.i18n import STRINGS, Tr
    missing = [k for k, v in STRINGS.items() if "fr" not in v]
    assert missing == []
    t = Tr("fr")
    assert not t.rtl
    assert t("state_ready", wake="ordinateur") == "À l'écoute du mot d'éveil « ordinateur »"


def test_all_commands_have_three_languages(specs):
    for s in specs:
        assert {"ar", "en", "fr"} <= set(s["phrases"]), s["id"]


# ---------------- audio réel (voix Windows « Hortense ») ----------------
MODEL_FR = ROOT / "models" / "vosk" / "fr"


@pytest.fixture(scope="module")
def rec_fr():
    if not MODEL_FR.exists():
        pytest.skip("modèle Vosk français non téléchargé")
    from audio.recognizer import VoskRecognizer
    from commands.grammar import build_grammar, grid_and_dictation_phrases
    from commands.parser import CommandParser
    from config.loader import load_command_specs
    p = CommandParser(load_command_specs(FIXTURES / "no_user_dir"))
    g = build_grammar(p, "fr", ["ordinateur"], ["ouvre calculatrice"] + grid_and_dictation_phrases("fr"))
    return VoskRecognizer(MODEL_FR, 16000, g)


def transcribe(rec, name):
    import webrtcvad
    from audio.vad import FRAME_BYTES, Segmenter
    from audio.worker import AudioPipeline
    vad = webrtcvad.Vad(2)
    out = []
    pipe = AudioPipeline(rec, Segmenter(), lambda f: vad.is_speech(f, 16000), out.append, "fr")
    with wave.open(str(FIXTURES / "audio" / f"{name}.wav")) as w:
        data = w.readframes(w.getnframes()) + b"\0" * FRAME_BYTES * 40
    for i in range(0, len(data) - FRAME_BYTES + 1, FRAME_BYTES):
        pipe.process(data[i:i + FRAME_BYTES])
    pipe.flush()
    return [e for e in out if isinstance(e, SpeechEvent)]


@pytest.mark.parametrize("name,expected", [
    ("fr_close_window", [("close_window",)]),
    ("fr_open_calc", [("launch", "calc.exe")]),
    ("fr_copy", []),
    ("fr_chatter", []),
])
def test_french_wav_to_action(env, rec_fr, name, expected):
    env.gate.wake_words = ["ordinateur"]
    env.config.speech.language = "fr"
    env.config.app_aliases["calculatrice"] = "calc.exe"
    env.disp.ctx.apps.set_aliases(env.config.app_aliases)
    for ev in transcribe(rec_fr, name):
        env.disp.handle(ev)
    assert env.os.calls == expected


def test_french_wav_search_keeps_free_text(env, rec_fr):
    env.gate.wake_words = ["ordinateur"]
    env.config.speech.language = "fr"
    for ev in transcribe(rec_fr, "fr_search"):
        env.disp.handle(ev)
    assert env.os.calls[0] == ("open_search",)
    assert "météo" in env.os.calls[1][1] and "demain" in env.os.calls[1][1]


def test_french_wav_stop_and_wake_only(env, rec_fr):
    env.gate.wake_words = ["ordinateur"]
    env.config.speech.language = "fr"
    for name in ("fr_wake_only", "fr_copy"):
        for ev in transcribe(rec_fr, name):
            env.disp.handle(ev)
    assert env.os.calls == [("hotkey", "ctrl", "c")]
    for ev in transcribe(rec_fr, "fr_stop"):
        env.disp.handle(ev)
    assert env.app.calls[-1] == "pause"
