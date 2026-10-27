#!/usr/bin/env python3
"""AgeLens quota-aware batch scheduler (stdlib only).

Layer 1 (work):  each batch = one `claude -p "/goal <condition>"` run on ONE task with an explicit --session-id.
Layer 2 (pace):  this program. Waiting and deciding are local; the model is called only to do a batch.
Quota comes ONLY from the official statusLine `rate_limits` (captured by statusline_capture.py) or manual entry.
Never: --bare (API billing), --dangerously-skip-permissions, reading OAuth credentials, unofficial endpoints.
One automation process at a time (flock). Commands: start status pause resume stop dry-run run quota tasks.
"""
import argparse, fcntl, hashlib, json, os, re, shlex, signal, shutil, statistics, subprocess, sys, time, uuid
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

DEFAULTS = {
    "model": "sonnet", "effort": "medium", "max_turns": 25, "batch_timeout_min": 45,
    "five_hour": {"large_task_pct": 85, "stop_new_pct": 95},
    "weekly": {"reserve_pct": 5, "end_reserve_pct": 2, "end_window_hours": 12, "front_load_pct": 12, "urgent_priority": 1},
    "quota": {"fresh_minutes": 20, "stream_fresh_minutes": 45, "weekly_fresh_hours": 6, "stream_utilization_multiplier": 100,
              "suspect_unchanged_minutes": 90, "unknown_mode": "wait",
              "unknown_interval_minutes": 180, "max_projected_batches": 1, "reset_buffer_minutes": 3},
    "estimates_prior": {"small": {"five_hour": 6, "seven_day": 1.5}, "medium": {"five_hour": 12, "seven_day": 3},
                        "large": {"five_hour": 25, "seven_day": 6}},
    "safety_factor": 1.3, "run_hours": {"start": 0, "end": 24}, "poll_seconds": 30,
    "backoff_minutes": [5, 15, 30, 60, 120, 180], "max_consecutive_failures": 3, "max_no_progress": 2,
    "max_attempts_per_task": 4, "claude_bin": "claude", "use_tmux": True, "tmux_session": "agelens-auto",
    "allowed_tools": ["Read", "Edit", "Write", "Glob", "Grep", "Bash(.venv/bin/python *)", "Bash(python3 *)",
                      "Bash(~/agelens-tools/pw/bin/python *)", "Bash(ls *)", "Bash(mkdir *)"],
    "denied_tools": ["Bash(sudo *)", "Bash(rm -rf *)", "Bash(pip install *)", "Bash(git push *)",
                     "Edit(automation/state.json)", "Edit(automation/tasks.json)", "Edit(automation/config.json)",
                     "Edit(automation/quota.json)", "Edit(automation/events.jsonl)",
                     "Write(automation/state.json)", "Write(automation/tasks.json)", "Write(automation/config.json)",
                     "Write(automation/quota.json)", "Write(automation/events.jsonl)"],
    "fingerprint_excludes": [".venv", "__pycache__", "node_modules", ".git", "data/uploads", "docs/screenshots",
                             "frontend/vendor", "frontend/geo", "automation/runs", "automation/state.json",
                             "automation/events.jsonl", "automation/quota.json", "automation/.lock",
                             "automation/runner.log", "automation/checkpoint.md", "automation/tasks.json",
                             "automation/batch-settings.json", "automation/config.json", ".db"],
}
TERMINAL = {"done", "blocked", "human_pending_never"}


def deep_merge(base, over):
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


class Paths:
    def __init__(self, base=None, root=None):
        self.base = Path(base or HERE)
        self.root = Path(root or ROOT)
        for n in ("config", "tasks", "state", "quota"):
            setattr(self, n, self.base / f"{n}.json")
        self.events, self.checkpoint = self.base / "events.jsonl", self.base / "checkpoint.md"
        self.lock, self.runs = self.base / ".lock", self.base / "runs"
        self.batch_settings = self.base / "batch-settings.json"


class Clock:
    def time(self): return time.time()
    def sleep(self, s): time.sleep(s)


