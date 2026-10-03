@echo off
title HADJ NO-TOUCH - Windows Packaging
chcp 65001 >nul
cls

echo ============================================================
echo   HADJ NO-TOUCH AI - Windows Packaging ^& Distribution Build 
echo ============================================================
echo.

set "PY_EXE=C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY_EXE%" (
    where python >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY_EXE=python"
    ) else (
        echo [ERROR] Python was not found on your system.
        pause
        exit /b 1
    )
)

echo [HADJ] Running build_windows_dist.py with %PY_EXE%...
"%PY_EXE%" "%~dp0scripts\build_windows_dist.py"
echo.
pause
