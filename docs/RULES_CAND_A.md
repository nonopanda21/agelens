# Rules candidate A (precision first): `age-rules-2.1.0-a`

- **File:** `backend/ageparse_cand_a.py`. It is a drop-in copy of `backend/ageparse.py` (`age-rules-2.0.0`) with the same public API (`parse_age`, `ad_class`, `age_status`, `term_class`, `has_conflict`, `RULE_VERSION`), the same term fields and the same class semantics.
- **New:** `cohort_terms(text)` returns graduate-cohort mentions separately (see F4). It does not feed any class.
- **Status:** a candidate only. `backend/ageparse.py` is unchanged. The lead scores this file against the blind gold set and decides.
- **Stance:** remove false positives without losing true conditions. Recall was added only where the reading is unambiguous: a range with 岁 on both ends, or a doubled dash.
- Every change is marked `# CAND-A Fn` in the code.
- All snippets below are short, masked extracts from the 2021–2024 Zhaopin sample. Masking used `backend.realdata.mask_contacts`.

## Changes

### F1: other numbers read as ages (audit failure 1)

**Cause:** `MAX[0]` (`最高|不超过|低于|小于… AGE 岁?`) took any two digits, with the unit optional and no check on the next character. `低于` also matched inside `不低于` ("at least"). The rules therefore read salaries, typing speeds, hours, days, heights and percentages as age caps.

**Fix:**
- A two-digit age may not be followed by another digit: `(\d{2})(?!\d)`.
- The comparison-word cap needs 岁/周岁, or a 年龄/年纪 prefix together with the existing `NOTUNIT` veto.
- `低于` and `小于` count only when 不 does not precede them.
- `未满` is read like `不满`. `满` preceded by 未 or 不 is never a minimum.
- A "cap" of 18 or less is dropped. It always describes minors or children (未满14周岁子女, 12岁以下儿童).
- A bound followed by a refusal flips direction:
  - `30岁以上勿扰` becomes a cap of 30. The old rules read it as a minimum of 30.
  - `不满22岁不安排` and `未满18周岁勿扰` become minimums. The old rules read the first as a cap of 21.

| Before | After | Snippet |
|---|---|---|
| hard_cap 60 | (no term) | 长期服务奖最高6000元/年 |
| max 45 → conflict | (no term) | 实发不低于4500 |
| hard_cap 40 | (no term) | 每周工作不超过40小时 |
| max 16 → conflict | (no term) | 身高最低不低于165CM |
| max 40 → conflict | (no term) | 打字速度不低于40字/分钟 |
| hard_cap 18 | min 18 (low, uncertain) | 18岁以下未成年勿扰 |
| range_or_min (min 30) | hard_cap 30 | 2.30岁以上勿扰 |
| hard_cap 21 | min 22, with the range 22–38 | 年龄：22--38周岁，不满22岁不安排 |
| hard_cap 20 | (no term) | 距退休年龄不小于20年 |

These are kept, with the same result as before: `年龄不超过35，`, `年龄：小于35`, `最高45岁`, `2.35周岁以下`, and glued list numbers such as `135岁以下` and `5000-800018-50岁`.

### F2: ranges with unusual separators (audit failure 2)

**Fix:**
- A new first RANGE pattern handles 岁 on both ends: `AGE 岁 SEP AGE 岁`.
- `SEP` now also accepts `——`, `--`, `－－`, `〜` and `∼`.

| Before | After | Snippet |
|---|---|---|
| none | range 18–32 | 招聘对象：18岁至32岁的青年 |
| none | range 20–35 | 职位要求：20——35岁 |
| ambiguous (relaxable only) | range 25–40 | 1、25岁-40岁，大专以上学历 |
| hard_cap 52 | range 16–52 | 年龄16岁-52岁以内 |
| none | preference 22–28 | 年龄在22周岁--28周岁优先 |

### F3: team and company wording (audit failure 3)

**Fix:** a generation term (`90后`) or a vague term (`年轻人`, `年轻化`…) is dropped when either of these holds:

- **Team or company context:** a team or company word (团队, 小伙伴, 员工, 氛围, 公司, 我们, 都是, 为主, 居多, 店长, 副总…) appears within 25 characters, and the term's own clause has no applicant marker (要求, 限, 优先, 招聘, 欢迎, 适合, 希望, 需要, 期待, 应聘, 条件, 资格, 面试…).
- **Audience or income wording:** it is followed directly by audience or income wording (`年轻人审美`, `95后也能月薪过万`).

`年轻化` is dropped unless an applicant marker sits in its clause, because it almost always describes the team (`年轻化团队` appears in many benefit lists).

