# AgeLens

AgeLens is a local English web app (Northwestern SEPOL425, Group Delta course project) that helps a mid-career job seeker read the age wording in a job ad against their own background and question, see the original-text evidence, exceptions and gaps, and prepare questions for a human to answer. Current state, stated plainly: **all ad data is simulated** (labelled "Demo · Synthetic data"), **no AI model is connected** (briefs come from fixed rules and templates and are labelled "Template demo"), no real recruitment data has been imported, and no formal trial with participants has been run. AgeLens gives no legal advice and makes no hiring or eligibility decisions. What was actually run and verified is recorded in `DEVELOPMENT_LOG.md`; this README claims nothing beyond it.

## Run
```bash
cd ~/agelens
.venv/bin/python app.py --port 8765    # serves http://127.0.0.1:8765 (127.0.0.1 only; picks the next free port if busy)
```
If `.venv` is missing: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
To work on a copy of the database: `AGELENS_DB=/path/copy.db .venv/bin/python app.py --port 8815`.

Access:
- Seekers need nothing: each request gets a private key kept in the submitting browser.
- Reviewer token (demo-grade shared secret): `data/reviewer_token` (created at server start; the start message says which source is in use), or env `AGELENS_REVIEWER_TOKEN`.
- **Public demo** (`python app.py --public`, `docs/DEPLOY.md`): no sign-up; the whole site needs an **invite code** (personal or shared, viewer or reviewer) made with `scripts/invite.py`; secrets only from the environment; the database is rebuilt from the simulated dataset. Render blueprint: `render.yaml`.
- Study / rater token: `data/study/study_token`, or env `AGELENS_STUDY_TOKEN`.

## Simulated data
Generator `scripts/make_sim_data.py` (`sim-1.0.0`, default seed 20261023): 960 unique fictional ads + 58 duplicate rows, written to `data/sim/` and stored with `is_demo=1`. Details: `docs/SIMULATION.md`.
```bash
.venv/bin/python scripts/reset_sim.py --db data/agelens.db          # dry run: what would be deleted
.venv/bin/python scripts/reset_sim.py --db data/agelens.db --yes    # deletes only is_demo=1 rows
.venv/bin/python scripts/import_csv.py --source sim [--seed N]
```
`reset_sim.py` requires `--db` and refuses non-AgeLens databases. Rehearse on a copy first (`AGELENS_DB=/tmp/x.db` for the importer). Own CSV: `scripts/import_csv.py FILE.csv --inspect`, then `scripts/import_csv.py FILE.csv [--mapping map.json]`; see `docs/REAL_DATA.md`. Real and simulated rows are never mixed in stats or search.

## Tests
```bash
.venv/bin/python -m unittest discover -s tests          # last recorded run: 232 tests OK (2026-10-27)
```
Browser checks are Playwright scripts in `tests/browser/`, run with the separate environment `~/agelens-tools/pw/bin/python` (not a project dependency). `sweep.py`, `review_loop.py`, `e2e_loop.py` and `public_demo.py` start their own server on a temp copy of the database. The others take a base URL as the first argument and expect a running server; start that server on a database copy, because several scripts create requests or simulated study participants (the study scripts need a simulation-mode server on its own copy, never the main one). Example:
```bash
AGELENS_DB=/tmp/agelens-copy.db .venv/bin/python app.py --port 8815 &
~/agelens-tools/pw/bin/python tests/browser/demo_cases.py http://127.0.0.1:8815
```
| Script | Checks |
|---|---|
| `sweep.py` | every route at 1280/360: console errors, 4xx/5xx, overflow, CJK outside evidence (own server) |
| `a11y_check.py`, `palette_check.py` | scripted accessibility checks; text contrast in map/heatmap/charts |
| `e2e_loop.py` | seeker → reviewer → seeker loop through the UI |
| `public_demo.py` | public demo with invite codes: gate, roles, personal vs shared codes, reviewer code, sign out (own server on 127.0.0.1) |
| `demo_cases.py` | "Try a demo case" and "Paste an ad to check" at 1280/360 |
| `seeker_flow.py` | Job Seeker form, CV drop, answer, errors, download |
| `review_loop.py` | seeker + reviewer loop (starts its own server on 8805 with a temp DB) |
| `study_flow.py`, `study_timeout.py` | study tools in simulation mode |
| `map_v2.py`, `map_explore.py` | regional map 3D/2D and Explore |
| `perf.py` | render loops and WebGL contexts (software WebGL, not a GPU) |
| `theme_check.py`, `labels_check.py`, `lit_check.py` | inner-page theme, English labels, literature/About |
| `final_shots.py` | delivery screenshots into `docs/screenshots/final/` |
| `legacy/` | `hero_check.py`, `map_shots.py`: stale since the redesigns, kept for the record, do not rely on them |

