# SETUP.md: guide for the user's Claude

You are a Claude Code session that a user opened in this folder to set up **claude-mode-strip**: a small
Windows program that draws a colored strip at Claude Desktop's input box showing the current mode and
model (see README.md). Follow these steps in order. You adapt the program to this machine, test it, install
it if the user wants, and at the end can draft an install report for the project.

## Ground rules (read first, follow throughout)
1. **Ask before every step that changes the user's system.** Each such step below starts with a line
   **ASK FIRST**. Show the exact command, say in one or two sentences what it changes, and wait for a clear
   yes. A yes covers that step only. If the user says no, skip it and note that.
2. **Ask before any network call.** Only three steps use the network: installing Python packages (step 3),
   optionally updating this folder from GitHub, and sending the install report (step 10). The program
   itself never uses the network and has no telemetry.
3. **Don't write outside this folder** except where a step says so and the user agreed: the Python
   packages (step 3), the Startup shortcut (step 9), and the program's own error log
   `%LOCALAPPDATA%\DesktopColorMod\error.log`, which is written only if the strip hits an error (mention
   this at step 6).
4. **Nothing hidden.** Run commands in the open, show their output, and explain failures in plain words.
5. **Record every change you make to the code or scripts** in `install-notes.md` in this folder (it is
   git-ignored): file, what changed, why, and the minimal diff. Step 10 builds the report's "What had to be
   changed" section from it.
6. **Never touch Claude Desktop itself.** The program only reads Claude's window through Windows UI
   Automation and draws its own window. Don't edit Claude Desktop's files, settings or processes.
7. Use PowerShell syntax, one command per line, from this folder.

## Step 1: Read-only checks (no changes)
Tell the user you're going to run read-only checks, then run:
```
python --version
python tools\system_info.py
```
- Python must be 3.10 or newer. If `python` is missing, stop and tell the user. Installing Python is their
  decision (e.g. Microsoft Store "Python 3.12", or python.org). Don't install it yourself.
- `system_info.py` uses only the standard library. It prints the Windows version and build, Python version,
  whether Claude Desktop is running and its version, display scaling and monitor count. It prints no names
  or paths. Keep this output for the report.
- If `claude_desktop.running` is false, ask the user to open Claude Desktop (not minimized) and run it again.
  If Claude is open but still not found, the window-finding assumption failed: see step 5, row 1.

## Step 2: Read the code you are about to run
Skim `src/` (5 files) and `tools/` before running anything that isn't read-only, and tell the user in a few
lines what it does. It should match README.md: read-only UI Automation, one click-through overlay window,
no network. If you find anything else, stop and tell the user.

## Step 3: Install the Python packages
First check, read-only and offline, whether they are already there:
```
python -m pip show uiautomation pillow
```
If both are listed (`uiautomation` must be 2.0.29, `pillow` 10 or newer), skip the install and tell the user.
Ignore pip's "a new release of pip is available" notice; upgrading pip is not part of this setup.

Mention once that the packages can go into a virtual environment in this folder instead of their normal
Python. The default is their normal Python.

