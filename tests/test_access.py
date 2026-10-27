"""Public-demo invite access (backend/api_access.py): the gate, codes, roles, personal vs shared codes, revocation, limits.
Temp DB, real HTTP server on an ephemeral port. AGELENS_PUBLIC is switched on per test and off afterwards."""
import hashlib
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

_tmp = tempfile.mkdtemp()
os.environ.setdefault("AGELENS_DB", os.path.join(_tmp, "t.db"))

from http.server import ThreadingHTTPServer  # noqa: E402
from backend import api_access as AX, api_requests as AR, db, server  # noqa: E402

CODES = {"teacher": "AL-TEAC-HER2", "class": "AL-CLAS-S777", "rev": "AL-REVW-ER99", "old": "AL-OLDX-CODE", "once": "AL-ONCE-ONLY"}
H = lambda c: hashlib.sha256(c.upper().encode()).hexdigest()
INVITES = [
    {"id": "inv_t", "role": "viewer", "label": "Teacher", "personal": True, "expires": "2099-12-31", "max_uses": 0, "sha256": H(CODES["teacher"])},
    {"id": "inv_c", "role": "viewer", "label": "Class", "personal": False, "expires": "2099-12-31", "max_uses": 0, "sha256": H(CODES["class"])},
    {"id": "inv_r", "role": "reviewer", "label": "Reviewer A", "personal": True, "expires": "2099-12-31", "max_uses": 0, "sha256": H(CODES["rev"])},
    {"id": "inv_o", "role": "viewer", "label": "Expired", "personal": False, "expires": "2020-01-01", "max_uses": 0, "sha256": H(CODES["old"])},
    {"id": "inv_1", "role": "viewer", "label": "Once", "personal": False, "expires": "2099-12-31", "max_uses": 1, "sha256": H(CODES["once"])},
]
EV = [{"id": "ad_acc001", "title": "采购专员", "description": "年龄35岁以下。", "is_demo": True,
       "age_terms": [{"kind": "max", "max_age": 35, "snippet": "年龄35岁以下", "start_offset": 0, "end_offset": 7}]}]


class Base(unittest.TestCase):
    PUBLIC = True

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
        self._env = {k: os.environ.get(k) for k in ("AGELENS_PUBLIC", "AGELENS_INVITES", "AGELENS_REVIEWER_TOKEN", "AGELENS_STUDY_TOKEN")}
        if self.PUBLIC:
            os.environ.update(AGELENS_PUBLIC="1", AGELENS_INVITES=json.dumps(INVITES),
                              AGELENS_REVIEWER_TOKEN="reviewer-token-for-tests-only", AGELENS_STUDY_TOKEN="study-token-for-tests-only")
        for lim in (AX.fail_by_client, AX.fail_all, AR.create_limiter, AR.answer_limiter, AR.bad_token_limiter):
            lim.reset()
        with db.connect() as c:
            c.execute("DELETE FROM invite_uses")

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def call(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.base + path, data=data, method=method, headers=dict({"Content-Type": "application/json"}, **(headers or {})))
        try:
            with urllib.request.urlopen(r) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if "json" in resp.headers.get("Content-Type", "") else raw.decode()), resp.headers
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw), e.headers
            except ValueError:
                return e.code, raw.decode(), e.headers

    def enter(self, who, xff="10.0.0.1"):
        s, b, _ = self.call("POST", "/api/access/redeem", {"code": CODES[who]}, {"X-Forwarded-For": xff})
        self.assertEqual(s, 200, b)
        return {"Authorization": "Bearer " + b["token"]}, b

    def ask(self, hdr):
        s, b, _ = self.call("POST", "/api/requests", {"question": "Is under 35 a hard cap? %s" + os.urandom(4).hex(), "evidence": EV}, hdr)
        self.assertEqual(s, 201, b)
        return b


