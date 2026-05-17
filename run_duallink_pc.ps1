$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating Python environment..."
    python -m venv .venv
}

Write-Host "Installing required packages..."
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "Starting DualLink Keyboard PC..."
& ".\.venv\Scripts\python.exe" -m duallink_pc.gui

