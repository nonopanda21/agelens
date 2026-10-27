"""Evidence layer: parameterised, paginated SQL over ads / age_terms. No full-table loads.

Scope rule (contract): demo rows (is_demo=1) never mix with real rows.
  - include_demo omitted/None: real data if any exists, else demo (using_demo=True).
  - include_demo True: demo rows only.   include_demo False: real rows only (may be empty).
Per-ad "max age" = MIN(max_age) over that ad's high-confidence terms that carry a max_age.
"""
import json
import sqlite3
import statistics

from . import db
from .ageparse import ad_class as _ad_class, has_conflict as _has_conflict, term_class as _term_class

LABEL = "Demo · Synthetic data"   # badge text for every simulated/demo-derived number

_P = [("北京", "Beijing", "北京市"), ("天津", "Tianjin", "天津市"), ("河北", "Hebei", "河北省"),
      ("山西", "Shanxi", "山西省"), ("内蒙古", "Inner Mongolia", "内蒙古自治区"), ("辽宁", "Liaoning", "辽宁省"),
      ("吉林", "Jilin", "吉林省"), ("黑龙江", "Heilongjiang", "黑龙江省"), ("上海", "Shanghai", "上海市"),
      ("江苏", "Jiangsu", "江苏省"), ("浙江", "Zhejiang", "浙江省"), ("安徽", "Anhui", "安徽省"),
      ("福建", "Fujian", "福建省"), ("江西", "Jiangxi", "江西省"), ("山东", "Shandong", "山东省"),
      ("河南", "Henan", "河南省"), ("湖北", "Hubei", "湖北省"), ("湖南", "Hunan", "湖南省"),
      ("广东", "Guangdong", "广东省"), ("广西", "Guangxi", "广西壮族自治区"), ("海南", "Hainan", "海南省"),
      ("重庆", "Chongqing", "重庆市"), ("四川", "Sichuan", "四川省"), ("贵州", "Guizhou", "贵州省"),
      ("云南", "Yunnan", "云南省"), ("西藏", "Tibet", "西藏自治区"), ("陕西", "Shaanxi", "陕西省"),
      ("甘肃", "Gansu", "甘肃省"), ("青海", "Qinghai", "青海省"), ("宁夏", "Ningxia", "宁夏回族自治区"),
      ("新疆", "Xinjiang", "新疆维吾尔自治区"), ("香港", "Hong Kong", "香港特别行政区"),
      ("澳门", "Macao", "澳门特别行政区"), ("台湾", "Taiwan", "台湾省")]
PROVINCES = [{"name": n, "en": e, "full": f} for n, e, f in _P]
_PROV_ALIAS = {}
for _p in PROVINCES:
    for _k in (_p["name"], _p["full"], _p["en"], _p["en"].lower()):
        _PROV_ALIAS[_k] = _p["name"]

# preference terms (35岁以下优先) are not limits and never enter max-age statistics
MAXAGE_SQL = ("LEFT JOIN (SELECT ad_id, MIN(max_age) AS m FROM age_terms "
              "WHERE max_age IS NOT NULL AND confidence='high' AND kind <> 'preference' GROUP BY ad_id) mx ON mx.ad_id = a.id")
AGE_CLASSES = ("hard_cap", "cap_with_exception", "preference", "range_or_min", "ambiguous", "none")


def ensure_columns(conn):
    """Round-2 additive columns (schema.sql is not edited). Guarded by PRAGMA table_info; old rows are back-filled once."""
    def cols(t):
        return {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
    ac, tc = cols("ads"), cols("age_terms")
    if not ac or not tc:
        return False
    added = False
    for table, have, col, ddl in (("ads", ac, "age_class", "TEXT"), ("ads", ac, "conflict", "INTEGER NOT NULL DEFAULT 0"),
                                  ("age_terms", tc, "age_class", "TEXT"), ("age_terms", tc, "flag", "TEXT")):
        if col not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            added = True
    conn.execute("CREATE INDEX IF NOT EXISTS ix_ads_class ON ads(is_demo, age_class)")
    if added:
        _backfill(conn)
    conn.commit()
    return added


def _backfill(conn):
    """Derive age_class/conflict for rows imported before round 2 from their stored terms."""
    ids = [r[0] for r in conn.execute("SELECT id FROM ads WHERE age_class IS NULL")]
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        terms = {x: [] for x in part}
        for r in conn.execute("SELECT * FROM age_terms WHERE ad_id IN (%s)" % ",".join("?" * len(part)), part):
            d = dict(r)
            terms[d["ad_id"]].append(d)
        for aid, ts in terms.items():
            for t in ts:
                conn.execute("UPDATE age_terms SET age_class=? WHERE id=?", (_term_class(t), t["id"]))
            conn.execute("UPDATE ads SET age_class=?, conflict=? WHERE id=?", (_ad_class(ts), 1 if _has_conflict(ts) else 0, aid))


def _connect():
    c = db.connect()
    ensure_columns(c)
    return c


def _canon_province(v):
    v = str(v).strip()
    return _PROV_ALIAS.get(v, _PROV_ALIAS.get(v.lower(), v))


def _as_list(v):
    if v is None or v == "":
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if str(x) != ""]
    return [s for s in str(v).split(",") if s.strip()]


