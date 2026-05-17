$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$pythonCandidates = @(
    "$PSScriptRoot\.build-venv\Scripts\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:ProgramFiles\Python312\python.exe",
    "$env:ProgramFiles\Python311\python.exe",
    "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

$systemPython = Get-Command python -ErrorAction SilentlyContinue
if ($systemPython) {
    $pythonCandidates += $systemPython.Source
}

if ($pythonCandidates.Count -eq 0) {
    throw "Python was not found. Install Python 3.11+ or run this from Codex where the bundled Python runtime is available."
}

$bootstrapPython = $pythonCandidates[0]
if (-not (Test-Path -LiteralPath ".build-venv\Scripts\python.exe")) {
    Write-Host "Creating build environment..."
    & $bootstrapPython -m venv ".build-venv"
}

$python = Resolve-Path ".build-venv\Scripts\python.exe"
Write-Host "Installing build dependencies..."
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt pyinstaller

Write-Host "Building Windows app..."
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name "DualLink Keyboard PC" `
    --distpath "dist" `
    --workpath "build\pyinstaller" `
    --specpath "build\pyinstaller" `
    "duallink_pc_gui.pyw"

$appDir = Resolve-Path "dist\DualLink Keyboard PC"
Copy-Item -LiteralPath "install_duallink_pc.bat" -Destination $appDir -Force
Copy-Item -LiteralPath "install_duallink_pc.ps1" -Destination $appDir -Force
Copy-Item -LiteralPath "uninstall_duallink_pc.bat" -Destination $appDir -Force
Copy-Item -LiteralPath "uninstall_duallink_pc.ps1" -Destination $appDir -Force

$readme = @"
DualLink Keyboard PC

Install:
1. Run install_duallink_pc.bat.
2. Open "DualLink Keyboard PC" from the Desktop or Start Menu.

Portable use:
Run "DualLink Keyboard PC.exe" directly from this folder.

Android:
Install the Android APK, open DualLink Keyboard, enable Accessibility, tap Start, then connect from this PC app.
"@
Set-Content -LiteralPath (Join-Path $appDir "README_INSTALL.txt") -Value $readme -Encoding UTF8

$zipPath = "dist\DualLinkKeyboardPC-Windows.zip"
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
Compress-Archive -LiteralPath $appDir -DestinationPath $zipPath

Write-Host ""
Write-Host "Windows app folder: $appDir"
Write-Host "Installer zip: $(Resolve-Path $zipPath)"
