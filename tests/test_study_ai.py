"""Design crossover-ai-v1 (fixed template vs contextual AI, identical evidence): arm assignment, template builder, simulated drafter,
formal-mode refusal without a model and approval, export shape and blinding, scoring math and the paired test. Temp DB + real HTTP server.
No model is called anywhere: the 'model' paths use llm.FakeProvider / test doubles."""
import json
import os
import re
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
from backend import db, llm, server, api_study as S, study_arms as A, study_stats as ST_  # noqa: E402

ST = {"X-Study-Token": "test-study-token"}
REAL_APPROVAL = Path(S.APPROVAL_PATH)
CJK = re.compile(r"[㐀-鿿＀-￯]")
RATERS = ("R1", "R2", "R3")


def call(base, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = dict(headers or {})
    if data:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if "json" in r.headers.get("Content-Type", "") else raw.decode())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw.decode()


def good_model():
    """A model double whose statements pass llm.validate_output for task T1 (ad SIM-S01)."""
    return llm.FakeProvider({"statements": [
        {"section": "explicit", "type": "ad_fact", "text": "This ad states a maximum age of 35.", "evidence_ids": ["SIM-S01"]},
        {"section": "cannot", "type": "model_inference", "text": "The ad does not say whether the limit is applied strictly.", "evidence_ids": ["SIM-S01"]},
        {"section": "ask", "type": "user_stated", "text": "I am 38 with eight years of procurement experience; is the 35 limit applied strictly?", "evidence_ids": []}]})


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_schema()
        server.load_routes()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = "http://127.0.0.1:%d" % cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        S.APPROVAL_PATH = self.tmpdir / "APPROVAL.json"
        S.DESIGN_OVERRIDE = None          # default = crossover-ai-v1
        A.PROVIDER_OVERRIDE = None
        with S.conn() as c:
            for t in ("study_scores", "study_calibration", "study_scores_ai", "study_calibration_ai", "study_task_runs", "study_participants", "study_settings"):
                c.execute("DELETE FROM " + t)

    def tearDown(self):
        S.APPROVAL_PATH = REAL_APPROVAL
        S.DESIGN_OVERRIDE = None
        A.PROVIDER_OVERRIDE = None

    def c(self, method, path, body=None, headers=None):
        return call(self.base, method, path, body, headers)

    def enrol(self):
        st, r = self.c("POST", "/api/study/enrol", {"consent": True})
        self.assertEqual(st, 200, r)
        return r["code"], {"X-Participant-Code": r["code"], "X-Participant-Token": r["token"]}, r

    def run_all(self, hdr, reading="The ad sets an age limit of 35.", question="I am 38. Is the limit of 35 applied strictly for this vacancy?"):
        sess = self.c("GET", "/api/study/session", headers=hdr)[1]
        starts = {}
        for step in sess["steps"]:
            st, t = self.c("POST", "/api/study/task/%s/start" % step["task_id"], {}, hdr)
            self.assertEqual(st, 200, t)
            starts[step["task_id"]] = t
            st, r = self.c("POST", "/api/study/task/%s/submit" % step["task_id"], {"reading": reading, "question": question, "client_elapsed_ms": 1000}, hdr)
            self.assertEqual(st, 200, r)
        return starts

    def arm_of(self, code):
        with S.conn() as c:
            return c.execute("SELECT arm FROM study_participants WHERE code=?", (code,)).fetchone()[0]

    def good_approval(self):
        a = {"approved": True, "teacher_name": "TEST FIXTURE ONLY", "approval_date": "2026-01-01", "protocol_version": "x", "assignment_mechanism": "blocked",
             "stopping_rule": "fixed N", "recruitment_target": 24, "allocation_seed": 7,
             "preregistration": {"reference": "test-fixture", "sha256": "a" * 64}, "tasks_sha256": S.tasks_sha256()}
        S.APPROVAL_PATH.write_text(json.dumps(a))

    def rater(self, who):
        return dict(ST, **{"X-Rater-Id": who})

    def calibrate(self, who, exact=True):
        doc = S.load_tasks()
        for it in doc["calibration_ai"]:
            ref = it["reference"]
            body = {"facts": {k: bool(v) for k, v in ref["facts"].items()}, "unsupported": ref["unsupported"], **{k: bool(v) for k, v in ref["q"].items()}}
            st, r = self.c("POST", "/api/study/calibration/" + it["id"], body, self.rater(who))
            self.assertEqual(st, 200, r)
            if exact:
                self.assertEqual(r["agreed"], r["of"])


