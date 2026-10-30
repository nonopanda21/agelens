> **SUPERSEDED 2026-10-29 by `docs/EVAL_PLAN.md` (contextual AI assistance versus fixed templates, identical evidence). Kept for the record; the code keeps this design selectable as `crossover-rules-v1`.**

# AgeLens evaluation plan (crossover-rules-v1)

> **STATUS: DRAFT for teacher approval, 2026-10-27. Not filed, not approved, no participant recruited, no results.** The only data so far is a SIMULATED dry run of the tools (section 10). This plan supersedes the parallel model-vs-template design in `docs/EVAL_PROTOCOL.md`, which needs a connected model that the project does not have; that design stays in the code as `parallel-llm-v0`.

## 1. Why this evaluation (policy cycle)

| Stage | AgeLens |
|---|---|
| Problem and evidence | Mid-career job seekers in China meet short age lines in ads ("35岁以下", "条件优秀者可放宽"). Applicants just above a posted limit get about 14–20% fewer applications and callbacks (Feng et al. 2026, see `docs/LITERATURE.md`). The wording is often ambiguous: a cap, a cap with an exception, or only a preference. |
| Design claim | AgeLens keeps the original words next to what is explicit and what is still unclear, and suggests neutral questions, so a person can **ask the employer a clear, answerable question** instead of guessing or self-excluding. It never decides eligibility. |
| Evaluation claim | Seeing AgeLens's evidence check makes the clarification request a person writes **more often usable** than reading the ad alone. |
| What it cannot show | Employment, callback or hiring effects; accuracy of the age parser on real ads; anything about real job seekers' outcomes. |

The evaluated condition is **the product as it exists**: the same rules-only output the Job Seeker page shows for a pasted ad (`api_seeker.check_pasted`, `allow_model=False`). No model and no simulated provider is involved, so the study can run before any model is connected.

## 2. Pre-registered claim and threshold (text to file)

- **H1.** Within the same person, the share of usable clarification requests is higher on tasks with the AgeLens evidence check (B) than on tasks with the ad only (A).
- **Primary outcome.** Per participant, D = usable share on the 2 B tasks − usable share on the 2 A tasks. Missing or empty answers count as not usable.
- **Estimate.** Mean D with a 95% percentile bootstrap CI over participants (20,000 resamples, seed 20261023). Sign-flip randomisation test, two-sided, 20,000 flips; a paired t test is also shown.
- **Success threshold (applied verbatim).** Mean D ≥ **+0.20** AND 95% CI lower bound **> 0**. Any other outcome is reported as "threshold not met", with the estimate and CI.
- **Sample.** Target **N = 24**, which is 6 complete blocks of the 4 sequences. Minimum to analyse: 16. Fixed N, no interim looks. Stop early only for ethics or harm.
- **Harm check (pre-specified, descriptive).** Severe-error rate on B tasks is not more than 10 points above that on A tasks.
- These rules are stored in `data/study/tasks.json > design.threshold`, and `scripts/analyze_study.py` applies them as written.

## 3. Conditions (the only thing that differs)

| | A · Ad only | B · AgeLens evidence check |
|---|---|---|
| Ad text (Chinese, fictional) + English gloss | yes | yes |
| Job seeker profile and their question | yes | yes |
| Aid panel | "No extra help on this task" | AgeLens output under its five headings, with the ad's own wording quoted (rules `age-rules-2.0.0`) |
| Time limit, layout, instructions | 7 min, identical | identical |

Participants write their own message. AgeLens's output is not a draft, and there is no "insert" button. Copying parts of it is allowed, because real users can do that.

## 4. Design and assignment

- **Within-participant crossover.** Each participant does all four fictional tasks (`data/study/tasks.json`):
  - T1: age cap.
  - T2: cap with a qualification exception.
  - T3: age preference.
  - T4: incomplete ad text.
- **Task sets.** S1 = {T1, T3} and S2 = {T2, T4}. Each set has one clearer task and one harder one.
- **Sequences.** There are four sequences, XY-Sk:
  - The first two tasks are in condition X and the last two in condition Y.
  - The tasks of set Sk get B (AgeLens).
  - The four sequences are AB-S1, AB-S2, BA-S1 and BA-S2.
- **Allocation.**
  - Permuted blocks of 4, one of each sequence, from the seeded generator `Random("seed|mode|block")`.
  - The formal seed is set by the approver in `APPROVAL.json`.
  - Task order within each half is shuffled per participant.
  - Allocation happens server-side after consent, and the sequence is never sent to the browser.
