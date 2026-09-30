"""غلاف Vosk: مُعرِّف حر + مُعرِّف مقيّد بالقواعد (إن دعم النموذج ذلك)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def supports_grammar(model_dir: Path) -> bool:
    """النماذج ذات الرسم الديناميكي (Gr.fst + HCLr.fst) تقبل قواعد وقت التشغيل."""
    g = model_dir / "graph"
    return (g / "Gr.fst").exists() and (g / "HCLr.fst").exists()


class VoskRecognizer:
    def __init__(self, model_dir: Path, sample_rate: int = 16000,
                 grammar: list[str] | None = None, use_grammar: str = "auto"):
        import vosk
        vosk.SetLogLevel(-1)
        if not model_dir.exists():
            raise FileNotFoundError(f"نموذج الصوت غير موجود: {model_dir}")
        self._vosk = vosk
        self.rate = sample_rate
        self.model = vosk.Model(str(model_dir))
        can = supports_grammar(model_dir)
        self.grammar_enabled = bool(grammar) and (use_grammar == "on" or (use_grammar == "auto" and can))
        if use_grammar == "on" and not can:
            log.warning("النموذج %s لا يدعم القواعد؛ سيُستخدم التعرف الحر", model_dir.name)
            self.grammar_enabled = False
        self._grammar_json = json.dumps(list(grammar or []) + ["[unk]"], ensure_ascii=False)
        self._free = None
        self._gram = None
        self.reset()

    def reset(self) -> None:
        self._free = self._vosk.KaldiRecognizer(self.model, self.rate)
        self._gram = (self._vosk.KaldiRecognizer(self.model, self.rate, self._grammar_json)
                      if self.grammar_enabled else None)

    def set_grammar(self, grammar: list[str]) -> None:
        self._grammar_json = json.dumps(list(grammar) + ["[unk]"], ensure_ascii=False)
        self.reset()

    def accept(self, frame: bytes) -> None:
        self._free.AcceptWaveform(frame)
        if self._gram is not None:
            self._gram.AcceptWaveform(frame)

    def partial(self) -> str:
        return json.loads(self._free.PartialResult()).get("partial", "")

    def finish(self) -> tuple[str, str]:
        """يرجع (نص القواعد أو الحر، النص الحر) ويجهّز لعبارة جديدة."""
        free = json.loads(self._free.FinalResult()).get("text", "").strip()
        gram = ""
        if self._gram is not None:
            gram = json.loads(self._gram.FinalResult()).get("text", "").strip()
        # FinalResult يعيد تهيئة المُعرِّف تلقائياً لعبارة جديدة
        return (gram or free), free