class DesignAndTasks(unittest.TestCase):
    def test_default_design_and_tasks_file(self):
        S.DESIGN_OVERRIDE = None
        d = S.design()
        self.assertEqual(d["id"], "crossover-ai-v1")
        self.assertTrue(S.is_ai())
        self.assertEqual(d["conditions"]["A"]["kind"], "template")
        self.assertEqual(d["conditions"]["B"]["kind"], "ai_contextual")
        self.assertEqual(d["outcomes"]["primary"], "interpretation_accuracy")
        self.assertEqual(S.design_id(), "crossover-ai-v1")
        S.DESIGN_OVERRIDE = S.RULES_DESIGN
        self.assertEqual(S.design_id(), "crossover-rules-v1")   # legacy stays selectable
        S.DESIGN_OVERRIDE = S.LEGACY_DESIGN
        self.assertEqual(S.design_id(), "parallel-llm-v0")
        S.DESIGN_OVERRIDE = None

    def test_tasks_additions_english_only_and_complete(self):
        doc = S.load_tasks()
        for t in doc["tasks"]:
            self.assertTrue(t["key_facts"])
            self.assertFalse(CJK.search(json.dumps(t["key_facts"], ensure_ascii=False)))
        new = {k: doc[k] for k in ("design_ai", "instructions_ai", "consent_ai_draft", "rubric_ai", "calibration_ai")}
        self.assertFalse(CJK.search(json.dumps(new, ensure_ascii=False)))
        for it in doc["calibration_ai"]:
            task = S.task_by_id(doc, it["task_id"])
            self.assertEqual(set(it["reference"]["facts"]), {f["id"] for f in task["key_facts"]})
        self.assertEqual([q["id"] for q in doc["rubric_ai"]["question_criteria"]], ["q1", "q2", "q3", "q4"])
        self.assertEqual(doc["design"]["id"], "crossover-rules-v1")   # legacy block untouched
        self.assertIn("improved decision support only", doc["design_ai"]["claim"].lower())


