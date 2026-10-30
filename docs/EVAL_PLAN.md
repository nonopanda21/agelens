# AgeLens evaluation plan (crossover-ai-v1)

> **STATUS: DRAFT for teacher approval. Decided by the team on 2026-10-29. Not filed, not approved. No AI model is connected. No participant is recruited. There are no results.** The only data is a SIMULATED dry run of the tools (section 11), written by scripts. It says nothing about AI.

## One-page summary

- **Question.** Does contextual AI assistance help a mid-career job seeker read an ad's age wording and ask the employer a better question than a fixed template does, when both get the same evidence?
- **Design.** Within-person crossover. Every participant does 4 fictional tasks: 2 with a **fixed template** (arm `template`) and 2 with **contextual AI assistance** (arm `ai_contextual`). Order and task-to-arm assignment are counterbalanced (4 sequences, permuted blocks). Participants see only "Tool A" and "Tool B".
- **Same evidence.** Both tools get the same evidence package: the age wording and findings of the AgeLens rules (`age-rules-2.1.0`). The AI tool also reads the job seeker's profile.
- **Outcomes** (scored blind by two raters, a third resolves): **primary = interpretation accuracy**; **key safety outcome = unsupported claims**; secondary = actionable question, completion time.
- **Analysis.** Paired differences (AI minus template) per participant, exact sign-flip test, 95% bootstrap CI. One confirmatory test. Target N = 24 (minimum 16).
- **Claim size (verbatim).** *Improved decision support only. No claim about interviews, hiring, employment or GDP. Any employment benefit would depend on employers responding and considering applicants; the tool cannot remove a binding age restriction.*
- **What exists today.** The study tooling, a rubric, a calibration set, a simulated rehearsal. **What does not:** a connected model, approval, participants, results.
- **While no model is connected,** the AI arm cannot run for real. The server refuses formal mode. Only a clearly labelled SIMULATED rehearsal is possible, in which a script writes the AI-arm text.

## 1. Where this comes from (policy cycle)

| Stage | AgeLens |
|---|---|
| Problem | Mid-career job seekers in China meet short age lines in ads ("35岁以下", "条件优秀者可放宽"; shown in English in the product). The wording is often ambiguous: a cap, a cap with an exception, or only a preference. |
| Mechanism | A person who reads the wording correctly and asks a specific, neutral, answerable question can get a clear reply instead of guessing or self-excluding. |
| Literature | Burn et al. (*Help Really Wanted*, NBER WP 30287) and Belot et al. (IZA DP 10068) motivate the mechanism: ad wording signals who is wanted, and applicants respond to it. They do **not** establish that any tool is effective. The data here are ad wording, not outcomes. See `docs/lit_notes/` and `docs/LITERATURE.md`. |
| This evaluation | Whether contextual AI assistance, compared with a fixed template and with identical evidence, improves interpretation and question quality, without adding unsupported claims. |
| Not shown | Interviews, callbacks, hiring, employment, GDP; accuracy of the age parser on real ads; anything about real job seekers' outcomes. |

The team's wording to the teacher: "We will compare contextual AI assistance with fixed templates using identical evidence, measuring interpretation accuracy, actionable questions, unsupported claims, and completion time. Any employment benefit would depend on employers responding and considering applicants; the tool cannot remove a binding age restriction. Our initial claim is therefore improved decision support, with hiring and broader economic effects reserved for future evaluation."

## 2. Arms (the only thing that differs)

| | Arm 1 · Fixed template (`template`, condition A) | Arm 2 · Contextual AI (`ai_contextual`, condition B) |
|---|---|---|
| Ad text (English), profile card, the job seeker's question | yes | yes |
| Evidence package (rules `age-rules-2.1.0`: wording found, explicit and exception findings, cut-off flag) | yes, identical | yes, identical |
| Tool output | A reading, a 4-item checklist and a question built **by rules** from the evidence: `The ad says: "<age sentence>". Does <the exception \| any exception> apply to the <role>? Please confirm ...`. Same wording structure for every task. It does not use the profile. | A model reads the profile and the same evidence and drafts: (a) a plain-language reading, (b) what is explicit and what is unclear, (c) a targeted question that uses the person's background (for example whether 12 years of experience counts for a stated exception). |
| Checks | none needed (deterministic) | every statement goes through `llm.run_explanation` / `validate_output` (cited evidence, exact quotes, numbers from the rules, no eligibility or legal wording), then a second code check that drops any "you qualify" or accusation. A failed call is recorded and the participant writes alone. |
| Participant label | Tool A or Tool B by period, never the arm name | same |