**ASK FIRST:** "May I run `python -m pip install -r requirements.txt`? It downloads `uiautomation` (reads
window controls) and `pillow` (only used by the guided test to read the strip's colors) from PyPI and
installs them into your Python. This uses the network and writes to Python's package folder."
```
python -m pip install -r requirements.txt
```
If the user wants a virtual environment, **ASK FIRST:** "May I create a virtual environment with
`python -m venv .venv` in this folder and install the packages there instead of your normal Python? It
writes a `.venv` folder here and downloads the packages from PyPI." Then use `.venv\Scripts\python.exe` and
`.venv\Scripts\pythonw.exe` from then on. Record that in `install-notes.md`, and adjust the scripts as in
step 5, row 9.

## Step 4: Unit tests and locator check (read-only)
```
python -m unittest tests.test_core
python tools\check_locator.py
```
- The unit tests cover placement, text and colors. They must all pass before you go on.
- `check_locator.py` runs the program's own discovery once against the open Claude window and ends with
  `OK` or `NOT OK` plus which assumption failed. Run it with Claude Desktop **open, in Code mode**, then ask
  the user to switch to the **Claude (Cowork)** mode button and run it again. Both must say `OK`.
- If Claude is in Cowork mode when you start, run it there first and then ask for Code mode.
- Its output lists the names of the buttons under the input box. Those can include folder or project names
  and the usage button's text (context and plan-limit figures), so **don't put that output into the
  report.** Summarize it as OK / NOT OK and which assumption.

Then:
- If one says `NOT OK`, go to step 5.
- Otherwise go to step 6. That covers both modes `OK`, and the case where the user didn't want to switch
  modes: then tell them the other mode is untested, and write "not checked (user declined)" for it in
  the report.

## Step 5: Adapt to this machine (only if something didn't hold)
The program was built on one machine: Windows 10 Home 22H2, 100 % scaling, light and dark theme, English
Claude Desktop UI, Microsoft Store Python 3.10. These are the assumptions that may differ, and where they
live:

| # | Assumption | Where | How to check / typical fix |
|---|---|---|---|
| 1 | Claude's main window is visible, titled exactly `Claude`, class `Chrome_WidgetWin_1`, process `Claude.exe` | `src/winutil.py` `find_claude_hwnd()` | List top-level windows of `Claude.exe` with UI Automation and compare their title and class. Adjust the match. |
| 2 | Mode buttons are RadioButtons named `Claude` and `Code` (English UI); the active one's aria properties contain `checked=true`. `Claude` means Cowork mode. | `src/strip_uia.py` `discover()` and the mode re-read in `Tracker._loop()` | Inspect the RadioButtons with `uiautomation` (e.g. `auto.ControlFromHandle(hwnd)`, walk descendants). Other UI languages need the translated names in both places. |
| 3 | The input box is an Edit control whose class contains `ProseMirror` (the lowest visible one is used) | `src/strip_uia.py` `discover()` | Find the Edit control under the text cursor. Adjust the class test. |
| 4 | The composer container is an ancestor of the input (within 8 levels) whose class contains `bg-surface` and that is wider than the input | `src/strip_uia.py` `discover()` | Walk the input's parents and print class names and rects. Choose the box that visually frames the input. |
| 5 | The button row: buttons whose vertical centre is between the container's bottom − 4 px and bottom + 70 px, horizontally within the container ± 24 px. These limits are physical pixels and are **not** scaled for DPI. | `src/strip_uia.py` `discover()` | At high scaling (150 % and up), if the model button is missed, scale these limits by the window's DPI scale (`winutil.dpi_scale`). |
| 6 | Model button name starts with `Model: `; effort button (Code mode) with `Effort: ` | `src/strip_uia.py` `discover()`, `src/strip_core.py` `strip_text()` | Other UI languages: adjust both prefixes. Keep the unit tests passing (update `tests/test_core.py` only if the text format changes on purpose). |
| 7 | Theme: "dark" when both pixels 12 px left and right of the container (at its vertical centre) have luma < 110, for 3 samples in a row (one every 2 s) | `src/strip_uia.py` `Tracker._loop()` | `check_locator.py` prints both samples. If a sidebar or other panel sits there, move the sample points. |
| 8 | DPI: the process is per-monitor DPI aware. Strip size, font (Segoe UI 12 px semibold), inset and radius are scaled by the window's DPI. **Only tested at 100 %.** | `src/winutil.py` `set_dpi_aware()`, `src/strip_core.py` `place()`, `src/strip_overlay.py` | Watch the guided test at your scaling. Report anything misplaced or clipped. |
| 9 | `tools\install.ps1` and `tools\start.ps1` launch `pythonw` found on PATH (`Get-Command pythonw`); `install.ps1` checks the packages with `python`; `tools\guided_test.ps1` runs `python` for the strip, `strip_state.py` and `summarize_guided.py` | `tools/install.ps1`, `tools/start.ps1`, `tools/guided_test.ps1` | If `pythonw` is missing, or is a different Python from the one that has the packages, use the full path to `pythonw.exe` next to `python -c "import sys; print(sys.executable)"`. |

Rules for adapting:
- Change as little as possible, and only for an assumption that actually failed here.
- Before editing a file, show the user the change and why. Then record it in `install-notes.md` (rule 5).
- After each change, rerun step 4.
- Don't change the colors, sizes or placement rules. They are the design (README.md). If one doesn't work
  here, tell the user and put it in the report instead.
- If you can't make `check_locator.py` say `OK`, stop here. Offer the report (step 10) with what you found.

## Step 6: Try it
Only one strip can run per log-on session, whichever folder it comes from. Check first (read-only):
```
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python' -and $_.CommandLine -like '*src\main.py*' } | Select-Object ProcessId, CommandLine
```
A match whose command line isn't this program (another project's `src\main.py`) can be ignored. If a strip
from a **different** folder is running, tell the user. This folder's copy can't start until that one is
stopped with that folder's own `tools\stop.ps1`. Ask the user before stopping it. **If they say no, skip
the rest of step 6 and step 7**: everything you'd check would be the other copy, not this folder's code.
Write "not run: another copy of the strip was running" for those items in the report, and go to step 9
or 10. Keep the command line out of the report; it contains a path.

