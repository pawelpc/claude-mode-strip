# Starts the strip now, with no console window. A second start does nothing (single instance).
$root = Split-Path -Parent $PSScriptRoot
$pyw = (Get-Command pythonw -ErrorAction Stop).Source
Start-Process $pyw -ArgumentList "`"$root\src\main.py`"" -WorkingDirectory $root
"started (if it was not already running)"