class TestGate(Base):
    def test_api_closed_without_code_static_and_health_open(self):
        for path in ("/api/overview", "/api/ads", "/api/stats/provinces", "/api/requests/mine", "/api/study/config", "/api/reviewer/requests"):
            s, b, _ = self.call("GET", path)
            self.assertEqual(s, 401, path)
            self.assertTrue(b.get("invite_required"), path)
        self.assertEqual(self.call("POST", "/api/age/check", {"text": "年龄35岁以下"})[0], 401)
        self.assertEqual(self.call("GET", "/api/health")[0], 200)
        s, html, hd = self.call("GET", "/")
        self.assertEqual(s, 200)
        self.assertIn("<html", html.lower())
        self.assertEqual(hd.get("X-Robots-Tag"), None if not server.PUBLIC else "noindex, nofollow")
        self.assertEqual(self.call("GET", "/api/access/status")[1], {"public": True, "invite": True, "signed_in": False})

    def test_valid_code_opens_the_api(self):
        hdr, b = self.enter("class")
        self.assertEqual((b["role"], b["label"], b["personal"]), ("viewer", "Class", False))
        self.assertEqual(self.call("GET", "/api/overview", headers=hdr)[0], 200)
        st = self.call("GET", "/api/access/status", headers=hdr)[1]
        self.assertTrue(st["signed_in"])
        self.assertEqual(self.call("POST", "/api/age/check", {"text": "年龄35岁以下"}, hdr)[1]["age_class"], "hard_cap")

    def test_code_normalised(self):
        s, b, _ = self.call("POST", "/api/access/redeem", {"code": " al-clas-s777 "})
        self.assertEqual(s, 200, b)

    def test_wrong_expired_and_used_up_codes_look_the_same(self):
        bad = [self.call("POST", "/api/access/redeem", {"code": c})[1] for c in ("AL-NOPE-NOPE", CODES["old"], "x", "")]
        self.enter("once")
        bad.append(self.call("POST", "/api/access/redeem", {"code": CODES["once"]})[1])
        self.assertEqual({json.dumps(b) for b in bad}, {json.dumps({"error": AX.BAD_CODE})})

    def test_failed_codes_limited_per_client(self):
        codes = [self.call("POST", "/api/access/redeem", {"code": "AL-WRON-G%03d" % i}, {"X-Forwarded-For": "10.9.9.9"})[0] for i in range(11)]
        self.assertEqual(codes[:10], [401] * 10)
        self.assertEqual(codes[10], 429)
        self.assertEqual(self.call("POST", "/api/access/redeem", {"code": CODES["class"]}, {"X-Forwarded-For": "10.9.9.9"})[0], 429)
        self.assertEqual(self.call("POST", "/api/access/redeem", {"code": CODES["class"]}, {"X-Forwarded-For": "10.1.1.1"})[0], 200)

    def test_signout_and_revocation(self):
        hdr, _ = self.enter("class")
        self.assertEqual(self.call("POST", "/api/access/signout", {}, hdr)[0], 200)
        self.assertEqual(self.call("GET", "/api/overview", headers=hdr)[0], 401)
        hdr, _ = self.enter("class")
        os.environ["AGELENS_INVITES"] = json.dumps([i for i in INVITES if i["id"] != "inv_c"])  # revoked by removal
        self.assertEqual(self.call("GET", "/api/overview", headers=hdr)[0], 401)

    def test_expired_session_closed(self):
        hdr, b = self.enter("class")
        with db.connect() as c:
            c.execute("UPDATE invite_sessions SET expires_at='2000-01-01T00:00:00Z' WHERE token_hash=?", (server.hash_token(b["token"]),))
        self.assertEqual(self.call("GET", "/api/overview", headers=hdr)[0], 401)

    def test_diag_off_in_public(self):
        hdr, _ = self.enter("class")
        self.assertEqual(self.call("POST", "/api/diag", {"x": 1}, hdr)[0], 404)

    def test_only_hashes_stored(self):
        _, b = self.enter("teacher")
        with db.connect() as c:
            dump = json.dumps([dict(r) for r in c.execute("SELECT * FROM invite_sessions")])
        self.assertNotIn(b["token"], dump)
        self.assertNotIn(CODES["teacher"], dump)


class TestRoles(Base):
    def test_viewer_cannot_review_reviewer_can(self):
        v, _ = self.enter("class")
        self.assertEqual(self.call("GET", "/api/reviewer/requests", headers=v)[0], 401)
        r, _ = self.enter("rev")
        self.assertEqual(self.call("GET", "/api/reviewer/requests", headers=r)[0], 200)
        # the shared reviewer token still works too (with a session to pass the gate)
        self.assertEqual(self.call("GET", "/api/reviewer/requests", headers=dict(v, **{"X-Reviewer-Token": "reviewer-token-for-tests-only"}))[0], 200)

    def test_study_desk_needs_the_study_token_as_well(self):
        r, _ = self.enter("rev")
        self.assertEqual(self.call("GET", "/api/study/rater/status", headers=r)[0], 401)
        self.assertEqual(self.call("GET", "/api/study/config", headers=r)[0], 200)