## Page map
- **Overview `#/`** (sections in order): hero with the nebula particle field ("Pause animation" in the footer); "how it works" cards with the one-line statement of what AgeLens does; data **carousel** (live counts from the simulated-data API); simulated-data overview with the **regional map** (3D province prisms from real boundaries, 2D fallback, ranking table); occupation fields; "Why it matters" literature; boundaries + FAQ; steps; footer. A section rail in the left margin (wide screens) marks where you are and jumps between sections.
- **Quick check** (yellow tab on the right edge of every page except the study pages): paste one line of age wording and see how the rules classify it, with the verbatim quote. Rules only, nothing stored, never says whether someone qualifies.
- **Explore data `#/explore`**: filters, charts, ad list; each ad links to `#/evidence/<id>` (original text with highlighted wording).
- **Job Seeker `#/seeker`**: question first, background (optional CV drop: PDF/DOCX/TXT, fields editable and confirmed, never stored), answer under five headings with tags Ad text / You said / Rules, Markdown download, "Submit for human review". **Try a demo case**: six one-click fictional cases for presenters (procurement, hidden instruction, contradictory wording, cut-off text, no match, no model). **Paste an ad to check (optional)**: one pasted ad (≤ 4000 characters) checked in memory by the same rules, not stored, not sendable for review.
- **My requests `#/requests`**: replies and reviewer questions; owner keys live in this browser; on the public demo, requests sent with a personal invite code open in any browser with that code.
- **Invite code `#/access`** (public demo only): the invite page shown before anything else, and afterwards the current code's label, role and expiry with sign out.
- **Reviewer `#/reviewer`**: sign in with the reviewer token; queue, ask for info, draft, publish, close.
- **Study tools `#/study`** (participants) and **Scoring `#/study/score`** (raters, operator): crossover study (2 tasks ad only, 2 with the AgeLens evidence check; `docs/EVAL_PLAN.md`); simulation mode only; formal mode is refused without `data/study/APPROVAL.json`, which does not exist.
- **Method and sources `#/about`**.

## Automation
`automation/agelens_auto.py` is a quota-aware batch runner for small queued tasks. It starts **paused** and runs nothing until a person marks gate `T00` done and runs `start`. Commands, quota sources and safety rules: `automation/README.md`. Do not hand-edit `automation/*.json`; use the CLI.

## Docs index
| File | Content |
|---|---|
| `DEVELOPMENT_LOG.md` | what was built, run, verified, and not verified (source of truth) |
| `docs/CHANGELOG.md` | dated changes 2026-10-22 to 2026-10-24 with evidence |
| `docs/DELIVERABLES.md` | course deliverables mapped to files and status |
| `docs/COURSE_CHECKLIST.md` | course requirement cross-reference |
| `docs/PENDING_TEACHER.md` | items awaiting teacher decisions |
| `docs/DEMO_SCRIPT.md` | midterm/final live-demo outline, adversarial handling |
| `docs/SPEC.md`, `docs/SPEC2.md`, `docs/CONTRACT.md` | round-1 and round-2 briefs, API contract (+ round-3 addendum) |
| `docs/DEPLOY.md` | public demo: invite codes, Render deployment steps, free-plan limits, what was verified |
| `docs/SIMULATION.md`, `docs/REAL_DATA.md` | simulated data; onboarding real data |
| `docs/MODEL_CONFIG.md`, `backend/prompts/` | model adapter config, prompt versions |
| `docs/ADVERSARIAL_CASES.md` | adversarial and demo cases |
| `docs/EVAL_PLAN.md` | **current evaluation plan**: crossover, ad only vs AgeLens evidence check, threshold, power, dry run |
| `docs/EVAL_PROTOCOL.md`, `docs/PREREGISTRATION_DRAFT.md`, `data/study/` | legacy parallel protocol (superseded), scoring template, power analyses, dry-run exports |
| `docs/BUDGET.md` | budget plan, prices checked, spend log template |
| `docs/LITERATURE.md`, `docs/COMPETITORS.md`, `docs/GEO_SOURCES.md` | sources verified, competitor notes, map data source |
| `docs/PERFORMANCE.md` | render-loop measurements (software WebGL) |
| `docs/screenshots/` | desktop (1280) and mobile (360) screenshots from browser runs |

## Layout
`app.py` · `backend/` (server, schema, evidence, age parser, data sources, CV, brief, LLM adapter, requests, invite access, study) · `frontend/` (pages, css, js, vendored libraries, geo) · `scripts/` · `data/` (local DB, demo, sim, study) · `tests/` (+ `tests/browser/`) · `docs/` · `automation/`.
