#!/usr/bin/env python3
"""Aggregate the real Zhaopin (智联招聘) export into ONE province x occupation matrix JSON (aggregates only).

  python scripts/real_aggregate.py --years 2021-2024 [--out data/real/matrix_zhaopin_2021-2024.json] [--sample N]
                                   [--csv data/raw/zhaopin_2016-2025.7.csv] [--workers 16]
                                   [--save-cube PATH] [--from-cube PATH]

Streams the CSV (never loads it), keeps rows whose 招聘发布年份 is in range, maps 工作城市 -> province and
招聘岗位 -> occupation (backend/realdata.py), runs backend/ageparse.parse_age on 招聘岗位 + "\\n" + 职位描述 in a
process pool, and writes the exact shape of GET /api/stats/matrix (cells, provinces, occupations, total,
filters_applied, using_demo=false, label) plus `meta`. Per-ad fields follow evidence.matrix() (realdata.measures_from_terms).
Rows without a province are left out of cells/provinces and counted in meta. No ad text, company or contact leaves
the workers: the output holds counts and medians only.

--sample N   stop after the first N in-range rows (quick runs; not a random sample).
--save-cube  also write the (year, province, occupation) cube for ALL years seen (git-ignored place, e.g. data/raw/).
--from-cube  build the matrix from a saved cube instead of re-reading the CSV.
"""
import argparse, csv, json, os, sys, time
from collections import Counter
from datetime import datetime, timezone
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.ageparse import RULE_VERSION, parse_age  # noqa: E402
from backend.evidence import PROVINCES, _MATRIX_KEYS  # noqa: E402
from backend.realdata import OTHER, ad_text, city_to_province, measures_from_terms, occupation_of  # noqa: E402

DEFAULT_CSV = ROOT / "data" / "raw" / "zhaopin_2016-2025.7.csv"
SOURCE = "智联招聘 (Zhaopin) recruitment export 2016–2025.7, supplied by the user"
I_TITLE, I_CITY, I_DESC, I_YEAR = 1, 2, 6, 17
COUNT_KEYS = _MATRIX_KEYS  # ads, explicit, cap, age_wording, with_exception, preference, n_max_age
METHOD = ("Each ad's job title and description were read by the fixed rules in backend/ageparse.py; the city was mapped to "
          "a province and the job title to an occupation by keyword rules (backend/realdata.py); counts and medians were "
          "then summed per province and occupation, with no ad text kept.")


def parse_years(s):
    s = str(s).strip()
    if "-" in s:
        a, b = s.split("-", 1)
        a, b = int(a), int(b)
    else:
        a = b = int(s)
    if a > b:
        a, b = b, a
    return list(range(a, b + 1))


def years_label(years):
    return str(years[0]) if years[0] == years[-1] else f"{years[0]}–{years[-1]}"


# ------------------------------------------------------------------ cube: (year, province|None, occupation) -> counts
def _new_bucket():
    """[ads, explicit, cap, age_wording, with_exception, preference, n_max_age, Counter(max_age), n_cap_with_exception]"""
    return [0] * len(COUNT_KEYS) + [Counter(), 0]


def _add(cube, key, m, max_age, cls=None):
    b = cube.get(key)
    if b is None:
        b = cube[key] = _new_bucket()
    b[0] += 1
    b[8] += cls == "cap_with_exception"
    for i, k in enumerate(("explicit", "cap", "age_wording", "with_exception", "preference"), 1):
        b[i] += m[k]
    if max_age is not None:
        b[6] += 1
        b[7][max_age] += 1


def process_rows(rows):
    """Worker: rows of (year, city, title, description) -> (partial cube, Counter of unmapped (year, city))."""
    cube, unmapped = {}, Counter()
    for year, city, title, desc in rows:
        prov = city_to_province(city)
        if prov is None:
            unmapped[(year, city)] += 1
        m, mx, cls = measures_from_terms(parse_age(ad_text(title, desc)))
        _add(cube, (year, prov, occupation_of(title)), m, mx, cls)
    return cube, unmapped


def merge(into, part):
    for k, b in part.items():
        a = into.get(k)
        if a is None:
            into[k] = b
            continue
        for i in range(7):
            a[i] += b[i]
        a[7].update(b[7])
        a[8] += b[8]


