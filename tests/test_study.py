"""Study tools: formal-mode refusal, allocation, blinding, scoring flow, anonymous export. Temp DB + real HTTP server."""
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ.setdefault("AGELENS_DB", os.path.join(_tmp, "t.db"))
os.environ["AGELENS_STUDY_TOKEN"] = "test-study-token"

from http.server import ThreadingHTTPServer  # noqa: E402
from backend import db, server, api_study as S, study_arms  # noqa: E402

ST = {"X-Study-Token": "test-study-token"}
REAL_APPROVAL = Path(S.APPROVAL_PATH)


def call(base, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = dict(headers or {})
    if data:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            ct = r.headers.get("Content-Type", "")
            return r.status, (json.loads(raw) if "json" in ct else raw.decode())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw.decode()


class FailingProvider:
    def generate(self, inp):
        raise RuntimeError("boom")


class OkProvider:
    def generate(self, inp):
        return {"findings": [], "uncertainties": ["Not sure if the cap is strict."], "clarification_questions": ["Is the 35 limit strict?"],
                "suggested_next_steps": [], "limitations": []}


class Base(unittest.TestCase):
    DESIGN = S.LEGACY_DESIGN  # these tests cover the legacy parallel design; CrossoverTests below cover the default

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
        self.tmpdir = Path(tempfile.mkdtemp())
        S.APPROVAL_PATH = self.tmpdir / "APPROVAL.json"  # never the real path in tests
        S.DESIGN_OVERRIDE = self.DESIGN
        study_arms.PROVIDER_OVERRIDE = None
        with S.conn() as c:
            for t in ("study_scores", "study_calibration", "study_task_runs", "study_participants", "study_settings"):
                c.execute("DELETE FROM " + t)

    def tearDown(self):
        S.APPROVAL_PATH = REAL_APPROVAL
        S.DESIGN_OVERRIDE = None
        study_arms.PROVIDER_OVERRIDE = None

    def c(self, method, path, body=None, headers=None):
        return call(self.base, method, path, body, headers)

    def enrol(self):
        st, r = self.c("POST", "/api/study/enrol", {"consent": True})
        self.assertEqual(st, 200, r)
        return r["code"], {"X-Participant-Code": r["code"], "X-Participant-Token": r["token"]}, r

    def run_all(self, hdr, text="Hello, I am 38 with eight years in procurement. The ad lists 年龄35周岁以下. I cannot tell if this is strict. Is it?"):
        st, sess = self.c("GET", "/api/study/session", headers=hdr)
        for step in sess["steps"]:
            st, t = self.c("POST", "/api/study/task/%s/start" % step["task_id"], {}, hdr)
            self.assertEqual(st, 200, t)
            st, r = self.c("POST", "/api/study/task/%s/submit" % step["task_id"], {"answer": text, "client_elapsed_ms": 1000}, hdr)
            self.assertEqual(st, 200, r)
        return sess

    def good_approval(self):
        a = {"approved": True, "teacher_name": "TEST FIXTURE ONLY", "approval_date": "2026-01-01", "protocol_version": "x", "assignment_mechanism": "blocked",
             "stopping_rule": "fixed N", "recruitment_target": 24, "allocation_seed": 7,
             "preregistration": {"reference": "test-fixture", "sha256": "a" * 64}, "tasks_sha256": S.tasks_sha256()}
        S.APPROVAL_PATH.write_text(json.dumps(a))
        return a


class FormalGate(Base):
    def test_default_is_simulation_with_banner(self):
        st, r = self.c("GET", "/api/study/config")
        self.assertEqual((r["mode"], r["banner"]), ("simulation", "SIMULATION — not study data"))
        self.assertFalse(r["formal_allowed"])

    def test_formal_refused_without_approval(self):
        st, r = self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)
        self.assertEqual(st, 403)
        self.assertTrue(any("APPROVAL.json" in b for b in r["blockers"]))
        self.assertEqual(self.c("GET", "/api/study/config")[1]["mode"], "simulation")
        self.assertFalse(REAL_APPROVAL.exists(), "tests/server must never create the real approval file")

    def test_formal_refused_without_token(self):
        self.assertEqual(self.c("POST", "/api/study/mode", {"mode": "formal"})[0], 401)

    def test_approval_alone_is_not_enough_model_needed(self):
        self.good_approval()
        st, r = self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)
        self.assertEqual(st, 403)
        self.assertTrue(any("model" in b.lower() for b in r["blockers"]))

    def test_model_alone_is_not_enough(self):
        study_arms.PROVIDER_OVERRIDE = OkProvider()
        st, r = self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)
        self.assertEqual(st, 403)

    def test_incomplete_and_mismatched_approval_refused(self):
        study_arms.PROVIDER_OVERRIDE = OkProvider()
        for mutate in (lambda a: a.pop("teacher_name"), lambda a: a.update(approved=False), lambda a: a["preregistration"].update(sha256="zz"),
                       lambda a: a.update(tasks_sha256="0" * 64), lambda a: a.pop("allocation_seed"), lambda a: a.update(recruitment_target=0)):
            a = self.good_approval()
            mutate(a)
            S.APPROVAL_PATH.write_text(json.dumps(a))
            self.assertEqual(self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)[0], 403)
        S.APPROVAL_PATH.write_text("{not json")
        self.assertEqual(self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)[0], 403)

    def test_formal_enrol_and_export_refused_when_gate_closed(self):
        self.assertEqual(self.c("GET", "/api/study/export?scope=formal", None, ST)[0], 403)
        with S.conn() as c:
            S.set_setting(c, "mode", "formal")  # even if the setting were forced, nothing formal runs
        st, r = self.c("POST", "/api/study/enrol", {"consent": True})
        self.assertEqual(st, 403)
        self.assertEqual(self.c("GET", "/api/study/config")[1]["mode"], "simulation")

    def test_fixture_approval_plus_model_allows_formal_and_keeps_data_separate(self):
        sim_code, sim_hdr, _ = self.enrol()
        self.run_all(sim_hdr)
        study_arms.PROVIDER_OVERRIDE = OkProvider()
        self.good_approval()
        st, r = self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)
        self.assertEqual(st, 200, r)
        fc, fh, _ = self.enrol()
        self.assertTrue(fc.startswith("P-"))
        st, ex = self.c("GET", "/api/study/export?scope=formal", None, ST)
        self.assertEqual(st, 200)
        codes = {p["participant_code"] for p in ex["participants"]}
        self.assertEqual(codes, {fc})
        self.assertIsNone(ex["meta"]["banner"])
        st, exs = self.c("GET", "/api/study/export?scope=simulated", None, ST)
        self.assertEqual({p["participant_code"] for p in exs["participants"]}, {sim_code})
        # approval removed -> falls back to simulation, formal enrolment refused
        S.APPROVAL_PATH.unlink()
        self.assertEqual(self.c("GET", "/api/study/config")[1]["mode"], "simulation")
        self.assertEqual(self.c("POST", "/api/study/enrol", {"consent": True})[0], 403)


