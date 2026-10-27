"""SIMULATED tests for automation/agelens_auto.py: fake clock, fake quota, fake executor.
These prove scheduling logic only. They are NOT tests of real Claude quota or of the real `claude` CLI."""
import json, os, sys, tempfile, unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "automation"))
import agelens_auto as A  # noqa: E402

H = 3600
T0 = datetime(2026, 10, 23, 10, 0).timestamp()   # fixed "now"


class FakeClock:
    def __init__(self, now=T0): self.now = now
    def time(self): return self.now
    def sleep(self, s): self.now += s


def stream(subtype="success", text="done", turns=3, is_error=False):
    return [json.dumps({"type": "system", "session_id": "s"}),
            json.dumps({"type": "result", "subtype": subtype, "is_error": is_error, "result": text, "num_turns": turns, "session_id": "s"})]


class FakeExec:
    def __init__(self, *outcomes): self.outcomes, self.cmds = list(outcomes), []
    def run(self, cmd, cwd, timeout_s, log_path, on_start=None):
        self.cmds.append(cmd)
        if on_start: on_start(os.getpid())
        o = self.outcomes.pop(0) if self.outcomes else A.ExecResult(0, False, stream())
        if callable(o): o = o(self)
        return o
    def kill(self): pass


def task(id, size="small", priority=3, deps=(), status="pending", kind="work", acceptance=("true",)):
    return {"id": id, "title": f"task {id}", "goal": "g", "size": size, "priority": priority, "depends_on": list(deps),
            "status": status, "kind": kind, "acceptance": list(acceptance)}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root / "automation").mkdir()
        self.paths = A.Paths(self.root / "automation", self.root)
        self.clock = FakeClock()
        self.checks_ok = True
        self.counter = 0

    def tearDown(self): self.tmp.cleanup()

    def make(self, tasks, executor=None, cfg=None, control="run", state=None):
        A.jsave(self.paths.tasks, {"tasks": tasks})
        A.jsave(self.paths.config, cfg or {})
        st = {"control": control, "history": [], "next_allowed_at": 0, "consecutive_failures": 0}; st.update(state or {})
        A.jsave(self.paths.state, st)
        self.ex = executor or FakeExec()
        self.s = A.Scheduler(self.paths, self.clock, self.ex, checker=lambda t, root: [{"cmd": "c", "ok": self.checks_ok}])
        return self.s

    def quota(self, five=None, week=None, age_min=0, **kw):
        """five/week = (used_pct, seconds_until_reset). Written like the statusline capture would."""
        now = self.clock.now - age_min * 60
        q = {"source": "statusline", "captured_at": now, "values_changed_at": now}
        if five: q["five_hour"] = {"used_pct": five[0], "resets_at": self.clock.now + five[1]}
        if week: q["seven_day"] = {"used_pct": week[0], "resets_at": self.clock.now + week[1]}
        q.update(kw); A.jsave(self.paths.quota, q)

    def touch(self):
        self.counter += 1; (self.root / f"work{self.counter}.txt").write_text(str(self.counter))

    def state(self): return A.jload(self.paths.state, {})
    def tasks(self): return A.jload(self.paths.tasks, {})["tasks"]