- **Why crossover.** Each person is their own control, which removes between-person differences in writing skill.
  - At N = 24 and a true effect of +0.25, power is 0.76. The old parallel design had 0.46.
  - Over a block, every task appears twice in each condition.
- **Carryover risk.** In BA sequences, seeing AgeLens first may improve the later ad-only answers, which shrinks D. That works against H1, not for it.
  - It is checked twice: the order difference (AB vs BA group), and a period-1-only between-participant comparison that has no carryover (section 7).

## 5. Participants and procedure

- **Who.** Adults from the course and its network who agree to take part. TEACHER: confirm who may be recruited, and whether other teams count.
- **Exclusions.**
  - The AgeLens team members do not take part as participants.
  - Nobody who has seen the four study tasks takes part.
  - They are not real job seekers, which is a stated limitation.
- **Session (about 35 minutes), in person or remote, one browser each.**
  1. The facilitator gives the link (`#/study`) and reads the one-paragraph script: purpose, voluntary, about 35 min, no real personal information.
  2. The participant reads the consent text on screen, ticks the box, and clicks Begin. The server then allocates a sequence.
  3. The participant does four tasks of 7 minutes each, with a visible timer. Each request is written in English, 3 to 8 sentences.
  4. A completion screen shows their anonymous code. Withdrawal is possible at any time and deletes the text.
- **Recorded.** Code, sequence, task order, timing, answer, condition, aid provider and rule version. Not recorded: name, email, IP or user agent.

## 6. Scoring

- **Rubric** `rubric-v0.1-draft`. A request is **usable** only if all four criteria are met and no severe error is flagged:
  1. Background accurate.
  2. Citation faithful.
  3. States uncertainty.
  4. Specific, answerable question.
- **Severe errors:**
  - S1: invented fact.
  - S2: eligibility or outcome assertion.
  - S3: legal conclusion or accusation.
  - S4: ignoring or distorting a stated exception.
- **Raters.**
  - **R1 and R2** are two raters who are not in the session and are blind to condition, participant and each other. The scoring desk never shows the condition (tested).
  - **Calibration:** each first scores 6 frozen calibration examples and must reach ≥ 90% agreement with the reference.
  - **R3** sees only R1/R2 disagreements. The final value is the majority of the three.
  - Scores are never edited.
- **Blinding limit.** An answer that copies AgeLens's phrasing can hint at condition B. This is reported, not hidden.
- **Rubric alignment, conceded.** Criterion 3 and the "questions" part of criterion 4 match what AgeLens is designed to help with. That is the mechanism being tested, so it is not a defect. But it means the result says nothing about other qualities of a message.

## 7. Analysis (`scripts/analyze_study.py`, run on the export)

1. **Primary:** mean D, the CI, the p values, the distribution of D, and the threshold decision line.
2. **Order:** mean D in the AB and BA groups, the order-balanced effect, and the AB − BA difference with its CI. A large difference means a period or carryover effect, and the primary result is then read with the period-1 sensitivity next to it.
3. **Sensitivity:**
   - Period 1 only: A in AB group vs B in BA group. This is between participants and has low power.
   - Completers only.
4. **Descriptive:** by condition, each criterion and the severe rate; by task kind × condition. Tasks are not independent, so these figures are not inferential.
5. **Agreement:** Cohen's kappa per criterion (R1 vs R2, before adjudication) and raw agreement.
6. **Always reported:**
   - N enrolled, analysed and excluded per sequence.
   - Dropouts and withdrawals.
   - Null and negative results.
   - Every deviation from this plan.

## 8. Power (`scripts/power_crossover.py`; full table `data/study/power_crossover.md`)

The model is a beta-binomial: each person has their own usable probability (within-person correlation 0.2) and an ad-only baseline of 0.35. **These inputs are assumptions; no pilot data exist.** 4,000 trials per cell.

| N | true effect | power | P(threshold met) | with +0.10 carryover: P(threshold met) |
|---|---|---|---|---|
| 16 | +0.25 | 0.56 | 0.56 | 0.36 |
| **24** | **+0.25** | **0.76** | **0.69** | **0.48** |
| 24 | +0.35 | 0.96 | 0.94 | 0.83 |
| 32 | +0.25 | 0.86 | 0.74 | 0.53 |
| 48 | +0.25 | 0.97 | 0.77 | 0.47 |

