# Removes the strip: stops it, deletes the Startup shortcut and the error log folder.
# The project folder itself is left alone (delete it by hand if you want it gone).
# Run from the project folder:  powershell -ExecutionPolicy Bypass -File tools\uninstall.ps1
# -StartupDir is for testing only (defaults to your real Startup folder).
param([string]$StartupDir = [Environment]::GetFolderPath('Startup'))
& "$PSScriptRoot\stop.ps1"
$lnk = Join-Path $StartupDir 'Desktop Color Mod Strip.lnk'
if (Test-Path $lnk) { Remove-Item -LiteralPath $lnk -Force; Write-Host "Removed: $lnk" -ForegroundColor Green } else { Write-Host "No startup shortcut at $lnk" }
$ld = Join-Path $env:LOCALAPPDATA 'DesktopColorMod'
if (Test-Path $ld) { Remove-Item -LiteralPath $ld -Recurse -Force; Write-Host "Removed: $ld" -ForegroundColor Green }
Write-Host "Done. Nothing else was installed or changed."
