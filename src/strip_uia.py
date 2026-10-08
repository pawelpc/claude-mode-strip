"""Tracker thread: read-only UI Automation of Claude Desktop -> latest reading.

Discovery (slow, ~0.3-0.5 s) walks the tree once and caches element handles.
Each tick then re-reads cached rects only (~0.3 ms). Rediscovery happens when a read
fails, a rect is implausible, or the mode changes. UIA transients (mode None, empty row,
off-window box) are held over, never shown.
"""
import threading, time
import uiautomation as auto
import strip_core as core
import winutil as wu

TICK = 0.05
LABEL_EVERY = 0.25      # model / effort / row re-read period
MODE_EVERY = 0.1        # mode radio re-read period (cached handles, ~0.3 ms)
THEME_EVERY = 2.0
HOLD_BAD_S = 1.0        # keep last good placement this long through bad reads, then hide


def _aria(c):
    try:
        return c.GetPropertyValue(auto.PropertyId.AriaPropertiesProperty) or ""
    except Exception:
        return ""


def _rect(c):
    r = c.BoundingRectangle
    return (r.left, r.top, r.right, r.bottom)


class Layout:
    """Cached handles from one discovery pass."""
    def __init__(self):
        self.edit = self.box = self.model = self.effort = None
        self.radios = {}            # 'Claude' / 'Code' -> control
        self.row = []               # [(control, name)]
        self.mode = None


_IA = None


def _ia():
    global _IA
    if _IA is None:
        import uiautomation.uiautomation as U
        _IA = U._AutomationClient.instance().IUIAutomation
    return _IA


def _find_all(win, type_id):
    """Server-side search: one UIA call per control type (~25 ms) instead of walking the tree (~300 ms)."""
    ia = _ia()
    arr = win.Element.FindAll(4, ia.CreatePropertyCondition(30003, type_id))   # TreeScope_Descendants
    return [arr.GetElement(i) for i in range(arr.Length)]


def _erect(e):
    r = e.CurrentBoundingRectangle
    return (r.left, r.top, r.right, r.bottom)


def discover(win):
    lay = Layout()
    ctl = auto.Control.CreateControlFromElement
    for e in _find_all(win, 50013):                              # RadioButton
        try:
            if e.CurrentName in ("Claude", "Code"):
                lay.radios[e.CurrentName] = ctl(e)
        except Exception:
            pass
    for r in lay.radios.values():
        if "checked=true" in _aria(r):
            lay.mode = "Cowork" if r.Name == "Claude" else "Code"
    ed = []
    for e in _find_all(win, 50004):                              # Edit
        try:
            if "ProseMirror" in (e.CurrentClassName or ""):
                r = _erect(e)
                if r[2] > r[0] and r[3] > r[1]:
                    c = ctl(e)
                    if "hidden=true" not in _aria(c):
                        ed.append((r, c))
        except Exception:
            pass
    if not ed:
        return lay
    er, lay.edit = max(ed, key=lambda t: t[0][1])
    p = lay.edit
    for _ in range(8):
        p = p.GetParentControl()
        if p is None:
            break
        r = _rect(p)
        if "bg-surface" in (p.ClassName or "") and r[2] - r[0] > er[2] - er[0]:
            lay.box = p
            break
    if lay.box is None:
        return lay
    br = _rect(lay.box)
    for e in _find_all(win, 50000):                              # Button
        try:
            r = _erect(e)
            if r[2] <= r[0] or r[3] <= r[1]:
                continue
            cy = (r[1] + r[3]) / 2
            if br[3] - 4 <= cy <= br[3] + 70 and r[0] >= br[0] - 24 and r[2] <= br[2] + 24:
                b = ctl(e)
                if "hidden=true" in _aria(b):
                    continue
                name = e.CurrentName
                lay.row.append((b, name))
                if name.startswith("Model:"):
                    lay.model = b
                elif name.startswith("Effort:"):
                    lay.effort = b
        except Exception:
            pass
    return lay


