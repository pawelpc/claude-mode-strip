# Guided test for the Claude mode strip. Run it yourself in a normal PowerShell window:
#   powershell -ExecutionPolicy Bypass -File tools\guided_test.ps1
# It walks you through ~13 short steps. After each one, come back here and answer y / n / na.
# What it does: stops the strip if it is running from this folder, starts a test copy with an event
# log, and after each step reads the strip's own window (position, colors, click-through) with
# tools\strip_state.py. It takes no full screenshots (only the strip's own pixels, read in memory) and sends
# nothing anywhere. states.jsonl includes the title of the window in front at each step; summary.md does not.
# Output: test-output\guided-<date>\ inside this folder (summary.md is the part to read).
# If the strip was running before the test, it is started again at the end.

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$main = Join-Path $root 'src\main.py'
$out = Join-Path $root ('test-output\guided-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force $out | Out-Null
$answers = Join-Path $out 'answers.jsonl'
$states = Join-Path $out 'states.jsonl'

function Get-StripProcs { Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -and $_.CommandLine.ToLower().Contains($main.ToLower()) } }
function Stop-Strip { & (Join-Path $PSScriptRoot 'stop.ps1') | Out-Null }
function Start-Strip {
    Start-Process python -ArgumentList "`"$main`"", '--log', "`"$out\strip-events.jsonl`"" -WindowStyle Hidden -RedirectStandardError "$out\strip.err"
}
function Capture($label) {
    Start-Sleep -Milliseconds 1200
    python -W ignore tools\strip_state.py $label | Add-Content -Path $states -Encoding utf8
}
function Step($id, $title, $text) {
    Write-Host ""
    Write-Host "=== $id : $title ===" -ForegroundColor Cyan
    Write-Host $text
    $null = Read-Host "Press Enter when done (wait about 3 s after the action first)"
    Capture $id
}
function Ask($id, $q) {
    $a = Read-Host "$q`n  Answer y / n / na (optionally add a short note after a space)"
    (@{ id = $id; q = $q; a = $a } | ConvertTo-Json -Compress) | Add-Content -Path $answers -Encoding utf8
}

Clear-Host
Write-Host "Claude mode strip: guided test" -ForegroundColor Green
Write-Host "Output folder: $out"
Write-Host "Start with Claude Desktop open, maximized on your main monitor, in Code mode."
$null = Read-Host "Press Enter to start a test copy of the strip"
$wasRunning = [bool](Get-StripProcs)
Stop-Strip
Start-Strip
Start-Sleep 6
if (-not (Get-StripProcs)) {
    Write-Host "The test copy did not start or exited at once. See $out\strip.err." -ForegroundColor Red
    Write-Host "If a copy of the strip from ANOTHER folder is running, stop it first (only one copy can run)." -ForegroundColor Red
    exit 1
}

Step 's01' 'Code mode' 'Look at the row of buttons under the input box.'
Ask 's01' "Is there a blue strip in that row, between the left buttons and the model button, reading 'Code', then the model and effort exactly as Claude's own buttons show them?"

Step 's02' 'Switch to Cowork' "Click the 'Claude' mode button at the top of the window (Cowork mode)."
Ask 's02' "Is there an amber strip just ABOVE the input box reading 'Cowork' and the model, not covering any text below the box? (It may show '...' for about a second first.)"

Step 's03' 'Grow the box in Cowork' 'Type 5 lines in the input box (Shift+Enter between lines). Then delete them.'
Ask 's03' 'Did the strip stay just above the top of the box as it grew and shrank, never overlapping it?'

Step 's04' 'Back to Code' "Click the 'Code' mode button."
Ask 's04' 'Is the blue strip back in the button row with the right model and effort?'

Step 's05' 'Change model or effort' 'In Code mode, pick a different model or effort level with Claude''s own buttons.'
Ask 's05' 'Does the strip text match the new choice exactly (within about a second)?'

Step 's06' 'Grow the box in Code' 'Type 5 lines (Shift+Enter), wait, then delete them.'
Ask 's06' 'Did the strip stay in the button row, never overlapping the box or any button?'