class QuotaDecisions(Base):
    def test_five_hour_insufficient_waits_until_reset_plus_buffer(self):
        s = self.make([task("A")]); self.quota(five=(96, 2 * H), week=(10, 6 * 24 * H))
        d = s.tick()
        self.assertEqual(d["action"], "wait"); self.assertEqual(self.ex.cmds, [])
        self.assertAlmostEqual(d["wait_until"], self.clock.now + 2 * H + 3 * 60)

    def test_85_percent_blocks_large_but_allows_small(self):
        s = self.make([task("BIG", size="large", priority=1), task("SMALL", size="small", priority=2)])
        self.quota(five=(86, 3 * H), week=(10, 6 * 24 * H))
        d = s.tick()
        self.assertEqual(d["action"], "ran"); self.assertEqual(d["task"], "SMALL")
        s2 = self.make([task("BIG", size="large")]); self.quota(five=(88, 3 * H), week=(10, 6 * 24 * H))
        self.assertEqual(s2.tick()["action"], "wait")

    def test_weekly_exhausted_blocks_even_after_five_hour_reset(self):
        s = self.make([task("A")])
        self.quota(five=(10, 1 * H), week=(97, 3 * 24 * H))        # five-hour fine, weekly gone
        d = s.tick(); self.assertEqual(d["action"], "wait"); self.assertIn("weekly", d["reason"]); self.assertEqual(self.ex.cmds, [])
        self.clock.now += 2 * H                                      # five-hour window has reset; weekly has not
        self.quota(five=(0, 5 * H), week=(97, 3 * 24 * H - 2 * H))
        self.assertEqual(s.tick()["action"], "wait"); self.assertEqual(self.ex.cmds, [])

    def test_weekly_pacing_spreads_budget(self):
        s = self.make([task("A", size="medium")])
        self.quota(five=(0, 5 * H), week=(40, int(6.6 * 24 * H)))    # day 1: 40% used is ahead of pace
        self.assertEqual(s.tick()["action"], "wait")
        s = self.make([task("A", size="medium")]); self.quota(five=(0, 5 * H), week=(40, int(1.5 * 24 * H)))   # late week: fine
        self.assertEqual(s.tick()["action"], "ran")

    def test_weekly_reserve_lowers_near_reset_for_high_priority(self):
        s = self.make([task("A", size="small", priority=1)])
        self.quota(five=(0, 5 * H), week=(95.5, 6 * H))             # above the 95% normal ceiling, below the 98% end-of-week one
        self.assertEqual(s.tick()["action"], "ran")
        s = self.make([task("A", size="small", priority=4)]); self.quota(five=(0, 5 * H), week=(95.5, 6 * H))
        self.assertEqual(s.tick()["action"], "wait")

    def test_unknown_quota_waits_and_manual_entry_unblocks(self):
        s = self.make([task("A")]); d = s.tick()
        self.assertEqual(d["action"], "wait"); self.assertTrue(d.get("quota_unknown")); self.assertEqual(self.ex.cmds, [])
        st = self.state(); st["quota_manual"] = {"source": "manual", "captured_at": self.clock.now,
            "five_hour": {"used_pct": 10, "resets_at": self.clock.now + 3 * H}, "seven_day": {"used_pct": 20, "resets_at": self.clock.now + 5 * 24 * H}}
        A.jsave(self.paths.state, st)
        self.assertEqual(s.tick()["action"], "ran")

    def test_stale_data_blocks_even_if_numbers_look_low(self):
        s = self.make([task("A")]); self.quota(five=(5, 3 * H), week=(5, 5 * 24 * H), age_min=120)
        d = s.tick(); self.assertEqual(d["action"], "wait"); self.assertTrue(d.get("quota_unknown"))

    def test_reset_passed_with_stale_reading(self):
        # five-hour window reset an hour ago but weekly reading is stale and still in the future -> unknown, wait
        s = self.make([task("A"), task("B")])
        A.jsave(self.paths.quota, {"source": "statusline", "captured_at": self.clock.now - 8 * H, "values_changed_at": self.clock.now - 8 * H,
            "five_hour": {"used_pct": 97, "resets_at": self.clock.now - 3 * H}, "seven_day": {"used_pct": 30, "resets_at": self.clock.now + 4 * 24 * H}})
        self.assertEqual(s.tick()["action"], "wait"); self.assertEqual(self.ex.cmds, [])      # weekly reading 8 h old (> weekly_fresh_hours=6): unknown
        A.jsave(self.paths.quota, {"source": "statusline", "captured_at": self.clock.now - 4 * H, "values_changed_at": self.clock.now - 4 * H,
            "five_hour": {"used_pct": 97, "resets_at": self.clock.now - H}, "seven_day": {"used_pct": 30, "resets_at": self.clock.now + 4 * 24 * H}})
        self.assertEqual(s.tick()["action"], "ran")                                            # 4 h old weekly is acceptable; five-hour window has reset
        # both windows have passed their reset: old numbers no longer apply -> a small batch may start (assumed fresh window)
        A.jsave(self.paths.quota, {"source": "statusline", "captured_at": self.clock.now - 9 * 24 * H, "values_changed_at": self.clock.now - 9 * 24 * H,
            "five_hour": {"used_pct": 97, "resets_at": self.clock.now - 8 * 24 * H}, "seven_day": {"used_pct": 99, "resets_at": self.clock.now - H}})
        q = A.read_quota(self.paths, self.s.cfg(), {}, self.clock.now)
        self.assertEqual({w["status"] for w in q["windows"].values()}, {"reset_passed"})
        self.assertEqual(s.tick()["action"], "ran")

    def test_suspect_unchanged_numbers_are_flagged(self):
        s = self.make([task("A")])
        self.quota(five=(10, 3 * H), week=(10, 5 * 24 * H), values_changed_at=self.clock.now - 5 * H)
        q = A.read_quota(self.paths, s.cfg(), {}, self.clock.now); self.assertTrue(q["suspect"] and q["fresh"])

    def test_other_session_consumes_quota_and_scheduler_replans(self):
        def other_session_burns(ex):
            self.clock.now += 60; self.touch()                                   # someone else used 60 points meanwhile
            A.jsave(self.paths.quota, {"source": "statusline", "captured_at": self.clock.now, "values_changed_at": self.clock.now,
                "five_hour": {"used_pct": 80, "resets_at": T0 + 3 * H}, "seven_day": {"used_pct": 15, "resets_at": T0 + 5 * 24 * H}})
            return A.ExecResult(0, False, stream())
        s = self.make([task("A", size="medium"), task("B", size="medium", deps=["A"])], FakeExec(other_session_burns))
        self.quota(five=(20, 3 * H), week=(10, 5 * 24 * H))
        self.assertEqual(s.tick()["action"], "ran")
        self.assertEqual(self.state()["history"][-1]["five_hour_delta"], 60)       # observed, includes the other session: recorded honestly
        self.assertEqual(s.tick()["action"], "wait")                                  # B no longer fits: 80 + 60*1.3 > 95
        self.assertEqual(len(self.ex.cmds), 1)

    def test_projection_is_bounded(self):
        s = self.make([task("A"), task("B"), task("C")], FakeExec(), cfg={"quota": {"max_projected_batches": 1}})
        self.quota(five=(10, 3 * H), week=(10, 5 * 24 * H))
        self.assertEqual(s.tick()["action"], "ran")          # no fresh reading afterwards -> projected, 1 batch
        self.assertTrue(self.state()["projection"]["batches"] == 1)
        self.assertEqual(s.tick()["action"], "ran")          # second allowed? projection batches (1) not > max (1)
        self.assertEqual(s.tick()["action"], "wait")         # now 2 > 1 -> must wait for a real reading
        self.assertEqual(len(self.ex.cmds), 2)


