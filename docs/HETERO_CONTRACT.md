# Heterogeneity file contract (`hetero_zhaopin_2021-2024.json`)

Served by `GET /api/stats/hetero?source=real` (404 `{"error": ...}` when the file is absent; the front end must handle that).
File: `data/real/hetero_zhaopin_2021-2024.json`. Counts only, no ad text. All names are English (occupations and provinces
through `gloss.occupation_en` / `gloss.province_en`). Describes how ads are worded, not hiring outcomes.

```
{
 "meta": {
   "years": [2021, 2022, 2023, 2024],
   "rows_used": N,                       // ads read in those years (every row counts, also rows without a province)
   "rows_with_province": N,              // the ads in by_experience_province
   "age_rule_version": "age-rules-2.1.0",
   "gender_rule_version": "gender-rules-1.0.0",
   "experience_bands": ["No experience required", "Under 1 year", "1–3 years", "3–5 years", "5+ years", "Not stated"],
   "experience_mapping": {"No experience required": ["不限", "无经验", "无"], "Under 1 year": ["1年以下"], ...},   // source values (Chinese, as in the export) -> band
   "gender_classes": ["male_only","female_only","male_preferred","female_preferred","no_limit","conflict","none"],
   "generated": "YYYY-MM-DD",
   "source": "Zhaopin recruitment export 2016–2025.7, supplied by the team",
   "caveat": "Counts of how ads are worded, not hiring outcomes"
 },
 "by_experience": [            // one row per band, in band order
   {"band": "...", "ads": n, "explicit": n, "cap": n, "age_wording": n, "with_exception": n, "preference": n,
    "n_max_age": n, "max_age_counts": {"30": n, "35": n, ...}}      // each ad counted once at its evidence max age
 ],
 "by_experience_occupation": [{"band","occupation","ads","explicit","cap","age_wording"}],   // all (band, occupation) pairs with ads>0
 "by_experience_province":   [{"band","province","ads","explicit","cap"}],
 "gender": {
   "by_class":      [{"gender_class","ads","explicit","cap"}],          // 7 classes
   "by_occupation": [{"occupation","ads","male_only","female_only","male_preferred","female_preferred","no_limit","conflict","none"}],
   "by_experience": [{"band","ads","male_only",... "none"}],
   "age_by_gender": [{"gender_class","ads","explicit","cap","age_wording"}]
 },
 "cohort": {"graduate_cohort_ads": n}   // ads with 应届 / graduate-year wording (ageparse.parse_cohort); NOT an age term
}
```

Definitions: `explicit`, `cap`, `age_wording`, `with_exception`, `preference`, `n_max_age` are exactly those of
`backend/realdata.measures_from_terms` (the same as the main matrix). Shares = count / ads. `ads` in gender rows = all ads in
that class; the seven class counts of a row sum to its `ads`.
"explicit gender" classes: male_only, female_only, male_preferred, female_preferred; `no_limit` = stated "男女不限"-type wording;
`conflict` = both genders required for different posts or contradictory wording; `none` = no gender wording found.
Rule version, gold-set precision and recall: `docs/GENDER_RULES.md`.

## Notes for the front end (from the real run, 2026-10-29)
* The shipped file is `data/real/hetero_zhaopin_2021-2024.json` (about 38 KB, all four tables included): 10,058,826 ads, 10,054,663 with a province.
* `by_experience_occupation` has the occupation "Other" (27.9% of ads, keyword rules leave it unclassified); label it plainly or leave it out of rankings. Rank occupations only where `ads >= 5000` (the table has small cells).
* Explicit gender restrictions are very rare: male_only 1,047, female_only 1,556, male_preferred 3, female_preferred 5, conflict 756 of 10.06 M ads. `no_limit` ("男女不限" wording) is 7.0%. Show counts next to shares and do not rank occupations by the four directional classes (cells hold a handful of ads).
* Shares: `explicit / ads` etc. `age_wording` includes `explicit`. `max_age_counts` keys are strings.
* English only: occupation and province names come from `gloss.occupation_en` / `gloss.province_en`; the keys `experience_mapping` values are the original Chinese source values (do not render them).
* Required wording near any chart: "Counts of how ads are worded, not hiring outcomes" (`meta.caveat`).
