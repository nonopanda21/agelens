"""The randomized test: group held by the server, clock never reset, answers never leak, formal mode refused without what it needs."""
import csv
import io
import json
import os
import tempfile
import unittest
from unittest import mock

TMP = tempfile.mkdtemp()
os.environ.setdefault("AGELENS_DB", os.path.join(TMP, "t.db"))
os.environ["AGELENS_RCT_ENABLED"] = "1"

from backend import api_rct, llm, rct, server  # noqa: E402
from backend.server import HTTPError, Request  # noqa: E402

TOKEN = "desk-token"


def router():
    r = server.Router()
    api_rct.register(r)
    return r


ROUTES = router()


def call(method, path, body=None, headers=None, query=None):
    fn, params = ROUTES.match(method, path)
    req = Request(method, path, {k: [v] for k, v in (query or {}).items()}, headers or {}, json.dumps(body or {}).encode(), params)
    return fn(req)


def desk(path, body=None, method="POST", query=None):
    return call(method, path, body, {"X-Study-Token": TOKEN}, query)


def wipe():
    with rct.conn() as c:
        for t in ("rct_settings", "rct_case_sets", "rct_codes", "rct_participants", "rct_items", "rct_model_answers"):
            c.execute("DELETE FROM " + t)
        c.commit()


def enrol():
    r = call("POST", "/api/rct/enrol", {"consent": True})
    return r, {"X-Participant-Code": r["code"], "X-Participant-Token": r["token"]}


def full_set():
    occ = ["O%d" % i for i in range(16)]
    cases, ans = [], {}
    labels = ["Match"] * 12 + ["Conflict"] * 12 + ["Unknown"] * 8
    for i in range(32):
        cid = "C%d" % i
        cases.append({"id": cid, "source_ad_id": i, "ad_text": "Clerk. Must be under 35.", "entry_date": "2027-01-01", "cv": {"birth_date": "1990-01-01"},
                      "stratum": {"wording": "explicit" if i < 16 else "indirect", "province": "P%d" % (i % 4), "occupation": occ[i % 16]}})
        ans[cid] = {"gold_label": labels[i], "evidence_text": "Must be under 35."}
    prac = [{"id": "PX%d" % i, "ad_text": "Clerk.", "entry_date": "2027-01-01", "cv": {"birth_date": "1990-01-01"}} for i in range(2)]
    for x in prac:
        ans[x["id"]] = {"gold_label": "Match", "evidence_text": "Clerk."}
    return {"version": "t", "practice": prac, "cases": cases}, {"answers": ans}


class Base(unittest.TestCase):
    def setUp(self):
        wipe()
        self.env = mock.patch.dict(os.environ, {"AGELENS_STUDY_TOKEN": TOKEN, "AGELENS_LLM_PROVIDER": "template"}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)


class SwitchedOff(unittest.TestCase):
    def test_switching_it_off_leaves_only_a_closed_config(self):
        with mock.patch.dict(os.environ, {"AGELENS_RCT_ENABLED": "0"}):
            r = server.Router()
            api_rct.register(r)
        fn, params = r.match("GET", "/api/rct/config")
        self.assertEqual(fn(Request("GET", "/api/rct/config", {}, {}, b"", params)), {"enabled": False})
        for method, path in (("POST", "/api/rct/enrol"), ("POST", "/api/rct/next"), ("POST", "/api/rct/tool"), ("POST", "/api/rct/admin/import"), ("GET", "/api/rct/admin/export"), ("GET", "/api/rct/admin/status")):
            self.assertIsNone(r.match(method, path)[0], path)


class Assignment(Base):
    def test_consent_required(self):
        with self.assertRaises(HTTPError):
            call("POST", "/api/rct/enrol", {})

    def test_groups_balance_in_blocks(self):
        groups = [enrol()[1] for _ in range(8)]
        with rct.conn() as c:
            n = [r[0] for r in c.execute("SELECT grp FROM rct_participants ORDER BY rowid")]
        self.assertEqual(n.count("treatment"), 4)
        for i in (0, 4):
            self.assertEqual(n[i:i + 4].count("treatment"), 2)
        self.assertEqual(len(groups), 8)

    def test_logging_in_again_keeps_the_group_and_order(self):
        r, _ = enrol()
        with rct.conn() as c:
            a = c.execute("SELECT grp, case_order FROM rct_participants WHERE code=?", (r["code"],)).fetchone()
            again = None
        again = call("POST", "/api/rct/enrol", {"code": r["code"]})
        self.assertTrue(again["resumed"])
        with rct.conn() as c:
            b = c.execute("SELECT grp, case_order FROM rct_participants WHERE code=?", (r["code"],)).fetchone()
        self.assertEqual(tuple(a), tuple(b))

    def test_unknown_code_is_refused(self):
        with self.assertRaises(HTTPError):
            call("POST", "/api/rct/enrol", {"code": "P-NOPE", "consent": True})

    def test_practice_comes_first_then_order_differs(self):
        orders = set()
        for _ in range(6):
            r, _h = enrol()
            with rct.conn() as c:
                o = json.loads(c.execute("SELECT case_order FROM rct_participants WHERE code=?", (r["code"],)).fetchone()[0])
            self.assertEqual(o[:2], ["PR1", "PR2"])
            orders.add(tuple(o[2:]))
        self.assertGreater(len(orders), 1)