class Lifecycle(Base):
    def test_empty_queue_and_all_done_finish(self):
        s = self.make([]); self.assertEqual(s.tick()["action"], "finish")
        s = self.make([task("A", status="done"), task("B", status="blocked")]); self.quota(five=(1, H), week=(1, 5 * 24 * H))
        self.assertEqual(s.tick()["action"], "finish")

    def test_human_gate_blocks_dependents_and_does_not_finish(self):
        s = self.make([task("GATE", kind="human"), task("A", deps=["GATE"])]); self.quota(five=(1, H), week=(1, 5 * 24 * H))
        d = s.tick(); self.assertEqual(d["action"], "pause"); self.assertIn("GATE", d["needs_human"]); self.assertEqual(self.ex.cmds, [])

    def test_run_loop_exits_when_only_human_items_remain(self):
        s = self.make([task("GATE", kind="human"), task("A", deps=["GATE"])]); self.quota(five=(1, H), week=(1, 5 * 24 * H))
        self.assertEqual(s.run_forever(), 0)                                   # returns instead of idling forever
        self.assertIn("waiting_for_human", self.paths.events.read_text()); self.assertEqual(self.ex.cmds, [])

    def test_run_loop_exits_when_everything_done(self):
        s = self.make([task("A", status="done")]); self.assertEqual(s.run_forever(), 0)
        self.assertIn('"finished"', self.paths.events.read_text())

    def test_dependencies_and_priority_order(self):
        s = self.make([task("B", priority=1, deps=["A"]), task("A", priority=5)]); self.quota(five=(1, H), week=(1, 5 * 24 * H))
        self.assertEqual(s.tick()["task"], "A")

    def test_pause_prevents_new_batches(self):
        s = self.make([task("A")], control="paused"); self.quota(five=(1, H), week=(1, 5 * 24 * H))
        self.assertEqual(s.tick()["action"], "pause"); self.assertEqual(self.ex.cmds, [])
        s = self.make([task("A")], control="stopping"); self.assertEqual(s.tick()["action"], "pause")

    def test_done_task_never_runs_twice(self):
        s = self.make([task("A"), task("B")], FakeExec(lambda e: (self.touch(), A.ExecResult(0, False, stream()))[1],
                                                     lambda e: (self.touch(), A.ExecResult(0, False, stream()))[1]))
        for _ in range(4):
            self.quota(five=(5, 3 * H), week=(5, 5 * 24 * H)); s.tick()
        ids = [c[c.index("-p") + 1].split()[2] for c in self.ex.cmds]
        self.assertEqual(sorted(ids), ["A", "B"]); self.assertEqual({t["status"] for t in self.tasks()}, {"done"})

    def test_interrupted_batch_already_satisfied_is_not_rerun(self):
        s = self.make([task("A", status="in_progress")], state={"current_batch": {"task": "A", "session_id": "sid-1", "pid": 999999, "resumes": 0}})
        self.quota(five=(1, H), week=(1, 5 * 24 * H)); self.checks_ok = True
        s.tick(); self.assertEqual(self.ex.cmds, []); self.assertEqual(self.tasks()[0]["status"], "done")

    def test_interrupted_batch_resumes_same_session_once(self):
        s = self.make([task("A", status="in_progress")], FakeExec(lambda e: (self.touch(), A.ExecResult(0, False, stream()))[1]),
                      state={"current_batch": {"task": "A", "session_id": "sid-1", "pid": 999999, "resumes": 0}})
        self.quota(five=(1, H), week=(1, 5 * 24 * H)); self.checks_ok = False
        s.tick()
        self.assertEqual(len(self.ex.cmds), 1); cmd = self.ex.cmds[0]
        self.assertIn("--resume", cmd); self.assertEqual(cmd[cmd.index("--resume") + 1], "sid-1"); self.assertNotIn("--session-id", cmd)

    def test_only_one_scheduler_can_hold_the_lock(self):
        s1, s2 = self.make([task("A")]), A.Scheduler(self.paths, self.clock, FakeExec())
        fd1 = s1.acquire_lock(); self.assertIsNotNone(fd1)
        self.assertIsNone(s2.acquire_lock())            # second start is refused
        os.close(fd1)
        fd3 = s2.acquire_lock(); self.assertIsNotNone(fd3); os.close(fd3)   # released lock (even after a crash) is reusable: no stale lock

    def test_sched_pid_ignores_foreign_processes(self):
        self.paths.lock.write_text(json.dumps({"pid": os.getpid()}))   # this test process is not agelens_auto.py
        self.assertIsNone(A.sched_pid(self.paths))


