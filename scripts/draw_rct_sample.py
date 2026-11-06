#!/usr/bin/env python3
"""Draw the ad sample for the RCT evaluation: 4 provinces x 16 occupation groups x 6 ads = 384 ads.

  python scripts/draw_rct_sample.py [--csv data/raw/zhaopin_2016-2025.7.csv] [--out data/raw/rct_sample]
                                    [--provinces 广东,江苏,河南,四川] [--years 2021-2024] [--seed 425] [--limit N]

Each cell gets 3 ads to keep (2 with a stated maximum age, 1 with no age wording) and 3 ads with a stated maximum age for
the team to rewrite by hand into indirect wording. Draws are seeded and per row, so the same file gives the same sample.
One pass over the CSV; the raw file is only read. Output holds ad text (contacts masked), so it must stay in a git-ignored
place (data/raw/). The rules only choose candidates: a person still has to check every ad and write the answer key.
"""
import argparse, csv, hashlib, heapq, json, re, sys, time
from collections import Counter, defaultdict
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from backend.ageparse import parse_age  # noqa: E402
from backend.realdata import OCCUPATIONS, ad_text, city_to_province, mask_contacts, measures_from_terms, occupation_of  # noqa: E402
from real_aggregate import DEFAULT_CSV, parse_years  # noqa: E402

I_COMPANY, I_TITLE, I_CITY, I_DESC, I_EDU, I_EXP, I_DATE, I_YEAR = 0, 1, 2, 6, 7, 8, 15, 17
MIN_DESC, MAX_DESC = 80, 1500  # long enough to hold requirements, short enough to read inside a 120 s task
AGE_HINT = re.compile(r"岁|年龄|年纪|出生|年轻|应届|青年")  # "no age wording" also has to pass this stricter check
KEEP_POOL = 40  # candidates held per province, occupation and kind, before removing duplicates
N_STATED, N_NONE = 5, 1
SPARE_STATED, SPARE_NONE = 4, 2
FIELDS = ("source_ad_id", "province", "occupation_group", "group", "source_kind", "ad_date", "city", "title", "education",
          "experience", "stated_max_age", "has_exception", "rules_age_quote", "original_ad", "edited_ad", "edit_note", "row_sha1")


def priority(seed, rec):
    return hashlib.sha256(f"{seed}:{rec}".encode()).hexdigest()


def read_batch(args):
    """Worker: (seed, [(record number, row)]) -> candidates. The age rules only run on rows that pass the cheap filters."""
    seed, batch = args
    out = []
    for rec, row in batch:
        title, desc = row[I_TITLE].strip(), row[I_DESC].strip()
        occ = occupation_of(title)
        if occ not in OCCUPATIONS or not MIN_DESC <= len(desc) <= MAX_DESC:
            continue
        terms = parse_age(ad_text(title, desc))
        m, max_age, _cls = measures_from_terms(terms)
        if m["cap"] and max_age is not None and 18 <= max_age <= 70:
            kind = "stated_max_age"
        elif not m["age_wording"] and not AGE_HINT.search(title + desc):
            kind = "no_age_wording"
        else:
            continue
        out.append((priority(seed, rec), rec, occ, kind, row, max_age, m["with_exception"],
                    next((t.get("snippet") or "" for t in terms if t.get("max_age") == max_age), "")))
    return out


def batches(path, provinces, years, seed, limit, stats, size=2000):
    csv.field_size_limit(sys.maxsize)
    cur = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r)
        for rec, row in enumerate(r, 1):
            if limit and rec > limit:
                break
            stats["rows"] = rec
            if len(row) <= I_YEAR or row[I_YEAR].strip()[:4] not in years:
                continue
            prov = city_to_province(row[I_CITY])
            if prov not in provinces:
                continue
            stats[prov] += 1
            cur.append((rec, row))
            if len(cur) >= size:
                yield (seed, cur)
                cur = []
    if cur:
        yield (seed, cur)