class Allocation(Base):
    def test_balanced_blocks_and_seeded(self):
        arms = []
        for _ in range(24):
            code, hdr, r = self.enrol()
            self.assertNotIn("arm", r)  # allocation concealed in the enrolment reply
            self.assertNotIn("arm", r["session"])
            arms.append(self.c("GET", "/api/study/session", headers=hdr)[1]["aid_kind"])
        self.assertEqual(arms.count("template"), 12)
        for i in range(0, 24, 4):
            self.assertEqual(arms[i:i + 4].count("template"), 2)
        # reproducible from the documented seed
        import random
        for b in range(6):
            blk = ["template", "template", "assisted", "assisted"]
            random.Random("%s|simulation|%d" % (S.SIM_SEED, b)).shuffle(blk)
            self.assertEqual(arms[b * 4:b * 4 + 4], blk)

    def test_consent_required(self):
        self.assertEqual(self.c("POST", "/api/study/enrol", {})[0], 400)
        with S.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM study_participants").fetchone()[0], 0)


class ParticipantFlow(Base):
    def test_flow_aid_by_arm_and_order(self):
        seen = {}
        for _ in range(4):
            code, hdr, r = self.enrol()
            sess = self.c("GET", "/api/study/session", headers=hdr)[1]
            first, second = sess["steps"][0]["task_id"], sess["steps"][1]["task_id"]
            self.assertEqual(self.c("POST", "/api/study/task/%s/start" % second, {}, hdr)[0], 409)  # order enforced
            st, t = self.c("POST", "/api/study/task/%s/start" % first, {}, hdr)
            seen[sess["aid_kind"]] = t["aid"]
            self.assertNotIn("facts", json.dumps(t))  # fact sheet / rubric never sent to participants
            st, again = self.c("POST", "/api/study/task/%s/start" % first, {}, hdr)
            self.assertLessEqual(again["remaining_ms"], t["remaining_ms"])
        self.assertIn("[job title]", seen["template"]["text"])
        self.assertTrue(seen["assisted"]["simulated"])
        self.assertEqual(seen["assisted"]["provider"], "SIMULATED")

    def test_requires_participant_token(self):
        code, hdr, _ = self.enrol()
        self.assertEqual(self.c("GET", "/api/study/session")[0], 401)
        bad = dict(hdr, **{"X-Participant-Token": "nope"})
        self.assertEqual(self.c("GET", "/api/study/session", headers=bad)[0], 401)

    def test_timing_late_and_timeout(self):
        code, hdr, _ = self.enrol()
        tid = self.c("GET", "/api/study/session", headers=hdr)[1]["steps"][0]["task_id"]
        self.c("POST", "/api/study/task/%s/start" % tid, {}, hdr)
        with S.conn() as c:
            c.execute("UPDATE study_task_runs SET started_ms=started_ms-1000000 WHERE code=?", (code,))
        st, r = self.c("POST", "/api/study/task/%s/submit" % tid, {"answer": "late text"}, hdr)
        self.assertTrue(r["late"])
        with S.conn() as c:
            row = c.execute("SELECT timed_out, late, elapsed_ms FROM study_task_runs WHERE code=?", (code,)).fetchone()
        self.assertEqual((row["timed_out"], row["late"]), (1, 1))

    def test_model_failure_recorded_not_hidden(self):
        study_arms.PROVIDER_OVERRIDE = FailingProvider()
        # find an assisted participant
        for _ in range(4):
            code, hdr, _ = self.enrol()
            sess = self.c("GET", "/api/study/session", headers=hdr)[1]
            if sess["aid_kind"] == "assisted":
                st, t = self.c("POST", "/api/study/task/%s/start" % sess["steps"][0]["task_id"], {}, hdr)
                self.assertTrue(t["aid"]["failed"])
                self.assertEqual(t["aid"]["text"], "")
                with S.conn() as c:
                    self.assertEqual(c.execute("SELECT model_failure FROM study_task_runs WHERE code=?", (code,)).fetchone()[0], 1)
                return
        self.fail("no assisted participant in 4 enrolments")

    def test_withdraw_deletes_text_keeps_fact(self):
        code, hdr, _ = self.enrol()
        tid = self.c("GET", "/api/study/session", headers=hdr)[1]["steps"][0]["task_id"]
        self.c("POST", "/api/study/task/%s/start" % tid, {}, hdr)
        self.c("POST", "/api/study/task/%s/submit" % tid, {"answer": "my private text"}, hdr)
        self.assertEqual(self.c("POST", "/api/study/withdraw", {}, hdr)[0], 200)
        with S.conn() as c:
            r = c.execute("SELECT answer FROM study_task_runs WHERE code=?", (code,)).fetchone()
            self.assertIsNone(r["answer"])
            self.assertEqual(c.execute("SELECT status FROM study_participants WHERE code=?", (code,)).fetchone()[0], "withdrawn")
        ex = self.c("GET", "/api/study/export", None, ST)[1]
        self.assertEqual(ex["participants"][0]["dropout"], 1)