class Failures(Base):
    def test_three_consecutive_failures_pause_the_scheduler(self):
        s = self.make([task("A"), task("B"), task("C"), task("D")], FakeExec(*[A.ExecResult(1, False, stream("error_during_execution", f"unexpected failure kind{chr(97+i)}", is_error=True)) for i in range(4)]))
        for i in range(3):
            self.quota(five=(1, 4 * H), week=(1, 5 * 24 * H)); self.clock.now += 3 * H; self.quota(five=(1, 4 * H), week=(1, 5 * 24 * H))
            s.tick()
        st = self.state(); self.assertEqual(st["control"], "paused"); self.assertIn("consecutive", st["pause_reason"])
        self.quota(five=(1, 4 * H), week=(1, 5 * 24 * H)); self.assertEqual(s.tick()["action"], "pause"); self.assertEqual(len(self.ex.cmds), 3)

    def test_same_error_twice_blocks_the_task(self):
        s = self.make([task("A"), task("Z")], FakeExec(*[A.ExecResult(1, False, stream("error_during_execution", "weird crash", is_error=True))] * 2))
        for _ in range(2):
            self.clock.now += 3 * H; self.quota(five=(1, 4 * H), week=(1, 5 * 24 * H)); s.tick()
        self.assertEqual(next(t for t in self.tasks() if t["id"] == "A")["status"], "blocked")

    def test_no_progress_blocks_task_after_two_batches(self):
        s = self.make([task("A")], FakeExec(A.ExecResult(0, False, stream()), A.ExecResult(0, False, stream())))
        self.checks_ok = False                                  # nothing changed on disk, acceptance fails
        for _ in range(2):
            self.quota(five=(1, 4 * H), week=(1, 5 * 24 * H)); s.tick()
        t = self.tasks()[0]; self.assertEqual(t["status"], "blocked"); self.assertIn("no progress", t["blocked_reason"])

    def test_progress_without_acceptance_is_partial_not_done(self):
        s = self.make([task("A")], FakeExec(lambda e: (self.touch(), A.ExecResult(0, False, stream()))[1]))
        self.checks_ok = False; self.quota(five=(1, 4 * H), week=(1, 5 * 24 * H)); s.tick()
        self.assertEqual(self.tasks()[0]["status"], "partial")

    def test_auth_failure_pauses_without_retry(self):
        s = self.make([task("A")], FakeExec(A.ExecResult(1, False, stream("error", "authentication_failed: please run /login", is_error=True))))
        self.quota(five=(1, 4 * H), week=(1, 5 * 24 * H)); s.tick()
        self.assertEqual(self.state()["control"], "paused"); self.assertIn("authentication", self.state()["pause_reason"])
        self.assertEqual(self.tasks()[0]["attempts"], 0)   # not the task's fault

    def test_permission_denial_blocks_for_human_decision(self):
        s = self.make([task("A")], FakeExec(A.ExecResult(1, False, stream("error", "permission denied for Bash(curl ...)", is_error=True))))
        self.quota(five=(1, 4 * H), week=(1, 5 * 24 * H)); s.tick()
        self.assertEqual(self.tasks()[0]["status"], "blocked")

    def test_limit_with_official_reset_time_waits_until_then(self):
        s = self.make([task("A")], FakeExec(A.ExecResult(1, False, stream("error", "Usage limit reached · limit resets 3:45pm", is_error=True))))
        self.quota(five=(50, 4 * H), week=(10, 5 * 24 * H)); s.tick()
        st = self.state(); want = datetime(2026, 10, 23, 15, 45).timestamp() + 3 * 60
        self.assertAlmostEqual(st["next_allowed_at"], want); self.assertEqual(self.tasks()[0]["attempts"], 0)
        self.clock.now += 3600; self.quota(five=(1, 4 * H), week=(1, 5 * 24 * H))
        self.assertEqual(s.tick()["action"], "wait"); self.assertEqual(len(self.ex.cmds), 1)    # no model probing before the reset

    def test_limit_without_reset_time_uses_bounded_backoff(self):
        outs = [A.ExecResult(1, False, stream("error", "You've hit your usage limit", is_error=True)) for _ in range(3)]
        s = self.make([task("A")], FakeExec(*outs)); gaps = []
        for _ in range(3):
            self.quota(five=(1, 4 * H), week=(1, 5 * 24 * H)); s.tick()
            gaps.append(round((self.state()["next_allowed_at"] - self.clock.now) / 60)); self.clock.now = self.state()["next_allowed_at"] + 1
        self.assertEqual(gaps, [5, 15, 30])

    def test_weekly_limit_is_reported_as_weekly(self):
        s = self.make([task("A")], FakeExec(A.ExecResult(1, False, stream("error", "You've hit your weekly limit · resets Oct 26 at 9am", is_error=True))))
        self.quota(five=(1, 4 * H), week=(20, 5 * 24 * H)); s.tick()
        self.assertIn("weekly", self.state()["next_allowed_reason"])
        self.assertAlmostEqual(self.state()["next_allowed_at"], datetime(2026, 10, 26, 9, 0).timestamp() + 180)


