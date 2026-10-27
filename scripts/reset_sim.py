#!/usr/bin/env python3
"""Dev tool: delete ONLY simulated/demo data (is_demo=1) from a database. Real batches are never touched.

    python scripts/reset_sim.py --db PATH [--yes]

--db is mandatory (no default, so it can never hit data/agelens.db by accident). Without --yes it only reports what it would delete.
Deletes age_terms, ads, raw_ads and import_batches rows whose batch has is_demo=1. Requests/messages are not touched.
Typical refresh:  reset_sim.py --db X --yes && AGELENS_DB=X import_csv.py --source sim
"""
import argparse, sqlite3
from pathlib import Path


def reset_sim(db_path, apply=False):
    p = Path(db_path)
    if not p.is_file():
        raise SystemExit(f"Refusing: {p} does not exist (will not create a database).")
    conn = sqlite3.connect(p, timeout=10)
    try:
        have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"import_batches", "raw_ads", "ads", "age_terms"} <= have:
            raise SystemExit("Refusing: not an AgeLens database (tables missing).")
        n = {"batches": conn.execute("SELECT COUNT(*) FROM import_batches WHERE is_demo=1").fetchone()[0],
             "ads": conn.execute("SELECT COUNT(*) FROM ads WHERE is_demo=1").fetchone()[0],
             "raw_ads": conn.execute("SELECT COUNT(*) FROM raw_ads WHERE batch_id IN (SELECT id FROM import_batches WHERE is_demo=1)").fetchone()[0],
             "age_terms": conn.execute("SELECT COUNT(*) FROM age_terms WHERE ad_id IN (SELECT id FROM ads WHERE is_demo=1)").fetchone()[0]}
        kept = {"real_batches": conn.execute("SELECT COUNT(*) FROM import_batches WHERE is_demo=0").fetchone()[0],
                "real_ads": conn.execute("SELECT COUNT(*) FROM ads WHERE is_demo=0").fetchone()[0]}
        # an ads row of a demo batch must be flagged demo too; a mismatch means the data is mixed -> do not guess
        bad = conn.execute("SELECT COUNT(*) FROM ads a JOIN import_batches b ON b.id=a.batch_id WHERE a.is_demo<>b.is_demo").fetchone()[0]
        if bad:
            raise SystemExit(f"Refusing: {bad} ads disagree with their batch's is_demo flag.")
        if apply:
            with conn:
                conn.execute("DELETE FROM age_terms WHERE ad_id IN (SELECT id FROM ads WHERE is_demo=1)")
                conn.execute("DELETE FROM ads WHERE is_demo=1")
                conn.execute("DELETE FROM raw_ads WHERE batch_id IN (SELECT id FROM import_batches WHERE is_demo=1)")
                conn.execute("DELETE FROM import_batches WHERE is_demo=1")
        return {"applied": apply, "deleted" if apply else "would_delete": n, "kept": kept}
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="path of the SQLite file (required)")
    ap.add_argument("--yes", action="store_true", help="actually delete (default: dry run)")
    a = ap.parse_args()
    print(reset_sim(a.db, a.yes))


if __name__ == "__main__":
    main()
