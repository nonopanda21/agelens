#!/usr/bin/env python3
"""Analyse the exports from the test desk (#/study/admin).

  python scripts/analyze_rct.py PERSONS.csv [--items ITEMS.csv] [--model MODEL.csv] [--out result.md]

Prints two OLS models with robust standard errors, a randomization check and the claim the pre-set rule allows. In Stata:
  reg score assist, vce(robust)
  reg search_seconds assist, vce(robust)
"""
import argparse, csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import rct_stats  # noqa: E402


def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("persons")
    ap.add_argument("--items")
    ap.add_argument("--model")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    persons = rows(a.persons)
    modes = {p["mode"] for p in persons}
    if len(modes) != 1:
        sys.exit("The file mixes modes %s; analyse one at a time." % sorted(modes))
    label = "FORMAL" if modes == {"formal"} else "SIMULATED, not study data"
    text = rct_stats.render(rct_stats.analyse(persons, rows(a.items) if a.items else None, rows(a.model) if a.model else None), label)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