**ASK FIRST:** "May I start the strip now? It runs in the background with no console window (`pythonw`),
until you stop it or log off. It does not start at log-in yet. If it hits an error it writes
`%LOCALAPPDATA%\DesktopColorMod\error.log`."
```
powershell -ExecutionPolicy Bypass -File tools\start.ps1
```
`-ExecutionPolicy Bypass` applies only to that one PowerShell process; it does not change any system
setting. `start.ps1` reports which copy is running afterwards: "running from this folder", or "NOT
started" with the reason. **Only if it says "running from this folder"**, check the strip's window
objectively (read-only). `strip_state.py` reads whichever strip is on screen, so after "NOT started" its
output belongs to another copy and proves nothing about this one.
```
python -W ignore tools\strip_state.py try
```
`strip.visible` must be true (`"strip": "no overlay window found"` means no strip window owned by Claude
exists), `ex_transparent` and `ex_noactivate` true, `hit_test.returns_strip` false (click-through),
`foreground.is_strip` false (it never takes focus), and `closest_spec_row` should show `bg_dev` and
`text_dev` of 3 or less. Its output includes the title of the window in front, so keep it out of the
report. Then ask the user whether the strip appears and reads correctly. Ask them to switch to the other
mode (Code / Claude) and look again; if they decline, that mode is "not checked (user declined)".
To stop it at any time:
```
powershell -ExecutionPolicy Bypass -File tools\stop.ps1
```

