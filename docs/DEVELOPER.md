# AgeLens developer guide

Operational detail moved out of the README on 2026-10-27, so the README can stay short. What was actually run and verified is in `DEVELOPMENT_LOG.md`.

## Run locally
```bash
cd ~/agelens
.venv/bin/python app.py --port 8765    # http://127.0.0.1:8765 (127.0.0.1 only; picks the next free port if busy)
```
- If `.venv` is missing: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
- To work on a copy of the database: `AGELENS_DB=/path/copy.db .venv/bin/python app.py --port 8815`.
- **Public mode** (what the host runs): `python app.py --public`. See `docs/DEPLOY.md`. To rehearse it on this machine, always pass `--host 127.0.0.1`.

## Access
- **Seekers** need nothing. Each request gets a private key kept in the submitting browser.
- **Reviewer token** (demo-grade shared secret): `data/reviewer_token`, created at server start, or the env var `AGELENS_REVIEWER_TOKEN`. On a public host, the token comes only from the environment; if unset, the reviewer desk is closed.
- **Study / rater token:** `data/study/study_token`, or the env var `AGELENS_STUDY_TOKEN`. On a public host the same rule applies.
- **Invite codes** (optional, public host): `scripts/invite.py` → `AGELENS_INVITES`.
- **Pro codes:** `scripts/pro_code.py` → `data/pro_codes.local.json` locally, or `AGELENS_PRO_CODES` on a host. See `docs/PRO.md`.

## Simulated data
- **Generator:** `scripts/make_sim_data.py` (`sim-1.0.0`, default seed 20261023) makes 960 unique fictional ads plus 58 duplicate rows. They are written to `data/sim/` and stored with `is_demo=1`. Details: `docs/SIMULATION.md`.
- **Reset and re-import:**
  ```bash
  .venv/bin/python scripts/reset_sim.py --db data/agelens.db          # dry run: what would be deleted
  .venv/bin/python scripts/reset_sim.py --db data/agelens.db --yes    # deletes only is_demo=1 rows
  .venv/bin/python scripts/import_csv.py --source sim [--seed N]
  ```
  `reset_sim.py` requires `--db` and refuses databases that are not AgeLens databases. Rehearse on a copy first (`AGELENS_DB=/tmp/x.db` for the importer).
- **Your own CSV:** run `scripts/import_csv.py FILE.csv --inspect`, then `scripts/import_csv.py FILE.csv [--mapping map.json]`. See `docs/REAL_DATA.md`.
- Real and simulated rows are never mixed in statistics or search.

## Before every push
```bash
bash scripts/check_before_push.sh          # about 3 minutes; --quick for unit tests + Render rehearsal only
```
It does four things:
1. Checks that nothing sensitive is tracked by git.
2. Runs all unit tests.
3. Rehearses Render: only committed files, a fresh venv, then `app.py --public --host 127.0.0.1`. It checks that 960 ads are rebuilt, the open demo is open, Pro is locked, the reviewer desk is closed and the public headers are present.
4. Runs the sweep, public-demo, Pro-flow and accessibility browser checks.

It says "DO NOT PUSH" on the first failure.

