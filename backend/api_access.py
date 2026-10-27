"""Invite-code access for the public demo (docs/DEPLOY.md). Replaces self-registration: nobody signs up.

Public mode (AGELENS_PUBLIC=1, set by `app.py --public`): every /api/* call except a few open ones needs a session
obtained by redeeming an invite code. Local mode (the default): no gate, everything works as before.

Invite codes live in the environment variable AGELENS_INVITES, a JSON list written by scripts/invite.py:
  [{"id": "inv_k3x9", "role": "viewer"|"reviewer", "label": "Teacher", "personal": true, "expires": "2026-12-31",
    "max_uses": 1, "sha256": "<sha256 of the code>"}]
They are kept in the environment rather than the database because a free hosting instance wipes its disk on restart.
Only hashes are stored anywhere; the plain code is shown once by scripts/invite.py. Removing an entry and redeploying
revokes it: its sessions stop working at once.
  * personal code: one person. Requests sent with it are kept on the code, so the same code opens them in any browser.
  * shared code: a group (class, other team). Requests are NOT kept on the code (people sharing it must not see each
    other's requests); they stay with the submitting browser's private key, as in local mode.
Roles: viewer (everything a seeker can do, study participation) and reviewer (viewer + the reviewer workspace).
Study raters/operators still need the study token on top (api_study.require_study).
"""
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from . import db
from .api_requests import Limiter, load
from .server import HTTPError, hash_token

SESSION_DAYS = 14
ROLES = ("viewer", "reviewer")
CODE_RX = re.compile(r"^[A-Z0-9-]{8,40}$")
OPEN_PATHS = ("/api/health", "/api/access/status", "/api/access/redeem", "/api/access/signout")
BAD_CODE = "That invite code is not valid or has expired."

fail_by_client = Limiter(10, 300)   # failed redemptions per client address
fail_all = Limiter(60, 60)          # failed redemptions overall

TABLES = """
CREATE TABLE IF NOT EXISTS invite_sessions (
  token_hash TEXT PRIMARY KEY, invite_id TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_invite_sessions_inv ON invite_sessions(invite_id);
CREATE TABLE IF NOT EXISTS invite_uses (invite_id TEXT PRIMARY KEY, uses INTEGER NOT NULL DEFAULT 0, last_used_at TEXT);
CREATE TABLE IF NOT EXISTS invite_requests (
  request_id INTEGER PRIMARY KEY REFERENCES requests(id), invite_id TEXT NOT NULL, linked_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_invite_requests_inv ON invite_requests(invite_id);
"""


def public_mode():
    return os.environ.get("AGELENS_PUBLIC") == "1"


def now_dt():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalise(code):
    """Codes are shown as AL-XXXX-XXXX; accept any case and stray spaces."""
    return re.sub(r"\s+", "", str(code or "")).upper()


def code_hash(code):
    return hashlib.sha256(normalise(code).encode()).hexdigest()


def load_invites():
    """-> {id: entry} from AGELENS_INVITES. A malformed variable gives no invites (and the start check reports it)."""
    raw = os.environ.get("AGELENS_INVITES", "").strip()
    if not raw:
        return {}
    try:
        items = json.loads(raw)
    except ValueError:
        return {}
    out = {}
    for it in items if isinstance(items, list) else []:
        if isinstance(it, dict) and it.get("id") and it.get("role") in ROLES and re.fullmatch(r"[0-9a-f]{64}", str(it.get("sha256", ""))):
            out[str(it["id"])] = it
    return out


def check_config():
    """-> list of problems with the public-mode configuration (empty = fine). Used at start-up."""
    problems = []
    raw = os.environ.get("AGELENS_INVITES", "").strip()
    try:
        items = json.loads(raw) if raw else []
    except ValueError:
        return ["AGELENS_INVITES is not valid JSON."]
    if not items:
        problems.append("AGELENS_INVITES is empty: nobody could get in. Create codes with scripts/invite.py.")
    valid = load_invites()
    if len(valid) != len(items):
        problems.append("%d of %d AGELENS_INVITES entries are malformed (need id, role viewer|reviewer, sha256)." % (len(items) - len(valid), len(items)))
    for k in ("AGELENS_REVIEWER_TOKEN", "AGELENS_STUDY_TOKEN"):
        if len(os.environ.get(k, "")) < 16:
            problems.append("%s must be set to a random value of at least 16 characters." % k)
    return problems


def expired(inv):
    exp = inv.get("expires")
    return bool(exp) and str(exp) < now_dt().strftime("%Y-%m-%d")  # valid through the expiry day (UTC)


def ensure_tables():
    with db.connect() as c:
        c.executescript(TABLES)


def bearer(req):
    a = req.headers.get("Authorization", "")
    return a[7:].strip() if a[:7].lower() == "bearer " else ""


def session(req, conn=None):
    """-> (invite entry, session row) for a valid session whose invite still exists and has not expired, else (None, None)."""
    tok = bearer(req)
    if not tok or len(tok) > 200:
        return None, None
    own = conn is None
    conn = conn or db.connect()
    try:
        row = conn.execute("SELECT * FROM invite_sessions WHERE token_hash=? AND expires_at>?", (hash_token(tok), iso(now_dt()))).fetchone()
    finally:
        if own:
            conn.close()
    if not row:
        return None, None
    inv = load_invites().get(row["invite_id"])
    if not inv or expired(inv):
        return None, None  # revoked (removed from AGELENS_INVITES) or expired: the session stops working at once
    return inv, row


