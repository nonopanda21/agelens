# Rules candidate B (recall-first): `backend/ageparse_cand_b.py`, `age-rules-2.1.0-b`

Drop-in copy of `backend/ageparse.py` (same API, same term fields). One extra function, `parse_cohort()`. Every change is marked in the code with `[F1]`..`[F4]` (the four audit failures) or `[R]` (extra recall). Examples are masked and short. All results are mine alone, with no second judge.

## Changes

| # | Change | Before -> after (examples) | Why |
|---|---|---|---|
| F1 | Age number must end there (no digit after, no 3+ digit number). A unit-less cap needs 年龄/年纪 just before it. `不低于/不小于` is a minimum, not a cap. More money/size/speed words veto (万, 千, 块, 字, cm...). | `最高6000元` max 60 -> none. `不低于4500` max 45 -> none. `年龄不低于25岁` max 25 -> min 25. `打字速度不低于60字` max 60 -> none | Audit failure 1. Also fixes the inverted 不低于 meaning, which the audit did not list. |
| F2 | Separator accepts any dash, doubled dashes, `_`, `一`, `至`, `到`, and the first 岁 is optional. | `18岁至32岁` none -> range 18-32. `20——35岁` none -> range. `18一35岁`, `25―60周岁`, `18- -35岁` -> range | Audit failure 2. 203 doubled-dash ads and 433 岁...岁 ads in the 50k sample. |
| F3 | Drop generation/vague wording when the nearby 15 characters talk about the team (团队, 员工, 小伙伴, 氛围, 公司, 平均年龄...) and carry no requirement word (要求, 以下, 优先, 欢迎...). `平均年龄` never counts as the 年龄 prefix. | `公司团队年轻化` ambiguous -> none. `80、90后小伙伴` -> none. `欢迎90后加入` stays ambiguous. | Audit failure 3. |
| F4 | Graduate cohort (应届, 毕业N年内, 22届) is not an age term. `parse_age()` ignores it. New `parse_cohort(text)` returns separate terms (`kind` "cohort", flag `graduate_cohort`, class `none`). | `应届毕业生` none in both; `parse_cohort` returns it | Audit failure 4. See decision below. |
| R1 | Chinese numerals | `三十五岁以下` none -> max 35. `十八至三十五岁` -> range | recall |
| R2 | 岁内 / 一下 / 或以下 / `（含）` forms | `40周岁内`, `35周岁(含35周岁)以下`, `30周岁一下` -> max | recall |
| R3 | `≤ < ＜`, `18＜年龄＜35`, `年龄上限为40岁`, `年龄不超35` | none -> max or range | recall |
| R4 | Refusal wording | `30岁以上勿扰` min 30 -> max 30. `超过40岁不予考虑` -> max 40. `未满18周岁勿扰` -> low-confidence min | recall and a polarity fix |
| R5 | `年龄在25-35之间`, `年龄：\n25-35`, `35岁\n以下` (line break inside the clause), HTML tags after 年龄:, `年龄：28-452、学历` (glued list number) | none -> range | recall |
| R6 | Birth-year (`1985年以后出生`), stated age (`年龄：30岁`), `年龄30左右`, retirement distance (`距退休10年以上`), Chinese generations (`九零后`) | none -> ambiguous (flags `birth_year`, `retirement`) | They are real age conditions but no cut-off can be computed. |
| R7 | Ages of pupils/customers are skipped (`针对18-35岁女性用户`, `教授6至12岁儿童`). | range -> none | precision |
| R8 | `最好/最好是` before the number is a preference. A number after `放宽到/至` belongs to the exception, not a second cap. `优先` that closes a previous clause (`有客服经验优先  年龄18-40`) does not make the range a preference. | cap 30 -> preference. `可放宽至45周岁` no longer causes a false conflict. | precision, and fewer false conflicts |
| R9 | Speed: sentences with no age-relevant character are skipped. | | speed |

### Decision on graduate-cohort wording

It is not an age condition: 应届 describes a status, and a 40-year-old career changer can be one. Folding it into `age_wording` would add about 6% of all ads (2,944 of 50,435 mention 应届) and would drown the real signal. But it works as an indirect age filter, so ignoring it hides something an applicant cares about. Choice: keep it out of `parse_age()`, `ad_class` and `age_status`, so every existing measure keeps its meaning, and expose it through `parse_cohort()` for a separate "cohort" measure. On the audit sample it finds the five cohort ads (应届毕业生, 毕业3年以内, 17-20届, 25届). The wording `[0-9]{2}届` is the riskiest part (see risks).