Both tools only draft. The participant writes the final reading and question, and may start from the draft (recorded as `aid_inserted`).

**The AI never says the user qualifies.** The prompt (`backend/prompts/explain_v1.txt`, rule 5) forbids it, ads and CVs are passed as data inside `BEGIN_DATA_JSON`, and code re-checks the output.

**Third arm ("ad text only").** Not in the primary design. With 4 tasks a third arm cannot be balanced within a person, and each arm would get a third fewer observations (power drops, section 8). The old comparison "ad only versus AgeLens rules aid" stays in the code as the separate design `crossover-rules-v1` (`docs/EVAL_PLAN_v1_rules_vs_ad.md`) and can be run later as a secondary baseline on its own. Arm id `ad_only` exists in `study_arms.tool_aid(..., "none")` for that purpose.

## 3. Participants, tasks, procedure

- **Who.** Mid-career job seekers or proxies: students role-playing a 38-year-old applicant given a profile. **No real personal data.** TEACHER: confirm who may be recruited.
- **Tasks.** The same 4 fictional ads and evidence packages (`data/study/tasks.json`): T1 age cap, T2 cap with a qualification exception, T3 age preference, T4 incomplete text. Sets S1 = {T1, T3}, S2 = {T2, T4}.
- **Sequences.** `AB-S1`, `AB-S2`, `BA-S1`, `BA-S2` (A = template, B = AI; the set Sk gets B; the first half of the session uses the first letter). Permuted blocks of 4 from a seeded generator, server-side; the sequence is never sent to the browser. Within each half the task order is shuffled per participant. Over one block each task has the AI tool twice and the template twice, and AI comes first twice.
- **Session (about 35 min).** Consent, then 4 tasks of 7 minutes with a visible timer. In each task: read the ad, profile and evidence; use the tool; write **(1) your reading** of the age wording and **(2) the one question** you would send. Submit. After the last task the participant is told which tool was which. Withdrawal at any time deletes the text.
- **Exclusions.** Team members; anyone who has seen the tasks.
- **Recorded.** Code, sequence, order, timestamps, texts, tool source, `aid_inserted`, model failures. Not recorded: name, email, IP, user agent.

## 4. Outcomes (pre-specified)

All scoring is by raters who see only the ad, the profile, the participant's reading and question. They never see the tool, the arm, the participant or other raters (tested). Rubric `rubric-ai-v0.1-draft` in `tasks.json > rubric_ai`.

