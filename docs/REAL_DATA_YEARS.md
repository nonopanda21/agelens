# Real data: which years to show on the map

**Recommendation:** use **2021–2024** (publish year, `招聘发布年份`) for the map:
`data/real/matrix_zhaopin_2021-2024.json`, about 10.05 million ads.

The source is the Zhaopin (智联招聘) export the user supplied, `data/raw/zhaopin_2016-2025.7.csv`. It is not in git.
All numbers below come from one streaming pass over the full file (13,322,606 rows) with `scripts/real_profile.py`.
They use the fixed rules in `backend/ageparse.py` (`age-rules-2.0.0`) on the job title plus the description.

## How each measure is defined

Each measure follows `evidence.matrix()`:

- **Ads:** rows whose city maps to a province.
- **Age wording:** the rules found any age wording (`age_status` ≠ none).
- **Explicit:** a usable numeric age condition.
- **Cap:** the ad's class is `hard_cap` or `cap_with_exception`.
  - A range such as 18–45岁 is `range_or_min`, not a cap, so caps are much rarer than explicit conditions.
- **Cap with exception:** the ad's class is `cap_with_exception`.
- **Median stated max age:** the median, over ads that state a maximum (including the top of a range; preferences are excluded), of each ad's lowest high-confidence maximum.
- **Provinces ≥ 500 ads:** out of the province units present that year. The 34 units include Hong Kong, Macao and Taiwan.

## Year by year

| Year | Ads (with province) | Age wording | Explicit | Cap (hard or with exception) | Cap with exception | Median stated max age | Max age ≤ 35 | Provinces ≥ 500 ads |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2016 | 947,989 | 12.9% | 11.7% | 2.4% | 0.04% | 35 | 71.3% | 29 / 31 |
| 2017 | 1,542,311 | 14.2% | 13.0% | 3.0% | 0.05% | 35 | 65.9% | 30 / 31 |
| 2018 | 672,801 | 13.3% | 12.2% | 3.2% | 0.07% | 35 | 62.7% | 29 / 31 |
| 2019 | 25 | 12.0% | 8.0% | 4.0% | 4.0% (1 ad) | 40 | 50.0% | 0 / 15 |
| 2020 | 2,118 | 16.2% | 14.3% | 5.3% | 0.09% | 35 | 55.1% | 0 / 32 |
| 2021 | 2,165,139 | 22.7% | 20.2% | 5.9% | 0.16% | 35 | 52.4% | 31 / 34 |
| 2022 | 3,871,002 | 25.4% | 22.9% | 6.2% | 0.18% | 40 | 45.9% | 31 / 34 |
| 2023 | 1,976,851 | 26.0% | 23.2% | 6.5% | 0.21% | 40 | 42.6% | 31 / 34 |
| 2024 | 2,041,671 | 27.8% | 25.2% | 5.8% | 0.21% | 40 | 32.8% | 31 / 33 |
| 2025 (Jan–Jul) | 95,484 | 5.9% | 5.4% | 2.9% | 0.11% | 35 | 60.4% | 26 / 32 |

**Other facts, also measured:**

