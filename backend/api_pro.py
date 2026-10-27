"""Pro (stage 1 of the paid plan, docs/PRO.md): free features stay free; the full Word report needs a Pro code with credits.
No money changes hands in stage 1: Pro codes are handed out by the team (scripts/pro_code.py), like the invite codes.

Codes: environment variable AGELENS_PRO_CODES (JSON list, sha256 only), or locally (not in public mode) the git-ignored
file data/pro_codes.local.json. Entry: {"id", "label", "credits", "expires", "sha256"}. One code = one wallet of credits,
shared by every browser that redeems it. Redeeming gives a Pro session token (header X-Pro-Token; only its sha256 is
stored). Generating a report uses one credit, taken in the same transaction that checks the balance, and only when the
report was actually built (a failed or empty report costs nothing). Credits used are counted in the database: on a
free host whose disk is wiped at restart, the count starts again from zero (documented limitation).
Endpoints: GET /api/pro/status · POST /api/pro/redeem · POST /api/pro/signout · POST /api/report/preview (free) ·
POST /api/report (Pro; returns the .docx). The server, not the page, decides whether a report may be made."""
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from . import db, report
from .api_requests import Limiter
from .server import HTTPError, Response, hash_token

LOCAL_FILE = db.DATA_DIR / "pro_codes.local.json"
SESSION_DAYS = 30
MAX_BODY = 64 * 1024
BAD_CODE = "That Pro code is not valid or has expired."
CODE_RX = re.compile(r"^[A-Z0-9-]{8,40}$")
fail_by_client = Limiter(10, 300)
report_limiter = Limiter(20, 60)  # report builds per minute, whole process

TABLES = """
CREATE TABLE IF NOT EXISTS pro_sessions (token_hash TEXT PRIMARY KEY, code_id TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pro_usage (code_id TEXT PRIMARY KEY, used INTEGER NOT NULL DEFAULT 0, last_used_at TEXT);
CREATE TABLE IF NOT EXISTS pro_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, code_id TEXT NOT NULL, created_at TEXT NOT NULL,
  ads INTEGER NOT NULL, report_version TEXT NOT NULL);
"""


def now_dt():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalise(code):
    return re.sub(r"\s+", "", str(code or "")).upper()


def code_hash(code):
    return hashlib.sha256(normalise(code).encode()).hexdigest()


def load_codes():
    raw = os.environ.get("AGELENS_PRO_CODES", "").strip()
    if not raw and os.environ.get("AGELENS_PUBLIC") != "1" and LOCAL_FILE.exists():
        raw = LOCAL_FILE.read_text()
    try:
        items = json.loads(raw) if raw else []
    except ValueError:
        return {}
    return {str(i["id"]): i for i in items if isinstance(i, dict) and i.get("id") and re.fullmatch(r"[0-9a-f]{64}", str(i.get("sha256", "")))
            and isinstance(i.get("credits"), int) and i["credits"] > 0}


def expired(c):
    return bool(c.get("expires")) and str(c["expires"]) < now_dt().strftime("%Y-%m-%d")


def ensure_tables():
    with db.connect() as c:
        c.executescript(TABLES)


def pro_session(req, conn):
    """-> (code entry, used) for a valid Pro session, else (None, 0)."""
    tok = req.headers.get("X-Pro-Token", "")
    if not tok or len(tok) > 200:
        return None, 0
    row = conn.execute("SELECT * FROM pro_sessions WHERE token_hash=? AND expires_at>?", (hash_token(tok), iso(now_dt()))).fetchone()
    code = load_codes().get(row["code_id"]) if row else None
    if not code or expired(code):
        return None, 0
    u = conn.execute("SELECT used FROM pro_usage WHERE code_id=?", (code["id"],)).fetchone()
    return code, (u["used"] if u else 0)


def wallet(code, used):
    return {"active": True, "label": str(code.get("label") or "")[:60], "credits_total": code["credits"], "credits_used": min(used, code["credits"]),
            "credits_left": max(0, code["credits"] - used), "expires": code.get("expires")}


def client_key(req):
    return ((req.headers.get("X-Forwarded-For", "").split(",")[0].strip()) or "local")[:64]


