# Changelog (2026-10-22 to 2026-10-24)

Derived from `DEVELOPMENT_LOG.md` (agent D3, 2026-10-24). Each item names the verification the log records, or says "not verified". Several round-2 log sections carry no date; they are placed by their order in the log and by the file dates of their screenshots, and are marked "(undated)". Test counts are those reported at the time; the latest recorded full run is 205 tests OK.

## 2026-10-22 — round 1 (local prototype)
**Data and parsing**
- Age parser, evidence queries, CSV importer, round-1 demo CSV (300 rows → 292 unique, 8 duplicates). Verified: unit tests (57 OK across agents); import idempotent on re-run; all `/api/*` data endpoints curled on a temp DB.
**Seeker, CV, brief**
- CV parse (TXT/DOCX/PDF), rules-based brief, disabled LLM adapter. Verified: unit tests; API calls on a DB copy. Frontend not verified at that stage.
**Requests and reviewer**
- Request codes, owner-token hashing, reviewer endpoints. Verified: 11 tests; curl loop create → info request → answer → draft → publish → close.
**Home, explore, map**
- ECharts 3D province map, Explore filters. Verified: API shapes; GeoJSON 34/34 names join. Browser rendering not verified by the agent.
**Integration (lead)**
- Verified in headless Chromium: all pages load without JS errors; 3D map rendered (software WebGL); no horizontal scroll at 1280/360; seeker → brief → submit → reviewer sees request. Fixes: reviewer token created at start; Explore date overflow; literal "null" text. Not verified: reviewer reply via UI, CV drag-drop, print, Markdown download.

## 2026-10-23 — round 2
**Course documents (agent D2)**
- `docs/COMPETITORS.md`, `BUDGET.md`, `COURSE_CHECKLIST.md`, `DEMO_SCRIPT.md`, `PENDING_TEACHER.md`. Verified: official pages fetched (Textio, LinkedIn help, Claude and OpenAI API pricing). Not verified: Applied's offer, ChatGPT consumer pricing (HTTP 403).
**Literature and About (agent L)**
- "Why it matters" section, `#/about`, Feng et al. Figure 1 redrawn from printed estimates. Verified: NBER PDF read; Lin (2025) abstract only; browser at 1280/360, 0 console errors, 0 px overflow. Lin figure not delivered.
**Requests and reviewer (agent C2)** (undated)
- Idempotency key, duplicate guard, consent, event timeline, pagination, size and rate limits, recovery states. Verified: 67 tests OK; `tests/browser/review_loop.py` 37/37 checks.
**Simulated data (agent A2)** (undated)
- `DataSource` interface, generator `sim-1.0.0` (960 unique + 58 duplicates), parser `age-rules-2.0.0` (classes, preference, truncation, conflict), `/api/status`, `reset_sim.py`. Verified: identical sha256 over two runs; 145 tests OK; endpoints on a temp DB. Not verified: accuracy on real text; 15 GB path.
**Hero, steps, FAQ (agent H)** (undated)
- First Evidence lens scene with stages and fallback. Verified: Chromium at 1280/360, keyboard tabs, loop stops off-screen, reduced motion, fallback. Superseded later the same day.
**Map and data section (agent M)** (undated)
- Three.js extruded provinces with data bars, 2D SVG fallback, on-demand rendering; ECharts removed. Verified: `map_shots.py`, `map_explore.py`; 0 frames when collapsed/idle; disposal counts. Ran on the round-1 demo DB.
**Seeker, LLM adapter, safety (agent B2)** (undated)
- Question-first form, answer under five headings with source tags, recovery states, versioned prompt `explain_v1`, output validator, `model_calls` table. Verified: 179 tests OK; `seeker_flow.py` incl. keyboard-only, CV failures, forced errors, double submit. Not verified: Anthropic provider against the real API.
**Evaluation tools (agent E)**
- Draft tasks and rubric, seeded block assignment, study and scoring pages, formal-mode gate, power and analysis scripts. Verified: 181 tests OK; 8 scripted simulated participants and 3 raters in the browser; formal mode refused. No approval, preregistration or real participants.
**Automation (lead)**
- Quota-aware scheduler `automation/`, paused by default. Verified: 44 simulated tests; one real batch (`once`, T01). Not verified: utilization scale, real usage-limit hit, multi-batch loop.
**Hero redesign and nebula (lead)**
- Perspective scene, 5,400 particles, glass lens, English-only hero; persistent nebula; fix for a negative first-frame dt that left particles invisible. Verified: Chromium screenshots (software WebGL), reduced motion, fallback; 189 tests OK. Not verified: real GPU. `hero_check.py` left stale.

## 2026-10-24
**Home rebuild (lead)**
- Full-viewport nebula hero, "how" cards, Evidence lens as its own section, data marquee, fields, FAQ, steps, footer; light palette. Fixed: marquee occupation count (limit=15), stuck lens fade. Verified: 0 CJK on home; 960 ads / 16 occupations / 32 provinces consistent; one WebGL loop at a time; no overflow at 360; reduced motion; 189 tests OK.
- Nebula motion and coverage; tri-state motion preference. Verified: pixel diff 1.84% (normal), 0% (reduced), 1.92% (forced on).
**Performance and search (lead)**
- `tests/browser/perf.py`, `docs/PERFORMANCE.md`; WebGL probe context leak fixed (made 8 / released 4 → 5 / 5). FTS5 trigram search with LIKE fallback. Verified: 205 tests OK; 4–10x faster at 200,000 ads with identical counts.
**Inner-page theme (agent P1)**
- `frontend/css/theme-x.css`; 360 px gutter restored. Verified: `theme_check.py` screenshots at 1280/360, no console errors, no overflow. Not verified: screen reader, Firefox/Safari.
**English labels (agent P2)**
- English occupation/province/source labels; Explore occupation dropdown; evidence `[object HTMLElement]` bug fixed. Verified: `labels_check.py` visible CJK outside evidence → 0 on checked routes; 205 tests OK. Seeker page labels not changed.
**Live-demo cases (agent P5)**
- "Try a demo case" (six cases) and "Paste an ad to check" (`POST /api/paste/check`, in memory, not stored); contradiction/truncation wording in briefs. Verified: 205 tests OK (11 new); `demo_cases.py` at 1280/360, 0 console errors, 0 px overflow.
**Documentation (agent D3)**
- README, `docs/DELIVERABLES.md`, `docs/COURSE_CHECKLIST.md`, `docs/PENDING_TEACHER.md`, this file. Not verified by running; written from the log.