- **Exceptions:** ads with any exception or "relaxable" term (the map's `with_exception`) are 0.5% of ads in 2016–2018 and 0.9% in 2021–2024. Among capped ads, 2.6–3.6% carry an exception in 2021–2024.
- **Rows dropped:**
  - 2 rows have no publish year.
  - Rows without a mappable city (foreign countries, 全国, 其他, empty) number 1,302 / 1,731 / 12 in 2016–2018 and 3,744 / 201 / 144 / 74 in 2021–2024.
- **Small provinces in 2021–2024:**
  - 2021–2023: Taiwan, Hong Kong and Macao are the three units under 500 ads. In 2022–2023 they have 1 to 12 ads each.
  - 2024: Taiwan is absent; Hong Kong (448) and Macao (78) are under 500.
  - Tibet is the smallest mainland unit: 2,019 to 5,562 ads per year.
- **Description length (a sampled check, every 20th row):**
  - In 2016–2018, 36–42% of descriptions are exactly 240 characters long, so the export cut them off at 240.
  - In 2021–2024, the median description is 276–376 characters, and only 0.2% are exactly 240.
  - In 2025, 99.9% of descriptions are under 240 characters (median 203).
  - The share of descriptions containing 岁 or 年龄 follows the same pattern: 13.9–15.3% in 2016–2018, 23.7–29.3% in 2021–2024, and 6.0% in 2025.

## Why 2021–2024

1. **Current market.** These are the four most recent complete years. The map describes how ads are worded now, not a decade ago.
2. **Text is comparable.**
   - 2016–2018 descriptions are cut at 240 characters for about 40% of ads. Requirements, including age, usually come at the end, so age wording is undercounted (12.9–14.2% against 22.7–27.8%).
   - 2025 descriptions look abridged in the same way (5.9% age wording).
   - Mixing those years in would mix a data artefact with real change.
3. **Continuity.** 2019 (25 rows) and 2020 (2,118 rows) are effectively missing. A range across the gap (e.g. 2016–2024) would join two different collections.
   - 2021–2024 is continuous, and the four years agree closely: age wording 22.7–27.8%, cap 5.8–6.5%, median stated max age 35–40.
4. **Sample size.** About 10.05 million ads, at least 1.98 million in every year. Every mainland province has at least 14,608 ads over the range (Tibet). The smallest occupation (数据分析) has 26,920.
5. **Provincial coverage.** All 31 mainland provinces have ≥ 500 ads in every year from 2021 to 2024. Hong Kong (750 ads over the range), Macao (447) and Taiwan (44) are thin and should be shown as "few ads" on the map.

**Not recommended:**

- **2016–2018 as a "before" period:** the 240-character cut makes the comparison unfair.
- **2025 alone:** half a year of abridged text.
- **2019 and 2020:** too few rows.

If a reviewer wants the newest single year, 2024 is usable on its own: 2.04 M ads, 31 mainland provinces ≥ 500. It still has the same occupation mix caveats.

## Caveats for anyone reading the map

- The numbers count wording that the rules flag, not verified discrimination. See `docs/REAL_DATA_AUDIT.md` for a 120-ad accuracy check: numeric caps and ranges were right in 49 of 50 flagged cases, and some ads with age wording are missed.
- **Occupation** comes from keyword rules on the job title. 27.9% of 2021–2024 ads stay 其他 because their title names no clear function (项目经理, 总经理, 司机, 保安 …).
- **The median stated max age rose from 35 (2021) to 40 (2022–2024).** The share of stated maxima ≤ 35 fell from 52% to 33%. This may reflect a changing mix of ads (more factory and service ads with 18–45 / 18–50 ranges) rather than employers relaxing limits. It was not analysed further.
- **The most common stated maximum** (from `meta.max_age_counts`: each ad counted once at its evidence.py max age, ranges included) is 35 in 2021–2023. In 2024 it is 45:

  | Year | Ads stating a maximum | 35 | 45 | 40 | 30 | 28 |
  |---|---:|---:|---:|---:|---:|---:|
  | 2021 | 421,584 | 31.3% | 15.4% | 16.9% | 10.8% | 3.6% |
  | 2022 | 863,436 | 27.5% | 19.1% | 15.8% | 9.3% | 3.1% |
  | 2023 | 446,475 | 26.4% | 19.8% | 16.9% | 8.2% | 2.8% |
  | 2024 | 504,188 | 20.1% | 22.9% | 15.8% | 6.0% | 1.7% |
  | 2021–2024 | 2,235,683 | 26.4% | 19.4% | 16.2% | 8.6% | 2.8% |

- **Source coverage:** Zhaopin is one platform, so its ads are not a census of Chinese hiring. Year sizes vary (3.87 M in 2022 against 1.98 M in 2023) for reasons not documented in the file.

## Reproduce

```
.venv/bin/python scripts/real_profile.py --save-cube data/raw/zhaopin_cube.json \
    --audit-out data/raw/audit_sample_2021-2024.jsonl          # ~4 min on 16 workers; prints the table above
.venv/bin/python scripts/real_aggregate.py --years 2021-2024   # ~4 min; or add --from-cube data/raw/zhaopin_cube.json
```
