
## Agent C — requests / reviewer
Files: `backend/api_requests.py`, `frontend/pages/requests.js`, `frontend/pages/reviewer.js`, `tests/test_requests.py`, "requests / reviewer" block in `frontend/css/pages.css`.
- Design: request codes `AL-<year>-NNNN` allocated inside `BEGIN IMMEDIATE` with UNIQUE(code) retry; only sha256 of the owner token is stored. Seeker lookups return 404 on wrong token (no existence leak). Seeker responses are built from `published=1` messages only; one editable draft row per request, deleted on publish. Reviewer endpoints call `require_reviewer` before parsing the body. No schema change: the optional neutral rewrite suggestion is stored in `messages.to_verify_json` as `{"items":[...],"rewrite":"..."}`. Profile is whitelisted (age, occupation, years_experience, skills, region, education, summary); evidence/scope stored verbatim and never updated. Transitions: info-request pending|needs_info -> needs_info; seeker answer needs_info -> pending; draft/publish from pending|needs_info; close from pending|needs_info|replied.
- Run: `.venv/bin/python -m unittest tests/test_requests.py` -> 11 tests OK (temp DB, real HTTP server on ephemeral port; covers 401s, cross-seeker isolation, draft never in seeker JSON, concurrent unique codes, validation, immutability).
- Run: server on port 8793 with temp DB; curl loop create -> reviewer list (401 without token) -> info-request -> answer -> draft -> publish -> seeker view (no draft text, kinds question/info_request/answer/reply) -> close: all as expected; server log contained no request text.
- Gaps: frontend never executed in a browser (no node/browser available); only a bracket-balance check and code review. Reviewer queue capped at 500 rows, no pagination. Demo token auth only. Seeker page (agent B) must call POST /api/requests and store `AgeLens.ownerTokens.add(code, token)`.

## Agent A (data): ageparse, evidence, importer, demo data

Files: backend/ageparse.py, backend/evidence.py, backend/api_data.py, scripts/import_csv.py, scripts/geo_table.py, scripts/make_demo_data.py, data/demo/demo_ads.csv + README.txt, tests/test_ageparse.py, tests/test_data.py.

