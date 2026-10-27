# AgeLens automation: quota-aware, resumable batches

One small program (`agelens_auto.py`, Python stdlib only) decides **when** to run; the model only does the **work** (`claude -p "/goal …"`, one small task per batch). Waiting, quota checks and bookkeeping are local — no model calls while idle.

It uses your existing claude.ai subscription. It never uses `--bare` (that mode requires an API key and would bill the API), never `--dangerously-skip-permissions`, never reads OAuth credentials. Check: `claude auth status` should say `authMethod: claude.ai`.

## Commands (run from `~/agelens`)
```
python3 automation/agelens_auto.py status      # scheduler, quota (with age/freshness), queue, next decision
python3 automation/agelens_auto.py dry-run     # what it WOULD do now; no model call, nothing written
python3 automation/agelens_auto.py once        # exactly one decision, at most one batch, then exit (controlled runs)
python3 automation/agelens_auto.py start       # start in tmux session "agelens-auto" (or background if no tmux)
python3 automation/agelens_auto.py pause       # no NEW batch starts (a running batch finishes)
python3 automation/agelens_auto.py resume      # allow batches again   (--now also clears a cooldown)
python3 automation/agelens_auto.py stop        # terminate the scheduler and ITS child only; kills the tmux session it made
python3 automation/agelens_auto.py tasks list|done ID|block ID|unblock ID|reset ID
python3 automation/agelens_auto.py quota set --five-hour 40 --five-resets "15:30" --seven-day 55 --seven-resets "2026-10-26 09:00"
tmux attach -t agelens-auto                     # watch it; detach with Ctrl-b d
```
Starts **paused**. Task `T00` is a human gate: mark it done (`tasks done T00`) only when no other Claude session is editing the project, then `start`.

## Where quota numbers come from (checked on claude 2.1.308, 2026-10-23)
1. **Batch event stream (automatic, observed).** `claude -p --output-format stream-json` emits `rate_limit_event` messages with `unifiedWindows.five_hour/seven_day` `{utilization, resetsAt}`. The scheduler reads the last one after every batch (and uses `resetsAt` when a batch is rejected). *Caveats:* this event is not described on the doc pages I read, so its schema may change; and the **scale of `utilization` is unconfirmed** — 0.68 is assumed to mean 68% (`quota.stream_utilization_multiplier: 100`). If it actually meant 0.68%, the scheduler would over-estimate usage (the safe direction). Confirm once: compare `status` with `/usage` in Claude Code.
2. **Statusline (interactive sessions only).** `.claude/settings.json` registers `statusline_capture.py`, which saves the documented `rate_limits.five_hour/seven_day` (`used_percentage`, `resets_at`) to `quota.json` (numbers + timestamps only). Pro/Max only, after the first API response. **Verified: it does NOT run under `claude -p`**, so batches cannot use it.
3. **Manual.** Read `/usage` and enter it with `quota set` (`source=manual`).
4. **Unknown.** Nothing fresh → the scheduler **waits** and `status` says `STALE/UNKNOWN`. Local token counts, API prices and context-window percentages are never used as quota. (`total_cost_usd` in batch results is an API-equivalent estimate, not subscription quota.)

Freshness is per window: five-hour data must be ≤ 20 min old (≤ 45 min for batch-stream data); the weekly window changes slowly, so ≤ 6 h is accepted (the 5% reserve covers other sessions). Within a window usage only rises, so an old reading is still a valid *lower bound*: if it already says "stop", waiting until `resetsAt` is conclusive. A window whose `resetsAt` has passed is treated as reset (`[reset_passed]`). `captured_at` is when the data was recorded, not proof the server data is current; numbers frozen for 90 min are flagged `suspect`.

## Policy (adjustable in `config.json`; starting values, not official limits)
- five-hour ≥ 85%: only `small` / verify tasks; ≥ 95%: no new batch until reset (+3 min buffer).
- weekly: 5% always reserved; the allowed ceiling rises linearly over the week (12% on day 0 → 95% at reset) so the first two days cannot burn everything. Within 12 h of reset, if a priority-1 task is waiting, the reserve drops to 2%. Weekly exhausted → nothing starts, even if the five-hour window has reset.
- A batch starts only if `used + estimate × 1.3` fits. Estimates start from priors and become the median of observed per-batch deltas (per size). Deltas include other people's/sessions' use; nothing here can control that.
- After a batch with no fresh reading, usage is *projected* (labelled) for at most 1 batch, then it waits for a real reading.

## Limits, failures, resume
- Usage limit: reset time parsed from the message if present, else bounded backoff 5→15→30→60→120→180 min. No model polling. The attempt is refunded.
- Auth/billing error → paused, needs you. Permission denied → task `blocked` (needs a human decision). 3 consecutive failed batches → paused. Same error twice, or two batches with no file progress → task `blocked`.
- Interrupted batch (crash/stop): on restart it runs the task's acceptance commands first; if they pass the task is marked done without re-running; otherwise it resumes the **same session** once (`--resume`).
- Acceptance is checked **locally** by the commands in `tasks.json`, not by the model. Statuses: `done`, `partial`, `failed`, `blocked`, plus `pending`/`in_progress`.
- One writer: an `flock` on `.lock` — a second `start` is refused, and a crash cannot leave a stale lock.
- Hard bounds per batch: `--max-turns` (if this CLI accepts it; if it is rejected the flag is dropped automatically and recorded), a turn clause inside `/goal`, and `batch_timeout_min`.

## Files
`tasks.json` queue · `checkpoint.md` progress (batches read this, not the repo) · `state.json` runtime/quota/estimates · `config.json` thresholds · `events.jsonl` concise log (no credentials/content) · `runs/` raw stream per batch · `quota.json` statusline capture · `batch-settings.json` deny rules passed to batches.

## Not automated
Teacher approvals, spend facts, CNKI access (H01/H02), publishing, purchasing, recruiting participants. It never touches those. When only human items remain it pauses and says so; when everything is done or blocked it exits.
It does not survive logout/reboot: tmux keeps it alive across remote-desktop disconnects only. No systemd unit is installed (user lingering is off, and the school's policy on user services is unconfirmed).

## Uninstall
`python3 automation/agelens_auto.py stop`, then delete `automation/` and `.claude/settings.json` (the statusLine entry). Nothing else was changed outside `~/agelens` except the Playwright test environment in `~/agelens-tools/` (optional).

## Tests
`.venv/bin/python -m unittest tests.test_automation` — 44 SIMULATED tests (fake clock, fake quota, fake executor). They check the logic; they are not tests of real Claude quota.

## Controlled real verification (2026-10-23)
One real batch (`once`, task T01, README update, `--effort medium`, sonnet): exit 0, 13 turns reported (limit given: 12 — `--max-turns` was accepted, enforcement not proven), 49 s, locally verified acceptance 4/4, checkpoint entry written by the model, nothing outside the task edited except its own checkpoint. `apiKeySource: none` → subscription login, no API key. Two Bash calls were auto-denied (no approval surface) and the batch still succeeded. Statusline did not run under `-p`; the stream gave five-hour 0.67→0.68 and weekly 0.12. One small batch moved the five-hour reading by about one point; one sample is not an estimate, so the priors in `config` are kept. Details: `DEVELOPMENT_LOG.md`.
