@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_duallink_pc.ps1"
if errorlevel 1 (
    echo.
    echo Install failed.
    pause
    exit /b 1
)
echo.
echo DualLink Keyboard PC installed.
pause
