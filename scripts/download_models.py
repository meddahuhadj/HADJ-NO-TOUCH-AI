"""تنزيل كل النماذج مرة واحدة قبل التشغيل/التغليف.

الاستخدام:
    python scripts/download_models.py            # كل النماذج
    python scripts/download_models.py vosk-ar    # نموذج محدد

بعد التنزيل لا يحتاج التطبيق أي اتصال بالإنترنت.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

HF_WHISPER = "https://huggingface.co/Systran/faster-whisper-small/resolve/main/"

# name -> (kind, url(s), destination)
CATALOG: dict[str, tuple[str, object, Path]] = {
    "vosk-en": (
        "zip",
        "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
        MODELS / "vosk" / "en",
    ),
    "vosk-ar": (
        "zip",
        "https://alphacephei.com/vosk/models/vosk-model-ar-mgb2-0.4.zip",
        MODELS / "vosk" / "ar",
    ),
    "vosk-fr": (
        "zip",
        "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip",
        MODELS / "vosk" / "fr",
    ),
    "hand": (
        "file",
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/latest/hand_landmarker.task",
        MODELS / "mediapipe" / "hand_landmarker.task",
    ),
    "whisper-small": (
        "files",
        [HF_WHISPER + f for f in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")],
        MODELS / "whisper" / "small",
    ),
}


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as resp, open(tmp, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {dest.name}: {done * 100 // total}% ({done >> 20} MB)", end="", flush=True)
    print()
    tmp.replace(dest)


def _install_zip(url: str, dest: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        archive = Path(td) / "model.zip"
        _download(url, archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(td)
        # الأرشيف يحتوي مجلداً واحداً في الجذر
        inner = next(p for p in Path(td).iterdir() if p.is_dir())
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(inner), dest)


def fetch(name: str) -> None:
    kind, src, dest = CATALOG[name]
    if dest.exists() and (dest.is_file() or any(dest.iterdir())):
        print(f"[=] {name}: موجود مسبقاً في {dest.relative_to(ROOT)}")
        return
    print(f"[↓] {name}")
    if kind == "zip":
        _install_zip(src, dest)
    elif kind == "file":
        _download(src, dest)
    else:
        for url in src:
            _download(url, dest / url.rsplit("/", 1)[1])
    print(f"[✓] {name} → {dest.relative_to(ROOT)}")


def main(argv: list[str]) -> int:
    names = argv or list(CATALOG)
    unknown = [n for n in names if n not in CATALOG]
    if unknown:
        print("نماذج غير معروفة:", ", ".join(unknown), "| المتاح:", ", ".join(CATALOG))
        return 2
    for n in names:
        fetch(n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