| Before | After | Snippet |
|---|---|---|
| ambiguous | none | 公司团队年轻化，老板大方有想法 |
| ambiguous | none | 员工都是一群80、90后小伙伴 |
| ambiguous | none | 职位福利：…年轻化团队、团队气氛活泼 |
| ambiguous | none | 公司都是年轻人，气氛轻松有趣 |
| ambiguous | none | 目前基地10位90后副总经理 |
| ambiguous (kept) | ambiguous | 要求： 1、90后，1年以上工作经验 |
| ambiguous (kept) | ambiguous | 欢迎90后加入 / 85后优先 / 希望你是个95后 |

### F4: graduate-cohort wording (audit failure 4): not an age condition

**Decision:** 应届生, 毕业3年以内 and 17-20届 are **not** age conditions, and they get no class.

**Why:**
- **It names a cohort, not an age.** It sets a condition on graduation date. That correlates with age but does not state one: a 30-year-old graduate qualifies.
- **Counting it would change what "explicit" means.** Folding it into `age_status` would mix two constructs and break comparability with every published 2.0.0 number.
- **It is very common, and often not a restriction.** 6.2% of sampled ads mention it (3,130 of 50,435). Many of those mentions only welcome graduates (欢迎优秀应届毕业生加入, 可接受应届博士生).

**What changes:** `parse_age` ignores cohort wording, as before. The new `cohort_terms(text)` returns `{kind: "cohort", flag: "graduate_cohort", snippet, start_offset, end_offset}`, so a separate column such as `cohort_mention` can be reported next to age wording. It is a mention detector, so it does not say whether the mention is a restriction.

**Audit items it flags:** 27, 35, 50, 69, 87, 93, 99, 108 and 118. In 108 and 118 the mention is not a restriction.

### F5: ages that describe other people (new, found in real data)

**Fix:** an age followed directly by a non-applicant population is dropped. The populations are 儿童, 孩子, 子女, 青少年, 学员, 顾客, 用户, 人群, 老人, 患者, 会员 and 消费者, among others. The words 青年, 女性 and 学生 are deliberately not on that list, because they usually describe the applicant.

| Before | After | Snippet |
|---|---|---|
| range_or_min (min 50) | none | 年龄在50岁以上的人群 |
| range_or_min 16–35 | none | 16-35岁的用户人群占比在78%以上 |

### F6: "<other field>不限" read as 不限年龄 (new, found in real data)

**Cause:** `男女不限年龄要求：20岁—45岁` contains the string 不限年龄. The old rules read it as "no age limit" and missed the range, so the ad was classed `none`.

**Fix:** 不限年龄 and 不限年纪 no longer count when 要求, 范围, 限制, a colon or a digit follows them.

| Before | After | Snippet |
|---|---|---|
| none (unlimited) | range 20–45 | 男女不限年龄要求：20岁—45岁 |
| none (unlimited) | range 22–32 | 专业不限年龄范围 22岁-32岁 |

### Speed

**Change:** a sentence with no two-digit run now skips all numeric patterns. That sentence cannot match any of them, so the output is unchanged.

## Results

### Unit tests

- **Method:** the existing tests ran against the candidate through `sys.modules` monkeypatching. No test file was edited. Script: `/tmp/claude-1002/-home-mssep-delta/e834b7a3-c216-403d-9d99-e7249ce46d5d/scratchpad/cand_a/run_tests.py`.
- **`tests/test_ageparse.py`:** 24 of 25 pass. The one failure is intentional: `test_term_fields_present` asserts `RULE_VERSION == "age-rules-2.0.0"`.
- **All 16 unit-test modules (287 tests):** 286 pass, and the only failure is the same version assertion. On the current module all 287 pass.
  - On one earlier run, both the current module and the candidate also failed `test_realdata.test_same_as_evidence_matrix` and `test_pro.test_sections_labels_and_quotes`. Both passed on two reruns, so they look environment-dependent and are unrelated to these rules.
- **Candidate behaviour:** `/tmp/claude-1002/-home-mssep-delta/e834b7a3-c216-403d-9d99-e7249ce46d5d/scratchpad/cand_a/test_cand_a.py` has 9 test groups covering F1–F6, and all 9 pass.

### Real-data sample

**Sample:** 50,435 ads drawn at random, with seed 20261028 and p = 0.005 per 2021–2024 row, from `data/raw/zhaopin_2016-2025.7.csv`. The text is title + newline + description, contacts masked. A disjoint development sample of 201,230 ads (p = 0.02, same pass) was used to design the rules. The numbers below come from the untouched evaluation sample.

