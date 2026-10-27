"""Tests for the human-review loop. Uses a temp DB and a real HTTP server on an ephemeral port."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

_tmp = tempfile.mkdtemp()
os.environ["AGELENS_DB"] = os.path.join(_tmp, "t.db")
os.environ["AGELENS_REVIEWER_TOKEN"] = "test-reviewer-token"

from http.server import ThreadingHTTPServer  # noqa: E402
import itertools  # noqa: E402
from backend import db, server, api_requests as AR  # noqa: E402

_n = itertools.count(1)

RV = {"X-Reviewer-Token": "test-reviewer-token"}
EVIDENCE = [{"id": "ad_abc123", "title": "运营经理", "description": "要求35岁以下，条件优秀者可放宽。", "is_demo": True,
             "age_terms": [{"kind": "max", "max_age": 35, "snippet": "35岁以下", "start_offset": 2, "end_offset": 7}]}]
SECRET_DRAFT = "DRAFT-SECRET-zebra-91"


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_schema()
        server.load_routes()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        for lim in (AR.create_limiter, AR.answer_limiter, AR.bad_token_limiter):
            lim.reset()

    def call(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.base + path, data=data, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(r) as resp:
                raw = resp.read().decode()
                return resp.status, json.loads(raw), raw
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            return e.code, json.loads(raw), raw

    def create(self, question=None, **extra):
        question = question or f"Is 'under 35' a hard limit? #{next(_n)}"
        s, b, _ = self.call("POST", "/api/requests", {"question": question, "profile": {"age": 38, "occupation": "ops", "phone": "139"},
                                                       "evidence": EVIDENCE, "scope": {"count": 1}, **extra})
        self.assertEqual(s, 201, b)
        return b["code"], {"X-Owner-Token": b["token"]}, b


class TestCreate(Base):
    def test_create_and_token_hashed(self):
        code, h, b = self.create()
        self.assertRegex(code, r"^AL-\d{4}-\d{4}$")
        self.assertEqual(b["status"], "pending")
        with db.connect() as c:
            r = c.execute("SELECT * FROM requests WHERE code=?", (code,)).fetchone()
        self.assertNotIn(b["token"], json.dumps(dict(r)))
        self.assertEqual(r["owner_token_hash"], server.hash_token(b["token"]))
        self.assertNotIn("phone", json.loads(r["profile_json"]))  # non-shared field dropped
        self.assertEqual(json.loads(r["evidence_json"]), EVIDENCE)  # verbatim

    def test_codes_unique_under_concurrency(self):
        codes, lock = [], threading.Lock()

        def go():
            c, _, _ = self.create()
            with lock:
                codes.append(c)
        ts = [threading.Thread(target=go) for _ in range(12)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(len(codes), 12)
        self.assertEqual(len(set(codes)), 12)

    def test_validation(self):
        bad = [{"question": "", "evidence": EVIDENCE}, {"question": "x" * 5000, "evidence": EVIDENCE},
               {"question": 5, "evidence": EVIDENCE}, {"question": "q", "evidence": []}, {"question": "q", "evidence": "x"},
               {"question": "q", "evidence": [{"no": "id"}]}, {"question": "q", "evidence": EVIDENCE, "profile": "x"},
               {"question": "q", "evidence": EVIDENCE, "scope": []}]
        for body in bad:
            s, b, _ = self.call("POST", "/api/requests", body)
            self.assertEqual(s, 400, body)
            self.assertIn("error", b)
        s, _, _ = self.call("POST", "/api/requests", None)
        self.assertEqual(s, 400)


class TestIsolation(Base):
    def test_reviewer_endpoints_require_token(self):
        code, _, _ = self.create()
        eps = [("GET", "/api/reviewer/requests"), ("GET", f"/api/reviewer/requests/{code}")] + [
            ("POST", f"/api/reviewer/requests/{code}/{a}") for a in ("info-request", "draft", "publish", "close")]
        for m, p in eps:
            for hdr in ({}, {"X-Reviewer-Token": "wrong"}):
                s, b, _ = self.call(m, p, {"body": "x"} if m == "POST" else None, hdr)
                self.assertEqual(s, 401, (m, p))

    def test_owner_token_does_not_grant_reviewer(self):
        code, h, b = self.create()
        s, _, _ = self.call("GET", "/api/reviewer/requests", None, {"X-Reviewer-Token": b["token"]})
        self.assertEqual(s, 401)

    def test_seeker_cannot_read_others(self):
        c1, h1, _ = self.create("first question")
        c2, h2, _ = self.create("second question")
        self.assertEqual(self.call("GET", f"/api/requests/{c1}", None, h1)[0], 200)
        self.assertEqual(self.call("GET", f"/api/requests/{c1}", None, h2)[0], 404)
        self.assertEqual(self.call("GET", f"/api/requests/{c1}")[0], 401)
        self.assertEqual(self.call("GET", "/api/requests/AL-1999-0001", None, h1)[0], 404)
        self.assertEqual(self.call("POST", f"/api/requests/{c1}/answer", {"body": "hi"}, h2)[0], 404)
        # mine: only verified codes are returned
        hdr = {"X-Owner-Tokens": f"{c1}={h1['X-Owner-Token']},{c2}=bogus"}
        s, b, raw = self.call("GET", f"/api/requests/mine?codes={c1},{c2}", None, hdr)
        self.assertEqual([r["code"] for r in b["requests"]], [c1])
        self.assertEqual(b["unavailable"], [c2])
        self.assertNotIn("second question", raw)

    def test_full_loop_and_draft_never_leaks(self):
        code, h, _ = self.create()
        rv = lambda p, body=None, m="POST": self.call(m, f"/api/reviewer/requests/{code}{p}", body, RV)  # noqa: E731
        # answer before info request is a state error
        self.assertEqual(self.call("POST", f"/api/requests/{code}/answer", {"body": "x"}, h)[0], 409)
        # info request
        s, b, _ = rv("/info-request", {"body": "Which city?"})
        self.assertEqual((s, b["status"]), (200, "needs_info"))
        s, b, _ = self.call("GET", f"/api/requests/{code}", None, h)
        self.assertEqual(b["status"], "needs_info")
        self.assertIn("info_request", [m["kind"] for m in b["messages"]])
        # seeker answers -> pending
        s, b, _ = self.call("POST", f"/api/requests/{code}/answer", {"body": "Shanghai"}, h)
        self.assertEqual((s, b["status"]), (200, "pending"))
        self.assertEqual(self.call("POST", f"/api/requests/{code}/answer", {"body": "again"}, h)[0], 409)
        # draft: persisted for reviewer, absent for seeker
        s, b, _ = rv("/draft", {"body": SECRET_DRAFT, "facts": ["f1"], "to_verify": ["v1"], "rewrite_suggestion": "neutral"})
        self.assertEqual(s, 200)
        rv("/draft", {"body": SECRET_DRAFT + " v2", "facts": ["f1"]})  # overwrite, still single draft
        s, d, _ = rv("", None, "GET")
        drafts = [m for m in d["messages"] if m["kind"] == "draft"]
        self.assertEqual(len(drafts), 1)
        self.assertIn(SECRET_DRAFT, drafts[0]["body"])
        s, seeker, raw = self.call("GET", f"/api/requests/{code}", None, h)
        self.assertNotIn("zebra", raw)
        self.assertNotIn("draft", [m["kind"] for m in seeker["messages"]])
        s, _, raw = self.call("GET", f"/api/requests/mine", None, {"X-Owner-Tokens": f"{code}={h['X-Owner-Token']}"})
        self.assertNotIn("zebra", raw)
        # publish needs facts
        self.assertEqual(rv("/publish", {"body": "r", "facts": []})[0], 400)
        self.assertEqual(rv("/publish", {"body": "r", "facts": "x"})[0], 400)
        s, b, _ = rv("/publish", {"body": "Reply summary", "facts": ["The ad says 35岁以下."], "to_verify": ["Whether exceptions apply"],
                                  "rewrite_suggestion": "Neutral wording"})
        self.assertEqual((s, b["status"]), (200, "replied"))
        self.assertTrue(b["published_at"])
        s, seeker, raw = self.call("GET", f"/api/requests/{code}", None, h)
        reply = [m for m in seeker["messages"] if m["kind"] == "reply"][0]
        self.assertEqual(reply["facts"], ["The ad says 35岁以下."])
        self.assertEqual(reply["to_verify"], ["Whether exceptions apply"])
        self.assertEqual(reply["rewrite_suggestion"], "Neutral wording")
        self.assertNotIn("zebra", raw)  # published reply replaced the draft entirely
        self.assertEqual(seeker["published_at"], b["published_at"])
        # no second publish / draft after replied; close works once
        self.assertEqual(rv("/publish", {"body": "r", "facts": ["f"]})[0], 409)
        self.assertEqual(rv("/draft", {"body": "x"})[0], 409)
        s, b, _ = rv("/close", {})
        self.assertEqual((s, b["status"]), (200, "closed"))
        self.assertTrue(b["closed_at"])
        self.assertEqual(rv("/close", {})[0], 409)
        self.assertEqual(rv("/info-request", {"body": "x"})[0], 409)
        self.assertEqual(self.call("GET", f"/api/requests/{code}", None, h)[1]["closed_at"], b["closed_at"])

    def test_seeker_json_never_contains_draft_text_while_pending(self):
        code, h, _ = self.create()
        self.call("POST", f"/api/reviewer/requests/{code}/draft", {"body": SECRET_DRAFT, "facts": [SECRET_DRAFT], "to_verify": [SECRET_DRAFT],
                                                                    "rewrite_suggestion": SECRET_DRAFT}, RV)
        for path, hdr in ((f"/api/requests/{code}", h), ("/api/requests/mine", {"X-Owner-Tokens": f"{code}={h['X-Owner-Token']}"})):
            self.assertNotIn("zebra", self.call("GET", path, None, hdr)[2])
        self.assertIn("zebra", self.call("GET", f"/api/reviewer/requests/{code}", None, RV)[2])


class TestReviewerList(Base):
    def test_counts_and_filter(self):
        code, _, _ = self.create("list test")
        self.call("POST", f"/api/reviewer/requests/{code}/info-request", {"body": "more?"}, RV)
        s, b, _ = self.call("GET", "/api/reviewer/requests", None, RV)
        self.assertEqual(sum(b["counts"].values()), b["total"])
        self.assertGreaterEqual(b["counts"]["needs_info"], 1)
        s, f, _ = self.call("GET", "/api/reviewer/requests?status=needs_info", None, RV)
        self.assertTrue(f["requests"] and all(r["status"] == "needs_info" for r in f["requests"]))
        self.assertEqual(f["counts"], b["counts"])
        self.assertEqual(self.call("GET", "/api/reviewer/requests?status=bogus", None, RV)[0], 400)
        self.assertEqual(self.call("GET", "/api/reviewer/requests/AL-1999-9999", None, RV)[0], 404)

    def test_input_validation(self):
        code, _, _ = self.create()
        p = f"/api/reviewer/requests/{code}"
        self.assertEqual(self.call("POST", p + "/info-request", {"body": ""}, RV)[0], 400)
        self.assertEqual(self.call("POST", p + "/info-request", {"body": "x" * 9000}, RV)[0], 400)
        self.assertEqual(self.call("POST", p + "/draft", {"body": "x", "facts": [1]}, RV)[0], 400)
        self.assertEqual(self.call("POST", p + "/draft", {"body": "x", "to_verify": {"a": 1}}, RV)[0], 400)

    def test_snapshots_immutable_through_loop(self):
        code, h, _ = self.create()
        with db.connect() as c:
            before = tuple(c.execute("SELECT profile_json,evidence_json,scope_json,question FROM requests WHERE code=?", (code,)).fetchone())
        p = f"/api/reviewer/requests/{code}"
        self.call("POST", p + "/info-request", {"body": "q"}, RV)
        self.call("POST", f"/api/requests/{code}/answer", {"body": "a"}, h)
        self.call("POST", p + "/publish", {"body": "r", "facts": ["f"]}, RV)
        self.call("POST", p + "/close", {}, RV)
        with db.connect() as c:
            after = tuple(c.execute("SELECT profile_json,evidence_json,scope_json,question FROM requests WHERE code=?", (code,)).fetchone())
        self.assertEqual(before, after)


class TestHardening(Base):
    def post(self, body, hdr=None):
        return self.call("POST", "/api/requests", body, hdr)

    def payload(self, q, **extra):
        return {"question": q, "profile": {"age": 38, "occupation": "ops"}, "evidence": EVIDENCE, **extra}

    def test_idempotency_key_same_content_returns_original(self):
        k = {"X-Idempotency-Key": "key-" + str(next(_n)) + "-abcdefgh"}
        s1, b1, _ = self.post(self.payload("idem question one"), k)
        self.assertEqual((s1, b1["duplicate"]), (201, False))
        s2, b2, _ = self.post(self.payload("idem question one"), k)
        self.assertEqual(s2, 200)
        self.assertTrue(b2["duplicate"])
        self.assertEqual(b2["code"], b1["code"])
        self.assertIsNone(b2["token"])  # tokens are never recoverable
        with db.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM requests WHERE question='idem question one'").fetchone()[0], 1)
            self.assertNotIn("key-", json.dumps([dict(r) for r in c.execute("SELECT * FROM request_meta")]))  # key stored hashed

    def test_idempotency_key_different_content_conflicts(self):
        k = {"X-Idempotency-Key": "key-" + str(next(_n)) + "-zzzzzzzz"}
        s1, b1, _ = self.post(self.payload("first content"), k)
        s2, b2, _ = self.post(self.payload("other content"), k)
        self.assertEqual((s1, s2), (201, 409))
        self.assertTrue(b2["duplicate"])
        self.assertEqual(b2["code"], b1["code"])
        self.assertIn("error", b2)
        self.assertEqual(self.post(self.payload("x"), {"X-Idempotency-Key": "short"})[0], 400)

    def test_identical_content_window_blocks_double_submit(self):
        q = f"double click {next(_n)}"
        s1, b1, _ = self.post(self.payload(q))
        s2, b2, _ = self.post(self.payload(q))
        self.assertEqual((s1, s2), (201, 409))
        self.assertTrue(b2["duplicate"])
        self.assertEqual(b2["code"], b1["code"])
        self.assertEqual(self.post(self.payload(q + " (edited)"))[0], 201)  # different content is fine
        old = AR.DUP_WINDOW_S
        AR.DUP_WINDOW_S = -5   # window elapsed
        try:
            self.assertEqual(self.post(self.payload(q))[0], 201)
        finally:
            AR.DUP_WINDOW_S = old

    def test_concurrent_same_key_creates_one_row(self):
        k = {"X-Idempotency-Key": "conc-" + str(next(_n)) + "-abcdefgh"}
        out, lock = [], threading.Lock()

        def go():
            r = self.post(self.payload("concurrent idem"), k)
            with lock:
                out.append(r[0])
        ts = [threading.Thread(target=go) for _ in range(6)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(out.count(201), 1)
        self.assertTrue(all(c in (200, 201, 409) for c in out))
        with db.connect() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM requests WHERE question='concurrent idem'").fetchone()[0], 1)

    def test_consent_recorded_and_enforced(self):
        body = self.payload(f"consent q {next(_n)}", consent={"fields": ["occupation"]})
        body["profile"] = {"age": 38, "occupation": "ops", "region": "Shanghai"}
        s, b, _ = self.post(body)
        self.assertEqual(s, 201)
        _, rv, _ = self.call("GET", f"/api/reviewer/requests/{b['code']}", None, RV)
        self.assertEqual(rv["profile"], {"occupation": "ops"})  # non-consented fields are dropped server-side
        self.assertEqual(rv["consent"]["fields"], ["occupation"])
        self.assertTrue(rv["consent"]["recorded_at"])
        _, sk, _ = self.call("GET", f"/api/requests/{b['code']}", None, {"X-Owner-Token": b["token"]})
        self.assertEqual(sk["consent"]["fields"], ["occupation"])
        self.assertEqual(self.post(self.payload("bad consent", consent={"fields": ["phone"]}))[0], 400)
        self.assertEqual(self.post(self.payload("bad consent 2", consent="all"))[0], 400)
        # no consent object: the fields actually sent are recorded
        code, h, _ = self.create()
        _, rv, _ = self.call("GET", f"/api/reviewer/requests/{code}", None, RV)
        self.assertEqual(rv["consent"]["fields"], ["age", "occupation"])

    def test_event_history_and_draft_event_hidden_from_seeker(self):
        code, h, _ = self.create()
        p = f"/api/reviewer/requests/{code}"
        self.call("POST", p + "/info-request", {"body": "BODYTEXT-info"}, RV)
        self.call("POST", f"/api/requests/{code}/answer", {"body": "BODYTEXT-ans"}, h)
        self.call("POST", p + "/draft", {"body": "BODYTEXT-draft"}, RV)
        self.call("POST", p + "/publish", {"body": "BODYTEXT-reply", "facts": ["f"]}, RV)
        self.call("POST", p + "/close", {}, RV)
        _, rv, _ = self.call("GET", p, None, RV)
        self.assertEqual([e["event"] for e in rv["events"]], ["created", "info_requested", "answered", "draft_saved", "published", "closed"])
        self.assertEqual([e["to_status"] for e in rv["events"]], ["pending", "needs_info", "pending", "pending", "replied", "closed"])
        _, sk, raw = self.call("GET", f"/api/requests/{code}", None, h)
        self.assertEqual([e["event"] for e in sk["events"]], ["created", "info_requested", "answered", "published", "closed"])
        with db.connect() as c:
            dump = json.dumps([dict(r) for r in c.execute("SELECT * FROM request_events")])
        self.assertNotIn("BODYTEXT", dump)  # history holds no body text
        self.assertTrue(all(set(e) == {"event", "actor", "from_status", "to_status", "at"} for e in rv["events"]))

    def test_pagination(self):
        for _ in range(7):
            self.create()
        _, a, _ = self.call("GET", "/api/reviewer/requests?limit=3", None, RV)
        self.assertEqual((len(a["requests"]), a["limit"], a["offset"]), (3, 3, 0))
        self.assertTrue(a["has_more"])
        _, b, _ = self.call("GET", "/api/reviewer/requests?limit=3&offset=3", None, RV)
        self.assertFalse({r["code"] for r in a["requests"]} & {r["code"] for r in b["requests"]})
        _, z, _ = self.call("GET", f"/api/reviewer/requests?limit=100&offset={a['total']}", None, RV)
        self.assertEqual((z["requests"], z["has_more"]), ([], False))
        _, p, _ = self.call("GET", "/api/reviewer/requests?status=pending&limit=2", None, RV)
        self.assertEqual(p["matching"], p["counts"]["pending"])
        self.assertEqual(self.call("GET", "/api/reviewer/requests?limit=abc", None, RV)[0], 400)
        self.assertEqual(self.call("GET", "/api/reviewer/requests?limit=100000", None, RV)[1]["limit"], AR.PAGE_MAX)

    def test_size_and_count_limits(self):
        big = self.payload("big body")
        big["evidence"] = [{"id": "ad_big", "description": "x" * (AR.MAX_CREATE_BODY + 10)}]
        s, b, _ = self.post(big)
        self.assertEqual(s, 413)
        self.assertIn("too large", b["error"].lower())
        many = self.payload("many ev")
        many["evidence"] = [{"id": f"ad_{i}"} for i in range(AR.MAX_EVIDENCE + 1)]
        self.assertEqual(self.post(many)[0], 400)
        one = self.payload("one huge ev")
        one["evidence"] = [{"id": "ad_x", "description": "y" * (AR.MAX_EVIDENCE_BYTES + 5)}]
        self.assertEqual(self.post(one)[0], 413)
        code, h, _ = self.create()
        s, _, _ = self.call("POST", f"/api/reviewer/requests/{code}/info-request", {"body": "z" * (AR.MAX_ACTION_BODY + 10)}, RV)
        self.assertEqual(s, 413)
        long_item = self.call("POST", f"/api/reviewer/requests/{code}/draft", {"body": "x", "facts": ["a" * 1001]}, RV)
        self.assertEqual(long_item[0], 400)

    def test_rate_limits_429(self):
        old = AR.create_limiter.limit
        AR.create_limiter.limit = 3
        try:
            codes = [self.post(self.payload(f"rate {next(_n)}"))[0] for _ in range(5)]
        finally:
            AR.create_limiter.limit = old
        self.assertEqual(codes, [201, 201, 201, 429, 429])
        for _ in range(10):
            self.assertEqual(self.call("GET", "/api/reviewer/requests", None, {"X-Reviewer-Token": "nope"})[0], 401)
        self.assertEqual(self.call("GET", "/api/reviewer/requests", None, RV)[0], 200)  # the right token still works
        s, b, _ = self.call("GET", "/api/reviewer/requests", None, {"X-Reviewer-Token": "nope"})
        self.assertEqual(s, 429)
        self.assertIn("wait", b["error"].lower())

    def test_error_messages_are_human_readable(self):
        s, b, _ = self.call("GET", "/api/reviewer/requests")
        self.assertEqual(s, 401)
        self.assertIn("Sign in", b["error"])
        code, h, _ = self.create()
        s, b, _ = self.call("GET", f"/api/requests/{code}", None, {"X-Owner-Token": "wrong"})
        self.assertEqual((s, b["error"]), (404, "Request not found for this browser."))
        s, b, _ = self.call("POST", f"/api/requests/{code}/answer", {"body": "x"}, h)
        self.assertEqual(s, 409)
        self.assertIn("not waiting", b["error"])


if __name__ == "__main__":
    unittest.main()
