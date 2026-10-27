#!/usr/bin/env python3
"""Chunked, streaming, idempotent CSV importer for AgeLens.

  python scripts/import_csv.py FILE.csv [--mapping map.json] [--demo] [--chunk 5000] [--inspect]
  python scripts/import_csv.py --source sim [--seed N]     # generate the simulated ads and import them (is_demo=1)

The importer reads through backend.datasource (CsvSource / SimulatedSource) and does not know which one it has.

Never loads the whole file. The file is hashed (streamed) so re-running the same file is a no-op.
Env AGELENS_DB selects the database (default data/agelens.db).
"""
import argparse, hashlib, json, re, sys, time, unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from backend import db, evidence  # noqa: E402
from backend.ageparse import parse_age, age_status, ad_class, has_conflict, RULE_VERSION  # noqa: E402
from backend.datasource import (ALIASES, ALIAS_MAP, FIELDS, CsvSource, SimulatedSource, detect_encoding,  # noqa: E402,F401
                                detect_delimiter, suggest_mapping, sha256_file)
from geo_table import CITY_TO_PROVINCE, NAMES  # noqa: E402

DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日", "%Y%m%d", "%Y-%m", "%Y/%m", "%Y年%m月", "%d-%m-%Y", "%m/%d/%Y"]


def norm(s):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or "")).lower()


def parse_date(s):
    s = (s or "").strip()
    if not s:
        return None, None
    core = re.split(r"[ T]", s, 1)[0] if re.match(r"^\d{4}[-/.]\d", s) else s
    core = re.sub(r"[日号]?\s*\d{1,2}[:：]\d{2}.*$", "", core)
    for fmt in DATE_FORMATS:
        try:
            d = datetime.strptime(core, fmt)
            if 1990 <= d.year <= 2100:
                return d.strftime("%Y-%m-%d"), fmt
        except ValueError:
            pass
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            return datetime(int(m[1]), int(m[2]), int(m[3])).strftime("%Y-%m-%d"), "%Y-%m-%d"
        except ValueError:
            pass
    return None, None


def locate(city_raw, prov_raw):
    """Return (city, province) using the built-in table. Unknown stays None."""
    prov = None
    if prov_raw and prov_raw.strip():
        p = evidence._canon_province(prov_raw.strip())
        names = {x["name"] for x in evidence.PROVINCES}
        if p not in names:
            for n in names:
                if prov_raw.startswith(n):
                    p = n; break
        prov = p if p in names else None
    city, text = None, (city_raw or "").strip()
    if text:
        best = None
        for n in NAMES:
            i = text.find(n)
            if i >= 0 and (best is None or i < best[0]):
                best = (i, n)
        pn = None
        for x in evidence.PROVINCES:
            for k in (x["name"], x["full"]):
                i = text.find(k)
                if i >= 0 and (pn is None or i < pn[0]):
                    pn = (i, x["name"])
        if best:
            city = best[1]
            prov = prov or CITY_TO_PROVINCE[best[1]]
        elif pn:
            prov = prov or pn[1]
        if city is None:
            c = re.split(r"[-–—·/,，、\s]", text)[0].strip()
            city = re.sub(r"[市区县]$", "", c) if len(c) > 2 else c
            city = city or None
    return city, prov


def clean_occupation(category, title):
    s = (category or "").strip()
    if s:
        return s[:60]
    t = re.sub(r"[\(（\[【].*?[\)）\]】]", "", title or "")
    t = re.sub(r"(急聘|诚聘|招聘|\d+[kK千万元/月-]+.*$)", "", t).strip(" -_/|")
    return t[:60] or None


def ensure_indexes(conn):
    for sql in [
        "CREATE INDEX IF NOT EXISTS ix_ads_demo_prov ON ads(is_demo, province)",
        "CREATE INDEX IF NOT EXISTS ix_ads_demo_date ON ads(is_demo, posted_date)",
        "CREATE INDEX IF NOT EXISTS ix_ads_batch ON ads(batch_id)",
        "CREATE INDEX IF NOT EXISTS ix_ads_city ON ads(city)",
        "CREATE INDEX IF NOT EXISTS ix_raw_batch ON raw_ads(batch_id)",
        "CREATE INDEX IF NOT EXISTS ix_terms_kind ON age_terms(kind)",
    ]:
        conn.execute(sql)


def import_file(path, mapping=None, demo=False, chunk=5000, inspect=False, quiet=False, now=None):
    """CSV convenience wrapper (kept for round-1 callers and tests)."""
    src = CsvSource(path, mapping)
    if inspect:
        return src.describe()
    return import_source(src, demo=demo, chunk=chunk, quiet=quiet, now=now)