Step 's07a' 'Restore and narrow' 'Click the window''s Restore button (un-maximize), then drag its corner to make the window about 700 px wide.'
Step 's07b' 'Move' 'Drag the window by its title bar to another spot on the same monitor.'
Step 's07c' 'Maximize' 'Click Maximize.'
Ask 's07' 'Through restore, narrow, move and maximize: did the strip follow the input box, stay inside the window, and never overlap the box, a button or the taskbar?'

Step 's08' 'Cover with another app' 'Open any other app (e.g. Notepad) and move its window over the strip area.'
Ask 's08' 'Is the strip hidden behind the other app''s window (not drawn on top of it)?'
Write-Host 'Close or move that app away again.'

Step 's09a' 'Minimize' 'Minimize Claude Desktop.'
Ask 's09a' 'Is NO strip visible anywhere on any monitor?'
Step 's09b' 'Restore' 'Restore Claude Desktop from the taskbar.'
Ask 's09b' 'Is the strip back in the right place?'

Step 's10' 'Second monitor (optional)' 'If you have a second monitor: move Claude Desktop there and maximize it. If not, just press Enter.'
Ask 's10' 'Is the strip on the same monitor as Claude, in the right place, with no copy left behind? (na if you have one monitor)'
Write-Host 'If you moved it, move Claude back to the main monitor and maximize it.'

Write-Host ''
Write-Host '=== s11 : Click-through ===' -ForegroundColor Cyan
Write-Host '1) Click in the input box and type abc.  2) Press Ctrl+A, then Delete.  3) Drag-select some text just above the input box.'
$null = Read-Host 'Press Enter when done'
Capture 's11-on'
Stop-Strip
Write-Host 'The strip is now OFF. Repeat the same three actions.' -ForegroundColor Yellow
$null = Read-Host 'Press Enter when done'
Ask 's11' 'Did clicking, typing and selecting behave the same with the strip on and off?'
Start-Strip; Start-Sleep 5

Write-Host ''
Write-Host '=== s12 : Theme (optional) ===' -ForegroundColor Cyan
$dk = Read-Host 'Do you want to test the other Claude theme (light/dark) now? (y/n)'
if ($dk -eq 'y') {
    $null = Read-Host 'Switch Claude Desktop to the other theme in its settings, wait about 5 s, then press Enter'
    Capture 's12-code'
    $null = Read-Host "Click the 'Claude' mode button (Cowork), wait about 5 s, then press Enter"
    Capture 's12-cowork'
    Ask 's12' 'In the other theme, are both strips readable with colors matching the theme?'
    $null = Read-Host 'Switch the theme back to what you normally use and return to Code mode, then press Enter'
} else {
    (@{ id = 's12'; q = 'other theme'; a = 'na skipped' } | ConvertTo-Json -Compress) | Add-Content -Path $answers -Encoding utf8
}

Write-Host ''
Write-Host '=== s13 : Idle CPU (60 s) ===' -ForegroundColor Cyan
$null = Read-Host 'Leave Claude maximized and do not touch anything for 60 s. Press Enter to start'
$pr = Get-StripProcs | Select-Object -First 1
if ($pr) {
    $c0 = (Get-Process -Id $pr.ProcessId).TotalProcessorTime.TotalSeconds; $t0 = Get-Date
    Start-Sleep 60
    $c1 = (Get-Process -Id $pr.ProcessId).TotalProcessorTime.TotalSeconds; $dt = ((Get-Date) - $t0).TotalSeconds
    $one = [math]::Round(100 * ($c1 - $c0) / $dt, 2)
    Write-Host "Strip CPU: $one % of one core" -ForegroundColor Green
    (@{ id = 's13'; q = 'idle cpu percent of one core'; a = "$one" } | ConvertTo-Json -Compress) | Add-Content -Path $answers -Encoding utf8
}
Capture 's13-final'
Stop-Strip
python tools\summarize_guided.py "$out"
if ($wasRunning) { & (Join-Path $PSScriptRoot 'start.ps1') | Out-Null; Write-Host 'Your strip was running before the test; it has been started again.' }
Write-Host ''
Write-Host "Done. Results: $out\summary.md" -ForegroundColor Green
