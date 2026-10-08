"""Small ctypes helpers (read-only window queries). Windows 10 safe."""
import ctypes, ctypes.wintypes as wt, os

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]


LOGDIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "DesktopColorMod")


def log_error(text):
    """Append to %LOCALAPPDATA%\DesktopColorMod\error.log (pythonw has no console). Never raises."""
    import time
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        path = os.path.join(LOGDIR, "error.log")
        if os.path.exists(path) and os.path.getsize(path) > 200000:
            os.replace(path, path + ".old")
        with open(path, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + text + chr(10))
    except Exception:
        pass


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # per-monitor (Win 8.1+)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def _exe(pid):
    h = kernel32.OpenProcess(0x1000, False, pid)           # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520); n = wt.DWORD(520)
        kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n))
        return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(h)


_exe_cache = {}


def find_claude_hwnd():
    """Visible top-level window titled exactly 'Claude', class Chrome_WidgetWin_1, process Claude.exe."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        if not user32.IsWindowVisible(h):
            return True
        b = ctypes.create_unicode_buffer(64); user32.GetClassNameW(h, b, 64)
        if b.value != "Chrome_WidgetWin_1":
            return True
        t = ctypes.create_unicode_buffer(64); user32.GetWindowTextW(h, t, 64)
        if t.value != "Claude":
            return True
        pid = wt.DWORD(); user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value not in _exe_cache:
            _exe_cache[pid.value] = _exe(pid.value)
        if _exe_cache[pid.value] == "claude.exe":
            found.append(h)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def window_rect(hwnd):
    r = wt.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return (r.left, r.top, r.right, r.bottom)


def work_area(hwnd):
    class MI(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("rc", wt.RECT), ("wk", wt.RECT), ("fl", wt.DWORD)]
    mi = MI(); mi.cb = ctypes.sizeof(MI)
    hm = user32.MonitorFromWindow(hwnd, 2)                 # MONITOR_DEFAULTTONEAREST
    user32.GetMonitorInfoW(hm, ctypes.byref(mi))
    return (mi.wk.left, mi.wk.top, mi.wk.right, mi.wk.bottom)


def monitors():
    """[(monitor_rect, work_rect)] for every monitor."""
    class MI(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("rc", wt.RECT), ("wk", wt.RECT), ("fl", wt.DWORD)]
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wt.RECT), wt.LPARAM)
    def cb(hm, hdc, lprc, lp):
        mi = MI(); mi.cb = ctypes.sizeof(MI)
        if user32.GetMonitorInfoW(hm, ctypes.byref(mi)):
            out.append(((mi.rc.left, mi.rc.top, mi.rc.right, mi.rc.bottom),
                        (mi.wk.left, mi.wk.top, mi.wk.right, mi.wk.bottom)))
        return True

    user32.EnumDisplayMonitors(None, None, cb, 0)
    return out


def is_usable(hwnd):
    return bool(user32.IsWindow(hwnd)) and bool(user32.IsWindowVisible(hwnd)) and not user32.IsIconic(hwnd)


def dpi_scale(hwnd):
    try:
        return user32.GetDpiForWindow(hwnd) / 96.0
    except Exception:
        return 1.0


def pixel_luma(x, y):
    """Luma (0-255) and RGB of one screen pixel via GDI GetPixel (virtual-desktop coords). Read-only."""
    gdi32 = ctypes.windll.gdi32
    user32.GetDC.restype = ctypes.c_void_p
    gdi32.GetPixel.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    hdc = user32.GetDC(None)
    try:
        c = gdi32.GetPixel(hdc, x, y)
    finally:
        user32.ReleaseDC(None, hdc)
    if c in (-1, 0xFFFFFFFF):
        raise OSError("GetPixel failed")
    r, g, b = c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF
    return 0.299 * r + 0.587 * g + 0.114 * b, (r, g, b)
