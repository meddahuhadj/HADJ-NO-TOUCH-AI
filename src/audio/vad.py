"""تقطيع الصوت إلى عبارات باستخدام كاشف الكلام (VAD).

Segmenter منطق بحت (بلا ميكروفون) لكي يُختبر بمدخلات محاكاة.
"""
from __future__ import annotations

from collections import deque

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_BYTES = SAMPLE_RATE * FRAME_MS // 1000 * 2  # int16 mono


class Segmenter:
    def __init__(self, silence_ms: int = 600, max_ms: int = 12000, preroll_ms: int = 300,
                 trigger_window: int = 5, trigger_voiced: int = 3, frame_ms: int = FRAME_MS):
        self.frame_ms = frame_ms
        self.silence_frames = max(1, silence_ms // frame_ms)
        self.max_frames = max(1, max_ms // frame_ms)
        self.trigger_voiced = trigger_voiced
        self._preroll: deque[bytes] = deque(maxlen=max(1, preroll_ms // frame_ms))
        self._window: deque[bool] = deque(maxlen=trigger_window)
        self.in_speech = False
        self._silence = 0
        self._length = 0

    def reset(self) -> None:
        self._preroll.clear()
        self._window.clear()
        self.in_speech = False
        self._silence = 0
        self._length = 0

    def push(self, frame: bytes, is_speech: bool) -> list[tuple[str, bytes]]:
        """يرجع أحداثاً: ("start", b"") ثم ("audio", frame)... ثم ("end", b"")."""
        out: list[tuple[str, bytes]] = []
        if not self.in_speech:
            self._preroll.append(frame)
            self._window.append(is_speech)
            if sum(self._window) >= self.trigger_voiced:
                self.in_speech = True
                self._silence = 0
                self._length = len(self._preroll)
                out.append(("start", b""))
                out.extend(("audio", f) for f in self._preroll)
                self._preroll.clear()
                self._window.clear()
            return out
        out.append(("audio", frame))
        self._length += 1
        self._silence = 0 if is_speech else self._silence + 1
        if self._silence >= self.silence_frames or self._length >= self.max_frames:
            out.append(("end", b""))
            self.in_speech = False
            self._silence = 0
            self._length = 0
        return out
