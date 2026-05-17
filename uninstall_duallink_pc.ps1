$ErrorActionPreference = "Stop"

$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "DualLink Keyboard PC.lnk"
$startMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "DualLink Keyboard"
$startShortcut = Join-Path $startMenuDir "DualLink Keyboard PC.lnk"
$installDir = Join-Path $env:LOCALAPPDATA "DualLink Keyboard PC"

Remove-Item -LiteralPath $desktopShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $startShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $startMenuDir -Force -Recurse -ErrorAction SilentlyContinue

if ((Resolve-Path -LiteralPath $PSScriptRoot -ErrorAction SilentlyContinue).Path -ne (Resolve-Path -LiteralPath $installDir -ErrorAction SilentlyContinue).Path) {
    Remove-Item -LiteralPath $installDir -Force -Recurse -ErrorAction SilentlyContinue
} else {
    Write-Host "Shortcuts removed. Close this window, then delete $installDir if you want to remove the portable files."
}