| # | Outcome | Definition | Level |
|---|---|---|---|
| 1 | **Interpretation accuracy (PRIMARY)** | Per task, share of the task's `key_facts` (3 or 4, English) that the reading states correctly, 0/1 per fact. Missing or empty = 0. | Participant mean over 2 tasks per arm |
| 2 | Actionable question | Binary: all four checks met, **q1 specific** (refers to the ad wording and the person's situation), **q2 answerable** in one reply, **q3 neutral**, **q4 no demands**. No question = 0. | Share of 2 tasks per arm |
| 3 | **Unsupported claims (KEY SAFETY)** | Count of statements in the reading and question that neither the ad nor the profile supports: U1 invented content, U2 eligibility/outcome claim, U3 legal or accusation, U4 misstated ad or profile. Lower is better. | Mean count per task per arm |
| 4 | Completion time | Server-side seconds from task open to submit (capped at the limit). | Mean seconds per task per arm |

**Why binary for question quality.** A 0-2 scale loses inter-rater agreement at this sample size and adds noise; the four sub-checks are stored, so partial quality can still be described.

**Why accuracy is primary.** The AI's job is to help the person read the wording correctly; this is the most direct, most objective outcome. **Unsupported claims is the key safety outcome** because an AI that raises accuracy while inventing claims or promising eligibility would be harmful; it is reported with equal prominence and has its own rule (section 6).

## 5. Raters and agreement

Two independent raters (R1, R2) score every non-empty item; a third (R3) scores only items where they disagree on any fact bit, any q check or the unsupported count. Final value: majority per fact and per q check; unsupported count = the agreed value, or the median of three. Unresolved items are reported, not guessed. Scores are never edited. Before real scoring each rater scores 4 frozen calibration items and must agree with the reference on at least 90% of judgements; otherwise the wording is clarified and a new set is used. Agreement reported: Cohen's kappa (fact bits, q checks) and exact agreement plus mean absolute difference (counts), R1 vs R2 before adjudication. Raters are not the session facilitators.

## 6. Analysis and decision rules

- **Unit.** The participant. For each outcome, D = (AI-arm mean) minus (template-arm mean) over that participant's tasks.
- **Test and CI.** Exact sign-flip permutation test on the D values (exact for N up to 16, 100,000 random flips above, seed 20261023); 95% percentile bootstrap CI (20,000 resamples, seed 20261023). Code: `backend/study_stats.py`, `scripts/analyze_study_ai.py`.
- **Family.** **One confirmatory test**: the primary outcome, two-sided, alpha 0.05. The other three outcomes are secondary and exploratory: estimates with CIs, Holm-adjusted p over those three. No other tests are used to support the claim.
- **Evidence of benefit** (accuracy): mean D at least **+0.10** (10 percentage points of key facts) AND CI lower bound above 0 AND p below 0.05.
- **No evidence of benefit:** anything else. This is *not* evidence that the AI does not help: at small N the CI is wide and is reported as it is.
- **Safety signal:** if the CI lower bound of D for unsupported claims is above 0, the report says the AI arm added unsupported claims, whatever the accuracy result. No safety signal at small N is weak reassurance, and is described so.
- **Descriptive only:** order check (mean D when template first versus AI first), accuracy by task, completers only.
- **Missing data.** Missing or empty answers count as accuracy 0, not actionable, 0 claims. Participants with unscored or unresolved items are excluded from that outcome and counted in the report.
- **Stop rules.** Fixed N, no interim looks. Stop early only for harm or ethics: any participant distress, or a model output that breaks the safety rules (promises eligibility, accuses an employer); then the arm is paused and the event is reported.

## 7. Sample size and power (assumptions, not data)

`scripts/power_ai.py`, full table `data/study/power_ai.md`. Assumed: template accuracy 0.60, person-to-person variation (logit SD 0.8), 13 key facts over the 4 tasks. The SD of the participant difference D comes out about 0.25. **No pilot data exist; these inputs may be wrong.**

| N | true effect | P(CI lower bound > 0) | P(evidence-of-benefit rule met) |
|---|---|---|---|
| 16 | +0.10 | 0.25 | 0.25 |
| 16 | +0.20 | 0.81 | 0.81 |
| **24** | +0.10 | 0.40 | 0.37 |
| **24** | +0.15 | 0.74 | 0.72 |
| **24** | +0.20 | 0.94 | 0.93 |
| 32 | +0.15 | 0.85 | 0.79 |
| 48 | +0.10 | 0.68 | 0.40 |

- At **N = 24** the study can reliably detect a difference of about **+0.20** and detects +0.15 about 7 times in 10. A true +0.10 would be missed more than half the time. So a "no evidence" result is common even when a modest benefit is real.
- **Minimum to analyse: 16.** Below that the primary result is reported as inconclusive.
- A third arm (ad text only) would give each arm one third fewer tasks per person, and cost power.
- This power is for the primary only; secondary outcomes are underpowered by design.

## 8. Safety, ethics, data handling

- **Fictional ads only; no real participants' personal data.** Participants are told not to type any. Text is stored for scoring and deleted on withdrawal; exports hold no free text.
- **Approval gate (unchanged).** Formal mode and formal enrolment are refused by the server unless `data/study/APPROVAL.json` is complete (teacher, date, seed, target, preregistration reference and hash, hash of `tasks.json`). This build never creates that file. **New:** formal mode is also refused while no model is connected, because the AI arm would not be real.
- **Model handling per `docs/MODEL_CONFIG.md`.** Keys only in server environment variables, never in the front end, exports or logs; ads and profiles are data, not instructions; cost cap and call log with no content. **The cost cap and any purchase need the teacher's decision (`docs/PENDING_TEACHER.md` item 6). Nothing is bought.**
- **Simulation labelling.** Every simulated session carries `SIMULATED: No AI model was used; text drafted by a script for the rehearsal.` on every participant and rater screen, in every export (`data_label`, `no_model_used`, `tool_source = SIMULATED-script`, CSV header), and in the analysis output. A simulated session is never presented as an AI result and is never exported as formal. In formal mode a simulated drafter is never used: a model failure is recorded and the participant writes alone.
- **Participants** are told one tool is AI-assisted; they are not told which during the tasks (consent text `consent_ai_draft`).
- **Do not recruit, publish, buy or start a formal run** before approval.

## 9. Limits

- Participants are students or proxies, not real job seekers; the tasks are fictional and few (4); the rubric is unvalidated and the key facts were written by the team.
- Raters may infer the tool from style (AI text tends to be fuller). This is reported, not hidden.
- Participants cannot be blind to the style difference of the tools.
- Carryover: using a tool first may change later reading. Order is balanced and checked descriptively.
- Whatever the result, it concerns decision support in a lab task, not effects in the labour market.
- Accuracy depends on the rules' evidence package; if the rules misread an ad, both tools inherit the error.

## 10. Schedule (proposed; none of it is booked)

| When | Step |
|---|---|
| Done 2026-10-29 | Decision, tooling, rehearsal with simulated data |
| Next | Teacher reviews plan, consent, key facts and rubric; items in `docs/PENDING_TEACHER.md` |
| After approval | Decide model, key handling and cost cap; connect model; run a 2-3 person pilot outside the team (timings, rubric wording); freeze `tasks.json`, file the preregistration, write `APPROVAL.json` |
| Then | Calibrate raters; run sessions (target 24); score blind; analyse once |
| Final presentation | Report the primary decision, the safety result, N, dropouts, kappa, all deviations, and the limits above |

## 11. Dry run, 2026-10-29 (SIMULATED, software only; says NOTHING about AI)

- **What.** Isolated server (port 8866, a copy of the database, simulation mode). `tests/browser/study_flow.py` drove **6 simulated participants x 4 tasks** through the real participant UI, and three scripted raters through the real scoring desk. Exports and analysis: `data/study/dryrun_2026-10-29/` (every file prefixed `SIMULATED_`).
- **No AI model was used.** The contextual-tool text is `SimulatedAiDrafter` (script). The scripted writers include each key-fact sentence with probability 0.60 (template tool) or 0.70 (contextual tool); that difference is an assumption built in to exercise the analysis. Completion times are browser-automation seconds and mean nothing.
- **What it checked:** allocation across sequences; the SIMULATED notice on every screen; blinded rater screens (no tool or arm text); calibration; R1, R2 and R3 scoring with 12 disagreements all resolved; export shape and labelling; formal-mode refusal naming both the missing approval and the missing AI model; the paired analysis and decision text.
- **Machinery output (not a result):** the analysis printed accuracy template 0.549 and scripted-contextual 0.743, "no evidence of benefit" at n = 6 (CI crosses 0). These numbers come from the script's own assumption and from 6 scripted people. They must not be quoted as findings.

## 12. NOT yet done

1. **No model is connected** (no provider, key or model id; no spend). The AI arm has never produced a real output. The prompt and adapter are tested only with test doubles.
2. **No participants** recruited; no pilot with humans.
3. **No approval**, no preregistration filed, no `APPROVAL.json`; `tasks.json` not frozen (its sha256 changed on 2026-10-29).
4. **No results.** Rubric and key facts are untested by humans; kappa is unknown.
5. Open: cost cap and who pays; whether students may be recruited; who R1-R3 are.

## 13. How to run (rehearsal on a copy; never the main database)

```bash
cp data/agelens.db /tmp/study-copy.db
AGELENS_DB=/tmp/study-copy.db AGELENS_STUDY_TOKEN=<token> .venv/bin/python app.py --port 8866
STUDY_TOKEN=<token> STUDY_OUT=/tmp/out ~/agelens-tools/pw/bin/python tests/browser/study_flow.py http://127.0.0.1:8866 6
python3 scripts/analyze_study_ai.py /tmp/out/SIMULATED_agelens_study_task.json
python3 scripts/power_ai.py --sims 3000 --out data/study/power_ai.md
# legacy designs: AGELENS_STUDY_DESIGN=crossover-rules-v1 (or parallel-llm-v0) when starting the server
```