Verified by running: `.venv/bin/python -m unittest discover -s tests` (57 tests OK at the time, all agents' tests included; test_ageparse 18, test_data 10); demo import into a temp AGELENS_DB (300 raw rows -> 292 unique, 8 duplicates; age_status explicit 143 / uncertain 24 / none 125); second run reported "already imported" (idempotent); server started on port 8791 against the temp DB and every /api/* data endpoint was curled (200s, 404 for unknown ad). data/agelens.db was not touched by tests.

Decisions / semantics
- Scope: `include_demo` omitted = real only, or demo if no real exists (`using_demo`); True = demo only; False = real only. Demo and real are never mixed.
- Per-ad max age = MIN(max_age) over its high-confidence terms (for range and max). Gender-split wording (男30岁以下，女28岁以下) is flagged low confidence -> 'uncertain'.
- age_status: explicit = high-confidence max/range, or min above 18; uncertain = wording present without a usable numeric limit (generations 85后, 年轻, 35岁左右, 不限年龄, bare 年满18周岁); none = no wording. 不限年龄 is stored as kind 'relaxable' with exception_text, so it counts under has_exception.
- Exceptions are only attached when the clause is not about 学历/经验/专业 etc.
- Stats endpoints return bare lists (same as the evidence functions); use /api/overview for the denominator.
- Additive indexes (created by the importer's ensure_indexes, no schema.sql change): ix_ads_demo_prov, ix_ads_demo_date, ix_ads_batch, ix_ads_city, ix_raw_batch, ix_terms_kind. No columns added. Idempotency uses the file SHA-256 stored in import_batches.log_json (status running/complete; an interrupted batch is deleted and redone).
- Dedupe key: normalised title + company + city + sha1(description); duplicates across files fold into the existing ad's duplicate_count while the raw row is kept in raw_ads.

Known gaps: not run on multi-GB data (design is streaming + chunked but untested at scale; `q` search is a LIKE scan, FTS5 would be the next step; by_province median loads one int per ad). server.py decodes raw non-ASCII query bytes as latin-1 (curl without percent-encoding gives mojibake; browsers are fine). The city table covers major cities/districts, not every county. Rules are heuristic; precision/recall on real ads is unmeasured.

## Agent D — home / explore / map
Files: `frontend/pages/home.js`, `frontend/pages/explore.js`, `frontend/js/map.js`, `frontend/js/charts.js`, `frontend/vendor/*`, `frontend/geo/*`, `docs/GEO_SOURCES.md`, "home / explore / map" block in `pages.css`. `index.html` untouched; map.js/charts.js/ECharts are injected as scripts on demand by the pages.
- Verified (port 8794, temp DB, demo CSV imported: 292 unique ads from 300 rows): `/api/overview`, `/api/stats/{provinces,max-age,occupations}`, `/api/provinces`, `/api/ads` respond with the shapes the pages read; filters (province, max_age_gte/lte, age_status, date_from, occupation) and page/sort change totals as expected; vendor, geo and JS files served with correct content types. GeoJSON parses; all 34 province names match `/api/provinces` exactly; 6 provinces have no demo ads (rendered as "no data").
- JS syntax: only a Python bracket/string balance check passed on all four JS files; no JS engine or browser was available.
- NOT verified: nothing was executed in a browser. Visual layout, ECharts map3D rendering, per-region `height` on map3D data (believed supported by echarts-gl, unconfirmed), hover/click, parallax, 360px overflow and the WebGL fallback were not observed.
- Gaps: key-city markers not implemented (no city aggregate endpoint; none invented). Reset view rebuilds the chart. GeoJSON licence unresolved (see docs/GEO_SOURCES.md).

## Agent B: seeker / evidence / CV / brief / LLM adapter

Built: `backend/cv.py`, `backend/brief.py`, `backend/llm.py`, `backend/api_seeker.py`, `frontend/pages/seeker.js`, `frontend/pages/evidence.js`, the "seeker / evidence" block in `pages.css`, `tests/test_brief.py`, `tests/test_cv.py`. No schema changes.

Endpoints: `POST /api/cv/parse`, `POST /api/brief`, `GET /api/ai/status`, `GET /api/seeker/aliases` (extra: English job word -> Chinese search word map used to suggest, not silently apply, a search term).

Verified (actually run):
- `.venv/bin/python -m unittest discover -s tests`: 57 tests OK at last run (includes other agents' tests). My tests use generated TXT, DOCX (python-docx), hand-built text PDF, blank-page PDF (scanned case), corrupt files, a 5 MB+ file and a DOCX zip-bomb; brief tests use a fake in-memory evidence module; llm tests use a fake provider.
- Server on port 8792 with a copy of `data/agelens.db` (demo data, 292 ads): `/api/cv/parse` returned fields for TXT, 415 for .png, 422 for a corrupt .docx; `/api/brief` for 38-year-old / Shanghai / 运营 matched 7 demo ads (5 explicit, 1 needing interpretation, 1 none), gave counts with denominators and the neutral "states a maximum of 32; you entered 38 ... ask how they are decided" sentences; a no-match query returned `insufficient: true` with no findings. `/api/ai/status` -> enabled false.

Not verified: the frontend was NOT run in a browser (no browser or node available). seeker.js/evidence.js were only checked by bracket-balance script and code review. Drag-drop, print layout, Markdown download and the request hand-off (`POST /api/requests`) UI have not been exercised end to end.

Design choices / gaps:
- CV files are never stored; no opt-in storage was implemented (stated in the UI). Confirmed fields are kept only in sessionStorage.
- No real LLM provider exists; `llm.enrich` is a no-op with the default disabled provider. Setting AGELENS_LLM_PROVIDER does not enable anything and status says so.
- Rules cannot read scanned PDFs (no OCR). Years-of-experience is taken only from explicit phrases, never from date ranges.
- Brief analyses at most 300 ads and reports truncation; fewer than 5 matched ads -> "insufficient evidence", no aggregate statements.

## Lead: integration and verification (2026-10-22)
Environment: Python 3.12.3, no Node; pypdf + python-docx in `.venv`. Browser checks used Playwright + headless Chromium installed in a throw-away venv outside the project (not a project dependency).
- Unit tests: `.venv/bin/python -m unittest discover -s tests` → 57 tests OK.
- Demo data imported: 300 raw rows → 292 unique ads, 8 duplicates (synthetic, flagged `is_demo`).
- Browser: home, explore, seeker, reviewer, requests loaded with no JS errors; 3D province map rendered (software WebGL). No horizontal scroll at 1280 and 360 px after the fixes below.
- End-to-end in a real browser: example question → search (7 ads) → rules-based brief → submit for review → request code stored in browser → reviewer (separate browser context, demo token) sees the request in the queue.
- End-to-end via API: create → reviewer 401 without token → info-request → seeker answer → draft → seeker response contains no draft text → publish → seeker sees `replied` → wrong owner token gets 404.
- Fixes found by testing: (1) reviewer token file was never created before first use → now created at server start; (2) Explore date-range input overflowed its column (pages.css); (3) literal text "null" appeared in search/brief areas because native `replaceChildren` stringifies `null` (seeker.js).
- Test requests created during verification were deleted from `data/agelens.db`; ad data kept.

### Not verified / known gaps
- Reviewer reply, info-request and My requests views were not driven through the browser UI (API only). Drag-and-drop CV upload, print layout, Markdown download not exercised in a browser.
- Mobile (360 px) checked for overflow only, not visually reviewed in detail. Safari/Firefox not tested with the 3D map.
- Hero callout partly covers the sample ad text; the 3D map is small inside its frame.
- Parsed snippets can include list numbering (e.g. "4、25~35周岁").
- Map extrusion height and echarts-gl licence unconfirmed; GeoJSON licence unresolved (see docs/GEO_SOURCES.md) — local demo use only.
- No real recruitment CSV has been imported; parser accuracy on real ads is unmeasured. No real LLM provider; AI is disabled by design.
- Query-string bytes that are not percent-encoded are decoded as latin-1 (browsers percent-encode, so unaffected).
- Reviewer queue capped at 500 rows, no pagination. Auth is demo-grade.

## Agent D2 (course docs), 2026-10-23
Files written: docs/COMPETITORS.md, docs/BUDGET.md, docs/COURSE_CHECKLIST.md, docs/DEMO_SCRIPT.md, docs/PENDING_TEACHER.md. No code touched; no app run in this task.
- Verified online (official pages, fetched 2026-10-23): Textio home, /products/library, 2020 blog on age graph and age phrase highlights; LinkedIn help page on job search and alerts; Claude pricing (claude.com/pricing); OpenAI API pricing (developers.openai.com/api/docs/pricing).
- NOT verified: Applied's own product description (app.beapplied.com is a login app with no readable text; appliedhq.com is a domain-for-sale page; only third-party search summaries were seen); Textio's current age features beyond the 2020 post (/products/job-posts missing); any LinkedIn age-wording or AI-match feature; ChatGPT consumer pricing (HTTP 403).
- Budget: incurred spend left blank for the team; no paid API has been connected by the build.
- Course checklist statuses reflect the repo on this date; most round-2 artifacts did not yet exist (docs/ had no EVAL_PROTOCOL, MODEL_CONFIG, LITERATURE; tests/browser and docs/screenshots empty) so are marked planned. Demo click paths are written from round-1 UI and not rehearsed.

## Round 2 · agent L (literature + About) · 2026-10-23
Implemented: `frontend/pages/home_literature.js` ("Why it matters", id literature, order 20), `frontend/pages/about.js` (#/about "Method and sources"), `frontend/figures/feng2026_fig1_redrawn.svg`, `frontend/css/literature.css`, `frontend/css/about.css`, `docs/LITERATURE.md`, `tests/browser/lit_check.py`.
Verified (real fetches): Feng et al. NBER WP 35709 — NBER page metadata and the full 43-page PDF read (pdftotext; Figures 1-2 rendered and looked at); authors confirmed; Fig 1 estimates (theta -0.161/-0.062/-0.050, pre-limit means 0.949/0.323/0.365) match the text's 17% / nearly 20% / 13.7%. Lin (2025) — DOI resolves via chndoi.org to CNKI; title, author, pages and Chinese abstract read on the CNKI overseas page; full text NOT accessible (CNKI download/login; a PKU-hosted PDF found by search returned 404). So Lin is abstract-only and its card is a "To be verified" state with no figure and no invented content.
Figure: one figure only (Feng Fig 1, redrawn; bars computed from printed estimates, no digitisation, CIs not reproduced). A second figure for Lin is NOT delivered because the paper's figures could not be read.
Browser: Playwright at 1280 and 360, home literature section (closed and expanded) and About; 0 console errors, 0 px horizontal overflow; screenshots in docs/screenshots/lit/. At 360 the figure scrolls sideways inside its own frame (min-width 480px) so labels stay legible; the numbers also sit in a table inside the expandable note. First draft had overlapping SVG footnotes; fixed after viewing.
Frontend-design applied: quiet single-column text with ruled top borders instead of a card kit, no eyebrow caps, status pills used only where they carry verification meaning, tokens only.
Planned/blocked: someone with CNKI access must verify Lin's full text (sample: census vs 1% survey, outcome definition, figure number) and choose a figure to redraw. Server on 8803 (temp DB copy) was stopped.

## Round 2 - Agent C2 (requests / reviewer)
Files: backend/api_requests.py, frontend/pages/requests.js, reviewer.js, css/reviewer.css, tests/test_requests.py, tests/browser/review_loop.py, docs/screenshots/review/*.
Implemented
- Server: `X-Idempotency-Key` on POST /api/requests (same key+content -> 200 `{code,duplicate:true,token:null}`; same key, different content -> 409; key stored hashed); 30 s identical-content guard -> 409 `{duplicate:true,code}`; consent recorded (`consent` in request JSON; profile cut server-side to consented fields); tables `request_events` (role/status/time, no body text) and `request_meta` created in register() (no schema.sql change; legacy requests get a backfilled `created` event); events + consent returned to both views (`draft_saved` event hidden from seeker); reviewer list `limit/offset` (default 25, max 100) + `matching`, `has_more`, per-status `counts`; 413 (body 3 MB create / 96 KB actions, 400 KB per evidence item), 429 (40 creates/answers per minute per process, 10 wrong reviewer tokens per minute), clearer 401/404/409 messages.
- UI: restyled to white/blue; "Demo · Synthetic data" badge; timeline, consent block, collapsible evidence; recovery panels (no owner key, wrong key, unreachable server with Try again, expired/invalid reviewer token -> sign-in with message); empty states with actions; seeker answer draft kept in sessionStorage; reviewer: info request, save draft, inline confirm before publish/close, unsaved reply text kept across re-renders and a sign-in detour, queue pagination. Honest demo-grade auth notice on sign-in and in the workspace header.
- frontend-design / web guidelines applied: tokens only, visible focus, labels bound to inputs, aria-live status lines, aria-busy on saving buttons, no blocking confirm() dialogs, 360 px single column.
Verified (real runs)
- `.venv/bin/python -m unittest discover -s tests`: 67 tests OK (test_requests.py now 21; new: idempotency, window guard, concurrent same key, consent, events/no body text, pagination, size/count limits, 429, draft never leaks).
- Real Chromium via tests/browser/review_loop.py on port 8805 (temp DB): 37/37 checks - full loop (API-created request, reviewer asks info through UI, seeker answers through UI, draft saved, seeker has no draft text/event, publish with confirm, seeker sees only published reply, close), network-failure on publish keeps text, expired + mid-session token, no-key and wrong-key browsers, empty list, unreachable server + retry, no console errors, no horizontal overflow at 360/1280. Screenshots viewed; fixed a stray "null" in the queue and an oversized status badge (class clash).
Gaps: seeker submission UI (agent B2) not driven by me - request created through the API; a lost response to an idempotent retry cannot return the owner token (only a hash is stored); rate limits are per-process memory; reviewer token is shared demo auth with no expiry (expiry simulated by invalid token); published replies cannot be edited; no search/filter beyond status in the queue.

## Round 2 - Agent A2 (data / simulation)

Implemented and verified (real runs):
- `backend/datasource.py` (new): `DataSource` interface, `CsvSource(path, mapping)` (the round-1 reader logic moved here), `SimulatedSource(seed)`. `scripts/import_csv.py` now has `import_source(src)`; `import_file(path)` is a thin wrapper (tests unchanged). New CLI: `--source sim [--seed N]`.
- `scripts/make_sim_data.py` (generator `sim-1.0.0`, seed 20261023): 960 unique + 58 duplicate rows, fictional companies, 16 occupation groups, 32 of 34 provinces (澳门, 台湾 none; 青海 2, 西藏 1, 宁夏 1 sparse). Outputs `data/sim/{sim_ads.csv, sim_ads.meta.json, cases.json, README.txt}`. Determinism: two runs gave the same sha256 `b5a229ea...a528323` for the CSV (cases.json/README/meta identical too, compared by sha256sum).
- `backend/ageparse.py` `age-rules-2.0.0`: `age_class` per term and ad, kind `preference`, truncation detection (no cap invented), conflict detection (both terms kept, low confidence, flag `conflict`), `flag` per term. Fixed an old quirk: list markers like `3、` no longer end up inside snippets before a number. Parser vs generator intent on the 960 ads: all scenario labels map to the expected class (this is self-consistency, not accuracy on real text).
- Additive DB columns (no schema.sql edit), added by `evidence.ensure_columns` guarded by PRAGMA table_info, old rows back-filled once: `ads.age_class`, `ads.conflict`, `age_terms.age_class`, `age_terms.flag`, index `ix_ads_class`. Tested on a round-1-shaped DB.
- API: `age_class`/`conflict`/`label` on ads, `age_class`+`flag` on terms; `/api/stats/provinces` adds `age_wording`, `age_wording_share`, `age_class_counts`; `/api/overview` adds `data_version`, `simulated`, `label`, `age_wording_count/share`, `age_class_counts`, `conflict_count`, `truncated_count`; new filters `age_class`, `conflict`; `/api/ads` and batches carry `label`; `GET /api/status` (data part from the latest batch's source metadata; model part from `llm.status()` if it has `connected`, else `{connected:false,label:"Template demo"}`). `using_demo`/`is_demo` kept.
- `scripts/reset_sim.py --db PATH [--yes]`: deletes only is_demo=1 rows; `--db` mandatory; dry run by default; refuses non-AgeLens or flag-inconsistent DBs. Tested on temp DBs only. NOT run on data/agelens.db.
- Tests: `.venv/bin/python -m unittest discover -s tests` -> 145 tests OK (all agents). New: parser classes/preference/truncated/conflict/non-age phrases; generator determinism; counts overview == sum(province) == search totals for 10 filter sets; HTTP handler parity; status + llm fallback; old-DB migration; reset_sim.
- Server on port 8807 with a temp DB: /api/status, provinces, overview, ads (+ filters age_class, conflict), ads/<id>, stats/max-age, stats/provinces, stats/occupations, batches all 200; unknown ad 404. Real counts: explicit 415 / uncertain 238 / none 307; age_class hard_cap 193, cap_with_exception 112, preference 72, range_or_min 110, ambiguous 116, none 357; conflicts 44; truncated 27; 32 provinces, sum of province ads 960.

Known gaps: simulated phrasing equals the phrasing the rules know (no precision/recall claim); sim age-wording share (68%) is a generator setting; 不限年龄 ads are age_class `none` but status `uncertain`; truncated exception clauses after a complete cap still read as hard_cap; 15 GB path not run; no FTS yet. data/agelens.db still holds round-1 demo rows until the lead runs: `.venv/bin/python scripts/reset_sim.py --db data/agelens.db --yes && .venv/bin/python scripts/import_csv.py --source sim` (with AGELENS_DB unset or pointing at data/agelens.db). Docs: docs/SIMULATION.md, docs/REAL_DATA.md.

## Agent H (hero, steps, FAQ) — round 2
Implemented: frontend/pages/home_hero.js, home_steps.js, home_faq.js, frontend/js/lens.js (ES module, lazy `import('../js/lens.js')`), css/hero.css, tests/browser/hero_check.py.
- Hero: copy left, "Evidence lens" scene right (Three.js orthographic, px units). Desktop 900 particles + 80 thin lines + 6 decorative ad-fragment textures + translucent lens; mobile/coarse-pointer 300 / 28 / 4. Four blended layouts (scatter, halo, text rows with condition+exception clusters linked, funnel to three lanes). Intro plays once per page load (scatter to halo, ~3 s). Bounded mouse response (22 px max push, 9 px parallax). Real HTML text overlay: tablist (click, arrows, Home/End, aria-selected, roving tabindex), tabpanels, aria-live caption, fictional 38-year-old procurement example, ad text 申请人年龄一般在35岁以下，特别优秀者可适当放宽 with bracket linking condition and exception, badge "Illustrative example". Local "Pause motion" button uses AgeLens.motion. Scroll recede = transform/opacity via CSS var. Fallback static SVG when WebGL/import fails. Registered with AgeLens.gfx ('hero'); disposal via AgeLens.onLeave. Idle (settled, no pointer) throttles to ~11 fps.
- Design plan (frontend-design): one bold element (scene), quiet copy; system-ui scale; no eyebrow caps, no card kit; steps are a genuine sequence so numbered, thin line only. Web guidelines applied: button/anchor semantics, visible :focus-visible, aria-live caption, no transition:all, transform/opacity only, reduced-motion honoured, curly quotes, text-wrap balance, decorative canvas/SVG aria-hidden.
Verified (real headless Chromium, software WebGL, port 8801, screenshots in docs/screenshots/hero/): no console errors from hero code at 1280 and 360; no horizontal overflow at 360/1280 (also with fallback); keyboard Arrow/End/Home switching works; hero loop stops when scrolled to #steps and restarts on return; stops on route change and when motion paused; reduced-motion emulation renders static frames (5 frames, loop never runs); forced fallback (three import aborted) shows title, buttons and working stage text; "See how it works" scrolls to #steps. Cost (SwiftShader, NOT a GPU): about 0.34 ms JS submit time per frame, ~176 frames in 3 s incl. pointer movement; GPU/raster time not measured; no FPS claim.
Known 404 in console: /api/status (not yet provided by A2; not hero). Gaps: not tested on a real GPU, Safari/Firefox; Chinese glyphs in canvas fragments depend on installed CJK font; stage-3 funnel is simple; steps/FAQ copy not user-tested; no CJK text selection test beyond HTML.

## Round 2 · agent M (map/data section)
Implemented: pages/home_data.js (overview tiles + collapsible "Explore the regional map", lazy, aria-expanded/controls, disposed via onLeave); js/mapcore.js (NEW shared file: Albers projection, metric model, UI controller, legend, detail panel, region table); js/map3d.js (Three.js, extruded real provinces with constant 0.6 thickness, data bars, on-demand rendering, OrbitControls, HTML labels/tooltip, keyboard, dispose); js/map2d.js (SVG fallback, auto on no-WebGL/context-loss + 3D/2D toggle); explore-map.css rewritten (hero rules dropped: hero.css owns them); charts/explore restyled (blue palette, "Demo · Synthetic data" badge). Removed legacy js/map.js and vendor/echarts*. Frontend-design/web-guidelines applied: quiet white/blue panel, no decorative motion, focus-visible, labelled controls, aria-live, no scroll hijack (wheel zoom only when map focused or Ctrl/Cmd), touch-action pan-y.
Verified (tests/browser/map_shots.py, map_explore.py; headless Chromium, SwiftShader software WebGL, port 8802, copy of round-1 demo DB): no horizontal overflow at 1280/360; selection by click/dropdown/keyboard; 2D forced by disabling WebGL; context loss -> 2D; 0 frames while collapsed, off-screen or idle; drag of 20 moves = 85 frames; geometry build 57-80 ms; JS render-call ~1.4 ms avg (SwiftShader, NOT representative of a GPU; no FPS claim); dispose: 70/70 geometries, 159/159 materials freed, renderer.info geometries 69->0, no canvas left. Console: only 404 for /api/status until A2 lands it.
Not verified/gaps: simulated data from A2 (used round-1 demo DB; age_wording computed from explicit+uncertain fallback); real touch devices; unmatched-region state only exercised in code, no real unmatched name exists (34/34 join); GeoJSON licence still UNCERTAIN.

## Agent B2 — seeker / LLM adapter / safety (round 2)
Files: backend/brief.py, llm.py, api_seeker.py (unchanged), backend/prompts/explain_v1.txt, frontend/pages/seeker.js, evidence.js (badges/error state), css/seeker.css, tests/test_brief.py, test_llm.py, test_adversarial.py, tests/browser/seeker_flow.py, docs/MODEL_CONFIG.md, docs/ADVERSARIAL_CASES.md, docs/screenshots/seeker/*.
Implemented: question-first form (question, about you incl. optional education, CV drop zone with editable/confirmed fields, manual fallback); answer-first results under the five required headings, statements tagged Ad text / You said / Rules / Model inference with quotes (only if they occur literally in the ad), ad id, source, date, data version; Markdown (server-built) + print; Demo · Synthetic data / Template demo labels; empty-result broaden buttons; typed recovery states (unreachable, timeout 30s, 5xx, unreadable reply, 401/403 session, 409 duplicate); X-Idempotency-Key on POST /api/requests, button disabled in flight, 409 shows existing number. llm.py: status(), template/anthropic(urllib)/fake providers, versioned prompt, delimited data block, validator (ids, literal quotes, numbers from extracted terms, omitted exceptions, preference-as-cap, contradictions, legal/eligibility claims), model_calls table (no content; cost only from real tokens x configured price). Design skills applied: single quiet column, one blue accent, tokens only, no card-per-block, text labels not colour alone, visible focus, 360px stack.
Verified: `.venv/bin/python -m unittest discover -s tests` -> 179 tests OK (mine: brief 11, llm 21, adversarial 15). Real Chromium on port 8804 (copy of round-1 demo DB, 292 ads; A2's simulated data had not landed): keyboard-only completion, set_input_files and dispatched drag/drop CV, corrupt/png/zip-bomb CV failures, empty result + broaden, forced 500/garbage/abort/401 on API with retry, double click on submit (1 POST with idempotency key), mocked 409 showing AL-2026-0042, Markdown download contents, print view, no horizontal overflow at 1280/360, 0 JS errors (8 console lines are Chromium's notes about the deliberately forced non-2xx responses). Screenshots reviewed; fixed: links rendering as URLs (nested array), literal "null" in review box, "required" wrapping, missing quotes (search summaries lack text -> ads' text now loaded).
Not verified / gaps: Anthropic provider never run against the real API (mock only); the idempotent/409 server side is C2's and was only tested with a mocked response; real printing to PDF not done (print CSS inspected via emulation); data/sim/cases.json absent so adversarial cases are my own; validator is regex-based; select type-ahead with Chinese labels not tested by keyboard (arrow keys used).

## Agent E (round 2): evaluation tools (2026-10-23)
**Implemented.** `data/study/tasks.json` (4 fictional tasks, rubric with severe-error types S1-S4, 6 frozen calibration examples, consent DRAFT text; version tasks-v0.1-draft, status DRAFT/not frozen); `backend/study_arms.py` (template aid, SimulatedProvider, thin wrapper over llm.status()/get_provider()/validate_output with try/except so B2's rework will not break it); `backend/api_study.py` (tables created lazily with CREATE TABLE IF NOT EXISTS in the shared DB: study_settings, study_participants, study_task_runs, study_scores, study_calibration — additive, schema.sql untouched); `frontend/pages/study.js`, `score.js`, `css/study.css`; `scripts/power_analysis.py`, `scripts/analyze_study.py`; `data/study/{scoring_template.csv,EXPORT_SCHEMA.md,power_results.json,power_table.md,simulated_example/}`; `docs/EVAL_PROTOCOL.md`, `docs/PREREGISTRATION_DRAFT.md`; `tests/test_study.py` (20 tests), `tests/browser/study_flow.py`, `study_timeout.py`.
**Verified (actually run).** `.venv/bin/python -m unittest discover -s tests`: 181 tests OK (20 mine: formal refusal in 7 variants incl. approval-only, model-only, bad hash, invalid JSON; balanced seeded allocation 12/12 and block 2/2 reproduced from the documented seed; blinding; calibration gate; R3 only on disagreements; no score edits; missing=not usable; withdrawal deletes text; export has no free text; simulated/formal separation). Real browser (Playwright/Chromium, server on 8806, temp DB copy): 8 simulated participants through the UI (4 per arm, keyboard-driven consent/Begin), R1 and R2 each scored 32 items, 4 disagreements adjudicated by R3, operator desk refused formal mode with visible reasons, exports downloaded, analysis script run on the export. 0 console errors (the expected 403 refusals are filtered), no horizontal overflow at 360. Screenshots in `docs/screenshots/study/` (I viewed assisted task 1280, template task 360, scoring item 1280, operator 1280/360). Bugs found by browser and fixed: `h('tag#id')` does not set ids in AgeLens.h (textarea missing); countdown timer never ran because show() cleared it right after it was created (found by study_timeout.py, now auto-submits at 0 with timed_out flag); `.section` shorthand zeroed `.wrap` side padding on mobile; long filename caused 2 px overflow at 360.
**Power headline (simulation, assumptions unverified, no pilot).** N=24 (12/arm), baseline .35, task correlation rho .2: MDE for 80% power = +0.365 in mean usable share (about 1.5 of 4 tasks); power +.25 = 46%, +.15 = 20%. Range over baseline .20-.50 and rho 0-.4: MDE .28-.43. Welch is about 5 points optimistic vs the randomisation test (checked). For MDE ~.26 need N=48; ~.23 N=64. N=24 is a pilot, not a confirmatory test.
**Not done / gaps.** No model is connected: the assisted arm only runs with the labelled SIMULATED provider; the real-model path (study_arms.assisted_aid) is tested only with fake providers, not against B2's final llm.py. APPROVAL.json does NOT exist and was never created; no preregistration filed; consent and tasks await teacher/ethics approval. SIMULATED example results (`data/study/simulated_example/`) are scripted placeholder behaviour and mean nothing. Rubric has never been tried by humans on real answers; kappa unknown. Rater/operator access is a shared local token (demo-grade). No Safari/Firefox test. Screens not tested with a screen reader.

## Lead: quota-aware automation (2026-10-23)
**Implemented:** `automation/` (agelens_auto.py scheduler, statusline_capture.py, tasks.json, config.json, state.json, checkpoint.md, events.jsonl, README.md) + project `.claude/settings.json` (statusLine capture only). Native `/goal` does the work per batch; a local Python scheduler paces it. `/loop` not used (session-scoped, 1-min minimum, dies with the session). `--bare` and skip-permissions are never used (a test asserts it).
**Environment checked:** Claude Code 2.1.308, `authMethod: claude.ai`, subscription Pro, no ANTHROPIC_API_KEY/AUTH_TOKEN in the environment; tmux and `systemd --user` present, linger=no (no unit installed). `claude --help` of this version does not list `--max-turns` although cli-reference documents it.
**Verified (simulated):** 44 tests in tests/test_automation.py with fake clock/quota/executor — five-hour wait, 85% large-task rule, weekly exhausted/pacing/end-of-week reserve, stale + reset-passed handling, other-session quota jumps, bounded projection, interruption/resume without re-running done tasks, single lock, 3-failure pause, same-error and no-progress blocking, auth/permission handling, usage-limit parsing with and without reset time, unsupported-flag dropping, exit when queue empty or only human items remain. These are NOT real-quota tests.
**Verified (real, one batch, `once`):** see automation/README.md "Controlled real verification". Findings that changed the design: (1) statusLine does not run under `claude -p`; (2) the stream carries `rate_limit_event` with five_hour/seven_day utilization and resetsAt — adopted as the batch quota source, scale unconfirmed (×100 assumed, safe direction); (3) stale quota data would have deadlocked an unattended scheduler — fixed with per-window freshness, a 6 h weekly allowance, and lower-bound waiting.
**Bugs found by testing:** event() argument name clash; fingerprint counted scheduler-written files so "no progress" never fired; fresh-after-batch check too lax; scheduler idled forever when only human items remained.
**Not verified / planned / blocked:** utilization scale vs `/usage` (needs the user); `--max-turns` enforcement; behaviour on a real usage-limit hit (parsing is tested on invented message strings only); long-running tmux loop over multiple batches; survival across logout/reboot (not provided); weekly pacing against real multi-day use. Tasks T02–T06 are queued but NOT started: `start` is the user's decision. H01/H02 and teacher items are human-only.

## Lead: hero scene redesign (2026-10-23, after user feedback "too crude; higher resolution; cooler; no Chinese")
**Why it looked crude (observed in 2x screenshots):** the 3D area was only ~210 px tall (text card took the rest), 900 tiny grey particles, ad "fragments" were 384-px canvas textures (blurry) and Chinese, the lens was an empty ring and the caption overlapped the scene.
**Implemented (frontend/js/lens.js rewritten, home_hero.js + hero.css adjusted):** real perspective camera; 5,400 shader particles (1,900 on mobile/touch) as soft round sprites with depth fade, twinkle and bokeh discs; four morphing layouts (spiral galaxy → three orbits around the lens → rows of "text" on an ad sheet with condition/exception clusters → funnel into three lanes); an always-on ambient galaxy layer; glass lens (fresnel edge, sheen, scan band, dashed counter-rotating rings, sonar ripple) that glides to the evidence and MAGNIFIES the clause (English, canvas textures drawn at 2x, mipmapped + anisotropic, text auto-fitted to width); an arc drawn between condition and exception; English ad fragments and question chips clamped inside the scene; bounded pointer parallax + particle repel; panel colours now match the scene (condition = blue, exception = amber). All Chinese removed from the hero (scene textures, panel, fallback).
**Verified (real Chromium, software WebGL at deviceScaleFactor 2, screenshots viewed):** three stages render and read correctly; no console errors; no horizontal overflow at 360 px; reduced motion → loop not running (3 frames, unchanged after 2 s); blocking the three.js import → static fallback, tabs still work; hero loop still governed by AgeLens.gfx (one active loop). Mobile nav made one scrollable row (was 3 rows).
**Performance (software WebGL, NOT a real GPU — no FPS claim):** JS cost per frame 0.45–0.76 ms; sustained-motion frame interval ≈ 31–39 ms because SwiftShader rasterises on the CPU; adaptive resolution (every 30 animated frames, avg > 32 ms → pixel ratio −0.25, floor 1.0) fired once (2.0 → 1.75) and then held at 30.9 ms. Idle drift is throttled to ~30 fps. Desktop pixel ratio cap is now 2 (was 1.5 via gfx.pixelRatio) — a deliberate departure from the earlier cap, requested for sharpness; slow machines are protected by the adaptive step.
**Bugs found while doing it:** adaptive-resolution rule never triggered with alternating 33/50 ms headless frames (replaced by a 30-frame average); idle throttling was being counted as "slow" (now excluded); lens clip texture text was cut by the circular mask in a wide fallback font (now fitted); ripple was a heavy blurred ring in the intro (thinner, fainter).
**Not verified / open:** real GPU smoothness and the visual feel of the intro on the user's machine; tests/browser/hero_check.py is stale (expects its own server on 8801 and the old particle counts/Chinese) and was not re-run; one Chinese string remains on the home page — the literature card's citation title for Lin (2025), kept because it is the actual bibliographic title.

## Lead: nebula restored (2026-10-23, user: "why is there no nebula any more?")
**Cause:** the spiral galaxy layout was only the intro/start state; after morphing into the stage layouts it disappeared, and the "ambient galaxy" I added afterwards was too small/faint to see in my own screenshots — my earlier statement that a rotating nebula was always present was wrong.
**Fix:** persistent two-arm spiral with a dense core (≈70% of the non-text particles, tilted, centred by a new uGal uniform), radius-based colour ramp (deep blue core → violet arms → pink tips), larger/brighter core particles, plus three big soft spiral haze planes (canvas textures, slowly counter-rotating, drawn behind everything, faded while the ad sheet is shown). Verified in screenshots at stages 1–2 (galaxy/haze visible; sheet and lens text still legible). Software-WebGL run dropped the pixel ratio to 1.25 via the adaptive rule (3 steps); real-GPU look not verified.

## Lead: nebula polish + intro race fix (2026-10-23)
**Bug found (real, intermittent):** the first animation frame could get a negative dt (rAF timestamp earlier than the performance.now() taken at start). The intro clock then went below zero and never advanced, so uIntro stayed ≈ −0.003 and every particle was multiplied to alpha 0 — the scene showed haze but no particles/galaxy. Reproduced reliably in a time series, confirmed by reading the uniforms, fixed by clamping dt ≥ 0 and uIntro to [0,1]. This is a likely cause of "no nebula" on a real refresh too.
**Polish:** blob haze replaced by a nebula baked once on the GPU into a 1024² mipmapped texture (6-octave domain-warped fbm along the same two-arm spiral the particles follow, bright knots, thin dust lanes, deep-blue → violet → rose ramp, pearl core); two copies at different scale/depth for parallax; per frame it is just two textured quads. Spiral loosened (WIND 7.5) and arms tightened; steady rotation made rigid and shared (GAL_ROT) so particles, nebula and stars stay aligned; galaxy core moved up-right of the lens so it is not hidden; soft core bloom; 13 twinkling four-point stars (5 on mobile) riding the arms.
**Verified (Chromium, software WebGL, screenshots viewed):** all three stages; particles present over time; no console errors; mobile no overflow (1,900 particles, ratio 1.5); reduced motion loop not running; three.js blocked → static fallback with working tabs; 189 unit tests OK. Software-WebGL adaptive resolution settled at 1.5 (2 steps) — real-GPU sharpness and smoothness not verified.

## Lead: home page rebuilt in the reference site's style and motion, light palette (2026-10-24)
**Request:** "fully follow corexpertdata.com's style and dynamic effects for the home page, light colours, replicate the motion".
**Studied first (real Chromium, frames viewed):** native scroll (no hijack); full-viewport particle "nebula" canvas behind centred copy; gradient first headline line; gradient-border pill CTA with arrow; animated scroll cue (dot running down a line, "SCROLL"); pointer glow that lights nearby particles; transparent header that frosts on scroll; sections with centred heads, three numbered glass cards with a soft glow underneath and a gradient border on hover; an auto-scrolling band of leaderboard cards; field cards with dot lists; testimonial grid; numbered-circle steps joined by a gradient line + CTA; footer with a particle wave. Staggered blur-to-sharp reveals.
**Re-implemented (own code, no copied JS/assets/brand/text):** js/nebula.js (70k-point dune + far "sky" sheet, value-noise vertex shader, lane-biased sampling, soft gaussian haze, pointer lift/glow, adaptive pixel ratio then adaptive particle count; 18k on mobile), pages/home_hero.js (new), home_how.js, home_marquee.js (all numbers from the live simulated-data API), home_fields.js, home_faq.js (boundary cards + FAQ incl. honest evaluation note), home_steps.js, home_footer.js (particle wave), css/home-x.css (scoped to body[data-route="home"]); app.js sets body data-route and a nav-scrolled class. The Evidence lens moved into its own section (home_lens.js) so the page still has an evidence-related interaction (course acceptance item); data overview/map and literature sections restyled, logic unchanged.
**Deliberately NOT copied:** the reference's testimonial grid (we have no real users; fictional testimonials are prohibited by the brief) — replaced by literature/evidence cards in the same visual language. Black theme replaced by a light palette as requested.
**Fixed along the way:** marquee showed 938 ads/15 occupations vs 960/16 elsewhere because /api/stats/occupations defaults to limit=15 (now requests the full list); lens section was stuck faded (old top-of-page recede logic); last Chinese text on the home page (Lin 2025 citation) replaced by a pinyin author name and an English title marked "translated by the AgeLens team" (original kept in docs/LITERATURE.md); automation `status` showed FRESH for a 26-hour-old reading (now per-window freshness).
**Verified:** home has 0 CJK characters; numbers consistent (960 ads, 16 occupations, 32 provinces) across marquee and overview; one WebGL loop at a time across hero nebula → lens → footer nebula (sampled every 300 px); no console errors; no horizontal overflow at 360; reduced motion → nebula not running, reveals fully visible, marquee static; three.js blocked → static hero with title visible; 189 unit tests OK. Software-WebGL screenshots only — real-GPU density/smoothness not verified (adaptive thinning drew 52.5k of 70k points in one software run).

## Lead: nebula motion + coverage (2026-10-24, user: "why is it static; make the nebula cover more")
**Cause checked:** desktop animations are enabled (gsettings enable-animations=true; no Firefox reduced-motion override), so reduced motion was not the cause; the field evolved at only ~0.05 noise periods/s, which reads as static. **Changed:** whole field streams sideways (wrapped), rolling waves, per-point drift, 2.8x faster morphing, slow camera sway; wider lanes, larger sky sheet (45% of points), wider span, lighter text mask; desktop 90k points (mobile 22k). Motion preference is now tri-state (auto/paused/on): when the OS asks for reduced motion the nav button reads "Play motion (system: reduced)" and can force motion on.
**Verified (pixel diff of a particles-only strip over 1.5 s, software WebGL):** normal 1.84% pixels changed, loop running; OS reduced motion 0% (static, as required); after "Play motion" 1.92%, running. One WebGL loop at a time; no console errors; mobile no overflow. Real-GPU look not verified.

## Lead: performance checks, WebGL context leak, full-text index (2026-10-24, "comprehensive polish" round)
**Performance (tests/browser/perf.py, docs/PERFORMANCE.md):** injected counters for requestAnimationFrame and WebGL contexts; measured one loop at a time (hero nebula / lens), 0 frames with no graphics on screen, map collapsed or idle, tab hidden; pause/play works. **Bug found and fixed:** `AgeLens.gfx.webgl()` created and leaked a real WebGL context on every call (4 per home visit; made 8 / released 4) — now probed once, cached, probe released (made 5 / released 5). Automation task T05 marked done after its acceptance commands passed.
**Search index:** FTS5 trigram index for `q` (backend/evidence.py, lazy + triggers, LIKE fallback < 3 chars); tests/test_fts.py (5 tests: equality with LIKE, plan uses index, short-query fallback, trigger sync, quote safety); scripts/bench_search.py: 4–10x faster at 200k ads with identical counts. Full suite 205 tests OK.

## Inner-page theme pass (agent P1, visual theme) — 2026-10-24
- Added `frontend/css/theme-x.css` (scoped `body:not([data-route="home"])`, so home-x.css stays sole owner of home). No JS/HTML/base/tokens/home CSS edited; per-area CSS files untouched.
- Inner pages now share the home background (#F6F7FC + very soft lilac/blue radial tints on a fixed pseudo-element), a sticky opaque-frosted header, medium-weight page headings (500, home scale) with ink-soft leads.
- Reading/form areas are plain white panels with hairline borders and a faint shadow: seeker form, seeker answer, evidence sections, about page, study/score cards. Glass-card language (gradient fill, gradient hairline border, soft blue glow) only on explore chart cards and the reviewer/score sign-in card; clickable list cards (`.rq-item`, `.rv-item`) get gradient border + 3px lift on hover. Non-clickable cards no longer lift.
- Buttons: primary = solid blue→indigo (#2563EB→#4F46E5, white text ≥5:1); secondary = home gradient-border pill; quiet = white hairline pill. Inputs white with #C4CBD8 border and a visible focus ring.
- Fixed a pre-existing layout bug: base `.section{padding:X 0}` wiped `.wrap` side padding, so at 360 px inner pages sat flush against the screen edge. Gutter restored (24 px, 16 px under 640 px). Removed the blue focus outline that showed around `<main>` after each route change (programmatic focus). Footer text is centred.
- Motion: one 0.5 s opacity/translate entrance per route render; off under prefers-reduced-motion and the Pause-motion toggle.
- Verification: `tests/browser/theme_check.py` (Playwright/Chromium, reduced motion) screenshots every inner route at 1280 and 360 px into `docs/screenshots/theme/`, incl. seeker after "Use an example" + "Read the evidence". Final run: no console errors, no horizontal overflow, nav sticky, keyboard focus outline 3 px. The first run found `[object HTMLElement]` text and 1478 px overflow on #/evidence (from a nested-array `kv()` in evidence.js); it was gone on re-run, fixed by a concurrent change outside this pass.
- Not verified: a real screen reader, Firefox/Safari rendering of backdrop-filter/gradient borders, signed-in reviewer/score views (needs tokens), filled request detail pages.

## P2 — English category labels (occupation, province, source) — 2026-10-24
- `frontend/js/labels.js`: added `.source()` ('合成示例数据' → 'Synthetic sample data') and `.orig(text)` (muted `span.zh-orig[lang=zh-CN]` for original values in evidence metadata lines). All 16 occupation values in the DB were already mapped.
- Explore: the province dropdown is English-only (sorted by English name, value = original Chinese name). The occupation filter is now a dropdown of the groups from `/api/stats/occupations?limit=200` (English text, original value), replacing the free-text 'contains' box. Chips, the scope line and chart bars show English; the keys sent to the API and written to the URL stay original (checked: `?province=%E5%B9%BF%E4%B8%9C&occupation=%E9%94%80%E5%94%AE`). List metadata: company (original, marked as evidence), English province plus muted original 'province city', English occupation and English source.
- Map (mapcore/map2d/map3d): the region menu, region table, detail heading, hover tooltips and unplaced-region note are English-only. The join still uses the Chinese canonical names internally.
- Evidence page: fixed an existing bug where `kv()` rendered `[object HTMLElement]` (nested arrays were not flattened). Occupation, location and source now show English with the muted original. Company, snippets, exception wording and the raw row are marked as original evidence.
- Requests/reviewer evidence cards use the same metadata line. The profile occupation/region go through the labels. charts.js: bar names get a `title` so labels cut off by the column width can still be read in full.
- New check `tests/browser/labels_check.py` (counts visible CJK outside `.orig, .ex-snip, .ex-ad-t, .ev-title, .rq-ev-title, .st-adtext, mark.age, .zh-orig`). Before → after: home map 3D 72→0, map 2D+table 142→0, explore 733→0, evidence 8→0 (the page was also showing `[object HTMLElement]`), requests 33→0, reviewer 33→0. The 'before' run already contained my mapcore/map2d/map3d edits, which I reverted temporarily for that run. Screenshots: docs/screenshots/labels/.
- Not changed (owned elsewhere): pages/seeker.js still shows Chinese region options, 'Region: 上海' / 'Title contains “运营”' scope items, a '上海 · 徐汇' city meta line and '合成示例数据' in the meta/refs lines (468 CJK chars after a sample search, most of them inside evidence quotes or titles). `#/about` has a Chinese citation (author/journal name, intended). Unit tests: 205 OK.

## 2026-10-24 — P5: live-demo cases and "Paste an ad to check"
Implemented
- Job Seeker page: "Try a demo case" (collapsed `details` under "Use an example") with six fictional cases that fill the form and run with the real backend: 1 procurement S01 (search), 2 prompt injection, 3 contradictory wording, 4 truncated text (2-4 via pasted text), 5 no-match search, 6 no model connected.
- "Paste an ad to check (optional)" + `POST /api/paste/check` (backend/api_seeker.py): same age rules and brief templates on one pasted ad, in memory only; limits 4000 chars / 64 KB; 400 empty, 413 oversize, 422 binary-looking. Labelled "Pasted text, not stored"; visible note that instructions inside ads are ignored, and instruction-like lines quoted as plain text. Not sendable for human review (not stored).
- backend/brief.py: conflict-/truncation-flagged terms no longer count as a stated max/min; contradiction is stated with both snippets (explicit, relates, cannot, ask); 年龄不限 no longer described as exception or preference. This also changes briefs for the 44 stored ads with conflict=1.
Verified
- Unit tests: `.venv/bin/python -m unittest discover -s tests` → 205 tests OK (11 new in tests/test_demo_cases.py: injection incl. all 10 simulated adversarial texts, conflict, two caps, truncation, empty, oversize, binary, non-string, HTML, not logged / not in DB file).
- Browser (Playwright, own server on :8815 with a DB copy): tests/browser/demo_cases.py runs every case by keyboard at 1280 and 360 → all checks passed, 0 console errors (one expected 422 network log from the deliberate binary paste is filtered), 0 px horizontal overflow. Screenshots in docs/screenshots/demo_cases/ were looked at; fixed an empty "This ad states ." sentence and 年龄不限-as-preference found that way.
Not done / gaps
- A connected model failing (API error) cannot be shown live without a key; unit tests only. Instruction detection is a regex for the note only, not a security boundary. Automated checks are not human observation.

## Agent D3 (documentation sync) — 2026-10-24
Files written: README.md (rewritten, 78 lines), docs/DELIVERABLES.md (new), docs/COURSE_CHECKLIST.md (refreshed), docs/PENDING_TEACHER.md (updated, items 1-12 kept, 13-14 added), docs/CHANGELOG.md (new). No code, tests or other docs touched.
- Sources: this log, the listed docs, and `ls` of every referenced path. One read-only check of data/agelens.db: 960 ads, all is_demo=1, batch sim-1.0.0-seed20261023. No tests or browser scripts were run by D3.
- Checklist: 36 rows — done and verified 11, implemented, unverified 10, planned 5, blocked/needs teacher 10. Rubric 9 vs 8 inconsistency still flagged.
- Re-checked this log for QA-agent entries (docs/UI_AUDIT.md, new browser tests) once: none present yet, so no status reflects them.
- Open: pitch document missing (dropped-since-pitch row); incurred spend blank; docs/screenshots/hero/ predates the hero redesign and tests/browser/hero_check.py is stale.

## Lead: nebula recoloured to the site palette (2026-10-24, "polish the nebula, consistent with the whole project")
**Changed (js/nebula.js, hero/footer rules in css/home-x.css):** palette now follows the site tokens — silver dust, project-blue (#2563EB) lanes deepening on ridges, violet (#7C5CFF) far sheet, ~4% rose/violet glinting sparkles echoing the headline gradient; atmospheric perspective (far = lighter, more silver); near-camera point growth capped and the near fade softened so the foreground stays quiet; haze tinted blue-violet; hero background tints and pointer glow moved from pink/lilac to blue/violet. Same shader drives the footer wave, so both match.
**Mistake caught:** the first recolour used a shader variable before its declaration, the program failed to compile and the hero showed no particles; my screenshot script was not printing console output, so it was visible only in the image. Fixed the order, and the screenshot script now reports console errors.
**Verified (software WebGL, screenshots viewed):** hero and footer render in the new palette; pixel-diff motion 1.45% in 1.5 s; OS reduced motion static, Play restores motion; one WebGL loop at a time; mobile no overflow; three.js blocked → readable static hero; no console errors. Ownership of nebula.js, home_hero.js, home_footer.js and the .xh*/.xf* CSS was taken back from the QA agent (message sent) before editing.

## Agent Q — QA + fixes (2026-10-24): seeker labels, e2e loop (T02), sweep (T03), UI audit (T04)
**Implemented**
- Seeker English labels (phase-1 leftover). In `pages/seeker.js`:
  - the region menu is English-only, sorted, with the original value;
  - match chips read "Region: Shanghai" and "Title matches Operations" (unmapped search text is quoted as `lang=zh-CN`);
  - card meta lines read "Shanghai 上海 徐汇 (muted .zh-orig) · date · Synthetic sample data · ID";
  - evidence refs use `labels.source`; the review preview shows the English region;
  - Chinese quoted inside demo notes and the term hint is marked `lang=zh-CN`.
  - Filters still send the original values.
  - `backend/brief.py` "You said: … looking in 上海" now uses the English province name.
- Layout:
  - demo-case buttons form an even grid at 360 px;
  - Explore's Apply/Reset share one row, and the date inputs are no longer clipped;
  - the Explore intro is `p.lead` (no visual change; the theme already styled it as a lead);
  - the study DRAFT badge got spacing.
- `about.js`: English citation for Lin (2025), with the original marked; the privacy line wrongly said a CV is stored if you choose to save it, now corrected.
- New tests:
  - `tests/browser/e2e_loop.py` (T02, 22 checks, own server on a free port 8822–8829 with a temp DB copy);
  - `tests/browser/sweep.py` (T03, 10 route states × 2 widths × 4 checks = 80);
  - `tests/browser/a11y_check.py` (scripted names/ARIA refs/contrast/focus/trap checks).
- Audit `docs/UI_AUDIT.md`: 6 high (all fixed), 8 medium (2 fixed; 2 are in lead-owned hero files), 9 low (1 fixed). The high fixes:
  - names for the Explore range inputs;
  - a date-input focus ring;
  - `AgeLens.h` now supports `#id` (this fixes the broken `aria-describedby="rvhelp"`);
  - tab roles replaced by `aria-pressed` buttons (reviewer, score);
  - the confirm bar returns focus on Cancel/Escape;
  - publish validation focuses the first invalid field.
  - Also added `scroll-padding-top` under the sticky nav and score-form error focus.
- I did not edit `nebula.js`, `home_hero.js`, `home_footer.js` or `home-x.css`.

**Verified (real outputs)**
- `unittest`: Ran 205, OK.
- `e2e_loop.py`: 22/22 passed. The seeker never sees the saved draft text, and only the published reply appears.
- `sweep.py`: 80/80 passed (0 console errors, 0 4xx/5xx, 0 overflow, 0 CJK outside evidence). Its first run failed on the about-page citation; fixed.
- `a11y_check.py`: 8 high findings before, 0 after.
- `perf.py` against my server on :8821: fails [] (software WebGL).
- `demo_cases.py` (against :8821): failed_checks [] and 0 console errors.
- `labels_check.py`: 0 CJK outside evidence on all routes.
- Screenshots in `docs/screenshots/e2e/` (10) and `docs/screenshots/sweep/` (20); I viewed the ones I fixed against.

**Not verified**
- No screen reader; no axe-core (nothing installed); no Firefox or Safari.
- The confirm-bar Cancel/Escape focus return was not driven in a browser.
- Gradient-text contrast on the home hero cannot be measured by script.
- `review_loop.py` was not re-run, because it hard-codes port 8805, outside my allowed range. `e2e_loop.py` covers the same loop.

## Lead: final integration of the "comprehensive polish" round (2026-10-24)
**Phase 1 (parallel agents):** P1 inner pages in the home design language (css/theme-x.css only); P2 English labels everywhere outside quoted ad evidence (js/labels.js + explore/map/evidence/requests/reviewer/study); P5 'Try a demo case' (6 live-demo cases incl. prompt injection, contradiction, truncation, no-match, no model) and 'Paste an ad to check' (POST /api/paste/check, in-memory, not stored or logged). **Phase 2:** Q full-site QA (e2e loop, sweep, a11y audit with all 6 high findings fixed, seeker labels, About-page CV privacy wording corrected); D3 docs (README, DELIVERABLES, COURSE_CHECKLIST, PENDING_TEACHER, CHANGELOG). **Lead:** perf checks + WebGL context leak fix, FTS5 search index (4–10x faster at 200k ads), nebula recolour, hero "See how it works" made a real button, SCROLL label contrast raised to 6.0–6.6:1 (headline gradient 3.6–4.5:1 is large text, passes 3:1), Explore dropdown label shortened.
**Re-run by the lead, all green:** 205 unit tests; e2e_loop 22/22; sweep 80/80; a11y_check 0 high; demo_cases 0 failed checks; labels_check 0 CJK outside evidence on 6 routes; perf no failures. demo_cases/labels_check initially "failed" only because they default to ports of servers that no longer exist; passed against a fresh temp server. Automation tasks T02–T06 marked done after their acceptance commands passed (only human items H01/H02 remain). Stale hero test archived to tests/browser/legacy/, old hero screenshots to docs/screenshots/legacy/; 26 delivery screenshots (desktop + mobile, @2x) in docs/screenshots/final/ via tests/browser/final_shots.py.
**Note:** a temp DB copy replayed a stale -wal file from an earlier test server, so one fictional request appears in the reviewer screenshot; the main data/agelens.db has 0 requests.
**Not verified:** screen reader / axe-core, Firefox/Safari, real GPU, human rehearsal of the demo script, any real model call.

## Lead: "still no motion" in the user's Firefox — diagnosed (2026-10-25)
**Tool added:** open `#/?diag=1`; after 6 s the page measures motion preference, OS reduced-motion, WebGL renderer, real rAF rate and nebula stats, shows them in a panel and POSTs them to `/api/diag` (written to data/diag.json; small, no personal data).
**Finding in the user's browser (Firefox 158, X11/Ubuntu):** `motionPref: "paused"` (the "Pause motion" choice had been stored in this browser's localStorage), so the nebula never started (frames 0); OS reduced motion was false, WebGL true; renderer "llvmpipe, or similar" = CPU software rendering; devicePixelRatio 0.70.
**Changes:** the hero now shows "Animation is paused in this browser · Play animation" (or the system-reduced-motion variant) whenever motion is off, and the nav button is highlighted when paused; the nebula detects software rasterisers (llvmpipe/SwiftShader/softpipe) and starts at 35% of its points with pixel ratio ≤ 1, thinning further to 15% if frames stay slow. **Verified (Chromium, user state reproduced via localStorage):** notice visible and nebula stopped while paused; one click → notice hidden, nebula running (153 frames in 2.5 s); software renderer detected, 31,499 of 90,000 points drawn; no console errors. Not verified: the look and frame rate inside the user's llvmpipe Firefox after pressing Play.

## Lead: nebula density + default motion + lens section removed (2026-10-26)
**User request:** nebula must animate by default (it only moved after pressing Play), density at least like the reference site, delete the three-stage demo (Evidence lens).
**Default motion:** the pause choice was stored in localStorage and silently persisted across visits (the user's Firefox had `paused` stored). Pause now lasts for the tab session only (sessionStorage); an old stored `paused` is migrated away on load; OS reduced-motion is still respected (with the "Play motion (system: reduced)" override). Verified by reproducing the user's stored state: motion pref → auto, nebula running, no paused notice.
**Density:** js/nebula.js rewritten — terrain noise, lanes, ridges and colour are precomputed per particle in JS (integer-hash value noise), built in chunks over the first ~24 frames, stored as two vec4 attributes; the vertex shader only does flow, two crossing waves, drift, twinkle and pointer lift. 320,000 points on desktop (80k mobile; footer 120k/40k); software rasterisers start at 60% (192k) and adapt down to ≥ 30%. Lower screen filled (near-biased ground sampling, shorter near fade). **Measured (SwiftShader, not a real GPU):** all 320k built within 1.5 s; 192k drawn at 39 renders/s; pixel-diff motion 5.58% in 1.5 s (was 1.45%); perf.py no failures; 205 unit tests OK.
**Lens section removed from the home page** (pages/home_lens.js moved to pages/legacy/, script tag removed, "See how it works" now scrolls to #how). Trade-off noted to the user: the course acceptance item "cover interaction relates to ad evidence" is now carried by the map/marquee rather than the cover. perf.py and final_shots.py updated (footer-vs-hero loop check replaces the lens check).

## 2026-10-26 · Agent MAP2: regional + industry map v2 (home "data" section)
**Implemented**
- Backend: `GET /api/stats/matrix` (`backend/evidence.py: matrix()`, route in `backend/api_data.py`). One grouped SQL query by province × occupation over the usual filters; each cell has ads, explicit, cap (hard cap + cap with exception), age_wording, with_exception, preference, n_max_age, median_max_age (from GROUP_CONCAT of per-ad max ages, so still one query). Row/column totals and grand total are computed in Python from the cells. NULL province/occupation stay as cells, so cells sum to `/api/overview`.
- Front end (`js/mapcore.js`, `map3d.js`, `map2d.js`, `pages/home_data.js`, `css/explore-map.css`): the map is open by default in the data section; WebGL is created only when the panel first scrolls into view (IntersectionObserver); "Collapse map" toggle (aria-expanded); "Explore the regional map" now expands and focuses the map. Five metrics (ad count, any age wording, explicit cap, mentions an exception, median stated max age; age measured from 18, as the legend says), each with its unit, denominator and a small-sample rule (n < 10 paler and flagged, n < 5 palest; thinner bars in 3D). Industry chips (English, "All industries" default) re-score every province. Spread panel (highest/lowest with n, range, which comparison set was used, caution when no region reaches 10 ads) + dot strip (one dot per region, roving focus, hover syncs the map). Detail panel with a per-industry mini-bar breakdown for the selected region (or all regions). Industry × region heatmap (top 12 regions by ads × 16 occupations) as a table of buttons with grid arrow-key navigation; hover highlights the province on the map, click sets industry + region. Top-10 ranking (reliable regions first) synced with map selection.
- Motion: intro once (provinces rise west→east, bars grow in rank order, labels fade in); keyed tweens for bar height/colour on metric/industry change (760 ms ease-in-out, rank stagger); hover lift + two-ribbon glow outline; selection = three pulse rings then a static ring + eased fly-to; Reset view tweens home. Idle "orbit" is a ±13° sway over one 36 s cycle, only when the map is the active gfx loop, motion allowed, and no input anywhere in the map panel for 8 s; any input stops it. Rendering is on demand otherwise. Reduced motion: no intro/tweens/pulses/fly/orbit (tween count 0, final state drawn at once). Keyboard (both engines, in mapcore): Tab to the map, ←/→ step provinces by rank, Enter selects, Esc resets, Shift+arrows rotate/pan, +/− zoom. 2D SVG fallback shares every panel; colour cross-fades via CSS, fly-to tweens the viewBox.
**Verified (this machine, headless Chromium, software WebGL/SwiftShader; not a real GPU)**
- `python -m unittest discover -s tests`: 210 tests OK (new `tests/test_matrix.py`, 5 tests: cells sum to overview totals, totals consistent with by_province, filters respected, empty scope empty, HTTP route).
- `tests/browser/map_v2.py`: all checks pass (every metric, Procurement + Healthcare, selection by map click / ranking / heatmap cell / keyboard, reset, dot hover sync, idle draws 0 in 1.5 s, 0 draws while collapsed, idle sway starts after the delay and stops on input, 2D fallback with WebGL disabled, 360 px no horizontal overflow, reduced motion, 0 console errors, 0 CJK characters in map UI). Screenshots in `docs/screenshots/map_v2/` (desktop @2x, mobile, 2D, reduced motion, intro and tween frame sequences), reviewed by eye.
- `tests/browser/perf.py`: exit 0 (map collapsed 0 rAF/s, expanded idle 0 rAF/s, drag 84 frames, contexts released on route change). `tests/browser/sweep.py`: 80/80.
- Under SwiftShader a metric tween drew about 17–27 frames in its ~1.1 s, so it is smooth-ish here; no frame-rate claim for real GPUs.
**Honest notes**
- Simulated data: 960 ads over 512 province × industry combinations, so most cells hold 1–5 ads. Regional differences within one industry are mostly small-sample noise; the UI says so (caution box, pale cells, ranking dividers). Median max age is 35 almost everywhere (range 35–38 among regions with ≥10 stated ages).
- Bug fixed during review: spread highest/lowest was taken from the tier-sorted ranking rather than by value.
- `perf.py` still passes; with the map open by default its "map_collapsed" step no longer measures a collapsed map (the button now expands/focuses), and the idle sway means a map left on screen without input will draw frames after 8 s for up to 36 s.

## Lead: map review after MAP2 (2026-10-26)
Restarted the main server (new /api/stats/matrix endpoint). Re-ran: 210 unit tests OK; map_v2.py 0 fails (temp server); sweep 80/80; perf.py no failures. **Found by looking at the screenshots:** heatmap numbers on small-sample (dashed) cells were grey-brown (#6B5B4A) on mid-brown fills and hard to read. Cell text colour is now chosen per cell from the WCAG contrast of its actual background (ink if ≥ 4.5:1, else white); small samples keep the dashed border. Measured lowest contrast over 175 filled cells: 5.33:1. map_v2.py re-run after the fix: 0 fails.

## Lead: white + blue + violet palette, Apple-style refinement, richer motion (2026-10-26)
**Palette (css/tokens.css rewritten):** greys after Apple (#FFFFFF / #F5F5F7 / #1D1D1F / #6E6E73), Apple blue #0071E3, violet #7B61FF, lavender #A98BFF; gradient blue → violet → lavender. All warm/amber/pink tokens now alias to violet (age-wording emphasis, Demo badge, exception highlight, "To be verified"), so every page follows without per-file edits; old blues replaced in lead-owned CSS; nebula's rose accent → lavender. Contrast computed: white on #0071E3 4.7:1 and on #6246EA 5.86:1 (button gradient); #7B61FF only for graphics/large text (4.2:1); headline gradient ends at #8E72FF (large text).
**Apple-style refinement:** frosted nav (saturate 180% blur 20px), gradient-fill pill primary buttons sitewide, 28 px card radius with whisper shadows, bolder tighter headings on home and inner pages.
**Motion (js/fx.js new + css/home-x.css):** pointer spotlight + gentle tilt (≤ 3°) on cards, rotating conic aura and one-shot sheen on primary buttons, one-shot shine across gradient headings when they appear, steps connector draws itself, numbered circles pop in, 2 px gradient reading-progress bar. Transform/opacity only; off for coarse pointers and under reduced/paused motion; no cursor trails and no buttons that follow the pointer (both excluded by the brief).
**Verified so far:** no console errors on home and seeker; tilt vars set on hover (--rx/--ry); seeker shows the violet Demo badge. The steps-line check was inconclusive because the map agent was rebuilding the section above it (layout shifting); re-check after the map agent finishes.

## 2026-10-26 · Agent VIS: map + charts recoloured to white/blue/violet, Apple-like finish, new motion
**Changed (mapcore.js, map3d.js, map2d.js, charts.js, explore-map.css; new tests/browser/palette_check.py)**
- Data scales now come from the tokens: ad count #EAF2FD→#0071E3→#1B3F9E; age-wording shares #F1EEFF→#7B61FF→#3B26B0; median max age #E8EFFC→#5B7FEF→#4A2FBF (sequential). They feed the 3D bars, 2D fills, legend, glass mini legend, dot strip, top-10 and detail bars, heatmap. Small-sample marks went from brown/amber to dashed violet. Explore charts use blue gradient bars, and the 35 highlight and the selected bar use the blue→violet gradient. Text on heatmap cells still comes from inkOn().
- 3D: soft silver provinces. Vertex colours run from grey at the base to white at the top, the tops get a faint north→south tint and the edges are hairlines. Province tops now take only a light tint (mix 0.8 white). Hover gets a blue outline; the selected province gets a blue→violet vertex-coloured glow edge plus a radial blue→violet halo that breathes three times and then rests. 2D: gradient selection stroke with a soft glow.
- UI: segmented controls with a sliding white indicator (clip-path transition), softer chips, glass tooltip and labels plus a glass mini legend on the stage, 18–28 px radii, hairline dividers, tabular numbers.
- Motion (all off under AgeLens.motion.reduced()): 3D bars use a spring (~7 % overshoot), and a light band runs up each bar after a change (one tweened uniform per bar, via onBeforeCompile). Top-10 rows and detail/Explore bars move by FLIP with overshoot growth (Web Animations, transform/opacity), and a CSS sweep runs on rank bars. On first view the heatmap cells fade and scale in on a diagonal stagger; on later changes the colours cross-fade (the old colour is an overlay that fades out by opacity). The Explore distribution grows from its previous heights.
- Also fixed: "1 ads" became "1 ad", and the count dot-strip caption no longer says "fewer than 1 ads". Renamed one class to `mp-xf` after it clashed with the footer's `.xf`, which gave heatmap cells a transparent background.
**Verified (headless Chromium, SwiftShader, own server :8851 on a DB copy)**: unit tests 210 OK; map_v2.py 0 fails (tween frames 20–31 per metric change, idle draws 0, reduced-motion tweens 0, 360 px overflow 0, 0 console errors); perf.py 0 fails (map idle 0 rAF/s, collapsed 0); palette_check.py exit 0: 0 warm hits over ~63k computed colours, 875 heatmap cells, lowest cell text contrast 4.54:1. Screenshots in docs/screenshots/vis/ (desktop @2x, 360 px mobile, metric_change_0–5 and explore_resort_0–2 frame sequences), reviewed by eye.
**Gaps**: the segmented indicator animates clip-path, not transform, so it is paint-only and not composited everywhere. The sweep and halo are tuned only under SwiftShader. Pale small-sample violet cells still look a little dusty. Not checked in Firefox or Safari (backdrop-filter has a -webkit- prefix and falls back to a white glass tint).

## Lead: final check of the white/blue/violet round (2026-10-26)
After the VIS agent (map/heatmap/charts palette, segmented controls, spring bars, FLIP re-ordering, diagonal heatmap fade): 210 unit tests OK; map_v2 0 fails; palette_check (map area) 0 warm hits; perf no failures (contexts released); sweep 80/80. **Site-wide warm-colour scan written by the lead** (every visible element's computed colours incl. gradient stops, hue 12–60°, saturation > 25%) over #/, #/seeker (with results), #/explore, #/evidence/<id>, #/requests, #/reviewer, #/study, #/study/score, #/about: 0 warm colours on every route. Steps connector confirmed drawing once the layout settles (earlier failure was the map section re-flowing during the check). Not verified: Firefox/Safari, real GPU, the user's llvmpipe Firefox frame rate with the new effects.

## 2026-10-27 · Premium polish from two independent reviews

- Two independent review agents (A: static visual design; B: motion, interaction, inner-page finish) audited every route at 1440 and 390 px using screenshots. Their findings were merged and implemented by two agents with separate file ownership (H: home; I: inner pages + nav/footer); the lead set the shared foundation.
- Foundation (lead): vendored Inter Variable (OFL, `frontend/vendor/inter/`, licence included) as the fallback after the Apple system fonts; one type scale (weights 400/500/600, h1/h2/h3 tokens); three radii (12/18/999); solid Apple-blue primary button tokens; `.section` uses `padding-block`, which fixes the missing side gutter on home Data/Literature (desktop and mobile).
- Home: removed button aura/sheen, heading shine, card tilt/spotlight/glow blobs, blurred reveals and the slow blurred hero intro (now ≤900 ms); uniform section rhythm with alternating #F5F5F7 bands; marquee replaced by a scroll-snap paddle carousel (3 cards, no clones, no clipped text); stat tiles with a clear number hierarchy; quieter heatmap; Apple-style footer; progress bar on home only. Map, heatmap, table and nebula kept on home, as the user asked.
- Inner pages: 48 px nav with an underline for the active link; one footer; two centred column widths (1120 data / 980 content); a control kit (selects, disclosures, 44 px inputs, invalid state, white spinner, skeleton loading); one "Demo · Synthetic data" label per view in Explore instead of one per card; operator/CLI text moved into "For operators" notes; friendly evidence labels; plurals; designed 404, empty and sign-in states.
- Tests updated where selectors were stale (labels_check: map open by default, rank buttons; seeker_flow: English region label).
- Verified: 210 unit tests OK; sweep 80/80; e2e_loop 22/22; map_v2, palette_check (0 warm, lowest contrast 4.54), perf, demo_cases, labels_check, seeker_flow with no failures; a11y_check 0 high-severity. Software WebGL only; Firefox/Safari and real GPUs not verified.
- Not changed: "Model not run — Template demo." keeps its capital T because the backend string and a unit test depend on it.

## 2026-10-27 · Sketchbook restyle after the user's reference site + map redesign

- User request: the map was "very ugly" — redesign it — and restyle the whole site after https://nonopanda20.github.io; then: keep the home nebula, in that style. This replaces the white/blue/violet Apple style and its "no warm colours" rule.
- Lead: new tokens (paper #FFF9F5, brown ink #4A3728, five pastel fills, darker text-safe accent inks so text stays ≥ 4.5:1 — the reference's pastel-on-white text is not copied), hard offset shadows, 2.5 px ink outlines; vendored OFL fonts Nunito, Patrick Hand, Press Start 2P (`frontend/vendor/fonts/`, licences included; downloaded once from jsdelivr, no runtime network); Inter removed. Shared spec handed to three agents with separate file ownership.
- Map (M): 3D provinces as paper cut-outs with pastel value tops, brown ink edges and an offset shadow plate; data pegs with ink outlines (peg height + colour = value, thickness = decoration, stated in the legend); stripes for < 10 ads in 3D/2D/heatmap; sketch panel UI, hatched ranking bars, long notes folded into "How to read this map". palette_check.py rewritten to check text and heatmap contrast (2,834 text elements, 875 cells, lowest 4.75); old map_shots.py moved to tests/browser/legacy/. Lead: map column sticky on desktop so the tall detail list doesn't leave a blank gap.
- Home (H): reference-style hero (hand-lettered title, badge, sketch buttons, live pixel stats, inline SVG doodles) over the kept nebula, recoloured to brown ink + pastel dust with normal blending and a text-clearing mask; all sections and footer re-skinned; back-to-top button.
- Inner pages + chrome (I): scalloped paper nav with book mark, canonical sketch components in base.css, all inner pages and states re-skinned; Explore chart (charts.js) in pastel/ink.
- Verified (lead re-run): 210 unit tests OK; sweep 80/80; e2e_loop 22/22; map_v2, palette_check, perf, demo_cases, labels_check, seeker_flow: no failures; a11y_check 0 high. Software WebGL in headless Chromium only; Firefox/Safari/real GPU not verified.

## 2026-10-27 · Map pins + richer loading intro

- Map: data bars slimmed into pins (stem radius 0.95 → 0.24 map units, ink silhouette kept), a toon-shaded bead head that stays round, and a small ink collar at the foot; low-n pins shrink as a whole; labels sit above the bead; user-facing "peg" wording → "pin". map_v2 / palette_check / perf re-run after the later intro change: no failures.
- Loading intro (`frontend/js/intro.js`, `frontend/css/intro.css`): once-per-session splash (book opens, "AgeLens" letters hop in, pastel confetti, sheet lifts away with a scalloped edge, ~1.7 s; decorative, aria-hidden, pointer-events none, any key/click/wheel skips); hero title letter-by-letter hop (h1 keeps its accessible name), underline draws, doodle inked stroke by stroke then coloured, accents pop, stats count up; section underlines draw on reveal and cards drop and settle; inner pages land like a sheet. All off under reduced motion.
- Bugs found while checking frames: two `animation` rules on the same doodle shapes replaced each other (outlines never drew) — combined into one rule; confetti and a rotated page-landing frame caused 1–2 px horizontal overflow at 360 px in demo_cases — splash clipped, rotation removed.
- Verified: sweep 80/80, a11y 0 high, perf / map_v2 / palette_check (lowest 4.75) / labels_check / seeker_flow / demo_cases no failures, e2e_loop 22/22, no console errors. Headless software WebGL only.

## 2026-10-27 · Map: pins replaced by value-height provinces

- User: the pins were still ugly — change the style. The 3D map no longer has bars or pins. Each province stands on the same paper base (1.1 units, no data) and rises above it by its value (largest = 4.6 units, proportional from zero; age metric from the age base as before); the top colour carries the same value; walls are the top colour a shade deeper, ink outline on the top edge. Small islets stay at base height so they don't become needles. Low-n regions keep the striped top. Selection ring, hover/selection ribbons and labels ride on the raised top.
- This changes SPEC2 §5's "province thickness is decoration; bar height carries data": height now IS the data, and the legend, the "How to read" note and the explanation all say so ("Colour and height above the paper base show the value").
- Verified: map_v2, palette_check, perf, labels_check: no failures; screenshots (desktop default/selected, mobile) checked.

## 2026-10-27 · Apple-style scroll effects on top of the sketchbook style

- New home section `home_statement.js` (order 15): a pinned statement (220 vh section, sentence sticks in view) whose words light up from pale to ink as you scroll; three key phrases get a one-stroke pink highlighter sweep. Copy is a plain description of what AgeLens does (no outcome claim).
- `fx.js` scroll layer (rAF, transform/opacity only): hero exit (copy drifts up/shrinks/fades, doodle parallax faster, particle canvas eases in), `[data-zoom]` panels (map panel, data carousel) grow 92 % → 100 % as they enter. CSS in `css/intro.css` section 5.
- Reduced motion: statement not pinned and fully lit, no hero exit, no zoom. Known trade-off: unlit words are deliberately pale until scrolled to.
- Verified: sweep 80/80, a11y 0 high, palette_check (0 low-contrast text, lowest cell 4.75), perf, map_v2, labels_check, demo_cases no failures, e2e_loop 22/22; frames checked at 1440. No console errors, no horizontal scroll.

## 2026-10-27 · Bolder scroll effects
- New decorative home section `home_ribbon.js` (order 17, aria-hidden): a giant lettered row and a tilted yellow tape row that slide in opposite directions with scroll and lean (skewX) with scroll speed, easing back once scrolling stops.
- Statement: words rise and come into focus (blur → sharp) as they light; three pastel blobs drift behind at different speeds (`--p` set by fx.js).
- Hero exit now also blurs the copy; `[data-zoom]` panels stand up from a 24° tipped-back 3D tilt (was a flat 92% zoom); section headings wipe up out of a slot; "how" cards and steps flip up in 3D.
- Fix during the round: ribbon rows first sized to their content (~14,000 px) so the −2° tape rotated off screen; rows are now limited to the column width.
- Reduced motion: ribbons still, words sharp and lit, no blur/tilt/wipe/flip.
- Verified: sweep 80/80, a11y 0 high, palette_check (0 low-contrast text, lowest cell 4.75), perf, map_v2, labels_check, demo_cases no failures, e2e_loop 22/22; frames checked at 1440 and 390 with no console errors or horizontal overflow. Lean strength under real trackpad/wheel input not measured (headless wheel gives small deltas). Not checked in Firefox/Safari or on a real GPU.

## 2026-10-27 · Fewer effects: statement and ribbon removed
- User feedback: too many effects; the full-screen statement felt abrupt. Removed the pinned statement section (`home_statement.js`) and the giant ribbon (`home_ribbon.js`), their fx.js code and CSS.
- The statement sentence now sits under the "How" heading as its lead paragraph (replacing the old subtitle, which said much the same); its three key phrases get the pink marker sweep once the heading is revealed.
- Kept: hero exit with blur, 3D stand-up of the map panel and data carousel, heading wipe, card/step 3D flip.
- Verified: sweep 80/80, a11y 0 high, palette_check (0 low-contrast text, lowest cell 4.75), perf, map_v2, labels_check, demo_cases no failures, e2e_loop 22/22; frames at 1440 and 390, no console errors or horizontal overflow.

## 2026-10-27 · Margin widgets: section rail + Quick check
- `js/sidekit.js` + `css/sidekit.css` (loaded after app.js / intro.css).
- Section rail (home only, ≥1280 px): dots in the left margin with a dashed spine; the current section is marked while scrolling; labels unfold on hover/focus (always for the current one at ≥1560 px); click jumps to the section and moves focus to its heading. Found by browser test: the first long smooth jump stopped ~2200 px short when the lazily mounted map entered view (no JS interference; reproduced with plain `scrollTo`). Fixed by re-issuing the scroll on `scrollend` if it stopped early (max 2 retries).
- Quick check (right-edge tab, all routes except `#/study` and `#/study/score` so the study is not influenced): paste one line of age wording; shows the rule class with a plain-English explanation, the verbatim quote (`lang="zh"`), ages and exception text. Never says whether someone qualifies; links to the Job Seeker for a full check. Esc/× closes and returns focus to the tab.
- Backend: `POST /api/age/check` → `api_seeker.check_age_line()`: rules only (`ageparse`, no model call), ≤300 chars, nothing stored or logged. 4 unit tests in `tests/test_demo_cases.py` (cap with exception, preference/none, rejects empty/long/non-text, injected instruction stays a verbatim quote and does not change the reading).
- Verified: unit tests OK; browser sweep 80/80, a11y 0 high, palette_check 0 low-contrast text, perf, demo_cases, map_v2, labels_check, seeker_flow no failures, e2e_loop 22/22; screenshots at 1440 and 390, no console errors or horizontal overflow.
- Mistake during verification: `tests/browser/study_flow.py` was run against the main server (8765) instead of a simulation-mode server on 8806 with a temp DB. It enrolled 8 SIMULATED participants (SIM-…, simulated=1) into `data/agelens.db` before timing out; no exports or screenshots were overwritten (their times predate the run). Not cleaned up: `/api/study/simulated/clear` would also delete all other simulated participants and all calibration rows, so this is left to the team. The DB now holds 24 simulated participants, 0 formal.

## 2026-10-27 · Optional accounts + project polish
**Accounts (implemented and verified locally).** `backend/api_accounts.py` (new): `POST /api/auth/register|login|logout|password|requests/link`, `GET /api/auth/me|requests`, `DELETE /api/auth/account`. Username + password only (any extra field refused, email/phone-like usernames refused, reserved names refused); scrypt N=2^14 r=8 p=1 with per-account salt; sessions are random bearer tokens stored as sha256, 14-day expiry, max 10 per account; same 401 message and dummy-hash timing for unknown user vs wrong password; limits: 10 registrations/10 min, 5 failed sign-ins per username/5 min, 30 failed/min overall (only failures count; new `Limiter.full()`); password change signs out other sessions; delete needs the password and unlinks requests (requests stay, the submitting browser can still open them). Tables created at start (`CREATE TABLE IF NOT EXISTS` accounts, sessions, account_requests; schema.sql unchanged). `api_requests.py`: `seeker_row()` lets `GET /api/requests/<code>` and `/answer` use either the owner key or a linked account session (same 404 otherwise); `POST /api/requests` links the new request when signed in and returns `on_account`; unused `owner_token()` removed. Reviewer endpoints unchanged; an account session gets 401 there (tested).
Frontend: `AgeLens.session` (localStorage `al_session` = token, username, expiry; never the password) and `AgeLens.api` adds `Authorization` automatically, clearing the session on a 401 from `/api/auth/*`; `er.data` now carries the server's JSON on errors (the Job Seeker duplicate handler already read `e.data` but it was never set). Nav link "Sign in" / username. `pages/account.js` + `css/account.css`: sign in / create account (show-hide password, plain-language facts), signed-in overview, keep this browser's requests on the account, change password, sign out, delete. My requests merges account and local requests, marks "On account", offers to link local ones; a linked request opens without the local key. Job Seeker confirmation says when a request is kept on the account. Docs: `docs/ACCOUNTS.md` (new), CONTRACT round-3 addendum, README, DELIVERABLES rows 6/6a.
**Verified.** `tests/test_accounts.py` 18 tests (hash-only storage, extra fields refused, bad usernames/passwords, case-insensitive uniqueness, register limit, login/logout, identical failure responses, per-username failure limit incl. blocking the right password during the window, successes not counted, bad/expired sessions, session cap, password change revokes other sessions, delete flow, linking needs the owner key and never moves another account's request, answer through the account, no reviewer access). Full unit run: 232 tests OK. `tests/browser/account_flow.py` (new; own server on a temp DB copy) 34/34 at 1280 and 360. sweep (now incl. `#/account`) 88/88, a11y_check 0 high, palette_check 0 low-contrast text, theme_check no problems, perf, demo_cases, map_v2, labels_check, seeker_flow (its 500 is a forced failure), e2e_loop 22/22. Screenshots viewed: `docs/screenshots/account/{signin_360,account_1280}.png`.
**Polish.** Stdlib AST check (no linter installed): removed unused imports (api_study `Path`, analyze_study `math`, import_csv `csv`/`os`, reset_sim `sys`, test_data/test_fts `sqlite3`/`os`) and dead locals (api_study `unresolved`, brief `used`, llm `version`); backend/scripts now report nothing. Quick check tab on phones became a bottom-left pill (the edge tab covered form fields at 360). README page map updated (Evidence lens section no longer on the home page; carousel, map prisms, section rail, Quick check, Account), browser-script table updated (isolated vs. shared-server scripts; legacy folder).
**Not done / found.** Not production auth: no HTTPS, no password reset, no third-party review; limits are per process. `frontend/js/lens.js` is referenced only by `pages/legacy/`; left in place. Main DB `data/agelens.db` holds 11 demo requests (is_demo=1) created today by browser scripts run against the main server (seeker_flow/demo_cases), plus the 24 simulated study participants noted above; not cleaned up (team decision). No accounts were created in the main DB.

## 2026-10-27 · Whole-project polish pass (screenshot review)
Reviewed every route's sweep screenshots at 1280/360 (cropped at full resolution) and fixed what was wrong:
- **Real bug: horizontal page scroll on the home page right after load** (456 px at 1280, 737 px at 360). The `[data-zoom]` 3D stand-up tilt made the data carousel wider than the page while it was still below the fold; earlier checks measured at the bottom of the page, after the panels had stood up, so they missed it. Fixed with `.home-sec:has([data-zoom]){overflow-x:clip}` (clip keeps the sticky map column working; map_v2 passes).
- **Real bug (mine, this round): "[object HTMLElement]" text** in the new reviewer preview caused 688 px overflow on Job Seeker. `AgeLens.h` flattened children one level only; it now flattens at any depth, so this class of bug cannot recur. New sweep check: no `[object …]`, `undefined` or `NaN%` in page text.
- Explore bar charts: occupation names were cut off ("Procurem…", "Customer …"); rows now put name + value on the first line and the bar below.
- Job Seeker: evidence references no longer break inside "Ad 2 · Shanghai · 2026-06-04"; "Preview of what the reviewer will see" is a label/value list instead of raw JSON; the pager is hidden when there is one page (Explore shows the count instead).
- Request detail: consent box text no longer wraps at 65ch inside the wide box.
- `tests/browser/sweep.py`: scrolls back to the top before the full-page home shot (the hero was captured faded by its scroll exit). The thin pink line across "How to use" in full-page shots is the fixed reading-progress bar, not a page defect.
Verified: sweep 110/110 (now incl. the text-leak check), a11y_check 0 high, palette_check 0 low-contrast text, theme_check no problems, perf, demo_cases, map_v2, labels_check no failures, e2e_loop 22/22, account_flow 34/34; unit tests 232 OK. Screenshots viewed after the fixes: explore charts, Job Seeker review panel, home hero.
Not checked: Firefox/Safari, a real GPU, a screen reader.

## 2026-10-27 · "Pause motion" removed from the nav
At the user's request the nav button is gone. Because the hero/footer animation runs continuously (WCAG 2.2.2 Pause, Stop, Hide), the same toggle remains as a quiet "Pause animation" text link in both footers (`AgeLens.motionToggle()`, `.motion-toggle`); OS reduced-motion is still honoured. perf.py now clicks `.motion-toggle`. Verified: sweep 110/110, perf (paused → loop stopped, play → running), a11y 0 high, theme_check no problems, account_flow 34/34.

## 2026-10-27 · Evaluation plan v2 (crossover) + simulated dry run
**Why.** The rubric's evaluation criterion (10 pts) requires that the pre-registered claim is what is tested, the threshold is applied as registered, and the target N is met or the shortfall reported. "Coherence" (12 pts) requires the evaluation to test the claim the design makes. The previous protocol (template vs model-drafted help) needs a connected model, which the project does not have, and AgeLens itself is not an LLM drafter. New plan `docs/EVAL_PLAN.md`: within-participant crossover, A = ad only vs B = AgeLens evidence check (the product's own rules-only output), 2 tasks each; 4 sequences AB/BA × task sets S1 {T1,T3} / S2 {T2,T4} in permuted blocks of 4; primary D = usable share B − A; threshold mean D ≥ +0.20 AND 95% CI lower bound > 0; target N = 24 (minimum 16).
**Implemented.**
- `brief.build_brief(allow_model=)` and `api_seeker.check_pasted(allow_model=)`, so the study aid stays rules-only even with a model connected (tested).
- `study_arms.no_aid()` / `agelens_aid()`.
- `tasks.json` v0.2-draft: `design` block, consent text updated. Backup of v0.1 in the scratchpad only.
- `api_study`: crossover allocation and task order, a per-task aid by condition, condition labels. Formal gate: a model is required only for the legacy design. Export v2 adds `condition`, `sequence`, `usable_share_A/B`, `diff_B_minus_A`, `meta.design`/`threshold`. The legacy `parallel-llm-v0` stays selectable (`DESIGN_OVERRIDE`).
- `study.js`: the two condition panels, intro and banner wording.
- `analyze_study.py`: crossover analysis (bootstrap CI, sign-flip test, paired t, threshold decision, order/carryover and period-1 sensitivity, per-criterion by condition, kappa).
- New `scripts/power_crossover.py`, output in `data/study/power_crossover.md`.
- `study_flow.py`: crossover-aware scripted writers (P_GOOD_A/B env); its rater sign-in clicked the new nav "Sign in" link and was fixed (`button:has-text`).
- Docs: EVAL_PROTOCOL and PREREGISTRATION_DRAFT are marked superseded; EXPORT_SCHEMA has export-v2 notes; README index updated.
**Verified.**
- Unit tests 242 OK: 20 legacy study tests pinned to the legacy design, plus `CrossoverTests`. CrossoverTests covers sequence balance per block, seed reproducibility, 2+2 in sequence order, real AgeLens aid on B and none on A, every task twice per condition per block, aid unchanged with a model connected, formal needing approval but not a model, the rater never seeing the condition, and the export difference; the scoring tests also run under the crossover.
- Power (4,000 trials/cell, assumptions only): N=24, +.25 → power .76, P(threshold met) .69 (parallel design .46 power); with +.10 carryover, P(threshold met) .48; no effect → .009. The t-shortcut agrees with the analysis's bootstrap threshold decision in 99% of 300 check trials.
- **Dry run (SIMULATED)**, isolated server 8806, temp DB copy with emptied study tables, main DB untouched:
  - 24 scripted participants via the real UI (6 per sequence); R1/R2 scored 96 each; R3 adjudicated 20; 0 unresolved; PROBLEMS none.
  - Analysis (built-in assumed +.25): A .583, B .750, D +.167, CI [−.042, .354], p .17, threshold NOT MET.
  - Outputs in `data/study/dryrun_2026-10-27/`. Screenshots of both condition panels viewed at 1280/360.
  - Dry-run server stopped by PID.
- sweep 110/110, a11y 0 high.
**Not done / needs people.** Teacher approval of design, claim, threshold, N, consent, seed and raters; a human pilot (2–3 non-team people) to check the 7-minute limit, the instructions and the rubric before freezing the tasks; recruitment; the actual study. The old `docs/screenshots/study/*assisted*`/`*template*` shots are from the legacy design (15:44 run).

## 2026-10-27 · Public demo with invite codes (accounts removed); prepared, not published
**Decision (user).** No sign-up; access to a public deployment only by invite code. Chosen defaults: the whole site behind the code; personal and shared codes; roles viewer and reviewer; Render free plan, native Python runtime (no Docker permission on this machine, so a Dockerfile could not be tested; Render's build and start commands are plain commands that were reproduced here).
**Removed.** The self-registration accounts added earlier today: `backend/api_accounts.py`, `tests/test_accounts.py`, `frontend/pages/account.js`, `css/account.css`, `tests/browser/account_flow.py`, `docs/ACCOUNTS.md`, `docs/screenshots/account/`. Copies are kept in the session scratchpad (`retired_accounts/`), not in the project. The local DB still contains the empty `accounts`/`sessions`/`account_requests` tables from earlier runs; nothing uses them.
**Implemented.**
- `backend/api_access.py`: invites in env `AGELENS_INVITES` (sha256 only), not the DB, because the free disk is wiped on restart. Sessions are hashed with a 14-day cap, limited by code expiry. Expiry and revocation are checked on every request. `max_uses` is counted in the DB, so on the free plan it resets on restart. Failed codes are limited per client (X-Forwarded-For) and overall, with one identical message for wrong, expired and used-up codes. Personal codes keep requests (`invite_requests`); shared codes never do.
- `server.py`: gate for all /api/* except health/status/redeem/signout when `AGELENS_PUBLIC=1`; 401 carries `invite_required`; a reviewer invite session passes `require_reviewer`; diagnostics off; no token file written in public mode; headers Referrer-Policy and X-Frame-Options always, plus X-Robots-Tag noindex and HSTS in public mode.
- `app.py --public [--host]`: refuses to start on incomplete config; rebuilds an empty DB from the seeded sim data; binds 0.0.0.0 on $PORT by default, or `--host 127.0.0.1` for rehearsal.
- Other: `scripts/invite.py` (new/list/revoke/env/secrets; local list `data/invites.local.json`, git-ignored, 0600); frontend `pages/access.js` + `css/access.css` (invite page before every route, nav chip "label · role", Reviewer link only for reviewer codes, status page with sign out) and the reviewer workspace opening without the token for reviewer codes; `render.yaml`; `.gitignore` extended (tokens, logs, invite list, scheduler run records, `.claude/`, lock file); requirements pinned (pypdf 6.21.2, python-docx 1.2.0); `docs/DEPLOY.md`.
- Stale tests fixed: `review_loop.py` expected `.rq-status.error` where the reviewer sign-in note uses `.field-err` (2 places; the UI was unchanged today, so this was already failing).
**Verified.**
- Unit tests: 240 OK (16 new in test_access).
- Clean-copy rehearsal: only git-publishable files (440), fresh venv with the pinned deps. `--public` refused without config (3 reasons listed); with config it rebuilt 960 ads and listened on 127.0.0.1 only (checked with `ss`); /api/overview gave 401 with invite_required; headers present.
- `tests/browser/public_demo.py` 33/33 at 1280/360 (own server on 127.0.0.1). Screenshots `docs/screenshots/public/` viewed: invite page 1280, reviewer 360.
- Local mode unchanged: sweep 110/110 (now with `#/access`), a11y 0 high, theme_check ok, e2e_loop 22/22, demo_cases, seeker_flow no failures, review_loop 37/37.
- Rehearsal servers stopped by PID; the main server restarted on the new code.
**Not done (needs the team).** Git identity and GitHub repository, Render account and blueprint, entering the three secrets, generating and sending real codes (DEPLOY.md steps 1-6). Not verified: the Render build itself, Render's X-Forwarded-For behaviour, outside load.

## 2026-10-27 · Open public demo (invite codes optional)
At the user's request the invite step is skipped for the first deployment. `--public` without `AGELENS_INVITES` = **open demo**: no gate (`api_access.gate_enabled()`); `/api/access/status` adds `invite`; redeem → 404. Reviewer/study tokens are optional on the host: unset → a random in-memory value at each start (nobody knows it, the desks stay closed, no token file is written). `check_config` now fails only on a malformed invite list or a too-short token. Frontend uses `access.invite` for the gate/chip and hides the Reviewer link on any public host unless signed in with a reviewer code; the access page explains the open demo. `render.yaml` no longer asks for secrets.
Verified: unit tests 243 OK (test_access 19: +open-demo tests: no gate, desks closed, no token file written, diag off; adjusted config-check cases). Open-mode rehearsal on 127.0.0.1 with a fresh DB and no secrets: 960 ads rebuilt, /api/overview 200, no gate, Reviewer link hidden, Quick check works, access page text correct, no console errors, 0 overflow at 1280/360, `data/reviewer_token` unchanged. Invite-mode browser rehearsal still 33/33; local sweep 110/110. Main server restarted on the new code.

## 2026-10-27 · Public demo live (open mode)
Deployed by the team on Render (free plan) from GitHub `nonopanda21/agelens`, commit 5a34daf: https://agelens-c8kj.onrender.com
Checked from this machine (read-only: nothing was submitted):
- API: /api/health 200 with 960 ads; /api/access/status reports public, no invite; /api/overview 200; reviewer API without a token 401; /api/diag 404.
- Headers: HTTPS (HTTP/2) with HSTS, X-Frame-Options DENY, Referrer-Policy no-referrer, X-Robots-Tag noindex.
- Real Chromium at 1280 and 390: home with all 9 sections and the map drawn; Explore, an evidence page, Job Seeker "Use an example" answer (5 sections), Quick check, My requests, About and Study load; no console errors, no 4xx/5xx, no horizontal overflow. Screenshots viewed (home 1280, Job Seeker 390).
- The instance was awake (first load 1.6 s); the free plan's sleep/wake delay and data reset on restart were not measured.

## 2026-10-27 · Pro stage 1: free features + paid-style full report, no payment, no API
User decision: stage 1 only, no model API. Defaults taken: 5 credits per code (`--credits`), human review stays free, reports only for searched answers (a pasted ad is not stored).
**Implemented.**
- `backend/report.py`: Word report from `brief.build_brief(allow_model=False)` plus dataset context. Contents: cover; summary numbers; five answer sections with verbatim quotes; region and occupation comparison; questions plus a draft message; evidence appendix; method. Captions separate the tables.
- `backend/api_pro.py`: Pro codes from env `AGELENS_PRO_CODES`, or locally `data/pro_codes.local.json`; hashed Pro sessions (`X-Pro-Token`); per-code credits; free `/api/report/preview`.
- `/api/report` returns 402 without Pro and 403 at 0 credits. The credit is taken in one IMMEDIATE transaction after a successful build (empty or failed reports are free). Limits: wrong codes 10 per client per 5 min, builds 20 per min.
- `scripts/pro_code.py` (new/list/revoke/env; the local list is git-ignored).
- Frontend: `AgeLens.pro`; `pages/pro.js` (free vs Pro table, code form, wallet, remove; `AgeLens.reportPanel` with the preview, code form, generate and download); "Full report · Pro" button on the Job Seeker answer; nav "Pro"; `css/pro.css`.
- `docs/PRO.md`; DEPLOY/README updated; sweep, a11y and theme route lists include `#/pro`.
**Fixed during testing.**
- test_pro first shared the suite's temp DB (other modules' ads) and found no matching ads in the full run; it now uses its own DB.
- UTC expiry date shown a day early in negative-offset time zones (pro.js, access.js).
- In the report rendered via LibreOffice, adjacent tables looked like one table and median ages were formatted inconsistently (35.0 vs 35); both fixed.
**Verified.**
- Unit tests 259 OK (16 new). Highlights: atomic last credit (4 concurrent → exactly one 200); outcome/legal phrases absent; every ad's age wording quoted; deterministic.
- Browser: pro_flow 27/27 (1280/360: two real .docx downloads, credits 2→1→0, disabled at 0); sweep 120/120; a11y 0 high; theme ok; e2e 22/22; demo_cases and seeker_flow ok; review_loop 37/37; public_demo 33/33.
- Report rendered to PDF and viewed: 7 pages for 10 ads.
**Not done.** Payment (stages 2/3); persistence of used credits on the free host (resets at restart); the Pro codes are not yet set on Render (needs the team: `AGELENS_PRO_CODES`).

## 2026-10-27 · Phone layout pass (user: "用手机看很奇怪")
Looked at real-phone emulation (Playwright "iPhone 13": 390×664 viewport, DPR 3, touch, mobile UA), viewport by viewport (18 screens of home plus the main pages). Earlier phone checks only covered overflow and errors at 360/390. Found and fixed:
- Nav took two rows and hid Pro/Reviewer in a sideways scroll. It is now one row (brand + "Menu" button); the links open as a list (aria-expanded/aria-controls, closes on link, route change, Esc or outside tap; focus returns to the button).
- Quick check's bottom-left pill and back-to-top covered text (e.g. the hero's "960"). On phones Quick check is a Menu item (`AgeLens.quickCheck.open()`, hidden on the study pages like the tab).
- There were two back-to-top buttons in the same place (`app.js .float-top` and `fx.js .x-top`); removed the app.js one.
- Section spacing on phones: `--xpad` 40–56 px instead of 64–104 px; tighter heading gap; `scroll-padding-top` 76 px for the one-row nav.
- Map metric/industry chips were cut at the right edge in a hidden scroll; they now wrap.
- Footer links and the animation toggle were 26–28 px tall; now at least 40 px on phones.
Tests updated for the Menu: `public_demo.py` checks `hidden` attributes instead of visibility (the chip lives in the Menu on phones) and opens Quick check through the Menu.
Verified: sweep 120/120, a11y 0 high, theme ok, labels 0, e2e 22/22, demo_cases, seeker_flow, review_loop 37/37, public_demo 33/33, pro_flow 27/27, perf, map_v2; unit tests 259 OK. Phone screenshots viewed after the changes (menu closed and open, Quick check, home, map, Pro). Not checked on a physical phone or in Safari.

## 2026-10-27 · Live check after the push of ae08aa0 (Pro stage 1 + phone layout)
https://agelens-sepol425.onrender.com served the new code about 1 minute after the push was confirmed (`git ls-remote` = ae08aa0). Read-only checks from this machine:
- API: /api/health 960 ads; /api/report without Pro 402; /api/report/preview 10 sections for a Shanghai procurement profile; a fake Pro code 401.
- iPhone 13 emulation: one-row nav with Menu; the Menu lists Overview, Explore data, Job Seeker, My requests, Pro and Quick check (Reviewer hidden on the public host); Quick check works from the Menu; report preview panel with 10 sections; Pro page renders.
- Desktop 1280: edge Quick check tab and report preview work.
- Both: no console errors, no 4xx/5xx, no horizontal overflow; phone screenshots viewed.
- `AGELENS_PRO_CODES` is not set on Render yet, so no code unlocks the report there (expected until the team adds it).

## 2026-10-27 · Pre-push check script
`scripts/check_before_push.sh` (`--quick` for steps 1-3): (1) no databases, tokens, local code lists, logs or local tooling tracked by git; (2) all unit tests; (3) Render rehearsal: only committed files, a fresh venv with `requirements.txt`, and `app.py --public --host 127.0.0.1`; checks that the server rebuilds 960 ads, that the open demo is open, Pro is locked (402), the reviewer API is closed and the public headers are present; (4) sweep, public_demo, pro_flow and a11y_check. Stops with "DO NOT PUSH" on the first failure.
Full run: all passed in about 3 minutes. Bug found by checking afterwards: the rehearsal server on port 8890 kept running because `kill` hit the wrapping subshell, not Python. Fixed with `exec env …` (verified: the port is free after `--quick`). The leftover process was stopped by its PID.

## 2026-10-28 · Comprehensive check + README rewrite
**Checks (all run, all passed unless noted).**
- Code:
  - stdlib AST check: 1 dead local in `report.py` removed, then clean;
  - `py_compile` of all Python files.
  - Unit tests: 259 OK.
- Git:
  - no databases, tokens, local code lists, logs, uploads, `.venv` or `.claude` tracked;
  - no secret-like strings in tracked files;
  - no real invite/Pro code lists generated yet.
- Browser, all 18 scripts:
  - **own servers:** sweep 120/120, e2e 22/22, review_loop 37/37, public_demo 33/33, pro_flow 27/27;
  - **read-only, main server:** a11y 0 high, palette 0 low-contrast, theme ok, labels 0, lit_check OK, map_v2 and map_explore no errors, perf no fails;
  - **writing scripts on an isolated DB copy (8807):** demo_cases and seeker_flow no failures;
  - **study scripts on an isolated simulation copy (8806):** study_flow 8 participants PROBLEMS none, study_timeout auto-submits at 0;
  - isolated servers stopped by PID afterwards.
- Live site (https://agelens-sepol425.onrender.com):
  - The home page took 21 s while the free instance woke up.
  - Health 960; overview/stats/provinces 200; report without Pro 402; reviewer and study desks without token 401; diag 404; all 4 security headers; unknown asset 404; `..` path 400; `/data/agelens.db` 404.
- Found:
  - The main DB holds 15 demo requests (`is_demo=1`). AL-2026-0012…0015 (22:43–00:05 UTC) came from my earlier `seeker_flow` runs against the main server in previous rounds; this round used copies. Not deleted (team decision).
  - From now on, write tests run on copies (documented in `docs/DEVELOPER.md`).
**README.**
- Rewritten as a GitHub landing page: one-line pitch, live demo link, honest status box, why (Feng et al. 2026 figure, verified in `docs/LITERATURE.md`), what it does with fresh screenshots (`docs/screenshots/readme/`, viewed), quick start, deploy, evaluation summary (no results claimed), how it is built, documentation, license (none chosen; vendored MIT/OFL noted).
- Operational detail moved to `docs/DEVELOPER.md` (test count updated to 259, write-tests-on-copies rule).
- The quick start was verified in a fresh `git clone`: venv + pinned deps, sim import, `app.py` → health 960, local Pro code accepted; the clone was removed.

## 2026-10-28 · Real recruitment data received (not imported yet)
- **Received:** the user shared a Google Drive file, `智联招聘数据库2016-2025.7.csv.zip`.
  - Downloaded to `data/raw/zhaopin_2016-2025.7.csv.zip`: 5,002,743,827 bytes, matching the server's content-length.
  - Extracted to `data/raw/zhaopin_2016-2025.7.csv`: 14,046,330,485 bytes, matching the zip listing; unzip CRC passed; UTF-8 with BOM. The Mac `__MACOSX` entry was not extracted.
  - `data/raw/` is git-ignored.
- **Header:** 21 columns: 企业名称, 招聘岗位, 工作城市, 工作区域, 最低月薪, 最高月薪, 职位描述, 学历要求, 要求经验, 招聘人数, 招聘类别, 初级分类, 来源平台, 公司地点, 工作地点, 招聘发布日期, 招聘结束日期, 招聘发布年份, 招聘结束年份, 来源, and an empty last column.
- **First 20,000 rows:**
  - every row has 21 fields;
  - 24.9% mention 岁/周岁/年龄;
  - mobile numbers, landlines and emails appear in a few dozen descriptions and addresses.
- **`import_csv.py --inspect`:** auto-maps company, title, city, description and source. Not mapped: posted_date (招聘发布日期). No province column (derive it from the city). No usable occupation column (招聘类别 is the employment type; 初级分类 is 1% filled).
- **Permission:** the user stated in the conversation that the recruitment data may be used ("可以用招聘数据 这个不用担心"). Recorded as the user's statement; no approval document is in the repository.
- **Plan:** mask contact details (phone, email) at import, import into a separate `data/real.db`, keep it local (the free host cannot hold it), and keep the simulated public demo unchanged.

## MAP agent: real-data switch on the home map (2026-10-27)
- Backend (`backend/api_data.py` only): `GET /api/stats/matrix?source=real` serves the newest `matrix_*.json` in `AGELENS_REAL_DIR`
  (default `data/real`); files starting with `_` count only when `AGELENS_REAL_FIXTURE=1`. Cached per file, keyed by mtime+size.
  404 when none exists (or the file is unreadable). No `source` or `source=demo` behaves as before; any other value gets a 400.
  New `GET /api/real/status` -> {available, label, years, rows_used, generated_at, method, source, total_ads}.
- Front end (`frontend/js/mapcore.js`, `frontend/css/explore-map.css`, one line in `frontend/js/labels.js`: 其他 -> "Other"):
  a "Data" pill group (Real (Zhaopin 2021–2024) | Simulated demo), shown only when real data is available, where it is the default. The choice is kept per tab
  in sessionStorage `al_map_source`. Switching re-fetches the matrix and rebuilds the industry chips, map, legend, ranking, spread, detail, heatmap and table.
  The badge shows the response label. In real mode a caption under the legend gives rows_used and years from meta. Wording that said "simulated" in
  the map panels now follows the source. In real mode "Show these ads in the explorer" is replaced by a note, because the explorer holds only the simulated sample.
  Other pages are not changed. home_data.js was not edited, so its section heading ("The simulated data at a glance") and badge still say simulated.
- Tests: `tests/test_real_api.py` (6 tests). `tests/browser/map_real.py` (38 checks at 1280 and iPhone 13, plus a no-real-data server).
  Screenshots are in docs/screenshots/map_real/. Development used the fixture `data/real/_fixture_matrix.json` (a rescaled copy of the simulated data,
  labelled FIXTURE; ignored unless AGELENS_REAL_FIXTURE=1). The real Zhaopin file had not appeared when this work ended.

## 2026-10-28 · Home section "The motivation" + Lin (2025) verified from the full text (agent MOTIVATION)
- **Sources read.**
  - The team's `Design Pitch.pdf` (7 pages).
  - Feng et al. (2026), NBER WP 35709: page references rechecked; printed page = PDF page − 1.
  - The full text of Lin (2025), CEQ 25(1): 103–120. Text extracted with pdftotext; pp. 105, 106, 111 and 120 rendered and looked at.
  - Lin's online appendix was NOT read.
  - The PDFs stay in `data/raw/` (git-ignored).
- **Lin verified.**
  - Data and design: RD at age 35 in the 2015 census, 205,967 people, 45-month bandwidth.
  - Estimate: 0.3970% → 0.5373% lost a job for an employer reason; jump 0.1403, SE 0.0594 (Tables 1–2, pp. 108–109).
  - Ads: 18.95% of 59.69M postings state an age limit; 35 is the most common cap on all five sites (pp. 105–106).
  - The jump is not significant for college graduates; significant in 2005, not in 2010 (Table 6, p. 117).
  - Details are in `docs/LITERATURE.md` §1.
- **New:**
  - `frontend/pages/home_motivation.js`: order 25, right after "how". It has four parts: problem (an ad clipping with the Chinese quote in `lang="zh-CN"`), research with limits, gap, and five design decisions, each with its reason and source. It ends with a status line (rules only, no model, simulated public demo) and a link to `#/about`.
  - `frontend/css/motivation.css`
  - `frontend/figures/lin2025_redrawn.svg`: printed values only, no digitising.
  - `docs/MOTIVATION.md`
  - `docs/screenshots/motivation/`
- **Changed.**
  - `home_literature.js`: the Lin card now has the "Checked against the full text" status, the figure, a table and page-referenced limits. It no longer has the "To be verified" status or the "No figure shown" box. Figure loading moved into a shared helper.
  - `literature.css`: the cards stack in one column (both have wide figures).
  - `index.html`: two lines (stylesheet and script).
  - `docs/LITERATURE.md`: Lin section rewritten.
- **Verified.**
  - sweep 120/120 (incl. no CJK outside evidence)
  - a11y 0 high
  - lit_check OK
  - unit tests 265 OK
  - own server on 8853 with a DB copy, stopped by PID afterwards
  - Screenshots viewed at 1280 and iPhone 13, with motion full and reduced: no overflow, no console errors, all reveals visible. Found and fixed: a clipped footnote in the Lin SVG.
- **Not done:** `pages/about.js` still says Lin is "Abstract only, to be verified". This agent does not own that file; it needs a one-line update.

## 2026-10-28 · Real Zhaopin data: aggregate, year profile, accuracy audit (data agent)
- **Implemented:**
  - `backend/realdata.py`:
    - `city_to_province`: own prefecture table plus `scripts/geo_table.py` as fallback; 朝阳 → 辽宁 because the export's city column is prefecture level.
    - `occupation_of`: ordered keyword rules on the job title, conservative, falls back to 其他.
    - `mask_contacts`: phone, tel and email.
    - `measures_from_terms`: per-ad fields with `evidence.matrix()` semantics.
  - `scripts/real_aggregate.py`: streaming CSV, 16-process pool, (year, province, occupation) cube, matrix JSON + `meta`, including `max_age_counts`, `max_age_counts_by_year` and `ads_with_max_age`.
  - `scripts/real_profile.py`: per-year profile + seeded audit sample.
  - `tests/test_realdata.py`: 22 tests, including an equivalence test that imports the fixture through `import_csv` and checks that `evidence.matrix()` gives identical cells, totals and medians.
  - `docs/REAL_DATA_YEARS.md` and `docs/REAL_DATA_AUDIT.md`.
- **Verified (real numbers):**
  - **Full pass:** 13,322,606 rows read in 217–249 s.
  - **2021–2024:**
    - 10,058,826 rows; 10,054,663 used; 4,163 without a province (69 distinct unmapped values: foreign countries, 全国, 其他, 国外).
    - 其他 occupation: 2,805,405 (27.9%).
    - total: age_wording 2,555,249; explicit 2,296,499; cap 617,437; with_exception 91,820; median max age 40.
  - **Output:** `data/real/matrix_zhaopin_2021-2024.json`, 113,181 bytes, 566 cells. A streamed run and a cube-built run give identical cells and totals.
  - **Years:**
    - 2016–2018 descriptions are cut at 240 characters (36–42% exactly 240).
    - 2019 has 25 rows and 2020 has 2,123.
    - 2025 is abridged (99.9% under 240 characters).
    - → recommended range 2021–2024.
  - **Audit (single AI reviewer):**
    - flagged 49/60 right; numeric classes 49/50.
    - unflagged: 2/60 clear misses.
    - Found bugs: salary digits read as caps ("最高6000元" → 60); "18岁至32岁" and "20——35岁" missed; team-culture "年轻化/90后" flagged.
  - **Max age:** stated maximum 35 is the mode in 2021–2023 (26–31%); in 2024 the mode is 45 (22.9% against 20.1% for 35).
  - **Tests:** `unittest discover`: 287 tests OK.
- **Not done:**
  - `ageparse.py` is unchanged; fixes are only proposed, with an impact estimate in the audit.
  - No DB import of real ads.
  - Occupation and province mapping were not hand-audited on real titles beyond spot checks.
  - The audit has one reviewer and no agreement measure.
  - Audit sample, cube and profile stay in git-ignored `data/raw/`.

## 2026-10-28 · Lead integration: real-data map, motivation figures, fixes
**Agents.** Three subagents (DATA, MAP, MOTIVATION) ran in parallel with separate file ownership. Each appended its own log section above.
**Lead work after hand-back.**
- **Motivation, figures in place of the three evidence cards.** Both are modelled on the team's design pitch slides 1–2, at the user's request, and explained for readers who do not know regression discontinuity.
  - **Figure 1: "35 is the most common age limit".**
    - Data: our own count over 2,235,683 real Zhaopin ads (2021–2024) that state a maximum age (`meta.max_age_counts`). 35 = 26.4%, 45 = 19.4%, 40 = 16.2%.
    - It includes a 3-in-10 pictogram and a year table, where 35 falls from 31.3% to 20.1% and 45 rises from 15.4% to 22.9% (2024: 45 > 35).
    - The title follows the data: "but 45 is catching up" appears only when a year flips.
    - Without a real aggregate, it falls back to Lin's printed shares (p. 106).
  - **Figure 2: "Crossing the line changes what happens".**
    - It has a plain-language "how to read these" note.
    - Lin panel: 40 vs 54 per 10,000 dot grids, from printed 0.3970%/0.5373%.
    - Feng panel: 100 vs about 81 positive replies, from the printed theta and pre-limit mean.
    - Each panel cites its pages and states its limits.
  - The pitch's digitised values (not printed in the papers) are not used.
- **Data heading on home.** It now reads "The data at a glance". Tiles and explorer stay simulated, and a "Map: real data" badge plus a sentence appear when `/api/real/status` reports real data.
- **Map: industry chips.** "Other" (其他) is sorted last.
- **About page.** Lin is now "Checked in full text". DELIVERABLES and PENDING_TEACHER #11 are marked resolved.
- **Fixes found by the suites after integration:**
  - (a) `map_real` "no real data" run logged a 404 from Figure 1. Fixed: Figure 1 asks `/api/real/status` first.
  - (b) a11y: 4 high-severity findings, all from my new figure labels (4.40:1 on pink-soft). Fixed with darker text.
  - (c) `map_v2`: CJK in the map's sources line (meta.source holds 智联招聘). Fixed with English text.
  - (d) `labels_check` counted the motivation section's quoted ad (marked lang="zh-CN") as a leak. Its evidence list now accepts `[lang^="zh"]`, like sweep.py.
**Verified.**
- Unit tests 287 OK. Browser: sweep 120/120, map_real 38/38 (real file and no-data server), a11y 0 high, labels 0, map_v2 no fails, palette 0 low-contrast, theme ok, perf no fails, lit_check OK, public_demo 33/33, pro_flow 27/27, e2e 22/22.
- Screenshots viewed: Figure 1 real (desktop and phone), Figure 2 (desktop and phone), real map (desktop and phone).
**Open.**
- On phones, the 18 industry chips take many rows above the map (a select would be shorter).
- The ageparse fixes proposed in docs/REAL_DATA_AUDIT.md are not applied: salary digits read as caps, unusual range separators missed, team-culture wording flagged. On the full range they would change explicit by +5.1% and cap by −2.8%.
- The real aggregate is computed with rules age-rules-2.0.0 as they are.

## 2026-10-28 · Home statistics switched to the real aggregate
- The user asked that the "960 simulated ads" figures follow the real data.
- New `AgeLens.realSummary()` (app.js): one cached request to `/api/real/status` → `/api/stats/matrix?source=real`, summarised.
- Sections switched to it when real data exists; otherwise they fall back to the simulated set with the old labels:
  - **hero:** 10.05M / 34 / 16; badge "Rules only, no AI · real Zhaopin ads"; millions shortened for the pixel font;
  - **data tiles:** real ads, regions/occupations with the "Other" share, age-wording share, most common stated maximum with its share among ads stating one;
  - **"ad by ad" cards:** six cards recomputed from the aggregate. Links point to the map, because the explorer is simulated.
  - **footer:** stats, note, bar text.
- **"How age is written" card.** It shows only quantities the aggregate holds exactly: cap, range or minimum (= explicit − cap), mentions an exception, preference. A first idea, splitting hard cap / cap with exception / unclear from totals, was checked against the simulated set's exact class counts. It did NOT match (`with_exception` counts every exception clause, not one class), so it was dropped.
- **FAQ:** "Honest about what runs" and "Where does the data come from?" now describe both sources. "How will you test…" now describes the crossover plan, not the superseded template-vs-model design.
- **README:** the status box and feature row are updated.
- **Verified:**
  - In the browser at 1280 and iPhone 13: hero, cards, tiles and footer show the real numbers; no "960" or "Simulated ads" text is left on home; no console errors; 0 overflow. Phone screenshots viewed.
  - Explore, Job Seeker and demo cases stay simulated and labelled.

## 2026-10-28 · Hero badge
At the user's request the hero badge now reads "A tool for reading age limits in job ads", a one-line description of the project, the same with or without real data. Checked at 1280 and iPhone 13: one line (about 310×43 px), no overflow, no errors.

## 2026-10-28 · Polish pass after the real-data integration
- **Map, phones:** the 18 industry chips (many rows above the map) are now a `<select>` at ≤ 640 px, with the same state as the chips (`mapcore.js` chipSel). Wide screens keep the chips.
- **Map, small-sample thresholds now depend on the source.**
  - Real data uses 500 / 100 ads instead of 10 / 5, which suit the 960 simulated ads.
  - Before, with Engineering selected, Macao (46 ads) topped the ranking and was the "highest" in the spread.
  - Now rankings and spreads compare regions with ≥ 500 ads. All industries: highest Chongqing 32.3% of 172,130; lowest Hong Kong 16.7% of 750. Engineering: highest Jilin 16.9% of 19,786.
  - `AL.mapCore.SMALL/TINY` are getters.
- **Map caption:** the striping sentence was removed from the real-data caption (the legend already says it). `map_real.py` now checks the legend for "fewer than 500 ads" and uses the select on phones (40/40).
- **Stale text fixed:**
  - The motivation "Where it stands today" box said real data was "being prepared". It now describes both sources.
  - About: "What 'simulated data' means" said every ad was generated and the counts say nothing about real markets. It is now "Two data sources": the real aggregate (years and why, mappings, the "Other" share, rule accuracy from the audit, known rule errors not fixed, counts only), then the simulated set. 智联招聘 is marked `lang="zh-CN"`.
- **Docs:** README and DEVELOPER test counts (287 unit, 19 browser scripts); DEVELOPER gets map_real and the real-data/motivation docs; DELIVERABLES gets rows 6b (real data) and 6c (motivation).
- **Code:** 2 dead locals in `scripts/real_profile.py` (from the DATA agent) renamed `_o` / `_m`; the static check is clean.
- **Verified:**
  - Unit tests 287 OK.
  - Browser: sweep 120/120, map_real 40/40, e2e 22/22, review_loop 37/37, public_demo 33/33, pro_flow 27/27, a11y 0 high, palette 0 low-contrast, theme ok, labels 0, map_v2 and map_explore no errors, perf no fails, lit_check OK.
  - The phone home page was reviewed screen by screen (iPhone 13 emulation).
- **Not done (needs a decision):** the ageparse fixes from docs/REAL_DATA_AUDIT.md (they would change all real-data numbers).

## 2026-10-28 · English-only display, backend (ENGLISH-BACKEND agent)
Requirement: the website shows no Chinese. The rules keep reading the Chinese text; the API adds English display fields (`*_en`) and keeps every original field. Contract: docs/ENGLISH.md.
- **New `backend/gloss.py`** (rules only, no model):
  - `term_en`, `exception_en`, `class_en`, `quote_en` and `en_text`;
  - `province_en`, `occupation_en`, `city_en` and `source_en`;
  - `enrich_ad` / `enrich_term`.
- **API.**
  - `/api/ads` and `/api/ads/<id>`: title/company/city/province/occupation/source/class English fields, `description_en`, `age_sentence(s)_en`, per-term `gloss_en`, `class_en`, `exception_en`.
  - Brief and paste check: `text_en` on every statement, `quote_en`, `questions[*].text_en`, `findings[*].statement_en`, `unclear_en`, English evidence index; `pasted.truncated_en`, `conflict_en`, `instruction_like_en`.
  - `/api/age/check` terms: `gloss_en`, `class_en`, `exception_en`.
  - Request evidence snapshots: glossed at read time; the snapshot is not changed.
  - Stats by province/occupation: `*_en`.
  - `/api/real/status` `source`: English only, mapped in `api_data.real_source_en`. `data/real` is untouched.
- **Exports.** The Markdown export, the Word report and the study aid are English only. The report appendix shows English titles and term glosses instead of verbatim snippets.
- **Simulated ads.**
  - `make_sim_data.py` adds `title_en`, `company_en`, `city_en`, `description_en` and `age_sentence_en`. English columns version `sim-en-1.0.0`; GENERATOR_VERSION stays sim-1.0.0.
  - They come from lookup tables keyed by the Chinese template already chosen, with no extra random draws. The Chinese columns of all 1,018 rows are identical to before (sha256 pinned in tests/test_english.py).
  - Ids are unchanged: verified on a DB copy, where all 960 ids and classes are identical after reset_sim + import.
  - `datasource` maps the new columns, `evidence.ensure_columns` adds them, and `import_csv` stores them.
  - `data/sim/*` was regenerated. The CSV sha256 is now 9fbd546005c1c131…; it was b5a229ea… The `cases.json` English fields were added.
- **Study.**
  - `data/study/tasks.json` gets `ad_text_en`, `job_title_en` and `facts.quote_en` per task.
  - Calibration answers K1/K5 and one rubric example no longer contain the Chinese quote.
  - The sha256 changed from 4543eded… to 328992c7… (the study is not approved). The old value is still recorded in `data/study/dryrun_2026-10-27/` (historical, left as is).
  - `api_study.task_payload` now also returns `ad_text_en` / `job_title_en`. This is a two-line additive edit, needed so the page can show the English ad.
- **Tests.**
  - New `tests/test_english.py` (21 tests): no CJK in any `_en` field of all 960 ads and the details, the Markdown, the Word report, the study aid, `/api/age/check`, `/api/real/status`, `cases.json`; plus gloss unit tests.
  - `tests/test_pro.py`: the report test asserted verbatim Chinese snippets, which contradicts the requirement. It now asserts each term's English gloss and no CJK.
  - Full suite: 308 OK.
- **Main DB not modified.** The lead re-imports it after a backup (docs/ENGLISH.md, "Re-importing a database").

## 2026-10-28 · Rules candidate A (precision first), `age-rules-2.1.0-a`
- **New files:** `backend/ageparse_cand_a.py` (drop-in copy of `ageparse.py`, same API; adds `cohort_terms`) and `docs/RULES_CAND_A.md`. `backend/ageparse.py` and all existing files are unchanged.
- **Changes:**
  - F1, numbers read as ages: an age may not be followed by a digit; a 最高/不超过/低于 cap needs 岁 or a 年龄 prefix; 不低于 is never a cap; 未满 = 不满; caps ≤ 18 are dropped; "30岁以上勿扰" is a cap.
  - F2: ranges with 岁 on both ends, and the ——, --, 〜 separators.
  - F3: team or company 90后 / 年轻化 / 年轻人 wording is dropped.
  - F4: graduate cohort is not an age condition. It is reported separately by `cohort_terms()`.
  - F5: an age that describes customers, pupils or children is dropped.
  - F6: "男女不限年龄要求：…" is no longer read as 不限年龄.
- **Development sample:** 201,230 ads. **Evaluation sample:** a disjoint 50,435 ads (2021–2024, seed 20261028).
- **Evaluation results:**
  - explicit 11,533 → 12,088 (+4.8%); cap 3,082 → 2,958 (−4.0%); ambiguous 1,162 → 625.
  - 30 random differing ads were all judged in the candidate's favour.
- **Audit (120 items):** 107 → 119 right (strict). No regressions. This set is not held out.
- **Tests:** the existing unit tests ran against the candidate by monkeypatching the import: 286/287 pass. The only failure is the intentional `RULE_VERSION` assertion.
- **Speed:** ≈ 5,860 ads/s per core against ≈ 5,290 today. A two-digit pre-check skips the numeric patterns on sentences without one.
- **Not adopted:** the lead will choose after scoring on the blind gold set. Scratch scripts are in the session scratchpad (`cand_a/`).

## 2026-10-29 · GOLD-SET agent: blind reference set and evaluation harness
- **Gold set:** `data/raw/gold_age_2021-2024.jsonl` (git-ignored), 415 real 2021-2024 ads: 150 uniform random plus 265 targeted over 10 strata. One AI annotator, labelled by reading, before any rule was run. 227 gold positive, 21 low-confidence labels.
- **Guideline, sampling, test-retest, baseline:** all in `docs/RULES_GOLD.md`. Test-retest on a seeded 10% (40 items): has_age_condition 40/40, class 39/40 (kappa 0.96). Agreement between annotators was not measured.
- **Harness:** `scripts/eval_rules.py` (gold scoring with Wilson intervals, `--diff`, `--json`, `--population` over a seeded 50,000-ad sample with at most 6 workers, plus the draw modes). Population sample cached in git-ignored `data/raw/`.
- **Fixtures:** `tests/fixtures/age_gold_snippets.jsonl`, 89 short cases covering all strata. No test asserts on them.
- **Baseline `age-rules-2.0.0`, random stratum:** detection P 97.5% / R 97.5%, class accuracy 98.0% (147/150). On the hard-case-heavy full set: recall 78.4%, class accuracy 75.7%. Population flagged share 25.58%.
- **Main failures:** Chinese numerals unread, ranges with 岁 on both ends or repeated dashes, salary/height/eyesight digits after bound words, team wording flagged, relaxations missed.
- No changes to `backend/`; no `ageparse_cand_*` file was read.

## English-only frontend (ENGLISH-FRONTEND agent)
- No CJK anywhere in the UI (text, title, aria-label, placeholder, alt). Evidence exception removed from sweep.py and labels_check.py; new tests/browser/no_cjk_crawl.py; demo_cases/seeker_flow/map_v2/study_flow adjusted.
- labels.js rewritten around *_en fields with English fallbacks (never Chinese); app.js h() has a CJK safety net (AgeLens.noCJK, scrubLog).
- Pages: evidence, explore, seeker, requests/reviewer, study/score, sidekit (English chips, Chinese example sent to checker without showing it), home_motivation, about, home_how, pro copy.
- Details and remaining Chinese lookup keys in source: docs/ENGLISH_UI.md.
- Results against a DB re-imported with English sim data: crawler 0 CJK on all routes at 1280/390; sweep 121/121; labels_check, a11y_check, demo_cases, seeker_flow, e2e_loop 22/22, review_loop 37/37; unit tests 308 OK.

## Rules candidate B (recall-first) -- age-rules-2.1.0-b
- New files only: `backend/ageparse_cand_b.py`, `docs/RULES_CAND_B.md`. No existing file changed (this log aside).
- Fixes audit failures 1-3 in the rules, handles failure 4 (graduate cohort) by a separate `parse_cohort()`; adds recall patterns (Chinese numerals, 岁内, refusals, line breaks, birth year, ...). Method, results and risks: `docs/RULES_CAND_B.md`.
- Checks: existing unit tests 24/25 (only the RULE_VERSION assertion differs); 50,435 seeded 2021-2024 ads: range_or_min +938, ambiguous -469, hard_cap -62; 30 sampled disagreements B right 29, current 1; 120 audit ads: flagged right 49 -> 59, clear misses 2 -> 0; speed 5,065 -> 9,158 ads/s per core.
- A nested-quantifier regex bug in the separator caused a hang on dash rulers; fixed with a bounded repeat before the final run.
- Single-reviewer judgement; scratch files in the session scratchpad `cand_b/`.

## 2026-10-29 · Rules 2.1.0 adopted
- Chosen on a 415-ad hand-labelled set from three versions (accuracy 75.7% -> 94.9%, recall 78.4% -> 97.8%); details in docs/RULES_2_1_0.md. Old file kept as backend/ageparse_v2_0_0.py.
- Added a long-run guard after a timing test (4,000 repeated characters: seconds -> 0.3 s). tests/test_ageparse_gold.py added; 313 unit tests OK.
- Real aggregate re-run: same 10,054,663 ads; explicit +7.6%, cap -2.1%; 45 still overtakes 35 in 2024 (23.4% vs 19.8%). Sim DB re-imported (697 terms, unchanged).
- A data/backups/ copy of the main DB (before the English re-import) is local only and now git-ignored; it had been staged by mistake and was removed from the commit before any push.

## 2026-10-29 content-and-frontend: revised position (clarification assistant), five-paper literature, theory of change, patterns section
- Hero, how, FAQ ("Who is AgeLens for?"), About lead: "clarification assistant for mid-career jobseekers (changing jobs or returning to work)"; no AI claim; claim-size bullet on About. Evaluation wording untouched.
- Literature: home_literature.js (three new text cards, lead says findings motivate but do not establish effectiveness), about.js (five sources, "working paper version"). Burn et al. 2022 for application behaviour is NBER WP 30287 (WP 26552 is the callback paper).
- New figure 3 (theory of change, ordered list + two columns + worked example) in home_motivation.js; css in motivation.css.
- New home_patterns.js (order 27, id patterns) built on docs/HETERO_CONTRACT.md; tested with data/real/_fixture_hetero.json (invented numbers, tests only) via route interception in tests/browser/patterns_check.py. AL.heteroData() is shared by the data lead, footer note and FAQ so they mention experience/gender only when the endpoint answers.
- Open: until /api/stats/hetero exists, a server with real data logs one 404 on the home page, so sweep.py fails 4 home checks (console + 4xx). Fix on the backend side: add a "hetero": true flag to /api/real/status, then the front end can skip the call.

## HETEROGENEITY-DATA agent: gender rules, heterogeneity file, endpoint
- **New files:** `backend/genderparse.py` (`gender-rules-1.0.0`), `backend/api_hetero.py` (`GET /api/stats/hetero?source=real`), `scripts/real_hetero.py`, `scripts/eval_gender.py`, `tests/test_genderparse.py`, `tests/test_hetero.py`, `tests/fixtures/gender_gold_snippets.jsonl`, `docs/GENDER_RULES.md`, `docs/HETERO_CONTRACT.md`, `docs/HETERO_FINDINGS.md`. Git-ignored: `data/raw/gold_gender_2021-2024.jsonl` (415 ads), candidate/dev pools, `data/raw/hetero_cube_2021-2024.json`. Output: `data/real/hetero_zhaopin_2021-2024.json` (38 KB, counts only). No existing file edited except this log.
- **Gold set:** 415 real ads (150 random, 265 targeted), one AI annotator, labelled by reading before the rules were run on them. Only 24 carry a restriction or preference. Pass 1 (rules as first written): restriction/preference precision 20/31 (64.5%), recall 20/24 (83.3%); any wording 96.8% / 94.8%; class accuracy 94.7%. After fixes driven by those errors (not held out): 23/24 and 23/24 (95.8%, [79.8, 99.3]); any wording 99.5% / 97.9%; accuracy 98.6%. Random stratum: 150/150 correct, 0 of 143 negatives flagged.
- **Finding:** explicit single-sex requirements are very rare in these ads (male only 1,047, female only 1,556, preferences 8 of 10.06 M). "Either sex" wording is 7.0%.
- **Experience bands:** 不限/无经验/无 -> No experience required; 1年以下; 1-3年; 3-5年; 5-10年+10年以上 -> 5+ years; empty/other -> Not stated.
- **Full run:** 10,058,826 ads, 6 workers, about 4 minutes; explicit age 24.6%, cap 6.0% (matches the 2.1.0 matrix within rows without a province).
- **Not done:** the About-page text request from the lead (frontend files are outside this task's ownership).

## 2026-10-29 · Evaluation-design agent: crossover-ai-v1 (contextual AI vs fixed template, identical evidence)
- **Decision (team, final):** the primary comparison is contextual AI assistance vs fixed templates with identical evidence; claim = improved decision support only. **No model connected.** Old plan kept as `docs/EVAL_PLAN_v1_rules_vs_ad.md`; `docs/EVAL_PLAN.md` rewritten; DEVELOPER, COURSE_CHECKLIST, PENDING_TEACHER (items 3, 9, new 15), PREREGISTRATION_DRAFT, EVAL_PROTOCOL header and README evaluation section aligned.
- **Code:** `backend/study_arms.py` (evidence_package, template_tool, SimulatedAiDrafter, tool_aid with the llm adapter path and `violates()` check), new `backend/study_ai.py` (participant view, rubric scoring, export), `backend/study_stats.py` (paired exact test, bootstrap CI, Holm, kappa, analysis), `backend/api_study.py` (design selection: default crossover-ai-v1; `DESIGN_OVERRIDE` / env `AGELENS_STUDY_DESIGN` = crossover-rules-v1 or parallel-llm-v0; formal refused without approval AND a model; reading/question columns; English-only payloads; tools labelled Tool A/B). Scripts: `analyze_study_ai.py`, `power_ai.py` (+ `data/study/power_ai.md`); `analyze_study.py` dispatches.
- **tasks.json** extended additively (design_ai, rubric_ai, calibration_ai, key_facts, instructions_ai, consent_ai_draft). **sha256 changed:** 328992c7... -> see `sha256sum data/study/tasks.json` (still DRAFT, not approved).
- **Frontend:** `study.js`, `score.js`, `study.css` (two text boxes, evidence card, tool card, SIMULATED banner on every screen, blinded rater form with key facts / q1-q4 / unsupported count).
- **Existing tests adapted:** `CrossoverTests` in `tests/test_study.py` now sets `DESIGN = S.RULES_DESIGN` because the default design changed. Old `study_flow.py` moved to `tests/browser/legacy/study_flow_rules_v1.py`; new `study_flow.py` for the AI design; `study_timeout.py` handles both layouts.
- **Tests:** new `tests/test_study_ai.py` (31 tests); full suite 364 OK. Browser: study_flow (6 x 4, no problems), study_timeout, sweep 121/121, a11y 0 high, no_cjk 0 CJK.
- **Dry run (SIMULATED, no AI):** `data/study/dryrun_2026-10-29/`. Machinery only; numbers are from scripted assumptions and mean nothing.
- Not done: model, participants, approval, preregistration, results.

## 2026-10-30 · Overview made short; detail moved to two pages in the top nav
- Overview `#/` now holds hero, how, data map, a new "Read more" strip (link cards) and steps. Page length at 1440 px: 20,811 -> 5,172 px; at 390 px: 29,331 -> 7,933 px.
- New routes `#/why` (motivation, literature, fields, FAQ) and `#/findings` (patterns, carousel), each with a page head (h1); nav links "Why it matters" and "Findings" after Overview; footer columns updated. Section text unchanged, except: FAQ evaluation answer now describes the decided design (fixed template vs contextual AI, same evidence, no model connected); FAQ and global footer no longer say all data is simulated.
- Mechanics: `pages/home.js` composes any page from sections tagged `page`/`rail`; CSS selectors `data-route="home"` -> `data-layout="home"` (router sets it from `page.layout`); fx.js and the section rail follow the layout; rail labels come from the page shown; the carousel's "See the map" opens the Overview map via `AL.home.goto`.
- Tests: routes added to sweep, no_cjk_crawl, a11y_check; lit_check and patterns_check point to the new pages. Unit 364 OK; sweep 141/141; map_real 40/40; public_demo 33/33; pro_flow 27/27; patterns_check, lit_check, labels_check, theme_check, map_v2 pass; no_cjk 0 CJK; a11y 0 high.
- Seen, not changed: at 1024 px the page is 9 px wider than the window (also in the committed version; the carousel cards).

## 2026-10-30 · Review and polish of the three pages
- Overview map: spread, top 10 regions and industry × region heatmap moved under one "More views" disclosure (closed by default); the map, legend and selected-region panel stay open. Data intro shortened (no internal data-version label; links to Findings); ad-count tile shows 10.05M (the full number overflowed the tile) with the exact count below.
- Findings: headline cards first, renamed "The headline numbers" (they are aggregates, not single ads); gender charts show "per 10,000 ads" (percentages rounded to 0.0%) and say the bars are scaled to the chart's largest value.
- Why it matters: literature heading "The studies in detail" (it repeated the page title); FAQ card no longer says "home-page statistics". About: references to "the home page" now name Overview / Findings / Why it matters. Footer: "course prototype"; first-paint note no longer says all ads are simulated.
- Fixed the 9 px sideways overflow at ~1024 px: unrevealed cards are tilted in 3D and their projection passed the window edge; home-layout sections now clip x-overflow. Checked 0 px at 1440/1024/768/390 on all three pages.
- Tests: map_real, map_v2, labels_check, palette_check open "More views" through an init script.

## 2026-10-30 · Site aligned with the team's reply to teacher feedback
- Hero badge and About lead: "evidence-grounded clarification assistant".
- Why it matters: new bridge note after the research figures (occupation, experience and gender matter; our data compares stated age requirements across occupations, required experience and locations with explicit gender requirements; describes ads, not hiring; link to Findings). Theory-of-change figure: "How we will test it" (contextual AI vs fixed templates on identical evidence; four outcomes; no model connected, not run); "not shown" now says any employment benefit depends on employers responding. Neumark/Burn/Belot lines reworded to match the reply (also in docs/THEORY_OF_CHANGE.md).
- Findings head: location differences are on the Overview map.
- Checks: unit 364 OK; sweep 141/141; no_cjk 0; a11y 0 high; patterns_check, lit_check pass.

## 2026-10-30 · Explore data page removed
- The `#/explore` page (filters, charts and a list of the 960 simulated ads) is gone at the user's request: nav, footer, Overview button, Findings card links and the map's "Show these ads in the explorer" button removed; `pages/explore.js`, `js/charts.js` and their CSS deleted. Old `#/explore…` links now land on the Overview data map. Simulated ads are still opened from Job Seeker answers (`#/evidence/<id>`).
- Tests: Explore routes dropped from sweep, no_cjk_crawl, a11y, theme, labels, palette, public_demo, map_v2, perf, final_shots; `map_explore.py` now checks the redirect. Unit 364 OK; sweep 131/131; no_cjk 0; a11y 0 high; map_real 40/40; public_demo 33/33; map_explore, map_v2, palette, labels, theme, patterns, demo_cases, seeker_flow pass.

## 2026-10-30 · Positioning, Overview and Check-an-ad polish
- Based on a competitor scan (Textio, Applied, Gender Decoder, Jobscan, Teal, Rezi, ToS;DR, GOV.UK checkers; findings only from fetched pages) and a first-time-user walkthrough. Two parallel workstreams on disjoint files.
- Overview: headline "Does “under 35” in a job ad rule you out?"; positioning line as a visible eyebrow; CTAs "Check an ad" / "See an example"; a "Check one line" card in the hero (shared `AgeLens.lineCheck` with the edge tab); new "What you get" section with a labelled fictional example output; one-line limits; how/steps/footer/FAQ/About copy aligned; stale "all data is simulated" lines fixed on Pro and the invite page; opaque phone menu.
- Nav: Check an ad (#/seeker), Human review (#/requests), Full report (#/pro); the Quick check tab is "Check one line".
- Check an ad: the pasted ad comes first and is open; dataset search is secondary ("See similar ads"); the answer leads with "In short" and "Your question for the employer" (Copy button); ad-by-ad lines and ad cards folded; "Ad 1 · title · province" instead of raw ids; tags "Ad wording (translated)" / "AgeLens rules"; one limits line instead of repeated notices; example situations with user-facing titles (presenter cases at `#/seeker?demo=1`); after submitting for review the next step is stated. Answer page 8,557 → ~5,900 px desktop, 12,309 → ~8,250 px phone.
- brief.py: experience sentence grammar ("as an operations manager"); new `summary` and `employer_question`; the employer question never mentions age and, with several similar ads, does not cite the other ads.
- Checks: unit 368 OK; sweep 131/131; no_cjk 0; a11y 0 high; map_real 40/40; public_demo 33/33; e2e_loop 22/22; review_loop 37/37; pro_flow 27/27; demo_cases, seeker_flow, theme, palette, labels, map_v2, map_explore, patterns, lit pass.

## 2026-10-30 · Fixes from a four-persona walkthrough
- Four scripted personas (desktop jobseeker with a Chinese ad; phone user; keyboard-only at 200% zoom with reduced motion; adversarial examiner) walked the site on DB copies. These are automated walkthroughs by agents, not human user testing.
- Fixed:
  - English-only text: "Check one line" and the pasted-ad check said "no age requirement" (the rules read Chinese wording). Both now say to paste the original wording; the server answers 422.
  - Pasted ads offered "Ask a human reviewer" but could not be sent: the button is now "Ask a reviewer about similar ads" and runs the similar-ads search with the same question and background.
  - Self-contradicting ad: "How it relates to you" said there was no maximum; it now says the ad gives more than one limit.
  - A CV header line "Name - Title" became the occupation, so the name appeared in the question for the employer; only the title segment is kept now (unit test).
  - A failed re-check left the previous answer on screen; it is cleared.
  - "Back to your answer" lost the scroll position and the open ad list; both are restored.
  - Focus after confirming a CV and after submitting a review no longer drops to the page; Escape on the edge panel returns focus to the tab; "See an example" moves focus to the example.
  - Brief: "Ads read: 1 (the ad you pasted)", "Source: the ad you pasted", "not stored" instead of "kept in the ad record", no "Insufficient evidence" line for one pasted ad, plural headings with several ads, "Model inference" tag explained only when a model ran.
  - Copy: no "Pitch, slide N" references on Why it matters; Why example question no longer uses "qualify"; Findings explains its ad count; About single-sex count matches the data (about 2,600 plus 756 contradictory); demo ads show no dead link; the "Title matches your search text" reason now names the occupation group; "Use an example" is "Fill in an example question"; the pasted-ad answer shows the injection note only when instruction-like lines were found.
  - Phones: the menu layout also applies to phones held sideways; example chips, table toggles and map buttons are at least 40px tall.
- Not changed: required honesty labels ("Demo · Synthetic data", "Template demo"); the edge tab's place in the tab order; the long Why it matters page on phones.
- Checks: unit 372 OK; sweep 131/131; no_cjk 0; a11y 0 high; map_real 40/40; public_demo 33/33; e2e_loop 22/22; review_loop 37/37; pro_flow 27/27; demo_cases, seeker_flow, theme, palette, labels, map_v2, map_explore, patterns, lit pass.
