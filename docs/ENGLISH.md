# English-only display

The website shows no Chinese. The age rules (`backend/ageparse.py`) still read the original Chinese text, and every original field is
kept. Only what is **displayed** is English. The API adds `*_en` fields next to the original fields, and the front end shows only
the `*_en` fields.

## Where the English comes from

- **`backend/gloss.py`.** Fixed rules, deterministic, no model.
  - `term_en(term)` renders one age term, e.g. "Age 35 or under", "Ages 25–40", "Age 35 or under preferred", "Age 30 or over",
    "No age limit", "Age 35 or under; may be relaxed for outstanding candidates", "Age wording cut off in the text; no limit could be read",
    "Generation wording (people born in the 1990s), not a stated age limit", or "Age wording that the rules could not read as a number".
  - `exception_en(text)` uses keyword rules for exception clauses. 条件优秀者可放宽 gives "may be relaxed for outstanding candidates";
    特别优秀者可放宽至40岁 gives "may be relaxed to 40 for exceptional candidates". When it is unsure, it returns "an exception clause".
  - `class_en(age_class)` gives "Hard cap", "Cap with an exception", "Preference, not a rule", "Range or minimum", "Unclear wording" or
    "No age wording".
  - `quote_en(quote, terms)` renders a quoted snippet as the gloss of the terms the rules read from it.
  - `en_text(text, terms)` renders a sentence: each Chinese “quote” is replaced by its gloss, and any other Chinese is removed.
  - A gloss describes what the rules read. It is not a full translation, and it never says whether anyone qualifies.
- **Simulated ads.** `scripts/make_sim_data.py` (English columns `sim-en-1.0.0`) builds the English version from the same template
  it chose for the Chinese one. The lookup draws **no** random numbers, so for the same seed the Chinese ads, their order and their ids
  (`ad_` + sha1 of title/company/city/description) are exactly those of sim-1.0.0. `tests/test_english.py` pins a sha256 of the Chinese
  columns to check this.

## Field contract

| Endpoint | Added fields |
|---|---|
| `/api/ads` items | `title_en`, `company_en`, `city_en`, `province_en`, `occupation_en`, `source_en`, `age_class_en`, `age_sentence_en`, `age_sentences_en`, `snippet_highlight_en`; per `age_terms[*]`: `gloss_en`, `class_en`, `exception_en` |
| `/api/ads/<id>` | the same, plus `description_en` (full English ad; each of `age_sentences_en` is a literal substring of it, for highlighting) |
| `/api/brief`, `/api/paste/check` | `answer[*][*].text_en` (every statement), `.quote_en` (when `quote`); `questions[*].text_en`; `findings[*].statement_en`; `unclear_en`; `evidence_index[*]`: `title_en`, `company_en`, `province_en`, `source_en` |
| `/api/paste/check` `pasted` | `truncated_en`, `conflict_en`, `instruction_like_en` (a Chinese instruction-like line is described, not shown) |
| `/api/age/check` `terms[*]` | `gloss_en`, `class_en`, `exception_en` (top-level keys unchanged) |
| `/api/requests/*` `evidence[*]` | at read time: `gloss_en`/`class_en`/`exception_en` per term, plus `title_en` etc. from the ad if it is still in the database. The stored snapshot is not changed. |
| `/api/stats/provinces`, `/api/stats/occupations` | `province_en` / `occupation_en` |
| `/api/real/status` | `source` is English only: "Zhaopin recruitment export 2016–2025.7, supplied by the team" (mapped in `api_data.real_source_en`; `data/real/*.json` is not edited) |
| `/api/study/...` task payload | `ad_text_en`, `job_title_en` (from `data/study/tasks.json`) |

Use `text_en`, not `text`, for statements. A `text` that quotes contradictory ad wording still contains the Chinese quote.

**Exports.**
- The Markdown export (`brief.to_markdown`), the Word report (`backend/report.py`) and the study aid (`study_arms.agelens_aid`) use only the `*_en` fields.
- `brief._en` is a final guard in the exports that removes any Chinese left over.
- The report appendix lists English titles, fictional English company names, English places and the term glosses.

## Data files

- `data/sim/sim_ads.csv` has five new columns before `sim_scenario`: `title_en`, `company_en`, `city_en`, `description_en` and `age_sentence_en`.
  - In `age_sentence_en`, several age sentences are joined with a newline.
  - The CSV sha256 changed; the Chinese columns did not.
  - The importer stores the five columns in `ads` (added by `evidence.ensure_columns`).
- `data/sim/cases.json` gains `question_en`, `profile_en`, `suggested_filters_en`, `evidence[*].company_en/quote_en` and `ad_text_en`.
- `data/study/tasks.json` gains:
  - `ad_text_en`, `job_title_en` and `facts.quote_en` per task;
  - English-only calibration answers K1 and K5 and an English-only rubric example.
  - Its sha256 changed (the study is not approved).

## Re-importing a database

Stored ads get their English columns only when they are imported. For an existing database, delete only the simulated rows and import them again:

    .venv/bin/python scripts/reset_sim.py --db data/agelens.db --yes
    AGELENS_DB=data/agelens.db .venv/bin/python scripts/import_csv.py --source sim

The ids stay the same, so request snapshots still point to the same ads. Make a backup first.

## Still Chinese in the API, on purpose

These fields are kept, and the UI must not show them:
- `title`, `company`, `city`, `province`, `occupation`, `description`, `snippet`, `exception_text`, `quote`, `pasted.truncated/conflict/instruction_like`;
- `raw_row` (the original CSV row);
- the study `ad_text` and `gloss`;
- the real matrix (`/api/stats/matrix?source=real`: Chinese province/occupation keys and `meta`).

Text the user types (question, profile, pasted ad) comes back as typed in the original fields. In `text_en` it is shown with Chinese
runs replaced by "[Chinese text]", and known occupation words are translated.
