@echo off
title HADJ NO-TOUCH OFFLINE AI
chcp 65001 >nul
cls

echo ============================================================
echo        HADJ NO-TOUCH OFFLINE AI - Desktop Controller        
echo   Complete Touchless Computer Control (Voice + Gesture + Vision)
echo ============================================================
echo.

set "PY_EXE=C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe"
if exist "%PY_EXE%" (
    echo [HADJ] Found Python 3.12 environment: %PY_EXE%
    "%PY_EXE%" "%~dp0main.py" %*
    goto :eof
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    echo [HADJ] Launching with system Python...
    python "%~dp0main.py" %*
    goto :eof
)

echo [ERROR] Python was not found on your system.
echo Please install Python 3.11 or 3.12 and ensure dependencies are installed.
pause
