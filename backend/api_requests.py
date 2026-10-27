"""Human-review loop: seeker requests + reviewer workspace.

Isolation is enforced here, server-side:
  * seeker endpoints need X-Owner-Token (or X-Owner-Tokens), or on the public demo the personal invite code the
    request was kept on (api_access.py); only sha256 hashes are stored;
    a wrong/unknown token yields 404 so existence is not leaked;
  * seeker responses are built from published=1 messages only (drafts never leave the reviewer side);
  * reviewer endpoints call require_reviewer() first (401 without the demo reviewer token).
Snapshots (profile/evidence/scope) are written once at creation and never updated.
Question/answer/reply text is never logged. Reply extras (neutral rewrite suggestion) are kept inside
messages.to_verify_json as {"items": [...], "rewrite": "..."} to avoid a schema change.
"""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone

from . import db
from .server import HTTPError, hash_token, new_owner_token, require_reviewer

STATUSES = ("pending", "needs_info", "replied", "closed")
PROFILE_KEYS = ("age", "occupation", "years_experience", "skills", "region", "education", "summary")
MAX_QUESTION, MAX_TEXT, MAX_ITEMS, MAX_ITEM_LEN, MAX_EVIDENCE = 4000, 8000, 30, 1000, 10
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024
MAX_CREATE_BODY, MAX_ACTION_BODY, MAX_EVIDENCE_BYTES = 3 * 1024 * 1024, 96 * 1024, 400 * 1024
DUP_WINDOW_S = 30           # identical content from a double submit inside this window is refused
PAGE_DEFAULT, PAGE_MAX = 25, 100
IDEM_RX = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
EVENT_NAMES = ("created", "info_requested", "answered", "draft_saved", "published", "closed")
SEEKER_HIDDEN_EVENTS = ("draft_saved",)   # drafts must not even be hinted at on the seeker side
CONSENT_VERSION = "2026-10-a"


class Limiter:
    """In-memory sliding window (per process). Demo-grade abuse limit, not a security boundary."""
    def __init__(self, limit, window):
        self.limit, self.window, self.hits, self.lock = limit, window, {}, threading.Lock()

    def check(self, key):
        now_ = time.monotonic()
        with self.lock:
            q = [t for t in self.hits.get(key, []) if now_ - t < self.window]
            if len(q) >= self.limit:
                self.hits[key] = q
                return False
            q.append(now_)
            self.hits[key] = q
            return True

    def full(self, key):
        """True if the window for key is already at the limit (does not record a hit)."""
        now_ = time.monotonic()
        with self.lock:
            q = [t for t in self.hits.get(key, []) if now_ - t < self.window]
            self.hits[key] = q
            return len(q) >= self.limit

    def reset(self):
        with self.lock:
            self.hits.clear()


_rate = int(os.environ.get("AGELENS_REQ_RATE", "40"))
create_limiter = Limiter(_rate, 60)      # POST /api/requests, all callers (local demo: one process)
answer_limiter = Limiter(_rate, 60)      # seeker answers
bad_token_limiter = Limiter(10, 60)      # failed reviewer sign-ins
TOO_MANY = "Too many attempts in a short time. Please wait a minute and try again."


def size_guard(req, limit):
    if len(req.body) > limit:
        raise HTTPError(413, f"That submission is too large (limit {limit // 1024} KB). Shorten the text or select less evidence.")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def text_field(data, key, maxlen, required=True, label=None):
    v = data.get(key)
    label = label or key
    if v is None or v == "":
        if required:
            raise HTTPError(400, f"{label} is required.")
        return ""
    if not isinstance(v, str):
        raise HTTPError(400, f"{label} must be text.")
    v = v.strip()
    if required and not v:
        raise HTTPError(400, f"{label} is required.")
    if len(v) > maxlen:
        raise HTTPError(400, f"{label} is too long (max {maxlen} characters).")
    return v