class Clock(Base):
    def test_refresh_does_not_reset_the_clock(self):
        _, h = enrol()
        a = call("POST", "/api/rct/next", {}, h)
        with mock.patch.object(rct, "now_ms", return_value=rct.now_ms() + 30000):
            b = call("POST", "/api/rct/next", {}, h)
        self.assertEqual(a["case"]["id"], b["case"]["id"])
        self.assertLess(b["remaining_ms"], a["remaining_ms"] - 25000)

    def test_first_answer_stands(self):
        _, h = enrol()
        cid = call("POST", "/api/rct/next", {}, h)["case"]["id"]
        call("POST", "/api/rct/answer", {"case_id": cid, "label": "Conflict"}, h)
        again = call("POST", "/api/rct/answer", {"case_id": cid, "label": "Match"}, h)
        self.assertTrue(again["already"])
        with rct.conn() as c:
            self.assertEqual(c.execute("SELECT label FROM rct_items WHERE case_id=?", (cid,)).fetchone()[0], "Conflict")

    def test_time_out_is_recorded_and_moves_on(self):
        _, h = enrol()
        first = call("POST", "/api/rct/next", {}, h)["case"]["id"]
        with mock.patch.object(rct, "now_ms", return_value=rct.now_ms() + 200000):
            nxt = call("POST", "/api/rct/next", {}, h)
        self.assertNotEqual(nxt["case"]["id"], first)
        with rct.conn() as c:
            r = c.execute("SELECT state, label, timed_out, elapsed_ms FROM rct_items WHERE case_id=?", (first,)).fetchone()
        self.assertEqual((r["state"], r["label"], r["timed_out"], r["elapsed_ms"]), ("timed_out", None, 1, 120000))

    def test_an_answer_after_the_limit_does_not_count(self):
        _, h = enrol()
        cid = call("POST", "/api/rct/next", {}, h)["case"]["id"]
        with mock.patch.object(rct, "now_ms", return_value=rct.now_ms() + 200000):
            call("POST", "/api/rct/answer", {"case_id": cid, "label": "Match"}, h)
        with rct.conn() as c:
            self.assertIsNone(c.execute("SELECT label FROM rct_items WHERE case_id=?", (cid,)).fetchone()[0])


class Blinding(Base):
    def test_no_answer_or_stratum_reaches_a_participant(self):
        _, h = enrol()
        seen = []
        while True:
            d = call("POST", "/api/rct/next", {}, h)
            if d["done"]:
                break
            seen.append(json.dumps(d))
            r = call("POST", "/api/rct/answer", {"case_id": d["case"]["id"], "label": "Unknown"}, h)
            seen.append(json.dumps(r))
        blob = " ".join(seen)
        for word in ("gold", "evidence_text", "rationale", "stratum", "wording", "correct", '"score"'):
            self.assertNotIn(word, blob)

    def test_case_file_holding_answers_is_refused(self):
        cases, key = full_set()
        cases["cases"][0]["gold_label"] = "Match"
        with mock.patch("sys.stderr"):
            status, body = desk("/api/rct/admin/import", {"cases": cases, "answer_key": key})
        self.assertEqual(status, 422)
        self.assertIn("must not hold answers", " ".join(body["problems"]))