class Scoring(Base):
    def rater(self, who):
        return dict(ST, **{"X-Rater-Id": who})

    def calibrate(self, who):
        doc = S.load_tasks()
        for it in doc["calibration"]:
            ref = it["reference"]
            st, r = self.c("POST", "/api/study/calibration/" + it["id"], dict(ref), self.rater(who))
            self.assertEqual(st, 200)
            self.assertEqual(r["agreed"], 5)

    def test_token_and_calibration_gate(self):
        self.assertEqual(self.c("GET", "/api/study/rater/next", None, {"X-Rater-Id": "R1"})[0], 401)
        self.assertEqual(self.c("GET", "/api/study/rater/next", None, ST)[0], 400)
        self.assertEqual(self.c("GET", "/api/study/rater/next", None, self.rater("R1"))[0], 409)
        st, r = self.c("GET", "/api/study/calibration", None, self.rater("R1"))
        self.assertNotIn('"reference"', json.dumps(r))

    def test_blinded_independent_scoring_disagreement_and_export(self):
        for _ in range(4):
            code, hdr, _ = self.enrol()
            self.run_all(hdr)
        self.c("POST", "/api/study/withdraw", {}, hdr)  # last one withdraws: not scorable
        for w in RATERS:
            self.calibrate(w)
        st, s = self.c("GET", "/api/study/calibration/summary", None, self.rater("R1"))
        self.assertTrue(s["target_met"])
        yes = {"c1": True, "c2": True, "c3": True, "c4": True, "severe": False}
        n1 = 0
        while True:
            st, nx = self.c("GET", "/api/study/rater/next", None, self.rater("R1"))
            if not nx["item"]:
                break
            flat = json.dumps(nx)
            for forbidden in ("arm", "assisted", "SIM-", "participant", "aid", "R2"):
                if forbidden == "SIM-":
                    continue
                self.assertNotIn('"%s"' % forbidden, flat)
            self.assertNotIn("facts", flat)
            n1 += 1
            body = dict(yes, item_key=nx["item"]["item_key"])
            if n1 % 3 == 0:
                body["c3"] = False
            self.assertEqual(self.c("POST", "/api/study/rater/score", body, self.rater("R1"))[0], 200)
            self.assertEqual(self.c("POST", "/api/study/rater/score", body, self.rater("R1"))[0], 409)  # no edits
        self.assertEqual(n1, 12)  # 3 non-withdrawn participants x 4
        # R3 sees nothing before R2 has scored
        self.assertIsNone(self.c("GET", "/api/study/rater/next", None, self.rater("R3"))[1]["item"])
        while True:
            nx = self.c("GET", "/api/study/rater/next", None, self.rater("R2"))[1]
            if not nx["item"]:
                break
            self.c("POST", "/api/study/rater/score", dict(yes, item_key=nx["item"]["item_key"], severe=(hash(nx["item"]["item_key"]) % 5 == 0) and False), self.rater("R2"))
        dis = self.c("GET", "/api/study/disagreements", None, self.rater("R1"))[1]
        self.assertEqual(dis["n"], 4)  # every third item differs on c3
        self.assertEqual(dis["open"], 4)
        ex = self.c("GET", "/api/study/export", None, ST)[1]
        self.assertEqual(sum(1 for r in ex["tasks"] if r["resolution"] == "unresolved"), 4)
        r3 = self.rater("R3")
        while True:
            nx = self.c("GET", "/api/study/rater/next", None, r3)[1]
            if not nx["item"]:
                break
            self.assertEqual(self.c("POST", "/api/study/rater/score", dict(yes, item_key=nx["item"]["item_key"]), r3)[0], 200)
        ex = self.c("GET", "/api/study/export", None, ST)[1]
        self.assertEqual(sum(1 for r in ex["tasks"] if r["resolution"] == "unresolved"), 0)
        self.assertEqual(sum(1 for r in ex["tasks"] if r["resolution"] == "adjudicated"), 4)
        adj = [r for r in ex["tasks"] if r["resolution"] == "adjudicated"][0]
        self.assertEqual(adj["final_c3"], 1)  # majority R2+R3 yes over R1 no
        # anonymity + simulation labelling
        flat = json.dumps(ex)
        self.assertNotIn("Hello, I am 38", flat)
        self.assertTrue(ex["meta"]["simulated"])
        self.assertEqual(ex["meta"]["banner"], "SIMULATION — not study data")
        self.assertTrue(all(r["simulated"] == 1 for r in ex["tasks"]))
        w = [p for p in ex["participants"] if p["dropout"]]
        self.assertEqual(len(w), 1)
        st, csvtext = self.c("GET", "/api/study/export?format=csv&level=participant", None, ST)
        self.assertTrue(csvtext.startswith("# SIMULATION — not study data"))
        self.assertIn("usable_share", csvtext)
        self.assertEqual(self.c("GET", "/api/study/export", None, {})[0], 401)

    def test_severe_flag_makes_unusable_and_missing_counts_zero(self):
        code, hdr, _ = self.enrol()
        sess = self.c("GET", "/api/study/session", headers=hdr)[1]
        for i, step in enumerate(sess["steps"]):
            self.c("POST", "/api/study/task/%s/start" % step["task_id"], {}, hdr)
            self.c("POST", "/api/study/task/%s/submit" % step["task_id"], {"answer": "" if i == 3 else "some answer"}, hdr)
        bad_key = []
        for w in ("R1", "R2"):
            self.calibrate(w)
            n = 0
            while True:
                nx = self.c("GET", "/api/study/rater/next", None, self.rater(w))[1]
                if not nx["item"]:
                    break
                n += 1
                if not bad_key:
                    bad_key.append(nx["item"]["item_key"])
                self.c("POST", "/api/study/rater/score", {"item_key": nx["item"]["item_key"], "c1": True, "c2": True, "c3": True, "c4": True, "severe": nx["item"]["item_key"] == bad_key[0]}, self.rater(w))
            self.assertEqual(n, 3)  # the empty answer is never offered
        ex = self.c("GET", "/api/study/export", None, ST)[1]
        p = ex["participants"][0]
        self.assertEqual((p["n_usable"], p["usable_share"], p["tasks_missing"]), (2, 0.5, 1))

    def test_r3_cannot_score_agreed_items(self):
        code, hdr, _ = self.enrol()
        self.run_all(hdr)
        for w in RATERS:
            self.calibrate(w)
        key = self.c("GET", "/api/study/rater/next", None, self.rater("R1"))[1]["item"]["item_key"]
        yes = {"c1": True, "c2": True, "c3": True, "c4": True, "severe": False, "item_key": key}
        self.c("POST", "/api/study/rater/score", yes, self.rater("R1"))
        self.c("POST", "/api/study/rater/score", yes, self.rater("R2"))
        self.assertEqual(self.c("POST", "/api/study/rater/score", yes, self.rater("R3"))[0], 403)


