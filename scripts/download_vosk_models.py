"""
Downloads the offline Vosk speech models used by voice/audio_listener.py.

Usage:
    python scripts/download_vosk_models.py            # French + English
    python scripts/download_vosk_models.py fr ar      # chosen languages

Models are unpacked to models/vosk/<lang>/. They are large binary files, so
they are kept out of git and fetched once per machine.
"""
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

MODELS = {
    "fr": "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip",
    "en": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
    # No small Arabic model exists; this one is ~320 MB.
    "ar": "https://alphacephei.com/vosk/models/vosk-model-ar-mgb2-0.4.zip",
}

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "vosk")


def download(lang: str) -> None:
    target = os.path.join(ROOT, lang)
    if os.path.isdir(target) and os.listdir(target):
        print(f"[{lang}] already present: {target}")
        return

    url = MODELS[lang]
    os.makedirs(ROOT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = os.path.join(tmp, "model.zip")
        print(f"[{lang}] downloading {url}")
        urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
        # Archives contain a single versioned folder; store it under the language code.
        inner = next(
            os.path.join(tmp, d) for d in os.listdir(tmp)
            if os.path.isdir(os.path.join(tmp, d))
        )
        shutil.move(inner, target)
    print(f"[{lang}] installed in {target}")


if __name__ == "__main__":
    langs = sys.argv[1:] or ["fr", "en"]
    for code in langs:
        if code not in MODELS:
            sys.exit(f"Unknown language '{code}'. Choose from: {', '.join(MODELS)}")
        download(code)
