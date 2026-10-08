"""Summarize a guided-test folder into summary.md: one pass/fail/na line per step plus automatic checks.

Usage: python tools/summarize_guided.py <folder>
The summary holds no window titles, paths or names, so its "Report lines" section can go into an
install report as-is (after the user has read it).
"""
import json, os, sys

d = sys.argv[1]


def jl(name):
    p = os.path.join(d, name)
    out = []
    if os.path.exists(p):
        for line in open(p, encoding="utf-8-sig"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    return out


states, answers = jl("states.jsonl"), jl("answers.jsonl")


def verdict(a):
    w = (a or "").strip().lower().split(" ")[0]
    return {"y": "pass", "yes": "pass", "n": "FAIL", "no": "FAIL", "na": "n/a", "n/a": "n/a"}.get(w, "unclear")


lines = [f"# Guided test summary ({os.path.basename(d)})", "", "## Your answers", "",
         "| step | result | question | note |", "|---|---|---|---|"]
report = []
for a in answers:
    if a["id"] == "s13":
        lines.append(f"| s13 | {a['a']} % of one core | idle CPU over 60 s | |")
        report.append(f"- s13 idle CPU: {a['a']} % of one core")
        continue
    v = verdict(a["a"])
    note = " ".join((a["a"] or "").split(" ")[1:]).strip()
    lines.append(f"| {a['id']} | {v} | {a['q']} | {note} |")
    report.append(f"- {a['id']}: {v}")

lines += ["", "## Automatic checks (strip window, read after each step)", "",
          "| step | strip | took focus? | click-through | color deviation (bg/text, max 3) | theme |",
          "|---|---|---|---|---|---|"]
focus_bad = ct_bad = col_bad = shown = 0
themes = set()
for s in states:
    st = s.get("strip")
    took = bool(s.get("foreground", {}).get("is_strip"))
    focus_bad += took
    if isinstance(st, dict) and st.get("visible"):
        shown += 1
        ht = st.get("hit_test", {})
        ct_ok = ht.get("returns_strip") is False
        ct_bad += not ct_ok
        cs = st.get("closest_spec_row", {})
        dev_ok = cs.get("bg_dev", 99) <= 3 and cs.get("text_dev", 99) <= 3
        col_bad += not dev_ok
        theme = (cs.get("row") or "?/?").split("/")[1]
        themes.add(theme)
        lines.append(f"| {s['label']} | shown | {'YES' if took else 'no'} | "
                     f"{'ok' if ct_ok else 'FAIL'} | {cs.get('bg_dev')}/{cs.get('text_dev')} {'ok' if dev_ok else 'FAIL'} | {theme} |")
    else:
        lines.append(f"| {s['label']} | {'hidden' if isinstance(st, dict) else 'not found'} | {'YES' if took else 'no'} | | | |")
lines += ["", "Position is not judged automatically; your answers above cover it.", ""]
report += [f"- automatic: strip took focus in {focus_bad} of {len(states)} checks; click-through failed in {ct_bad} of {shown}; "
           f"colors off by more than 3 in {col_bad} of {shown}; theme(s) seen: {', '.join(sorted(themes)) or 'none'}"]
lines += ["## Report lines (safe to copy into an install report)", ""] + report
open(os.path.join(d, "summary.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
