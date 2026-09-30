# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: نسخة محمولة (onedir). النماذج تُنسخ بجانب الملف التنفيذي بواسطة build.ps1
# (وليس داخل الحزمة) لكي يمكن استبدالها أو إضافة نماذج دون إعادة البناء.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).parent
SRC = ROOT / "src"

datas = [(str(p), "config") for p in (SRC / "config").glob("*.yaml")]
binaries = []
hiddenimports = []
for pkg in ("audio", "commands", "config", "core", "os_layer", "ui", "vision"):
    hiddenimports += collect_submodules(pkg)

# مكتبات أصلية وملفات بيانات لا يكتشفها التحليل تلقائياً
for pkg in ("mediapipe",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
binaries += collect_dynamic_libs("vosk") + collect_dynamic_libs("ctranslate2")
datas += collect_data_files("vosk") + collect_data_files("faster_whisper")
hiddenimports += ["webrtcvad", "winsound", "win32api", "rapidfuzz.fuzz", "rapidfuzz.process"]

a = Analysis(
    [str(SRC / "main.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(ROOT / "scripts" / "pyi_hooks")],
    excludes=["tkinter", "IPython", "jupyter", "notebook", "pytest", "sounddevice",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "PySide6.QtPdf"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HADJ-NoTouch",
    console=False,               # تطبيق شريط النظام: بلا نافذة أوامر
    icon=str(ROOT / "build" / "app.ico"),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="HADJ-NoTouch")