def stream_cube(csv_path, years=None, workers=16, sample=None, batch=2000, on_row=None, progress=True):
    """Stream the CSV once. years=None keeps every row with a 4-digit year. on_row(row, year) is called in the main
    process for every kept row (used by real_profile.py to draw the audit sample). Returns (cube, stats)."""
    csv.field_size_limit(sys.maxsize)
    keep = set(years) if years else None
    cube, unmapped = {}, Counter()
    stats = {"rows_in_file": 0, "rows_in_years": 0, "rows_bad_year": 0}
    t0 = time.time()
    ctx = get_context("fork")
    with ctx.Pool(max(1, min(16, workers))) as pool, open(csv_path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r)  # header
        pending, buf = [], []

        def drain(limit):
            while len(pending) > limit:
                c, u = pending.pop(0).get()
                merge(cube, c); unmapped.update(u)

        for row in r:
            stats["rows_in_file"] += 1
            ys = row[I_YEAR].strip() if len(row) > I_YEAR else ""
            if not (len(ys) == 4 and ys.isdigit()):
                stats["rows_bad_year"] += 1
                continue
            y = int(ys)
            if keep is not None and y not in keep:
                continue
            if sample is not None and stats["rows_in_years"] >= sample:
                stats["rows_in_file"] = None  # not counted: the run stopped early
                break
            stats["rows_in_years"] += 1
            if on_row:
                on_row(row, y)
            buf.append((y, row[I_CITY].strip(), row[I_TITLE].strip(), row[I_DESC]))
            if len(buf) >= batch:
                pending.append(pool.apply_async(process_rows, (buf,)))
                buf = []
                drain(4 * workers)
            if progress and stats["rows_in_file"] % 1_000_000 == 0:
                print(f"  {stats['rows_in_file']:,} rows read, {stats['rows_in_years']:,} kept, {time.time() - t0:.0f}s",
                      file=sys.stderr, flush=True)
        if buf:
            pending.append(pool.apply_async(process_rows, (buf,)))
        drain(0)
    stats["unmapped_cities"] = unmapped  # Counter of (year, city)
    stats["seconds"] = round(time.time() - t0, 1)
    return cube, stats


def save_cube(cube, stats, path):
    out = {"rule_version": RULE_VERSION, "rows_in_file": stats["rows_in_file"], "rows_bad_year": stats.get("rows_bad_year", 0),
           "unmapped_cities": [[y, c, n] for (y, c), n in stats["unmapped_cities"].items()],
           "cells": [[y, p, o] + b[:7] + [{str(a): n for a, n in b[7].items()}, b[8]] for (y, p, o), b in cube.items()]}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


