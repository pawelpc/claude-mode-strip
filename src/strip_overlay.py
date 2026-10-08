"""Overlay window: opaque, click-through, never-activating, OWNED by Claude's window (native Win32).

Owned popup = z-order stays directly above its owner (other apps' windows cover it), it is
hidden when the owner is minimized, and it never takes focus (WS_EX_NOACTIVATE +
SW_SHOWNOACTIVATE + SWP_NOACTIVATE; WS_EX_TRANSPARENT makes mouse input fall through).
No injection or hooks into Claude: it reads UIA/rects and draws its own window.
"""
import ctypes, ctypes.wintypes as wt, json, time
import strip_core as core

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32
VP = ctypes.c_void_p

WS_POPUP = 0x80000000
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x80, 0x08000000, 0x80000, 0x20
SWP_NOZORDER, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x4, 0x10, 0x40
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
WM_PAINT, WM_DESTROY, WM_ERASEBKGND, WM_MOUSEACTIVATE, WM_NCHITTEST = 0x0F, 0x02, 0x14, 0x21, 0x84
MA_NOACTIVATE, HTTRANSPARENT = 3, -1
TRANSPARENT_BK = 1
DT_LEFT, DT_VCENTER, DT_SINGLELINE, DT_NOPREFIX, DT_END_ELLIPSIS = 0x0, 0x4, 0x20, 0x800, 0x8000
FW_SEMIBOLD = 600
PM_REMOVE = 1

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, VP, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", VP), ("hIcon", VP), ("hCursor", VP),
                ("hbrBackground", VP), ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [("hdc", VP), ("fErase", wt.BOOL), ("rcPaint", wt.RECT), ("fRestore", wt.BOOL),
                ("fIncUpdate", wt.BOOL), ("rgbReserved", ctypes.c_byte * 32)]


