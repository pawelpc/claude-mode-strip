# Stops the strip (every copy started from this folder). Safe to run when nothing is running.
# Only matches python processes whose command line contains this folder's own src\main.py path.
$main = (Join-Path (Split-Path -Parent $PSScriptRoot) 'src\main.py').ToLower()
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -and $_.CommandLine.ToLower().Contains($main) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force; "stopped strip process $($_.ProcessId)" }
