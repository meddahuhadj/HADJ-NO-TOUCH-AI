@echo off
setlocal
title HADJ NO-TOUCH OFFLINE AI
chcp 65001 >nul
cd /d "%~dp0"
cls

echo ============================================================
echo        HADJ NO-TOUCH OFFLINE AI - Desktop Controller
echo   Complete Touchless Computer Control (Voice + Gesture + Vision)
echo ============================================================
echo.

rem The app runs from its own environment in .venv so it works on any PC,
rem whatever Python packages are (or are not) installed system-wide.
set "VENV=%~dp0.venv"
set "VPY=%VENV%\Scripts\python.exe"

if exist "%VPY%" goto :deps

rem mediapipe 0.10.x only ships wheels for Python 3.10 - 3.12.
set "BASE_PY="
for %%V in (3.12 3.11 3.10) do (
    if not defined BASE_PY (
        py -%%V -c "import sys" >nul 2>nul && set "BASE_PY=py -%%V"
    )
)
if not defined BASE_PY (
    python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>nul && set "BASE_PY=python"
)
if not defined BASE_PY goto :nopython

echo [HADJ] Premiere installation : creation de l'environnement (.venv)...
%BASE_PY% -m venv "%VENV%"
if errorlevel 1 goto :fail

:deps
rem Install on first run, and again whenever requirements.txt changes.
fc /b "requirements.txt" "%VENV%\requirements.installed" >nul 2>nul
if not errorlevel 1 goto :models
echo [HADJ] Installation des dependances (plusieurs minutes la premiere fois)...
"%VPY%" -m pip install --disable-pip-version-check --upgrade pip
"%VPY%" -m pip install --disable-pip-version-check -r "requirements.txt"
if errorlevel 1 goto :fail
copy /y "requirements.txt" "%VENV%\requirements.installed" >nul

:models
if not exist "models\vosk\fr" (
    echo [HADJ] Telechargement des modeles vocaux hors ligne...
    "%VPY%" "scripts\download_vosk_models.py" fr en
    if errorlevel 1 echo [HADJ] Modeles vocaux non installes : la voix utilisera la reconnaissance en ligne.
)

echo [HADJ] Demarrage...
"%VPY%" "main.py" %*
if errorlevel 1 (
    echo.
    echo [ERREUR] L'application s'est arretee avec une erreur ^(voir ci-dessus^).
    pause
)
goto :eof

:nopython
echo [ERREUR] Python 3.10, 3.11 ou 3.12 est introuvable sur ce PC.
echo          ^(Python 3.13 et plus ne sont pas compatibles avec MediaPipe.^)
echo.
where winget >nul 2>nul
if errorlevel 1 goto :manualpython
choice /c ON /m "Installer Python 3.12 automatiquement maintenant (O = oui, N = non)"
if errorlevel 2 goto :manualpython
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo [HADJ] Python installe. Fermez cette fenetre puis relancez launch.bat.
pause
exit /b 1

:manualpython
echo Telechargez Python 3.12 : https://www.python.org/downloads/release/python-3120/
echo Cochez "Add python.exe to PATH" pendant l'installation, puis relancez launch.bat.
pause
exit /b 1

:fail
echo.
echo [ERREUR] L'installation a echoue. Verifiez la connexion Internet puis relancez launch.bat.
echo          Pour repartir de zero, supprimez le dossier .venv.
pause
exit /b 1