def to_row(c, prov, occ, group):
    _prio, rec, _occ, kind, row, max_age, exc, quote = c
    return {"source_ad_id": rec, "province": prov, "occupation_group": occ, "group": group, "source_kind": kind,
            "ad_date": row[I_DATE].strip(), "city": row[I_CITY].strip(), "title": mask_contacts(row[I_TITLE].strip()),
            "education": row[I_EDU].strip(), "experience": row[I_EXP].strip(), "stated_max_age": max_age if max_age is not None else "",
            "has_exception": exc if kind == "stated_max_age" else "", "rules_age_quote": mask_contacts(quote or ""),
            "original_ad": mask_contacts(row[I_DESC].strip()), "edited_ad": "", "edit_note": "",
            "row_sha1": hashlib.sha1("\x1f".join(row).encode()).hexdigest()}


def distinct(cands, seen_text):
    """Lowest priority first; one ad per company in a cell, and no ad text twice in the whole sample."""
    companies, out = set(), []
    for c in sorted(cands):
        row = c[4]
        text = hashlib.sha1(re.sub(r"\s+", "", row[I_DESC]).encode()).hexdigest()
        if text in seen_text or row[I_COMPANY].strip() in companies:
            continue
        seen_text.add(text); companies.add(row[I_COMPANY].strip())
        out.append(c)
    return out


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel opens the Chinese correctly
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--out", default=str(ROOT / "data" / "raw" / "rct_sample"))
    ap.add_argument("--provinces", default="广东,江苏,河南,四川")
    ap.add_argument("--years", default="2021-2024")
    ap.add_argument("--seed", type=int, default=425)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists() and any(out.iterdir()):
        sys.exit(f"{out} already holds files; choose another --out")
    out.mkdir(parents=True, exist_ok=True)
    provinces = a.provinces.split(",")
    years = {str(y) for y in parse_years(a.years)}
    stats, pool, seen = Counter(), defaultdict(list), Counter()
    t0 = time.time()
    with get_context("fork").Pool(a.workers) as p:
        for i, found in enumerate(p.imap_unordered(read_batch, batches(a.csv, set(provinces), years, a.seed, a.limit, stats), chunksize=1)):
            for c in found:
                key = (city_to_province(c[4][I_CITY]), c[2], c[3])
                seen[key] += 1
                # heap of the lowest priorities: negate by keeping the largest on top through a complement
                item = (tuple(-b for b in bytes.fromhex(c[0])), c)
                if len(pool[key]) < KEEP_POOL:
                    heapq.heappush(pool[key], item)
                elif item[0] > pool[key][0][0]:
                    heapq.heapreplace(pool[key], item)
            if i % 500 == 0:
                print(f"{stats['rows']:,} rows, {time.time() - t0:.0f}s", flush=True)
    sample, spares, short, seen_text = [], [], [], set()
    for prov in provinces:
        for occ in OCCUPATIONS:
            stated = distinct([x[1] for x in pool[(prov, occ, "stated_max_age")]], seen_text)
            none = distinct([x[1] for x in pool[(prov, occ, "no_age_wording")]], seen_text)
            if len(stated) < N_STATED or len(none) < N_NONE:
                short.append([prov, occ, len(stated), len(none)])
            sample += [to_row(c, prov, occ, "to_rewrite") for c in stated[:3]]
            sample += [to_row(c, prov, occ, "keep_explicit") for c in stated[3:N_STATED]]
            sample += [to_row(c, prov, occ, "keep_neutral") for c in none[:N_NONE]]
            spares += [to_row(c, prov, occ, "spare") for c in stated[N_STATED:N_STATED + SPARE_STATED] + none[N_NONE:N_NONE + SPARE_NONE]]
    write_csv(out / "sample_384.csv", sample)
    write_csv(out / "spares.csv", spares)
    meta = {"source_file": Path(a.csv).name, "seed": a.seed, "years": a.years, "provinces": provinces, "occupation_groups": list(OCCUPATIONS),
            "rows_read": stats["rows"], "rows_in_scope": {p: stats[p] for p in provinces}, "sample_rows": len(sample), "spare_rows": len(spares),
            "cells_short": short, "candidates_per_cell": {"|".join(k): v for k, v in sorted(seen.items())},
            "filters": {"description_chars": [MIN_DESC, MAX_DESC], "occupation": "not 其他", "stated_max_age": "rules: cap, high-confidence max age 18-70",
                        "no_age_wording": "rules: no age wording, and no match for " + AGE_HINT.pattern}}
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"done: {len(sample)} ads, {len(spares)} spares, short cells {short}, {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
