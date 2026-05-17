@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment...
    python -m venv .venv
)

echo Installing required packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo Starting DualLink Keyboard PC...
".venv\Scripts\python.exe" -m duallink_pc.gui

if errorlevel 1 (
    echo.
    echo DualLink PC app closed with an error.
    pause
)
