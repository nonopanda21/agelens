# Simulated data (round 2)

All numbers shown by AgeLens in this build come from a **synthetic** data set. It carries the badge **"Demo · Synthetic data"**.
It is a test bench for the interface, the rules parser and the clarification flow. **Its counts say nothing about the real labour market**: every
proportion below is a setting in `scripts/make_sim_data.py`, not an observation.

## What is simulated
- 960 unique fictional ads (+58 exact re-posted duplicates = 1018 raw rows), seed `20261023`, generator `sim-1.0.0`, `data_version = sim-1.0.0-seed20261023`.
- Fictional companies (`<invented word>示例<industry>有限公司（虚构）`), `example.invalid` URLs, a synthetic marker in every description
  (truncated ads end mid-clause, so their marker is at the start). 16 occupation groups (procurement, operations, engineering, sales, admin, finance, HR, design,
  customer service, logistics, marketing, legal, production, education, care, data), mixed education and experience requirements, three date formats.
- 32 of 34 provincial units have ads. Deliberately sparse: 青海 2, 西藏 1, 宁夏 1, 香港 5, 海南 6, 新疆 6, 甘肃 8. **No ads:** 澳门, 台湾 (the "no data" path).
  Each province has its own random bias for how often age wording appears, so the map metric varies (share of age wording 56%-88% among provinces with >= 20 ads).
- Fixtures for other agents: `data/sim/cases.json` (12 fictional seekers incl. the 38-year-old procurement example, 6 fictional review cases, 10 adversarial ad texts with
  prompt-injection lines). Labelled `synthetic`; not users, not reviews, not trial results.

## Scenario table (unique ads; counts from the generated file, verified by import)
| Scenario (generator label) | Ads | What the parser must say (`age_class`) |
|---|---|---|
| hard cap, mostly 35, also 25/28/30/32/38/40/45 | 193 | `hard_cap` |
| cap with qualification exception (条件优秀者可适当放宽 ...) | 112 | `cap_with_exception` |
| preference, not a limit (35岁以下优先, 年轻有活力优先) | 72 | `preference` |
| range (25-35岁) | 79 | `range_or_min` |
| minimum age (30岁以上) | 31 | `range_or_min` |
| 不限年龄 / 年龄无要求 | 50 | `none` (status stays `uncertain`: wording exists) |
| no age wording | 197 | `none` |
| experience-year trap (工作经验3-5年) | 81 | `none` |
| non-age numbers (团队规模35人以下) | 29 | `none` |
| truncated (`年龄35岁以`) | 27 | `ambiguous`, term flag `truncated`, no cap invented |
| contradictory (two caps, or 不限年龄 + 35岁以下) | 44 | `ambiguous`, `conflict=true`, both terms kept, low confidence |
| other vague (90后, 35岁左右, 年龄面谈) | 45 | `ambiguous` |

Overview of the import: explicit 415, uncertain 238, none 307 (age wording = 653 = 68.0% of 960); class counts hard_cap 193, cap_with_exception 112, preference 72,
range_or_min 110, ambiguous 116, none 357. These match the table (tests `test_parser_matches_generator_intent`). Because the generator uses phrasings the rules know,
agreement is expected; it shows the pipeline is wired correctly, **not** parser accuracy on real ads.

## Semantics
- `age_class` (ad and term): `hard_cap | cap_with_exception | preference | range_or_min | ambiguous | none`. Priority at ad level:
  cap_with_exception > hard_cap > range_or_min > preference > ambiguous > none; a conflicting ad is `ambiguous`.
- `age_status` (round 1, unchanged): `explicit` only for a high-confidence cap/range/min; preference, truncated, conflicting and vague wording are `uncertain`.
- **age wording** = explicit + uncertain (`age_wording`, `age_wording_share` = age_wording / ads in that province). It is a share of ads containing wording, never a
  discrimination or rejection rate.
- `preference` terms keep the number for display but never enter max-age statistics or the `max_age_*` filters.
- Truncated: the fragment is never read as a cap. Conflict: demoted to low confidence, so it cannot feed the max-age distribution either.

## Regenerate
```
.venv/bin/python scripts/make_sim_data.py                 # writes data/sim/{sim_ads.csv,sim_ads.meta.json,cases.json,README.txt}
.venv/bin/python scripts/make_sim_data.py --seed 7 --n 500 --out /tmp/other/sim_ads.csv
```
Same seed + same generator version = identical bytes (no clock, no environment input; uses Python's `random.Random`, whose sequence for these calls is stable across 3.x).
Changing a template or weight requires bumping `GENERATOR_VERSION`.

## Load into a database
```
AGELENS_DB=/path/x.db .venv/bin/python scripts/import_csv.py --source sim      # generate + import, is_demo=1
AGELENS_DB=/path/x.db .venv/bin/python scripts/import_csv.py data/sim/sim_ads.csv   # same batch (same hash); sidecar .meta.json marks it simulated
.venv/bin/python scripts/reset_sim.py --db /path/x.db            # dry run: what would be deleted (only is_demo=1)
.venv/bin/python scripts/reset_sim.py --db /path/x.db --yes      # delete simulated rows, keep real batches
```
Do not import `data/demo/demo_ads.csv` (round-1 demo) together with the sim file: both are `is_demo=1` and would be summed.

## Limits
Fictional text, templated phrasing, uniform-ish dates, no salary realism, no company structure, no repeat-posting dynamics. Province weights are rough
population-style guesses. Nothing here is evidence about hiring, discrimination or employment outcomes.