def gate(req):
    """Called by the server for every /api/* request in public mode. Raises 401 without a valid invite session."""
    if req.path in OPEN_PATHS:
        return None
    inv, _ = session(req)
    if not inv:
        raise HTTPError(401, "This demo needs an invite code. Enter it on the start page.", {"invite_required": True})
    return inv


def is_reviewer(req):
    inv, _ = session(req)
    return bool(inv and inv["role"] == "reviewer")


def client_key(req):
    # behind the host's proxy the client is the first X-Forwarded-For entry; locally it is the socket address
    fwd = req.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() or "local")[:64]


# --- personal codes keep requests ---------------------------------------------------------------

def link_request(conn, req, request_id):
    """After a request is created: keep it on the invite if the session's code is personal. -> True if kept."""
    inv, _ = session(req, conn)
    if not inv or not inv.get("personal"):
        return False
    conn.execute("INSERT OR IGNORE INTO invite_requests(request_id,invite_id,linked_at) VALUES(?,?,?)", (request_id, inv["id"], iso(now_dt())))
    return True


def owns(conn, req, code):
    """-> request row iff it is kept on this session's personal invite, else None."""
    inv, _ = session(req, conn)
    if not inv or not inv.get("personal"):
        return None
    r = load(conn, code)
    if r and conn.execute("SELECT 1 FROM invite_requests WHERE request_id=? AND invite_id=?", (r["id"], inv["id"])).fetchone():
        return r
    return None


# --- handlers -----------------------------------------------------------------------------------

def status(req):
    if not public_mode():
        return {"public": False, "signed_in": False}
    inv, row = session(req)
    if not inv:
        return {"public": True, "signed_in": False}
    return {"public": True, "signed_in": True, "role": inv["role"], "label": str(inv.get("label") or "")[:60],
            "personal": bool(inv.get("personal")), "session_expires_at": row["expires_at"], "code_expires": inv.get("expires")}


def redeem(req):
    if not public_mode():
        raise HTTPError(404, "Invite codes are used only on the public demo.")
    if len(req.body or b"") > 2048:
        raise HTTPError(413, "That request is too large.")
    key = client_key(req)
    if fail_all.full("all") or fail_by_client.full(key):
        raise HTTPError(429, "Too many wrong codes. Wait a few minutes and try again.")
    code = normalise(req.json().get("code"))
    h = code_hash(code)
    inv = next((i for i in load_invites().values() if secrets.compare_digest(i["sha256"], h)), None) if CODE_RX.match(code) else None
    if not inv or expired(inv):
        fail_by_client.check(key)
        fail_all.check("all")
        raise HTTPError(401, BAD_CODE)
    t = now_dt()
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        u = conn.execute("SELECT uses FROM invite_uses WHERE invite_id=?", (inv["id"],)).fetchone()
        uses = u["uses"] if u else 0
        if inv.get("max_uses") and uses >= int(inv["max_uses"]):
            fail_by_client.check(key)
            raise HTTPError(401, BAD_CODE)
        conn.execute("INSERT INTO invite_uses(invite_id,uses,last_used_at) VALUES(?,1,?) ON CONFLICT(invite_id) DO UPDATE SET uses=uses+1, last_used_at=excluded.last_used_at",
                     (inv["id"], iso(t)))
        tok = secrets.token_urlsafe(32)
        exp = t + timedelta(days=SESSION_DAYS)
        if inv.get("expires"):
            exp = min(exp, datetime.strptime(inv["expires"], "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1))
        conn.execute("DELETE FROM invite_sessions WHERE expires_at<=?", (iso(t),))
        conn.execute("INSERT INTO invite_sessions(token_hash,invite_id,created_at,expires_at) VALUES(?,?,?,?)", (hash_token(tok), inv["id"], iso(t), iso(exp)))
        conn.commit()
    return {"token": tok, "expires_at": iso(exp), "role": inv["role"], "label": str(inv.get("label") or "")[:60], "personal": bool(inv.get("personal"))}


def signout(req):
    tok = bearer(req)
    if tok:
        with db.connect() as conn:
            conn.execute("DELETE FROM invite_sessions WHERE token_hash=?", (hash_token(tok),))
    return {"ok": True}


def kept_requests(req):
    from .api_requests import summary_out
    with db.connect() as conn:
        inv, _ = session(req, conn)
        if not inv or not inv.get("personal"):
            return {"requests": []}
        rows = conn.execute("SELECT r.* FROM invite_requests l JOIN requests r ON r.id=l.request_id WHERE l.invite_id=? ORDER BY r.created_at DESC",
                            (inv["id"],)).fetchall()
        return {"requests": [summary_out(r) for r in rows]}


def register(router):
    ensure_tables()
    router.add("GET", "/api/access/status", status)
    router.add("POST", "/api/access/redeem", redeem)
    router.add("POST", "/api/access/signout", signout)
    router.add("GET", "/api/access/requests", kept_requests)
