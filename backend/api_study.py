"""Evaluation tools: participant sessions, blinded scoring, anonymous export. See docs/EVAL_PROTOCOL.md.

Safety rules enforced HERE (server-side), not in the UI:
  * mode defaults to 'simulation'. 'formal' is refused unless data/study/APPROVAL.json is complete and
    valid, the task file hash matches it, and a model is connected. This module never creates that file.
  * simulated sessions carry simulated=1; every export is scoped to ONE of simulated/formal, and the
    formal export refuses simulated rows by construction.
  * raters never receive arm, participant code or other raters' scores; participants never receive
    scores, other participants' data or their own arm name.
  * demo-grade access: a local study token (data/study/study_token or AGELENS_STUDY_TOKEN) + a rater
    label R1/R2/R3. This is NOT production authentication.
"""
import csv
import hashlib
import io
import json
import os
import random
import re
import secrets
import time
from datetime import datetime, timezone

from . import db, study_arms
from .server import HTTPError, Response, hash_token

STUDY_DIR = db.DATA_DIR / "study"
TASKS_PATH = STUDY_DIR / "tasks.json"
APPROVAL_PATH = STUDY_DIR / "APPROVAL.json"
SIM_SEED = 20261023          # documented allocation seed for SIMULATION mode only
BLOCK_SIZE = 4               # permuted blocks: crossover = one of each of the 4 sequences; legacy = 2 template + 2 assisted
LEGACY_DESIGN = "parallel-llm-v0"
DESIGN_OVERRIDE = None       # tests may force LEGACY_DESIGN; otherwise tasks.json "design" decides
AID_LABELS = {"template": "Fixed template", "assisted": "Drafted help", "none": "Ad only", "agelens": "AgeLens evidence check"}
RATERS = ("R1", "R2", "R3")
CRITERIA = ("c1", "c2", "c3", "c4")
SCHEMA_VERSION = "export-v2"
BANNER = "SIMULATION — not study data"
GRACE_MS = 5000
INACTIVE_MIN = 60            # pre-specified: unfinished + no activity this long = dropout (unless withdrawn earlier)
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

SCHEMA = """
CREATE TABLE IF NOT EXISTS study_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS study_participants (
  code TEXT PRIMARY KEY, token_hash TEXT NOT NULL, arm TEXT NOT NULL, mode TEXT NOT NULL,
  simulated INTEGER NOT NULL, block_no INTEGER NOT NULL, block_pos INTEGER NOT NULL, task_order TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'enrolled', consent_version TEXT, consent_at TEXT, enrolled_at TEXT NOT NULL,
  last_activity_ms INTEGER NOT NULL, withdrawn_at TEXT);
CREATE TABLE IF NOT EXISTS study_task_runs (
  code TEXT NOT NULL, task_id TEXT NOT NULL, item_key TEXT NOT NULL, position INTEGER NOT NULL,
  started_ms INTEGER NOT NULL, submitted_ms INTEGER, limit_ms INTEGER NOT NULL, elapsed_ms INTEGER,
  client_elapsed_ms INTEGER, late INTEGER NOT NULL DEFAULT 0, timed_out INTEGER NOT NULL DEFAULT 0,
  answer TEXT, answer_chars INTEGER, aid_kind TEXT, aid_text TEXT, aid_provider TEXT, aid_simulated INTEGER,
  aid_inserted INTEGER NOT NULL DEFAULT 0, model_failure INTEGER NOT NULL DEFAULT 0, model_error TEXT,
  aid_latency_ms INTEGER, state TEXT NOT NULL DEFAULT 'started', PRIMARY KEY (code, task_id));
CREATE UNIQUE INDEX IF NOT EXISTS ix_study_item ON study_task_runs(item_key);
CREATE TABLE IF NOT EXISTS study_scores (
  item_key TEXT NOT NULL, rater TEXT NOT NULL, c1 INTEGER NOT NULL, c2 INTEGER NOT NULL, c3 INTEGER NOT NULL, c4 INTEGER NOT NULL,
  severe INTEGER NOT NULL, notes TEXT, scored_at TEXT NOT NULL, PRIMARY KEY (item_key, rater));
CREATE TABLE IF NOT EXISTS study_calibration (
  rater TEXT NOT NULL, cal_id TEXT NOT NULL, c1 INTEGER NOT NULL, c2 INTEGER NOT NULL, c3 INTEGER NOT NULL, c4 INTEGER NOT NULL,
  severe INTEGER NOT NULL, notes TEXT, scored_at TEXT NOT NULL, PRIMARY KEY (rater, cal_id));
"""


# ---- helpers ----------------------------------------------------------------------------------
def design(doc=None):
    """-> the crossover design dict from tasks.json, or None for the legacy parallel design."""
    doc = doc or load_tasks()
    if DESIGN_OVERRIDE == LEGACY_DESIGN or not isinstance(doc.get("design"), dict):
        return None
    return doc["design"]


def design_id(doc=None):
    d = design(doc)
    return d["id"] if d else LEGACY_DESIGN


def condition_of(d, seq, tid):
    """Crossover: 'B' (AgeLens) if the task is in the sequence's B set, else 'A' (ad only)."""
    return "B" if tid in d["task_sets"][seq.split("-")[1]] else "A"


