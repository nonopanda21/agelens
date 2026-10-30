# Course cross-reference

Status vocabulary (only these): **done and verified** / **implemented, unverified** / **planned** / **blocked/needs teacher**.
Refreshed 2026-10-24 by agent D3 strictly from `DEVELOPMENT_LOG.md` and files that exist (first version 2026-10-23, agent D2). "Verified" means checked by running something, as recorded in the log; it never means tested with real users, real ads or a real model. Requirements: `docs/SPEC2.md` section 11. Deliverable-by-deliverable mapping: `docs/DELIVERABLES.md`. Nothing here records a date, spend, pitch content, approval, participant or result that is not in the repo.

## Midterm (week 7 Friday, 8 min, 10% of grade, 20 points)
| Requirement | Repo artifact | Status | Note |
|---|---|---|---|
| State what runs / what does not | `DEVELOPMENT_LOG.md` ("Verified" / "Not verified" per section); slide wording in `docs/DEMO_SCRIPT.md` section D; `README.md` first paragraph | done and verified | The log records runs for every round-2 part; slide wording must be edited to the state on the day |
| What was dropped since the pitch, and why | none (pitch document not in the repo) | planned | Team must supply the pitch. Drops visible in the log (e.g. ECharts map replaced by Three.js, testimonials not built because no real users, Lin figure not drawn) can be cited only once compared with the pitch |
| Actual spend and biggest item | `docs/BUDGET.md` section 2 (blank) | blocked/needs teacher | Team fills from receipts; permitted uses unconfirmed (PENDING_TEACHER 6). Log: the build connected no paid API |
| Live demo handling >=1 adversarial input from another team | `#/seeker` "Paste an ad to check" + "Try a demo case"; `docs/DEMO_SCRIPT.md` section C; `docs/ADVERSARIAL_CASES.md`; `tests/test_demo_cases.py`; `tests/browser/demo_cases.py` | done and verified | Browser run at 1280/360, 205 unit tests OK (log P5, 2026-10-24). Not yet rehearsed by people; exchange format with other teams unconfirmed (PENDING_TEACHER 8) |
| Evaluation plan: claim | `docs/EVAL_PROTOCOL.md` section 1 | implemented, unverified | Draft, written |
| ... threshold | `docs/EVAL_PROTOCOL.md` section 7 (proposal) | blocked/needs teacher | Proposal: lower CI bound > 0 and estimate >= +.20; not approved |
| ... counterfactual (fixed template vs LLM assistance) | `docs/EVAL_PROTOCOL.md` section 1; template arm in `backend/study_arms.py` | implemented, unverified | Re-decided 2026-10-29: contextual AI vs fixed template, identical evidence (`docs/EVAL_PLAN.md`, design `crossover-ai-v1`). The AI arm runs only as a labelled SIMULATED script rehearsal; no model connected; formal mode refused |
| ... teacher-approved assignment mechanism | `docs/EVAL_PROTOCOL.md` section 4; `backend/api_study.py` (seeded permuted blocks of 4); `tests/test_study.py` | blocked/needs teacher | Mechanism implemented and tested on simulated sessions (12/12 balance reproduced, log E); NOT approved |
| ... defensible power analysis | `scripts/power_analysis.py`, `data/study/power_table.md`, `docs/EVAL_PROTOCOL.md` section 7 | blocked/needs teacher | Run (log E): N=24, p0 .35, rho .2 gives MDE +0.365; assumptions unverified, no pilot; target N needs approval |
| Two truly open design questions | none written by the team | planned | Draft candidates only: how to define a "severe unsupported claim"; whether the reviewer reply should be shown before or after the seeker's own draft |

## Final (week 10, 12 min + 8 min Q&A, 30% of grade, 60 points)
| Requirement (points) | Repo artifact | Status | Note |
|---|---|---|---|
| Innovation (15) | `docs/COMPETITORS.md`; seeker → evidence → request → human reply flow | implemented, unverified | Flow works end to end in the browser (log C2, B2, P5); Applied's offer not verified from an official source (log D2) |
| Policy-cycle coherence (12): problem evidence -> mechanism -> product -> pre-registered evaluation -> results | `docs/LITERATURE.md`, `frontend/figures/feng2026_fig1_redrawn.svg`, `docs/PREREGISTRATION_DRAFT.md` | blocked/needs teacher | Feng et al. read in full; Lin (2025) abstract-only (log L). No preregistration filed and no results exist; both depend on approvals |
| Evaluation design and execution (10) | `docs/EVAL_PLAN.md` (crossover-ai-v1); study tools (`#/study`, `#/study/score`); `tests/test_study.py`, `tests/test_study_ai.py`; `tests/browser/study_flow.py`; SIMULATED dry run `data/study/dryrun_2026-10-29/` | blocked/needs teacher | Tools verified with scripted simulated sessions only (log E). No formal trial: `data/study/APPROVAL.json` absent, no model connected |
| Live demo (8) | `docs/DEMO_SCRIPT.md`; app at http://127.0.0.1:8765 | implemented, unverified | Pages verified by automated browser scripts (log P1, P2, P5, M, C2); no human rehearsal recorded |
| Honest reporting (8; see inconsistency below) | `DEVELOPMENT_LOG.md`; `docs/BUDGET.md`; `docs/CHANGELOG.md`; UI labels "Demo · Synthetic data", "Template demo" | implemented, unverified | Labels checked in browser runs; spend section still blank |
| Defence (7) | `docs/DEMO_SCRIPT.md` role table and Q&A prep | planned | Names are placeholders; team to assign and rehearse |
| >=2 examiner adversarial inputs in live demo | as midterm adversarial row | done and verified | Six demo cases + pasted-ad check verified in browser (log P5); live handling not rehearsed |
| Budget-driven trade-offs reported | `docs/BUDGET.md` section 5 | done and verified | Text matches the repo state: no model connected, simulated data only, no formal trial (log, 2026-10-24) |
| Adoption / rejection of midterm advice | none (midterm has not happened) | planned | |
| Every member can explain and answer | `docs/DEMO_SCRIPT.md` role table | planned | Depends on the team, not on code; never list someone who did not take part |

