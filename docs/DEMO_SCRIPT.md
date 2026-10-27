# Demo script

Local app: `cd ~/agelens && .venv/bin/python app.py --port 8765`, then http://127.0.0.1:8765. Routes: `#/` home, `#/seeker`, `#/explore`, `#/reviewer`, `#/study`. Reviewer sign-in uses the token in `data/reviewer_token` (printed at server start). Click paths for the Job Seeker page and section C were re-checked on 2026-10-24 against the current UI (tests/browser/demo_cases.py, screenshots in docs/screenshots/demo_cases/); other pages: rehearse once and correct any path. Team member names are placeholders: [Member A] ... [Member E]. Do not list anyone who did not take part.

Fictional example (always say it is fictional): a 38-year-old job seeker with eight years in procurement asks: "I'm 38 with eight years of procurement experience. This ad says applicants should normally be under 35, but exceptions are possible. What should I clarify before applying?"

## Before every demo (5 min)
1. Start the server; open http://127.0.0.1:8765/api/status (if present) or `#/` and confirm the badge "Demo · Synthetic data" and the model state "Template demo".
2. Open a second browser window for the reviewer (separate profile, so the seeker's stored tokens stay separate).
3. Have the adversarial texts ready in a plain text file on the desktop.
4. Have screenshots from docs/screenshots/ open in case the browser fails.

## A. Midterm demo: 8 minutes
| Min | Beat | Do / say |
|---|---|---|
| 0:00-0:45 | Problem and user | One sentence on the user (mid-career job seeker) and the task (read age wording in an ad, prepare what to ask). Do not claim effect on employment. |
| 0:45-1:30 | What runs / does not run (slide) | Wording below. |
| 1:30-3:30 | Seeker flow | `#/seeker` (nav "Job Seeker"): open "Try a demo case" under the question box, click "1 · 38-year-old in procurement" (fills age 38, Procurement, 8 years, 上海 and the question, then runs). Point to the badges "Demo · Synthetic data" and "Template demo", the five answer headings, the tags Ad text / You said / Rules, and "(4 of 10 ads)". Under "The ads behind this answer" click "View original" on one ad to show the highlighted wording. "Download brief (Markdown)". |
| 3:30-4:30 | Request and reviewer | Back on the seeker results, tick "Select for review" on one or two ads, then "Submit for human review"; copy the request number. In the other window `#/reviewer`, sign in, open the request, send an info request or draft a reply and publish. Back in the seeker window `#/requests`: show the reply. |
| 4:30-6:00 | Adversarial input from another team | Open "Paste an ad to check (optional)", paste their ad text into "Ad text", keep or type a question, click "Check this ad". See section C. |
| 6:00-7:00 | Evaluation plan slide | Claim, threshold, counterfactual (fixed template), assignment mechanism (awaiting teacher approval), power analysis (candidate N only, awaiting approval). `#/study` only if it shows simulated sessions labelled as such. |
| 7:00-7:40 | Spend slide | Actual spend and biggest item from docs/BUDGET.md section 2, as filled by the team. If empty, say so. |
| 7:40-8:00 | Two open design questions | State the two questions from COURSE_CHECKLIST.md (drafts) and ask for advice. |

## B. Final demo: 12 minutes + 8 minutes Q&A
| Min | Beat | Do / say |
|---|---|---|
| 0:00-1:30 | Problem evidence | Literature slide: why age thresholds matter. Say it is not an AgeLens effect. Show only sources the team has actually read. |
| 1:30-2:30 | Mechanism and differentiator | docs/COMPETITORS.md summary. Say chat UI and LLM summarisation are not novel. Say Applied's current offer was not verified. |
| 2:30-3:30 | Home and map | `#/` then scroll to the data section; open `#/explore`, rotate and zoom the 3D map, select a province, switch to the 2D alternative. Say the data is synthetic. |
| 3:30-6:00 | Seeker to reviewer flow | As in A, with the 38-year-old example. |
| 6:00-8:30 | Examiner adversarial inputs (at least 2) | Section C. |
| 8:30-10:00 | Evaluation design and what was actually executed | `#/study`. Report only what ran, labelled simulated. Effect size, CI, N and dropouts only if they exist; if no formal trial was run, say that. |
| 10:00-11:00 | Budget trade-offs and midterm advice | Table from BUDGET.md section 5; list advice adopted/rejected and why (team to fill). |
| 11:00-12:00 | Limits | Slide wording below. |

Q&A prep (8 min): prepare one-line answers on: why synthetic data; what the rules cannot do; how model output would be checked (self-check is not a guarantee); how raters score "usable"; why participant is the analysis unit; what happens on model failure; privacy of CVs (not stored); no legal conclusions; what we would do with real data; why not claim an employment effect.

## C. Handling adversarial inputs live
Say first: "The ad is data, not instructions." Everything below is on `#/seeker`. Rehearsed cases are under "Try a demo case" (one click each, fictional, labelled "Demo case N ... (fictional)" in the answer); a real input from another team or an examiner goes into "Paste an ad to check (optional)" → "Ad text" → "Check this ad" (up to 4000 characters; checked in memory by the same rules, not stored, not logged; labelled "Pasted text, not stored"). The question box must have a question (any).
- Prompt injection: demo case "2 · Ad with a hidden instruction", or paste their text. Expected (observed 2026-10-24): box "Instructions inside the ad were ignored" quoting the injected lines as plain text; the brief reports only the real age wording ("This ad states a maximum age of 35" with the Chinese quote) and makes no approval or hiring promise. Template demo means no model was called.
- Contradictory wording: demo case "3 · Contradictory age wording" (年龄不限 + 35岁以下). Expected: "This ad's age wording contradicts itself: it contains “…” and “…”. The rules do not choose between them."; it is not compared with your age; a question "Which of these applies to this role?". Do not resolve it.
- Truncated text: demo case "4 · Ad text cut off" (ends 年龄35岁以). Expected: "No age limit was read from the cut-off part. Ask for the full ad."
- No-match query: demo case "5 · Search with no matches" (lighthouse keeper, 西藏). Expected: "No ads match all of these conditions", "Nothing was broadened for you", buttons "Search all regions" and "Drop the occupation text". Click the second to show 1 ad and "Not enough evidence".
- Model unavailable / API off: demo case "6 · No model connected". Expected: badge "Template demo", the server's own reason text, and "Model not run — Template demo." A connected model that fails cannot be shown live without configuring a key; say it is covered by unit tests (API1-3, docs/ADVERSARIAL_CASES.md).
- Garbage / binary / oversize paste: expected a plain message ("This does not look like ad text ..." or "the limit is 4000"), the page keeps working. If anything unexpected appears, show it, say so, reload, and log it in DEVELOPMENT_LOG.md afterwards.
Record the input, expected and actual result after the demo.

## D. Slide wording: what does not run
"Runs: simulated-data search, age-wording extraction by rules, evidence brief, request to human reviewer and reply. Does not run: no AI model is connected (Template demo); no real recruitment data; no formal trial with participants; no pre-registration filed; effects on users are untested." Edit to match the state on the day.

## E. Fallbacks
- WebGL fails or is slow: use the 2D map alternative; or the screenshots; say software rendering/no GPU. Use "Pause animation" in the footer to stop the cover animation.
- Network fails: the app is local and vendors its scripts; only slides/literature links need network, so keep PDFs/screenshots offline.
- Server dies: restart with the command above; data is in data/agelens.db. Keep 2 minutes of screenshots as backup.
- Reviewer sign-in fails: check data/reviewer_token.

## F. Role split (placeholders)
| Part | Presenter | Must also be able to explain |
|---|---|---|
| Problem and literature | [Member A] | Why the cited studies do not evaluate AgeLens |
| Seeker flow and evidence boundary | [Member B] | Ad facts vs user statements vs inference; why no model |
| Reviewer loop and privacy | [Member C] | Tokens, what is stored, what is not |
| Map and simulated data | [Member D] | How synthetic data is generated and labelled |
| Evaluation and budget | [Member E] | Outcome definition, power analysis assumptions, spend |
Every member must be able to answer questions on any part; the team must fill the names truthfully.
