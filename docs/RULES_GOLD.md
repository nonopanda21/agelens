# Blind gold set for the age rules (2021–2024 Zhaopin ads)

> **One AI annotator, no second human coder, no agreement measured.** These labels are one careful reader's judgement under a
> written guideline, made BEFORE any rule was run on the items. They are a reference for comparing rule versions, not ground truth.

## 1. Labelling guideline (written before labelling)

The label describes what the **stored text** (`text`, at most 600 characters) says about **the applicant**, the person being hired.
Text outside the stored window does not exist for the label, so the rules and the gold always see the same characters.

### 1.1 `has_age_condition`

**True** when the text states an age-based condition or preference on applicants:

- a numeric bound: maximum, minimum, range or approximate age (35岁以下, 年满22周岁, 18-45岁, 30岁左右), in Arabic or Chinese numerals (三十五岁以下);
- a soft numeric bound (35岁以下优先, 25-35岁为宜);
- a generation requirement or preference about applicants (限90后, 90后优先, 要求85后);
- vague youth wording that describes the wanted applicant (要求年轻有活力, 年轻者优先, 年龄适中);
- a bare age requirement with no usable content (年龄要求： and nothing after it, 年龄符合要求);
- a legal minimum only (年满18周岁, 16周岁以上, 已成年).

**False** for:

- 年龄不限 / 不限年龄 / 年龄无要求: an explicit statement that there is no limit;
- team or company description: 团队年轻化, 90后团队, 平均年龄25岁, 年轻的团队, 公司成立10年;
- ages of other people: pupils (6-12岁儿童), patients, the elderly cared for, customers;
- graduate cohort: 应届生, 毕业3年以内, 2023届. These are education status, not age; they are an indirect age filter in practice, so the
  gold records them in a separate field `grad_cohort` (see 1.5), but they do NOT count as an age condition. Reason: the rules
  and the published measures are defined over age wording; mixing a proxy in would change what "explicit" means, and a
  graduate can be any age. The lead can report the proxy separately.
- other proxies such as 退休人员 / 退休返聘 / 宝妈 / 学生 / 在校生 (same reasoning; noted in `note`);
- 身体健康, 男女不限, 成熟稳重, 吃苦耐劳 and other non-age wording;
- experience years (5年以上经验, 工作经验3-5年), years of service, company age, salary or other digits.

### 1.2 `class` (same six classes and the same priority as `ageparse.ad_class`)

Ad level, highest priority first: `cap_with_exception` > `hard_cap` > `range_or_min` > `preference` > `ambiguous` > `none`.

| Class | Meaning | Examples |
|---|---|---|
| `hard_cap` | a firm upper bound, no lower bound stated for that requirement, no relaxation | 35岁以下, 不超过40周岁, 年龄45岁以内, 限30岁, 不满35周岁 |
| `cap_with_exception` | a firm upper bound (no lower bound) plus a stated relaxation of the age | 40岁以下，优秀者可放宽; 45岁以下，特别优秀者年龄不限 |
| `range_or_min` | a firm range (any lower bound, 16/18 included) or a firm minimum above 18; a range keeps this class even with a relaxation (as `term_class`) | 18-45岁; 年满18周岁，45周岁以下; 25岁以上; 25-35岁，优秀者可放宽 |
| `preference` | age wording that is explicitly soft (优先, 为宜, 最佳, 更佳, 佳) and no firm bound elsewhere | 35岁以下优先; 优先考虑30岁以下; 年轻者优先; 90后优先; 25-35岁为宜 |
| `ambiguous` | age wording on the applicant with no usable firm numeric limit | 30岁左右; 限90后; 要求年轻; 年龄要求： (nothing after); legal minimum only (年满18周岁); a cut-off age clause; genuinely contradictory statements (年龄不限 … 35岁以下) |
| `none` | no age condition on the applicant | no age wording; 年龄不限; team wording; 应届; experience years |

Decisions on edge cases:

- **Lower and upper bound anywhere in the ad for the same post → `range_or_min`**, even if they sit in different sentences
  (年满18周岁 … 45周岁以下). This follows the audit's semantics: an upper bound inside a range is a range.
- **Several posts in one ad:** the class is the highest-priority class over all posts; `max_age` is the smallest firm cap
  (evidence uses MIN(max_age) per ad).
- **Different caps by gender** (男45岁以下，女40岁以下): `hard_cap`, `max_age` = the smaller cap, confidence low.
- **A relaxation next to a cap** ("优秀者年龄可放宽", "条件优秀者年龄不限", "可适当放宽") → `cap_with_exception`, `has_exception` true.
  年龄不限 that is a relaxation of a stated cap is an exception, not a contradiction.
