# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

project_dir = os.path.abspath(SPECPATH)

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

# Only shipped defaults: user_settings.json and auth_token.secret are created
# per machine on first run and must never be copied to other PCs.
added_files = [
    (os.path.join(project_dir, 'config', name), 'config')
    for name in ('default_config.json', 'custom_commands.json', 'macros.json')
] + [
    (os.path.join(project_dir, 'web'), 'web'),
    (os.path.join(project_dir, 'resources'), 'resources'),
    # Offline voice models (scripts/download_vosk_models.py).
    (os.path.join(project_dir, 'models', 'vosk'), os.path.join('models', 'vosk')),
] + collect_data_files('speech_recognition') + collect_data_files(
    # Graph (.binarypb) and model (.tflite) files the hand tracker loads by path.
    'mediapipe', includes=['**/*.binarypb', '**/*.tflite', '**/*.txt'],
)

# libvosk.dll and its runtime DLLs are loaded with ctypes, invisible to analysis.
added_binaries = collect_dynamic_libs('vosk')

hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebChannel',
    'mediapipe',
    'cv2',
    'numpy',
    'sounddevice',
    'speech_recognition',
    'pyttsx3',
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',
    'comtypes.client',
    'vosk',
    'pycaw.pycaw',
    'win32gui',
    'win32api',
    'win32con',
    'win32process',
    'psutil',
    'pyautogui',
]

a = Analysis(
    ['main.py'],
    pathex=[project_dir],
    binaries=added_binaries,
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # matplotlib stays: mediapipe's drawing_utils imports it.
    excludes=['tkinter', 'notebook', 'torch', 'torchvision', 'tensorflow', 'pandas', 'pyarrow', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_file = os.path.join(project_dir, 'resources', 'app_icon.ico')
exe_icon = icon_file if os.path.exists(icon_file) else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HADJ_NoTouch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HADJ_NoTouch',
)