class Arms(Base):
    def test_counterbalancing_over_blocks(self):
        d = S.design()
        seqs, ai_tasks, first_ai = [], {t: 0 for t in ("T1", "T2", "T3", "T4")}, 0
        for _ in range(8):
            code, hdr, r = self.enrol()
            self.assertNotIn("arm", r)
            seqs.append(self.arm_of(code))
            sess = self.c("GET", "/api/study/session", headers=hdr)[1]
            order = [s["task_id"] for s in sess["steps"]]
            seq = seqs[-1]
            kinds = [d["conditions"][S.condition_of(d, seq, t)]["kind"] for t in order]
            self.assertEqual(kinds[0], kinds[1]); self.assertEqual(kinds[2], kinds[3]); self.assertNotEqual(kinds[0], kinds[2])
            self.assertEqual(sorted(kinds), ["ai_contextual"] * 2 + ["template"] * 2)
            for t, k in zip(order, kinds):
                ai_tasks[t] += k == "ai_contextual"
            first_ai += kinds[0] == "ai_contextual"
        for b in range(2):
            self.assertEqual(sorted(seqs[b * 4:b * 4 + 4]), sorted(d["sequences"]))
        self.assertEqual(set(ai_tasks.values()), {4})   # 2 blocks: every task has the AI tool 4 times of 8
        self.assertEqual(first_ai, 4)

    def test_participant_sees_tool_a_b_only(self):
        code, hdr, r = self.enrol()
        flat = json.dumps(r) + json.dumps(self.c("GET", "/api/study/config")[1]["conditions"])
        starts = self.run_all(hdr)
        labels = []
        for t in starts.values():
            flat += json.dumps(t)
            labels.append((t["position"], t["aid"]["label"]))
            self.assertNotIn("notice", t["aid"]["tool"])
        for bad in ("ai_contextual", "Contextual", "Fixed template", "provider", "SIMULATED-script", "\"arm\"", "AB-S", "BA-S", "facts", "key_facts"):
            self.assertNotIn(bad, flat)
        self.assertEqual(sorted(labels), [(1, "Tool A"), (2, "Tool A"), (3, "Tool B"), (4, "Tool B")])

    def test_evidence_package_identical_for_both_arms(self):
        doc = S.load_tasks()
        for t in doc["tasks"]:
            e1, e2 = A.evidence_package(t), A.evidence_package(t)
            self.assertEqual(e1, e2)
            self.assertEqual(e1["rule_version"], "age-rules-2.1.0")
            self.assertTrue(e1["wording"])
        seen = {}
        for _ in range(4):
            code, hdr, _ = self.enrol()
            for tid, t in self.run_all(hdr).items():
                seen.setdefault(tid, []).append((json.dumps(t["evidence"], sort_keys=True), t["aid"]["tool"].get("checklist")))
        for tid, v in seen.items():
            self.assertEqual(len({e for e, _ in v}), 1, tid)           # same evidence whichever tool
            self.assertEqual({bool(ch) for _, ch in v}, {True, False})  # template has a checklist, the AI tool does not

    def test_template_builder_deterministic_and_fixed_structure(self):
        doc = S.load_tasks()
        outs = []
        for t in doc["tasks"]:
            ev = A.evidence_package(t)
            a, b = A.template_tool(t, ev), A.template_tool(t, ev)
            self.assertEqual(a, b)
            self.assertEqual(a["checklist"], A.CHECKLIST)
            self.assertEqual(a["explicit"], [])
            outs.append((t, a))
            self.assertFalse(CJK.search(json.dumps(a, ensure_ascii=False)))
            self.assertIn('The ad says: "%s"' % ev["wording"], a["question"])
            self.assertIn("Please confirm whether the wording is a requirement or a preference", a["question"])
            self.assertNotIn(str(t["profile"]["years_experience"]) + " years", a["question"])   # no context from the profile
        # the same skeleton for every task once the slots are blanked
        skel = set()
        for t, a in outs:
            ev = A.evidence_package(t)
            q = a["question"].replace(A._role(t), "<role>").replace(t["ad_id"], "<id>").replace(ev["wording"], "<w>")
            q = re.sub(r'Does .*? apply to', "Does <exc> apply to", q)
            skel.add(q)
        self.assertEqual(len(skel), 1, skel)
        t2 = [a for t, a in outs if t["id"] == "T2"][0]
        self.assertIn("may be relaxed to 40", t2["question"])        # exception slot filled from the evidence
        t1 = [a for t, a in outs if t["id"] == "T1"][0]
        self.assertIn("Does any exception apply to", t1["question"])

    def test_simulated_drafter_labelled_and_never_claims_a_model_or_eligibility(self):
        doc = S.load_tasks()
        for t in doc["tasks"]:
            out = A.SimulatedAiDrafter().draft(t)
            self.assertEqual(out["notice"], A.SIM_NOTICE)
            self.assertEqual(A.SimulatedAiDrafter().draft(t), out)       # deterministic
            text = " ".join([out["reading"], out["question"]] + out["explicit"] + out["unclear"])
            self.assertFalse(A.violates(text))
            self.assertNotRegex(text.lower(), r"\b(as an ai|language model|gpt|claude)\b")
            self.assertFalse(CJK.search(text))
            self.assertIn("?", out["question"])
        aid = A.tool_aid(doc["tasks"][0], "ai_contextual", A.evidence_package(doc["tasks"][0]), simulation_ok=True)
        self.assertTrue(aid["simulated"])
        self.assertEqual(aid["provider"], "SIMULATED-script")
        self.assertIn("No AI model was used", A.SIM_NOTICE)
        self.assertTrue(A.SIM_NOTICE.startswith("SIMULATED"))

    def test_forbidden_regex(self):
        for bad in ("You qualify for the exception.", "I definitely qualify.", "This ad is illegal.", "you will be rejected"):
            self.assertTrue(A.violates(bad), bad)
        for ok in ("Do I qualify for the relaxation?", "The ad does not say who qualifies."):
            self.assertFalse(A.violates(ok), ok)

    def test_no_model_formal_aid_is_refused_never_simulated(self):
        t = S.load_tasks()["tasks"][0]
        aid = A.tool_aid(t, "ai_contextual", A.evidence_package(t), simulation_ok=False)
        self.assertTrue(aid["failed"])
        self.assertEqual(aid["error"], "NoModelConnected")
        self.assertFalse(aid["simulated"])
        self.assertEqual(aid["text"], "")

    def test_model_path_uses_adapter_and_is_not_labelled_simulated(self):
        t = S.load_tasks()["tasks"][0]
        A.PROVIDER_OVERRIDE = good_model()
        aid = A.tool_aid(t, "ai_contextual", A.evidence_package(t), simulation_ok=False)
        self.assertFalse(aid["failed"], aid)
        self.assertFalse(aid["simulated"])
        self.assertEqual(aid["provider"], "model:fake")
        out = json.loads(aid["text"])
        self.assertIn("maximum age of 35", out["reading"])
        self.assertIn("?", out["question"])
        # the adapter received the profile and the original ad text as DATA
        sent = A.PROVIDER_OVERRIDE.calls[0]
        self.assertEqual(sent["confirmed_profile"]["age"], 38)
        self.assertEqual(sent["evidence"][0]["id"], "SIM-S01")

    def test_model_failure_or_empty_output_is_recorded_not_hidden(self):
        t = S.load_tasks()["tasks"][0]
        for prov in (llm.FakeProvider(raises=llm.ProviderError("timeout")), llm.FakeProvider({"statements": []}),
                     llm.FakeProvider({"statements": [{"section": "explicit", "type": "ad_fact", "text": "You qualify for the exception.", "evidence_ids": ["SIM-S01"]}]})):
            A.PROVIDER_OVERRIDE = prov
            aid = A.tool_aid(t, "ai_contextual", A.evidence_package(t), simulation_ok=False)
            self.assertTrue(aid["failed"])
            self.assertEqual(aid["text"], "")
            self.assertFalse(aid["simulated"])


