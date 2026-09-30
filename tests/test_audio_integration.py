"""تكامل حقيقي: ملفات WAV مسجلة ← VAD ← Vosk ← الموزّع ← طبقة نظام وهمية.

يُتخطى تلقائياً إن لم تكن النماذج منزّلة (python scripts/download_models.py).
"""
import wave

import pytest

from audio.vad import FRAME_BYTES, SAMPLE_RATE, Segmenter
from audio.worker import AudioPipeline
from commands.grammar import build_grammar
from conftest import FIXTURES, ROOT
from core.events import SpeechEvent

MODEL = ROOT / "models" / "vosk" / "en"
pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="نموذج Vosk الإنجليزي غير منزّل")


@pytest.fixture(scope="module")
def recognizer():
    from audio.recognizer import VoskRecognizer
    from commands.parser import CommandParser
    from config.loader import load_command_specs
    p = CommandParser(load_command_specs(FIXTURES / "no_user_dir"))
    return VoskRecognizer(MODEL, SAMPLE_RATE, build_grammar(p, "en", ["computer"], ["open notepad"]))


def transcribe(recognizer, name):
    import webrtcvad
    vad = webrtcvad.Vad(2)
    out = []
    pipe = AudioPipeline(recognizer, Segmenter(), lambda f: vad.is_speech(f, SAMPLE_RATE), out.append, "en")
    with wave.open(str(FIXTURES / "audio" / f"{name}.wav")) as w:
        data = w.readframes(w.getnframes()) + b"\0" * FRAME_BYTES * 40
    for i in range(0, len(data) - FRAME_BYTES + 1, FRAME_BYTES):
        pipe.process(data[i:i + FRAME_BYTES])
    pipe.flush()
    return [e for e in out if isinstance(e, SpeechEvent)]


@pytest.mark.parametrize("name,expected", [
    ("en_close_window", [("close_window",)]),
    ("en_open_notepad", [("launch", "notepad.exe")]),
    ("en_search", [("open_search",), ("type_text", "weather today")]),
    ("en_copy", []),              # بدون كلمة تنبيه ← لا شيء
    ("en_chatter", []),           # كلام عادي ← لا شيء
])
def test_wav_to_action(env, recognizer, name, expected):
    env.gate.wake_words = ["computer"]
    env.config.speech.language = "en"
    for ev in transcribe(recognizer, name):
        env.disp.handle(ev)
    assert env.os.calls == expected


def test_stop_without_wake_word(env, recognizer):
    env.config.speech.language = "en"
    for ev in transcribe(recognizer, "en_stop"):
        env.disp.handle(ev)
    assert env.app.calls == ["pause"]


def test_wake_only_then_command(env, recognizer):
    env.gate.wake_words = ["computer"]
    env.config.speech.language = "en"
    for name in ("en_wake_only", "en_copy"):
        for ev in transcribe(recognizer, name):
            env.disp.handle(ev)
    assert env.os.calls == [("hotkey", "ctrl", "c")]


WHISPER = ROOT / "models" / "whisper" / "small"


def _pcm(name):
    with wave.open(str(FIXTURES / "audio" / f"{name}.wav")) as w:
        return w.readframes(w.getnframes())


@pytest.mark.skipif(not WHISPER.exists(), reason="نموذج Whisper غير منزّل")
def test_whisper_thread_transcribes_in_order():
    from audio.dictation import DictationThread
    from core.events import DictationEvent
    out = []
    th = DictationThread(WHISPER, out.append)
    th.submit(1, _pcm("en_chatter"), "en")
    th.submit(2, _pcm("en_close_window"), "en")
    th.stop()                       # يكمل ما في الطابور قبل الخروج
    th.thread.join(300)
    texts = [e for e in out if isinstance(e, DictationEvent)]
    assert [e.seg_id for e in texts] == [1, 2]
    assert "lunch" in texts[0].text.lower()
    assert "close" in texts[1].text.lower()
    assert [e.state for e in out if not isinstance(e, DictationEvent)] == ["loading", "ready"]


def test_pipeline_dictation_with_vosk_engine(recognizer, tmp_path):
    import webrtcvad
    from audio.worker import DictationControl
    from core.events import DictationEvent
    vad = webrtcvad.Vad(2)
    out = []
    pipe = AudioPipeline(recognizer, Segmenter(), lambda f: vad.is_speech(f, SAMPLE_RATE), out.append, "en")
    ctl = DictationControl(tmp_path, out.append)
    ctl.configure(pipe, {"on": True, "engine": "vosk"})
    data = _pcm("en_chatter") + b"\0" * FRAME_BYTES * 40
    for i in range(0, len(data) - FRAME_BYTES + 1, FRAME_BYTES):
        pipe.process(data[i:i + FRAME_BYTES])
    speech = [e for e in out if isinstance(e, SpeechEvent)]
    dict_ev = [e for e in out if isinstance(e, DictationEvent)]
    assert len(speech) == 1 and len(dict_ev) == 1
    assert out.index(speech[0]) < out.index(dict_ev[0])     # الأمر أولاً ثم النص
    assert dict_ev[0].seg_id == speech[0].seg_id
    assert "lunch" in dict_ev[0].text
    ctl.configure(pipe, {"on": False})
    assert pipe.dictation is None