class Tool(Base):
    def _treatment(self):
        while True:
            r, h = enrol()
            if r["session"]["tool"]:
                return h

    def _control(self):
        while True:
            r, h = enrol()
            if not r["session"]["tool"]:
                return h

    def test_control_cannot_call_the_tool(self):
        h = self._control()
        cid = call("POST", "/api/rct/next", {}, h)["case"]["id"]
        with self.assertRaises(HTTPError) as e:
            call("POST", "/api/rct/tool", {"case_id": cid}, h)
        self.assertEqual(e.exception.status, 403)

    def test_tool_without_a_model_says_so_and_is_logged(self):
        h = self._treatment()
        cid = call("POST", "/api/rct/next", {}, h)["case"]["id"]
        v = call("POST", "/api/rct/tool", {"case_id": cid}, h)
        self.assertEqual(v["api_status"], "no_model")
        self.assertIn("No AI model", v["note"])
        self.assertNotRegex(json.dumps(v), r"\b(Match|Conflict)\b")
        again = call("POST", "/api/rct/next", {}, h)
        self.assertEqual(again["tool_view"]["api_status"], "no_model")
        with rct.conn() as c:
            r = c.execute("SELECT api_status, tool_opened_ms, tool_returned_ms FROM rct_items WHERE case_id=?", (cid,)).fetchone()
        self.assertEqual(r["api_status"], "no_model")
        self.assertIsNotNone(r["tool_opened_ms"])
        self.assertIsNotNone(r["tool_returned_ms"])

    def test_tool_refused_after_the_time_is_up(self):
        h = self._treatment()
        cid = call("POST", "/api/rct/next", {}, h)["case"]["id"]
        with mock.patch.object(rct, "now_ms", return_value=rct.now_ms() + 121000):
            with self.assertRaises(HTTPError):
                call("POST", "/api/rct/tool", {"case_id": cid}, h)

    def test_failed_model_is_shown_as_failed(self):
        v = rct.tool_view({"ai_status": "fallback", "summary": {"states": "Rules."}, "reports": {"ai": {"available": False}}})
        self.assertEqual(v["api_status"], "failed")
        self.assertIn("failed", v["note"])

    def test_model_output_reaches_the_view_without_a_label(self):
        v = rct.tool_view({"ai_status": "used", "summary": {"states": "The ad states a maximum age of 35.", "relates": "You entered 38; the stated maximum is 35."},
                           "reports": {"ai": {"available": True, "stated": ["Under 35."], "related": ["At 38, above it."], "unclear": ["How it is applied."]}}})
        self.assertEqual((v["api_status"], v["stated"], v["related"], v["unclear"]), ("ok", ["Under 35."], ["At 38, above it."], ["How it is applied."]))
        self.assertIn("This CV gives age 38 on the start date", v["relates"])

    def test_tool_reads_the_original_ad_not_a_translation(self):
        body = rct.tool_body({"ad_text": "年龄35岁以下", "ad_text_en": "Under 35", "entry_date": "2027-01-01", "cv": {"birth_date": "1990-01-01"}})
        self.assertEqual(body["text"], "年龄35岁以下")
        self.assertEqual(body["profile"]["age"], 37)

    def test_age_is_worked_out_on_the_entry_date(self):
        self.assertEqual(rct.age_on("1990-03-02", "2027-03-01"), 36)
        self.assertEqual(rct.age_on("1990-03-01", "2027-03-01"), 37)


class Formal(Base):
    def test_refused_without_approval_set_model_and_storage(self):
        status, body = desk("/api/rct/admin/mode", {"mode": "formal"})
        self.assertEqual(status, 403)
        text = " ".join(body["blockers"])
        for w in ("RCT_APPROVAL.json", "rehearsal", "No AI model", "AGELENS_RCT_DURABLE"):
            self.assertIn(w, text)

    def test_desk_needs_the_token(self):
        with self.assertRaises(HTTPError) as e:
            call("POST", "/api/rct/admin/mode", {"mode": "formal"})
        self.assertEqual(e.exception.status, 401)
        with self.assertRaises(HTTPError):
            call("GET", "/api/rct/admin/export", {}, {}, {"scope": "formal"})

    def test_formal_design_counts(self):
        cases, key = full_set()
        self.assertEqual(rct.formal_problems(cases, key), [])
        cases["cases"].pop()
        self.assertTrue(rct.formal_problems(cases, key))

    def _approved(self, sha):
        p = os.path.join(TMP, "a.json")
        with open(p, "w") as f:
            json.dump({"approved": True, "teacher_name": "T", "approval_date": "2026-11-20", "stopping_rule": "fixed N", "case_set_sha256": sha, "recruitment_target": 40, "allocation_seed": 7}, f)
        return mock.patch.object(rct, "APPROVAL_PATH", __import__("pathlib").Path(p))

    def test_formal_run_needs_a_code_and_freezes_the_set(self):
        cases, key = full_set()
        sha = desk("/api/rct/admin/import", {"cases": cases, "answer_key": key})["case_set_sha256"]
        with self._approved(sha), mock.patch.object(rct, "model_connected", return_value=True), mock.patch.dict(os.environ, {"AGELENS_RCT_DURABLE": "1"}):
            self.assertEqual(desk("/api/rct/admin/mode", {"mode": "formal"})["mode"], "formal")
            with self.assertRaises(HTTPError):
                call("POST", "/api/rct/enrol", {"consent": True})
            code = desk("/api/rct/admin/codes", {"n": 1})["codes"][0]
            r = call("POST", "/api/rct/enrol", {"consent": True, "code": code})
            self.assertFalse(r["session"]["simulated"])
            with self.assertRaises(HTTPError):
                desk("/api/rct/admin/import", {"cases": cases, "answer_key": key})

    def test_changed_set_falls_back_to_simulation(self):
        cases, key = full_set()
        desk("/api/rct/admin/import", {"cases": cases, "answer_key": key})
        with self._approved("different"), mock.patch.object(rct, "model_connected", return_value=True), mock.patch.dict(os.environ, {"AGELENS_RCT_DURABLE": "1"}):
            with rct.conn() as c:
                rct.set_setting(c, "mode", "formal")
                c.commit()
                self.assertEqual(rct.current_mode(c), "simulation")