## Tests
```bash
.venv/bin/python -m unittest discover -s tests          # 364 tests OK at the last full run (2026-10-29)
```
- Browser checks are Playwright scripts in `tests/browser/`. Run them with the separate environment `~/agelens-tools/pw/bin/python`, which is not a project dependency.
- **Scripts marked "own server"** start their own server on a temporary database.
- **The others** take a base URL. Point the ones that **write** (demo_cases, seeker_flow, study_*) at a server running on a copy of the database, never at the main one. The study scripts need a simulation-mode server on its own copy:
```bash
cp data/agelens.db /tmp/copy.db && AGELENS_DB=/tmp/copy.db .venv/bin/python app.py --port 8807 &
~/agelens-tools/pw/bin/python tests/browser/demo_cases.py http://127.0.0.1:8807
```
| Script | Checks | Server |
|---|---|---|
| `sweep.py` | every route at 1280/360 (141 checks since the Why/Findings pages): console errors, 4xx/5xx, overflow, CJK outside evidence, `[object …]` text | own |
| `e2e_loop.py`, `review_loop.py` | seeker → reviewer → seeker through the UI | own |
| `public_demo.py` | public mode with invite codes: gate, roles, personal vs shared codes, reviewer code, sign out | own (127.0.0.1) |
| `pro_flow.py` | Pro: report preview, Pro code, Word download, credits, Pro page | own |
| `a11y_check.py`, `palette_check.py` | scripted accessibility checks; text contrast in map, heatmap and charts | read-only |
| `theme_check.py`, `labels_check.py`, `lit_check.py` (port number) | inner-page theme, English labels, literature/About | read-only |
| `map_real.py` | home map Real/Simulated switch, labels, captions, a server without real data | own |
| `map_v2.py`, `map_explore.py`, `perf.py` | regional map 3D/2D, old Explore links redirect to the map, render loops (software WebGL, not a GPU) | read-only |
| `demo_cases.py`, `seeker_flow.py` | "Try an example situation" (presenter mode), the pasted-ad check, the Check an ad form, CV drop, errors | **writes: use a copy** |
| `study_flow.py`, `study_timeout.py` | study tools in simulation mode (`STUDY_TOKEN`, `STUDY_OUT` env) | **simulation copy** |
| `final_shots.py` | delivery screenshots into `docs/screenshots/final/` | read-only |
| `legacy/` | `hero_check.py`, `map_shots.py`: stale since the redesigns, kept for the record | — |

## Page map
- **Overview `#/`** (kept short since 2026-10-30), sections in order:
  - hero with the particle field ("Pause animation" is in the footer): the positioning line as an eyebrow, the question headline, "Check an ad" / "See an example", the one-line limits, and a "Check one line" card that reads a pasted line with the same rules as the edge tab (`AgeLens.lineCheck` in `js/sidekit.js`);
  - "What you get" (`home_example.js`): one static answer for a fictional case, labelled as such;
  - "how it works" cards, then the three steps with the "Check an ad" button;
  - the data overview with the regional map (3D province prisms, a 2D fallback, Real/Simulated switch); the spread, top-10 ranking and industry × region heatmap sit under "More views" (closed by default; map tests open it with an init script);
  - "Read more": link cards to the two detail pages and Method and sources, then "Check an ad";
  - footer.
- **Why it matters `#/why`:** page head, the motivation (figures and theory of change), the literature, occupation fields, boundaries and FAQ.
- **Findings `#/findings`:** page head, the headline-number cards (carousel), then patterns by experience, occupation and gender wording (single-sex requirements shown per 10,000 ads).

  The three pages share one composer (`pages/home.js`): each section registers with `page` (`home` by default, `why`, `findings`, or `*` for the footer) and a `rail` label. They share the home look through `body[data-layout="home"]`, which the router sets from `page.layout`. On wide screens, a section rail in the left margin lists the current page's sections (shown when there are at least three).
