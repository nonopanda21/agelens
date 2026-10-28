# Real data: accuracy audit of the age rules (120 Zhaopin ads, 2021–2024)

> **Single-reviewer judgement, not ground truth.** I am an AI agent, the AgeLens data agent, and I read each ad once and judged it.
> No second coder took part, no agreement was measured, and nobody adjudicated. Treat these numbers as a rough check, not a validated accuracy figure.

## Method

- **Population:**
  - Zhaopin ads published 2021–2024, the range recommended in `docs/REAL_DATA_YEARS.md`, from `data/raw/zhaopin_2016-2025.7.csv`.
  - The rules were `backend/ageparse.py`, `age-rules-2.0.0`, run on the job title + newline + description, as the aggregate does.
- **Draw:** `scripts/real_profile.py --audit-out data/raw/audit_sample_2021-2024.jsonl` (seed 425).
  1. In the streaming pass, each 2021–2024 row became a candidate with probability 0.0004 (seeded). This gave 4,032 candidates.
  2. The candidates were parsed: 1,005 had age terms ("flagged") and 3,027 had none ("unflagged").
  3. 60 flagged and 60 unflagged ads were drawn at random with the same seed.
  4. The sample file holds ad text with contacts masked. It lives in the git-ignored `data/raw/` and is not committed.
- **Judging:**
  - For each ad I read the rule's terms and class next to every passage of the description that mentions 岁, 年龄, 年纪, 年轻, an "x0后" generation, 青年/中年, 退休, 应届 or 毕业生.
  - For unflagged ads I also searched for 出生, 大龄, 宝妈 and the like.
  - An ad's class counts as **right** when the ad-level class (`hard_cap`, `cap_with_exception`, `range_or_min`, `preference`, `ambiguous`, `none`) and any stated maximum age match what the text says about the applicant.
  - Wording about the team ("团队年轻化") or about pupils ("教授6至12岁儿童") is not a condition on the applicant.

## Results

### Flagged ads (60)

| Rule class | Ads | Judged right |
|---|---:|---:|
| `hard_cap` | 15 | 14 |
| `range_or_min` | 35 | 35 |
| `ambiguous` | 10 | 0 (1 debatable) |
| **All flagged** | **60** | **49 (81.7%, 95% Wilson interval 70.1–89.4%)** |

- **Numeric classes (`hard_cap` + `range_or_min`):** 49 of 50 are right (98.0%, 89.5–99.6%). Their stated maximum ages also matched the text.
- **Lenient reading:** if a flag on team-description wording ("年轻化团队") counts as acceptable "unclear wording for a human to check", then 57 of 60 are right (95.0%, 86.3–98.3%).

### Unflagged ads (60)

- **Clear misses: 2 of 60 (3.3%, 0.9–11.4%).** Both state an applicant age range the rules did not read.
- **Wording outside the tool's definition: 4 of 60.** These state a graduate-cohort condition instead of an age: 应届毕业生, 毕业3年以内, 17-20届. That works as an indirect age filter, but the rules are not designed to catch it.
- **The other 54** had no age condition on the applicant. One mentions "6至12岁儿童" about pupils and was correctly not flagged.

About 74.6% of 2021–2024 ads are unflagged. A 3.3% miss rate there would mean roughly 2.5% of all ads carry an age range the rules miss. The interval is wide (0.7–8.5% of all ads). The full-data estimate below is more precise for the two known patterns.

## Common failure patterns

The snippets below are quoted from the ads, are under 30 characters, and contain no contact data.

1. **Team or company description read as age wording** (7 flagged ads, plus 1 debatable).
   - Examples: "公司团队年轻化" · "团队年轻有活力" · "年轻化团队" · "一群跨性格90后" · "80、90后小伙伴" · "90后年轻团队".
   - The VAGUE and GENERATION patterns flag these as `ambiguous`. That inflates `age_wording`, but not `explicit`, `cap` or the maximum ages.
   - The debatable case ("平均年龄23岁" with "只招新手") does signal a young hire profile.
2. **Salary digits read as an age cap** (2 ads).
   - "实发不低于4500" became max 45. That conflicted with the real range 20–26, so the ad turned `ambiguous`.
   - "长期服务奖最高6000元" became `hard_cap` 60.
   - Cause: the first MAX pattern (不超过|最高|低于|…) takes two digits with no check that the number ends there and no 岁 or 年龄 needed.
3. **Ranges with 岁 on both ends, or a doubled dash** (2 missed ads, 1 mis-classified ad).
   - Missed: "18岁至32岁的青年" and "职位要求：20——35岁".
   - "25岁-40岁…可适当放宽年龄" kept only the relaxable term, so the ad became `ambiguous` instead of a range with an exception.
4. **Graduate-cohort proxies** (not counted as errors): "应届毕业生", "毕业3年以内", "17-20届应届大学生".

**Semantics to keep in mind, not an error:** an upper bound inside a range (18–45岁) counts as `range_or_min`, not `cap`. In this sample 35 of the 50 numeric ads were ranges. That is why the map's `cap` (5.8–6.5% per year) is far below `explicit` (20–25%). The ranges still enter `n_max_age` and `median_max_age`.

## Proposed fixes to `backend/ageparse.py` (not applied)

`ageparse.py` was not changed. Below are proposals, with a full-data impact estimate. I made the estimate by running a monkeypatched copy of the rules over all 10,054,663 mapped 2021–2024 ads; that scratch script is not in the repository.

1. **MAX[0]:** add `(?!\d)` plus the existing `NOTUNIT` veto after the age, so "最高6000元" and "不低于4500" no longer match.
2. **RANGE:** add a pattern `AGE UNIT SEP AGE UNIT` (18岁至32岁, 25岁-40岁), and let `SEP` accept a doubled dash ("——", "--").
3. **VAGUE/GENERATION:** drop a low-confidence vague or generation term whose snippet talks about the team (团队, 同事, 小伙伴, 员工, 氛围, 平均年龄, 公司, 我们) and has no 要求, 限, 以下, 以内 or 优先.
4. **Not estimated:** an optional, separately reported "graduate cohort" flag (应届, 毕业N年以内, NN届). It should not be merged into age wording.

**Estimated combined effect of fixes 1–3 on the 2021–2024 aggregate (10,054,663 ads):**

| Measure | Now | With fixes 1–3 | Change |
|---|---:|---:|---:|
| explicit | 2,296,499 | 2,412,775 | +116,276 (+5.1%) |
| cap | 617,437 | 600,198 | −17,239 (−2.8%) |
| age_wording | 2,555,249 | 2,583,541 | +28,292 |
| n_max_age | 2,235,683 | 2,352,151 | +116,468 |
| with_exception | 91,820 | 91,574 | −246 |

**Largest class moves:**

| From | To | Ads |
|---|---|---:|
| none | range_or_min | 107,346 |
| ambiguous | none | 67,772 |
| ambiguous | range_or_min | 21,920 |
| hard_cap | none | 12,436 (false caps from money or other digits) |
| hard_cap | range_or_min | 5,309 |

These fixes were not validated against hand labels. They should go through `tests/test_ageparse.py` and the adversarial set before adoption.

## What this audit does not show

- It does not measure inter-rater agreement, legal relevance or whether employers enforce the wording.
- 60 + 60 ads give wide intervals. A proper evaluation needs two coders and a larger stratified sample.
- Occupation and province mapping were not audited here. They are keyword and lookup rules, covered by unit tests in `tests/test_realdata.py`.
