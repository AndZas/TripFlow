@echo off
setlocal
cd /d "%~dp0"
python -X utf8 stand.py %*
if errorlevel 1 (
    pause
    exit /b 1
)
