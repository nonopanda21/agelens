# AgeLens evaluation protocol

> **SUPERSEDED 2026-10-29 by `docs/EVAL_PLAN.md`** (2026-10-27: first by the rules-vs-ad crossover) (within-participant crossover, ad only vs AgeLens evidence check, no model needed). This file describes the legacy parallel model-vs-template design (`parallel-llm-v0`), which is still selectable in code but is not the planned study.

> **STATUS: DRAFT — NOT FILED, NOT APPROVED.** No participant has been recruited, no approval has been given, nothing has been preregistered, and there are no study results. Every number from the tools in this repository comes from SIMULATED sessions (software tests). Items marked **TEACHER** need the teacher's decision before any formal collection. Companion: `docs/PREREGISTRATION_DRAFT.md`, `data/study/EXPORT_SCHEMA.md`.

## 1. Question and claim
**Question.** With the same background, ad evidence and interface, does LLM-drafted help raise the share of *usable* clarification requests compared with a fixed template?
**Claim tested (H1).** Participants given drafted help write a higher share of usable requests (mean over their 4 tasks) than participants given the fixed template.
**What it is not.** Not a test of classification accuracy (that is a different, separate question), not an employment, hiring or macro-economic outcome, not a legal judgement. A classroom trial cannot show lower unemployment or higher GDP; those need long follow-up and are discussed only as mechanism.
**Counterfactual.** The template arm: the same ad, profile, time limit and screen, with a fixed generic template instead of drafted help. (A no-aid arm is not included; it would answer a different question. Listed as a possible extension, TEACHER.)

## 2. Design
Two-arm parallel randomised, participant is the unit. Each participant does the same four FICTIONAL tasks (`data/study/tasks.json`, frozen by hash): T1 age cap, T2 cap with qualification exception, T3 age preference, T4 incomplete evidence. Task order is randomised per participant (seeded). Identical information, 7-minute limit per task (candidate, TEACHER), layout and instructions; only the aid panel differs. Tasks are separate from the public simulated demo ads and cases. Participants write the request they would send; they never see scores or their arm name (aid type is visible on the aid card, which the consent text discloses).

## 3. Outcome
**Usable request** = raters meet all four criteria AND no severe unsupported claim: (1) background accurate; (2) citation faithful; (3) states uncertainty; (4) specific, answerable question. Definitions, examples and the severe-error types (S1 invented fact incl. invented cap/ad id; S2 eligibility/outcome assertion; S3 legal conclusion/accusation; S4 ignoring or distorting a stated exception) are in `tasks.json > rubric`.
**Primary outcome (participant level):** usable share = (number of usable tasks)/4. Missing, empty or unattempted tasks count as NOT usable (conservative; sensitivity: completers only).
**Secondary:** usable on >= 3 of 4 tasks (binary); time per task; timeouts; model failures; aid inserted; dropout; inter-rater agreement.
**Why share-of-4 rather than all four answers pooled:** the 4 answers of one person are correlated (ICC rho), so pooling them as 96 independent answers would overstate precision. The participant-level mean respects that structure. It also uses more information than a dichotomy (power table below).

## 4. Assignment (TEACHER to approve)
Permuted blocks of 4 (2 template + 2 assisted) inside each mode, from a seeded generator `Random("seed|mode|block")`; simulation seed 20261023 (documented in code); the formal seed is set by the approver in APPROVAL.json. Allocation happens at enrolment after consent, server-side; the sequence is never exposed to the browser; arms are balanced within 2 at all times and exactly 12/12 at N=24. Tests prove balance and reproducibility (`tests/test_study.py`).

## 5. Raters, calibration, disagreements
Two independent raters (R1, R2) blind to arm, to participant and to each other; opaque item keys; items offered in a per-rater shuffled order. Before real scoring each rater scores 6 frozen calibration examples and sees reference scores and reasoning; target >= 90% agreement with reference over 30 judgements and every severe flag matched, otherwise clarify the rubric text and repeat with a new frozen set (calibration is never mixed into data). **Disagreement** = any criterion or severe flag differs; logged; a third rater R3 (sees only disagreements, blind to R1/R2 scores) scores independently; the final value is the majority of R1, R2, R3. Submitted scores are never edited. Unresolved items are reported, and participants with unresolved tasks are excluded from the primary analysis until resolved (their count is reported). Limitation: a participant who pastes an aid text may leave stylistic traces that hint at the arm; blinding is by design, not guaranteed. Rater access is a demo-grade local token (`data/study/study_token`), not authentication.

## 6. Analysis plan (`scripts/analyze_study.py`)
Primary: difference in mean usable share (assisted − template), 95% percentile-bootstrap CI (resampling participants within arm), two-sided randomisation test (20,000 shuffles); Welch t shown for comparability with the power analysis. Secondary: risk difference for >= 3/4 usable, Newcombe hybrid-score 95% CI, Fisher exact p. Kappa per criterion (R1 vs R2, before adjudication) with raw agreement. Sensitivity: completers only. Per-task-kind tallies are descriptive only. Report effect size, CI, N randomised/analysed per arm, dropouts, model failures, null and negative results alike. No multiplicity adjustment is applied because there is one primary test; secondary results are labelled exploratory.