def load_cube(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    cube = {}
    for row in d["cells"]:
        cube[(row[0], row[1], row[2])] = list(row[3:10]) + [Counter({int(a): n for a, n in row[10].items()}), row[11]]
    return cube, {"rows_in_file": d["rows_in_file"], "rows_bad_year": d.get("rows_bad_year", 0),
                  "unmapped_cities": Counter({(y, c): n for y, c, n in d["unmapped_cities"]}), "rule_version": d.get("rule_version")}


# ------------------------------------------------------------------ matrix building (evidence.matrix semantics)
def median_counter(c):
    """statistics.median over the multiset in Counter c (odd n -> the middle value, even n -> mean of the two)."""
    n = sum(c.values())
    if not n:
        return None
    items = sorted(c.items())

    def nth(k):  # k-th smallest, 0-based
        acc = 0
        for v, cnt in items:
            acc += cnt
            if k < acc:
                return v
    if n % 2:
        return nth(n // 2)
    return (nth(n // 2 - 1) + nth(n // 2)) / 2


def _fin(name_key, name, b):
    d = {name_key: name} if name_key else {}
    d.update({k: b[i] for i, k in enumerate(COUNT_KEYS)})
    d["median_max_age"] = median_counter(b[7])
    return d


def _sum_into(acc, key, b):
    a = acc.get(key)
    if a is None:
        a = acc[key] = _new_bucket()
    for i in range(7):
        a[i] += b[i]
    a[7].update(b[7])
    a[8] += b[8]


def build_matrix(cube, years, stats, source=SOURCE, generated_at=None):
    years = sorted(years)
    ys = set(years)
    cells_b, prov_b, occ_b, year_b, year_all = {}, {}, {}, {}, Counter()
    total = _new_bucket()
    no_prov = other = 0
    for (y, p, o), b in cube.items():
        if y not in ys:
            continue
        year_all[y] += b[0]
        if p is None:
            no_prov += b[0]
            continue
        if o == OTHER:
            other += b[0]
        _sum_into(cells_b, (p, o), b)
        _sum_into(prov_b, p, b)
        _sum_into(occ_b, o, b)
        _sum_into(year_b, y, b)
        for i in range(7):
            total[i] += b[i]
        total[7].update(b[7])
    order = {x["name"]: i for i, x in enumerate(PROVINCES)}
    cells = [dict({"province": p, "occupation": o}, **_fin(None, None, b)) for (p, o), b in cells_b.items()]
    cells.sort(key=lambda r: (order.get(r["province"], 99), r["province"] or "", r["occupation"] or ""))
    provinces = sorted((_fin("province", p, b) for p, b in prov_b.items()),
                       key=lambda r: (-r["ads"], order.get(r["province"], 99), r["province"] or ""))
    occupations = sorted((_fin("occupation", o, b) for o, b in occ_b.items()), key=lambda r: (-r["ads"], r["occupation"] or ""))
    by_year = []
    for y in years:
        b = year_b.get(y, _new_bucket())
        by_year.append({"year": y, "ads": b[0], "age_wording": b[3], "explicit": b[1], "cap": b[2], "with_exception": b[4],
                        "median_max_age": median_counter(b[7])})
    um = stats.get("unmapped_cities") or Counter()
    unmapped_list = sorted({_safe_city(c) for (y, c), n in um.items() if y in ys and n})
    label = f"Real data · Zhaopin job ads {years_label(years)}"
    meta = {"source": source, "years": years,
            "rows_in_file": stats.get("rows_in_file"),
            "rows_in_years": sum(year_all.values()),
            "rows_used": total[0], "rows_no_province": no_prov, "rows_other_occupation": other,
            "share_other_occupation": round(other / total[0], 4) if total[0] else None,
            "distinct_cities_unmapped": unmapped_list,
            "rule_version": RULE_VERSION,
            "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "method": METHOD, "text_parsed": "job title + newline + description",
            "by_year": by_year,
            # each ad counted once at its evidence.py max age (MIN over high-confidence, non-preference terms with a
            # max_age; includes the top of a range such as 18-45岁), over rows_used ads only
            "ads_with_max_age": total[6],
            "max_age_counts": {str(k): v for k, v in sorted(total[7].items())},
            "max_age_counts_by_year": {str(y): {str(k): v for k, v in sorted(year_b.get(y, _new_bucket())[7].items())}
                                       for y in years}}
    if stats.get("sample") is not None:
        meta["sample_first_rows"] = stats["sample"]
    return {"cells": cells, "provinces": provinces, "occupations": occupations, "total": _fin(None, None, total),
            "filters_applied": {"scope": "real", "scope_label": label, "years": [years[0], years[-1]], "source": "zhaopin"},
            "using_demo": False, "label": label, "meta": meta}


def _safe_city(c):
    """Unmapped 工作城市 values go into public JSON: keep short place-like values, blank out anything else."""
    c = (c or "").strip()
    if not c:
        return "(empty)"
    if len(c) > 12 or any(ch in c for ch in ":：/.@") or any(ch.isdigit() for ch in c):
        return "(malformed value)"
    return c


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", default="2021-2024")
    ap.add_argument("--out")
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--sample", type=int)
    ap.add_argument("--workers", type=int, default=min(16, os.cpu_count() or 1))
    ap.add_argument("--save-cube")
    ap.add_argument("--from-cube")
    a = ap.parse_args(argv)
    years = parse_years(a.years)
    out = Path(a.out or ROOT / "data" / "real" / f"matrix_zhaopin_{years[0]}-{years[-1]}.json")
    if a.from_cube:
        cube, stats = load_cube(a.from_cube)
        if stats.get("rule_version") != RULE_VERSION:
            sys.exit(f"cube rule_version {stats.get('rule_version')} != {RULE_VERSION}; re-run without --from-cube")
    else:
        cube, stats = stream_cube(a.csv, None if a.save_cube else years, a.workers, a.sample)
        if a.save_cube:
            save_cube(cube, stats, a.save_cube)
        stats["sample"] = a.sample
        print(f"read {stats['rows_in_file'] or 'a sample of'} rows in {stats['seconds']}s", file=sys.stderr)
    m = build_matrix(cube, years, stats)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    mt = m["meta"]
    print(f"wrote {out} ({out.stat().st_size:,} bytes): rows_in_years {mt['rows_in_years']:,}, used {mt['rows_used']:,}, "
          f"no province {mt['rows_no_province']:,}, 其他 {mt['rows_other_occupation']:,}, cells {len(m['cells'])}")
    return m


if __name__ == "__main__":
    main()
