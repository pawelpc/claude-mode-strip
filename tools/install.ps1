# Installs the strip to start when you log in: one shortcut in your user Startup folder. No admin needed.
# Run from the project folder:  powershell -ExecutionPolicy Bypass -File tools\install.ps1
# -StartupDir is for testing only (defaults to your real Startup folder).
param([string]$StartupDir = [Environment]::GetFolderPath('Startup'))
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pyw = (Get-Command pythonw -ErrorAction Stop).Source
& python -c "import uiautomation" 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "Python package 'uiautomation' is missing. Run:  python -m pip install -r `"$root\requirements.txt`"" -ForegroundColor Yellow; exit 1 }
New-Item -ItemType Directory -Force $StartupDir | Out-Null
$lnk = Join-Path $StartupDir 'Desktop Color Mod Strip.lnk'
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($lnk)
$s.TargetPath = $pyw
$s.Arguments = "`"$root\src\main.py`""
$s.WorkingDirectory = $root
$s.WindowStyle = 7
$s.Description = 'Desktop Color Mod indicator strip'
$s.Save()
Write-Host "Created: $lnk" -ForegroundColor Green
Write-Host "Target : $pyw `"$root\src\main.py`""
& "$PSScriptRoot\start.ps1"
