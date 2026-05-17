@echo off
setlocal
cd /d "%~dp0"

echo DualLink Keyboard PC debug launcher
echo Folder: %CD%
echo.

where python
if errorlevel 1 (
    echo Python was not found. Install Python and tick "Add Python to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create Python environment.
        pause
        exit /b 1
    )
)

echo Installing required packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install packages.
    pause
    exit /b 1
)

echo.
echo Starting DualLink Keyboard PC GUI...
".venv\Scripts\python.exe" -m duallink_pc.gui

echo.
echo The app closed. If there is an error above, send it to Codex.
pause

