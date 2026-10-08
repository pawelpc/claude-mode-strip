"""Read-only: check that the strip can find what it needs in Claude Desktop on this machine.

Usage: python tools/check_locator.py
Uses the strip's own discovery code (src/strip_uia.py) once, prints what it found, and ends
with OK or a list of what is missing and where in the code that assumption lives.
Nothing is written anywhere. Output stays on screen; button names can include folder or
project names, so do not paste this output into an install report as-is.
"""
import os, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import winutil as wu
wu.set_dpi_aware()
import uiautomation as auto
import strip_core as core
import strip_uia as su

problems = []
hwnd = wu.find_claude_hwnd()
if not hwnd:
    print("Claude window: NOT FOUND")
    problems.append("src/winutil.py find_claude_hwnd(): expects a visible window titled exactly 'Claude', "
                    "class Chrome_WidgetWin_1, process Claude.exe. Is Claude Desktop open and not minimized?")
else:
    print("Claude window: found; usable (visible, not minimized):", wu.is_usable(hwnd))
    print("Window scaling:", f"{round(wu.dpi_scale(hwnd) * 100)} %")
    win = auto.ControlFromHandle(hwnd)
    lay = None
    for i in range(6):                           # the first UIA read after attaching is often empty
        lay = su.discover(win)
        if lay.mode and lay.box is not None:
            break
        time.sleep(0.5)
    print("Mode radios found:", sorted(lay.radios) or "none")
    print("Mode:", lay.mode)
    print("Input box (ProseMirror edit):", "found" if lay.edit else "NOT FOUND")
    print("Composer container (bg-surface):", su._rect(lay.box) if lay.box else "NOT FOUND")
    print("Buttons in the row below the box:", len(lay.row))
    for _, name in lay.row:
        print("   -", (name or "")[:60])
    print("Model button:", repr(lay.model.Name) if lay.model else "NOT FOUND")
    print("Effort button:", repr(lay.effort.Name) if lay.effort else "none (normal in Cowork mode)")
    if len(lay.radios) < 2 or not lay.mode:
        problems.append("src/strip_uia.py discover(): expects two RadioButtons named 'Claude' and 'Code' "
                        "(English UI), the active one with aria 'checked=true'.")
    if not lay.edit:
        problems.append("src/strip_uia.py discover(): expects an Edit control whose class name contains 'ProseMirror'.")
    elif not lay.box:
        problems.append("src/strip_uia.py discover(): expects a parent of the input (within 8 levels) whose class "
                        "contains 'bg-surface' and that is wider than the input.")
    if lay.box and not lay.model:
        problems.append("src/strip_uia.py discover(): expects a button whose name starts with 'Model:' in the row "
                        "under the box (centre between box bottom - 4 px and box bottom + 70 px).")
    if lay.mode and lay.box:
        box = su._rect(lay.box)
        btns = [(n, su._rect(b)) for b, n in lay.row]
        text = core.strip_text(lay.mode, lay.model.Name if lay.model else None,
                               lay.effort.Name if (lay.effort and lay.mode == "Code") else None)
        placed = core.place(lay.mode, box, btns, wu.window_rect(hwnd), wu.work_area(hwnd),
                            wu.dpi_scale(hwnd), zones=wu.monitors())
        print("Strip text would be:", text)
        print("Strip placement:", placed if placed else "NONE (no valid place; the strip would hide)")
        try:
            cy = (box[1] + box[3]) // 2
            for x in (box[0] - 12, box[2] + 12):
                luma, rgb = wu.pixel_luma(x, cy)
                print(f"Theme sample beside the box: rgb={rgb} luma={luma:.0f} -> {'dark' if luma < 110 else 'light'}")
        except Exception as e:
            print("Theme sample failed:", e)
print()
if problems:
    print("NOT OK. Assumptions that did not hold on this machine:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("OK: the strip can find everything it needs.")
