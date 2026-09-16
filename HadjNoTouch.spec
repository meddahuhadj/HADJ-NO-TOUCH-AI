# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for HADJ NO-TOUCH AI.
#
# NOTE: build_app.py is the primary build path (onedir, windowed, web bundled).
# This spec is kept as a reproducible alternative: single-file, console-less,
# with everything collected from the environment — no hard-coded absolute
# paths. Run from the repo root with:
#     python -m PyInstaller --noconfirm HadjNoTouch.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['comtypes', 'pythoncom', 'pywintypes', 'win32gui', 'win32con']
datas += collect_data_files('sounddevice')

# Bundle every model/data a runtime dependency ships (mediapipe tied to this
# app; hadj_no_touch itself; cv2) — guarded so a missing package never breaks
# the spec upfront.
for _pkg in ('mediapipe', 'hadj_no_touch', 'cv2'):
    try:
        _ret = collect_all(_pkg)
    except Exception:
        continue
    datas += _ret[0]
    binaries += _ret[1]
    hiddenimports += _ret[2]

# Marketing PWA (web/ folder) ships inside the binary so the local
# "web/README" mirror and landing pages travel with the product.
datas += [('web', 'web')]

# Optional local-voice packages (only bundled if present in this env).
for _pkg in ('vosk', 'soundcard'):
    try:
        _ret = collect_all(_pkg)
    except Exception:
        continue
    datas += _ret[0]
    binaries += _ret[1]
    hiddenimports += _ret[2]

_ROOT = Path(SPECPATH)
_ICON = _ROOT / 'build' / 'icon.ico'

a = Analysis(
    ['main.py'],
    pathex=[str(_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HADJ-NO-TOUCH-AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[str(_ICON)] if _ICON.exists() else None,
)