def rl_line(five, week, status="allowed", rtype="five_hour", five_reset=T0 + 3 * H, week_reset=T0 + 5 * 24 * H):
    return json.dumps({"type": "rate_limit_event", "rate_limit_info": {"status": status, "resetsAt": five_reset, "rateLimitType": rtype,
        "unifiedWindows": {"five_hour": {"utilization": five, "resetsAt": five_reset}, "seven_day": {"utilization": week, "resetsAt": week_reset}}}})


class StreamQuota(Base):
    def test_stream_event_is_converted_and_marked_conservatively(self):
        rec = A.quota_from_stream({"status": "allowed", "unifiedWindows": {"five_hour": {"utilization": 0.68, "resetsAt": 5}, "seven_day": {"utilization": 0.12, "resetsAt": 9}}}, T0, 100)
        self.assertAlmostEqual(rec["five_hour"]["used_pct"], 68.0); self.assertAlmostEqual(rec["seven_day"]["used_pct"], 12.0); self.assertEqual(rec["raw"]["five_hour"], 0.68)
        self.assertIsNone(A.quota_from_stream({"status": "allowed"}, T0, 100))

    def test_batch_stream_gives_real_delta_and_fresh_quota_without_statusline(self):
        def run(ex):
            self.clock.now += 60; self.touch()
            return A.ExecResult(0, False, [rl_line(0.30, 0.10)] + stream())
        s = self.make([task("A", size="small"), task("B", size="small")], FakeExec(run))
        self.quota(five=(20, 3 * H), week=(10, 5 * 24 * H))
        self.assertEqual(s.tick()["action"], "ran")
        st = self.state(); self.assertAlmostEqual(st["quota_stream"]["five_hour"]["used_pct"], 30.0)
        self.assertAlmostEqual(st["history"][-1]["five_hour_delta"], 10.0)                    # measured, not projected
        self.assertEqual(st["projection"]["batches"], 0)
        q = A.read_quota(self.paths, s.cfg(), st, self.clock.now); self.assertEqual(q["source"], "stream"); self.assertTrue(q["fresh"])

    def test_rejected_event_uses_official_reset_time(self):
        reset = T0 + 2 * H + 1234
        s = self.make([task("A")], FakeExec(A.ExecResult(1, False, [rl_line(1.0, 0.2, status="rejected", five_reset=reset)] + stream("error", "request failed", is_error=True))))
        self.quota(five=(50, 3 * H), week=(10, 5 * 24 * H)); s.tick()
        self.assertAlmostEqual(self.state()["next_allowed_at"], reset + 180); self.assertEqual(self.tasks()[0]["attempts"], 0)

    def test_stale_reading_is_still_a_lower_bound_for_waiting(self):
        s = self.make([task("A")])
        self.quota(five=(97, 2 * H), week=(10, 5 * 24 * H), age_min=300)                        # old, but it already said 97%
        d = s.tick(); self.assertEqual(d["action"], "wait"); self.assertIn("lower bound", d["reason"])
        self.assertAlmostEqual(d["wait_until"], self.clock.now + 2 * H + 180)

    def test_stream_data_goes_stale_after_stream_fresh_minutes(self):
        s = self.make([task("A")])
        st = self.state(); st["quota_stream"] = {"source": "stream", "captured_at": self.clock.now - 50 * 60, "values_changed_at": self.clock.now - 50 * 60,
            "five_hour": {"used_pct": 10, "resets_at": self.clock.now + 3 * H}, "seven_day": {"used_pct": 10, "resets_at": self.clock.now + 5 * 24 * H}}
        A.jsave(self.paths.state, st)
        self.assertTrue(s.tick().get("quota_unknown"))                                         # 50 min > 45 min
        st["quota_stream"]["captured_at"] = self.clock.now - 30 * 60; A.jsave(self.paths.state, st)
        self.assertEqual(s.tick()["action"], "ran")