| Class | Current 2.0.0 | Candidate A | Change |
|---|---:|---:|---:|
| hard_cap | 2,990 | 2,866 | −124 |
| cap_with_exception | 92 | 92 | 0 |
| range_or_min | 8,449 | 9,129 | +680 |
| preference | 71 | 73 | +2 |
| ambiguous | 1,162 | 625 | −537 (−46%) |
| none | 37,671 | 37,650 | −21 |
| **explicit** (status) | 11,533 | 12,088 | +555 (+4.8%) |
| **cap** measure | 3,082 | 2,958 | −124 (−4.0%) |
| age_wording | 12,858 | 12,881 | +23 |
| with_exception | 436 | 424 | −12 (F6: a false "unlimited" no longer counts) |

**Class moves (1,438 ads differ, 2.9%):**

| From | To | Ads |
|---|---|---:|
| none | range_or_min | 512 |
| ambiguous | none | 405 |
| ambiguous | range_or_min | 140 |
| hard_cap | none | 92 |
| hard_cap | range_or_min | 36 |
| ambiguous | hard_cap | 15 |
| hard_cap | ambiguous | 11 |
| range_or_min | ambiguous | 7 |
| none | ambiguous | 5 |
| others | | 3 |

**Rough scale to the 10.05 M 2021–2024 ads:**

| Measure | Change |
|---|---|
| explicit | about +4.8% (≈ +111 k ads) |
| cap | about −4.0% (≈ −25 k ads) |
| false caps removed (hard_cap → none) | ≈ 18 k ads |
| none → range_or_min | ≈ 102 k ads |

These are close to the earlier audit's estimates: explicit +5.1%, cap −2.8%, 12,436 false caps removed, 107,346 unclassified ads moved to range. The cap fall is larger here for two reasons: F1 also removes hours, days, typing speeds and heights, and ranges that also say 以内 become ranges.

**30 random differing ads (seed 30) with my verdict.** A = candidate right, C = current right.

| # | Current | Candidate | Term change | Snippet (masked) | Verdict |
|---|---|---|---|---|---|
| 1 | ambiguous | none | −vague | …多次晋升机会、年轻化团队、无官僚风气 | A |
| 2 | ambiguous | none | −vague | 优秀员工奖金、年轻化团队职位亮点 | A |
| 3 | none | range_or_min 45 | +range 26–45 | 1、年龄在26岁-45岁，有2年及以上 | A |
| 4 | ambiguous | none | −vague | 公司都是年轻人，气氛轻松有趣 | A |
| 5 | ambiguous | none | −vague | 优秀员工奖金、年轻化团队、团队气氛活泼 | A |
| 6 | none | range_or_min 38 | +range 18–38 | 1、年龄18--38岁、热爱HR岗位工作 | A |
| 7 | none | range_or_min 36 | +range 33–36 | 1、年龄于33岁—36岁之间 | A |
| 8 | none | range_or_min 45 | +range 18–45 | 【加入要求】 男女不限，18岁至45岁 | A |
| 9 | ambiguous | none | −generation | 00后年轻化团队气氛活泼 | A |
| 10 | none | range_or_min 35 | +range 18–35 | 2、18周岁~35周岁 | A |
| 11 | ambiguous | range_or_min 35 | −max 17 | 每月累计上班时间不超过176小时 | A |
| 12 | none | range_or_min 40 | +range 23–40 | 年龄23岁至40岁 | A |
| 13 | none | range_or_min 50 | +range 18–50 | 任职资格：年龄18岁到50岁之间 | A |
| 14 | none | range_or_min 40 | +range 18–40 | 18岁~40岁 | A |
| 15 | range_or_min 35 | range_or_min 35 | −vague | 收入稳定增长，年轻人多，工作氛围好 | A (term only) |
| 16 | none | range_or_min 50 | +range 18–50 | 1、18周岁-50周岁，品行端正 | A |
| 17 | range_or_min 35 | range_or_min 35 | −vague | 公司都是年轻人~~~工作氛围轻松 | A (term only) |
| 18 | none | range_or_min 32 | +range 24–32 | 年龄范围：24周岁-32周岁 | A |
| 19 | none | range_or_min 35 | +range 22–35 | 年龄：22--35周岁  大专及以上学历 | A |
| 20 | range_or_min 35 | range_or_min 35 | −generation | 公司氛围：公司90后、00后为主 | A (term only) |
| 21 | ambiguous | none | −generation | 90后团队欢乐多 | A |
| 22 | ambiguous | range_or_min 35 | −max 40 (conflict) | 打字速度…不低于40字/分钟 | A |
| 23 | none | range_or_min 50 | +range 16–50 | 招聘年龄：16岁~50岁 | A |
| 24 | none | range_or_min 50 | +range 23–50 | 年龄：23岁——50岁，热爱销售工作 | A |
| 25 | none | range_or_min 50 | +range 16–50 | 男女不限，16岁-50岁 | A |
| 26 | none | range_or_min 30 | +range 20–30 | 年龄20岁-30岁之间，男女不限 | A |
| 27 | range_or_min 30 | range_or_min 30 | same range, shorter snippet | 18~30岁，普通话标准 | A (snippet only) |
| 28 | ambiguous | ambiguous | −generation | 全集团已有90后店长656名 | A (term only) |
| 29 | range_or_min 39 | range_or_min 39 | −vague | 受年轻人喜欢的工作氛围，团队年轻化 | A (term only) |
| 30 | ambiguous | none | −vague | 3：年轻化团队 | A |