def _bool(v):
    if isinstance(v, bool) or v is None:
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _like(s):
    return "%" + s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# Full-text index for the free-text `q` filter (spec §6.4: indexed queries for large imports instead of LIKE scans).
# External-content FTS5 table with the trigram tokenizer, so substring search works for Chinese as well as English.
# Created lazily on first use and back-filled once; triggers keep it in sync with inserts/deletes/text updates afterwards.
_FTS_SQL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS ads_fts USING fts5(title, description, content='ads', content_rowid='rowid', tokenize='trigram')",
    "CREATE TRIGGER IF NOT EXISTS ads_fts_ai AFTER INSERT ON ads BEGIN INSERT INTO ads_fts(rowid, title, description) VALUES (new.rowid, new.title, new.description); END",
    "CREATE TRIGGER IF NOT EXISTS ads_fts_ad AFTER DELETE ON ads BEGIN INSERT INTO ads_fts(ads_fts, rowid, title, description) VALUES ('delete', old.rowid, old.title, old.description); END",
    "CREATE TRIGGER IF NOT EXISTS ads_fts_au AFTER UPDATE OF title, description ON ads BEGIN "
    "INSERT INTO ads_fts(ads_fts, rowid, title, description) VALUES ('delete', old.rowid, old.title, old.description); "
    "INSERT INTO ads_fts(rowid, title, description) VALUES (new.rowid, new.title, new.description); END",
)
_FTS_UNAVAILABLE = False


def _ensure_fts(conn):
    """True if the FTS index is usable on this connection's database (creating/back-filling it if needed)."""
    global _FTS_UNAVAILABLE
    if _FTS_UNAVAILABLE:
        return False
    try:
        existed = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ads_fts'").fetchone()
        for q in _FTS_SQL:
            conn.execute(q)
        if not existed:
            conn.execute("INSERT INTO ads_fts(ads_fts) VALUES ('rebuild')")
        conn.commit()
        return True
    except sqlite3.OperationalError:   # SQLite built without FTS5 / trigram: keep the LIKE path
        _FTS_UNAVAILABLE = True
        return False


def _fts_phrase(s):
    return '"' + s.replace('"', '""') + '"'


def _has(conn, demo):
    return conn.execute("SELECT 1 FROM ads WHERE is_demo=? LIMIT 1", (1 if demo else 0,)).fetchone() is not None


def _scope(conn, filters):
    has_real, has_demo = _has(conn, False), _has(conn, True)
    inc = _bool((filters or {}).get("include_demo"))
    if inc is None:
        using = (not has_real) and has_demo
    else:
        using = bool(inc)
    return {"using_demo": using, "has_real": has_real, "has_demo": has_demo}


def scope_info(filters=None):
    with _connect() as c:
        return _scope(c, filters)