def list_field(data, key, required=False):
    v = data.get(key, [])
    if v is None:
        v = []
    if not isinstance(v, list):
        raise HTTPError(400, f"{key} must be a list of text items.")
    if len(v) > MAX_ITEMS:
        raise HTTPError(400, f"{key} has too many items (max {MAX_ITEMS}).")
    out = []
    for it in v:
        if not isinstance(it, str):
            raise HTTPError(400, f"Every item in {key} must be text.")
        it = it.strip()
        if not it:
            continue
        if len(it) > MAX_ITEM_LEN:
            raise HTTPError(400, f"An item in {key} is too long (max {MAX_ITEM_LEN} characters).")
        out.append(it)
    if required and not out:
        raise HTTPError(400, f"{key} needs at least one item.")
    return out


def jloads(s, default=None):
    try:
        return json.loads(s) if s else default
    except ValueError:
        return default


def jdumps(o):
    return json.dumps(o, ensure_ascii=False)


# --- shaping -------------------------------------------------------------------------------

def unpack_verify(raw):
    v = jloads(raw, [])
    if isinstance(v, dict):
        return v.get("items", []), v.get("rewrite", "")
    return v or [], ""


def message_out(m):
    items, rewrite = unpack_verify(m["to_verify_json"])
    out = {"id": m["id"], "author": m["author"], "kind": m["kind"], "body": m["body"],
           "created_at": m["created_at"], "published": bool(m["published"])}
    if m["kind"] in ("reply", "draft"):
        out.update(facts=jloads(m["facts_json"], []), to_verify=items, rewrite_suggestion=rewrite)
    return out


def request_out(r, messages, reviewer, conn=None):
    d = {"code": r["code"], "status": r["status"], "question": r["question"],
         "profile": jloads(r["profile_json"], {}), "evidence": jloads(r["evidence_json"], []),
         "scope": jloads(r["scope_json"], None), "is_demo": bool(r["is_demo"]),
         "created_at": r["created_at"], "updated_at": r["updated_at"],
         "published_at": r["published_at"], "closed_at": r["closed_at"]}
    d["messages"] = [message_out(m) for m in messages if reviewer or m["published"]]
    if conn is not None:
        d["events"] = events_out(conn, r["id"], reviewer)
        d["consent"] = consent_out(conn, r["id"])
    return d


def summary_out(r, with_counts=False):
    q = r["question"]
    return {"code": r["code"], "status": r["status"], "question": q if len(q) <= 160 else q[:157] + "...",
            "is_demo": bool(r["is_demo"]), "evidence_count": len(jloads(r["evidence_json"], [])),
            "created_at": r["created_at"], "updated_at": r["updated_at"],
            "published_at": r["published_at"], "closed_at": r["closed_at"]}


def load(conn, code):
    return conn.execute("SELECT * FROM requests WHERE code=?", (code,)).fetchone()


def load_messages(conn, rid, published_only):
    sql = "SELECT * FROM messages WHERE request_id=?" + (" AND published=1" if published_only else "") + " ORDER BY id"
    return conn.execute(sql, (rid,)).fetchall()


def owned(conn, code, token):
    """Return the request row iff token matches; otherwise 404 (no existence leak)."""
    r = load(conn, code)
    if not r or not token or not secrets.compare_digest(r["owner_token_hash"], hash_token(token)):
        raise HTTPError(404, "Request not found for this browser.")
    return r


def seeker_row(conn, req, code):
    """The request row for this seeker: by owner key (X-Owner-Token), or, on the public demo, by the personal invite code
    the request was kept on (api_access.py). Both fail with the same 404 so existence is not leaked."""
    tok = req.headers.get("X-Owner-Token", "")
    if tok:
        return owned(conn, code, tok)
    from . import api_access  # late import: api_access imports this module
    if not api_access.bearer(req):
        raise HTTPError(401, "Missing owner token.")
    r = api_access.owns(conn, req, code)
    if not r:
        raise HTTPError(404, "Request not found for this browser.")
    return r


def reviewer_row(conn, code):
    r = load(conn, code)
    if not r:
        raise HTTPError(404, "Request not found.")
    return r


def add_message(conn, rid, author, kind, body, published, facts=None, verify=None, ts=None):
    cur = conn.execute(
        "INSERT INTO messages(request_id,author,kind,body,facts_json,to_verify_json,published,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (rid, author, kind, body, None if facts is None else jdumps(facts), None if verify is None else jdumps(verify),
         1 if published else 0, ts or now()))
    return cur.lastrowid