- **Check one line** (was Quick check): a tab on the right edge on desktop, or an item in the Menu on phones. Paste one line of age wording and see how the rules read it. It is rules only, nothing is stored, and it is hidden on the study pages.
- **`#/explore` (removed 2026-10-30):** the old simulated-ad explorer. Old links now land on the Overview's data map. Ads are opened from Job Seeker answers (`#/evidence/<id>`).
- **Check an ad `#/seeker`** (the Job Seeker page; nav label "Check an ad"):
  - Order: your question → "The ad you are looking at" (paste; checked in memory, never stored) → about you (+ optional CV: PDF/DOCX/TXT, fields confirmed, file never stored) → **Check this ad** (`#paste-btn`). Secondary: "No ad yet, or want context?" → **See similar ads** (`#go-btn`) searches the fictional example ads. Enter in a field checks the pasted ad if there is one, else searches.
  - The limits are one line under the lead; the answer repeats them only as two small tags (data label, "Template demo").
  - The answer leads with "In short" (`brief.summary`: what the ad(s) state, how that relates to the person, never eligibility wording) and "Your question for the employer" (`brief.employer_question`; uses experience, never age) with a Copy button. Then the five headings; with several ads the ad-by-ad lines fold under "Show N ad-by-ad lines", and the ad cards fold under "Show the N ads behind this answer" (`#ads-more`; tests open it). Tags: Ad wording (translated), You said, AgeLens rules. No raw ad ids on screen (they stay in the brief's provenance).
  - Downloads: Markdown brief (starts with "## In short"); "Full report · Pro".
  - "Submit for human review": the confirmation links to Human review and offers "Copy request link".
  - "Try an example situation": four fictional cases; `#/seeker?demo=1` (presenter mode) adds "no matches" and "no AI model" and the presenter "look for" notes.
- **Human review `#/requests`** (My requests): replies and reviewer questions.
- **Full report `#/pro`** (Pro): free vs Pro, the Pro code and the wallet.
- **Invite code `#/access`:** used only when the host sets invite codes.
- **Reviewer `#/reviewer`:** the queue; ask for information, draft, publish, close. It needs the token or a reviewer invite code.
- **Study tools `#/study`** (participants) and **Scoring `#/study/score`** (raters and operator): the crossover study (`docs/EVAL_PLAN.md`, design `crossover-ai-v1`; older designs via `AGELENS_STUDY_DESIGN=crossover-rules-v1`). Simulation mode only; formal mode is refused without `data/study/APPROVAL.json` AND a connected AI model.
- **Method and sources `#/about`.**

## Automation
`automation/agelens_auto.py` is a quota-aware batch runner for small queued tasks.
- It starts **paused** and runs nothing until a person marks gate `T00` done and runs `start`.
- Commands, quota sources and safety rules are in `automation/README.md`.
- Do not hand-edit `automation/*.json`; use the CLI.

## Docs index
| File | Content |
|---|---|
| `DEVELOPMENT_LOG.md` | what was built, run, verified and not verified (source of truth) |
| `docs/REAL_DATA_YEARS.md`, `docs/REAL_DATA_AUDIT.md`, `data/real/` | real Zhaopin data: year choice, rule accuracy audit, the published aggregate (counts only) |
| `docs/MOTIVATION.md` | the motivation section with page-referenced citations |
| `docs/DEPLOY.md`, `render.yaml` | public deployment on Render: open or invite-only, free-plan limits |
| `docs/PRO.md` | Pro stage 1: free vs Pro, codes and credits, the Word report |
| `docs/EVAL_PLAN.md` | **current evaluation plan** (decided 2026-10-29): contextual AI vs fixed template, identical evidence; outcomes, power, SIMULATED dry run. Old plan: `docs/EVAL_PLAN_v1_rules_vs_ad.md` |
| `docs/EVAL_PROTOCOL.md`, `docs/PREREGISTRATION_DRAFT.md`, `data/study/` | legacy parallel protocol (superseded), scoring template, power analyses, dry-run exports |
| `docs/DELIVERABLES.md`, `docs/COURSE_CHECKLIST.md`, `docs/PENDING_TEACHER.md` | course deliverables, requirement cross-reference, items awaiting the teacher |
| `docs/DEMO_SCRIPT.md`, `docs/ADVERSARIAL_CASES.md` | live-demo outline, adversarial inputs |
| `docs/SPEC.md`, `docs/SPEC2.md`, `docs/CONTRACT.md` | build briefs and API contract (with round-3 addendum) |
| `docs/SIMULATION.md`, `docs/REAL_DATA.md` | simulated data; onboarding real data |
| `docs/MODEL_CONFIG.md`, `backend/prompts/` | model adapter configuration (no model is connected) |
| `docs/LITERATURE.md`, `docs/COMPETITORS.md`, `docs/GEO_SOURCES.md` | verified sources, competitor notes, map data source |
| `docs/BUDGET.md`, `docs/PERFORMANCE.md`, `docs/UI_AUDIT.md` | budget, render-loop measurements, UI audit |
| `docs/CHANGELOG.md` | dated changes 2026-10-22 to 10-24 (later changes: the log) |

## Layout
- `app.py`
- `backend/`: server, schema, evidence, age parser, data sources, CV, brief, report, LLM adapter, requests, invite access, Pro, study.
- `frontend/`: pages, css, js, vendored libraries and fonts, geo.
- `scripts/`, `data/` (local DB, demo, sim, study), `tests/` (with `tests/browser/`), `docs/`, `automation/`.