class Tracker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.lock = threading.Lock()
        self.reading = {"visible": False}
        self.stop_flag = False
        self.theme = "light"
        self._theme_votes = []
        self.debug = []            # discovery attempts, drained by the overlay's logger

    def get(self):
        with self.lock:
            return dict(self.reading)

    def _set(self, rd):
        with self.lock:
            self.reading = rd

    def run(self):
        import traceback
        while not self.stop_flag:
            try:
                with auto.UIAutomationInitializerInThread():
                    self._loop()
                return
            except Exception:
                # never die silently: hide the strip, log, and start over
                self._set({"visible": False, "why": "tracker error"})
                wu.log_error("tracker restarted after:" + chr(10) + traceback.format_exc())
                time.sleep(1.0)

    def _text(self, lay):
        ml = lay.model.Name if lay.model else None
        ef = lay.effort.Name if (lay.effort and lay.mode == "Code") else None
        t = core.strip_text(lay.mode, ml, ef)
        now = time.time()
        if t.endswith("model ?"):
            # transient unreadable label: hold the last good text for the same mode briefly (never guess beyond that)
            g = getattr(self, "_good", None)
            if g and g[0] == lay.mode and now - g[2] < 1.5:
                return g[1]
        else:
            self._good = (lay.mode, t, now)
        return t

    def _loop(self):
        hwnd = None; win = None; lay = None
        last_good = None; last_good_t = 0         # last good reading (dict) and its time
        bad_since = None
        by_mode = {}                              # mode -> last good reading (for the instant mode switch)
        switch_to = None; last_seen = None; was_gone = False; last_mode = None
        t_mode = t_label = t_theme = t_btn = t_disc = 0
        last_box = last_win = None; btns = []
        text = "?"
        while not self.stop_flag:
            now = time.time()
            if hwnd is None or not wu.is_usable(hwnd):
                hwnd = wu.find_claude_hwnd(); win = lay = None; last_good = None; was_gone = True
                if hwnd is None or not wu.is_usable(hwnd):
                    hwnd = None
                    self._set({"visible": False, "why": "no window"})
                    time.sleep(0.2); continue
            if win is None:
                win = auto.ControlFromHandle(hwnd)
            winr = wu.window_rect(hwnd)
            if winr is None:
                time.sleep(TICK); continue
            if was_gone:
                # window is back (restored from minimize / tray). Its UI tree can take seconds to become readable,
                # so show the last-known placement now with the model as '...', then verify.
                was_gone = False
                g = by_mode.get(last_mode)
                if g and g["win"] == winr:
                    self._set(dict(g, text=core.pending_text(last_mode), t_detect=time.time()))
            need = lay is None and now - t_disc >= 0.1
            if lay is not None:
                if now - t_mode >= MODE_EVERY:
                    t_mode = now
                    try:
                        cur = None
                        for nm, rc in lay.radios.items():
                            if "checked=true" in _aria(rc):
                                cur = "Cowork" if nm == "Claude" else "Code"
                        if cur is not None and cur != lay.mode:      # None = UIA transient: ignore
                            need = True; switch_to = cur
                            self.debug.append({"ev": "mode_seen", "t": round(time.time(), 3), "from": lay.mode, "to": cur})
                    except Exception:
                        need = True
                if not need and now - t_label >= LABEL_EVERY:
                    t_label = now
                    try:
                        text = self._text(lay)
                        if text.endswith("model ?") and now - t_disc >= 0.5:
                            need = True                              # model button missed or unreadable: look again
                    except Exception:
                        need = True
            if need and switch_to:
                # Claude needs ~1.3 s before its new UI tree is readable. Show the new mode now, from that mode's
                # last-known placement (only if the window hasn't moved/resized since), with the model as '…'.
                g = by_mode.get(switch_to)
                if g and g["win"] == winr:
                    self._set(dict(g, mode=switch_to, text=core.pending_text(switch_to), t_detect=time.time()))
                else:
                    self._set({"visible": False, "why": "mode switching"})
                last_good = None; switch_to = None
            if need:
                t_disc = time.time()
                try:
                    lay = discover(win)
                except Exception:
                    lay = None
                self.debug.append({"ev": "disc", "t": round(time.time(), 3), "ms": round((time.time() - t_disc) * 1000),
                                   "mode": getattr(lay, "mode", None), "box": bool(getattr(lay, "box", None)),
                                   "row": len(getattr(lay, "row", []) or []), "model": bool(getattr(lay, "model", None))})
                if lay is not None and lay.mode and lay.box is not None:
                    try:
                        text = self._text(lay)
                    except Exception:
                        pass
                    t_label = t_mode = time.time(); t_btn = 0
                else:
                    lay = None
                    if now - last_good_t >= HOLD_BAD_S:
                        last_good = None
                        self._set({"visible": False, "why": "no layout"})
                    time.sleep(0.05); continue
            if lay is None:
                time.sleep(TICK); continue
            box = None
            try:
                box = _rect(lay.box)
                if box[2] > box[0]:
                    # buttons only move with the box/window or when labels change: re-read then, else reuse
                    if need or box != last_box or winr != last_win or now - t_btn >= LABEL_EVERY:
                        btns = [(n, _rect(b)) for b, n in lay.row]
                        btns = [(n, r) for n, r in btns if r[2] > r[0] and r[3] > r[1]]
                        t_btn = now
                    last_box, last_win = box, winr
            except Exception:
                box = None
            bw, bh = (box[2] - box[0], box[3] - box[1]) if box else (0, 0)
            plausible = bool(box) and (bw >= 200 and 20 <= bh <= 500 and box[0] >= winr[0] - 2 and box[2] <= winr[2] + 2
                                       and box[1] >= winr[1] and box[3] <= winr[3] + 2)
            if not plausible:
                # UIA transient (zero rect, box lagging a moving window). Hold; never drop the layout quickly.
                bad_since = bad_since or now
                if last_good and (last_good["win"][2] - last_good["win"][0], last_good["win"][3] - last_good["win"][1]) ==                         (winr[2] - winr[0], winr[3] - winr[1]) and now - last_good_t < HOLD_BAD_S:
                    dx, dy = winr[0] - last_good["win"][0], winr[1] - last_good["win"][1]     # pure window move: follow it
                    r = last_good["rect"]
                    moved = dict(last_good, rect=(r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy),
                                 box=(last_good["box"][0] + dx, last_good["box"][1] + dy,
                                      last_good["box"][2] + dx, last_good["box"][3] + dy), win=winr, t_detect=time.time())
                    if core._in_work(moved["rect"], wu.monitors()):
                        self._set(moved)
                elif now - last_good_t > HOLD_BAD_S:
                    last_good = None
                    self._set({"visible": False, "why": "implausible box"})
                if now - bad_since > 1.5 and now - t_disc >= 0.5:
                    lay = None                                       # stuck: rediscover
                time.sleep(0.02); continue
            bad_since = None
            if (box, winr) != last_seen:
                last_seen = (box, winr)
                self.debug.append({"ev": "seen", "t": round(time.time(), 3), "box": box, "win": winr})
            work = wu.work_area(hwnd)
            scale = wu.dpi_scale(hwnd)
            placed = core.place(lay.mode, box, btns, winr, work, scale, zones=wu.monitors())
            if now - t_theme >= THEME_EVERY:
                t_theme = now
                try:
                    pts = [(box[0] - 12, (box[1] + box[3]) // 2), (box[2] + 12, (box[1] + box[3]) // 2)]
                    samples = [(p, wu.pixel_luma(*p)) for p in pts]
                    self.theme_dbg = [(p, rgb) for p, (l, rgb) in samples]
                    lumas = [l for p, (l, rgb) in samples]
                    v = "dark" if sum(1 for l in lumas if l < 110) == len(lumas) else "light"
                    self._theme_votes = (self._theme_votes + [v])[-3:]
                    if len(self._theme_votes) == 3 and len(set(self._theme_votes)) == 1:
                        self.theme = v
                except Exception:
                    pass
            if placed is None:
                if now - last_good_t > HOLD_BAD_S:
                    last_good = None
                    self._set({"visible": False, "why": "no valid placement"})
                time.sleep(0.02); continue
            rect, pos = placed
            rd = {"visible": True, "rect": rect, "pos": pos, "mode": lay.mode, "text": text,
                  "theme": self.theme, "hwnd": hwnd, "scale": scale, "box": box, "win": winr,
                  "t_detect": time.time(), "theme_dbg": getattr(self, "theme_dbg", None)}
            self._set(rd)
            by_mode[lay.mode] = rd; last_mode = lay.mode
            last_good = rd; last_good_t = now
            time.sleep(TICK)
