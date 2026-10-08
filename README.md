# claude-mode-strip

A thin colored strip at Claude Desktop's input box (Windows) that always shows which mode you are in and which model is selected:

| Mode | Where | Looks like |
|---|---|---|
| **Code** | in the button row under the input box, in the gap between the left buttons and the model button | blue strip, `Code · Sonnet 5.5 Medium` |
| **Claude** (Cowork) | just above the input box | amber strip, `Cowork · Opus 5.5 Medium` |

Colors (light / dark theme): Code `#BFD9F7` on `#0B3D73` / `#1E3A5F` on `#DCEBFF`; Cowork `#F7D9A0` on `#5C3A00` / `#5A3D0A` on `#FFE9C2`. Every pair has a text contrast of at least 4.5:1. Height 18 px, corner radius 4 px, 12 px semibold system font.

If the Code-mode gap is narrower than 160 px, the strip moves above the input box. If the model can't be read it says `<Mode> · model ?`, never a guess.

## Using Claude Code to set it up
This repo is meant to be set up **by your own Claude Code session**. Get a copy (or download the ZIP from GitHub):
```
git clone https://github.com/pawelpc/claude-mode-strip
```
Then open the `claude-mode-strip` folder in Claude Code and say:

> Read SETUP.md and set this up for me.

Your Claude checks your machine, adapts anything that differs from the machine it was built on, runs the tests, and asks you before every step that installs something, changes your system or uses the network. At the end it can draft an install report for this repo. Nothing is sent unless you read the report and say yes.

## How it works (and what it does not do)
It is a **separate program**, not a change to Claude Desktop. It reads Claude's window with Windows UI Automation (read-only) and draws its own small window on top. It never injects code into, patches or hooks Claude Desktop, its files or its network traffic.

The strip window is **click-through** and **never takes focus**, so typing and clicking in Claude work as usual. It is owned by Claude's window: another application's window covers it, and it disappears when Claude is minimized or closed. It sends nothing over the network and has no telemetry.

## Requirements
- Windows 10 or 11 (built and tested on Windows 10 Home 22H2; it uses no Windows 11-only features).
- Claude Desktop with an English UI (the locator looks for English control names; see SETUP.md).
- Python 3.10+ (Microsoft Store Python is fine) and the packages in `requirements.txt` (`uiautomation`; `pillow` only for the guided test).

## Manual setup (without Claude)
```
python -m pip install -r requirements.txt
python -m unittest tests.test_core
python tools\check_locator.py
powershell -ExecutionPolicy Bypass -File tools\start.ps1
```
`check_locator.py` must end with `OK`. If it doesn't, see "Step 5: Adapt to this machine" in SETUP.md.

Start automatically at log-in (adds one shortcut, `Desktop Color Mod Strip.lnk`, to your user Startup folder; no admin needed):
```
powershell -ExecutionPolicy Bypass -File tools\install.ps1
```
`-ExecutionPolicy Bypass` applies to that one command only; it does not change your system's policy.

## Start, stop, uninstall
```
powershell -ExecutionPolicy Bypass -File tools\start.ps1
powershell -ExecutionPolicy Bypass -File tools\stop.ps1
powershell -ExecutionPolicy Bypass -File tools\uninstall.ps1
```
Only one strip runs at a time. Uninstall stops it and removes the Startup shortcut and the error-log folder `%LOCALAPPDATA%\DesktopColorMod`. Nothing else is installed, so deleting this folder afterwards removes everything (the Python packages stay; remove them with `python -m pip uninstall uiautomation pillow` if nothing else uses them).

## Behavior to expect
- **Switching Code ↔ Claude mode:** the color and mode word change within about 0.1 s. For about 1.3 s the model shows as `…`, because Claude's window can't be read during that time. Then the real model text appears.
- **Minimize and restore:** the strip hides with the window and comes back at once with `…`, then fills in.
- **Fast window drags** can lag a fraction of a second behind.
- In **Cowork mode** the strip sits 2 px above the input box, so it covers 18 px of a long reply scrolling behind it.

## If something is wrong
- **No strip:** check that Claude Desktop is open and not minimized, then run `tools\start.ps1`. Look for `%LOCALAPPDATA%\DesktopColorMod\error.log`.
- **Strip missing after a Claude Desktop update:** Claude's internal layout may have changed. Run `python tools\check_locator.py`; it names the assumption that broke and the code that holds it.
- **Watch it live:** `python src\main.py --log events.jsonl` runs in the console and logs every placement.

## Files
| Path | What |
|---|---|
| `src/` | the program: `main.py` entry, `strip_uia.py` tracker (UI Automation), `strip_overlay.py` window, `strip_core.py` placement/text/color logic, `winutil.py` Win32 helpers |
| `tests/test_core.py` | unit tests (`python -m unittest tests.test_core`) |
| `tools/` | `install`, `uninstall`, `start`, `stop` (.ps1); `check_locator.py`, `system_info.py` (read-only checks); `guided_test.ps1` + `strip_state.py` + `summarize_guided.py` (guided test) |
| `SETUP.md` | step-by-step guide for your Claude |
| `.github/ISSUE_TEMPLATE/install-report.md` | install report template |

## License
MIT, see `LICENSE`.
