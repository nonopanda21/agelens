# Preregistration — DRAFT

> **SUPERSEDED 2026-10-27:** the claim, threshold and sample to pre-register are in `docs/EVAL_PLAN.md` section 2. The text below belongs to the legacy parallel design.

> **DRAFT — NOT FILED, NOT APPROVED.** This text has not been submitted to any registry, has no registration id or hash, and has not been approved by the teacher. Nothing below may be described as preregistered until it is filed, its SHA-256 recorded in `data/study/APPROVAL.json`, and the teacher has approved. Bracketed items [TEACHER] are open decisions. Details and rationale: `docs/EVAL_PROTOCOL.md`.

1. **Title.** Does drafted help raise the share of usable clarification requests about age wording in job ads, compared with a fixed template? (fictional tasks, classroom sample)
2. **Hypothesis H1 (directional, two-sided test).** Mean participant usable share (usable tasks/4) is higher with drafted help than with the fixed template. H0: no difference.
3. **Design.** Parallel two-arm randomised study; permuted blocks of 4, seeded; allocation concealed until enrolment; each participant completes the same four fictional tasks (age cap; qualification exception; age preference; incomplete evidence) in randomised order, 7 minutes each [TEACHER].
4. **Population / sample.** Classmates and volunteers recruited by the team; target N = [24 pilot | 48] [TEACHER]; fixed N, no interim analysis.
5. **Arms.** Template: fixed generic template. Assisted: model-drafted help from the connected model adapter (model name, prompt version and settings to be recorded before data collection). Identical information, limit and UI.
6. **Primary outcome.** Participant usable share, from two blinded raters (criteria: background accurate; citation faithful; states uncertainty; specific and answerable; no severe unsupported claim: S1 invented fact, S2 eligibility/outcome assertion, S3 legal conclusion, S4 ignoring/distorting a stated exception). Disagreements resolved by majority of R1, R2, independent R3. Missing or unattempted tasks = not usable.
7. **Secondary outcomes.** Usable on >= 3 of 4 tasks; time on task; timeouts; model failures; aid insertion; inter-rater kappa; dropout.
8. **Analysis.** Difference in means with percentile-bootstrap 95% CI; two-sided randomisation test as the primary p-value; Fisher exact + Newcombe CI for the secondary binary; completers-only sensitivity. Software: `scripts/analyze_study.py` (seeded), version recorded.
9. **Threshold [TEACHER].** The result is described as supporting H1 only if the 95% CI lower bound > 0 AND the point estimate >= +0.20 in usable share. Otherwise reported as not supported / inconclusive with the CI.
10. **Power.** Seeded simulation (`scripts/power_analysis.py`): at N=24, baseline .35, task correlation .2, 80% power needs a true effect of about +.37 (Welch; about 5 points optimistic); +.25 is detected about 46% of the time. A null at N=24 is inconclusive. Assumptions are unverified guesses (no pilot).
11. **Rater procedure.** Calibration on 6 frozen examples (>= 90% agreement with reference, severe flags matched) before scoring; raters blind to arm and to each other; scores immutable once submitted.
12. **Exclusions.** Withdrawn participants (text deleted, counted as dropouts); participants with unresolved scores excluded from primary analysis until resolved (count reported); no outcome-based exclusions.
13. **Stopping rule [TEACHER].** Stop only for ethical concern, or if > 20% of drafted-help calls fail (then report as a system failure and do not interpret the arm comparison).
14. **Deviations and reporting.** All deviations will be listed. We will report effect size, CI, N randomised/analysed per arm, dropouts, model failures, and null/negative results.
15. **Limits.** Fictional tasks; classroom participants; no employment, hiring-probability, GDP or legal claim can follow; classification accuracy of the extractor is a separate question.
16. **Registry / hash / approval.** Registry: [not chosen]. Reference: [none]. SHA-256: [none]. Teacher approval: [none]. Ethics route: [TEACHER].