def import_source(src, demo=False, chunk=5000, quiet=False, now=None):
    """Import any DataSource. A source whose metadata says simulated=True is always stored with is_demo=1."""
    t0 = time.time()
    meta = src.metadata()
    demo = bool(demo or meta.get("simulated"))
    desc = src.describe()
    sha = src.fingerprint()
    db.init_schema()
    conn = db.connect()
    conn.execute("PRAGMA synchronous=NORMAL")
    evidence.ensure_columns(conn)
    ensure_indexes(conn)
    for r in conn.execute("SELECT id, log_json FROM import_batches WHERE is_demo=?", (1 if demo else 0,)).fetchall():
        try:
            lg = json.loads(r["log_json"] or "{}")
        except ValueError:
            continue
        if lg.get("file_sha256") == sha:
            if lg.get("status") == "complete":
                conn.close()
                if not quiet:
                    print(f"Already imported as batch {r['id']} (same content hash); nothing to do.")
                return {"batch_id": r["id"], "skipped": True, "log": lg}
            b = r["id"]  # interrupted earlier: drop partial batch and redo
            with conn:
                conn.execute("DELETE FROM age_terms WHERE ad_id IN (SELECT id FROM ads WHERE batch_id=?)", (b,))
                conn.execute("DELETE FROM ads WHERE batch_id=?", (b,))
                conn.execute("DELETE FROM raw_ads WHERE batch_id=?", (b,))
                conn.execute("DELETE FROM import_batches WHERE id=?", (b,))
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    log = {"status": "running", "file_sha256": sha, "source_meta": meta, "encoding": desc["encoding"],
           "delimiter": desc["delimiter"], "header": desc["header"], "chunk": chunk, "warnings": list(src.warnings)}
    if meta.get("file_bytes"):
        log["file_bytes"] = meta["file_bytes"]
    with conn:
        bid = conn.execute("INSERT INTO import_batches(filename,imported_at,mapping_json,log_json,rule_version,is_demo) VALUES (?,?,?,?,?,?)",
                           (src.filename, stamp, json.dumps(desc["mapping"], ensure_ascii=False), json.dumps(log, ensure_ascii=False),
                            RULE_VERSION, 1 if demo else 0)).lastrowid
    miss, datefmts, unk_cities = Counter(), Counter(), Counter()
    st = Counter()

    def flush(rows):
        """rows: list of (source_row, raw_dict, fields). One write transaction per chunk."""
        keyed = []
        for sr, raw, f in rows:
            title, comp, desc_ = f["title"], f["company"], f["description"]
            city_raw, prov_raw = f["city"], f["province"]
            city, prov = locate(city_raw, prov_raw)
            posted, fmt = parse_date(f["date"])
            for fld, v in (("title", title), ("company", comp), ("description", desc_), ("city", city_raw), ("date", f["date"])):
                if not v:
                    miss[fld] += 1
            if f["date"] and not posted:
                miss["date_unparseable"] += 1
            if fmt:
                datefmts[fmt] += 1
            if not prov:
                st["province_unknown"] += 1
                if city_raw: unk_cities[city_raw[:30]] += 1
            key = "|".join([("demo" if demo else ""), norm(title), norm(comp), norm(city or city_raw),
                            hashlib.sha1(norm(desc_).encode()).hexdigest()])
            aid = "ad_" + hashlib.sha1(key.encode()).hexdigest()[:12]
            keyed.append((sr, json.dumps(raw, ensure_ascii=False), aid, dict(
                title=title or None, company=comp or None, occupation=clean_occupation(f["category"], title),
                province=prov, city=city, posted_date=posted, source=f["source"] or None,
                url=f["url"] or None, description=desc_ or None)))
        with conn:
            if not conn.in_transaction:
                conn.execute("BEGIN IMMEDIATE")  # single writer: raw ids below are contiguous
            conn.executemany("INSERT INTO raw_ads(batch_id,source_row,raw_json) VALUES (?,?,?)",
                             [(bid, sr, rj) for sr, rj, _, _ in keyed])
            base = conn.execute("SELECT MAX(id) FROM raw_ads").fetchone()[0] - len(keyed)
            ids = [a for _, _, a, _ in keyed]
            existing = set()
            for i in range(0, len(ids), 500):
                part = ids[i:i + 500]
                existing.update(r[0] for r in conn.execute("SELECT id FROM ads WHERE id IN (%s)" % ",".join("?" * len(part)), part))
            dups, new_rows, seen = Counter(), [], set()
            for n, (sr, rj, aid, d) in enumerate(keyed):
                if aid in existing or aid in seen:
                    dups[aid] += 1
                else:
                    seen.add(aid); new_rows.append((aid, base + n + 1, d))
            terms, ad_rows = [], []
            for aid, rid, d in new_rows:
                ts = parse_age(d["description"] or "")
                status, cls, conf = age_status(ts), ad_class(ts), 1 if has_conflict(ts) else 0
                st["status_" + status] += 1
                st["class_" + cls] += 1
                st["conflict"] += conf
                ad_rows.append((aid, bid, rid, d["title"], d["company"], d["occupation"], d["province"], d["city"],
                                d["posted_date"], d["source"], d["url"], d["description"], status, 1 if demo else 0, cls, conf))
                for t in ts:
                    terms.append((aid, t["kind"], t["min_age"], t["max_age"], t["snippet"], t["start_offset"],
                                  t["end_offset"], t["exception_text"], t["confidence"], t["rule_version"],
                                  t["age_class"], t.get("flag")))
            conn.executemany("INSERT INTO ads(id,batch_id,raw_id,title,company,occupation,province,city,posted_date,source,url,description,age_status,is_demo,age_class,conflict) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ad_rows)
            conn.executemany("INSERT INTO age_terms(ad_id,kind,min_age,max_age,snippet,start_offset,end_offset,exception_text,confidence,rule_version,age_class,flag) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", terms)
            conn.executemany("UPDATE ads SET duplicate_count=duplicate_count+? WHERE id=?", [(n, a) for a, n in dups.items()])
            st["unique"] += len(new_rows); st["dups"] += sum(dups.values())

    buf = []
    for sr, raw, fields in src.iter_ads():
        buf.append((sr, raw, fields))
        st["raw"] += 1
        if len(buf) >= chunk:
            flush(buf); buf = []
            if not quiet:
                print(f"  ... {st['raw']} rows", file=sys.stderr)
    if buf:
        flush(buf)
    log.update(status="complete", seconds=round(time.time() - t0, 2), source_rows_read=src.stats["source_rows_read"],
               blank_rows_skipped=src.stats["blank_rows_skipped"], raw_rows=st["raw"], unique_ads=st["unique"], duplicates=st["dups"],
               missing_values=dict(miss), date_formats=dict(datefmts), province_unknown=st["province_unknown"],
               top_unknown_locations=unk_cities.most_common(20),
               age_status={k: st["status_" + k] for k in ("explicit", "uncertain", "none")},
               age_class={k: st["class_" + k] for k in ("hard_cap", "cap_with_exception", "preference", "range_or_min", "ambiguous", "none")},
               conflict_ads=st["conflict"],
               dedupe_key="normalised title + company + city + sha1(description)", rule_version=RULE_VERSION,
               warnings=list(src.warnings))
    with conn:
        conn.execute("UPDATE import_batches SET raw_rows=?, unique_ads=?, duplicates=?, log_json=? WHERE id=?",
                     (st["raw"], st["unique"], st["dups"], json.dumps(log, ensure_ascii=False), bid))
    conn.close()
    if not quiet:
        print(f"Imported batch {bid}: {st['raw']} raw rows -> {st['unique']} unique ads, {st['dups']} duplicates; "
              f"{st['province_unknown']} rows with unknown province; encoding={desc['encoding']}; {log['seconds']}s")
    return {"batch_id": bid, "skipped": False, "log": log}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?")
    ap.add_argument("--source", choices=["csv", "sim"], default="csv", help="sim = generate the simulated ads and import them")
    ap.add_argument("--seed", type=int, help="seed for --source sim (default: generator default)")
    ap.add_argument("--mapping", help="JSON file {csv_column: canonical_field}; canonical: " + ", ".join(FIELDS))
    ap.add_argument("--demo", action="store_true", help="mark rows as synthetic demo data (is_demo=1)")
    ap.add_argument("--chunk", type=int, default=5000)
    ap.add_argument("--inspect", action="store_true", help="only print encoding/header/suggested mapping")
    a = ap.parse_args()
    if a.source == "sim":
        src = SimulatedSource(a.seed)
        if a.inspect:
            print(json.dumps(src.describe(), ensure_ascii=False, indent=2)); return
        import_source(src, demo=True, chunk=max(1, a.chunk))
        return
    if not a.file:
        ap.error("FILE is required unless --source sim")
    mapping = json.loads(Path(a.mapping).read_text(encoding="utf-8")) if a.mapping else None
    if a.inspect:
        print(json.dumps(CsvSource(a.file, mapping).describe(), ensure_ascii=False, indent=2)); return
    import_source(CsvSource(a.file, mapping), demo=a.demo, chunk=max(1, a.chunk))


if __name__ == "__main__":
    main()