def _where(conn, filters, need_mx=False):
    """Return (where_sql, params, joins_sql, applied, scope). Alias for ads is `a`."""
    f = dict(filters or {})
    scope = _scope(conn, f)
    w, p, applied = ["a.is_demo = ?"], [1 if scope["using_demo"] else 0], {}
    provs = [_canon_province(x) for x in _as_list(f.get("province"))]
    if provs:
        w.append("a.province IN (%s)" % ",".join("?" * len(provs)))
        p += provs
        applied["province"] = provs
    if f.get("city"):
        w.append("a.city = ?"); p.append(str(f["city"])); applied["city"] = str(f["city"])
    if f.get("occupation"):
        s = str(f["occupation"]).strip()
        w.append("(a.occupation LIKE ? ESCAPE '\\' OR a.title LIKE ? ESCAPE '\\')")
        p += [_like(s), _like(s)]; applied["occupation"] = s
    st = f.get("age_status")
    if st in ("explicit", "uncertain", "none"):
        w.append("a.age_status = ?"); p.append(st); applied["age_status"] = st
    cl = f.get("age_class")
    if cl in AGE_CLASSES:
        w.append("a.age_class = ?"); p.append(cl); applied["age_class"] = cl
    if _bool(f.get("conflict")) is not None:
        w.append("a.conflict = ?"); p.append(1 if _bool(f.get("conflict")) else 0); applied["conflict"] = _bool(f.get("conflict"))
    lte, gte = _int(f.get("max_age_lte")), _int(f.get("max_age_gte"))
    if lte is not None:
        w.append("mx.m <= ?"); p.append(lte); applied["max_age_lte"] = lte; need_mx = True
    if gte is not None:
        w.append("mx.m >= ?"); p.append(gte); applied["max_age_gte"] = gte; need_mx = True
    ex = _bool(f.get("has_exception"))
    if ex is not None:
        sub = ("EXISTS (SELECT 1 FROM age_terms t WHERE t.ad_id = a.id AND "
               "(t.exception_text IS NOT NULL OR t.kind='relaxable'))")
        w.append(sub if ex else "NOT " + sub); applied["has_exception"] = ex
    if f.get("date_from"):
        w.append("a.posted_date >= ?"); p.append(str(f["date_from"])); applied["date_from"] = str(f["date_from"])
    if f.get("date_to"):
        w.append("a.posted_date <= ?"); p.append(str(f["date_to"])); applied["date_to"] = str(f["date_to"])
    if f.get("q"):
        s = str(f["q"]).strip()
        if len(s) >= 3 and _ensure_fts(conn):   # trigram index needs >= 3 characters
            w.append("a.rowid IN (SELECT rowid FROM ads_fts WHERE ads_fts MATCH ?)"); p.append(_fts_phrase(s))
        else:
            w.append("(a.title LIKE ? ESCAPE '\\' OR a.description LIKE ? ESCAPE '\\')")
            p += [_like(s), _like(s)]
        applied["q"] = s
    applied["scope"] = "demo" if scope["using_demo"] else "real"
    applied["scope_label"] = LABEL if scope["using_demo"] else "Imported data"
    return " AND ".join(w), p, (MAXAGE_SQL if need_mx else ""), applied, scope


def _terms(conn, ad_ids):
    out = {i: [] for i in ad_ids}
    ids = list(ad_ids)
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        for r in conn.execute("SELECT * FROM age_terms WHERE ad_id IN (%s) ORDER BY start_offset, id" % ",".join("?" * len(part)), part):
            d = dict(r)
            out[d.pop("ad_id")].append(d)
    return out


_SUM = "a.id,a.title,a.company,a.occupation,a.province,a.city,a.posted_date,a.source,a.is_demo,a.age_status,a.age_class,a.conflict"
_SORTS = {"date_desc": "a.posted_date IS NULL, a.posted_date DESC, a.id",
          "date_asc": "a.posted_date IS NULL, a.posted_date ASC, a.id",
          "max_age_asc": "mx.m IS NULL, mx.m ASC, a.id", "max_age_desc": "mx.m IS NULL, mx.m DESC, a.id",
          "title": "a.title, a.id"}


def _summary(row, terms):
    d = dict(row)
    d["age_terms"] = terms
    d["conflict"] = bool(d.get("conflict"))
    if not d.get("age_class"):
        d["age_class"] = _ad_class(terms)
    d["label"] = LABEL if d.get("is_demo") else None
    hi = next((t for t in terms if t["confidence"] == "high" and t["kind"] != "ambiguous"), terms[0] if terms else None)
    d["snippet_highlight"] = hi["snippet"] if hi else None
    return d