def jload(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def jsave(p, obj):
    p = Path(p); tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def fmt(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "-"


# ---------------------------------------------------------------- quota ---------------------------------------
def parse_when(s, now):
    """Accept epoch seconds, ISO 'YYYY-MM-DD HH:MM', or 'HH:MM' (next occurrence, local time)."""
    s = str(s).strip()
    if re.fullmatch(r"\d{9,11}", s): return float(s)
    for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
        try: return datetime.strptime(s, f).timestamp()
        except ValueError: pass
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
    if m:
        d = datetime.fromtimestamp(now).replace(hour=int(m[1]), minute=int(m[2]), second=0, microsecond=0)
        if d.timestamp() <= now: d += timedelta(days=1)
        return d.timestamp()
    raise ValueError(f"cannot parse time: {s!r} (use epoch, 'YYYY-MM-DD HH:MM' or 'HH:MM')")


def parse_limit_reset(text, now):
    """Best-effort reset time from a usage-limit message such as 'limit resets 3:45pm' / 'resets_at 1738425600'.
    Returns epoch or None. Never guesses 'five hours'."""
    t = text or ""
    m = re.search(r"resets_at\D{0,5}(\d{10})", t)
    if m: return float(m[1])
    m = re.search(r"resets?\s+(?:at\s+)?(?:(\w{3,9})\s+(\d{1,2})(?:,|\s+at)?\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)", t, re.I)
    if m:
        h = int(m[3]) % 12 + (12 if m[5].lower() == "pm" else 0)
        d = datetime.fromtimestamp(now).replace(hour=h, minute=int(m[4] or 0), second=0, microsecond=0)
        if m[1] and m[2]:
            try:
                d = datetime.strptime(f"{m[1][:3]} {m[2]} {d.year} {h}:{int(m[4] or 0)}", "%b %d %Y %H:%M")
            except ValueError: return None
        if d.timestamp() <= now: d += timedelta(days=1)
        return d.timestamp()
    m = re.search(r"in\s+(\d+)\s*(hour|hr|minute|min)s?", t, re.I)
    if m: return now + int(m[1]) * (3600 if m[2].lower().startswith("h") else 60)
    return None


def read_quota(paths, cfg, state, now):
    """Merge statusline capture, batch-stream readings and manual entry into one reading with explicit freshness.
    Freshness is per window: five_hour uses fresh_minutes (stream_fresh_minutes for stream data); seven_day changes slowly so it
    may be older (weekly_fresh_hours). Returns windows{five_hour,seven_day}->{used,resets_at,status,fresh}, fresh (five-hour), age_min, source."""
    cands = [q for q in (jload(paths.quota, None), state.get("quota_manual"), state.get("quota_stream")) if q and q.get("captured_at")]
    q = max(cands, key=lambda c: c["captured_at"]) if cands else None
    out = {"source": q.get("source") if q else None, "captured_at": q["captured_at"] if q else None, "windows": {},
           "fresh": False, "age_min": None, "suspect": False, "projected": False}
    if not q:
        out["windows"] = {w: {"used": None, "resets_at": None, "status": "unknown", "fresh": False} for w in ("five_hour", "seven_day")}
        return out
    qc = cfg["quota"]; age = (now - q["captured_at"]) / 60
    out["age_min"] = age
    fresh5 = age <= (qc["stream_fresh_minutes"] if q.get("source") == "stream" else qc["fresh_minutes"])
    fresh7 = age <= qc["weekly_fresh_hours"] * 60
    if q.get("source") == "statusline" and q.get("values_changed_at") and (now - q["values_changed_at"]) / 60 > qc["suspect_unchanged_minutes"] and fresh5:
        out["suspect"] = True   # script keeps running but numbers never move: display refresh, maybe not server data
    proj = state.get("projection") or {}
    for w, fr in (("five_hour", fresh5), ("seven_day", fresh7)):
        win = q.get(w)
        if not win or win.get("used_pct") is None:
            out["windows"][w] = {"used": None, "resets_at": None, "status": "unknown", "fresh": False}; continue
        used, rs = float(win["used_pct"]), win.get("resets_at")
        if rs and rs <= now:   # window reset since the reading: old percentage no longer applies
            out["windows"][w] = {"used": 0.0, "resets_at": None, "status": "reset_passed", "fresh": True}
        else:
            add = proj.get(w, 0) if proj.get("base") == q["captured_at"] else 0
            if add: out["projected"] = True
            out["windows"][w] = {"used": used + add, "resets_at": rs, "status": "known", "fresh": fr}
    out["fresh"] = out["windows"]["five_hour"]["fresh"]
    return out


def quota_from_stream(rl, now, mult):
    """Official CLI stream event `rate_limit_event.rate_limit_info.unifiedWindows` -> our quota record.
    Observed in claude 2.1.308 (not described in the docs pages read). utilization scale is UNCONFIRMED; mult=100 is the safe default."""
    uw = (rl or {}).get("unifiedWindows") or {}
    rec = {"source": "stream", "captured_at": now, "values_changed_at": now, "status": rl.get("status"), "raw": {}}
    for w in ("five_hour", "seven_day"):
        x = uw.get(w)
        if isinstance(x, dict) and isinstance(x.get("utilization"), (int, float)):
            rec[w] = {"used_pct": x["utilization"] * mult, "resets_at": x.get("resetsAt")}; rec["raw"][w] = x["utilization"]
    return rec if "five_hour" in rec or "seven_day" in rec else None


def weekly_cap(now, resets_at, cfg, urgent):
    w = cfg["weekly"]
    left = max(0, (resets_at or now) - now)
    ending = urgent and left <= w["end_window_hours"] * 3600
    top = 100 - (w["end_reserve_pct"] if ending else w["reserve_pct"])
    if ending: return top, top
    frac = 1 - min(7 * 86400, left) / (7 * 86400)
    return min(top, w["front_load_pct"] + (top - w["front_load_pct"]) * frac), top


def estimate(state, cfg, size):
    deltas = [h for h in state.get("history", []) if h.get("size") == size and h.get("five_hour_delta") is not None][-5:]
    prior = cfg["estimates_prior"].get(size, cfg["estimates_prior"]["medium"])
    if not deltas: return {"five_hour": prior["five_hour"], "seven_day": prior["seven_day"], "basis": "prior"}
    d7 = [h["seven_day_delta"] for h in deltas if h.get("seven_day_delta") is not None]
    return {"five_hour": max(0.5, statistics.median(h["five_hour_delta"] for h in deltas)),
            "seven_day": max(0.1, statistics.median(d7)) if d7 else prior["seven_day"], "basis": f"{len(deltas)} observed batch(es)"}


# ---------------------------------------------------------------- tasks ---------------------------------------
def runnable_tasks(tasks, cfg):
    by = {t["id"]: t for t in tasks}
    out = []
    for t in sorted(tasks, key=lambda t: (t.get("priority", 5), t["id"])):
        if t.get("kind") == "human" or t.get("status") not in ("pending", "partial", "failed"): continue
        if t.get("attempts", 0) >= cfg["max_attempts_per_task"]: continue
        if all(by.get(d, {}).get("status") == "done" for d in t.get("depends_on", [])): out.append(t)
    return out


def queue_summary(tasks):
    c = {}
    for t in tasks: c[t.get("status", "pending")] = c.get(t.get("status", "pending"), 0) + 1
    return c


def decide(now, cfg, state, quota, tasks):
    """Pure decision. Returns {action: run|wait|finish|pause, reason, wait_until?, task?, mode?}."""
    if state.get("control") == "paused": return {"action": "pause", "reason": "paused by user (control=paused)"}
    if state.get("control") == "stopping": return {"action": "pause", "reason": "stop requested"}
    pending = [t for t in tasks if t.get("status") in ("pending", "partial", "failed") and t.get("kind") != "human"]
    humans = [t for t in tasks if t.get("kind") == "human" and t.get("status") != "done"]
    if not tasks or (not pending and not humans):
        return {"action": "finish", "reason": "queue empty / all tasks finished or blocked"}
    run = runnable_tasks(tasks, cfg)
    if not run:
        why = "waiting for human items: " + ", ".join(t["id"] for t in humans) if humans else "no runnable task (dependencies unmet or attempts exhausted)"
        return {"action": "pause", "reason": why, "needs_human": [t["id"] for t in humans]}
    h = datetime.fromtimestamp(now).hour
    if not (cfg["run_hours"]["start"] <= h < cfg["run_hours"]["end"]):
        nxt = datetime.fromtimestamp(now).replace(hour=cfg["run_hours"]["start"] % 24, minute=0, second=0, microsecond=0)
        if nxt.timestamp() <= now: nxt += timedelta(days=1)
        return {"action": "wait", "reason": "outside run_hours", "wait_until": nxt.timestamp()}
    if state.get("next_allowed_at", 0) > now:
        return {"action": "wait", "reason": state.get("next_allowed_reason", "backoff / cooldown"), "wait_until": state["next_allowed_at"]}
    W, buf = quota["windows"], cfg["quota"]["reset_buffer_minutes"] * 60
    five, week = W["five_hour"], W["seven_day"]
    qc = cfg["quota"]
    usable = lambda w: w["status"] == "reset_passed" or (w["status"] == "known" and w["fresh"])
    unknown = not (usable(five) and usable(week))
    if quota.get("projected") and state.get("projection", {}).get("batches", 0) > qc["max_projected_batches"]: unknown = True
    urgent = any(t.get("priority", 5) <= cfg["weekly"]["urgent_priority"] for t in run)
    if unknown:
        # Within one window usage only goes UP, so even a stale reading is a valid LOWER bound: if it already says "stop", waiting is conclusive.
        top7 = 100 - cfg["weekly"]["reserve_pct"]
        if five["status"] == "known" and five["used"] >= cfg["five_hour"]["stop_new_pct"]:
            return {"action": "wait", "reason": f"five-hour usage was already >= {five['used']:.0f}% (stale reading is a lower bound)", "wait_until": (five["resets_at"] or now + 1800) + buf}
        if week["status"] == "known" and week["used"] >= top7:
            return {"action": "wait", "reason": f"weekly usage was already >= {week['used']:.0f}% (stale reading is a lower bound)", "wait_until": (week["resets_at"] or now + 3600) + buf}
        if qc["unknown_mode"] == "conservative_small":
            small = [t for t in run if t.get("size") == "small"]
            last = state.get("last_unknown_run", 0)
            if small and now - last >= qc["unknown_interval_minutes"] * 60:
                return {"action": "run", "task": small[0], "mode": "unknown-quota-small", "reason": "quota unknown/stale; conservative small batch"}
        return {"action": "wait", "reason": "quota unknown or data stale — update via 'quota set' or an interactive session with the statusline",
                "wait_until": now + max(cfg["poll_seconds"], 60) * 10, "quota_unknown": True}
    cap5 = cfg["five_hour"]
    if week["status"] == "known":
        cap, top = weekly_cap(now, week["resets_at"], cfg, urgent)
        if week["used"] >= top:
            return {"action": "wait", "reason": f"weekly quota exhausted ({week['used']:.0f}% >= {top:.0f}%)",
                    "wait_until": (week["resets_at"] or now + 3600) + buf}
    else:
        cap, top = 100 - cfg["weekly"]["reserve_pct"], 100 - cfg["weekly"]["reserve_pct"]
    if five["status"] == "known" and five["used"] >= cap5["stop_new_pct"]:
        return {"action": "wait", "reason": f"five-hour quota {five['used']:.0f}% >= {cap5['stop_new_pct']}%",
                "wait_until": (five["resets_at"] or now + 1800) + buf}
    for t in run:
        est = estimate(state, cfg, t.get("size", "medium")); sf = cfg["safety_factor"]
        if five["status"] == "known":
            if five["used"] >= cap5["large_task_pct"] and not (t.get("size") == "small" or t.get("kind") in ("verify", "checkpoint")):
                continue
            if five["used"] + est["five_hour"] * sf > cap5["stop_new_pct"]: continue
        if week["status"] == "known" and week["used"] + est["seven_day"] * sf > cap:
            continue
        return {"action": "run", "task": t, "reason": "quota allows", "estimate": est, "weekly_cap": round(cap, 1),
                "mode": "normal"}
    # nothing fits: wait for whichever window is the binding one
    if five["status"] == "known" and five["used"] >= cap5["large_task_pct"]:
        return {"action": "wait", "reason": f"five-hour {five['used']:.0f}% >= {cap5['large_task_pct']}%: no small/verify task available",
                "wait_until": (five["resets_at"] or now + 1800) + buf}
    if week["status"] == "known":
        return {"action": "wait", "reason": f"weekly pacing: used {week['used']:.0f}% + estimate exceeds cap {cap:.0f}%",
                "wait_until": min((week["resets_at"] or now + 6 * 3600), now + 6 * 3600) + 0}
    return {"action": "wait", "reason": "estimated batch does not fit the five-hour window", "wait_until": (five["resets_at"] or now + 1800) + buf}


# ---------------------------------------------------------------- results -------------------------------------
LIMIT_RX = re.compile(r"usage limit|limit reached|hit your .*limit|session limit|weekly limit|rate.?limit", re.I)
AUTH_RX = re.compile(r"authentication_failed|oauth|not logged in|please run /login|invalid.*(token|credential)|account_on_hold|billing_error|credit balance|organization_not_allowed", re.I)
PERM_RX = re.compile(r"permission (was )?denied|requires approval|not allowed to use|denied by", re.I)
OPT_RX = re.compile(r"unknown option\s+['\"]?(--[\w-]+)|unrecognized (?:option|arguments?)\s+['\"]?(--[\w-]+)", re.I)
TRANSIENT_RX = re.compile(r"overloaded|server_error|timeout|timed out|connection|ECONN|temporar|503|529", re.I)


def classify(exit_code, subtype, text, timed_out=False):
    t = text or ""
    if timed_out: return "timeout"
    if OPT_RX.search(t): return "cli_option"
    if AUTH_RX.search(t): return "auth"
    if LIMIT_RX.search(t) and (exit_code != 0 or subtype not in (None, "success")): return "limit"
    if subtype == "error_max_turns": return "max_turns"
    if exit_code == 0 and subtype in (None, "success"): return "ok"
    if PERM_RX.search(t): return "permission"
    if TRANSIENT_RX.search(t): return "transient"
    return "error"


def parse_stream(lines):
    """Extract final result event + session info from stream-json lines. Returns dict; unknown fields stay None."""
    res = {"subtype": None, "is_error": None, "text": "", "session_id": None, "cost_usd": None, "turns": None, "rate_limit_events": 0, "rl": None}
    for ln in lines:
        try: ev = json.loads(ln)
        except ValueError: continue
        if not isinstance(ev, dict): continue
        if ev.get("type") == "rate_limit_event":
            res["rate_limit_events"] += 1
            if isinstance(ev.get("rate_limit_info"), dict): res["rl"] = ev["rate_limit_info"]
        if ev.get("type") == "result":
            res.update(subtype=ev.get("subtype"), is_error=ev.get("is_error"), text=str(ev.get("result") or ev.get("error") or ""),
                       session_id=ev.get("session_id"), cost_usd=ev.get("total_cost_usd"), turns=ev.get("num_turns"))
        if ev.get("type") == "system" and ev.get("session_id") and not res["session_id"]: res["session_id"] = ev["session_id"]
    return res


class ExecResult:
    def __init__(self, exit_code=0, timed_out=False, lines=None, stderr="", duration=0.0):
        self.exit_code, self.timed_out, self.lines, self.stderr, self.duration = exit_code, timed_out, lines or [], stderr, duration


class RealExecutor:
    """Runs claude in its own process group so stop/timeout only touches OUR child."""
    def __init__(self): self.proc = None
    def run(self, cmd, cwd, timeout_s, log_path, on_start=None):
        t0 = time.time()
        with open(log_path, "w", encoding="utf-8") as log:
            self.proc = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.PIPE, text=True, start_new_session=True)
            if on_start: on_start(self.proc.pid)
            try:
                _, err = self.proc.communicate(timeout=timeout_s); to = False
            except subprocess.TimeoutExpired:
                self.kill(); _, err = self.proc.communicate(); to = True
        lines = Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()
        return ExecResult(self.proc.returncode, to, lines, (err or "")[-2000:], time.time() - t0)
    def kill(self):
        if self.proc and self.proc.poll() is None:
            try: os.killpg(self.proc.pid, signal.SIGTERM)
            except ProcessLookupError: return
            try: self.proc.wait(10)
            except subprocess.TimeoutExpired:
                try: os.killpg(self.proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass


def run_checks(task, root, timeout=900):
    res = []
    for cmd in task.get("acceptance", []):
        try:
            p = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True, timeout=timeout)
            res.append({"cmd": cmd, "ok": p.returncode == 0, "tail": (p.stdout + p.stderr)[-300:]})
        except subprocess.TimeoutExpired:
            res.append({"cmd": cmd, "ok": False, "tail": "timeout"})
    return res


def fingerprint(root, excludes):
    h = hashlib.sha1(); root = Path(root)
    for dp, dn, fn in os.walk(root):
        rel = os.path.relpath(dp, root)
        dn[:] = sorted(d for d in dn if not any(os.path.join(rel, d).lstrip("./").startswith(e) or d == e for e in excludes))
        for f in sorted(fn):
            r = os.path.normpath(os.path.join(rel, f))
            if any(e in r for e in excludes if e.startswith(".db")) or any(r.startswith(e) for e in excludes): continue
            try: st = os.stat(root / r)
            except OSError: continue
            h.update(f"{r}:{st.st_size}:{st.st_mtime_ns}\n".encode())
    return h.hexdigest()


# ---------------------------------------------------------------- scheduler -----------------------------------
class Scheduler:
    def __init__(self, paths=None, clock=None, executor=None, checker=run_checks):
        self.p, self.clock, self.ex, self.checker = paths or Paths(), clock or Clock(), executor or RealExecutor(), checker
        self.stop_flag = False

    # -- persistence
    def cfg(self): return deep_merge(DEFAULTS, jload(self.p.config, {}))
    def state(self): return jload(self.p.state, {"control": "paused", "history": [], "next_allowed_at": 0, "consecutive_failures": 0})
    def tasks(self): return jload(self.p.tasks, {"tasks": []})["tasks"]
    def save_state(self, s): s["updated_at"] = self.clock.time(); jsave(self.p.state, s)
    def save_tasks(self, ts): jsave(self.p.tasks, {"tasks": ts})
    def event(self, _name, **kw):
        rec = {"ts": round(self.clock.time(), 1), "at": fmt(self.clock.time()), "event": _name, **kw}
        with open(self.p.events, "a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def checkpoint_auto(self, line):
        txt = self.p.checkpoint.read_text(encoding="utf-8") if self.p.checkpoint.exists() else "# Checkpoint\n"
        b, e = "<!-- auto:begin -->", "<!-- auto:end -->"
        if b not in txt: txt = txt.rstrip() + f"\n\n## Scheduler log (auto)\n{b}\n{e}\n"
        head, rest = txt.split(b, 1); body, tail = rest.split(e, 1)
        lines = [l for l in body.strip().splitlines() if l][-19:] + [line]
        self.p.checkpoint.write_text(head + b + "\n" + "\n".join(lines) + "\n" + e + tail, encoding="utf-8")

    # -- lock
    def acquire_lock(self):
        fd = os.open(self.p.lock, os.O_RDWR | os.O_CREAT, 0o600)
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd); return None
        os.ftruncate(fd, 0); os.write(fd, json.dumps({"pid": os.getpid(), "started": self.clock.time()}).encode())
        return fd   # flock dies with the process, so a crash can never leave a stale lock

    # -- quota / decision
    def snapshot(self, now=None):
        now = now or self.clock.time(); cfg, st = self.cfg(), self.state()
        q = read_quota(self.p, cfg, st, now)
        return now, cfg, st, q, self.tasks()

    def command(self, task, session_id, resume=False):
        cfg = self.cfg()
        if resume:
            prompt = f"Continue the interrupted batch for task {task['id']}. Re-read automation/checkpoint.md first; do not redo finished work."
        else:
            checks = "; ".join(f"`{c}` exits 0" for c in task.get("acceptance", [])) or "the task's goal is demonstrably met"
            prompt = (f"/goal Task {task['id']} — {task['title']}. {task.get('goal', '')} Before editing, read automation/checkpoint.md "
                      f"(not the whole repo). Done when: {checks}, and automation/checkpoint.md has a new dated entry saying what changed and what "
                      f"you verified (real command output, nothing invented). Constraints: serial work only, no subagents, only files under this project, "
                      f"never edit automation/{{state,tasks,config,quota}}.json, no installs, no network except localhost, run only tests relevant to your change "
                      f"first. Stop after at most {task.get('max_turns', cfg['max_turns'])} turns, or sooner and say why if blocked.")
        cmd = [cfg["claude_bin"], "-p", prompt]
        cmd += ["--resume", session_id] if resume else ["--session-id", session_id]
        cmd += ["--model", task.get("model", cfg["model"]), "--effort", task.get("effort", cfg["effort"]),
                "--permission-mode", "acceptEdits", "--permission-prompts", "none",
                "--max-turns", str(task.get("max_turns", cfg["max_turns"])),
                "--output-format", "stream-json", "--verbose", "--settings", str(self.p.batch_settings),
                "--allowedTools", ",".join(cfg["allowed_tools"]), "--disallowedTools", ",".join(cfg["denied_tools"])]
        bad = set(self.state().get("unsupported_flags", []))
        if bad:   # drop a flag (and its value) this CLI version rejected earlier
            out, i = [], 0
            while i < len(cmd):
                if cmd[i] in bad: i += 2; continue
                out.append(cmd[i]); i += 1
            cmd = out
        return cmd

    def write_batch_settings(self):
        cfg = self.cfg()
        jsave(self.p.batch_settings, {"permissions": {"deny": cfg["denied_tools"]}})

    # -- one scheduling step
    def tick(self):
        now, cfg, st, q, tasks = self.snapshot()
        # recover an interrupted batch first
        cb = st.get("current_batch")
        if cb and not self._alive(cb.get("pid")):
            return self._recover(cb, st, tasks, cfg, now)
        d = decide(now, cfg, st, q, tasks)
        st["last_decision"] = {k: v for k, v in d.items() if k != "task"} | ({"task": d["task"]["id"]} if d.get("task") else {}) | {"at": now}
        if d["action"] != "run":
            self.save_state(st); return d
        return self._run_batch(d, st, tasks, cfg, q, now)

    def _alive(self, pid):
        if not pid: return False
        try: os.kill(pid, 0)
        except OSError: return False
        try: return "claude" in Path(f"/proc/{pid}/cmdline").read_text()
        except OSError: return False

    def _recover(self, cb, st, tasks, cfg, now):
        t = next((x for x in tasks if x["id"] == cb["task"]), None)
        st["current_batch"] = None
        self.event("recovered_interrupted_batch", task=cb["task"], session_id=cb["session_id"])
        if t is None or t.get("status") == "done":
            self.save_state(st); return {"action": "wait", "reason": "interrupted batch for finished task ignored"}
        checks = self.checker(t, self.p.root)
        if checks and all(c["ok"] for c in checks):
            t["status"], t["last_result"] = "done", {"at": now, "note": "acceptance passed after interruption (not re-run)"}
            self.save_tasks(tasks); self.save_state(st); self.event("task_done", task=t["id"], via="recovery")
            return {"action": "wait", "reason": f"{t['id']} already satisfies acceptance; marked done"}
        if cb.get("resumes", 0) < 1:
            return self._execute(t, st, tasks, cfg, now, session_id=cb["session_id"], resume=True, resumes=cb.get("resumes", 0) + 1)
        self.save_state(st); return {"action": "wait", "reason": "interrupted batch already resumed once; will retry as a fresh attempt"}

    def _run_batch(self, d, st, tasks, cfg, q, now):
        t = next(x for x in tasks if x["id"] == d["task"]["id"])
        st["last_estimate"] = d.get("estimate")
        if d.get("mode") == "unknown-quota-small": st["last_unknown_run"] = now
        return self._execute(t, st, tasks, cfg, now, session_id=str(uuid.uuid4()), resume=False, quota_before=q)

    def _execute(self, t, st, tasks, cfg, now, session_id, resume, resumes=0, quota_before=None):
        self.write_batch_settings(); self.p.runs.mkdir(exist_ok=True)
        before_fp = fingerprint(self.p.root, cfg["fingerprint_excludes"])
        t["status"], t["attempts"] = "in_progress", t.get("attempts", 0) + (0 if resume else 1)
        st["current_batch"] = {"task": t["id"], "session_id": session_id, "started_at": now, "pid": None, "resumes": resumes}
        self.save_tasks(tasks); self.save_state(st)
        if quota_before is None: quota_before = read_quota(self.p, cfg, st, now)
        self.event("batch_start", task=t["id"], session_id=session_id, resume=resume, attempt=t["attempts"],
                   five_hour=quota_before["windows"]["five_hour"]["used"], seven_day=quota_before["windows"]["seven_day"]["used"])

        def on_start(pid):
            s2 = self.state(); s2["current_batch"]["pid"] = pid; self.save_state(s2)
        log = self.p.runs / f"{t['id']}-{session_id[:8]}.jsonl"
        r = self.ex.run(self.command(t, session_id, resume), str(self.p.root), cfg["batch_timeout_min"] * 60, log, on_start)
        end = self.clock.time(); st = self.state(); st["current_batch"] = None
        info = parse_stream(r.lines)
        text = (info["text"] or "") + " " + (r.stderr or "")
        rl = info["rl"]
        if rl:   # official quota numbers from the CLI's own event stream (statusLine does not run under -p)
            rec = quota_from_stream(rl, end, cfg["quota"]["stream_utilization_multiplier"])
            if rec: st["quota_stream"] = rec
            if rl.get("status") not in (None, "allowed", "allowed_warning") and r.exit_code != 0:
                text += f" usage limit resets_at {int(rl.get('resetsAt') or 0)} " + ("weekly" if "seven" in str(rl.get("rateLimitType")) else "")
        kind = classify(r.exit_code, info["subtype"], text, r.timed_out)
        after_fp = fingerprint(self.p.root, cfg["fingerprint_excludes"])
        progressed = after_fp != before_fp
        q2 = read_quota(self.p, cfg, st, end)
        self._account_quota(st, t, quota_before, q2, end, r, started=now)
        res = {"at": end, "kind": kind, "exit": r.exit_code, "turns": info["turns"], "duration_s": round(r.duration, 1), "progress": progressed}
        outcome = self._apply_outcome(kind, t, st, cfg, end, text, progressed, res)
        t["last_result"] = res
        self.save_tasks(tasks); self.save_state(st)
        self.event("batch_end", task=t["id"], session_id=session_id, **{k: v for k, v in res.items() if k != "at"}, status=t["status"],
                   rate_limit_events=info["rate_limit_events"],
                   quota_after={w: (q2["windows"][w]["used"]) for w in ("five_hour", "seven_day")}, quota_source=q2["source"], cost_usd_api_equivalent=info["cost_usd"])
        self.checkpoint_auto(f"- {fmt(end)} {t['id']}: {kind}, status={t['status']}, {round(r.duration)}s, progress={progressed}")
        return {"action": "ran", "task": t["id"], "kind": kind, "status": t["status"], **outcome}

    def _account_quota(self, st, t, before, after, end, r, started):
        b5, a5 = before["windows"]["five_hour"], after["windows"]["five_hour"]
        b7, a7 = before["windows"]["seven_day"], after["windows"]["seven_day"]
        fresh_after = bool(after["captured_at"]) and after["captured_at"] > started and after["fresh"]   # a reading taken AFTER the batch began
        d5 = d7 = None
        if fresh_after and b5["status"] == "known" and a5["status"] == "known" and b5["resets_at"] == a5["resets_at"] and not before.get("projected"):
            d5 = round(a5["used"] - b5["used"], 2)
        if fresh_after and b7["status"] == "known" and a7["status"] == "known" and b7["resets_at"] == a7["resets_at"] and not before.get("projected"):
            d7 = round(a7["used"] - b7["used"], 2)
        if d5 is not None:   # real observation replaces any projection
            st.setdefault("history", []).append({"task": t["id"], "size": t.get("size", "medium"), "five_hour_delta": d5, "seven_day_delta": d7, "at": end})
            st["history"] = st["history"][-30:]; st["projection"] = {"base": None, "five_hour": 0, "seven_day": 0, "batches": 0}
        else:   # no fresh reading after the batch: project (clearly labelled) from the estimate, bounded by max_projected_batches
            est = st.get("last_estimate") or estimate(st, self.cfg(), t.get("size", "medium"))
            pr = st.get("projection") or {"batches": 0, "five_hour": 0, "seven_day": 0}
            base = after["captured_at"]
            if pr.get("base") != base: pr = {"base": base, "five_hour": 0, "seven_day": 0, "batches": 0}
            pr["five_hour"] += est["five_hour"]; pr["seven_day"] += est["seven_day"]; pr["batches"] += 1
            st["projection"] = pr

    def _apply_outcome(self, kind, t, st, cfg, now, text, progressed, res):
        out = {}; cf = st.get("consecutive_failures", 0)
        if kind in ("ok", "max_turns"):
            checks = self.checker(t, self.p.root) if t.get("acceptance") else []
            res["checks"] = [{"cmd": c["cmd"], "ok": c["ok"]} for c in checks]
            if checks and all(c["ok"] for c in checks): t["status"], st["consecutive_failures"] = "done", 0; self.event("task_done", task=t["id"]); return out
            t["status"] = "partial" if progressed else "failed"
            t["no_progress"] = 0 if progressed else t.get("no_progress", 0) + 1
            st["consecutive_failures"] = 0 if progressed else cf + 1
            if t["no_progress"] >= cfg["max_no_progress"]: t["status"], t["blocked_reason"] = "blocked", "no progress in consecutive batches"
            return out
        if kind == "cli_option":
            m = OPT_RX.search(text); flag = m.group(1) or m.group(2)
            bad = st.setdefault("unsupported_flags", [])
            if flag in bad or flag in ("-p", "--print", "--session-id", "--resume"):
                st["control"], st["pause_reason"] = "paused", f"CLI rejected essential option {flag}: needs a human"
            else: bad.append(flag)
            t["status"] = "pending"; t["attempts"] = max(0, t.get("attempts", 1) - 1)
            self.event("cli_option_unsupported", flag=flag, note="dropped; retrying without it")
            return out
        t["status"] = "failed"
        sig = f"{kind}:{re.sub(r'[0-9]+', '#', text)[:120]}"
        if t.get("last_error_sig") == sig and kind not in ("limit",): t["status"], t["blocked_reason"] = "blocked", f"same error repeated: {kind}"
        t["last_error_sig"] = sig
        if kind == "limit":
            weekly = bool(re.search(r"week|7-day|seven", text, re.I))
            reset = parse_limit_reset(text, now)
            t["status"], st["consecutive_failures"] = "pending", cf   # not the task's fault; attempts refunded
            t["attempts"] = max(0, t.get("attempts", 1) - 1)
            if reset:
                st["next_allowed_at"] = reset + cfg["quota"]["reset_buffer_minutes"] * 60
                st["next_allowed_reason"] = f"{'weekly' if weekly else 'five-hour'} usage limit; official reset {fmt(reset)}"
            else:
                i = min(st.get("backoff_index", 0), len(cfg["backoff_minutes"]) - 1); st["backoff_index"] = i + 1
                st["next_allowed_at"] = now + cfg["backoff_minutes"][i] * 60
                st["next_allowed_reason"] = f"usage limit with no reliable reset time; bounded backoff {cfg['backoff_minutes'][i]} min"
            out["wait_until"] = st["next_allowed_at"]
            self.event("limit_hit", task=t["id"], weekly=weekly, reset=fmt(reset) if reset else None, next=fmt(st["next_allowed_at"]))
            return out
        st["backoff_index"] = 0
        if kind == "auth":
            st["control"], st["pause_reason"] = "paused", "authentication/billing problem — needs a human (run `claude auth status`, log in, then resume)"
            t["status"] = "pending"; t["attempts"] = max(0, t.get("attempts", 1) - 1)
        elif kind == "permission":
            t["status"], t["blocked_reason"] = "blocked", "needs a human decision (permission denied in unattended mode)"
        elif kind in ("transient", "timeout", "error"):
            st["consecutive_failures"] = cf + 1
            i = min(cf, len(cfg["backoff_minutes"]) - 1)
            st["next_allowed_at"], st["next_allowed_reason"] = now + cfg["backoff_minutes"][i] * 60, f"{kind} backoff"
        if st.get("consecutive_failures", 0) >= cfg["max_consecutive_failures"]:
            st["control"], st["pause_reason"] = "paused", f"{cfg['max_consecutive_failures']} consecutive failed batches"
        return out

    # -- main loop
    def run_forever(self):
        fd = self.acquire_lock()
        if fd is None: print("another AgeLens automation process holds the lock; exiting", file=sys.stderr); return 2
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stop_flag", True)); signal.signal(signal.SIGINT, lambda *_: setattr(self, "stop_flag", True))
        self.event("scheduler_start", pid=os.getpid())
        st = self.state(); st["scheduler"] = {"pid": os.getpid(), "started_at": self.clock.time()}; self.save_state(st)
        try:
            while not self.stop_flag:
                d = self.tick()
                if d["action"] == "finish":
                    self.event("finished", reason=d["reason"]); print("finished:", d["reason"]); break
                if d["action"] == "ran": continue
                if d["action"] == "pause" and d.get("needs_human") is not None:
                    self.event("waiting_for_human", items=d["needs_human"]); print("stopping: only human items remain:", d["needs_human"]); break
                if d["action"] == "pause" and self.state().get("control") == "stopping": break
                wait = d.get("wait_until"); poll = self.cfg()["poll_seconds"]
                slept = 0
                while not self.stop_flag and slept < (min(poll, max(1, wait - self.clock.time())) if wait else poll):
                    self.clock.sleep(1); slept += 1
        finally:
            self.ex.kill() if hasattr(self.ex, "kill") else None
            st = self.state(); st["scheduler"] = {"pid": None};
            if st.get("current_batch") and not self._alive(st["current_batch"].get("pid")): pass   # kept for recovery
            self.save_state(st); self.event("scheduler_stop"); os.close(fd)
        return 0


# ---------------------------------------------------------------- CLI -----------------------------------------
def sched_pid(paths):
    try:
        info = json.loads(Path(paths.lock).read_text() or "{}")
        pid = info.get("pid")
        if pid and "agelens_auto.py" in Path(f"/proc/{pid}/cmdline").read_text(): return pid
    except (OSError, ValueError): pass
    return None


def cmd_once(S, args):
    """Exactly one scheduling decision, at most one batch, then exit (no loop). Used for controlled verification."""
    fd = S.acquire_lock()
    if fd is None: print("another automation process holds the lock", file=sys.stderr); return 2
    try:
        d = S.tick()
    finally:
        os.close(fd)
    print({k: v for k, v in d.items() if k != "task"} | ({"task": d["task"]["id"]} if isinstance(d.get("task"), dict) else {}))
    return 0


def cmd_status(S, args):
    now, cfg, st, q, tasks = S.snapshot()
    d = decide(now, cfg, st, q, tasks)
    pid = sched_pid(S.p)
    print(f"scheduler : {'RUNNING pid ' + str(pid) if pid else 'not running'}   control={st.get('control')}   {st.get('pause_reason', '')}")
    print(f"quota     : source={q['source'] or 'none'}  captured={fmt(q['captured_at'])}  age={'%.0f min' % q['age_min'] if q['age_min'] is not None else '-'}  "
          f"{'FRESH' if all(w['status'] == 'reset_passed' or (w['status'] == 'known' and w['fresh']) for w in q['windows'].values()) else 'STALE/UNKNOWN (额度未知/数据已过期)'}{'  suspect-unchanged' if q['suspect'] else ''}{'  +projected' if q['projected'] else ''}")
    for w in ("five_hour", "seven_day"):
        x = q["windows"][w]
        print(f"  {w:9}: used={'?' if x['used'] is None else '%.1f%%' % x['used']}  resets={fmt(x['resets_at'])}  [{x['status']}{'' if x['status'] != 'known' else (', fresh' if x['fresh'] else ', stale')}]")
    print(f"tasks     : {queue_summary(tasks)}")
    if st.get("current_batch"): print(f"batch     : {st['current_batch']}")
    print(f"decision  : {d['action']} — {d['reason']}" + (f" (until {fmt(d['wait_until'])})" if d.get("wait_until") else "") + (f" task={d['task']['id']}" if d.get("task") else ""))
    if st.get("next_allowed_at", 0) > now: print(f"cooldown  : until {fmt(st['next_allowed_at'])} — {st.get('next_allowed_reason')}")
    return 0


def cmd_dry_run(S, args):
    now, cfg, st, q, tasks = S.snapshot(); d = decide(now, cfg, st, q, tasks)
    print(f"decision: {d['action']} — {d['reason']}")
    if d.get("task"):
        cmd = S.command(d["task"], "<new-uuid>")
        print("would run:", " ".join(shlex.quote(c) if len(c) < 80 else shlex.quote(c[:77] + "...") for c in cmd))
        print("estimate :", d.get("estimate"), "weekly cap:", d.get("weekly_cap"))
    print("(dry-run: no model call, no state written)")
    return 0


def cmd_quota(S, args):
    now = time.time(); st = S.state()
    if args.action == "show": return cmd_status(S, args)
    if args.action == "clear": st["quota_manual"] = None; S.save_state(st); print("manual quota cleared"); return 0
    q = {"source": "manual", "captured_at": now, "values_changed_at": now}
    for key, used, rs in (("five_hour", args.five_hour, args.five_resets), ("seven_day", args.seven_day, args.seven_resets)):
        if used is not None: q[key] = {"used_pct": used, "resets_at": parse_when(rs, now) if rs else None}
    st["quota_manual"] = q; st["projection"] = {"base": None, "five_hour": 0, "seven_day": 0, "batches": 0}
    S.save_state(st); S.event("quota_manual", five_hour=args.five_hour, seven_day=args.seven_day); print("manual quota recorded (marked source=manual, expires as stale after fresh_minutes)")
    return 0


def cmd_tasks(S, args):
    ts = S.tasks()
    if args.action == "list":
        for t in ts: print(f"{t['id']:8} {t.get('status', 'pending'):11} p{t.get('priority', 5)} {t.get('size', '-'):6} {t.get('kind', 'work'):8} deps={t.get('depends_on', [])} {t['title']}")
        return 0
    t = next((x for x in ts if x["id"] == args.id), None)
    if not t: print("no such task"); return 1
    t["status"] = {"done": "done", "block": "blocked", "unblock": "pending", "reset": "pending"}[args.action]
    if args.action in ("unblock", "reset"): t["attempts"] = 0; t["no_progress"] = 0; t.pop("blocked_reason", None); t.pop("last_error_sig", None)
    S.save_tasks(ts); S.event("task_" + args.action, task=args.id, by="human"); print(args.id, "->", t["status"]); return 0


def cmd_control(S, args, value):
    st = S.state(); st["control"] = value
    if value == "run": st.pop("pause_reason", None); st["consecutive_failures"] = 0; st["next_allowed_at"] = 0 if args.cmd == "resume" and args.now else st.get("next_allowed_at", 0)
    S.save_state(st); S.event("control", value=value)
    print("control =", value); return 0


def cmd_start(S, args):
    if sched_pid(S.p): print("already running, pid", sched_pid(S.p)); return 0
    st = S.state(); st["control"] = "run"; st.pop("pause_reason", None); S.save_state(st)
    cfg = S.cfg(); me = f"python3 {HERE / 'agelens_auto.py'} run"
    if cfg["use_tmux"] and shutil.which("tmux"):
        if subprocess.run(["tmux", "has-session", "-t", cfg["tmux_session"]], capture_output=True).returncode == 0:
            print("tmux session exists but scheduler is not running; kill it with: tmux kill-session -t", cfg["tmux_session"]); return 1
        subprocess.run(["tmux", "new-session", "-d", "-s", cfg["tmux_session"], "-c", str(S.p.root), f"{me} >> {S.p.base / 'runner.log'} 2>&1"], check=True)
        print(f"started in tmux session '{cfg['tmux_session']}' (attach: tmux attach -t {cfg['tmux_session']}). Not guaranteed to survive logout/reboot.")
    else:
        subprocess.Popen(shlex.split(me), cwd=S.p.root, stdout=open(S.p.base / "runner.log", "a"), stderr=subprocess.STDOUT, start_new_session=True)
        print("started in background (no tmux)")
    return 0


def cmd_stop(S, args):
    st = S.state(); st["control"] = "stopping"; S.save_state(st)
    pid = sched_pid(S.p)
    if not pid: print("scheduler not running (control=stopping prevents new batches until you `resume`)"); return 0
    os.kill(pid, signal.SIGTERM)
    for _ in range(30):
        if not sched_pid(S.p): break
        time.sleep(1)
    cfg = S.cfg()
    if shutil.which("tmux"): subprocess.run(["tmux", "kill-session", "-t", cfg["tmux_session"]], capture_output=True)
    print("stopped" if not sched_pid(S.p) else "scheduler still shutting down"); return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agelens_auto", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("start", "status", "pause", "stop", "dry-run", "run", "once"): sub.add_parser(n)
    r = sub.add_parser("resume"); r.add_argument("--now", action="store_true", help="clear the cooldown too")
    q = sub.add_parser("quota"); q.add_argument("action", choices=["show", "set", "clear"], nargs="?", default="show")
    q.add_argument("--five-hour", type=float); q.add_argument("--five-resets"); q.add_argument("--seven-day", type=float); q.add_argument("--seven-resets")
    t = sub.add_parser("tasks"); t.add_argument("action", choices=["list", "done", "block", "unblock", "reset"], nargs="?", default="list"); t.add_argument("id", nargs="?")
    args = ap.parse_args(argv); S = Scheduler()
    return {"start": cmd_start, "status": cmd_status, "dry-run": cmd_dry_run, "once": cmd_once, "stop": cmd_stop, "quota": cmd_quota, "tasks": cmd_tasks,
            "pause": lambda S, a: cmd_control(S, a, "paused"), "resume": lambda S, a: cmd_control(S, a, "run"),
            "run": lambda S, a: S.run_forever()}[args.cmd](S, args)


if __name__ == "__main__":
    sys.exit(main())
