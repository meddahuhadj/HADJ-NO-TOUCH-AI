"""توليد أصوات التغذية الراجعة القصيرة كملفات WAV (مرة واحدة، دون ملفات خارجية)."""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

RATE = 22050

# kind -> [(التردد Hz, المدة بالثواني), ...]
TONES = {
    "ok": [(880, 0.07), (1320, 0.09)],
    "error": [(330, 0.12), (220, 0.18)],
    "wake": [(660, 0.08)],
    "confirm": [(740, 0.1), (0, 0.05), (740, 0.1)],
    "pause": [(520, 0.1), (390, 0.1), (260, 0.14)],
    "resume": [(260, 0.08), (390, 0.08), (520, 0.12)],
}


def _samples(freq: float, dur: float, volume: float = 0.35):
    n = int(RATE * dur)
    fade = max(1, int(RATE * 0.01))
    for i in range(n):
        env = min(1.0, i / fade, (n - i) / fade)
        yield volume * env * (math.sin(2 * math.pi * freq * i / RATE) if freq else 0.0)


def ensure_sounds(folder: Path) -> dict[str, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for kind, tones in TONES.items():
        p = folder / f"{kind}.wav"
        if not p.exists():
            frames = b"".join(
                struct.pack("<h", int(s * 32767)) for f, d in tones for s in _samples(f, d))
            with wave.open(str(p), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(frames)
        paths[kind] = p
    return paths
