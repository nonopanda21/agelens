SYNTHETIC DATA - NOT REAL JOB ADS.
sim_ads.csv was produced by scripts/make_sim_data.py (sim-1.0.0), seed 20261023.
Companies are fictional (marked 示例...（虚构）), URLs use example.invalid, every description carries a synthetic marker.
Counts describe this generator's settings only; they say nothing about the real labour market.
Rows: 1018 (960 unique + exact duplicates). CSV sha256: b5a229eadff5a8288b1ac5b2ab20194c243636b59faeeafc9b5febce4a528323
Regenerate: .venv/bin/python scripts/make_sim_data.py --seed 20261023
Import:     .venv/bin/python scripts/import_csv.py --source sim   (marks rows is_demo=1, label 'Demo · Synthetic data')
Files: sim_ads.csv, sim_ads.meta.json, cases.json (seeker profiles, review cases, adversarial ad texts).