class Once(Base):
    def test_once_runs_at_most_one_batch(self):
        s = self.make([task("A"), task("B")], FakeExec(lambda e: (self.touch(), A.ExecResult(0, False, stream()))[1]))
        self.quota(five=(5, 3 * H), week=(5, 5 * 24 * H))
        d = s.tick(); self.assertEqual(d["action"], "ran"); self.assertEqual(len(self.ex.cmds), 1)
        self.assertEqual(sorted(t["status"] for t in self.tasks()), ["done", "pending"])


class CliOptions(Base):
    def test_unsupported_flag_is_dropped_and_retried_for_free(self):
        err = A.ExecResult(1, False, [], stderr="error: unknown option '--max-turns'")
        s = self.make([task("A")], FakeExec(err, lambda e: (self.touch(), A.ExecResult(0, False, stream()))[1]))
        self.quota(five=(5, 3 * H), week=(5, 5 * 24 * H)); s.tick()
        st = self.state(); self.assertEqual(st["unsupported_flags"], ["--max-turns"])
        self.assertEqual(self.tasks()[0]["attempts"], 0); self.assertEqual(st.get("consecutive_failures", 0), 0)
        self.assertEqual(st.get("next_allowed_at", 0), 0)                       # no cooldown: it failed before any model call
        self.quota(five=(5, 3 * H), week=(5, 5 * 24 * H)); s.tick()
        self.assertIn("--max-turns", self.ex.cmds[0]); self.assertNotIn("--max-turns", self.ex.cmds[1])
        self.assertEqual(self.ex.cmds[1][self.ex.cmds[1].index("--effort") + 1], "medium")   # neighbours untouched

    def test_rejected_essential_flag_pauses(self):
        s = self.make([task("A")], FakeExec(A.ExecResult(1, False, [], stderr="error: unknown option '--session-id'")))
        self.quota(five=(5, 3 * H), week=(5, 5 * 24 * H)); s.tick()
        self.assertEqual(self.state()["control"], "paused")


