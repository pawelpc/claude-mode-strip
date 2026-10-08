"""Read-only: print the machine facts an install report may contain, and nothing else.

Usage: python tools/system_info.py
Standard library only (runs before any package is installed). Prints no user name, path,
host name or other identifier: only versions, display scaling and monitor count.
"""
import ctypes, ctypes.wintypes as wt, json, os, platform, sys, winreg

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import winutil as wu
wu.set_dpi_aware()


def windows():
    k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")

    def q(name):
        try:
            return winreg.QueryValueEx(k, name)[0]
        except OSError:
            return None
    build = int(q("CurrentBuild") or 0)
    product = q("ProductName") or "Windows"
    if build >= 22000:                       # Windows 11 still reports "Windows 10" in ProductName
        product = product.replace("Windows 10", "Windows 11")
    return {"product": product, "release": q("DisplayVersion") or q("ReleaseId"),
            "build": f"{build}.{q('UBR')}" if q("UBR") is not None else str(build)}


def file_version(path):
    v = ctypes.windll.version
    n = v.GetFileVersionInfoSizeW(path, None)
    if not n:
        return None
    buf = ctypes.create_string_buffer(n)
    if not v.GetFileVersionInfoW(path, 0, n, buf):
        return None
    p = ctypes.c_void_p(); ln = wt.UINT()
    if not v.VerQueryValueW(buf, "\\", ctypes.byref(p), ctypes.byref(ln)):
        return None
    ms, ls = ctypes.cast(p, ctypes.POINTER(wt.DWORD * 4)).contents[2:4]
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"


def claude():
    h = wu.find_claude_hwnd()
    if not h:
        return {"running": False}
    pid = wt.DWORD(); wu.user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    k32 = ctypes.windll.kernel32
    hp = k32.OpenProcess(0x1000, False, pid.value)
    path = None
    if hp:
        try:
            buf = ctypes.create_unicode_buffer(520); n = wt.DWORD(520)
            if k32.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(n)):
                path = buf.value
        finally:
            k32.CloseHandle(hp)
    return {"running": True, "version": file_version(path) if path else None,
            "window_scaling_percent": round(wu.dpi_scale(h) * 100)}


def monitor_scaling():
    """Scaling percent of every monitor (GetDpiForMonitor, Windows 8.1+)."""
    out = []
    try:
        sh = ctypes.windll.shcore
    except OSError:
        return out

    @ctypes.WINFUNCTYPE(wt.BOOL, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wt.RECT), wt.LPARAM)
    def cb(hm, hdc, lprc, lp):
        x, y = wt.UINT(), wt.UINT()
        if sh.GetDpiForMonitor(ctypes.c_void_p(hm), 0, ctypes.byref(x), ctypes.byref(y)) == 0:
            out.append(round(x.value * 100 / 96))
        return True
    wu.user32.EnumDisplayMonitors(None, None, cb, 0)
    return out


info = {
    "windows": windows(),
    "python": {"version": platform.python_version(), "bits": 64 if sys.maxsize > 2 ** 32 else 32,
               "microsoft_store": "WindowsApps" in sys.executable},
    "claude_desktop": claude(),
    "monitors": {"count": len(wu.monitors()), "scaling_percent": monitor_scaling()},
}
print(json.dumps(info, indent=2))