def add_event(conn, rid, event, actor, frm, to, ts):
    conn.execute("INSERT INTO request_events(request_id,event,actor,from_status,to_status,created_at) VALUES(?,?,?,?,?,?)",
                 (rid, event, actor, frm, to, ts))


def events_out(conn, rid, reviewer):
    rows = conn.execute("SELECT * FROM request_events WHERE request_id=? ORDER BY id", (rid,)).fetchall()
    return [{"event": e["event"], "actor": e["actor"], "from_status": e["from_status"], "to_status": e["to_status"], "at": e["created_at"]}
            for e in rows if reviewer or e["event"] not in SEEKER_HIDDEN_EVENTS]


def consent_out(conn, rid):
    m = conn.execute("SELECT consent_json FROM request_meta WHERE request_id=?", (rid,)).fetchone()
    c = jloads(m["consent_json"], None) if m else None
    return c or {"fields": None, "recorded_at": None, "legacy": True}


def set_status(conn, rid, status, ts, **extra):
    cols = {"status": status, "updated_at": ts, **extra}
    conn.execute("UPDATE requests SET " + ",".join(f"{k}=?" for k in cols) + " WHERE id=?", (*cols.values(), rid))


# --- validation of creation payload ---------------------------------------------------------

def clean_profile(p):
    if p is None:
        return {}
    if not isinstance(p, dict):
        raise HTTPError(400, "profile must be an object.")
    out = {}
    for k in PROFILE_KEYS:
        v = p.get(k)
        if v in (None, "", []):
            continue
        if isinstance(v, list):
            if len(v) > 40 or not all(isinstance(x, str) and len(x) <= 100 for x in v):
                raise HTTPError(400, f"profile.{k} must be a short list of text items.")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            pass
        elif isinstance(v, str):
            if len(v) > 1000:
                raise HTTPError(400, f"profile.{k} is too long.")
        else:
            raise HTTPError(400, f"profile.{k} has an unsupported type.")
        out[k] = v
    return out


def clean_consent(raw, profile):
    """Which profile fields the seeker agreed to share. Missing -> the fields actually sent. Profile is cut to the consented set."""
    if raw is None:
        fields = list(profile)
    else:
        if not isinstance(raw, dict) or not isinstance(raw.get("fields", []), list):
            raise HTTPError(400, "consent must be an object with a list of field names.")
        fields = []
        for f in raw.get("fields", []):
            if f not in PROFILE_KEYS:
                raise HTTPError(400, f"Unknown background field in consent: {str(f)[:40]}.")
            if f not in fields:
                fields.append(f)
    kept = {k: v for k, v in profile.items() if k in fields}
    return kept, {"fields": [f for f in PROFILE_KEYS if f in kept], "evidence": True, "recorded_at": now(),
                  "version": CONSENT_VERSION, "explicit": raw is not None}


def clean_evidence(ev):
    if not isinstance(ev, list) or not ev:
        raise HTTPError(400, "Select at least one piece of evidence to share.")
    if len(ev) > MAX_EVIDENCE:
        raise HTTPError(400, f"At most {MAX_EVIDENCE} pieces of evidence per request.")
    for e in ev:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not e["id"]:
            raise HTTPError(400, "Each evidence snapshot must be an object with a text id.")
        if "age_terms" in e and not isinstance(e["age_terms"], list):
            raise HTTPError(400, "evidence.age_terms must be a list.")
        if len(jdumps(e)) > MAX_EVIDENCE_BYTES:
            raise HTTPError(413, "One evidence item is too large to submit.")
    return ev


def make_code(conn, year):
    prefix = f"AL-{year}-"
    row = conn.execute("SELECT MAX(CAST(SUBSTR(code, ?) AS INTEGER)) FROM requests WHERE code LIKE ?",
                       (len(prefix) + 1, prefix + "%")).fetchone()
    return f"{prefix}{(row[0] or 0) + 1:04d}"


# --- seeker handlers --------------------------------------------------------------------------

