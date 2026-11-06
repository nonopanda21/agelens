# AgeLens evaluation plan (parallel-rct-v1)

> **STATUS: DRAFT for teacher approval. Chosen by the team on 2026-11-05, from the halfway slides and action guide in `course_materials/`. Not approved. No frozen test set, no participants, no results.** Earlier designs: `EVAL_PLAN_v2_crossover_ai.md`, `EVAL_PLAN_v1_rules_vs_ad.md`.

## Summary

| Item | Plan |
|---|---|
| Claim | AgeLens improves accuracy and reduces search time on these reading tasks. No claim about interviews, hiring or employment. |
| Design | Parallel randomized test, one person in one group throughout. |
| Assignment | Server randomizes each person once, 1:1 in permuted blocks of 4. Analysed as assigned. |
| Counterfactual | Control answers the same cases without AgeLens. |
| AI comparison | A model answers the same cases alone, compared with the control group. Not participants. |
| Primary outcomes | Score (correct / 32 x 100) and mean seconds per case, capped at 120. |
| Success rule | Accuracy: beta >= 10 points and robust 95% CI above 0. Then time: theta's robust 95% CI below 0. "More accurate and faster" needs both. |
| N | Not set. Comes from the pilot and recruiting reach. See Power. |

## Test set

Sample: `scripts/draw_rct_sample.py` draws 384 ads from 2021-2024: 4 provinces x 16 occupation groups x 6 ads. In each cell, 3 ads with a stated maximum age are for hand rewriting into indirect wording, 2 are kept with their stated maximum, 1 has no age wording. The sample holds ad text, so it stays in `data/raw/rct_sample/` (git-ignored).

Choices the action guide left open, made when drawing and open to change: provinces 广东, 江苏, 河南, 四川 (large provinces across four regions); the 2 + 1 split of kept ads; years 2021-2024; descriptions of 80-1,500 characters. The 16 groups are occupations read from job titles, not industries.

The team still has to clean contacts and HTML by hand, rewrite 192 ads, write CVs and answers, and freeze 32 pairs: 16 explicit or neutral, 16 indirect; 8 per province; 2 per group; 12 Match, 12 Conflict, 8 Unknown. The rules only propose candidates; they are not an answer key. Anyone who wrote the set or saw the answers does not take the test.

Two files go to the test desk:
- `cases.json`: `version`, `practice[]`, `cases[]`. Each case has `id`, `source_ad_id`, `job_title`, `ad_text`, optional `ad_text_en`, `entry_date`, `cv` (`name`, `birth_date`, `graduation_date`, `education`, `years_experience`, `experience[]`), `stratum` (`wording`, `province`, `occupation`). No answers: the import refuses them.
- `answer_key.json`: `version`, `answers{id: {gold_label, evidence_text, rationale, no_age_limit}}`. It stays on the server.

## How it runs

The public site shows the test as a simulated rehearsal; `AGELENS_RCT_ENABLED=0` removes it. Participant page `#/study`, desk `#/study/admin` (needs `AGELENS_STUDY_TOKEN`). Consent, group, 2 practice cases, 32 cases in random order, one question about other tools. Nobody sees the answers.

The server holds the group, the order and the clock. Time starts when a case is first shown and includes AI waiting. Refreshing or closing the page does not reset it. At 120 seconds the case closes with no answer. The first answer stands. Control is refused by the tool route. Treatment sees the product's own output, which explains and never says Match or Conflict. Model failures are shown and logged, and rules text is labelled as such; nothing is invented.

## Missing data

**Not yet fit for a formal run:** a review on 2026-11-05 found defects to fix first, including Chinese case text being hidden on the page, a silent fallback from formal to simulation, and cases readable before the run starts.

Unanswered or unreached cases count as wrong and 120 seconds, and stay in the group they were assigned to. Timeouts, missing rate and tool failures are reported per group. A person who withdraws has their answers deleted, as the consent says, and only the count per group is reported. The action guide counts all exits as wrong; the deletion on withdrawal is our addition, because the consent promises it. **The teacher should confirm this.**

## Analysis

`scripts/analyze_rct.py` on the desk's exports. One row per person, group as the only regressor, robust standard errors as Stata's `vce(robust)`, plus a randomization check. Explicit and indirect results and two error types (a no-limit ad called Conflict; a definite answer on an Unknown case) are supplementary. The desk shows counts only, so nobody can stop on seeing a result.

## Power (assumptions, not data)

`scripts/rct_power.py`, table in `data/study/power_rct.md`. Assumes score SD 20, time SD 25 s, no pilot.

- The slides' formula (112 / sqrt(N)) and the guide's 126 people are for beating zero. Simulation agrees: about 80% at N = 126 for a true 10 points.
- The full rule also needs the estimate itself to reach 10. With a true gain of exactly 10 it passes at most about half the time at any N.
- At N = 40: true gain 20 passes 87%, 15 passes 63%, 10 passes 34%. Both rules at gain 15 and 10 s saved: about 14%.

**A realistic reading for the class:** the test can detect a large accuracy gain, and probably cannot support "faster" as well unless the time saving is large or times vary less than assumed. The team should decide this before recruiting.

## Before a formal run

The server refuses formal mode until all of these hold:
1. `data/study/RCT_APPROVAL.json` exists with `approved: true`, `teacher_name`, `approval_date`, `stopping_rule`, `recruitment_target`, `allocation_seed`, `case_set_sha256`. Only the team writes it, after approval. No code here creates it.
2. An imported set meets the design above and matches that hash.
3. A real model is connected. Check `AGELENS_LLM_MAX_CALLS_PER_DAY`: each treatment person may use up to 34 calls.
4. `AGELENS_RCT_DURABLE=1`, set only when storage survives a restart.

**Storage is the biggest practical risk.** The live site is on Render's free plan with no persistent disk, so a restart or deploy erases all answers. A formal run needs a paid disk with `AGELENS_DB` on it (the team's decision; nothing is bought automatically), or another host that keeps files.

## Open decisions for the team

1. Testers' language: the ads are Chinese and the site is English. Recruit Chinese readers, or add `ad_text_en` to all 34 cases.
2. N, from the pilot.
3. Whether "faster" stays in the headline claim, given the power above.
4. Treatment output: AgeLens does not give a label. If it stays that way, the test measures whether its explanation helps, not whether it answers correctly.
5. Confirm with the teacher: withdrawal handling, and that a study on team-rewritten wording is acceptable.

## What this cannot show

Testers know their group, and control could open another tool (asked at the end, reported). The rewrites are the team's, so results do not describe how employers hint at age. Nothing here measures hiring or job outcomes.