class FormalGate(Base):
    def test_default_simulation_with_notice_and_no_model(self):
        r = self.c("GET", "/api/study/config")[1]
        self.assertEqual((r["mode"], r["design"], r["ai_design"]), ("simulation", "crossover-ai-v1", True))
        self.assertEqual(r["sim_notice"], A.SIM_NOTICE)
        self.assertFalse(r["ai_arm"]["runnable_for_real"])
        self.assertFalse(r["formal_allowed"])
        self.assertEqual(r["conditions"], {"first": "Tool A", "second": "Tool B"})

    def test_formal_refused_without_model_even_with_approval(self):
        self.good_approval()
        st, r = self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)
        self.assertEqual(st, 403)
        self.assertTrue(any("No AI model is connected" in b for b in r["blockers"]), r)
        self.assertFalse(any("APPROVAL.json" in b for b in r["blockers"]))
        self.assertEqual(self.c("GET", "/api/study/config")[1]["mode"], "simulation")

    def test_formal_refused_without_approval_even_with_model(self):
        A.PROVIDER_OVERRIDE = good_model()
        st, r = self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)
        self.assertEqual(st, 403)
        self.assertTrue(any("APPROVAL.json" in b for b in r["blockers"]))
        self.assertFalse(REAL_APPROVAL.exists())

    def test_formal_needs_both_and_enrolment_and_export_follow(self):
        self.assertEqual(self.c("POST", "/api/study/enrol", {"consent": True})[0], 200)   # simulated enrolment is fine
        A.PROVIDER_OVERRIDE = good_model()
        self.good_approval()
        st, r = self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)
        self.assertEqual(st, 200, r)
        code, hdr, _ = self.enrol()
        self.assertTrue(code.startswith("P-"))
        # model removed: formal falls back to simulation, formal enrolment and export refused
        A.PROVIDER_OVERRIDE = None
        self.assertEqual(self.c("GET", "/api/study/config")[1]["mode"], "simulation")
        self.assertEqual(self.c("POST", "/api/study/enrol", {"consent": True})[0], 403)
        self.assertEqual(self.c("GET", "/api/study/export?scope=formal", None, ST)[0], 403)

    def test_formal_session_with_failing_model_never_falls_back_to_simulation(self):
        A.PROVIDER_OVERRIDE = llm.FakeProvider(raises=llm.ProviderError("timeout"))
        self.good_approval()
        self.assertEqual(self.c("POST", "/api/study/mode", {"mode": "formal"}, ST)[0], 200)
        code, hdr, _ = self.enrol()
        starts = self.run_all(hdr)
        d = S.design()
        seq = self.arm_of(code)
        for tid, t in starts.items():
            if d["conditions"][S.condition_of(d, seq, tid)]["kind"] == "ai_contextual":
                self.assertTrue(t["aid"]["failed"])
                self.assertEqual(t["aid"]["tool"], {})
        with S.conn() as c:
            rows = c.execute("SELECT aid_simulated, model_failure, aid_provider FROM study_task_runs WHERE code=?", (code,)).fetchall()
        self.assertEqual(sum(r["model_failure"] for r in rows), 2)
        self.assertEqual(sum(r["aid_simulated"] for r in rows), 0)