RATERS = ("R1", "R2", "R3")


class CrossoverTests(Scoring):
    """The default design (tasks.json "design": crossover-rules-v1): each participant gets 2 ad-only and 2 AgeLens tasks."""
    DESIGN = None

    def conds(self, code):
        with S.conn() as c:
            return {r["task_id"]: (r["aid_kind"], r["position"], r["item_key"], r["aid_text"], r["aid_provider"])
                    for r in c.execute("SELECT * FROM study_task_runs WHERE code=?", (code,))}

    def test_sequences_balanced_per_block_and_seeded(self):
        d = S.design()
        seqs = []
        for _ in range(8):
            code, hdr, r = self.enrol()
            self.assertNotIn("arm", r)
            self.assertEqual(r["session"]["aid_kind"], "crossover")
            with S.conn() as c:
                seqs.append(c.execute("SELECT arm FROM study_participants WHERE code=?", (code,)).fetchone()[0])
        for b in range(2):
            self.assertEqual(sorted(seqs[b * 4:b * 4 + 4]), sorted(d["sequences"]))
        # reproducible from the documented seed: the same first block again after a reset
        first = seqs[:4]
        with S.conn() as c:
            c.execute("DELETE FROM study_participants")
        again = []
        for _ in range(4):
            code, _, _ = self.enrol()
            with S.conn() as c:
                again.append(c.execute("SELECT arm FROM study_participants WHERE code=?", (code,)).fetchone()[0])
        self.assertEqual(again, first)

    def test_each_participant_two_and_two_in_sequence_order_with_real_aid(self):
        d = S.design()
        task_in_b = {t: 0 for t in ("T1", "T2", "T3", "T4")}
        for _ in range(4):
            code, hdr, _ = self.enrol()
            self.run_all(hdr)
            with S.conn() as c:
                seq = c.execute("SELECT arm FROM study_participants WHERE code=?", (code,)).fetchone()[0]
            runs = self.conds(code)
            by_pos = [k for k, _ in sorted(runs.items(), key=lambda kv: kv[1][1])]
            kinds = [runs[t][0] for t in by_pos]
            first = "agelens" if seq[0] == "B" else "none"
            self.assertEqual(kinds[:2], [first, first])
            self.assertEqual(sorted(kinds), ["agelens", "agelens", "none", "none"])
            b_tasks = {t for t in runs if runs[t][0] == "agelens"}
            self.assertEqual(b_tasks, set(d["task_sets"][seq.split("-")[1]]))
            for t in b_tasks:
                task_in_b[t] += 1
                self.assertIn("What does the ad explicitly say?", runs[t][3])
                self.assertIn("[ad text:", runs[t][3])
                self.assertTrue(runs[t][4].startswith("agelens-rules age-rules-"))
            for t in set(runs) - b_tasks:
                self.assertEqual((runs[t][3], runs[t][4]), ("", "none"))
        self.assertEqual(set(task_in_b.values()), {2})  # over one block every task is in AgeLens exactly twice

    def test_agelens_aid_stays_rules_only_with_a_model_connected(self):
        doc = S.load_tasks()
        before = study_arms.agelens_aid(doc["tasks"][1])
        study_arms.PROVIDER_OVERRIDE = OkProvider()  # model "connected"
        after = study_arms.agelens_aid(doc["tasks"][1])
        self.assertEqual(before["text"], after["text"])
        self.assertFalse(after["simulated"])
        self.assertFalse(after["failed"])

    def test_formal_needs_approval_but_not_a_model(self):
        self.assertEqual(self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)[0], 403)
        self.good_approval()
        st, r = self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)
        self.assertEqual(st, 200, r)
        self.assertEqual(r["mode"], "formal")
        self.assertEqual(r["design"], "crossover-rules-v1")
        code, hdr, _ = self.enrol()
        self.assertTrue(code.startswith("P-"))

    def test_rater_never_sees_the_condition(self):
        code, hdr, _ = self.enrol()
        self.run_all(hdr)
        self.calibrate("R1")
        st, nx = self.c("GET", "/api/study/rater/next", None, self.rater("R1"))
        flat = json.dumps(nx)
        for forbidden in ("agelens", "AgeLens", "condition", "Ad only", "What does the ad explicitly say?", "crossover", "AB-S", "BA-S"):
            self.assertNotIn(forbidden, flat)

    def test_export_has_conditions_and_primary_difference(self):
        for _ in range(4):
            code, hdr, _ = self.enrol()
            self.run_all(hdr)
        for w in ("R1", "R2"):
            self.calibrate(w)
            while True:
                nx = self.c("GET", "/api/study/rater/next", None, self.rater(w))[1]
                if not nx["item"]:
                    break
                key = nx["item"]["item_key"]
                with S.conn() as c:
                    kind = c.execute("SELECT aid_kind FROM study_task_runs WHERE item_key=?", (key,)).fetchone()[0]
                ok = kind == "agelens"  # scripted: AgeLens tasks usable, ad-only tasks not (tests the arithmetic only)
                body = {"item_key": key, "c1": True, "c2": True, "c3": ok, "c4": True, "severe": False}
                self.assertEqual(self.c("POST", "/api/study/rater/score", body, self.rater(w))[0], 200)
        ex = self.c("GET", "/api/study/export", None, ST)[1]
        self.assertEqual(ex["meta"]["design"], "crossover-rules-v1")
        self.assertEqual(ex["meta"]["threshold"]["min_effect"], 0.2)
        self.assertEqual({r["condition"] for r in ex["tasks"]}, {"A", "B"})
        for p in ex["participants"]:
            self.assertEqual((p["usable_share_A"], p["usable_share_B"], p["diff_B_minus_A"]), (0.0, 1.0, 1.0))
            self.assertIn(p["first_condition"], ("A", "B"))
        self.assertNotIn("What does the ad explicitly say?", json.dumps(ex))  # aid text is not exported


class Tasks(unittest.TestCase):
    def test_tasks_file_is_fictional_and_complete(self):
        d = S.load_tasks()
        self.assertTrue(d["synthetic"])
        self.assertEqual([t["kind"] for t in d["tasks"]], ["age_cap", "qualification_exception", "age_preference", "incomplete_evidence"])
        self.assertEqual(len(d["rubric"]["criteria"]), 4)
        self.assertEqual({s["id"] for s in d["rubric"]["severe_error"]["types"]}, {"S1", "S2", "S3", "S4"})
        self.assertIn("DRAFT", d["_status"])
        self.assertEqual(sorted(sum(d["design"]["task_sets"].values(), [])), ["T1", "T2", "T3", "T4"])
        for t in d["tasks"]:
            self.assertIn("虚构", t["ad_text"])


if __name__ == "__main__":
    unittest.main()