def search_ads(filters=None, page=1, page_size=20, sort="date_desc"):
    page, page_size = max(1, _int(page) or 1), max(1, min(100, _int(page_size) or 20))
    with _connect() as c:
        need = sort in ("max_age_asc", "max_age_desc")
        where, p, joins, applied, scope = _where(c, filters, need_mx=need)
        total = c.execute(f"SELECT COUNT(*) FROM ads a {joins} WHERE {where}", p).fetchone()[0]
        order = _SORTS.get(sort, _SORTS["date_desc"])
        rows = c.execute(f"SELECT {_SUM} FROM ads a {joins} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
                         p + [page_size, (page - 1) * page_size]).fetchall()
        terms = _terms(c, [r["id"] for r in rows])
        items = [_summary(r, terms[r["id"]]) for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "filters_applied": applied, "using_demo": scope["using_demo"],
            "label": LABEL if scope["using_demo"] else None}


def get_ad(ad_id):
    with _connect() as c:
        r = c.execute(f"SELECT {_SUM}, a.description, a.url, a.batch_id, a.duplicate_count, a.raw_id, "
                      "b.filename, b.rule_version, r.raw_json, r.source_row "
                      "FROM ads a JOIN import_batches b ON b.id=a.batch_id JOIN raw_ads r ON r.id=a.raw_id WHERE a.id=?",
                      (ad_id,)).fetchone()
        if not r:
            return None
        terms = _terms(c, [ad_id])[ad_id]
    d = dict(r)
    raw = d.pop("raw_json")
    try:
        d["raw_row"] = json.loads(raw)
    except ValueError:
        d["raw_row"] = {"_raw": raw}
    d = _summary(d, terms)
    return d


def _counts(c, where, p, joins):
    r = c.execute(f"SELECT COUNT(*), COALESCE(SUM(a.duplicate_count),0), "
                  "COALESCE(SUM(a.age_status='explicit'),0), COALESCE(SUM(a.age_status='uncertain'),0), "
                  "COALESCE(SUM(a.age_status='none'),0), COUNT(DISTINCT a.province), COUNT(DISTINCT a.occupation), "
                  "MIN(a.posted_date), MAX(a.posted_date), COALESCE(SUM(a.province IS NULL),0) "
                  f"FROM ads a {joins} WHERE {where}", p).fetchone()
    return r


def overview(filters=None):
    with _connect() as c:
        where, p, joins, applied, scope = _where(c, filters, need_mx=True)
        u, dup, ex, un, no, provs, occs, dmin, dmax, unk = _counts(c, where, p, joins)
        top = [{"age": r[0], "count": r[1]} for r in c.execute(
            f"SELECT mx.m, COUNT(*) n FROM ads a {joins} WHERE {where} AND mx.m IS NOT NULL "
            "GROUP BY mx.m ORDER BY n DESC, mx.m LIMIT 5", p)]
        exc = c.execute(f"SELECT COUNT(*) FROM ads a {joins} WHERE {where} AND EXISTS (SELECT 1 FROM age_terms t "
                        "WHERE t.ad_id=a.id AND (t.exception_text IS NOT NULL OR t.kind='relaxable'))", p).fetchone()[0]
        bs = [dict(r) for r in c.execute(
            "SELECT id,filename,imported_at,raw_rows,unique_ads,duplicates,rule_version,is_demo FROM import_batches "
            "WHERE is_demo=? ORDER BY id DESC LIMIT 20", (1 if scope["using_demo"] else 0,))]
        for b in bs:
            b["label"] = LABEL if b["is_demo"] else None
        cls = {k: 0 for k in AGE_CLASSES}
        for k, n in c.execute(f"SELECT COALESCE(a.age_class,'none'), COUNT(*) FROM ads a {joins} WHERE {where} GROUP BY 1", p):
            cls[k] = n
        conf = c.execute(f"SELECT COUNT(*) FROM ads a {joins} WHERE {where} AND a.conflict=1", p).fetchone()[0]
        trunc = c.execute(f"SELECT COUNT(*) FROM ads a {joins} WHERE {where} AND EXISTS (SELECT 1 FROM age_terms t "
                          "WHERE t.ad_id=a.id AND t.flag LIKE '%truncated%')", p).fetchone()[0]
        info = _data_info(c, scope["using_demo"])
    return {"raw_rows": u + dup, "unique_ads": u, "duplicates": dup, "provinces": provs, "occupations": occs,
            "unknown_province_ads": unk, "date_min": dmin, "date_max": dmax,
            "explicit_count": ex, "uncertain_count": un, "none_count": no,
            "explicit_share": (ex / u) if u else None, "denominator": u, "top_max_ages": top,
            "exception_count": exc, "using_demo": scope["using_demo"], "has_real": scope["has_real"],
            "age_wording_count": ex + un, "age_wording_share": ((ex + un) / u) if u else None,
            "age_class_counts": cls, "conflict_count": conf, "truncated_count": trunc,
            "data_version": info["data_version"], "simulated": info["simulated"], "label": info["label"],
            "filters_applied": applied, "batches": bs}