- If there is no true effect, the threshold is met by chance in 0.9% of trials at N = 24.
- **What N = 24 can do.** It can detect a large benefit (+0.35) reliably. It misses a true +0.25 about 3 times in 10. A non-met threshold is therefore **not** evidence that AgeLens does nothing; the CI is about ±0.2 and is reported as such.
- **Why a larger N doesn't fix everything.** The threshold has two parts. When the true effect is near +0.20, the estimate falls below it about half the time, whatever N is.

## 9. Approvals and team decisions needed (TEACHER / team)

| # | Decision | Proposed |
|---|---|---|
| 1 | Approve the design, the claim H1 and the threshold | as in section 2 |
| 2 | Recruitment pool and target N | 24 (minimum 16); shortfall reported |
| 3 | Consent text and ethics route | `tasks.json > consent_draft` (updated for the crossover) |
| 4 | Freeze the tasks | sha256 of `tasks.json` recorded in `APPROVAL.json` |
| 5 | Allocation seed | set by the approver |
| 6 | Who are R1, R2 and R3 (not the session facilitator) | team or another team |
| 7 | Where the pre-registration is filed | course drive or OSF; its sha256 goes into `APPROVAL.json` |

Formal mode stays refused by the server until `data/study/APPROVAL.json` exists with all of these. Unlike the old design, it no longer requires a model.

## 10. Dry run, 2026-10-27 (SIMULATED, software only)

**What was run.**
- An isolated server: port 8806, a temporary copy of the database with its study tables emptied, simulation mode. The main database was not touched.
- `tests/browser/study_flow.py` drove **24 simulated participants** through the real participant UI, plus three scripted raters (R1, R2, R3) through the real scoring desk.
- The scripted writers write a "good" request with probability 0.40 on ad-only tasks and 0.65 on AgeLens tasks. **That +0.25 is an assumption built into the script to exercise the analysis. It says nothing about AgeLens.**
- Exports and the analysis are in `data/study/dryrun_2026-10-27/`.

**What it checked, and found.**
- **Allocation:** exactly 6 participants per sequence. Every participant got 2 + 2 tasks in sequence order.
- **Aid panels:** the AgeLens panel showed the real rules output. The ad-only panel showed none.
- **Scoring:** R1 and R2 each scored all 96 answers. 20 disagreements went to R3, and none were left unresolved.
- **Export and analysis:** the export carries the condition and D, and the analysis applies the threshold.
- **Problems found and fixed:**
  - The scoring-desk sign-in in the script clicked the new nav "Sign in" link; the selector was fixed.
  - The simulation banner still spoke of a "simulated provider"; the wording was fixed.

**Output (SIMULATED, not a result):**
- Ad-only 0.583, AgeLens 0.750.
- Mean D = +0.167, 95% CI [−0.042, 0.354], sign-flip p = 0.17. **Threshold NOT MET.**
- So even with a true +0.25 built into the script, this one run of 24 missed the threshold. That is the 24% to 31% miss rate from section 8, seen in practice.

**Not yet done (human only).** A **human pilot**: 2 or 3 people outside the team, not counted, run through the real flow. It checks:
- Whether 7 minutes is enough.
- Whether the instructions are clear.
- Whether two team raters reach the calibration target on real answers.

Record the timings and any rubric wording changes *before* freezing the tasks.

## 11. How to run

```bash
# formal study (after APPROVAL.json exists): the main server, operator switches mode on #/study/score > Operator
.venv/bin/python app.py --port 8765
# rehearsal on a copy (never the main DB):
cp data/agelens.db /tmp/study-copy.db
AGELENS_DB=/tmp/study-copy.db AGELENS_STUDY_TOKEN=<token> .venv/bin/python app.py --port 8806
STUDY_TOKEN=<token> STUDY_OUT=/tmp/out ~/agelens-tools/pw/bin/python tests/browser/study_flow.py http://127.0.0.1:8806 24
python3 scripts/analyze_study.py /tmp/out/SIMULATED_agelens_study_task.json
python3 scripts/power_crossover.py --sims 4000 --check --out data/study/power_crossover.md
```

## 12. What the final presentation must report (rubric: honesty and precision, evaluation execution)

- **Results:**
  - The pre-registered claim and threshold, and whether the threshold was met.
  - Mean D with its CI, and N randomised and analysed per sequence.
  - Dropouts, exclusions, kappa, and the order and period-1 checks.
- **Limitations and decisions:**
  - Every deviation from this plan.
  - The participants are not real job seekers, the tasks are fictional, and the rubric is unvalidated.
  - What the budget forced the team to drop: the connected-model arm.
  - Which halfway recommendations were adopted or rejected, with reasons.
