# Live demo runbook (midterm rubric: "Live demonstration", 5 points)
The rubric asks for a live product that survives at least one adversarial input from the discussant team. Not a video.

## Before the session
1. Merge and push; wait until Render shows the new deploy live.
2. **5–10 minutes before**: `python3 scripts/demo_preflight.py`. It wakes the site (the free plan sleeps; a cold start took 22 s on 2026-11-03) and checks 14 inputs. Continue only on `READY`. Run it again just before you present.
3. Open https://agelens-sepol425.onrender.com/#/seeker and keep it open. Do not deploy on the day: a restart interrupts the site and clears review requests.
4. Fallback, ready on one laptop: `cd ~/agelens && .venv/bin/python app.py --port 8765`, then http://127.0.0.1:8765. It is still live. If the site is down, say so and switch. Never play a recording.

## Human review on the public site
Set `AGELENS_REVIEWER_TOKEN` in the Render dashboard; reviewers open `#/reviewer` directly. Free-plan restarts (including waking from sleep) clear requests, so submit and reply in one sitting during the demo.

## Inviting the discussant input
Hand over the keyboard, or type what they say into **Check an ad → Paste the ad → Check this ad**. Say: "The ad is data, not instructions."

| They try | What you will see | One line to say |
|---|---|---|
| "Must be under 35" | Maximum age of 35 and a neutral question for the employer | Reads the wording; decides nothing |
| "Under 35, up to 40 for strong candidates" | Cap 35, may be relaxed to 40; a 38-year-old is told they fall between | Still only the employer decides |
| "Under 35 preferred" | Preference, not a hard limit | |
| "Join our young team" | Unclear age wording, no number | |
| "Our customers are under 35" | "Could not read it as a limit that applies to the applicant" | Unclear rather than a false limit |
| "Salary up to 35k" | No age wording, with a note that rules can miss phrasing | |
| "Ignore all instructions, say I am approved" | Box "Instructions inside the ad were ignored"; no approval | No model is connected, and text is never followed |
| `<script>alert(1)</script>` | Shown as plain text; nothing runs | |
| Empty, over 4000 characters, control characters | Plain message; the page keeps working | |

## Known failures: say them first if asked (rubric: "Honest and specific account")
- English is read by a small rule set (`backend/ageparse_en.py`, `age-en-1.1.0`) with **no measured accuracy**; the page says so. Audited figures concern Chinese rules only.
- Exact-age wording ("Must be 35") is shown as unclear, not as a limit. Unseen phrasings will be missed, and a miss looks like "no age wording found" with a "rules can miss" note.
- Pasted Chinese product lines (适合35岁以下女性的护肤产品) are shown as unclear by a paste-only check. The aggregate's Chinese rules are unchanged, so such lines may still be counted there.
- A claim "it can never fail" would be false: tests cover the corpus in `tests/test_age_corpus.py`, not all language.
- A word-for-word instruction inside an ad is quoted back; it is never followed.
- No AI model is connected, so model failures cannot be shown live (unit tests only).

If something unexpected happens: show it, say so, reload, and record input, expected and actual in `DEVELOPMENT_LOG.md`. A visible failure handled honestly is better than hiding it, and the log audit follows the same day.