def distribution_max_age(filters=None):
    with _connect() as c:
        where, p, joins, *_ = _where(c, filters, need_mx=True)
        return [{"max_age": r[0], "count": r[1]} for r in c.execute(
            f"SELECT mx.m, COUNT(*) FROM ads a {joins} WHERE {where} AND mx.m IS NOT NULL GROUP BY mx.m ORDER BY mx.m", p)]


def by_province(filters=None):
    with _connect() as c:
        where, p, joins, *_ = _where(c, filters, need_mx=True)
        agg = {r[0]: r for r in c.execute(
            f"SELECT a.province, COUNT(*), SUM(a.age_status='explicit'), "
            "SUM(EXISTS (SELECT 1 FROM age_terms t WHERE t.ad_id=a.id AND (t.exception_text IS NOT NULL OR t.kind='relaxable'))), "
            "SUM(a.age_status <> 'none'), "
            + ", ".join(f"SUM(COALESCE(a.age_class,'none')='{k}')" for k in AGE_CLASSES) + " "
            f"FROM ads a {joins} WHERE {where} AND a.province IS NOT NULL GROUP BY a.province", p)}
        ages = {}
        for prov, m in c.execute(f"SELECT a.province, mx.m FROM ads a {joins} WHERE {where} "
                                 "AND a.province IS NOT NULL AND mx.m IS NOT NULL", p):
            ages.setdefault(prov, []).append(m)
    order = {x["name"]: i for i, x in enumerate(PROVINCES)}
    out = []
    for prov, row in agg.items():
        _, n, ex, wex, aw = row[:5]
        a = ages.get(prov, [])
        out.append({"province": prov, "ads": n, "explicit": ex or 0, "explicit_share": (ex or 0) / n if n else None,
                    "with_exception": wex or 0, "min_max_age": min(a) if a else None,
                    "median_max_age": statistics.median(a) if a else None,
                    "age_wording": aw or 0, "age_wording_share": (aw or 0) / n if n else None,
                    "age_class_counts": {k: (v or 0) for k, v in zip(AGE_CLASSES, row[5:])}})
    out.sort(key=lambda r: (-r["ads"], order.get(r["province"], 99)))
    return out


def by_occupation(filters=None, limit=15):
    limit = max(1, min(200, _int(limit) or 15))
    with _connect() as c:
        where, p, joins, *_ = _where(c, filters)
        return [{"occupation": r[0], "ads": r[1], "explicit": r[2] or 0, "explicit_share": (r[2] or 0) / r[1]}
                for r in c.execute(
                    f"SELECT a.occupation, COUNT(*) n, SUM(a.age_status='explicit') FROM ads a {joins} "
                    f"WHERE {where} AND a.occupation IS NOT NULL AND a.occupation <> '' "
                    "GROUP BY a.occupation ORDER BY n DESC, a.occupation LIMIT ?", p + [limit])]


_EXC_SQL = "EXISTS (SELECT 1 FROM age_terms t WHERE t.ad_id=a.id AND (t.exception_text IS NOT NULL OR t.kind='relaxable'))"
_MATRIX_KEYS = ("ads", "explicit", "cap", "age_wording", "with_exception", "preference", "n_max_age")


def _median(xs):
    return statistics.median(xs) if xs else None


