"""Tiny stdlib HTTP server: JSON routes + static frontend. Bound to 127.0.0.1 only.

Route modules: any backend/api_*.py exposing `register(router)` is loaded automatically.
Handlers take a Request and return a dict/list (200), (status, obj), or a Response.
Logging never includes query strings or bodies.
"""
import hashlib
import importlib
import json
import mimetypes
import os
import pkgutil
import re
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import db

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
MAX_BODY = 12 * 1024 * 1024
PUBLIC = os.environ.get("AGELENS_PUBLIC") == "1"  # read once for headers; request checks read the environment each time


class HTTPError(Exception):
    def __init__(self, status, message, extra=None):
        super().__init__(message)
        self.status, self.message, self.extra = status, message, extra or {}


class Response:
    def __init__(self, body=b"", status=200, content_type="application/octet-stream", headers=None):
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.status, self.content_type, self.headers = status, content_type, headers or {}


class Request:
    def __init__(self, method, path, query, headers, body, params):
        self.method, self.path, self.headers, self.body, self.params = method, path, headers, body, params
        self.query = {k: v[0] for k, v in query.items()}

    def json(self):
        try:
            data = json.loads(self.body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            raise HTTPError(400, "Request body must be valid JSON.")
        if not isinstance(data, dict):
            raise HTTPError(400, "Request body must be a JSON object.")
        return data

    def int_query(self, name, default, lo=1, hi=1000):
        try:
            return max(lo, min(hi, int(self.query.get(name, default))))
        except (TypeError, ValueError):
            return default


class Router:
    def __init__(self):
        self.routes = []

    def add(self, method, pattern, fn):
        rx = "^" + re.sub(r"<(\w+)>", r"(?P<\1>[^/]+)", pattern) + "$"
        self.routes.append((method, re.compile(rx), fn))

    def get(self, pattern):
        return lambda fn: (self.add("GET", pattern, fn), fn)[1]

    def post(self, pattern):
        return lambda fn: (self.add("POST", pattern, fn), fn)[1]

    def match(self, method, path):
        path_known = False
        for m, rx, fn in self.routes:
            hit = rx.match(path)
            if hit:
                path_known = True
                if m == method:
                    return fn, {k: unquote(v) for k, v in hit.groupdict().items()}
        return (None, "method") if path_known else (None, "path")


# --- demo-grade access control (server-side; NOT production auth) -------------------------

def reviewer_token():
    env = os.environ.get("AGELENS_REVIEWER_TOKEN")
    if env:
        return env
    if os.environ.get("AGELENS_PUBLIC") == "1":
        raise HTTPError(503, "The reviewer token is not configured on this server.")  # never write a token file on a public host
    f = db.DATA_DIR / "reviewer_token"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_urlsafe(16))
        f.chmod(0o600)
    return f.read_text().strip()


def require_reviewer(req):
    got = req.headers.get("X-Reviewer-Token", "")
    if os.environ.get("AGELENS_PUBLIC") == "1" and not got:
        from . import api_access  # public demo: a reviewer invite code stands in for the shared token
        if api_access.is_reviewer(req):
            return
    if not got or not secrets.compare_digest(got, reviewer_token()):
        raise HTTPError(401, "Reviewer access requires the demo reviewer token.")


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_owner_token():
    return secrets.token_urlsafe(24)


def owner_hash(req):
    tok = req.headers.get("X-Owner-Token", "")
    if not tok:
        raise HTTPError(401, "Missing owner token.")
    return hash_token(tok)


# --- app wiring ---------------------------------------------------------------------------

router = Router()


@router.get("/api/health")
def health(req):
    with db.connect() as c:
        ads = c.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    return {"ok": True, "ads": ads}


@router.post("/api/diag")
def diag(req):
    """Local browser diagnostics (motion/WebGL/frame rate) posted by the page when opened with #/?diag=1.
    Written to data/diag.json for the operator; small, no personal data, overwritten each time. Off on the public demo."""
    if os.environ.get("AGELENS_PUBLIC") == "1":
        raise HTTPError(404, "Not found.")
    if len(req.body) > 8192:
        raise HTTPError(413, "Diagnostics too large.")
    data = req.json()
    (db.DATA_DIR / "diag.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


def load_routes():
    pkg = sys.modules[__package__]
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name.startswith("api_"):
            importlib.import_module(f"{__package__}.{info.name}").register(router)


class Handler(BaseHTTPRequestHandler):
    server_version = "AgeLens"

    def log_message(self, fmt, *args):  # method + path only, no query/body
        sys.stderr.write("%s %s -> %s\n" % (self.command, urlparse(self.path).path, args[1] if len(args) > 1 else ""))

    def _send(self, resp):
        self.send_response(resp.status)
        self.send_header("Content-Type", resp.content_type)
        self.send_header("Content-Length", str(len(resp.body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if PUBLIC:
            self.send_header("X-Robots-Tag", "noindex, nofollow")  # a course demo, not for search engines
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        self.send_header("Cache-Control", "no-store" if resp.content_type.startswith("application/json") else "no-cache")
        for k, v in resp.headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(resp.body)

    def _json(self, status, obj):
        self._send(Response(json.dumps(obj, ensure_ascii=False), status, "application/json; charset=utf-8"))

    def _dispatch(self):
        u = urlparse(self.path)
        try:
            if u.path.startswith("/api/"):
                fn, params = router.match(self.command, u.path)
                if fn is None:
                    raise HTTPError(405 if params == "method" else 404, "Not found.")
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    raise HTTPError(413, "Request body too large.")
                body = self.rfile.read(length) if length else b""
                rq = Request(self.command, u.path, parse_qs(u.query), self.headers, body, params)
                if os.environ.get("AGELENS_PUBLIC") == "1":
                    from . import api_access
                    api_access.gate(rq)  # public demo: every API call needs an invite session (a few open paths aside)
                out = fn(rq)
                if isinstance(out, Response):
                    return self._send(out)
                if isinstance(out, tuple):
                    return self._json(out[0], out[1])
                return self._json(200, out)
            if self.command != "GET":
                raise HTTPError(405, "Method not allowed.")
            return self._static(u.path)
        except HTTPError as e:
            self._json(e.status, dict(e.extra, error=e.message))
        except Exception as e:  # never leak internals or request data
            sys.stderr.write("ERROR %s %s: %s\n" % (self.command, u.path, type(e).__name__))
            self._json(500, {"error": "Internal error."})

    def _static(self, path):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        f = (FRONTEND / rel).resolve()
        if FRONTEND.resolve() not in f.parents or not f.is_file():
            raise HTTPError(404, "Not found.")
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(Response(f.read_bytes(), 200, ctype))

    do_GET = do_POST = do_PUT = do_DELETE = _dispatch


def serve(host="127.0.0.1", port=8765):
    db.init_schema()
    load_routes()
    httpd = ThreadingHTTPServer((host, port), Handler)
    reviewer_token()  # local: make sure the demo reviewer token exists before anyone needs it (public: env only)
    src = "env AGELENS_REVIEWER_TOKEN" if os.environ.get("AGELENS_REVIEWER_TOKEN") else str(db.DATA_DIR / "reviewer_token")
    print(f"AgeLens running at http://{host}:{port}  (Ctrl+C to stop)")
    print(f"Demo reviewer token: {src}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
