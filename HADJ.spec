# -*- mode: python ; coding: utf-8 -*-
import os
import sys

block_cipher = None

project_dir = os.path.abspath(SPECPATH)

added_files = [
    (os.path.join(project_dir, 'config'), 'config'),
    (os.path.join(project_dir, 'web'), 'web'),
    (os.path.join(project_dir, 'resources'), 'resources'),
]

hidden_imports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebChannel',
    'mediapipe',
    'mediapipe.python',
    'mediapipe.python.solutions',
    'cv2',
    'numpy',
    'sounddevice',
    'speech_recognition',
    'pyttsx3',
    'vosk',
    'win32gui',
    'win32api',
    'win32con',
    'win32process',
    'psutil',
    'pynput',
    'pynput.keyboard._win32',
    'pynput.mouse._win32',
    'pyautogui',
    'core.utils_path',
]

a = Analysis(
    ['main.py'],
    pathex=[project_dir],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'notebook', 'scipy'],
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
    name='HADJ',
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
    name='HADJ',
)