class Flow(Base):
    def fill(self, n=4):
        codes = []
        for _ in range(n):
            code, hdr, _ = self.enrol()
            self.run_all(hdr)
            codes.append(code)
        return codes

    def test_simulated_rows_are_labelled_everywhere(self):
        code, hdr, _ = self.enrol()
        starts = self.run_all(hdr)
        for t in starts.values():
            self.assertEqual(t["aid"]["sim_notice"], A.SIM_NOTICE)
        d, seq = S.design(), self.arm_of(code)
        with S.conn() as c:
            runs = {r["task_id"]: r for r in c.execute("SELECT * FROM study_task_runs WHERE code=?", (code,))}
        for tid, r in runs.items():
            ai = d["conditions"][S.condition_of(d, seq, tid)]["kind"] == "ai_contextual"
            self.assertEqual((r["aid_provider"], r["aid_simulated"]), ("SIMULATED-script", 1) if ai else ("fixed-template", 0))
            self.assertTrue(json.loads(r["aid_text"])["question"])
        ex = self.c("GET", "/api/study/export", None, ST)[1]
        self.assertTrue(ex["meta"]["simulated"])
        self.assertEqual(ex["meta"]["simulated_notice"], A.SIM_NOTICE)
        for r in ex["tasks"]:
            self.assertEqual(r["data_label"], "SIMULATED")
            self.assertEqual(r["no_model_used"], 1 if r["tool"] == "ai_contextual" else 0)
            self.assertEqual(r["tool_source"], "SIMULATED-script" if r["tool"] == "ai_contextual" else "fixed-template")
        csvtext = self.c("GET", "/api/study/export?format=csv&level=task", None, ST)[1]
        self.assertTrue(csvtext.startswith("# SIMULATION"))
        self.assertIn("No AI model was used", csvtext.split("\n")[1])
        # no free text in the export
        flat = json.dumps(ex)
        self.assertNotIn("Is the limit of 35 applied strictly", flat)
        self.assertEqual(self.c("GET", "/api/study/export?scope=formal", None, ST)[0], 403)

    def test_english_only_payloads(self):
        code, hdr, _ = self.enrol()
        starts = self.run_all(hdr)
        self.assertFalse(CJK.search(json.dumps(starts, ensure_ascii=False)))
        for t in starts.values():
            self.assertEqual(t["task"]["ad_text"], t["task"]["ad_text_en"])
        self.calibrate("R1")
        self.assertFalse(CJK.search(json.dumps(self.c("GET", "/api/study/calibration", None, self.rater("R1"))[1], ensure_ascii=False)))
        nx = self.c("GET", "/api/study/rater/next", None, self.rater("R1"))[1]
        self.assertFalse(CJK.search(json.dumps(nx, ensure_ascii=False)))

    def test_rater_blinded_and_gated(self):
        code, hdr, _ = self.enrol()
        self.run_all(hdr)
        self.assertEqual(self.c("GET", "/api/study/rater/next", None, {"X-Rater-Id": "R1"})[0], 401)
        self.assertEqual(self.c("GET", "/api/study/rater/next", None, self.rater("R1"))[0], 409)   # calibration first
        cal = self.c("GET", "/api/study/calibration", None, self.rater("R1"))[1]
        self.assertNotIn('"reference"', json.dumps(cal))
        self.calibrate("R1")
        nx = self.c("GET", "/api/study/rater/next", None, self.rater("R1"))[1]
        flat = json.dumps(nx)
        for bad in ("ai_contextual", "template", "Template", "Tool A", "Tool B", "Contextual", "SIMULATED", "condition", "sequence", "checklist", "provider", "participant", "AB-S", "BA-S"):
            self.assertNotIn(bad, flat, bad)
        self.assertIn("key_facts", flat)   # the rubric facts are the raters' own material
        self.assertEqual(set(nx["item"]), {"item_key", "task", "reading", "question"})

    def score_all(self, who, fn):
        n = 0
        while True:
            nx = self.c("GET", "/api/study/rater/next", None, self.rater(who))[1]
            if not nx["item"]:
                return n
            it = nx["item"]
            body = fn(it)
            body["item_key"] = it["item_key"]
            st, r = self.c("POST", "/api/study/rater/score", body, self.rater(who))
            self.assertEqual(st, 200, r)
            self.assertEqual(self.c("POST", "/api/study/rater/score", body, self.rater(who))[0], 409)   # no edits
            n += 1

    def test_full_scoring_resolution_and_export_numbers(self):
        self.fill(4)
        for w in RATERS:
            self.calibrate(w)
        # R1: all facts right, good question, 0 unsupported. R2: differs on the 3rd item only (one fact wrong, 1 unsupported)
        cnt = {"n": 0}

        def r1(it):
            ids = [f["id"] for f in it["task"]["key_facts"]]
            return {"facts": {i: True for i in ids}, "q1": True, "q2": True, "q3": True, "q4": True, "unsupported": 0}

        def r2(it):
            cnt["n"] += 1
            b = r1(it)
            if cnt["n"] % 4 == 0:
                b["facts"][it["task"]["key_facts"][0]["id"]] = False
                b["unsupported"] = 1
            return b
        self.assertEqual(self.score_all("R1", r1), 16)
        self.assertIsNone(self.c("GET", "/api/study/rater/next", None, self.rater("R3"))[1]["item"])   # nothing before R2
        self.assertEqual(self.score_all("R2", r2), 16)
        dis = self.c("GET", "/api/study/disagreements", None, self.rater("R1"))[1]
        self.assertEqual((dis["n"], dis["open"]), (4, 4))
        self.assertTrue(all("unsupported" in x["fields"] for x in dis["log"]))
        ex = self.c("GET", "/api/study/export", None, ST)[1]
        self.assertEqual(sum(1 for r in ex["tasks"] if r["resolution"] == "unresolved"), 4)
        self.assertEqual(self.score_all("R3", r1), 4)     # R3 sides with R1: majority 2 of 3
        ex = self.c("GET", "/api/study/export", None, ST)[1]
        self.assertEqual({r["resolution"] for r in ex["tasks"]}, {"agree", "adjudicated"})
        for r in ex["tasks"]:
            self.assertEqual((r["final_accuracy"], r["final_actionable"], r["final_unsupported"]), (1.0, 1, 0))
        for p in ex["participants"]:
            self.assertEqual((p["acc_template"], p["acc_ai"], p["diff_acc"], p["diff_uns"], p["diff_act"]), (1.0, 1.0, 0.0, 0.0, 0.0))
            self.assertIn(p["first_condition"], ("A", "B"))
        res = ST_.analyse(ex)
        self.assertIn("SIMULATED", res["label"])
        self.assertIn("No AI model was used", res["label"])
        self.assertFalse(res["primary_benefit"])
        self.assertIn("NO EVIDENCE OF BENEFIT", res["primary_decision"])

    def test_missing_answer_counts_zero_and_unscored_is_blank(self):
        code, hdr, _ = self.enrol()
        sess = self.c("GET", "/api/study/session", headers=hdr)[1]
        for i, step in enumerate(sess["steps"]):
            self.c("POST", "/api/study/task/%s/start" % step["task_id"], {}, hdr)
            self.c("POST", "/api/study/task/%s/submit" % step["task_id"], {"reading": "" if i == 3 else "x", "question": "" if i == 3 else "y?"}, hdr)
        ex = self.c("GET", "/api/study/export", None, ST)[1]
        miss = [r for r in ex["tasks"] if r["missing"] == 1]
        self.assertEqual(len(miss), 1)
        self.assertEqual((miss[0]["final_accuracy"], miss[0]["final_actionable"], miss[0]["final_unsupported"], miss[0]["resolution"]), (0.0, 0, 0, "missing"))
        self.assertEqual(ex["participants"][0]["diff_acc"], "")     # others unscored: unknown, excluded rather than guessed

    def test_withdraw_deletes_both_texts(self):
        code, hdr, _ = self.enrol()
        tid = self.c("GET", "/api/study/session", headers=hdr)[1]["steps"][0]["task_id"]
        self.c("POST", "/api/study/task/%s/start" % tid, {}, hdr)
        self.c("POST", "/api/study/task/%s/submit" % tid, {"reading": "private reading", "question": "private question?"}, hdr)
        self.assertEqual(self.c("POST", "/api/study/withdraw", {}, hdr)[0], 200)
        with S.conn() as c:
            r = c.execute("SELECT answer, reading, question_text, aid_text FROM study_task_runs WHERE code=?", (code,)).fetchone()
        self.assertEqual((r["answer"], r["reading"], r["question_text"], r["aid_text"]), (None, None, None, None))

    def test_validation_of_scores(self):
        self.fill(1)
        self.calibrate("R1")
        it = self.c("GET", "/api/study/rater/next", None, self.rater("R1"))[1]["item"]
        ids = [f["id"] for f in it["task"]["key_facts"]]
        ok = {"item_key": it["item_key"], "facts": {i: True for i in ids}, "q1": True, "q2": True, "q3": True, "q4": True, "unsupported": 0}
        for mutate in (lambda b: b.pop("facts"), lambda b: b["facts"].pop(ids[0]), lambda b: b.update(q2="yes"), lambda b: b.update(unsupported=-1),
                       lambda b: b.update(unsupported=11), lambda b: b.update(unsupported=True), lambda b: b.update(unsupported="1")):
            b = json.loads(json.dumps(ok))
            mutate(b)
            self.assertEqual(self.c("POST", "/api/study/rater/score", b, self.rater("R1"))[0], 400)
        self.assertEqual(self.c("POST", "/api/study/rater/score", ok, self.rater("R1"))[0], 200)


