"""Read-only state check of the running strip. Prints one JSON object.

Finds the overlay (window class DesktopColorModStrip, OWNED by Claude's window), then reports:
rect, owner==Claude, ex-style bits (transparent/noactivate/layered), foreground window,
hit-test at the strip centre (WindowFromPoint must NOT return the strip), sampled colors
(background = most common pixel, text = pixel farthest from it) and deviation from the spec.
Usage: python tools/strip_state.py [label]
"""
import ctypes, ctypes.wintypes as wt, json, os, sys, time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import winutil as wu
wu.set_dpi_aware()
import strip_core as core

u = ctypes.windll.user32
g = ctypes.windll.gdi32
VP = ctypes.c_void_p
u.GetWindow.argtypes = [VP, ctypes.c_uint]; u.GetWindow.restype = VP
u.GetForegroundWindow.restype = VP
u.WindowFromPoint.argtypes = [wt.POINT]; u.WindowFromPoint.restype = VP
u.GetAncestor.argtypes = [VP, ctypes.c_uint]; u.GetAncestor.restype = VP
u.GetWindowLongPtrW.argtypes = [VP, ctypes.c_int]; u.GetWindowLongPtrW.restype = VP
u.GetWindowRect.argtypes = [VP, ctypes.POINTER(wt.RECT)]
u.IsWindowVisible.argtypes = [VP]
u.GetClassNameW.argtypes = [VP, ctypes.c_wchar_p, ctypes.c_int]
u.GetWindowTextW.argtypes = [VP, ctypes.c_wchar_p, ctypes.c_int]


def title(h):
    b = ctypes.create_unicode_buffer(120); u.GetWindowTextW(h, b, 120); return b.value


def find_overlay(claude):
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(64); u.GetClassNameW(h, b, 64)
        if b.value == "DesktopColorModStrip" and u.GetWindow(h, 4) == claude:      # GW_OWNER
            out.append(h)
        return True
    u.EnumWindows(cb, 0)
    return out[0] if out else None


def sample(rect):
    from PIL import ImageGrab
    im = ImageGrab.grab(bbox=(rect[0] + 3, rect[1] + 1, rect[2] - 3, rect[3] - 1), all_screens=True).convert("RGB")
    return list(im.getdata())


def main():
    st = {"label": sys.argv[1] if len(sys.argv) > 1 else "", "t": round(time.time(), 3)}
    claude = wu.find_claude_hwnd()
    st["claude"] = bool(claude)
    if not claude:
        st["strip"] = None; print(json.dumps(st)); return
    st["claude_rect"] = wu.window_rect(claude)
    ov = find_overlay(claude)
    fg = u.GetForegroundWindow()
    st["foreground"] = {"hwnd": fg, "title": title(fg)[:60], "is_claude": fg == claude}
    if not ov:
        st["strip"] = "no overlay window found"; print(json.dumps(st)); return
    st["foreground"]["is_strip"] = (fg == ov)
    r = wt.RECT(); u.GetWindowRect(ov, ctypes.byref(r))
    rect = (r.left, r.top, r.right, r.bottom)
    ex = int(u.GetWindowLongPtrW(ov, -20) or 0)
    st["strip"] = {"visible": bool(u.IsWindowVisible(ov)), "rect": rect, "owner_is_claude": True,
                   "ex_transparent": bool(ex & 0x20), "ex_noactivate": bool(ex & 0x08000000), "ex_layered": bool(ex & 0x80000)}
    if st["strip"]["visible"]:
        cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        hit = u.WindowFromPoint(wt.POINT(cx, cy))
        st["strip"]["hit_test"] = {"point": [cx, cy], "returns_strip": u.GetAncestor(hit, 2) == ov if hit else None,
                                   "returns_claude": (u.GetAncestor(hit, 2) == claude) if hit else None,
                                   "hit_title": title(u.GetAncestor(hit, 2) or hit)[:50] if hit else None}
        px = sample(rect)
        bg = Counter(px).most_common(1)[0][0]
        tx = max(px, key=lambda p: sum((a - b) ** 2 for a, b in zip(p, bg)))
        st["strip"]["bg_rgb"] = bg; st["strip"]["text_rgb"] = tx
        hexs = lambda c: "#%02X%02X%02X" % c
        st["strip"]["bg_hex"] = hexs(bg); st["strip"]["text_hex_extreme_pixel"] = hexs(tx)
        match = []
        for (mode, theme), (sbg, sfg) in core.COLORS.items():
            dbg = max(abs(a - b) for a, b in zip(bg, core.hex_rgb(sbg)))
            dfg = max(abs(a - b) for a, b in zip(tx, core.hex_rgb(sfg)))
            match.append({"row": f"{mode}/{theme}", "bg_dev": dbg, "text_dev": dfg})
        best = min(match, key=lambda m: m["bg_dev"])
        st["strip"]["closest_spec_row"] = best
    print(json.dumps(st))


main()
