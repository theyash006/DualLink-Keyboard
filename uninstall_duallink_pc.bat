@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall_duallink_pc.ps1"
if errorlevel 1 (
    echo.
    echo Uninstall failed.
    pause
    exit /b 1
)
echo.
echo DualLink Keyboard PC uninstalled.
pause
