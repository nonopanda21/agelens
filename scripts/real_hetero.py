#!/usr/bin/env python3
"""Heterogeneity aggregation of the real Zhaopin export: stated age wording by required experience, occupation and province,
and explicitly written gender requirements (backend/genderparse.py). Counts only; no ad text is kept. Contract: docs/HETERO_CONTRACT.md.

  python scripts/real_hetero.py --years 2021-2024 [--out data/real/hetero_zhaopin_2021-2024.json] [--workers 6] [--sample N]
                                [--csv PATH] [--save-cube PATH] [--from-cube PATH]

Reuses the helpers of scripts/real_aggregate.py's world (backend/realdata.py): ad_text, city_to_province, occupation_of,
measures_from_terms. At most 6 workers (the CPU is shared). --save-cube writes the (year, band, province, occupation,
gender class) cube; --from-cube rebuilds the JSON from it without reading the 14 GB CSV.
"""
import argparse, csv, json, os, sys, time
from collections import Counter
from datetime import date
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.ageparse import RULE_VERSION as AGE_VERSION, parse_age, parse_cohort  # noqa: E402
from backend.genderparse import CLASSES as GENDER_CLASSES, RULE_VERSION as GENDER_VERSION, gender_class, parse_gender  # noqa: E402
from backend.gloss import occupation_en, province_en  # noqa: E402
from backend.realdata import ad_text, city_to_province, measures_from_terms, occupation_of  # noqa: E402

DEFAULT_CSV = ROOT / "data" / "raw" / "zhaopin_2016-2025.7.csv"
I_TITLE, I_CITY, I_DESC, I_EXP, I_YEAR = 1, 2, 6, 8, 17
MAX_WORKERS = 6
SOURCE = "Zhaopin recruitment export 2016–2025.7, supplied by the team"
CAVEAT = "Counts of how ads are worded, not hiring outcomes"

# 要求经验 (required experience) -> ordered bands. 不限 ("not limited") and 无经验 ("no experience") both mean the ad asks for
# no experience, so they share a band; "5-10年" and "10年以上" are merged because 10年以上 is under 1.5% of ads.
BANDS = ["No experience required", "Under 1 year", "1–3 years", "3–5 years", "5+ years", "Not stated"]
EXPERIENCE_MAPPING = {"No experience required": ["不限", "无经验", "无"], "Under 1 year": ["1年以下"], "1–3 years": ["1-3年"],
                      "3–5 years": ["3-5年"], "5+ years": ["5-10年", "10年以上"], "Not stated": ["(empty or any other value)"]}
_BAND_OF = {v: b for b, vs in EXPERIENCE_MAPPING.items() for v in vs}
AGE_KEYS = ("explicit", "cap", "age_wording", "with_exception", "preference")


def band_of(exp):
    return _BAND_OF.get((exp or "").strip(), "Not stated")


# bucket: [ads, explicit, cap, age_wording, with_exception, preference, n_max_age, cohort, Counter(max_age)]
def _new():
    return [0] * 8 + [Counter()]


def process_rows(rows):
    cube = {}
    for year, city, title, desc, exp in rows:
        text = ad_text(title, desc)
        m, mx, _cls = measures_from_terms(parse_age(text))
        gc = gender_class(parse_gender(text))
        key = (year, band_of(exp), city_to_province(city), occupation_of(title), gc)
        b = cube.get(key)
        if b is None:
            b = cube[key] = _new()
        b[0] += 1
        for i, k in enumerate(AGE_KEYS, 1):
            b[i] += m[k]
        if mx is not None:
            b[6] += 1
            b[8][mx] += 1
        if parse_cohort(text):
            b[7] += 1
    return cube


def merge(into, part):
    for k, b in part.items():
        a = into.get(k)
        if a is None:
            into[k] = b
            continue
        for i in range(8):
            a[i] += b[i]
        a[8].update(b[8])


def stream_cube(csv_path, years, workers=MAX_WORKERS, sample=None, batch=2000):
    csv.field_size_limit(sys.maxsize)
    workers = max(1, min(MAX_WORKERS, workers))
    keep = set(years)
    cube, stats, t0 = {}, {"rows_in_file": 0, "rows_in_years": 0}, time.time()
    ctx = get_context("fork")
    with ctx.Pool(workers) as pool, open(csv_path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r)
        pending, buf = [], []

        def drain(limit):
            while len(pending) > limit:
                merge(cube, pending.pop(0).get())

        for row in r:
            stats["rows_in_file"] += 1
            ys = row[I_YEAR].strip() if len(row) > I_YEAR else ""
            if not (len(ys) == 4 and ys.isdigit() and int(ys) in keep):
                continue
            if sample is not None and stats["rows_in_years"] >= sample:
                stats["rows_in_file"] = None
                break
            stats["rows_in_years"] += 1
            buf.append((int(ys), row[I_CITY].strip(), row[I_TITLE].strip(), row[I_DESC], row[I_EXP]))
            if len(buf) >= batch:
                pending.append(pool.apply_async(process_rows, (buf,)))
                buf = []
                drain(4 * workers)
            if stats["rows_in_file"] % 1_000_000 == 0:
                print(f"  {stats['rows_in_file']:,} rows read, {stats['rows_in_years']:,} kept, {time.time() - t0:.0f}s",
                      file=sys.stderr, flush=True)
        if buf:
            pending.append(pool.apply_async(process_rows, (buf,)))
        drain(0)
    stats["seconds"] = round(time.time() - t0, 1)
    return cube, stats


