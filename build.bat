@echo off
title HADJ NO-TOUCH AI - Compilation Windows Autonome (HADJ.exe)
chcp 65001 >nul
cls

echo ============================================================
echo   HADJ NO-TOUCH AI - Build Windows Autonome (HADJ.exe)
echo ============================================================
echo.

set "PY_EXE=C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY_EXE%" (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY_EXE=python"
    ) else (
        echo [ERREUR] Python n'a pas été trouvé sur votre système.
        pause
        exit /b 1
    )
)

echo [HADJ] Verification et installation des dépendances de compilation...
"%PY_EXE%" -m pip install --quiet pyinstaller pillow

echo [HADJ] Lancement de la compilation autonome avec HADJ.spec...
"%PY_EXE%" -m PyInstaller --noconfirm HADJ.spec

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] La compilation PyInstaller a échoué.
    pause
    exit /b %errorlevel%
)

echo.
echo ============================================================
echo   BUILD RÉUSSI !
echo   Exécutable autonome créé dans : dist\HADJ\HADJ.exe
echo ============================================================
echo.
pause
