#!/usr/bin/env python3
"""Claude Code statusLine hook: records the OFFICIAL rate_limits numbers for the AgeLens scheduler, prints a short status line.
Stores ONLY: used_pct + resets_at for five_hour/seven_day, session_id, and two timestamps. No transcript path, no cwd, no credentials.
captured_at   = when this script ran (a display refresh).  values_changed_at = last time the numbers actually moved.
Neither proves the server data is fresh; the scheduler treats old captured_at as stale and flags numbers that never move."""
import json, os, sys, time
from pathlib import Path

OUT = Path(os.environ.get("AGELENS_QUOTA_FILE", Path(__file__).resolve().parent / "quota.json"))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        print("quota n/a"); return
    rl = data.get("rate_limits") or {}
    cur = {}
    for w in ("five_hour", "seven_day"):
        x = rl.get(w)
        if isinstance(x, dict) and isinstance(x.get("used_percentage"), (int, float)):
            cur[w] = {"used_pct": x["used_percentage"], "resets_at": x.get("resets_at")}
    now = time.time()
    if cur:
        try:
            old = json.loads(OUT.read_text())
        except Exception:
            old = {}
        same = all((old.get(w) or {}) == cur.get(w) for w in ("five_hour", "seven_day")) and set(old) >= set(cur)
        rec = {"source": "statusline", "captured_at": now, "values_changed_at": old.get("values_changed_at", now) if same else now,
               "session_id": data.get("session_id"), **cur}
        try:
            tmp = OUT.with_suffix(".tmp"); tmp.write_text(json.dumps(rec)); os.replace(tmp, OUT)
        except OSError:
            pass
    parts = [f"{'5h' if w == 'five_hour' else '7d'} {cur[w]['used_pct']:.0f}%" for w in ("five_hour", "seven_day") if w in cur]
    print(" · ".join(parts) if parts else "quota n/a")


if __name__ == "__main__":
    main()