**Verdict:** 30 of 30 favour the candidate, and the current rules are right in none. In 6 of them only a term or snippet changed, not the class.

**Riskier moves in the evaluation sample, all read:**
- **hard_cap → ambiguous (11):** 10 are removed false caps such as 最高6000元 or 不超过24小时 next to a legal minimum of 18. The other is a two-role ad (35岁以下 and 25岁-30岁) that is now flagged as a conflict. All 11 favour the candidate.
- **range_or_min → ambiguous (7):**
  - 5 are multi-role ads whose second range is now read, so the existing conflict rule fires.
  - 1 is `18岁-26岁，30岁以上勿扰`. It is now a conflict, which beats the old false "minimum 30".
  - 1 is worse: in `18周岁—45周岁，且未满45周岁`, 未满45 becomes 44, so the two terms conflict.
- **none → ambiguous (5):** all are multi-role ads with several ranges, now flagged as conflicts.

### The 120 audit items

**Method:** the expected class is the rule class wherever the earlier reviewer judged it right. For the 13 items the audit lists as wrong or missed, it is the class the reviewer's notes imply. Script: `/tmp/claude-1002/-home-mssep-delta/e834b7a3-c216-403d-9d99-e7249ce46d5d/scratchpad/cand_a/audit.py`.

| | Current 2.0.0 | Candidate A |
|---|---:|---:|
| Right (strict) | 107 / 120 | 119 / 120 |
| Right (lenient: item 35, `平均年龄23岁` + `只招新手`, accepted as ambiguous) | 108 / 120 | 120 / 120 |
| Flagged stratum (60) | 49 (+1 debatable) | 59 (+1 debatable) |
| Unflagged stratum (60) | 58 | 60 |

**Items fixed:**
- **Team wording, now none:** 5, 19, 24, 29, 31, 38 and 39.
- **7:** the false 45 from 不低于4500 is gone, and the 20–26 range stands.
- **33:** the false cap of 60 is gone. The ad now carries only the legal minimum of 18, so it is ambiguous.
- **54:** now range 25–40.
- **96 and 112:** the missed ranges are now read.

No item that was right became wrong.

**Caveat:** these 120 items were the known failures, and I designed against them. They are not held-out evidence. The 50,435-ad comparison and the blind gold set are the fair tests.

### Speed

**Method:** single core, the first 20,000 evaluation ads, `parse_age` + `ad_class`, 3 repeats.

| Module | Ads per second |
|---|---:|
| Current | ≈ 5,290 |
| Candidate A | ≈ 5,860 |

The candidate is about 11% faster, thanks to the two-digit pre-check. Without that pre-check it was about 4,830 ads/s, roughly 9% slower than the current module.

## Risks: what could now be missed or misread

1. **Unit-less caps without a 年龄 prefix are no longer read.** `任职条件：1、小于40，大专` and `年龄不超过304、` (a list number glued on) are dropped. In the development sample, comparison-word caps without 岁 were about 1,675 hits, nearly all money, hours or speeds. Only about 7 of them had a 年龄 prefix, and those are kept.
2. **Caps of 18 or less are dropped.** A genuine cap that low would be lost, but no such case appeared in the development sample.
3. **More conflicts.** Reading more ranges exposes more multi-role ads (`服务员18——35岁 … 传菜员18——30岁`), which the existing conflict rule turns into `ambiguous`. That follows 2.0.0's semantics, but it shifts some ads from `none` to `ambiguous` rather than to `range_or_min`.
4. **F3 is keyword-based.** An applicant condition worded only with team words and no applicant marker would be dropped: `我们只要90后` keeps its term (只要), but `团队成员须为90后` would lose it. Such conditions are vague (`ambiguous`) in 2.0.0 anyway, so no numeric limit is lost.
5. **F5's population list** may drop a real condition when an applicant is described with one of those nouns, for example `招18-25岁学员` for a trainee role. 学生 and 青年 were left out for this reason.
6. **未满 conversion.** `未满45周岁` becomes 44 (the same convention as 不满). When an ad states both `18—45周岁` and `未满45周岁`, the result is a false conflict. It was seen once in 50,435 ads.
7. **The cohort flag is a mention detector.** It does not separate a restriction (`仅限应届生`) from a welcome (`欢迎应届生`), and any `NN届` matches, so `第21届` would match too. It never touches the age classes.
