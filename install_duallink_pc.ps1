$ErrorActionPreference = "Stop"

$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exeName = "DualLink Keyboard PC.exe"
$sourceExe = Join-Path $sourceDir $exeName
if (-not (Test-Path -LiteralPath $sourceExe)) {
    throw "Could not find $exeName next to this installer. Build the app first or run this from the release folder."
}

$installDir = Join-Path $env:LOCALAPPDATA "DualLink Keyboard PC"
if (-not (Test-Path -LiteralPath $installDir)) {
    New-Item -ItemType Directory -Path $installDir | Out-Null
}

Write-Host "Installing to $installDir..."
Copy-Item -Path (Join-Path $sourceDir "*") -Destination $installDir -Recurse -Force

$wsh = New-Object -ComObject WScript.Shell
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "DualLink Keyboard PC.lnk"
$startMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "DualLink Keyboard"
if (-not (Test-Path -LiteralPath $startMenuDir)) {
    New-Item -ItemType Directory -Path $startMenuDir | Out-Null
}
$startShortcut = Join-Path $startMenuDir "DualLink Keyboard PC.lnk"

foreach ($shortcutPath in @($desktopShortcut, $startShortcut)) {
    $shortcut = $wsh.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = Join-Path $installDir $exeName
    $shortcut.WorkingDirectory = $installDir
    $shortcut.Description = "DualLink Keyboard PC"
    $shortcut.Save()
}

Write-Host "Desktop shortcut: $desktopShortcut"
Write-Host "Start Menu shortcut: $startShortcut"