class Parsing(unittest.TestCase):
    def test_parse_limit_reset_variants(self):
        n = T0
        self.assertEqual(A.parse_limit_reset("resets 3:45pm", n), datetime(2026, 10, 23, 15, 45).timestamp())
        self.assertEqual(A.parse_limit_reset("limit resets 9am", n), datetime(2026, 10, 24, 9, 0).timestamp())   # already past today -> tomorrow
        self.assertEqual(A.parse_limit_reset("resets_at: 1738425600", n), 1738425600)
        self.assertEqual(A.parse_limit_reset("try again in 2 hours", n), n + 7200)
        self.assertIsNone(A.parse_limit_reset("usage limit reached", n))   # never guesses "five hours"

    def test_parse_when(self):
        self.assertEqual(A.parse_when("2026-10-24 09:30", T0), datetime(2026, 10, 24, 9, 30).timestamp())
        self.assertEqual(A.parse_when("11:30", T0), datetime(2026, 10, 23, 11, 30).timestamp())
        with self.assertRaises(ValueError): A.parse_when("whenever", T0)

    def test_classify(self):
        self.assertEqual(A.classify(0, "success", "all good"), "ok")
        self.assertEqual(A.classify(1, "error", "Usage limit reached"), "limit")
        self.assertEqual(A.classify(1, "error", "authentication_failed"), "auth")
        self.assertEqual(A.classify(1, "error_max_turns", ""), "max_turns")
        self.assertEqual(A.classify(1, "error", "API overloaded 529"), "transient")
        self.assertEqual(A.classify(0, None, "", timed_out=True), "timeout")

    def test_command_never_uses_bare_or_skip_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            p = A.Paths(Path(d), Path(d)); s = A.Scheduler(p)
            cmd = s.command(task("A"), "11111111-1111-1111-1111-111111111111")
        j = " ".join(cmd)
        for bad in ("--bare", "--dangerously-skip-permissions", "ANTHROPIC_API_KEY", "--max-budget-usd"): self.assertNotIn(bad, j)
        for need in ("--session-id", "--max-turns", "--permission-mode", "acceptEdits", "--permission-prompts", "/goal"): self.assertIn(need, j)

    def test_statusline_capture_stores_only_numbers(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "q.json"; env = dict(os.environ, AGELENS_QUOTA_FILE=str(out))
            payload = json.dumps({"session_id": "x", "transcript_path": "/very/private/path", "cwd": "/home/u",
                                  "rate_limits": {"five_hour": {"used_percentage": 12, "resets_at": 2000000000}}})
            subprocess.run([sys.executable, str(Path(A.__file__).with_name("statusline_capture.py"))], input=payload, text=True, env=env, capture_output=True)
            rec = json.loads(out.read_text())
            self.assertNotIn("private", json.dumps(rec)); self.assertEqual(rec["five_hour"]["used_pct"], 12); self.assertNotIn("seven_day", rec)


if __name__ == "__main__":
    unittest.main()