def save_cube(cube, stats, path):
    out = {"age_rule_version": AGE_VERSION, "gender_rule_version": GENDER_VERSION, "stats": stats,
           "cells": [list(k) + b[:8] + [{str(a): n for a, n in b[8].items()}] for k, b in cube.items()]}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


def load_cube(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    cube = {}
    for row in d["cells"]:
        cube[tuple(row[:5])] = list(row[5:13]) + [Counter({int(a): n for a, n in row[13].items()})]
    return cube, d


# ------------------------------------------------------------------ building the JSON
def _sum(cube, keyfn, years):
    acc = {}
    for k, b in cube.items():
        if k[0] not in years:
            continue
        kk = keyfn(k)
        if kk is None:
            continue
        a = acc.get(kk)
        if a is None:
            a = acc[kk] = _new()
        for i in range(8):
            a[i] += b[i]
        a[8].update(b[8])
    return acc


def build(cube, years, stats, generated=None):
    ys = set(years)
    bo = {b: i for i, b in enumerate(BANDS)}
    gco = {c: i for i, c in enumerate(GENDER_CLASSES)}
    occ_order = {}
    by_band = _sum(cube, lambda k: k[1], ys)
    by_band_occ = _sum(cube, lambda k: (k[1], k[3]), ys)
    by_band_prov = _sum(cube, lambda k: (k[1], k[2]) if k[2] else None, ys)
    by_class = _sum(cube, lambda k: k[4], ys)
    g_occ = _sum(cube, lambda k: (k[3], k[4]), ys)
    g_band = _sum(cube, lambda k: (k[1], k[4]), ys)
    total = sum(b[0] for b in by_band.values())
    with_prov = sum(b[0] for b in by_band_prov.values())
    cohort = sum(b[7] for b in by_band.values())

    def age_row(b, keys):
        return {"ads": b[0], **{k: b[1 + AGE_KEYS.index(k)] for k in keys}}

    def gdist(table, name_key, name_of):
        rows = {}
        for (n, gc), b in table.items():
            r = rows.setdefault(n, {name_key: name_of(n), "ads": 0, **{c: 0 for c in GENDER_CLASSES}})
            r["ads"] += b[0]
            r[gc] += b[0]
        return rows

    exp_rows = []
    for band in BANDS:
        b = by_band.get(band, _new())
        exp_rows.append({"band": band, "ads": b[0], **{k: b[1 + i] for i, k in enumerate(AGE_KEYS)}, "n_max_age": b[6],
                         "max_age_counts": {str(a): n for a, n in sorted(b[8].items())}})
    occ_rows = [{"band": bd, "occupation": occupation_en(o), **age_row(b, ("explicit", "cap", "age_wording"))}
                for (bd, o), b in sorted(by_band_occ.items(), key=lambda kv: (bo[kv[0][0]], -kv[1][0]))]
    prov_rows = [{"band": bd, "province": province_en(p), **age_row(b, ("explicit", "cap"))}
                 for (bd, p), b in sorted(by_band_prov.items(), key=lambda kv: (bo[kv[0][0]], -kv[1][0]))]
    g_by_class = [{"gender_class": c, **age_row(by_class[c], ("explicit", "cap"))} for c in GENDER_CLASSES if c in by_class]
    g_age = [{"gender_class": c, **age_row(by_class[c], ("explicit", "cap", "age_wording"))} for c in GENDER_CLASSES if c in by_class]
    g_occ_rows = sorted(gdist(g_occ, "occupation", occupation_en).values(), key=lambda r: -r["ads"])
    gb = gdist(g_band, "band", lambda x: x)
    g_band_rows = [gb[b] for b in BANDS if b in gb]
    return {"meta": {"years": sorted(years), "rows_used": total, "rows_with_province": with_prov,
                     "age_rule_version": AGE_VERSION, "gender_rule_version": GENDER_VERSION,
                     "experience_bands": BANDS, "experience_mapping": EXPERIENCE_MAPPING,
                     "gender_classes": list(GENDER_CLASSES),
                     "generated": generated or date.today().isoformat(), "source": SOURCE, "caveat": CAVEAT},
            "by_experience": exp_rows, "by_experience_occupation": occ_rows, "by_experience_province": prov_rows,
            "gender": {"by_class": g_by_class, "by_occupation": g_occ_rows, "by_experience": g_band_rows, "age_by_gender": g_age},
            "cohort": {"graduate_cohort_ads": cohort}}


def parse_years(s):
    a, _, b = str(s).partition("-")
    return list(range(int(a), int(b or a) + 1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", default="2021-2024")
    ap.add_argument("--out")
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--sample", type=int)
    ap.add_argument("--workers", type=int, default=MAX_WORKERS)
    ap.add_argument("--save-cube")
    ap.add_argument("--from-cube")
    a = ap.parse_args(argv)
    years = parse_years(a.years)
    out = Path(a.out or ROOT / "data" / "real" / f"hetero_zhaopin_{years[0]}-{years[-1]}.json")
    if a.from_cube:
        cube, d = load_cube(a.from_cube)
        if (d["age_rule_version"], d["gender_rule_version"]) != (AGE_VERSION, GENDER_VERSION):
            sys.exit("cube rule versions differ from the current rules; re-run without --from-cube")
        stats = d["stats"]
    else:
        cube, stats = stream_cube(a.csv, years, a.workers, a.sample)
        if a.save_cube:
            save_cube(cube, stats, a.save_cube)
    res = build(cube, years, stats)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} bytes), rows_used {res['meta']['rows_used']:,}", file=sys.stderr)
    return res


if __name__ == "__main__":
    main()