## Results

### Unit tests
Existing `tests/test_ageparse.py` copied to scratch, import swapped: 24 of 25 pass. The one failure is `assert RULE_VERSION == "age-rules-2.0.0"`, an intentional change. No test file was edited. Extra cases: 64 of 67 pass my own checklist. The 3 misses are wrong expectations of mine (a legal-minimum 18 is rightly low-confidence; `年龄不超过35` at end of text is the existing truncation rule; the 特别优秀者不限 exception is the existing tested behaviour).

### Population effect, 50,435 ads (seeded random draw of 2021-2024, p=0.005, seed 20261028)

| Class | Current | B | Change |
|---|---:|---:|---:|
| hard_cap | 2,990 | 2,928 | -62 |
| cap_with_exception | 92 | 100 | +8 |
| range_or_min | 8,449 | 9,387 | +938 |
| preference | 71 | 73 | +2 |
| ambiguous | 1,162 | 693 | -469 |
| none | 37,671 | 37,254 | -417 |

Measures: explicit 11,533 -> 12,416 (+7.7%); cap 3,082 -> 3,028 (-1.8%); age_wording 12,858 -> 13,277 (+3.3%); n_max_age 11,212 -> 12,091. This is in the same direction as the earlier audit estimate (explicit +5.1%, cap -2.8%). Explicit is higher because B adds the extra recall patterns. Largest moves: none -> range 753, ambiguous -> none 370, ambiguous -> range 148, hard_cap -> none 86 (false caps from money, typing speed, percent), none -> hard_cap 68 (岁内, 不超35, 三十五岁...).
Ads with graduate-cohort wording: 3,191 (2,290 of them have no age term in B).

### 30 random disagreements (seed 77), my verdict
B right in 29, current right in 1. Examples: `20——35岁` none -> range (B right); `最高70%提成` cap 70 -> none (B right); `年龄大于21岁` none -> min 21 (B right); `团队年轻化` ambiguous -> none (B right). Current right: `年龄18至45岁` plus a later clause `（46岁至50岁会用电脑…可做兼职` makes B read a second range and flag a conflict (B: ambiguous). Single reviewer, not ground truth.

### Audit sample (120 ads)
| | Current | B |
|---|---|---|
| Flagged 60: classes | 15 hard_cap, 35 range, 10 ambiguous | 14 hard_cap, 37 range, 2 ambiguous, 7 none |
| Flagged 60: judged right | 49 | 59 (ad 35, "平均年龄23岁/只招新手", stays debatable) |
| Unflagged 60: clear misses | 2 | 0 (ads 96, 112 now range 20-35 and 18-32) |
| Unflagged: cohort wording | not read | 5 found by `parse_cohort` |

Other audit moves: ad 33 (salary cap 60) -> ambiguous (only the real 18周岁以上 remains); ad 7 (不低于4500 conflict) -> range 20-26; ad 54 -> range 25-40 (the "放宽年龄" text is not attached, so it is range_or_min, not cap_with_exception).

### Speed
Single core, 5,000 real ads, best of 3: current 5,065 ads/s, B 9,158 ads/s. B is faster because it skips sentences with no age character. The 50k comparison (both modules) ran in 3.8 s on 6 workers.

## Risks (new false positives)
- `NN届` in `parse_cohort` can match other things (`第21届`, `连续七届` is guarded, `20届` meaning a class). Only affects the separate cohort flag.
- `NN岁内`, `一` and `_` as separators: `18一35岁` is a typo reading and `21_65` is a guess; a stray `20_30岁` in a product code could match.
- Chinese numerals `十岁`, `二十岁` in pupil text outside the guarded words (儿童, 学员...) can become ranges/caps; the `_ok` 16-70 filter helps.
- A relaxation clause that names a second range (see the item 25 case) raises a conflict and makes an ad ambiguous.
- `STATED` (`年龄：30岁`) and `BIRTH` add low-confidence ambiguous terms; they raise age_wording a little. `距退休N年` is rare.
- Team-wording filter is keyword-based: an ad that says `公司需要90后` with a 需 requirement word is still kept (intended), but `我们期待90后` relies on the added 期待 word.
- No hand labels exist for the 30k+ moved ads; only 30 + 120 were judged, by me.
- A catastrophic-backtracking bug appeared mid-work (nested quantifier in the separator) and was fixed with a bounded repeat. Every sample ad now parses without a time-out, but the full 10 M run has not been done.
