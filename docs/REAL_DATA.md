# Onboarding real job-ad data

The app is source-agnostic: the importer reads a `DataSource` (`backend/datasource.py`) and writes to SQLite; stats, map, search, briefs and reviewer pages read only the database.

## Switching source
| Source | Command | Stored as |
|---|---|---|
| Simulated | `scripts/import_csv.py --source sim [--seed N]` | `is_demo=1`, label "Demo · Synthetic data" |
| Round-1 demo CSV | `scripts/import_csv.py data/demo/demo_ads.csv --demo` | `is_demo=1` |
| Real CSV | `scripts/import_csv.py FILE.csv [--mapping map.json]` | `is_demo=0` |

Scope rule: real and demo rows are never mixed. With any real row present the API defaults to real only; `include_demo=true` shows demo only. To go "real only":
`scripts/reset_sim.py --db <path> --yes` (removes only `is_demo=1`). Add a new kind of source (database, API, Parquet) by subclassing `DataSource`
(`metadata()`, `fingerprint()`, `describe()`, `iter_ads()` yielding canonical fields); no other code changes.

## Steps for a CSV
1. **Inspect**: `import_csv.py FILE.csv --inspect` prints detected encoding (UTF-8/UTF-8-BOM/GB18030), delimiter, header and the suggested column mapping.
2. **Map fields**: canonical fields are title, company, city, province, date, description, category, url, source, salary. Aliases cover common English/Chinese headers. Override with
   `--mapping map.json` = `{"CSV column": "canonical"}`. `description` (original text) is required for age extraction and is never altered.
3. **Clean** (automatic, logged in `import_batches.log_json`): blank rows skipped; dates parsed from 10 formats (unparseable kept as NULL and counted); city/province resolved from the built-in
   city table to the 34 canonical names (unknown stays NULL and is counted, never guessed); occupation from the category column or a cleaned title.
4. **Dedupe**: key = normalised title + company + city + sha1(description); duplicates fold into the first ad's `duplicate_count`, every raw row stays in `raw_ads` (provenance).
5. **Extract**: `ageparse.parse_age` stores terms with exact snippet and offsets, `age_class`, `flag` (`truncated`, `conflict`, `unlimited`), rule version. Re-run after a rule change by importing into a fresh DB
   (rule version is stored per term and per batch).
6. **Index**: the importer creates the indexes it needs (province/date/class/batch/city/kind). Idempotent: the content hash is stored, a second run of the same file is a no-op; an interrupted run is rolled back and redone.
7. **Check**: `/api/batches` (counts, missing values, unknown locations), `/api/status`, spot-check ads in `#/explore`. Before showing numbers, replace the "Demo" wording only because the rows are `is_demo=0`; do not hand-edit labels.

## ~15 GB path
Streaming is already the design: the CSV is read row by row, written in chunks (default 5000 rows per transaction), raw rows are kept for provenance. Not yet measured at that size. Expected work, in order:
- run the importer on the server with `--chunk 20000`, disk >= 3x file size (raw_json + ads + terms), WAL mode;
- replace the `q` LIKE scan with SQLite FTS5 (external-content table on `ads.title/description`) and add covering indexes on filters in use;
- pre-aggregate province/occupation/class counts into summary tables updated per chunk if `by_province` becomes slow (today it is one GROUP BY plus one int per ad for the median);
- all list endpoints are paginated (`page_size` <= 100); no endpoint returns the table;
- split the file by month first if one transaction stream is too slow, import files in parallel is NOT safe (single writer).

**Never load into the browser, process memory or model context:** the full table, all descriptions, raw rows, or full CV text. The model sees only a handful of cited snippets chosen by the rules layer; stats are computed by SQL.

## Privacy and legal cautions
- Check licence/terms of the source before ingestion; scraped data may not be redistributable. Keep the raw file outside the repo and `data/` folder under version control.
- Ads can contain personal data (recruiter names, phone, email, WeChat ids). Decide before onboarding whether to mask them; the importer does not.
- Do not join ad data with any individual's CV or request data. `requests` store snapshots the seeker consented to share; exports must stay anonymous.
- Age wording counts describe ads, not employers' decisions; never label them discrimination, rejection or illegality.
- Real-data statistics must not be presented next to simulated ones without the badge; do not reuse simulated counts as findings.

## Free-text search index (added 2026-10-24)
The `q` filter now uses an SQLite FTS5 index with the **trigram** tokenizer (substring search that works for Chinese and English), created lazily on the first search and kept in sync by triggers on `ads`; queries shorter than 3 characters fall back to `LIKE`. Tests (`tests/test_fts.py`) check that results equal the old LIKE search and that inserts, text updates and deletes stay in sync.
Benchmark (`scripts/bench_search.py 200000`, temporary copy scaled to 200,000 ads, this server, best of 5): index build 5.3 s, database 342 MB; `35岁以下` LIKE 61.7 ms vs FTS 11.6 ms; `可适当放宽` 118.6 vs 11.9 ms; `工作经验` (67,310 hits) 115.8 vs 31.5 ms; identical row counts in every case. For a ~15 GB import, build the index once after loading (`INSERT INTO ads_fts(ads_fts) VALUES('rebuild')`) rather than paying trigger cost row by row, and expect the index to add a large fraction of the text size on disk; this has not been tested at 15 GB.
