@echo off
REM ============================================================
REM  HADJ NO-TOUCH AI - Windows launcher
REM  Prefers Python 3.10-3.12 (MediaPipe does not run on 3.13+).
REM ============================================================
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
    py -3.12 --version >nul 2>nul
    if not errorlevel 1 (
        py -3.12 main.py %*
        goto :eof
    )
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 (
        py -3.11 main.py %*
        goto :eof
    )
    py -3.10 --version >nul 2>nul
    if not errorlevel 1 (
        py -3.10 main.py %*
        goto :eof
    )
)

python --version >nul 2>nul
if not errorlevel 1 (
    python main.py %*
    goto :eof
)

echo Python 3.10-3.12 was not found. Install it from https://www.python.org/downloads/
pause