def crossover_order(d, doc, seq, salt):
    """Task order for a sequence 'XY-Sk': the two tasks of condition X, then the two of Y; each half shuffled with the salt."""
    ids = [t["id"] for t in doc["tasks"]]
    b, a = [t for t in ids if condition_of(d, seq, t) == "B"], [t for t in ids if condition_of(d, seq, t) == "A"]
    halves = [a, b] if seq[0] == "A" else [b, a]
    for i, half in enumerate(halves):
        random.Random("%s|half%d" % (salt, i)).shuffle(half)
    return halves[0] + halves[1]



def now_ms():
    return int(time.time() * 1000)


def iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def conn():
    c = db.connect()
    c.executescript(SCHEMA)
    return c


def load_tasks():
    return json.loads(TASKS_PATH.read_text(encoding="utf-8"))


def tasks_sha256():
    return hashlib.sha256(TASKS_PATH.read_bytes()).hexdigest()


def task_by_id(doc, tid):
    for t in doc["tasks"]:
        if t["id"] == tid:
            return t
    return None


def study_token():
    env = os.environ.get("AGELENS_STUDY_TOKEN")
    if env:
        return env
    f = STUDY_DIR / "study_token"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(secrets.token_urlsafe(12))
        f.chmod(0o600)
    return f.read_text().strip()


def require_study(req, raters=None):
    got = req.headers.get("X-Study-Token", "")
    if not got or not secrets.compare_digest(got, study_token()):
        raise HTTPError(401, "This needs the local study token (demo-grade access).")
    rater = req.headers.get("X-Rater-Id", "")
    if raters is not None:
        if rater not in raters:
            raise HTTPError(400, "Choose a rater label: " + ", ".join(raters) + ".")
        return rater
    return rater or None


