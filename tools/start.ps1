# Starts the strip now, with no console window. Only one strip can run per log-on session (any folder).
# Reports which copy is running afterwards: this folder's, or one started from a different folder.
$root = Split-Path -Parent $PSScriptRoot
$main = (Join-Path $root 'src\main.py').ToLower()
$pyw = (Get-Command pythonw -ErrorAction Stop).Source
function Get-Strips { Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -and $_.CommandLine.ToLower().Contains('src\main.py') } }
Start-Process $pyw -ArgumentList "`"$root\src\main.py`"" -WorkingDirectory $root
Start-Sleep -Seconds 2
$all = @(Get-Strips)
$mine = @($all | Where-Object { $_.CommandLine.ToLower().Contains($main) })
if ($mine.Count -gt 0) { "running from this folder (process $($mine[0].ProcessId))" }
elseif ($all.Count -gt 0) { Write-Host "NOT started: a strip from a different folder is already running (process $($all[0].ProcessId)). Stop that copy with its own tools\stop.ps1 first, then start this one." -ForegroundColor Yellow }
else { Write-Host "NOT running: it exited at once. See %LOCALAPPDATA%\DesktopColorMod\error.log, or run: python src\main.py" -ForegroundColor Yellow }