def body(req):
    if len(req.body or b"") > MAX_BODY:
        raise HTTPError(413, "That request is too large.")
    return req.json()


# --- handlers -----------------------------------------------------------------------------------

def status(req):
    with db.connect() as conn:
        code, used = pro_session(req, conn)
        return wallet(code, used) if code else {"active": False}


def redeem(req):
    key = client_key(req)
    if fail_by_client.full(key):
        raise HTTPError(429, "Too many wrong codes. Wait a few minutes and try again.")
    code = normalise(body(req).get("code"))
    h = code_hash(code)
    hit = next((c for c in load_codes().values() if secrets.compare_digest(c["sha256"], h)), None) if CODE_RX.match(code) else None
    if not hit or expired(hit):
        fail_by_client.check(key)
        raise HTTPError(401, BAD_CODE)
    tok, t = secrets.token_urlsafe(32), now_dt()
    exp = t + timedelta(days=SESSION_DAYS)
    if hit.get("expires"):
        exp = min(exp, datetime.strptime(hit["expires"], "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1))
    with db.connect() as conn:
        conn.execute("INSERT INTO pro_sessions(token_hash,code_id,created_at,expires_at) VALUES(?,?,?,?)", (hash_token(tok), hit["id"], iso(t), iso(exp)))
        u = conn.execute("SELECT used FROM pro_usage WHERE code_id=?", (hit["id"],)).fetchone()
        return dict(wallet(hit, u["used"] if u else 0), token=tok, session_expires_at=iso(exp))


def signout(req):
    tok = req.headers.get("X-Pro-Token", "")
    if tok:
        with db.connect() as conn:
            conn.execute("DELETE FROM pro_sessions WHERE token_hash=?", (hash_token(tok),))
    return {"ok": True}


def preview(req):
    """Free: what the report would contain for this question and background (titles + summary numbers)."""
    try:
        b, ctx = report.build(body(req))
    except ValueError as e:
        raise HTTPError(422, str(e))
    return report.outline(b, ctx)


def make_report(req):
    data = body(req)
    with db.connect() as conn:
        code, used = pro_session(req, conn)
    if not code:
        raise HTTPError(402, "The full report is a Pro feature. Enter a Pro code to unlock it; everything else stays free.", {"pro_required": True})
    if used >= code["credits"]:
        raise HTTPError(403, "This Pro code has no report credits left.", {"credits_left": 0})
    if not report_limiter.check("report"):
        raise HTTPError(429, "Too many reports at once. Please try again in a minute.")
    try:
        b, ctx = report.build(data)
        doc = report.to_docx(b, ctx)
    except ValueError as e:
        raise HTTPError(422, str(e))  # nothing matched: no report, no credit used
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")  # take the credit atomically: two tabs cannot spend the same last credit
        u = conn.execute("SELECT used FROM pro_usage WHERE code_id=?", (code["id"],)).fetchone()
        used_now = u["used"] if u else 0
        if used_now >= code["credits"]:
            conn.rollback()
            raise HTTPError(403, "This Pro code has no report credits left.", {"credits_left": 0})
        ts = iso(now_dt())
        conn.execute("INSERT INTO pro_usage(code_id,used,last_used_at) VALUES(?,1,?) ON CONFLICT(code_id) DO UPDATE SET used=used+1, last_used_at=excluded.last_used_at",
                     (code["id"], ts))
        conn.execute("INSERT INTO pro_reports(code_id,created_at,ads,report_version) VALUES(?,?,?,?)", (code["id"], ts, len(ctx["ads"]), report.REPORT_VERSION))
        conn.commit()
    left = max(0, code["credits"] - used_now - 1)
    name = "AgeLens-report-%s.docx" % now_dt().strftime("%Y%m%d-%H%M")
    return Response(doc, 200, "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    {"Content-Disposition": 'attachment; filename="%s"' % name, "X-Credits-Left": str(left), "Access-Control-Expose-Headers": "X-Credits-Left"})


def register(router):
    ensure_tables()
    router.add("GET", "/api/pro/status", status)
    router.add("POST", "/api/pro/redeem", redeem)
    router.add("POST", "/api/pro/signout", signout)
    router.add("POST", "/api/report/preview", preview)
    router.add("POST", "/api/report", make_report)