## Step 7: Guided test (the user runs it)
The guided test is interactive. It asks the user to do things in Claude Desktop and answer y / n / na, so
**the user runs it in their own PowerShell window**, not you. Give them this command:
```
powershell -ExecutionPolicy Bypass -File tools\guided_test.ps1
```
Tell them what it does first: it restarts the strip as a test copy with an event log, walks through 13
short steps (mode switch, typing, resize, move, maximize, covering with another app, minimize, optional
second monitor and theme, click-through, 60 s idle CPU), and after each step reads the strip's own window
(colors, click-through, focus). It takes no full screenshots: it reads only the pixels inside the strip,
in memory. It sends nothing. It writes only to `test-output\guided-<date>\` in this folder (`states.jsonl`
there includes the title of the window in front at each step; `summary.md` leaves titles out), and
restarts the strip at the end if it was running before. It needs `pillow` (step 3). If a strip from a
different folder is running, it stops with a message; see step 6.

When they're done, read `test-output\guided-<date>\summary.md`. A `FAIL` or a "took focus: YES" is a
problem: look at the step, go back to step 5 if it points to an assumption, and rerun. Keep the "Report
lines" section for the report.

## Step 8: Fix what failed (if anything)
Same rules as step 5. Record every change. Rerun the unit tests, `check_locator.py`, and the relevant
guided-test steps (the user reruns the whole guided test; it takes about 5 minutes).

## Step 9: Start at log-in (optional)
First check, read-only, whether a shortcut with this name already exists (e.g. from a copy in another
folder). If it does, tell the user where it points. Installing replaces it, so that other copy would no
longer start at log-in. Also tell the user if this folder is in a temporary location (e.g. under `%TEMP%`):
the shortcut points here and breaks if the folder is cleaned up.
```
$l = Join-Path ([Environment]::GetFolderPath('Startup')) 'Desktop Color Mod Strip.lnk'; if (Test-Path $l) { (New-Object -ComObject WScript.Shell).CreateShortcut($l).Arguments } else { 'no shortcut yet' }
```
**ASK FIRST:** "May I install it to start when you log in? This creates one shortcut,
`Desktop Color Mod Strip.lnk`, in your Startup folder (`%APPDATA%\Microsoft\Windows\Start
Menu\Programs\Startup`), outside this project folder. It needs no admin rights. It also starts the strip
now. `tools\uninstall.ps1` removes it again."
```
powershell -ExecutionPolicy Bypass -File tools\install.ps1
```
The shortcut points at this folder, so tell the user not to move or delete the folder while it's installed
(or uninstall first).

## Step 10: Install report (optional, consent-gated)
Offer once: "Would you like to send an install report to the project? It helps the author see where setup
needed changes. I'll show you the exact text first, and nothing is sent unless you say yes."

If yes, write the draft to `test-output\install-report.md`, using `.github/ISSUE_TEMPLATE/install-report.md`
(everything below its front matter). The title is separate:
`[install report] <Windows product and release, e.g. Windows 10 Home 22H2>, Claude Desktop <version>: <outcome>`.
Pick the first outcome that applies: `failed` (something checked failed and wasn't fixed),
`partly checked` (any check or guided-test step not run), `worked after changes` (all passed, with
changes from step 5/8), `worked` (all passed, nothing changed). **Only these fields:**
- Windows version and build, Claude Desktop version, Python version (and whether it's Store Python),
  display scaling per monitor, monitor count: from step 1. The Claude Desktop version is the `Claude.exe`
  file version that `system_info.py` prints; use it as is. Claude theme: from the user, or from
  `check_locator.py`'s theme samples (step 4).
- Unit test result, `check_locator.py` OK / NOT OK (and which assumption): from step 4.
- Step 6 result: started from this folder or not; the `strip_state.py` checks passed or which failed; what
  the user saw, per mode.
- Which guided-test steps passed / failed / n/a and the idle CPU: copy the "Report lines" from
  `summary.md`, not the notes. If the guided test wasn't run, replace the step list with one line
  "not run (reason)".
- What had to be changed: from `install-notes.md`, described or as a minimal diff. Write "Nothing" if
  `install-notes.md` doesn't exist.
- Anything that wasn't run or checked: write "not run" or "not checked" in its place, with the reason in a
  few words ("user declined", "another copy of the strip was running"). Never leave a field out and never
  guess.

Before showing it, scrub it. Replace any user name, folder path, host name, email, window title, folder or
project name, or other identifier with a placeholder: `%USERPROFILE%`, `%LOCALAPPDATA%`,
`<project folder>`, `<name>`. Paths inside diffs too. No screenshots, logs or command output beyond the
fields above.

**ASK FIRST** (network): **show the user the complete final title and body, exactly as they will be
sent**, and ask: "Send this as a public issue on github.com/pawelpc/claude-mode-strip? This posts it
publicly over the network. (yes / no / edit)". If they ask for edits, apply them and show the whole text
again. Send nothing without an explicit yes to the final text. That yes covers sending this text by one of
the two ways below, nothing else:
- If the GitHub CLI is installed and signed in (ask before checking: `gh auth status` contacts GitHub):
  ```
  gh issue create --repo pawelpc/claude-mode-strip --title "<title>" --body-file test-output\install-report.md
  ```
  This posts under the user's GitHub account. Show them the issue URL it prints.
- Otherwise, build a pre-filled link and give it to the user to open and submit themselves (nothing is sent
  until they click Submit on GitHub):
  ```
  python -c "import sys, urllib.parse as u; b = open(sys.argv[1], encoding='utf-8').read(); print('https://github.com/pawelpc/claude-mode-strip/issues/new?title=' + u.quote(sys.argv[2]) + '&body=' + u.quote(b))" test-output\install-report.md "<title>"
  ```
  Building the link is local; opening it is the user's action.

## Before you finish
Tell the user whether the strip is running and from which folder, and whether it will start at log-in.
If you started it only to try it and they don't want it running, stop it with `tools\stop.ps1`.

## Uninstall
**ASK FIRST:** "May I uninstall? It stops the strip, deletes the Startup shortcut and the
`%LOCALAPPDATA%\DesktopColorMod` log folder."
```
powershell -ExecutionPolicy Bypass -File tools\uninstall.ps1
```
Afterwards the user can delete this folder. The Python packages stay; removing them
(`python -m pip uninstall uiautomation pillow`) is a separate ask, and only if nothing else uses them.

## Updating this folder (optional)
**ASK FIRST** (network): if this folder is a git clone and the user wants the latest version, run
`git pull`. If you changed files in step 5, tell the user first: their changes may conflict, and
`install-notes.md` has the list.