## 7. Power and minimum detectable effect (`scripts/power_analysis.py`; table `data/study/power_table.md`)
Method: seeded Monte-Carlo (2,000 simulated trials per cell) with a beta-binomial model: participant latent usable-probability varies, 4 tasks per participant, within-participant task correlation rho; Welch t, two-sided alpha .05; secondary test power is exact. Validation: at N=24, p0=.35, +.30, rho=.2 the Welch test rejected in 60.7% of trials vs 55.0% for the randomisation test (94% same decision), so **Welch power is about 5 points optimistic**; treat the table as an upper bound.
**Assumptions (all unverified; no pilot data exist):** template baseline per-task usable probability p0 in {.20,.35,.50}; rho in {0,.2,.4}; arms differ only in mean; tasks equally hard in both arms (balanced by design); no dropout.
**Headline for N = 24 (12/arm), p0 = .35:**

| rho | MDE at 80% power (absolute increase in mean usable share) | power if true effect is +.15 / +.25 / +.35 |
|---|---|---|
| 0 | 0.30 | 0.31 / 0.68 / 0.93 |
| 0.2 | **0.365** (about 1.5 more usable tasks of 4) | 0.20 / 0.46 / 0.76 |
| 0.4 | 0.43 | 0.18 / 0.38 / 0.64 |

Range over p0 and rho at N=24: MDE .28 to .43. Secondary (>= 3/4 usable) at N=24, +.25: exact power only .10 to .44. Sample size for 80% power at p0=.35, rho=.2: N=24 gives MDE .37; N=32 .31; N=40 .28; **N=48 .26; N=64 .23; N=96 .18.**
**What N=24 can and cannot do.** It can detect only a large effect (roughly +.35 or more in usable share, e.g. 35% to 70% of tasks usable). A true improvement of +.15 would be missed about 70-80% of the time and +.25 about half the time (when tasks are correlated). A non-significant result at N=24 is therefore NOT evidence of no effect; the CI will be wide (about +/-.3) and must be reported as such. N=24 is feasible as a first, pre-registered pilot/feasibility estimate whose CI informs a larger study, not as a confirmatory test of a modest effect.
**Inputs the TEACHER must approve:** (a) recruitment target (24 as pilot, or 48 if recruitment allows) and whether the study is declared pilot vs confirmatory; (b) smallest effect worth detecting (the "meaningful effect") and the success threshold (proposal: lower CI bound > 0 AND point estimate >= +.20); (c) alpha (.05), tail (two-sided), power target (.80); (d) stopping rule (proposal: fixed N, no interim looks, stop early only for harm/ethics or model failure rate > 20% of aids); (e) assignment mechanism (blocked, seeded, server-side as above) and the seed; (f) time limit; (g) exclusion rules (section 9); (h) consent text and ethics route; (i) whether to add a no-aid arm; (j) task set freeze.

## 8. Formal-mode gate (server-enforced)
Default mode is `simulation`. `formal` is refused by `POST /api/study/mode` and by enrolment/export unless ALL hold: `data/study/APPROVAL.json` exists with `approved: true`, teacher_name, approval_date, protocol_version, recruitment_target, assignment_mechanism, stopping_rule, allocation_seed, `preregistration.reference` and 64-hex `preregistration.sha256`, `tasks_sha256` equal to the hash of the current `tasks.json`; AND a model is connected. The file is created only by the teacher/team after real approval; this code and its tests never create it (the tests use a fixture in a temp directory). If approval disappears mid-study, enrolment is refused. Simulated sessions carry `simulated=1`, show a persistent banner "SIMULATION — not study data", use a labelled SIMULATED aid provider, and are excluded from the formal export by construction. Model failures are recorded (`model_failure`) and shown to the participant; the SIMULATED provider is never used in formal mode.

## 9. Data recorded, exclusions
Recorded per task: start/submit times (server), elapsed, limit, late/timed-out flags, answer, aid shown, provider, whether the aid was inserted, model failure and error class, scores. Participants: anonymous code, arm, block, status, consent version/time. Not recorded: name, email, IP, user agent. Exports contain no free text (EXPORT_SCHEMA.md).
**Exclusions (pre-specified):** participants who withdraw are counted as dropouts and their text is deleted; they are excluded from scoring and analysed in the dropout table only. Participants with any unresolved score are excluded from the primary analysis until resolved. Do not exclude on outcome. Answers submitted > 5 s after the limit are flagged `late` and scored normally (sensitivity analysis may drop them).
**Dropout** = withdrawn, or unfinished and inactive > 60 minutes.

## 10. Reporting commitments
Report: N enrolled/randomised/analysed per arm, dropouts and model failures, effect size with CI, p-values with the method, kappa, all deviations, negative and null results, and that the study used fictional tasks and cannot support employment, GDP, hiring-probability or legal claims. Simulated results are never reported as findings.

## 11. Tools and how to run (simulation)
`#/study` (participants), `#/study/score` (raters + operator). Start: `.venv/bin/python app.py --port 8765`; token in `data/study/study_token`. Browser run: `tests/browser/study_flow.py`; countdown: `study_timeout.py`. Analysis: `python3 scripts/analyze_study.py <SIMULATED export>.json`. Example SIMULATED export + analysis: `data/study/simulated_example/`.

## 12. Known limits
Rubric not yet tested by humans on real answers (kappa is unknown; simulated kappa values mean nothing); fictional tasks may not transfer; class participants are not job seekers; a model is not connected, so the assisted arm cannot yet be run formally; one rater desk token is shared and not real authentication; tasks are in a fixed time-limited setting.
