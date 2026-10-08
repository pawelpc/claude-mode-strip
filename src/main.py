"""Desktop_Color_Mod indicator strip.

Run (console):    python src\\main.py [--log events.jsonl]
Run (no console): pythonw src\\main.py
Only one copy runs at a time (a second start exits at once). Ctrl+C quits a console run.
Errors go to %LOCALAPPDATA%\\DesktopColorMod\\error.log (pythonw has no console).
"""
import ctypes, os, sys, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import winutil
winutil.set_dpi_aware()

log_error = winutil.log_error


def single_instance():
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    h = k32.CreateMutexW(None, False, "Local\\DesktopColorModStrip")
    if k32.GetLastError() == 183:                                          # ERROR_ALREADY_EXISTS
        return None
    return h                                                               # keep alive for the process lifetime


def main():
    mutex = single_instance()
    if mutex is None:
        return
    from strip_uia import Tracker
    from strip_overlay import Overlay
    logpath = sys.argv[sys.argv.index("--log") + 1] if "--log" in sys.argv else None
    tr = Tracker(); tr.start()
    ov = Overlay(tr, logpath)
    try:
        ov.run()
    except KeyboardInterrupt:
        pass
    finally:
        tr.stop_flag = True


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log_error(traceback.format_exc())
        raise
