SYNTHETIC DATA - NOT REAL JOB ADS.
sim_ads.csv was produced by scripts/make_sim_data.py (sim-1.0.0), seed 20261023.
Companies are fictional (marked 示例...（虚构）), URLs use example.invalid, every description carries a synthetic marker.
Counts describe this generator's settings only; they say nothing about the real labour market.
Rows: 1018 (960 unique + exact duplicates). CSV sha256: 9fbd546005c1c131409b51c5155d6185a20760904bbfbea75242658adebdf750
Regenerate: .venv/bin/python scripts/make_sim_data.py --seed 20261023
Import:     .venv/bin/python scripts/import_csv.py --source sim   (marks rows is_demo=1, label 'Demo · Synthetic data')
Files: sim_ads.csv, sim_ads.meta.json, cases.json (seeker profiles, review cases, adversarial ad texts).
English display columns (sim-en-1.0.0): title_en, company_en, city_en, description_en, age_sentence_en. They are looked up from the Chinese template the
generator chose and draw no random numbers, so the Chinese ads and their ids are unchanged. The age rules read the Chinese.
