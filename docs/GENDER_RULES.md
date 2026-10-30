# Gender-requirement rules (`gender-rules-1.0.0`)

`backend/genderparse.py` reads **explicitly written** gender wording about the applicant in a job ad (title + description). Rules only,
no model. It describes how ads are worded; it says nothing about who was hired. Precision was preferred over recall because the field
is sensitive: a guess is worse than a gap.

## What it returns
`parse_gender(text)` returns terms `{kind, snippet, start, end, pattern}` with `kind` one of `male_only`, `female_only`,
`male_preferred`, `female_preferred`, `no_gender_limit`. `gender_class(terms)` gives one class per ad:
`male_only | female_only | male_preferred | female_preferred | no_limit | conflict | none`.

| Class | Meaning | Examples |
|---|---|---|
| male_only / female_only | the ad restricts applicants to one sex | 限男, 仅限女士, 性别：女, 前台（女）, "…，女性，身高160" as a list item |
| male_preferred / female_preferred | one sex preferred | 男士优先, 女生优先, 优先考虑女性, 男性为佳 |
| no_limit | the ad says either sex is welcome, or names both sexes as recruited | 男女不限, 性别不限, 男女均可, 招男女普工, 男女各2名, "男，女", "男性身高170，女性身高160" |
| conflict | male-side and female-side wording together, or a restriction together with "男女不限" (separate posts, or contradiction) | 限男 … 限女 |
| none | no explicit gender wording | the large majority of ads |

Precedence: a preference inside a no-limit statement keeps the preference (`男女不限，女生优先` is `female_preferred`).

## Decisions (what is deliberately not counted)
* Products and categories: 女装, 男装, 男鞋, 母婴, 女士护理, 男科, 男士内裤 (a lookahead on the word after the gender word).
* Customers or users: 女性客户, 面向女性, 服务对象; colleagues and benefits: 男同事, 男员工陪产假, 女生宿舍, 子女 (not 女 alone).
* Contact persons: 王女士 (a surname-like character before 女士/先生), "联系人：…女士".
* 男女老少 and similar; company names; 宝妈, 帅哥美女 (these are not requirements).
* A standard for ONE sex only ("男性身高170cm以上") is left as `none`: it implies a sex but does not write a requirement. Standards for BOTH sexes ("女性身高160，男性身高170") are read as `no_limit` because both sexes are named as eligible. This is a judgement call; it is the most common source of `no_limit` among restricted-looking ads.
* Typos and pinyin ("nan生") are not read. `性别：男（52岁以下）女（47岁以下）不限` is missed.
* Speed: every quantifier is bounded, there are no nested repeats, at most 200 terms are kept per ad. About 20,000 ads/s per core; 20,000-character runs of one repeated pattern take milliseconds.

## Gold set
File `data/raw/gold_gender_2021-2024.jsonl` (git-ignored, contacts masked with `mask_contacts` plus a Chinese-numeral phone mask). 415 real
2021-2024 ads, **one AI annotator, labelled by reading before any rule was run on them**; a few items are low-confidence (the `confidence`
field). No second annotator, so agreement is not measured.

Labelling guideline (the same as the rule decisions above, but applied by reading): label the whole ad with one of the seven classes. Count a
sex only when the text states it about applicants. Reading was done on windows of +-40 characters around every 男/女/性别/先生/小姐/帅哥/美女/
姑娘/小伙 token (plus the title); an ad with no such token is `none`. Heights for one sex only are `none`; heights for both sexes are `no_limit`.

Design: the unfiltered reality is that explicit restrictions are rare, so a random sample alone has almost no positives. Strata (seeded reservoir
samples from all 10,058,826 rows of 2021-2024, drawn by broad word lists that are not the rules):
* **random: 150** ads (the only stratum that estimates prevalence);
* targeted 265: 25 "either sex" wording, 25 male words, 25 female words, 20 preference, 20 male/female lists, 30 near-misses (女装, 母婴, 女神 ...), plus 120 drawn from restriction-looking wording (限男/限女, 男士/女性优先, 性别：男/女, （男）/（女）).
Targeted strata over-sample positives and hard cases, so their precision and recall are not population values.

Gold labels: none 221, no_limit 170, female_only 17, male_only 6, male_preferred 1, female_preferred 0, conflict 0. **Only 24 gold ads
carry a restriction or preference**, so those intervals are wide.

## Results (`python scripts/eval_gender.py`, Wilson 95% intervals)
Two passes. **Pass 1** is the rules as first written, scored once. The errors were then read and the rules fixed (adjacent pairs such as 男性女性,
男（女）, sex-specific heights, 优先 after 1、, 性别：男 女, 子女 and 男（女）宾 lookbehinds). **Final** is the shipped version. The final
numbers are **not held out**: the gold errors drove those fixes, so treat them as optimistic.

| | Pass 1 | Final (tuned on gold) |
|---|---|---|
| Random stratum, any gender wording: precision | 7/7 = 100% [64.6, 100] | 7/7 = 100% [64.6, 100] |
| Random stratum, any gender wording: recall | 7/7 = 100% [64.6, 100] | 7/7 = 100% [64.6, 100] |
| Random stratum, ads without wording flagged (false-positive rate) | 0/143 (upper 95% bound 2.6%) | 0/143 (upper 95% bound 2.6%) |
| Random stratum, class accuracy | 150/150 [97.5, 100] | 150/150 [97.5, 100] |
| Random stratum, restriction/preference | no gold positive and none flagged | same |
| All items, restriction/preference (directional): precision | 20/31 = 64.5% [47.0, 78.9] | 23/24 = 95.8% [79.8, 99.3] |
| All items, restriction/preference: recall | 20/24 = 83.3% [64.2, 93.3] | 23/24 = 95.8% [79.8, 99.3] |
| All items, any gender wording: precision | 184/190 = 96.8% [93.3, 98.5] | 190/191 = 99.5% [97.1, 99.9] |
| All items, any gender wording: recall | 184/194 = 94.8% [90.8, 97.2] | 190/194 = 97.9% [94.8, 99.2] |
| All items, exact class accuracy | 393/415 = 94.7% [92.1, 96.5] | 409/415 = 98.6% [96.9, 99.3] |
| Targeted strata only, class accuracy | 243/265 = 91.7% [87.8, 94.5] | 259/265 = 97.7% [95.2, 99.0] |

Pass 1 restriction precision was low (64.5%) because of `title_paren` firing on 男（女）宾, 生子（女）贺金 and on "（男）…（女）" height lists
(read as conflict). Remaining final errors (6): a female-only item written as a list marker with 岁 before it (`18-30岁女性`), two typos
(男 as 性, pinyin), `性别：男（52岁以下）女（47岁以下）不限`, a "男（女）" rhetorical use read as no_limit, and a mixed
`性别：女，净身高…男，净身高…`.

A further look at 44 rule-flagged restriction items from unlabelled pools (not gold, used partly in development) found 5 errors (2 wrong
detections, 3 wrongly `conflict` for two-sex height lists); the rules were adjusted for them, so this is also not a clean test.

## Limits
One annotator, no agreement measure; gold positives for restrictions are few (24); final scores were tuned on the gold errors (optimistic);
random-stratum intervals are wide where there are few positives; ads that state gender only implicitly (a single-sex height, 宝妈, a female name)
are `none` on purpose; platform ads, wording not hiring outcomes.
