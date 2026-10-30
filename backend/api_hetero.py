"""GET /api/stats/hetero?source=real -- precomputed heterogeneity counts (stated age wording by required experience,
occupation and province; explicit gender wording). Shape: docs/HETERO_CONTRACT.md. Counts of how ads are worded, not hiring outcomes.
Reads the newest hetero_*.json in the real-data directory (AGELENS_REAL_DIR, default data/real); files starting with "_"
(fixtures) are used only when AGELENS_REAL_FIXTURE=1. 404 {"error": ...} when there is none; the rest of the server is unaffected."""
import json, os, threading

from . import api_data
from .server import HTTPError

_CACHE = {}
_LOCK = threading.Lock()


def hetero_file():
    d = api_data.real_dir()
    if not d.is_dir():
        return None
    allow_fixture = os.environ.get("AGELENS_REAL_FIXTURE") == "1"
    found = []
    for f in d.iterdir():
        n = f.name
        if n.endswith(".json") and f.is_file() and (n.startswith("hetero_") or (allow_fixture and n.startswith("_") and "hetero" in n)):
            try:
                found.append((f.stat().st_mtime_ns, n, f))
            except OSError:
                continue
    return max(found)[2] if found else None


def load_hetero():
    f = hetero_file()
    if f is None:
        return None
    try:
        st = f.stat()
    except OSError:
        return None
    key = (st.st_mtime_ns, st.st_size)
    with _LOCK:
        hit = _CACHE.get(str(f))
        if hit and hit[0] == key:
            return hit[1]
    try:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("by_experience"), list) or not isinstance(data.get("meta"), dict):
        return None
    with _LOCK:
        _CACHE.clear()
        _CACHE[str(f)] = (key, data)
    return data


def register(router):
    @router.get("/api/stats/hetero")
    def hetero(req):
        src = req.query.get("source", "") or "real"
        if src != "real":
            raise HTTPError(400, "Unknown source; only source=real is available.")
        data = load_hetero()
        if data is None:
            raise HTTPError(404, "No heterogeneity file is available (expected data/real/hetero_*.json).")
        return data