def get_setting(c, key, default=None):
    r = c.execute("SELECT value FROM study_settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(c, key, value):
    c.execute("INSERT INTO study_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def item_salt(c):
    s = get_setting(c, "item_salt")
    if not s:
        s = secrets.token_hex(8)
        set_setting(c, "item_salt", s)
    return s


# ---- formal-mode gate -------------------------------------------------------------------------

def read_approval():
    """-> (approval dict | None, problems[])  — never writes."""
    try:
        raw = APPROVAL_PATH.read_text(encoding="utf-8")
    except OSError:
        return None, ["data/study/APPROVAL.json does not exist (teacher approval has not been recorded)."]
    try:
        a = json.loads(raw)
    except ValueError:
        return None, ["APPROVAL.json is not valid JSON."]
    if not isinstance(a, dict):
        return None, ["APPROVAL.json must be a JSON object."]
    p = []
    s = lambda k: isinstance(a.get(k), str) and a[k].strip()
    if a.get("approved") is not True:
        p.append('APPROVAL.json must contain "approved": true.')
    for k in ("teacher_name", "approval_date", "protocol_version", "assignment_mechanism", "stopping_rule"):
        if not s(k):
            p.append("APPROVAL.json missing field: %s." % k)
    if s("approval_date") and not re.match(r"^\d{4}-\d{2}-\d{2}$", a["approval_date"]):
        p.append("approval_date must be YYYY-MM-DD.")
    if not (isinstance(a.get("recruitment_target"), int) and a["recruitment_target"] > 0):
        p.append("recruitment_target must be a positive integer.")
    if not (isinstance(a.get("allocation_seed"), int) and not isinstance(a.get("allocation_seed"), bool)):
        p.append("allocation_seed must be an integer set by the approver.")
    pr = a.get("preregistration")
    if not isinstance(pr, dict) or not str(pr.get("reference") or "").strip():
        p.append("preregistration.reference (registry id / URL) is required.")
    elif not re.match(r"^[0-9a-f]{64}$", str(pr.get("sha256") or "")):
        p.append("preregistration.sha256 must be the 64-hex hash of the filed document.")
    if a.get("tasks_sha256") != tasks_sha256():
        p.append("tasks_sha256 does not match data/study/tasks.json (tasks must be frozen exactly as approved).")
    return a, p


def formal_blockers():
    _, problems = read_approval()
    ms = study_arms.model_status()
    if design() is None and not ms["connected"]:  # only the legacy model-vs-template design needs a model
        problems = problems + ["No model is connected (Template demo). A formal trial needs the model arm to be real."]
    return problems


def current_mode(c):
    m = get_setting(c, "mode", "simulation")
    if m == "formal" and formal_blockers():
        return "simulation"  # approval withdrawn/invalid: fall back safely, never run formal silently
    return m if m in ("simulation", "formal") else "simulation"


def alloc_seed(mode):
    if mode == "simulation":
        return SIM_SEED
    a, _ = read_approval()
    return int(a["allocation_seed"])


def allocate(c, mode):
    n = c.execute("SELECT COUNT(*) FROM study_participants WHERE mode=?", (mode,)).fetchone()[0]
    block, pos = divmod(n, BLOCK_SIZE)
    d = design()
    arms = list(d["sequences"]) if d else ["template"] * (BLOCK_SIZE // 2) + ["assisted"] * (BLOCK_SIZE // 2)
    random.Random("%s|%s|%d" % (alloc_seed(mode), mode, block)).shuffle(arms)
    return arms[pos], block, pos


# ---- participant side -------------------------------------------------------------------------

def participant(c, req):
    tok = req.headers.get("X-Participant-Token", "")
    code = req.headers.get("X-Participant-Code", "")
    if not tok or not code:
        raise HTTPError(401, "Missing participant session.")
    r = c.execute("SELECT * FROM study_participants WHERE code=?", (code,)).fetchone()
    if not r or not secrets.compare_digest(r["token_hash"], hash_token(tok)):
        raise HTTPError(401, "Unknown participant session.")
    return r


def public_config(c):
    doc = load_tasks()
    mode = current_mode(c)
    ms = study_arms.model_status()
    blockers = formal_blockers()
    return {"mode": mode, "requested_mode": get_setting(c, "mode", "simulation"), "simulated": mode == "simulation",
            "banner": BANNER if mode == "simulation" else None, "model": ms,
            "formal_allowed": not blockers, "formal_blockers": blockers,
            "tasks_version": doc["version"], "tasks_status": doc["_status"], "consent_draft": doc["consent_draft"],
            "instructions": doc["instructions"], "n_tasks": len(doc["tasks"]), "time_limit_s": time_limit_s(c, doc),
            "template_aid": doc["template_aid"]["label"], "design": design_id(doc),
            "conditions": {k: v["label"] for k, v in design(doc)["conditions"].items()} if design(doc) else None}


def time_limit_s(c, doc):
    o = get_setting(c, "sim_time_limit_s")
    if o and current_mode(c) == "simulation":
        return int(o)
    return int(doc["time_limit_s"])


def task_payload(task):
    return {k: task[k] for k in ("id", "kind", "title", "ad_id", "job_title", "ad_text", "gloss", "profile", "question")}


def session_view(c, p):
    doc = load_tasks()
    order = json.loads(p["task_order"])
    runs = {r["task_id"]: r for r in c.execute("SELECT * FROM study_task_runs WHERE code=?", (p["code"],))}
    steps = []
    for i, tid in enumerate(order):
        r = runs.get(tid)
        steps.append({"task_id": tid, "position": i + 1, "state": r["state"] if r else "todo"})
    done = sum(1 for s in steps if s["state"] == "submitted")
    crossover = design(doc) is not None and "-" in p["arm"]
    return {"code": p["code"], "status": p["status"], "simulated": bool(p["simulated"]), "mode": p["mode"], "design": design_id(doc),
            "aid_kind": "crossover" if crossover else p["arm"],
            "aid_label": "Ad only on two tasks, AgeLens evidence check on two" if crossover else (study_arms.template_aid(doc)["label"] if p["arm"] == "template" else "Drafted help"),
            "steps": steps, "done": done, "total": len(order), "time_limit_s": int(time_limit_s(c, doc))}


def register(router):
    @router.get("/api/study/config")
    def config(req):
        with conn() as c:
            return public_config(c)

    @router.post("/api/study/mode")
    def set_mode(req):
        require_study(req)
        want = str(req.json().get("mode") or "")
        if want not in ("simulation", "formal"):
            raise HTTPError(400, "mode must be 'simulation' or 'formal'.")
        if want == "formal":
            blockers = formal_blockers()
            if blockers:
                return 403, {"error": "Formal mode is refused: the approvals required for a formal trial are not in place (see blockers).",
                             "blockers": blockers, "mode": "simulation"}
        with conn() as c:
            set_setting(c, "mode", want)
            return public_config(c)

    @router.post("/api/study/sim-time-limit")
    def sim_limit(req):
        require_study(req)
        with conn() as c:
            if current_mode(c) != "simulation":
                raise HTTPError(403, "The time limit can only be shortened in simulation mode.")
            v = req.json().get("seconds")
            if v in (None, "", 0):
                c.execute("DELETE FROM study_settings WHERE key='sim_time_limit_s'")
            else:
                if not isinstance(v, int) or not 5 <= v <= 3600:
                    raise HTTPError(400, "seconds must be an integer 5-3600.")
                set_setting(c, "sim_time_limit_s", v)
            return public_config(c)

    @router.post("/api/study/enrol")
    def enrol(req):
        body = req.json()
        if body.get("consent") is not True:
            raise HTTPError(400, "Consent is required to take part. Nothing was recorded.")
        doc = load_tasks()
        with conn() as c:
            c.execute("BEGIN IMMEDIATE")
            mode = get_setting(c, "mode", "simulation")
            if mode == "formal":
                blockers = formal_blockers()
                if blockers:
                    c.rollback()
                    return 403, {"error": "Formal enrolment is refused: the approvals required for a formal trial are not in place (see blockers).", "blockers": blockers}
            else:
                mode = "simulation"
            arm, block, pos = allocate(c, mode)
            code = ("SIM-" if mode == "simulation" else "P-") + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
            token = secrets.token_urlsafe(18)
            d = design(doc)
            if d:
                order = crossover_order(d, doc, arm, "%s|order|%s" % (alloc_seed(mode), code))
            else:
                order = [t["id"] for t in doc["tasks"]]
                random.Random("%s|order|%s" % (alloc_seed(mode), code)).shuffle(order)
            c.execute("INSERT INTO study_participants(code,token_hash,arm,mode,simulated,block_no,block_pos,task_order,status,consent_version,consent_at,enrolled_at,last_activity_ms) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (code, hash_token(token), arm, mode, 1 if mode == "simulation" else 0, block, pos, json.dumps(order), "enrolled",
                       doc["version"] + "/consent-draft", iso(), iso(), now_ms()))
            c.commit()
            p = c.execute("SELECT * FROM study_participants WHERE code=?", (code,)).fetchone()
            return {"code": code, "token": token, "session": session_view(c, p)}

    @router.get("/api/study/session")
    def session(req):
        with conn() as c:
            return session_view(c, participant(c, req))

    @router.post("/api/study/task/<tid>/start")
    def start(req):
        doc = load_tasks()
        task = task_by_id(doc, req.params["tid"])
        if not task:
            raise HTTPError(404, "Unknown task.")
        with conn() as c:
            p = participant(c, req)
            if p["status"] == "withdrawn":
                raise HTTPError(409, "You have withdrawn from the study.")
            order = json.loads(p["task_order"])
            idx = order.index(task["id"])
            for prev in order[:idx]:
                r = c.execute("SELECT state FROM study_task_runs WHERE code=? AND task_id=?", (p["code"], prev)).fetchone()
                if not r or r["state"] != "submitted":
                    raise HTTPError(409, "Please finish the earlier task first.")
            run = c.execute("SELECT * FROM study_task_runs WHERE code=? AND task_id=?", (p["code"], task["id"])).fetchone()
            if run is None:
                limit_ms = time_limit_s(c, doc) * 1000
                d = design(doc)
                if d and "-" in p["arm"]:
                    aid = study_arms.agelens_aid(task) if condition_of(d, p["arm"], task["id"]) == "B" else study_arms.no_aid()
                elif p["arm"] == "template":
                    aid = study_arms.template_aid(doc)
                else:
                    aid = study_arms.assisted_aid(task, simulation_ok=(p["mode"] == "simulation"))
                key = hashlib.sha256((item_salt(c) + "|" + p["code"] + "|" + task["id"]).encode()).hexdigest()[:12]
                c.execute("INSERT INTO study_task_runs(code,task_id,item_key,position,started_ms,limit_ms,aid_kind,aid_text,aid_provider,aid_simulated,model_failure,model_error,aid_latency_ms) "
                          "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                          (p["code"], task["id"], key, idx + 1, now_ms(), limit_ms, aid["kind"], aid.get("text", ""), aid.get("provider"),
                           1 if aid.get("simulated") else 0, 1 if aid.get("failed") else 0, aid.get("error"), aid.get("latency_ms")))
                c.execute("UPDATE study_participants SET status='in_progress', last_activity_ms=? WHERE code=?", (now_ms(), p["code"]))
                run = c.execute("SELECT * FROM study_task_runs WHERE code=? AND task_id=?", (p["code"], task["id"])).fetchone()
            remaining = max(0, run["started_ms"] + run["limit_ms"] - now_ms())
            return {"task": task_payload(task), "position": run["position"], "total": len(order), "remaining_ms": remaining,
                    "limit_ms": run["limit_ms"], "state": run["state"], "answer": run["answer"] if run["state"] == "submitted" else "",
                    "aid": {"kind": run["aid_kind"], "label": AID_LABELS.get(run["aid_kind"], run["aid_kind"]),
                            "text": run["aid_text"], "simulated": bool(run["aid_simulated"]), "failed": bool(run["model_failure"]),
                            "provider": run["aid_provider"]}}

    @router.post("/api/study/task/<tid>/submit")
    def submit(req):
        body = req.json()
        answer = str(body.get("answer") or "")[:6000]
        with conn() as c:
            p = participant(c, req)
            run = c.execute("SELECT * FROM study_task_runs WHERE code=? AND task_id=?", (p["code"], req.params["tid"])).fetchone()
            if not run:
                raise HTTPError(409, "This task was not started.")
            if run["state"] == "submitted":
                return {"ok": True, "already": True, "session": session_view(c, p)}
            t = now_ms()
            elapsed = t - run["started_ms"]
            late = elapsed > run["limit_ms"] + GRACE_MS
            timed_out = bool(body.get("timed_out")) or elapsed >= run["limit_ms"]
            cel = body.get("client_elapsed_ms")
            cel = int(cel) if isinstance(cel, (int, float)) and 0 <= cel < 10 ** 9 else None
            c.execute("UPDATE study_task_runs SET state='submitted', submitted_ms=?, elapsed_ms=?, client_elapsed_ms=?, late=?, timed_out=?, answer=?, answer_chars=?, aid_inserted=? WHERE code=? AND task_id=?",
                      (t, elapsed, cel, 1 if late else 0, 1 if timed_out else 0, answer, len(answer.strip()), 1 if body.get("aid_inserted") else 0, p["code"], req.params["tid"]))
            done = c.execute("SELECT COUNT(*) FROM study_task_runs WHERE code=? AND state='submitted'", (p["code"],)).fetchone()[0]
            c.execute("UPDATE study_participants SET last_activity_ms=?, status=? WHERE code=?",
                      (t, "completed" if done >= len(json.loads(p["task_order"])) else "in_progress", p["code"]))
            p = c.execute("SELECT * FROM study_participants WHERE code=?", (p["code"],)).fetchone()
            return {"ok": True, "late": late, "session": session_view(c, p)}

    @router.post("/api/study/withdraw")
    def withdraw(req):
        with conn() as c:
            p = participant(c, req)
            c.execute("UPDATE study_participants SET status='withdrawn', withdrawn_at=?, last_activity_ms=? WHERE code=?", (iso(), now_ms(), p["code"]))
            c.execute("UPDATE study_task_runs SET answer=NULL, answer_chars=0, aid_text=NULL, state=CASE WHEN state='submitted' THEN 'withdrawn' ELSE state END WHERE code=?", (p["code"],))
            return {"ok": True, "message": "You have withdrawn. The text you wrote was deleted; only the fact that you withdrew is kept."}

    # ---- raters -------------------------------------------------------------------------------

    def cal_status(c, rater, doc):
        got = {r["cal_id"]: r for r in c.execute("SELECT * FROM study_calibration WHERE rater=?", (rater,))}
        return got, len(got) >= len(doc["calibration"])

    @router.get("/api/study/rater/status")
    def rater_status(req):
        rater = require_study(req, RATERS)
        doc = load_tasks()
        with conn() as c:
            got, done = cal_status(c, rater, doc)
            mode = current_mode(c)
            sim = 1 if mode == "simulation" else 0
            items = c.execute("SELECT item_key FROM study_task_runs r JOIN study_participants p USING(code) WHERE r.state='submitted' AND r.answer_chars>0 AND p.simulated=?", (sim,)).fetchall()
            mine = c.execute("SELECT COUNT(*) FROM study_scores s WHERE rater=? AND item_key IN (SELECT item_key FROM study_task_runs r JOIN study_participants p USING(code) WHERE p.simulated=?)", (rater, sim)).fetchone()[0]
            return {"rater": rater, "mode": mode, "banner": BANNER if sim else None, "calibration_done": done,
                    "calibration_items": len(doc["calibration"]), "calibration_scored": len(got),
                    "scorable_items": len(items), "scored_by_me": mine, "rubric": doc["rubric"]}

    def cal_view(item, doc):
        return {"id": item["id"], "task": task_payload(task_by_id(doc, item["task_id"])), "answer": item["answer"]}

    @router.get("/api/study/calibration")
    def calibration(req):
        rater = require_study(req, RATERS)
        doc = load_tasks()
        with conn() as c:
            got, done = cal_status(c, rater, doc)
            return {"items": [dict(cal_view(i, doc), scored=i["id"] in got) for i in doc["calibration"]], "done": done}

    def parse_score(body):
        out = {}
        for k in CRITERIA + ("severe",):
            if not isinstance(body.get(k), bool):
                raise HTTPError(400, "Answer every criterion with yes or no, and set the severe-error flag.")
            out[k] = 1 if body[k] else 0
        out["notes"] = str(body.get("notes") or "")[:500]
        return out

    @router.post("/api/study/calibration/<cid>")
    def calibration_score(req):
        rater = require_study(req, RATERS)
        doc = load_tasks()
        item = next((i for i in doc["calibration"] if i["id"] == req.params["cid"]), None)
        if not item:
            raise HTTPError(404, "Unknown calibration item.")
        s = parse_score(req.json())
        with conn() as c:
            c.execute("INSERT INTO study_calibration(rater,cal_id,c1,c2,c3,c4,severe,notes,scored_at) VALUES(?,?,?,?,?,?,?,?,?) "
                      "ON CONFLICT(rater,cal_id) DO UPDATE SET c1=excluded.c1,c2=excluded.c2,c3=excluded.c3,c4=excluded.c4,severe=excluded.severe,notes=excluded.notes,scored_at=excluded.scored_at",
                      (rater, item["id"], s["c1"], s["c2"], s["c3"], s["c4"], s["severe"], s["notes"], iso()))
        ref = item["reference"]
        match = {k: bool(s[k]) == ref[k] for k in CRITERIA + ("severe",)}
        return {"reference": ref, "rationale": item["rationale"], "match": match, "agreed": sum(match.values()), "of": 5}

    @router.get("/api/study/calibration/summary")
    def calibration_summary(req):
        rater = require_study(req, RATERS)
        doc = load_tasks()
        with conn() as c:
            rows = {r["cal_id"]: r for r in c.execute("SELECT * FROM study_calibration WHERE rater=?", (rater,))}
        agree = total = severe_miss = 0
        for it in doc["calibration"]:
            r = rows.get(it["id"])
            if not r:
                continue
            for k in CRITERIA + ("severe",):
                total += 1
                agree += (bool(r[k]) == it["reference"][k])
            severe_miss += (bool(r["severe"]) != it["reference"]["severe"])
        pct = agree / total if total else 0
        return {"agreement": round(pct, 3), "judgements": total, "severe_mismatches": severe_miss,
                "target_met": total == 5 * len(doc["calibration"]) and pct >= 0.9 and severe_miss == 0}

    def scorable(c, sim):
        return c.execute("SELECT r.item_key, r.task_id, r.answer FROM study_task_runs r JOIN study_participants p USING(code) "
                         "WHERE r.state='submitted' AND r.answer_chars>0 AND p.simulated=? AND p.status!='withdrawn'", (sim,)).fetchall()

    def disagreement_keys(c, sim):
        keys = []
        for it in scorable(c, sim):
            a = c.execute("SELECT * FROM study_scores WHERE item_key=? AND rater='R1'", (it["item_key"],)).fetchone()
            b = c.execute("SELECT * FROM study_scores WHERE item_key=? AND rater='R2'", (it["item_key"],)).fetchone()
            if a and b and any(a[k] != b[k] for k in CRITERIA + ("severe",)):
                keys.append(it["item_key"])
        return keys

    @router.get("/api/study/rater/next")
    def rater_next(req):
        rater = require_study(req, RATERS)
        doc = load_tasks()
        with conn() as c:
            _, done = cal_status(c, rater, doc)
            if not done:
                raise HTTPError(409, "Finish the calibration set first (Scoring > Calibration).")
            sim = 1 if current_mode(c) == "simulation" else 0
            mine = {r["item_key"] for r in c.execute("SELECT item_key FROM study_scores WHERE rater=?", (rater,))}
            if rater == "R3":
                pool = [it for it in scorable(c, sim) if it["item_key"] in set(disagreement_keys(c, sim))]
            else:
                pool = scorable(c, sim)
            pool = [it for it in pool if it["item_key"] not in mine]
            remaining = len(pool)
            if not pool:
                return {"item": None, "remaining": 0}
            pool.sort(key=lambda it: hashlib.sha256((rater + it["item_key"]).encode()).hexdigest())
            it = pool[0]
            return {"item": {"item_key": it["item_key"], "task": task_payload(task_by_id(doc, it["task_id"])), "answer": it["answer"]}, "remaining": remaining}

    @router.post("/api/study/rater/score")
    def rater_score(req):
        rater = require_study(req, RATERS)
        body = req.json()
        s = parse_score(body)
        key = str(body.get("item_key") or "")
        doc = load_tasks()
        with conn() as c:
            _, done = cal_status(c, rater, doc)
            if not done:
                raise HTTPError(409, "Finish the calibration set first.")
            sim = 1 if current_mode(c) == "simulation" else 0
            ok = [it for it in scorable(c, sim) if it["item_key"] == key]
            if not ok:
                raise HTTPError(404, "That item is not available for scoring.")
            if rater == "R3" and key not in set(disagreement_keys(c, sim)):
                raise HTTPError(403, "R3 scores only items where R1 and R2 disagree.")
            if c.execute("SELECT 1 FROM study_scores WHERE item_key=? AND rater=?", (key, rater)).fetchone():
                raise HTTPError(409, "You already scored this item; scores are not edited after submission.")
            c.execute("INSERT INTO study_scores(item_key,rater,c1,c2,c3,c4,severe,notes,scored_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (key, rater, s["c1"], s["c2"], s["c3"], s["c4"], s["severe"], s["notes"], iso()))
            return {"ok": True}

    @router.get("/api/study/disagreements")
    def disagreements(req):
        require_study(req, RATERS)
        with conn() as c:
            sim = 1 if current_mode(c) == "simulation" else 0
            log = []
            for key in disagreement_keys(c, sim):
                a = c.execute("SELECT * FROM study_scores WHERE item_key=? AND rater='R1'", (key,)).fetchone()
                b = c.execute("SELECT * FROM study_scores WHERE item_key=? AND rater='R2'", (key,)).fetchone()
                r3 = c.execute("SELECT 1 FROM study_scores WHERE item_key=? AND rater='R3'", (key,)).fetchone()
                log.append({"item": key, "fields": [k for k in CRITERIA + ("severe",) if a[k] != b[k]], "r3_done": bool(r3)})
            return {"rule": load_tasks()["rubric"]["disagreement_rule"], "n": len(log), "open": sum(1 for x in log if not x["r3_done"]), "log": log}

    # ---- operator -----------------------------------------------------------------------------

    @router.post("/api/study/simulated/clear")
    def clear_sim(req):
        require_study(req)
        with conn() as c:
            keys = [r["item_key"] for r in c.execute("SELECT item_key FROM study_task_runs r JOIN study_participants p USING(code) WHERE p.simulated=1")]
            for k in keys:
                c.execute("DELETE FROM study_scores WHERE item_key=?", (k,))
            c.execute("DELETE FROM study_task_runs WHERE code IN (SELECT code FROM study_participants WHERE simulated=1)")
            n = c.execute("DELETE FROM study_participants WHERE simulated=1").rowcount
            c.execute("DELETE FROM study_calibration WHERE 1=1")
            return {"deleted_participants": n}

    @router.get("/api/study/export")
    def export(req):
        require_study(req)
        scope = req.query.get("scope", "simulated")
        fmt = req.query.get("format", "json")
        level = req.query.get("level", "task")
        if scope not in ("simulated", "formal") or fmt not in ("json", "csv") or level not in ("task", "participant"):
            raise HTTPError(400, "scope=simulated|formal, format=json|csv, level=task|participant.")
        if scope == "formal":
            blockers = formal_blockers()
            if blockers:
                return 403, {"error": "A formal export is refused: no approved formal trial is configured.", "blockers": blockers}
        with conn() as c:
            data = build_export(c, scope)
        stamp = ("SIMULATED_" if scope == "simulated" else "") + "agelens_study_" + level
        if fmt == "json":
            return Response(json.dumps(data, ensure_ascii=False, indent=1), 200, "application/json; charset=utf-8",
                            {"Content-Disposition": 'attachment; filename="%s.json"' % stamp})
        rows = data["tasks"] if level == "task" else data["participants"]
        buf = io.StringIO()
        buf.write("# %s | schema %s | generated %s | simulated=%s\n" % (data["meta"]["banner"] or "FORMAL", SCHEMA_VERSION, data["meta"]["generated_at"], int(scope == "simulated")))
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) if rows else ["empty"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
        return Response(buf.getvalue(), 200, "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="%s.csv"' % stamp})

    @router.get("/api/study/export-schema")
    def export_schema(req):
        return EXPORT_FIELDS


EXPORT_FIELDS = {
    "version": SCHEMA_VERSION,
    "note": "Anonymous: participant codes only; no free text (answers and rater notes are NOT exported; only length and presence). Simulated exports carry simulated=1 and a SIMULATION banner; formal exports never contain simulated rows.",
    "task_level": {
        "participant_code": "random code, no link to identity", "arm": "crossover: sequence AB-S1 | AB-S2 | BA-S1 | BA-S2; legacy: template | assisted (the registered allocation)",
        "condition": "crossover: A (ad only) | B (AgeLens evidence check); blank in the legacy design", "simulated": "1 = simulated session, 0 = formal",
        "task_id": "T1..T4", "task_kind": "age_cap | qualification_exception | age_preference | incomplete_evidence", "position": "order shown (1-4)",
        "attempted": "1 if the task was started", "submitted": "1 if an answer was saved", "missing": "1 if not submitted OR empty answer (counted not usable)",
        "timed_out": "1 if the time limit ran out", "late": "1 if the answer arrived more than 5 s after the limit", "elapsed_s": "server-measured seconds from task start to submit",
        "time_limit_s": "limit applied", "answer_chars": "length of the answer after trimming", "aid_inserted": "1 if the participant used the insert button",
        "aid_provider": "fixed-template | SIMULATED | model | none", "aid_simulated": "1 if the aid text came from the simulated provider", "model_failure": "1 if the model call failed",
        "r1_c1..r2_severe": "each rater's yes(1)/no(0) per criterion and severe flag; blank = not scored", "disagreement": "1 if R1 and R2 differ on any field",
        "resolution": "agree | adjudicated | unresolved | unscored | missing", "final_c1..final_severe": "R1=R2 value, else majority of R1,R2,R3 (blank if unresolved)",
        "final_usable": "1 if final c1-c4 all 1 and final severe 0; 0 if missing or not; blank if unresolved/unscored", "participant_status": "completed | in_progress | withdrawn | enrolled", "dropout": "1 if withdrawn, or unfinished and inactive > %d min" % INACTIVE_MIN},
    "participant_level": {"participant_code": "", "arm": "", "simulated": "", "block_no": "allocation block", "tasks_attempted": "0-4", "tasks_submitted": "0-4", "tasks_missing": "4 - usable-evaluable tasks with answers",
                          "n_usable": "usable tasks of 4 (missing count as 0; blank if any answer unresolved/unscored)", "usable_share": "n_usable / 4 (legacy PRIMARY outcome; crossover: overall usable share, secondary)", "usable_ge3": "1 if n_usable >= 3 (secondary)",
                          "total_elapsed_s": "sum over submitted tasks", "model_failures": "count", "participant_status": "", "dropout": "",
                          "sequence": "crossover only: AB-S1 | AB-S2 | BA-S1 | BA-S2", "first_condition": "crossover only: A or B (period 1)",
                          "usable_share_A": "crossover only: usable share over the 2 ad-only tasks", "usable_share_B": "crossover only: usable share over the 2 AgeLens tasks",
                          "diff_B_minus_A": "crossover PRIMARY outcome: usable_share_B - usable_share_A (blank if any task unresolved/unscored)"},
}


def majority(vals):
    return 1 if sum(vals) * 2 > len(vals) else 0


def build_export(c, scope):
    sim = 1 if scope == "simulated" else 0
    doc = load_tasks()
    kinds = {t["id"]: t["kind"] for t in doc["tasks"]}
    dsg = design(doc)
    plist = c.execute("SELECT * FROM study_participants WHERE simulated=? ORDER BY enrolled_at, code", (sim,)).fetchall()
    scores = {}
    for r in c.execute("SELECT * FROM study_scores"):
        scores.setdefault(r["item_key"], {})[r["rater"]] = r
    t_now = now_ms()
    task_rows, part_rows = [], []
    for p in plist:
        runs = {r["task_id"]: r for r in c.execute("SELECT * FROM study_task_runs WHERE code=?", (p["code"],))}
        dropout = int(p["status"] == "withdrawn" or (p["status"] != "completed" and t_now - p["last_activity_ms"] > INACTIVE_MIN * 60000))
        order = json.loads(p["task_order"])
        usable_vals, attempted, submitted, elapsed, fails = [], 0, 0, 0.0, 0
        for pos, tid in enumerate(order, 1):
            r = runs.get(tid)
            cond = condition_of(dsg, p["arm"], tid) if dsg and "-" in p["arm"] else ""
            row = {"participant_code": p["code"], "arm": p["arm"], "condition": cond, "simulated": sim, "task_id": tid, "task_kind": kinds[tid], "position": pos,
                   "attempted": int(bool(r)), "submitted": int(bool(r and r["state"] in ("submitted", "withdrawn"))), "missing": 1, "timed_out": "", "late": "", "elapsed_s": "",
                   "time_limit_s": "", "answer_chars": "", "aid_inserted": "", "aid_provider": "", "aid_simulated": "", "model_failure": ""}
            for rt in ("r1", "r2", "r3"):
                for k in CRITERIA + ("severe",):
                    row["%s_%s" % (rt, k)] = ""
            row.update({"notes_present": "", "disagreement": "", "resolution": "missing"})
            for k in CRITERIA + ("severe",):
                row["final_" + k] = ""
            row["final_usable"] = 0
            if r:
                attempted += 1
                row.update({"timed_out": r["timed_out"], "late": r["late"], "time_limit_s": r["limit_ms"] // 1000, "aid_provider": r["aid_provider"],
                            "aid_simulated": r["aid_simulated"], "model_failure": r["model_failure"], "aid_inserted": r["aid_inserted"]})
                fails += r["model_failure"] or 0
                if r["state"] in ("submitted", "withdrawn"):
                    submitted += 1
                    row["elapsed_s"] = round((r["elapsed_ms"] or 0) / 1000, 1)
                    elapsed += (r["elapsed_ms"] or 0) / 1000
                    row["answer_chars"] = r["answer_chars"]
                    row["missing"] = 1 if not r["answer_chars"] else 0
                sc = scores.get(r["item_key"], {})
                if p["status"] != "withdrawn" and not row["missing"]:
                    for rt in ("R1", "R2", "R3"):
                        if rt in sc:
                            for k in CRITERIA + ("severe",):
                                row["%s_%s" % (rt.lower(), k)] = sc[rt][k]
                    row["notes_present"] = int(any((sc[x]["notes"] or "").strip() for x in sc))
                    fields = CRITERIA + ("severe",)
                    if "R1" in sc and "R2" in sc:
                        dis = any(sc["R1"][k] != sc["R2"][k] for k in fields)
                        row["disagreement"] = int(dis)
                        if not dis:
                            fin, row["resolution"] = {k: sc["R1"][k] for k in fields}, "agree"
                        elif "R3" in sc:
                            fin, row["resolution"] = {k: majority([sc[x][k] for x in ("R1", "R2", "R3")]) for k in fields}, "adjudicated"
                        else:
                            fin, row["resolution"] = None, "unresolved"
                        if fin:
                            for k in fields:
                                row["final_" + k] = fin[k]
                            row["final_usable"] = int(all(fin[k] for k in CRITERIA) and not fin["severe"])
                        else:
                            row["final_usable"] = ""
                    else:
                        row["resolution"] = "unscored"
                        row["final_usable"] = ""
            row["participant_status"], row["dropout"] = p["status"], dropout
            task_rows.append(row)
            usable_vals.append(row["final_usable"])
        known = all(v != "" for v in usable_vals)
        n_usable = sum(usable_vals) if known else ""
        xo = {}
        if dsg and "-" in p["arm"]:
            mine = task_rows[-len(order):]
            ua = [r["final_usable"] for r in mine if r["condition"] == "A"]
            ub = [r["final_usable"] for r in mine if r["condition"] == "B"]
            kn = known and ua and ub
            xo = {"sequence": p["arm"], "first_condition": p["arm"][0],
                  "usable_share_A": round(sum(ua) / len(ua), 4) if kn else "", "usable_share_B": round(sum(ub) / len(ub), 4) if kn else "",
                  "diff_B_minus_A": round(sum(ub) / len(ub) - sum(ua) / len(ua), 4) if kn else ""}
        part_rows.append({"participant_code": p["code"], "arm": p["arm"], "simulated": sim, "block_no": p["block_no"], "tasks_attempted": attempted,
                          "tasks_submitted": submitted, "tasks_missing": sum(1 for r in task_rows[-len(order):] if r["missing"]),
                          "n_usable": n_usable, "usable_share": round(n_usable / len(order), 4) if known else "", "usable_ge3": int(n_usable >= 3) if known else "",
                          "total_elapsed_s": round(elapsed, 1), "model_failures": fails, "participant_status": p["status"], "dropout": dropout, **xo})
    meta = {"schema": SCHEMA_VERSION, "scope": scope, "design": design_id(doc), "threshold": dsg.get("threshold") if dsg else None, "simulated": sim == 1, "banner": BANNER if sim else None, "generated_at": iso(),
            "tasks_version": doc["version"], "tasks_sha256": tasks_sha256(), "rubric_version": doc["rubric"]["version"],
            "allocation": "permuted blocks of %d, seeded (%s)" % (BLOCK_SIZE, "SIM seed %d" % SIM_SEED if sim else "seed from APPROVAL.json"),
            "model": study_arms.model_status(), "n_participants": len(plist)}
    return {"meta": meta, "participants": part_rows, "tasks": task_rows,
            "scores": [{"participant_code": r["participant_code"], "task_id": r["task_id"], **{k: r[k] for k in r if re.match(r"^r[123]_", k)}} for r in task_rows if r["resolution"] != "missing"]}