class Stats(unittest.TestCase):
    def test_exact_signflip_known_value(self):
        p, how = ST_.signflip_p([1, 1, 1, 1])
        self.assertAlmostEqual(p, 2 / 16)
        self.assertIn("exact", how)
        self.assertAlmostEqual(ST_.signflip_p([0.1, -0.1, 0.1, -0.1])[0], 1.0)
        self.assertAlmostEqual(ST_.signflip_p([1, 2, 3])[0], 2 / 8)

    def test_monte_carlo_used_above_exact_limit_and_reproducible(self):
        v = [0.1] * 12 + [0.2] * 8
        a, b = ST_.signflip_p(v), ST_.signflip_p(v)
        self.assertEqual(a, b)
        self.assertIn("Monte Carlo", a[1])
        self.assertLess(a[0], 0.001)

    def test_paired_and_bootstrap(self):
        r = ST_.paired([0.2, 0.1, 0.3, 0.0, 0.2, 0.1])
        self.assertAlmostEqual(r["mean"], 0.1500, places=4)
        self.assertLessEqual(r["ci95"][0], r["mean"] <= r["ci95"][1] and r["mean"])
        self.assertEqual(ST_.paired([0.1])["error"], "need at least 2 participants")
        self.assertEqual(ST_.paired([0.1, 0.2]), ST_.paired([0.1, 0.2]))   # seeded

    def test_holm(self):
        self.assertEqual(ST_.holm({"a": 0.01, "b": 0.04, "c": 0.03}), {"a": 0.03, "c": 0.06, "b": 0.06})

    def test_kappa(self):
        self.assertEqual(ST_.kappa([1, 0, 1, 0], [1, 0, 1, 0])[0], 1.0)
        self.assertEqual(ST_.kappa([1, 1, 0, 0], [1, 0, 1, 0]), (0.0, 0.5))

    def test_person_columns_and_unknowns(self):
        rows = [{"condition": "A", "final_accuracy": 0.5, "final_actionable": 0, "final_unsupported": 1, "completion_time_s": 100.0},
                {"condition": "A", "final_accuracy": 1.0, "final_actionable": 1, "final_unsupported": 0, "completion_time_s": 200.0},
                {"condition": "B", "final_accuracy": 1.0, "final_actionable": 1, "final_unsupported": 0, "completion_time_s": 60.0},
                {"condition": "B", "final_accuracy": 1.0, "final_actionable": 0, "final_unsupported": 0, "completion_time_s": 80.0}]
        c = ST_.person_columns(rows)
        self.assertEqual((c["acc_template"], c["acc_ai"], c["diff_acc"]), (0.75, 1.0, 0.25))
        self.assertEqual((c["act_template"], c["act_ai"], c["diff_act"]), (0.5, 0.5, 0.0))
        self.assertEqual((c["uns_template"], c["uns_ai"], c["diff_uns"]), (0.5, 0.0, -0.5))
        self.assertEqual((c["time_template"], c["time_ai"], c["diff_time"]), (150.0, 70.0, -80.0))
        rows[0]["final_accuracy"] = ""
        self.assertEqual(ST_.person_columns(rows)["diff_acc"], "")
        self.assertEqual(ST_.person_columns(rows)["diff_uns"], -0.5)   # other outcomes unaffected

    def test_unsupported_counts_and_accuracy_from_scored_facts(self):
        # accuracy = facts correct / facts; 2 of 4 facts -> 0.5
        self.assertEqual(2 / 4, 0.5)
        # median of three for the unsupported count when R1 and R2 differ
        from backend import study_ai
        sc = {r: {"facts": {"F1": 1}, "q1": 1, "q2": 1, "q3": 1, "q4": 1, "unsupported": u} for r, u in (("R1", 0), ("R2", 3), ("R3", 1))}
        res, fin, dis = study_ai.resolve(sc)
        self.assertEqual((res, fin["unsupported"], dis), ("adjudicated", 1, 1))
        sc["R2"]["unsupported"] = 0
        self.assertEqual(study_ai.resolve(sc)[0], "agree")
        sc["R2"]["unsupported"] = 2; del sc["R3"]
        self.assertEqual(study_ai.resolve(sc)[0], "unresolved")

    def synthetic(self, effect):
        parts = []
        for i in range(20):
            d = effect + (0.05 if i % 2 else -0.05)
            parts.append({"participant_code": "SIM-%d" % i, "sequence": "AB-S1", "first_condition": "A" if i % 2 else "B", "simulated": 1, "participant_status": "completed", "dropout": 0, "tasks_submitted": 4,
                          "acc_template": 0.6, "acc_ai": 0.6 + d, "diff_acc": round(d, 4), "act_template": 0.5, "act_ai": 0.5, "diff_act": 0.0,
                          "uns_template": 0.5, "uns_ai": 0.5, "diff_uns": 0.0, "time_template": 100.0, "time_ai": 100.0, "diff_time": 0.0})
        return {"meta": {"design": "crossover-ai-v1", "simulated": True, "schema": "export-ai-v1", "scope": "simulated", "generated_at": "x", "tasks_version": "v", "rubric_version": "r"},
                "participants": parts, "tasks": []}

    def test_analysis_decision_rule(self):
        hi = ST_.analyse(self.synthetic(0.2))
        self.assertTrue(hi["primary_benefit"])
        self.assertIn("EVIDENCE OF BENEFIT", hi["primary_decision"])
        self.assertFalse(hi["safety_signal"])
        lo = ST_.analyse(self.synthetic(0.05))
        self.assertFalse(lo["primary_benefit"])      # mean below the pre-specified +0.10
        self.assertIn("not evidence that the AI does not help", lo["primary_decision"])
        self.assertIn("SIMULATED", ST_.render(hi))
        self.assertIn("NOT results", ST_.render(hi))
        s = self.synthetic(0.2)
        for p in s["participants"]:
            p["diff_uns"], p["uns_ai"] = 0.5 + (0.1 if p["sequence"] else 0), 1.0
        self.assertTrue(ST_.analyse(s)["safety_signal"])


if __name__ == "__main__":
    unittest.main()
