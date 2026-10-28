#!/usr/bin/env python3
"""Year-by-year profile of the real Zhaopin export (2016–2025.7), to choose the year range for the map.

  python scripts/real_profile.py [--csv data/raw/zhaopin_2016-2025.7.csv] [--from-cube PATH | --save-cube PATH]
                                 [--out data/raw/profile_zhaopin.json] [--min-ads 500]
                                 [--audit-years 2021-2024 --audit-out data/raw/audit_sample.jsonl --seed 425]

One streaming pass (shared with real_aggregate.stream_cube) over every row with a year. Per publish year it reports:
ads (rows with a province), rows without a province, age-wording share, explicit share, cap share (hard cap or cap with an
exception), cap-with-exception share (ads with an exception / relaxable term), median stated max age, and the number of
provinces with >= --min-ads ads. It prints a Markdown table (pasted into docs/REAL_DATA_YEARS.md).

--audit-out draws the accuracy-audit sample in the same pass: each in-range row is a candidate with probability
--audit-p (seeded), candidates are parsed, and --audit-n flagged + --audit-n unflagged ads are drawn with the same seed.
The sample holds ad text (contacts masked) and must stay in a git-ignored place (data/raw/).
"""
import argparse, json, random, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from backend.ageparse import parse_age  # noqa: E402
from backend.realdata import ad_text, mask_contacts, measures_from_terms, occupation_of, city_to_province  # noqa: E402
from real_aggregate import (DEFAULT_CSV, I_CITY, I_DESC, I_TITLE, load_cube, median_counter, parse_years,  # noqa: E402
                            save_cube, stream_cube)


def profile(cube, min_ads=500):
    years = sorted({y for y, _, _ in cube})
    out = []
    for y in years:
        b = [0] * 7
        cwe = 0
        ages, prov_ads, no_prov = Counter(), Counter(), 0
        for (yy, p, o), v in cube.items():
            if yy != y:
                continue
            if p is None:
                no_prov += v[0]
                continue
            for i in range(7):
                b[i] += v[i]
            ages.update(v[7])
            cwe += v[8]
            prov_ads[p] += v[0]
        n = b[0]
        sh = (lambda k: round(k / n, 4) if n else None)
        out.append({"year": y, "ads": n, "rows_no_province": no_prov, "age_wording": b[3], "explicit": b[1], "cap": b[2],
                    "with_exception": b[4], "preference": b[5], "n_max_age": b[6],
                    "age_wording_share": sh(b[3]), "explicit_share": sh(b[1]), "cap_share": sh(b[2]),
                    "with_exception_share": sh(b[4]), "cap_with_exception": cwe, "cap_with_exception_share": sh(cwe),
                    "cap_with_exception_among_caps": round(cwe / b[2], 4) if b[2] else None,
                    "median_max_age": median_counter(ages),
                    "share_max_age_le_35": round(sum(c for a, c in ages.items() if a <= 35) / b[6], 4) if b[6] else None,
                    "provinces_with_min_ads": sum(1 for v in prov_ads.values() if v >= min_ads),
                    "provinces_any": len(prov_ads)})
    return out


def markdown(rows, min_ads):
    pct = (lambda x: "–" if x is None else f"{100 * x:.1f}%")
    h = ("| Year | Ads (with province) | Age wording | Explicit | Cap (hard or with exception) | Cap with exception | "
         f"Median stated max age | Max age ≤ 35 | Provinces ≥ {min_ads} ads |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    return h + "".join(
        f"| {r['year']} | {r['ads']:,} | {pct(r['age_wording_share'])} | {pct(r['explicit_share'])} | {pct(r['cap_share'])} | "
        f"{pct(r['cap_with_exception_share'])} | {r['median_max_age'] if r['median_max_age'] is not None else '–'} | "
        f"{pct(r['share_max_age_le_35'])} | {r['provinces_with_min_ads']} / {r['provinces_any']} |\n" for r in rows)


class AuditSampler:
    def __init__(self, years, p, seed):
        self.years, self.p, self.rng, self.cands = set(years), p, random.Random(seed), []

    def __call__(self, row, year):
        if year in self.years and self.rng.random() < self.p:
            self.cands.append((year, row[I_CITY].strip(), row[I_TITLE].strip(), row[I_DESC]))

    def draw(self, n, seed):
        flagged, unflagged = [], []
        for year, city, title, desc in self.cands:
            terms = parse_age(ad_text(title, desc))
            m, mx, cls = measures_from_terms(terms)
            rec = {"year": year, "province": city_to_province(city), "occupation": occupation_of(title),
                   "title": mask_contacts(title), "description": mask_contacts(desc), "ad_class": cls, "max_age": mx,
                   "terms": [{k: t.get(k) for k in ("kind", "min_age", "max_age", "confidence", "exception_text", "flag",
                                                     "age_class")} | {"snippet": mask_contacts(t.get("snippet") or "")}
                             for t in terms]}
            (flagged if terms else unflagged).append(rec)
        rng = random.Random(seed)
        pick_f = rng.sample(flagged, min(n, len(flagged)))
        pick_u = rng.sample(unflagged, min(n, len(unflagged)))
        return pick_f, pick_u, len(flagged), len(unflagged)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--from-cube")
    ap.add_argument("--save-cube")
    ap.add_argument("--out", default=str(ROOT / "data" / "raw" / "profile_zhaopin.json"))
    ap.add_argument("--min-ads", type=int, default=500)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--audit-years", default="2021-2024")
    ap.add_argument("--audit-out")
    ap.add_argument("--audit-n", type=int, default=60)
    ap.add_argument("--audit-p", type=float, default=0.0004)
    ap.add_argument("--seed", type=int, default=425)
    a = ap.parse_args(argv)
    sampler = AuditSampler(parse_years(a.audit_years), a.audit_p, a.seed) if a.audit_out else None
    if a.from_cube:
        cube, stats = load_cube(a.from_cube)
    else:
        cube, stats = stream_cube(a.csv, None, a.workers, on_row=sampler)
        if a.save_cube:
            save_cube(cube, stats, a.save_cube)
        print(f"read {stats['rows_in_file']:,} rows in {stats['seconds']}s", file=sys.stderr)
    rows = profile(cube, a.min_ads)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"rows_in_file": stats["rows_in_file"], "rows_bad_year": stats.get("rows_bad_year"),
                                       "min_ads": a.min_ads, "years": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(markdown(rows, a.min_ads))
    if sampler:
        f, u, nf, nu = sampler.draw(a.audit_n, a.seed)
        with open(a.audit_out, "w", encoding="utf-8") as fh:
            for i, r in enumerate(f + u, 1):
                fh.write(json.dumps(dict(r, id=i, stratum="flagged" if i <= len(f) else "unflagged"), ensure_ascii=False) + "\n")
        print(f"audit sample: {len(f)} flagged of {nf} candidates, {len(u)} unflagged of {nu} candidates -> {a.audit_out}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