def matrix(filters=None):
    """Province x occupation cells in ONE grouped query, plus row (province) / column (occupation) totals.
    Every ad in scope lands in exactly one cell (NULL province/occupation kept as None), so cells sum to overview().
    cap = explicit maximum age (hard cap or cap with an exception); n_max_age = ads stating a maximum age, i.e. the
    denominator of median_max_age. Medians of rows/columns are computed from the per-cell age lists, not by averaging."""
    with _connect() as c:
        where, p, joins, applied, scope = _where(c, filters, need_mx=True)
        rows = c.execute(
            "SELECT a.province, NULLIF(a.occupation,''), COUNT(*), COALESCE(SUM(a.age_status='explicit'),0), "
            "COALESCE(SUM(COALESCE(a.age_class,'') IN ('hard_cap','cap_with_exception')),0), "
            "COALESCE(SUM(a.age_status<>'none'),0), COALESCE(SUM(" + _EXC_SQL + "),0), "
            "COALESCE(SUM(COALESCE(a.age_class,'')='preference'),0), GROUP_CONCAT(mx.m) "
            f"FROM ads a {joins} WHERE {where} GROUP BY a.province, NULLIF(a.occupation,'')", p).fetchall()
    cells, rtot, ctot = [], {}, {}
    total = dict.fromkeys(_MATRIX_KEYS, 0)
    total_ages = []

    def acc(bucket, key, cell, ages, name_key):
        b = bucket.get(key)
        if b is None:
            b = bucket[key] = {name_key: key, **dict.fromkeys(_MATRIX_KEYS, 0), "_ages": []}
        for k in _MATRIX_KEYS:
            b[k] += cell[k]
        b["_ages"] += ages

    for prov, occ, n, ex, cap, aw, wex, pref, ages_s in rows:
        ages = [int(x) for x in ages_s.split(",")] if ages_s else []
        cell = {"province": prov, "occupation": occ, "ads": n, "explicit": ex, "cap": cap, "age_wording": aw,
                "with_exception": wex, "preference": pref, "n_max_age": len(ages), "median_max_age": _median(ages)}
        cells.append(cell)
        acc(rtot, prov, cell, ages, "province")
        acc(ctot, occ, cell, ages, "occupation")
        for k in _MATRIX_KEYS:
            total[k] += cell[k]
        total_ages += ages

    def fin(b):
        b["median_max_age"] = _median(b.pop("_ages"))
        return b

    order = {x["name"]: i for i, x in enumerate(PROVINCES)}
    provinces = sorted((fin(b) for b in rtot.values()), key=lambda r: (-r["ads"], order.get(r["province"], 99), r["province"] or ""))
    occupations = sorted((fin(b) for b in ctot.values()), key=lambda r: (-r["ads"], r["occupation"] or ""))
    cells.sort(key=lambda r: (order.get(r["province"], 99), r["province"] or "", r["occupation"] or ""))
    total["median_max_age"] = _median(total_ages)
    return {"cells": cells, "provinces": provinces, "occupations": occupations, "total": total,
            "filters_applied": applied, "using_demo": scope["using_demo"], "label": LABEL if scope["using_demo"] else None}


def list_batches():
    with _connect() as c:
        out = []
        for r in c.execute("SELECT * FROM import_batches ORDER BY id DESC LIMIT 100"):
            d = dict(r)
            d["label"] = LABEL if d.get("is_demo") else None
            for k in ("mapping_json", "log_json"):
                try:
                    d[k[:-5]] = json.loads(d.pop(k) or "null")
                except ValueError:
                    d[k[:-5]] = None
            out.append(d)
        return out


def _data_info(c, demo):
    """Describe the data currently in scope from the newest batch (generator seed/version live in its log)."""
    r = c.execute("SELECT filename, imported_at, log_json FROM import_batches WHERE is_demo=? AND unique_ads>0 "
                  "ORDER BY id DESC LIMIT 1", (1 if demo else 0,)).fetchone()
    meta, fname, at = {}, None, None
    if r:
        fname, at = r["filename"], r["imported_at"]
        try:
            meta = (json.loads(r["log_json"] or "{}").get("source_meta")) or {}
        except ValueError:
            meta = {}
    if demo:
        ver = meta.get("version") or "demo-csv"
        seed = meta.get("seed")
        dv = meta.get("data_version") or ("demo-csv:" + fname if fname else "demo-csv")
        return {"simulated": True, "label": LABEL, "source": meta.get("source") or ("csv:" + (fname or "")),
                "seed": seed, "version": ver, "data_version": dv, "generated_at": at}
    return {"simulated": False, "label": "Imported data", "source": "csv:" + (fname or ""), "seed": None,
            "version": None, "data_version": ("import:" + fname) if fname else "empty", "generated_at": at}


def data_info(filters=None):
    with _connect() as c:
        return _data_info(c, _scope(c, filters)["using_demo"])