- **A firm bound and a preference together** (20-40岁，30岁以下优先) → the firm bound's class wins.
- **以上 / 以下 / 以内** are read as inclusive bounds (35岁以下 → max 35). 不满35周岁 → max 34 (as the rules).
- **A minimum of 16 or 18 only** is the legal working age, not a usable limit: `ambiguous`, `min_age` 16/18,
  `has_age_condition` true (it is age wording about the applicant; the rules' `age_status` calls it "uncertain").
- **Title text counts** (普工18-50岁 in the title is a range).
- **Salary, hourly pay, headcount, dates and experience digits are never ages**, even next to 不超过/最高/不低于.
- **Unclear referent** (年轻 could describe the team or the applicant): choose the more likely reading and mark `confidence: low`.

### 1.3 `min_age`, `max_age`

Integers for the firm bounds behind `hard_cap`, `cap_with_exception` and `range_or_min` (and `min_age` 16/18 for a legal minimum).
`null` for `preference`, `ambiguous` and `none` (preference bounds are not limits and never enter max-age statistics, as in
`evidence.MAXAGE_SQL`; the preferred bound is written in `note`). For an approximate age (30岁左右) both are null.

### 1.4 `has_exception`

True when the text relaxes the age bound (放宽, 适当放宽, 可放宽至40岁, 优秀者年龄不限, 年龄可面议). Relaxations of education,
experience or other requirements do not count.

### 1.5 `confidence`, `note`, `grad_cohort`

- `confidence: high` when the reading is clear; `low` when the window cuts the clause, the wording is garbled, the referent
  is unclear, or the label depends on a debatable edge rule.
- `note`: a short reason, in English, with the key words.
- `grad_cohort` (extra field): true when the text restricts applicants by graduation status (应届, 毕业N年内, 2023届).

## 2. Sampling design

All draws use `scripts/eval_rules.py` and never run a rule. Rows come from `data/raw/zhaopin_2016-2025.7.csv`
(one streaming `csv` pass, `field_size_limit(sys.maxsize)`), restricted to 招聘发布年份 2021–2024 (about 10.7 M rows).
`id` is the 0-based data-row index after the header. `text` = 招聘岗位 + "\n" + 职位描述, masked with
`realdata.mask_contacts` plus `eval_rules.mask_more` (phone numbers spelled in Chinese numerals, contact-person names),
cut to at most 600 characters centred on the age-relevant part (the stratum match for targeted ads; the window covering the
most 岁/年龄/年纪 anchors for random ads).

| Step | Command | Seed |
|---|---|---|
| Main draw (random + 9 targeted strata) | `python scripts/eval_rules.py --draw-gold --out data/raw/gold_age_candidates.jsonl` | `--gold-seed 20261028` |
| Supplementary stratum `qual_age_unlimited` | `python scripts/eval_rules.py --draw-extra --gold data/raw/gold_age_2021-2024.jsonl --out …extra.jsonl` | `--extra-seed 20261029` |
| Population sample for `--population` (cached, git-ignored) | written in the same pass as the main draw | `--seed 2024`, n = 50,000 |

- **Random stratum:** each row is kept with probability 4·10⁻⁵ (429 candidates), then 150 are drawn with `Random(seed+1)`.
- **Targeted strata:** a disjoint Bernoulli(0.03) prefilter (about 320 k rows), a seeded reservoir of 400 per stratum, then
  the counts below drawn without overlap (rarest stratum first), exact duplicate windows dropped.
- **Why a supplementary pass:** the main draw held no 年龄不限 ad (the `qual_unlimited_health` regex was dominated by 男女不限 /
  身体健康). A 15-ad `qual_age_unlimited` stratum was drawn in a second pass and labelled blind like the rest.
- **Reproducibility note:** `mask_more` was added after the main draw; it changed 4 stored texts (one Chinese-numeral phone,
  three names). A fresh draw with the current code can shift those 4 windows by a few characters.

| Stratum | Regex idea | Ads | Gold positive | Gold classes |
|---|---|---:|---:|---|
| `random` | uniform | 150 | 40 | 110 none, 29 range_or_min, 9 hard_cap, 1 preference, 1 ambiguous |
| `range_sep` | `NN(岁)? 至/到/～/~/——/--/－/— NN岁`, `NN岁 [-~至到]+ NN` | 35 | 35 | 35 range_or_min |
| `salary_digits` | `不超过/最高/不低于/低于/至少… NNN+` with 岁/年龄 within 100 chars | 30 | 27 | 23 range_or_min, 3 none, 1 each other |
| `graduate` | 应届, 毕业N年, NN届 | 30 | 7 | 23 none, 7 range_or_min (8 grad_cohort) |
| `cohort_young` | 年轻, 90后/95后/00后 … | 30 | 16 | 14 none, 8 ambiguous, 6 range_or_min, 1 hard_cap, 1 preference |
| `cn_numeral` | 三十五岁, 十八周岁 … | 25 | 25 | 15 ambiguous (mostly 年满十八周岁), 5 hard_cap, 5 range_or_min |
| `qual_unlimited_health` | 年龄不限, 男女不限, 身体健康 | 25 | 19 | 16 range_or_min, 6 none, 3 hard_cap |
| `qual_pref_relax` | 岁/年龄 … 优先/放宽 | 25 | 25 | 17 range_or_min, 3 preference, 2 cap_with_exception, 2 hard_cap, 1 ambiguous |
| `qual_bounds` | NN岁 以上/以下/左右/以内 | 25 | 25 | 15 hard_cap, 6 range_or_min, 3 cap_with_exception, 1 ambiguous |
| `exp_years` | N年以上经验 | 25 | 7 | 18 none, 4 hard_cap, 2 range_or_min, 1 preference |
| `qual_age_unlimited` | 年龄不限 / 不限年龄 … (second pass) | 15 | 1 | 14 none, 1 ambiguous |
| **Total** | | **415** | **227** | 21 low-confidence labels; 14 grad_cohort |

Years: 2021 102, 2022 157, 2023 84, 2024 72. The targeted strata over-sample hard cases on purpose. **Prevalence,
precision and recall are unbiased only on the random stratum**; the all-items numbers describe performance on hard cases.

## 3. Blind procedure and consistency

1. The guideline (section 1) was written first.
2. All 400 main-draw ads were read and labelled in draw order. Labels were saved to `data/raw/gold_age_2021-2024.jsonl`
   before any rule ran on them. The 15 supplementary ads were labelled the same way, again before any rule ran on them.
3. The file order is the labelling order (`label_order`).
4. Nothing in the gold file was changed after the rules ran, except the 4 masking fixes above; they do not touch age wording.
   One label decision was revisited in the re-test (below) and kept as first labelled.

**Test–retest (self-consistency, not inter-rater agreement):**

- **Sample:** a seeded random 10% of the main draw (`random.Random(4242).sample(range(400), 40)`).
- **Method:** the 40 items were labelled a second time without their stratum and without looking at the first labels.
- **Results:**

| Field | Agreement |
|---|---|
| `has_age_condition` | 40/40 (100%, 95% Wilson 91.2–100%) |
| `class` | 39/40 (97.5%, 87.1–99.6%); Cohen's κ = 0.96 |
| `max_age` / `min_age` | 39/40 each |
| `has_exception` / `grad_cohort` | 40/40 |

- **The one disagreement** (id 3375610, low confidence both times): "25周岁以上(即1997年1月1日以后出生) … 年龄:22-45岁".
  The first label was `ambiguous` (self-contradictory). The re-test label was `range_or_min` 22–45. The first label is kept.
- **Caveats:**
  - Both passes ran in one session, so the second pass may remember the first; this flatters consistency.
  - Most sampled items are easy (no age wording, or a clean range).

## 4. Limits

- **One AI annotator** (this agent). There was no second human annotator and no adjudication, and inter-rater agreement was not measured.
  The test–retest above is self-consistency only.
- 21 labels are marked `confidence: low`, mostly vague youth wording (年轻人, 年轻时尚) whose referent or force is debatable,
  general relaxations (优秀者可放宽条件) that may or may not cover age, and garbled or contradictory clauses.
  `class acc (high-conf gold)` in the report excludes them.
- **Edge decisions are conventions, not facts:**
  - 年满18 is `ambiguous`;
  - 应届 is not an age condition;
  - a split min/max is a range;
  - 年龄16-30周岁青年才俊优先 is a preference.
  Another annotator could reasonably differ on each.
- **The 600-character window hides the rest of long ads.** Gold and rules see the same window, so the comparison is fair,
  but a gold "none" means "nothing in the window".
- **The random stratum is small:** 150 ads, 40 positive. Rates near 100% still have lower Wilson bounds near 87–90%.
  Rare failure modes (Chinese numerals, odd separators) hardly appear in 150 random ads, so the population mode is the
  better guide to how much a fix changes the totals.

## 5. Evaluation harness

```
python scripts/eval_rules.py --gold data/raw/gold_age_2021-2024.jsonl --modules backend.ageparse[,backend.ageparse_cand_a,...] [--diff] [--json out.json]
python scripts/eval_rules.py --population --modules backend.ageparse,backend.ageparse_cand_a [--n 50000] [--seed 2024] [--workers 6] [--json out.json]
```

- **Rule side** (same semantics as `realdata`/`evidence`):
  - detected = `age_status != 'none'`; a secondary view uses `ad_class != 'none'`, because `age_status` calls 年龄不限 "uncertain";
  - class = `ad_class`;
  - max age = MIN(max_age) over high-confidence non-preference terms;
  - exception = any non-"unlimited" term with `exception_text`.
- **Reported per module, on the random stratum and on all items:**
  - detection P/R/F1;
  - class accuracy (all gold, and high-confidence gold only);
  - 6×6 confusion matrix, per-class precision and recall;
  - max-age exact match where the gold max exists;
  - exception agreement;
  - FP/FN/class-wrong per stratum;
  - 95% Wilson intervals on every rate.
- **`--diff`:** with one module it lists items where the rules differ from gold; with several, items where the modules disagree.
  Each entry shows the gold label and note and 160 characters of masked text.
- **`--population`:** runs each module on the same seeded 50,000 real 2021–2024 ads (full title + description, as the
  aggregate does), with at most 6 worker processes. It reports class counts, flagged, explicit and cap shares (with a Wilson
  interval on flagged), and the top class moves against the first module. The sample is cached in
  `data/raw/eval_pop_n50000_seed2024.jsonl.gz` (raw, unmasked, git-ignored), so later runs take seconds.

## 6. Baseline: `backend.ageparse` (`age-rules-2.0.0`)

### Random stratum (unbiased; n = 150, gold positive 40 = 26.7%, 95% CI 20.2–34.3%)

| Measure | Value |
|---|---|
| Detection precision | 97.5% (39/40; 87.1–99.6%) |
| Detection recall | 97.5% (39/40; 87.1–99.6%) |
| Detection F1 | 0.975 |
| Class accuracy | 98.0% (147/150; 94.3–99.3%) |
| Max-age exact match | 100% (38/38; 90.8–100%) |
| Exception agreement | 100% (40/40) |

The three random-stratum errors:
- "青壮年优先" is missed (gold `preference`, low confidence);
- "80、90后小伙伴" (team) is flagged `ambiguous`;
- a title cap "45周岁以内" plus body "年龄20-45周岁" becomes `hard_cap`, where the gold is `range_or_min`.

### All 415 items (hard cases over-sampled; not a prevalence estimate)

| Measure | Value |
|---|---|
| Detection precision (status ≠ none) | 86.8% (178/205; 81.5–90.8%) |
| Detection precision (class ≠ none) | 92.7% (178/192; 88.1–95.6%) |
| Detection recall | 78.4% (178/227; 72.6–83.3%) |
| Detection F1 | 0.824 |
| Class accuracy | 75.7% (314/415; 71.3–79.5%); 77.4% on high-confidence gold |
| Max-age exact match | 70.4% (133/189; 63.5–76.4%) |
| Exception agreement | 94.3% (214/227) |

Per-class recall (precision):
- hard_cap 82% (75%);
- cap_with_exception 17% (100%);
- range_or_min 65% (97%);
- preference 29% (100%);
- ambiguous 32% (19%);
- none 93% (78%).

| Stratum | n | Gold + | FP | FN | Class wrong |
|---|---:|---:|---:|---:|---:|
| random | 150 | 40 | 1 | 1 | 3 |
| cn_numeral | 25 | 25 | 0 | 23 | 23 |
| range_sep | 35 | 35 | 0 | 14 | 17 |
| salary_digits | 30 | 27 | 3 | 1 | 25 |
| cohort_young | 30 | 16 | 9 | 3 | 13 |
| qual_pref_relax | 25 | 25 | 0 | 4 | 11 |
| qual_unlimited_health | 25 | 19 | 0 | 3 | 4 |
| qual_bounds | 25 | 25 | 0 | 0 | 3 |
| exp_years | 25 | 7 | 0 | 0 | 1 |
| graduate | 30 | 7 | 0 | 0 | 0 |
| qual_age_unlimited | 15 | 1 | 14\* | 0 | 1 |

\* All 14 are 年龄不限 ads. They are counted as detected because `age_status` returns "uncertain", while `ad_class` correctly
returns `none`. Under the class ≠ none view they are not false positives. This is a definitional choice for the lead,
not a pattern bug.

### Population (seeded 50,000 ads, 2021–2024)

| Measure | Value |
|---|---|
| Flagged (status ≠ none) | 25.58% (95% CI 25.20–25.97%) |
| Explicit | 23.02% |
| Cap (hard_cap + cap_with_exception) | 6.27% |

Classes:

| Class | Ads | Share |
|---|---:|---:|
| hard_cap | 3,027 | 6.05% |
| cap_with_exception | 109 | 0.22% |
| range_or_min | 8,372 | 16.74% |
| preference | 68 | 0.14% |
| ambiguous | 1,092 | 2.18% |
| none | 37,332 | 74.66% |

These numbers agree with the full-data aggregate in `docs/REAL_DATA_AUDIT.md` (explicit 22.8%, cap 6.1%).

### Failure patterns seen while scoring

1. **Chinese numerals are never read** (23 of 25 `cn_numeral` ads missed):
   - 年龄三十五岁以下 · 四十七周岁以下 · 二十五岁以上四十二岁以下 · 年龄二十至三十五岁;
   - the most common case, the legal minimum 年满十八周岁.
2. **Ranges with 岁 on both ends or with repeated dashes are missed** (14 of 35 `range_sep` missed outright, 4 more mis-read: 3 as the wrong cap or range, 1 as `ambiguous`):
   - 30岁-40岁 · 年龄22周岁到28周岁 · 年龄24岁——35岁 · 18岁到45岁之间 · 18--48周岁 · 16一40岁 (一 as a dash);
   - 年龄16岁---45周岁以内 becomes `hard_cap` 45.
3. **Salary, height, weight and eyesight digits after bound words**:
   - examples: 不低于6000元 · 最高5000 · 不低于165(cm) · 不超过60kg · 低于600度;
   - they create a second cap, so the `conflict` rule turns a correct range into `ambiguous`: 18 of the 27 positive `salary_digits` ads;
   - wrong caps also appear: 年龄85年--95年优先 + 身高不低于165 → `hard_cap` 16; 20岁一30岁 + 不低于6000 → `hard_cap` 60.
4. **Team or company wording is flagged `ambiguous`** (9 false positives in `cohort_young`):
   - 年轻化团队 · 90、00后年轻化团队 · 95后居多 · 全集团已有90后店长656名.
   - The reverse also happens: wording about the wanted applicant (我们需要…年轻时尚的帅哥美女, 年轻小伙，中年大叔) is missed.
5. **Relaxations are missed:**
   - 30岁以下，技术成熟的放宽到35岁 and 年龄在48岁以下…能力出众者可放宽条件 become `hard_cap` instead of `cap_with_exception` (5 of 6 missed);
   - 17岁至35岁(…可放宽年龄到40岁) is missed entirely.
6. **Preferences are missed or hardened:**
   - 年龄25岁至35岁优先 is missed (range form);
   - 35~45岁最好 becomes `range_or_min`, because 最好 is not a preference word;
   - 青壮年优先 is missed.
7. **A cap and a lower bound in different sentences** (title 45周岁以内 + body 20-45周岁) become `hard_cap` instead of a range.
8. **Missed short forms:** 27岁内.
9. **Not counted as errors:** graduate-cohort wording (应届, 2025届) is correctly left alone. The gold records it in
   `grad_cohort` (14 ads) for a possible separate measure.

## 7. Files

- `data/raw/gold_age_2021-2024.jsonl` (git-ignored): 415 labelled ads.
- `data/raw/gold_age_candidates*.jsonl` (git-ignored): the unlabelled draws.
- `data/raw/eval_pop_n50000_seed2024.jsonl.gz` (git-ignored): the population cache.
- `scripts/eval_rules.py`: the draw, scoring, diff and population modes.
- `tests/fixtures/age_gold_snippets.jsonl` (to commit): 89 short cases (≤ 40 characters, masked, no company names),
  covering all 11 strata.
  - Each holds the snippet, a label for the snippet on its own, the stratum and the gold id.
  - For a few cases the snippet label differs from the full-ad label, for example a title cap shown without its body range.
  - The current rules match 43 of the 89 classes. They were chosen as hard cases, so this is not an accuracy figure.
  - No test asserts on them.