user32.DefWindowProcW.argtypes = [VP, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.argtypes = [ctypes.c_uint, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_uint, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, VP, VP, VP, VP]
user32.CreateWindowExW.restype = VP
user32.SetWindowPos.argtypes = [VP, VP, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.ShowWindow.argtypes = [VP, ctypes.c_int]
user32.SetLayeredWindowAttributes.argtypes = [VP, ctypes.c_uint, ctypes.c_ubyte, ctypes.c_uint]
user32.SetWindowRgn.argtypes = [VP, VP, wt.BOOL]
user32.InvalidateRect.argtypes = [VP, VP, wt.BOOL]
user32.BeginPaint.argtypes = [VP, ctypes.POINTER(PAINTSTRUCT)]; user32.BeginPaint.restype = VP
user32.EndPaint.argtypes = [VP, ctypes.POINTER(PAINTSTRUCT)]
user32.GetClientRect.argtypes = [VP, ctypes.POINTER(wt.RECT)]
user32.FillRect.argtypes = [VP, ctypes.POINTER(wt.RECT), VP]
user32.DrawTextW.argtypes = [VP, wt.LPCWSTR, ctypes.c_int, ctypes.POINTER(wt.RECT), ctypes.c_uint]
user32.PeekMessageW.argtypes = [ctypes.POINTER(wt.MSG), VP, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DestroyWindow.argtypes = [VP]
kernel32.GetModuleHandleW.restype = VP
gdi32.CreateRoundRectRgn.restype = VP
gdi32.CreateSolidBrush.restype = VP
gdi32.CreateSolidBrush.argtypes = [ctypes.c_uint]
gdi32.CreateFontW.restype = VP
gdi32.SelectObject.argtypes = [VP, VP]; gdi32.SelectObject.restype = VP
gdi32.SetTextColor.argtypes = [VP, ctypes.c_uint]
gdi32.SetBkMode.argtypes = [VP, ctypes.c_int]
gdi32.DeleteObject.argtypes = [VP]


def colorref(hexs):
    r, g, b = core.hex_rgb(hexs)
    return r | (g << 8) | (b << 16)


class Overlay:
    CLASS = "DesktopColorModStrip"

    def __init__(self, tracker, logpath=None):
        self.tracker = tracker
        self.hwnd = None
        self.owner = None
        self.shown = False
        self.cur = None            # last applied (rect, text, mode, theme)
        self.bg = self.fg = 0
        self.text = ""
        self.inset = 8
        self.font = None
        self.font_px = None
        self.log = open(logpath, "a", encoding="utf-8") if logpath else None
        self._proc = WNDPROC(self._wndproc)       # keep a reference
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._proc
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = self.CLASS
        wc.hbrBackground = None
        user32.RegisterClassW(ctypes.byref(wc))
        self.hinst = wc.hInstance
        self._stop = False

    # -- window -----------------------------------------------------------
    def _create(self, owner_hwnd):
        ex = WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_LAYERED | WS_EX_TRANSPARENT
        self.hwnd = user32.CreateWindowExW(ex, self.CLASS, "Desktop Color Mod strip", WS_POPUP, 0, 0, 10, 10,
                                           owner_hwnd, None, self.hinst, None)
        if not self.hwnd:
            raise OSError("CreateWindowEx failed")
        user32.SetLayeredWindowAttributes(self.hwnd, 0, 255, 2)     # LWA_ALPHA 255: opaque, enables click-through
        self.owner = owner_hwnd

    def _wndproc(self, hwnd, msg, wp, lp):
        if msg == WM_NCHITTEST:
            return HTTRANSPARENT
        if msg == WM_MOUSEACTIVATE:
            return MA_NOACTIVATE
        if msg == WM_ERASEBKGND:
            return 1
        if msg == WM_PAINT:
            ps = PAINTSTRUCT()
            hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
            rc = wt.RECT(); user32.GetClientRect(hwnd, ctypes.byref(rc))
            br = gdi32.CreateSolidBrush(self.bg)
            user32.FillRect(hdc, ctypes.byref(rc), br)
            gdi32.DeleteObject(br)
            if self.font:
                old = gdi32.SelectObject(hdc, self.font)
                gdi32.SetBkMode(hdc, TRANSPARENT_BK)
                gdi32.SetTextColor(hdc, self.fg)
                rc.left += self.inset; rc.right -= self.inset
                user32.DrawTextW(hdc, self.text, -1, ctypes.byref(rc),
                                 DT_LEFT | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX | DT_END_ELLIPSIS)
                gdi32.SelectObject(hdc, old)
            user32.EndPaint(hwnd, ctypes.byref(ps))
            return 0
        return user32.DefWindowProcW(hwnd, msg, wp, lp)

    def _logrec(self, **k):
        if self.log:
            k["t"] = round(time.time(), 3)
            self.log.write(json.dumps(k) + "\n"); self.log.flush()

    def hide(self, why=""):
        if self.shown:
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self.shown = False; self.cur = None
            self._logrec(ev="hide", why=why)

    def _apply(self, rd):
        if self.hwnd is None or rd["hwnd"] != self.owner:
            if self.hwnd:
                user32.DestroyWindow(self.hwnd)
            self._create(rd["hwnd"])
        x0, y0, x1, y1 = rd["rect"]
        w, h = x1 - x0, y1 - y0
        key = (rd["rect"], rd["text"], rd["mode"], rd["theme"])
        if key == self.cur and self.shown:
            return
        bgh, fgh = core.colors_for(rd["mode"], rd["theme"])
        self.bg, self.fg = colorref(bgh), colorref(fgh)
        scale = rd["scale"]
        px = round(12 * scale)
        if self.font_px != px:
            if self.font:
                gdi32.DeleteObject(self.font)
            self.font = gdi32.CreateFontW(-px, 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI")  # CLEARTYPE
            self.font_px = px
        self.inset = round(core.INSET * scale)
        self.text = rd["text"]
        rect_changed = self.cur is None or self.cur[0] != rd["rect"]
        user32.SetWindowPos(self.hwnd, None, x0, y0, w, h, SWP_NOZORDER | SWP_NOACTIVATE)
        if rect_changed:
            r = round(core.RADIUS * scale)
            rgn = gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, 2 * r, 2 * r)
            user32.SetWindowRgn(self.hwnd, rgn, True)       # the system owns the region after this call
        if not self.shown:
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.InvalidateRect(self.hwnd, None, False)
        self.shown = True; self.cur = key
        self._logrec(ev="apply", rect=rd["rect"], pos=rd["pos"], mode=rd["mode"], text=rd["text"],
                     theme=rd["theme"], t_detect=round(rd["t_detect"], 3), box=rd["box"], win=rd["win"],
                     theme_dbg=rd.get("theme_dbg"))

    def tick(self):
        while self.tracker.debug:
            d = self.tracker.debug.pop(0)
            if self.log:
                self.log.write(json.dumps(d) + chr(10)); self.log.flush()
        rd = self.tracker.get()
        if rd.get("visible"):
            try:
                self._apply(rd)
            except Exception as ex:
                self._logrec(ev="error", err=repr(ex))
        else:
            self.hide(rd.get("why", ""))

    def run(self):
        msg = wt.MSG()
        while not self._stop:
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg)); user32.DispatchMessageW(ctypes.byref(msg))
            self.tick()
            time.sleep(0.02)