def create(req):
    if not create_limiter.check("create"):
        raise HTTPError(429, TOO_MANY)
    size_guard(req, MAX_CREATE_BODY)
    data = req.json()
    question = text_field(data, "question", MAX_QUESTION, label="Question")
    profile = clean_profile(data.get("profile"))
    profile, consent = clean_consent(data.get("consent"), profile)
    evidence = clean_evidence(data.get("evidence"))
    scope = data.get("scope")
    if scope is not None and not isinstance(scope, dict):
        raise HTTPError(400, "scope must be an object.")
    ev_json, prof_json, scope_json = jdumps(evidence), jdumps(profile), jdumps(scope) if scope is not None else None
    if len(ev_json) + len(scope_json or "") > MAX_SNAPSHOT_BYTES:
        raise HTTPError(413, "Evidence snapshot is too large.")
    is_demo = 1 if any(isinstance(e, dict) and e.get("is_demo") for e in evidence) else 0
    idem = req.headers.get("X-Idempotency-Key", "")
    if idem and not IDEM_RX.match(idem):
        raise HTTPError(400, "X-Idempotency-Key must be 8-128 letters, digits or . _ : -")
    idem_hash = hash_token(idem) if idem else None
    content_hash = hashlib.sha256(jdumps([question, profile, sorted(str(e["id"]) for e in evidence)]).encode()).hexdigest()
    token = new_owner_token()
    ts = now()
    for _ in range(8):  # race-safe: UNIQUE(code) + retry on collision
        conn = db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if idem_hash:
                hit = conn.execute("SELECT m.content_hash, r.code, r.status, r.created_at FROM request_meta m JOIN requests r ON r.id=m.request_id"
                                   " WHERE m.idem_hash=?", (idem_hash,)).fetchone()
                if hit:
                    base = {"code": hit["code"], "duplicate": True, "status": hit["status"], "created_at": hit["created_at"]}
                    if hit["content_hash"] != content_hash:
                        return 409, {**base, "error": "That submission key was already used for a different request."}
                    return 200, {**base, "token": None, "message": "This request was already received; no second copy was created. "
                                 "Open it from My requests in the browser where you submitted it."}
            since = datetime.fromtimestamp(time.time() - DUP_WINDOW_S, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            dup = conn.execute("SELECT r.code, r.status, r.created_at FROM request_meta m JOIN requests r ON r.id=m.request_id"
                               " WHERE m.content_hash=? AND r.created_at>=? ORDER BY r.id DESC LIMIT 1", (content_hash, since)).fetchone()
            if dup:
                return 409, {"error": "An identical request was submitted a few seconds ago, so this copy was not created. "
                             "Check My requests; if you really meant to send another, change the question and submit again.",
                             "code": dup["code"], "duplicate": True, "status": dup["status"], "created_at": dup["created_at"]}
            code = make_code(conn, ts[:4])
            cur = conn.execute(
                "INSERT INTO requests(code,owner_token_hash,status,question,profile_json,evidence_json,scope_json,is_demo,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (code, hash_token(token), "pending", question, prof_json, ev_json, scope_json, is_demo, ts, ts))
            add_message(conn, cur.lastrowid, "seeker", "question", question, True, ts=ts)
            conn.execute("INSERT INTO request_meta(request_id,consent_json,idem_hash,content_hash) VALUES(?,?,?,?)",
                         (cur.lastrowid, jdumps(consent), idem_hash, content_hash))
            add_event(conn, cur.lastrowid, "created", "seeker", None, "pending", ts)
            from . import api_access  # public demo with a personal invite code: keep the request on the code as well
            kept = api_access.link_request(conn, req, cur.lastrowid)
            conn.commit()
            return 201, {"code": code, "token": token, "status": "pending", "created_at": ts, "duplicate": False, "on_invite": kept}
        except sqlite3.IntegrityError:
            conn.rollback()
        finally:
            conn.close()
    raise HTTPError(503, "Could not allocate a request number; please retry.")


def parse_tokens(header):
    out = {}
    for part in (header or "").split(","):
        code, sep, tok = part.strip().partition("=")
        if sep and code and tok:
            out[code] = tok
    return out


def mine(req):
    tokens = parse_tokens(req.headers.get("X-Owner-Tokens", ""))
    wanted = [c for c in req.query.get("codes", "").split(",") if c] or list(tokens)
    items, invalid = [], []
    with db.connect() as conn:
        for code in wanted[:100]:
            try:
                items.append(summary_out(owned(conn, code, tokens.get(code, ""))))
            except HTTPError:
                invalid.append(code)
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {"requests": items, "unavailable": invalid}


def seeker_get(req):
    with db.connect() as conn:
        r = seeker_row(conn, req, req.params["code"])
        return request_out(r, load_messages(conn, r["id"], True), reviewer=False, conn=conn)


def seeker_answer(req):
    if not req.headers.get("X-Owner-Token") and not req.headers.get("Authorization"):
        raise HTTPError(401, "Missing owner token.")  # Authorization: a personal invite session (public demo)
    if not answer_limiter.check("answer"):
        raise HTTPError(429, TOO_MANY)
    size_guard(req, MAX_ACTION_BODY)
    body = text_field(req.json(), "body", MAX_TEXT, label="Answer")
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        r = seeker_row(conn, req, req.params["code"])
        if r["status"] != "needs_info":
            raise HTTPError(409, "This request is not waiting for more information.")
        ts = now()
        add_message(conn, r["id"], "seeker", "answer", body, True, ts=ts)
        set_status(conn, r["id"], "pending", ts)
        add_event(conn, r["id"], "answered", "seeker", "needs_info", "pending", ts)
        conn.commit()
        return {"code": r["code"], "status": "pending", "updated_at": ts}


# --- reviewer handlers ------------------------------------------------------------------------

def guard(req):
    """Reviewer token check with a small failed-attempt limiter (429 after repeated bad tokens)."""
    try:
        require_reviewer(req)
    except HTTPError:
        if req.headers.get("X-Reviewer-Token") and not bad_token_limiter.check("bad"):
            raise HTTPError(429, "Too many wrong reviewer tokens. Wait a minute before trying again.")
        raise HTTPError(401, "Reviewer sign-in needed: the token is missing, wrong or no longer valid. Sign in again.")


def page_params(req):
    def num(name, default, lo, hi):
        try:
            return max(lo, min(hi, int(req.query.get(name, default))))
        except (TypeError, ValueError):
            raise HTTPError(400, f"{name} must be a whole number.")
    return num("limit", PAGE_DEFAULT, 1, PAGE_MAX), num("offset", 0, 0, 10 ** 9)


def rv_list(req):
    guard(req)
    status = req.query.get("status", "")
    if status and status not in STATUSES:
        raise HTTPError(400, "status must be one of: " + ", ".join(STATUSES))
    limit, offset = page_params(req)
    with db.connect() as conn:
        counts = {s: 0 for s in STATUSES}
        for row in conn.execute("SELECT status, COUNT(*) n FROM requests GROUP BY status"):
            counts[row["status"]] = row["n"]
        sql = "SELECT * FROM requests" + (" WHERE status=?" if status else "") + " ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?"
        rows = conn.execute(sql, ((status,) if status else ()) + (limit, offset)).fetchall()
    matching = counts[status] if status else sum(counts.values())
    return {"requests": [summary_out(r) for r in rows], "counts": counts, "total": sum(counts.values()), "matching": matching,
            "limit": limit, "offset": offset, "has_more": offset + len(rows) < matching}


def rv_get(req):
    guard(req)
    with db.connect() as conn:
        r = reviewer_row(conn, req.params["code"])
        return request_out(r, load_messages(conn, r["id"], False), reviewer=True, conn=conn)


def rv_action(fn):
    def handler(req):
        guard(req)
        size_guard(req, MAX_ACTION_BODY)
        data = req.json()
        with db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            r = reviewer_row(conn, req.params["code"])
            out = fn(conn, r, data)
            conn.commit()
            return out
    return handler


def need_status(r, allowed, what):
    if r["status"] not in allowed:
        raise HTTPError(409, f"Cannot {what} while the request is '{r['status']}'.")


def do_info(conn, r, data):
    body = text_field(data, "body", MAX_TEXT, label="Information request")
    need_status(r, ("pending", "needs_info"), "request more information")
    ts = now()
    add_message(conn, r["id"], "reviewer", "info_request", body, True, ts=ts)
    set_status(conn, r["id"], "needs_info", ts)
    add_event(conn, r["id"], "info_requested", "reviewer", r["status"], "needs_info", ts)
    return {"code": r["code"], "status": "needs_info", "updated_at": ts}


def reply_fields(data, final):
    body = text_field(data, "body", MAX_TEXT, required=final, label="Reply summary")
    facts = list_field(data, "facts", required=final)
    verify = list_field(data, "to_verify", required=False)
    rewrite = text_field(data, "rewrite_suggestion", MAX_TEXT, required=False, label="Rewrite suggestion")
    return body, facts, {"items": verify, "rewrite": rewrite}


def do_draft(conn, r, data):
    need_status(r, ("pending", "needs_info"), "save a draft")
    body, facts, verify = reply_fields(data, final=False)
    ts = now()
    d = conn.execute("SELECT id FROM messages WHERE request_id=? AND kind='draft' AND published=0", (r["id"],)).fetchone()
    if d:
        conn.execute("UPDATE messages SET body=?,facts_json=?,to_verify_json=?,created_at=? WHERE id=?",
                     (body, jdumps(facts), jdumps(verify), ts, d["id"]))
    else:
        add_message(conn, r["id"], "reviewer", "draft", body, False, facts, verify, ts)
    conn.execute("UPDATE requests SET updated_at=? WHERE id=?", (ts, r["id"]))
    add_event(conn, r["id"], "draft_saved", "reviewer", r["status"], r["status"], ts)
    return {"code": r["code"], "status": r["status"], "draft_saved_at": ts}


def do_publish(conn, r, data):
    need_status(r, ("pending", "needs_info"), "publish a reply")
    body, facts, verify = reply_fields(data, final=True)
    ts = now()
    conn.execute("DELETE FROM messages WHERE request_id=? AND kind='draft' AND published=0", (r["id"],))
    add_message(conn, r["id"], "reviewer", "reply", body, True, facts, verify, ts)
    set_status(conn, r["id"], "replied", ts, published_at=ts)
    add_event(conn, r["id"], "published", "reviewer", r["status"], "replied", ts)
    return {"code": r["code"], "status": "replied", "published_at": ts}


def do_close(conn, r, data):
    need_status(r, ("pending", "needs_info", "replied"), "close")
    ts = now()
    set_status(conn, r["id"], "closed", ts, closed_at=ts)
    add_event(conn, r["id"], "closed", "reviewer", r["status"], "closed", ts)
    return {"code": r["code"], "status": "closed", "closed_at": ts}


META_SQL = """
CREATE TABLE IF NOT EXISTS request_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id INTEGER NOT NULL REFERENCES requests(id),
  event TEXT NOT NULL, actor TEXT NOT NULL,        -- actor: seeker | reviewer (role only, never a name)
  from_status TEXT, to_status TEXT,
  created_at TEXT NOT NULL                          -- no body text is ever stored here
);
CREATE INDEX IF NOT EXISTS ix_evt_req ON request_events(request_id);
CREATE TABLE IF NOT EXISTS request_meta (
  request_id INTEGER PRIMARY KEY REFERENCES requests(id),
  consent_json TEXT, idem_hash TEXT, content_hash TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_meta_idem ON request_meta(idem_hash) WHERE idem_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_meta_content ON request_meta(content_hash);
"""


def ensure_tables():
    conn = db.connect()
    try:
        conn.executescript(META_SQL)
        # requests created before this table existed get a 'created' event so the timeline is never empty
        conn.execute("INSERT INTO request_events(request_id,event,actor,from_status,to_status,created_at)"
                     " SELECT id,'created','seeker',NULL,'pending',created_at FROM requests"
                     " WHERE id NOT IN (SELECT request_id FROM request_events)")
        conn.commit()
    finally:
        conn.close()


def register(router):
    ensure_tables()
    router.add("POST", "/api/requests", create)
    router.add("GET", "/api/requests/mine", mine)
    router.add("GET", "/api/requests/<code>", seeker_get)
    router.add("POST", "/api/requests/<code>/answer", seeker_answer)
    router.add("GET", "/api/reviewer/requests", rv_list)
    router.add("GET", "/api/reviewer/requests/<code>", rv_get)
    router.add("POST", "/api/reviewer/requests/<code>/info-request", rv_action(do_info))
    router.add("POST", "/api/reviewer/requests/<code>/draft", rv_action(do_draft))
    router.add("POST", "/api/reviewer/requests/<code>/publish", rv_action(do_publish))
    router.add("POST", "/api/reviewer/requests/<code>/close", rv_action(do_close))
