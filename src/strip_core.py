"""Pure logic for the indicator strip: colors, text, placement. No Windows calls.

All visual values come from the design spec (rev 2; the colors are listed in README.md). Rects are
(left, top, right, bottom) in physical screen pixels.
"""

HEIGHT = 18          # spec: height 18 px
RADIUS = 4           # spec: corner radius 4 px
INSET = 8            # spec: text inset 8 px
CLEARANCE = 8        # spec: clearance from neighbouring buttons
FALLBACK_GAP = 2     # spec: 2 px above the input box
MIN_GAP = 160        # spec: below this gap width, use position 2

# (mode, theme) -> (background, text)
COLORS = {
    ("Code", "light"): ("#BFD9F7", "#0B3D73"),
    ("Cowork", "light"): ("#F7D9A0", "#5C3A00"),
    ("Code", "dark"): ("#1E3A5F", "#DCEBFF"),
    ("Cowork", "dark"): ("#5A3D0A", "#FFE9C2"),
}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(hex_rgb(a)), luminance(hex_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def colors_for(mode, theme):
    return COLORS[(mode, theme if theme in ("light", "dark") else "light")]


def strip_text(mode, model_label, effort_label=None):
    """`<Mode> · <model text>`; model_label is the button name (with or without 'Model: ').

    Code mode shows the effort in its own button; append it (design decision) unless
    the model label already ends with it (Cowork's model button includes the effort).
    """
    model = None
    if model_label:
        model = model_label[len("Model: "):] if model_label.startswith("Model: ") else model_label
        model = model.strip() or None
    if not model:
        return f"{mode} · model ?"
    if effort_label:
        eff = effort_label[len("Effort: "):] if effort_label.startswith("Effort: ") else effort_label
        eff = eff.strip()
        if eff and not model.endswith(eff):
            model = f"{model} {eff}"
    return f"{mode} · {model}"


def pending_text(mode):
    """Shown for ~1 s after a mode switch while Claude's UI tree is unreadable (design decision)."""
    return f"{mode} · …"


def split_row(buttons):
    """buttons: list of (name, rect). Split at the widest horizontal gap.

    Returns (left_anchor_rect, right_anchor_rect, gap_px) or None. By position only.
    """
    row = sorted(buttons, key=lambda b: b[1][0])
    if len(row) < 2:
        return None
    gaps = [(row[i + 1][1][0] - row[i][1][2], i) for i in range(len(row) - 1)]
    gw, gi = max(gaps)
    return row[gi][1], row[gi + 1][1], gw


def _inter(a, b):
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))


def place(mode, box, buttons, win, work, scale=1.0, zones=None):
    """Return (rect, position) or None if no valid placement exists.

    mode: 'Code' | 'Cowork'. box: input-box rect. buttons: [(name, rect)] of the row
    below the box. win: window rect. work: work-area rect (taskbar excluded) of the window's monitor.
    zones: optional [(monitor_rect, work_rect)] for ALL monitors; when given it replaces `work`, so a window
    straddling two monitors is judged per monitor (the strip may sit on either, never inside a taskbar band).
    The strip is clamped inside the window and must not overlap the box or buttons.
    """
    h = round(HEIGHT * scale)
    clr = round(CLEARANCE * scale)
    limit = _inter(win, work) if zones is None else win
    cand = []
    if mode == "Code":
        sp = split_row(buttons)
        if sp and sp[2] >= round(MIN_GAP * scale):
            la, ra, gap = sp
            cy = (min(la[1], ra[1]) + max(la[3], ra[3])) / 2.0
            top = int(round(cy - h / 2.0))
            cand.append(((la[2] + clr, top, ra[0] - clr, top + h), 1))
    top = box[1] - round(FALLBACK_GAP * scale) - h
    cand.append(((box[0], top, box[2], top + h), 2))
    for rect, pos in cand:
        if rect[2] - rect[0] < 20:
            continue
        if rect[0] < limit[0] or rect[1] < limit[1] or rect[2] > limit[2] or rect[3] > limit[3]:
            continue
        if not _clear(rect, [box] + [b[1] for b in buttons]):
            continue
        if zones is not None and not _in_work(rect, zones):
            continue
        return rect, pos
    return None


def _in_work(rect, zones):
    """Where the strip overlaps a monitor, that part must lie inside that monitor's work area (not the taskbar)."""
    for mon, wk in zones:
        i = _inter(rect, mon)
        if i[2] > i[0] and i[3] > i[1]:
            if i[0] < wk[0] or i[1] < wk[1] or i[2] > wk[2] or i[3] > wk[3]:
                return False
    return True


def _clear(rect, others):
    for o in others:
        if rect[0] < o[2] and o[0] < rect[2] and rect[1] < o[3] and o[1] < rect[3]:
            return False
    return True


def ellipsize(text, max_px, measure):
    if measure(text) <= max_px:
        return text
    while text and measure(text + "…") > max_px:
        text = text[:-1]
    return (text + "…") if text else ""