class TestPersonalCodes(Base):
    def test_personal_code_keeps_requests_across_browsers(self):
        a, _ = self.enter("teacher", "10.0.0.2")
        req = self.ask(a)
        self.assertTrue(req["on_invite"])
        b, _ = self.enter("teacher", "10.0.0.3")  # "another browser": a new session from the same code
        s, got, _ = self.call("GET", "/api/requests/" + req["code"], headers=b)
        self.assertEqual((s, got["code"]), (200, req["code"]))
        self.assertIn(req["code"], [r["code"] for r in self.call("GET", "/api/access/requests", headers=b)[1]["requests"]])

    def test_shared_code_never_shows_requests_to_others(self):
        a, _ = self.enter("class", "10.0.0.4")
        req = self.ask(a)
        self.assertFalse(req["on_invite"])
        b, _ = self.enter("class", "10.0.0.5")
        self.assertEqual(self.call("GET", "/api/requests/" + req["code"], headers=b)[0], 404)
        self.assertEqual(self.call("GET", "/api/access/requests", headers=b)[1]["requests"], [])
        # the submitting browser still opens it with its private key
        self.assertEqual(self.call("GET", "/api/requests/" + req["code"], headers=dict(a, **{"X-Owner-Token": req["token"]}))[0], 200)

    def test_other_personal_code_cannot_read(self):
        a, _ = self.enter("teacher")
        req = self.ask(a)
        r, _ = self.enter("rev")
        self.assertEqual(self.call("GET", "/api/requests/" + req["code"], headers=r)[0], 404)


class TestConfigCheck(unittest.TestCase):
    def test_check_config(self):
        old = {k: os.environ.get(k) for k in ("AGELENS_INVITES", "AGELENS_REVIEWER_TOKEN", "AGELENS_STUDY_TOKEN")}
        try:
            os.environ.update(AGELENS_INVITES="", AGELENS_REVIEWER_TOKEN="", AGELENS_STUDY_TOKEN="")
            self.assertEqual(AX.check_config(), [])  # open demo: nothing required
            os.environ.update(AGELENS_INVITES="[]", AGELENS_REVIEWER_TOKEN="short")
            self.assertEqual(len(AX.check_config()), 2)
            os.environ["AGELENS_INVITES"] = "not json"
            self.assertEqual(AX.check_config(), ["AGELENS_INVITES is not valid JSON."])
            os.environ.update(AGELENS_INVITES=json.dumps(INVITES + [{"id": "bad"}]), AGELENS_REVIEWER_TOKEN="x" * 20, AGELENS_STUDY_TOKEN="y" * 20)
            self.assertEqual(len(AX.check_config()), 1)
            os.environ["AGELENS_INVITES"] = json.dumps(INVITES)
            self.assertEqual(AX.check_config(), [])
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class TestOpenPublicDemo(Base):
    """Public mode without AGELENS_INVITES: open to everyone; reviewer and study desks closed unless their token is set."""
    PUBLIC = False

    def setUp(self):
        super().setUp()
        os.environ["AGELENS_PUBLIC"] = "1"
        for k in ("AGELENS_INVITES", "AGELENS_REVIEWER_TOKEN", "AGELENS_STUDY_TOKEN"):
            os.environ.pop(k, None)

    def test_open_without_code(self):
        self.assertEqual(self.call("GET", "/api/access/status")[1], {"public": True, "invite": False, "signed_in": False})
        self.assertEqual(self.call("GET", "/api/overview")[0], 200)
        self.assertEqual(self.call("POST", "/api/age/check", {"text": "年龄35岁以下"})[0], 200)
        self.assertEqual(self.call("POST", "/api/access/redeem", {"code": CODES["class"]})[0], 404)

    def test_desks_closed_and_no_token_files(self):
        before = {p: p.exists() for p in (db.DATA_DIR / "reviewer_token",)}
        self.assertEqual(self.call("GET", "/api/reviewer/requests", headers={"X-Reviewer-Token": "guess-guess-guess"})[0], 401)
        self.assertEqual(self.call("GET", "/api/study/rater/status", headers={"X-Study-Token": "guess-guess-guess", "X-Rater-Id": "R1"})[0], 401)
        self.assertEqual({p: p.exists() for p in before}, before)  # nothing written

    def test_diag_still_off(self):
        self.assertEqual(self.call("POST", "/api/diag", {"x": 1})[0], 404)


class TestLocalModeUnchanged(Base):
    PUBLIC = False

    def test_no_gate_locally(self):
        os.environ.pop("AGELENS_PUBLIC", None)
        self.assertEqual(self.call("GET", "/api/overview")[0], 200)
        self.assertEqual(self.call("GET", "/api/access/status")[1], {"public": False, "invite": False, "signed_in": False})
        self.assertEqual(self.call("POST", "/api/access/redeem", {"code": CODES["class"]})[0], 404)


if __name__ == "__main__":
    unittest.main()