class Export(Base):
    def _rows(self, table, scope="simulation"):
        resp = desk("/api/rct/admin/export", {}, "GET", {"scope": scope, "table": table})
        body = resp.body.decode() if isinstance(resp.body, bytes) else resp.body
        return list(csv.DictReader(io.StringIO(body)))

    def _finish(self, label="Unknown"):
        r, h = enrol()
        while True:
            d = call("POST", "/api/rct/next", {}, h)
            if d["done"]:
                break
            call("POST", "/api/rct/answer", {"case_id": d["case"]["id"], "label": label}, h)
        call("POST", "/api/rct/finish", {"used_other_tools": "no"}, h)
        return r["code"]

    def test_score_and_practice_are_kept_apart(self):
        code = self._finish("Unknown")
        rows = [x for x in self._rows("items") if x["participant_id"] == code]
        self.assertEqual(len(rows), 6)  # the 2 practice cases are not exported
        self.assertEqual(sum(int(x["correct"]) for x in rows), 2)  # RH3 and RH6
        p = [x for x in self._rows("persons") if x["participant_id"] == code][0]
        self.assertAlmostEqual(float(p["score"]), 2 / 6 * 100, 3)
        self.assertEqual(p["status"], "completed")
        self.assertEqual(p["used_other_tools"], "no")

    def test_person_who_stops_counts_wrong_and_at_the_limit(self):
        r, h = enrol()
        for _ in range(3):
            d = call("POST", "/api/rct/next", {}, h)
            call("POST", "/api/rct/answer", {"case_id": d["case"]["id"], "label": "Match"}, h)
        p = [x for x in self._rows("persons") if x["participant_id"] == r["code"]][0]
        self.assertEqual(float(p["missing_rate"]), round(5 / 6, 4))
        self.assertGreater(float(p["search_seconds"]), 90)

    def test_withdrawal_deletes_answers(self):
        r, h = enrol()
        d = call("POST", "/api/rct/next", {}, h)
        call("POST", "/api/rct/answer", {"case_id": d["case"]["id"], "label": "Match"}, h)
        call("POST", "/api/rct/withdraw", {}, h)
        with rct.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM rct_items WHERE code=?", (r["code"],)).fetchone()[0], 0)
        p = [x for x in self._rows("persons") if x["participant_id"] == r["code"]][0]
        self.assertEqual((p["status"], p["score"]), ("withdrawn", ""))

    def test_simulated_rows_never_reach_the_formal_export(self):
        self._finish()
        self.assertEqual(self._rows("persons", "formal"), [])

    def test_status_shows_counts_but_no_results(self):
        self._finish()
        blob = json.dumps(desk("/api/rct/admin/status", {}, "GET"))
        for word in ('"score"', "search_seconds", "correct", "gold"):
            self.assertNotIn(word, blob)

    def test_ai_answers_stay_apart_from_people(self):
        class Stub(llm.Provider):
            name, model = "stub", "m"
            def generate(self, llm_input, system=None, user=None):
                self.seen = (system, user)
                return {"label": "Unknown"}
        s = Stub()
        with mock.patch.object(llm, "get_provider", return_value=s):
            for cid in ("RH1", "RH3"):
                desk("/api/rct/admin/benchmark", {"case_id": cid})
        self.assertIn("Entry date", s.seen[1])
        rows = self._rows("model")
        self.assertEqual({(x["case_id"], x["correct"]) for x in rows}, {("RH1", "0"), ("RH3", "1")})
        self.assertEqual(self._rows("persons"), [])

    def test_ai_without_a_model_is_recorded_not_invented(self):
        self.assertEqual(desk("/api/rct/admin/benchmark", {"case_id": "RH1"})["status"], "no_model")
        self.assertEqual(self._rows("model")[0]["label"], "")


if __name__ == "__main__":
    unittest.main()
