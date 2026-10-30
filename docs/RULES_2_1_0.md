# Age rules 2.1.0: what changed and why

**Decision (2026-10-29):** `backend/ageparse.py` is now `age-rules-2.1.0`. The previous file is kept as `backend/ageparse_v2_0_0.py`, and the precision-first candidate as `backend/ageparse_cand_a.py`, so the comparison can be repeated with `scripts/eval_rules.py`.

## How it was chosen
Three versions were scored on the same hand-labelled set of 415 real ads (`docs/RULES_GOLD.md`; one annotator, labels written before any rule was run):

| | 2.0.0 (before) | Candidate A | **2.1.0 (adopted)** |
|---|---:|---:|---:|
| Class accuracy, all 415 ads | 75.7% | 87.2% | **94.9%** (95% CI 92.4–96.7) |
| Class accuracy, random 150 (unbiased) | 98.0% | 98.7% | 98.7% |
| Detection recall, all | 78.4% | 84.1% | **97.8%** |
| Detection precision, all | 86.8% | 92.3% | 92.9% |
| Highest age read exactly | 70.4% | 90.5% | **96.8%** |

The 415 ads over-sample hard cases on purpose, so the "all" rows show how well each version handles the known failure patterns. On ordinary ads (the random 150) the old rules were already right 98% of the time.

## What changed (details: `docs/RULES_CAND_B.md`)
1. Other numbers are no longer read as ages: salary (最高6000元), heights, typing speed. "不低于25岁" is now a minimum, not a maximum.
2. Ranges with any separator or with 岁 on both ends are read (18岁至32岁, 20——35岁).
3. Team and company wording (团队年轻化, 90后小伙伴, average age) is not an applicant condition.
4. Graduate-cohort wording (应届) is not an age condition. It is reported separately by `parse_cohort()` and never changes a class.
5. Chinese numerals (三十五岁以下), 岁内, 以下 forms, "30岁以上勿扰" (a cap), line breaks inside an age clause.
6. A guard cuts very long runs without a sentence stop into short pieces, so a hostile 4,000-character paste is parsed in 0.3 s (the old rules could take many seconds). Added after a timing test; tests in `tests/test_ageparse_gold.py`.

## Effect on the published real-data numbers (10,054,663 Zhaopin ads, 2021–2024)
| | 2.0.0 | 2.1.0 | change |
|---|---:|---:|---:|
| Ads that state an age requirement ("explicit") | 2,296,499 | 2,470,588 | +7.6% |
| Ads with a cap | 617,437 | 604,743 | −2.1% |
| Any age wording | 2,555,249 | 2,642,894 | +3.4% |
| Share of highest limits at 35 / at 45 (all years) | 26.4% / 19.4% | 26.4% / 19.8% | same story |
| 2024: share at 35 / at 45 | 20.1% / 22.9% | 19.8% / 23.4% | 45 still overtakes 35 |

Earlier documents (`docs/REAL_DATA_YEARS.md`, `docs/REAL_DATA_AUDIT.md`) quote numbers produced by 2.0.0 and are left as the record of that run.

## Limits
- One annotator, no second person: agreement is not measured (a repeat labelling by the same annotator agreed on 39 of 40 classes).
- The labelled set is small (415). The intervals above are wide enough that the three versions' ranking is clear, but individual percentages are approximate.
- Remaining known errors: an exception clause that names a second range can make an ad look contradictory; typo separators (18一35) are guesses; the team-wording filter is keyword-based.
- Rules read wording; they do not know whether an employer applies the limit.