## Other course and acceptance items (SPEC2 sections 12-13)
| Item | Artifact | Status | Note |
|---|---|---|---|
| Source and run instructions | `README.md`, `requirements.txt`, `app.py` | done and verified | README rewritten 2026-10-24 |
| Unit tests passing | `tests/*.py` | done and verified | 205 tests OK (log P5, 2026-10-24) |
| Simulated data generator | `scripts/make_sim_data.py`, `docs/SIMULATION.md`, `data/sim/` | done and verified | Deterministic sha256 (log A2) |
| Real-data onboarding doc | `docs/REAL_DATA.md` | implemented, unverified | No real data imported |
| Model config + prompt versions | `docs/MODEL_CONFIG.md`, `backend/prompts/explain_v1.txt` | implemented, unverified | Real provider never called |
| Evaluation protocol + anonymous scoring templates | `docs/EVAL_PROTOCOL.md`, `data/study/scoring_template.csv`, `data/study/EXPORT_SCHEMA.md` | blocked/needs teacher | Templates and export verified in simulation; protocol needs approval |
| Budget record | `docs/BUDGET.md` | blocked/needs teacher | Incurred spend blank; permitted uses unconfirmed |
| Course cross-reference | this file | implemented, unverified | Team to confirm |
| Live-demo outline | `docs/DEMO_SCRIPT.md` | implemented, unverified | Seeker paths checked 2026-10-24; rest not rehearsed |
| Desktop and mobile screenshots | `docs/screenshots/` (9 folders, 1280 and 360 px) | done and verified | Software WebGL; `hero/` predates the hero redesign |
| 3D map rotates, zooms, selects; 2D alternative | `frontend/js/map3d.js`, `map2d.js`, `mapcore.js`; `tests/browser/map_shots.py` | done and verified | Log M; software WebGL; real touch devices not tested |
| Cover and map do not fight for rendering | `frontend/js/gfx.js`; `tests/browser/perf.py`; `docs/PERFORMANCE.md` | done and verified | One loop at a time; WebGL context leak found and fixed (log 2026-10-24); no real-GPU figures |
| Mobile: no horizontal overflow; keyboard completes key flows | browser scripts (theme_check, demo_cases, seeker_flow, study_flow, review_loop) | done and verified | 0 px overflow at 360; keyboard-only seeker and study runs (log B2, E, P5). No screen-reader test |
| Automated tests and human observation recorded separately | `DEVELOPMENT_LOG.md` | implemented, unverified | Log notes screenshots "viewed" by agents; no separate human walkthrough by team members recorded |
| Follow course server, account and log requirements | `DEVELOPMENT_LOG.md` (local, append-only) | blocked/needs teacher | Requirements unconfirmed (PENDING_TEACHER 7) |
| GeoJSON licence for display | `docs/GEO_SOURCES.md` | blocked/needs teacher | PENDING_TEACHER 10 |

## Status counts (rows above)
Midterm 10, Final 10, Other 16 = 36 rows: done and verified 11 · implemented, unverified 10 · planned 5 · blocked/needs teacher 10. (Recount after any edit.)

## Open rubric inconsistency (for the teacher)
The honest-reporting subheading is written as 9 points; the total table and the full-mark description say 8. The six final items sum to 60 only with 8. Awaiting teacher confirmation (`docs/PENDING_TEACHER.md` item 1). This file uses 8 provisionally.

## Verification evidence, lead run 2026-10-24 (automated; not a human walkthrough)
All re-run by the lead after the QA round, against fresh servers on this machine (software WebGL):
- Unit tests: 205 OK (`.venv/bin/python -m unittest discover -s tests`).
- `tests/browser/e2e_loop.py`: 22/22 — seeker UI submit → reviewer asks for info → seeker answers → draft (never shown to seeker) → publish → seeker sees reply → close; server log holds no request or draft text.
- `tests/browser/sweep.py`: 80/80 — 10 route states × 1280/360 px: no console errors, no 4xx/5xx, no horizontal overflow, no Chinese text outside quoted evidence.
- `tests/browser/a11y_check.py`: 0 high findings (was 8); `docs/UI_AUDIT.md` lists 23 findings (6 high fixed, 2/8 medium, 1/9 low).
- `tests/browser/demo_cases.py`: six live-demo cases incl. prompt injection, contradiction, truncation, no-match, no model — 0 failed checks, 0 console errors.
- `tests/browser/labels_check.py`: 0 CJK characters outside ad evidence on map 3D/2D, Explore, Evidence, Requests, Reviewer.
- `tests/browser/perf.py`: one WebGL loop at a time, 0 frames when nothing animates, contexts released on route change.
Rows above whose status depends on people (rehearsal, teacher approval, team facts, a real model call) are unchanged.
