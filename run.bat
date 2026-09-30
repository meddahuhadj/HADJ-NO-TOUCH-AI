@echo off
rem تشغيل التطبيق من الكود المصدري (أضف --debug لسجل مفصل)
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" src\main.py %*
