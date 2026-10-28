"""Read-only data endpoints. Same filter query params everywhere.
/api/stats/matrix?source=real serves a precomputed real-data matrix (newest data/real/matrix_*.json, same shape as the
simulated one plus `meta`); /api/real/status says whether one exists. The directory is AGELENS_REAL_DIR (default data/real);
files starting with "_" (fixtures) are skipped unless AGELENS_REAL_FIXTURE=1."""
import json, os, threading
from pathlib import Path

from . import evidence as ev
from .server import HTTPError

_ROOT = Path(__file__).resolve().parent.parent
_REAL_CACHE = {}          # path -> (mtime_ns, size, parsed json)
_REAL_LOCK = threading.Lock()


def real_dir():
    return Path(os.environ.get("AGELENS_REAL_DIR") or (_ROOT / "data" / "real"))


def real_file():
    """Newest matrix_*.json in the real-data directory (by mtime, then name), or None."""
    d = real_dir()
    if not d.is_dir():
        return None
    allow_fixture = os.environ.get("AGELENS_REAL_FIXTURE") == "1"
    found = []
    for f in d.iterdir():
        n = f.name
        if not n.endswith(".json") or not f.is_file():
            continue
        if n.startswith("matrix_") or (allow_fixture and n.startswith("_") and "matrix" in n):
            try:
                found.append((f.stat().st_mtime_ns, n, f))
            except OSError:
                continue
    return max(found)[2] if found else None


def load_real():
    """Parsed real matrix (cached per file, re-read when its mtime or size changes), or None when there is none / it is unreadable."""
    f = real_file()
    if f is None:
        return None
    try:
        st = f.stat()
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    with _REAL_LOCK:
        hit = _REAL_CACHE.get(str(f))
        if hit and hit[0] == key:
            return hit[1]
    try:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("cells"), list):
        return None
    with _REAL_LOCK:
        _REAL_CACHE.clear()
        _REAL_CACHE[str(f)] = (key, data)
    return data

FILTER_KEYS = ("province", "city", "occupation", "age_status", "max_age_lte", "max_age_gte", "has_exception",
               "date_from", "date_to", "q", "include_demo", "age_class", "conflict")


def _filters(req):
    return {k: req.query[k] for k in FILTER_KEYS if req.query.get(k, "") != ""}


def register(router):
    @router.get("/api/provinces")
    def provinces(req):
        return ev.PROVINCES

    @router.get("/api/overview")
    def overview(req):
        return ev.overview(_filters(req))

    @router.get("/api/ads")
    def ads(req):
        return ev.search_ads(_filters(req), req.int_query("page", 1, 1, 10_000_000),
                             req.int_query("page_size", 20, 1, 100), req.query.get("sort", "date_desc"))

    @router.get("/api/ads/<ad_id>")
    def ad(req):
        d = ev.get_ad(req.params["ad_id"])
        if not d:
            raise HTTPError(404, "Ad not found.")
        return d

    # Stats endpoints return bare lists (same shape as the evidence functions); use /api/overview for the denominator.
    @router.get("/api/stats/max-age")
    def max_age(req):
        return ev.distribution_max_age(_filters(req))

    @router.get("/api/stats/provinces")
    def provs(req):
        return ev.by_province(_filters(req))

    @router.get("/api/stats/occupations")
    def occs(req):
        return ev.by_occupation(_filters(req), req.int_query("limit", 15, 1, 200))

    @router.get("/api/stats/matrix")
    def matrix(req):
        """Province x occupation cells (one grouped query) with row/column totals; same filters as the other stats.
        ?source=real returns the precomputed real-data matrix instead (filters do not apply to it)."""
        src = req.query.get("source", "") or "demo"
        if src == "real":
            data = load_real()
            if data is None:
                raise HTTPError(404, "No real-data matrix is available (expected data/real/matrix_*.json).")
            return data
        if src != "demo":
            raise HTTPError(400, "Unknown source; use source=real or source=demo.")
        return ev.matrix(_filters(req))

    @router.get("/api/real/status")
    def real_status(req):
        """Whether a real-data matrix exists, and its headline facts (from its meta)."""
        data = load_real()
        if data is None:
            return {"available": False, "label": None, "years": None, "rows_used": None, "generated_at": None, "method": None}
        meta = data.get("meta") or {}
        return {"available": True, "label": data.get("label"), "years": meta.get("years"), "rows_used": meta.get("rows_used"),
                "generated_at": meta.get("generated_at"), "method": meta.get("method"), "source": meta.get("source"),
                "total_ads": (data.get("total") or {}).get("ads")}

    @router.get("/api/status")
    def status(req):
        """Data state and model state, reported separately (never one claim for both)."""
        info = ev.data_info(_filters(req))
        try:
            from backend import llm
            m = llm.status()
            if not isinstance(m, dict) or "connected" not in m:
                raise ValueError("llm.status() has no 'connected' key")
        except Exception:  # llm module missing/older/failing: honest default
            m = {"connected": False, "label": "Template demo"}
        return {"data": info, "model": m}

    @router.get("/api/batches")
    def batches(req):
        return ev.list_batches()
