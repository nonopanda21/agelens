"""Read-only data endpoints. Same filter query params everywhere."""
from . import evidence as ev
from .server import HTTPError

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
        """Province x occupation cells (one grouped query) with row/column totals; same filters as the other stats."""
        return ev.matrix(_filters(req))

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
