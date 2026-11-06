"""Randomized evaluation (docs/EVAL_PLAN.md): control answers alone, treatment may open AgeLens, both on the same ad and CV pairs.

Safety rules enforced HERE (server-side), not in the UI:
  * mode defaults to 'simulation'. 'formal' is refused unless data/study/RCT_APPROVAL.json is complete, a valid frozen case set
    matches it, a model is connected and storage survives a restart. This module never creates that file.
  * the answer key stays on the server. Participants never receive labels, scores or evidence sentences.
  * the group is drawn once by the server; a repeat login with the same code keeps it. The control group cannot call the tool.
  * time is measured by the server and is never paused or reset. The first valid answer stands.
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
from collections import Counter
from datetime import date, datetime, timezone

from . import db
from .server import HTTPError, hash_token

STUDY_DIR = db.DATA_DIR / "study"
APPROVAL_PATH = STUDY_DIR / "RCT_APPROVAL.json"
REHEARSAL_CASES = STUDY_DIR / "rct_rehearsal_cases.json"
REHEARSAL_KEY = STUDY_DIR / "rct_rehearsal_key.json"
DESIGN_ID = "parallel-rct-v1"
SCHEMA_VERSION = "rct-export-v1"
CONSENT_VERSION = "rct-consent-draft-1"
LABELS = ("Match", "Conflict", "Unknown")
GROUPS = ("control", "treatment")
SIM_SEED = 20261105
BLOCK_SIZE = 4
TIME_LIMIT_S = 120
GRACE_MS = 5000
N_SCORED, N_PRACTICE = 32, 2
FORBIDDEN_IN_CASES = {"gold", "gold_label", "answer", "evidence_text", "rationale", "label"}
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
BANNER = "SIMULATED run, not study data."

SCHEMA = """
CREATE TABLE IF NOT EXISTS rct_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rct_case_sets (
  sha TEXT PRIMARY KEY, version TEXT NOT NULL, cases_json TEXT NOT NULL, key_json TEXT NOT NULL, imported_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rct_codes (code TEXT PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rct_participants (
  code TEXT PRIMARY KEY, token_hash TEXT NOT NULL, grp TEXT NOT NULL, mode TEXT NOT NULL, simulated INTEGER NOT NULL, case_sha TEXT NOT NULL,
  block_no INTEGER NOT NULL, block_pos INTEGER NOT NULL, case_order TEXT NOT NULL, status TEXT NOT NULL, consent_version TEXT, consent_at TEXT,
  enrolled_at TEXT NOT NULL, last_activity_ms INTEGER NOT NULL, other_tools TEXT, withdrawn_at TEXT);
CREATE TABLE IF NOT EXISTS rct_items (
  code TEXT NOT NULL, case_id TEXT NOT NULL, position INTEGER NOT NULL, practice INTEGER NOT NULL, displayed_ms INTEGER NOT NULL, limit_ms INTEGER NOT NULL,
  submitted_ms INTEGER, elapsed_ms INTEGER, client_elapsed_ms INTEGER, label TEXT, timed_out INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'shown',
  api_status TEXT, tool_opened_ms INTEGER, tool_returned_ms INTEGER, tool_view TEXT, provider TEXT, model TEXT, prompt_version TEXT,
  PRIMARY KEY (code, case_id));
CREATE TABLE IF NOT EXISTS rct_model_answers (
  case_sha TEXT NOT NULL, case_id TEXT NOT NULL, label TEXT, status TEXT NOT NULL, provider TEXT, model TEXT, prompt_version TEXT, latency_ms INTEGER, created_at TEXT NOT NULL,
  PRIMARY KEY (case_sha, case_id));
"""


def now_ms():
    return int(time.time() * 1000)


def iso(ms=None):
    t = datetime.fromtimestamp(ms / 1000, timezone.utc) if ms is not None else datetime.now(timezone.utc)
    return t.isoformat(timespec="seconds").replace("+00:00", "Z")


def conn():
    c = db.connect()
    c.executescript(SCHEMA)
    return c


def get_setting(c, key, default=None):
    r = c.execute("SELECT value FROM rct_settings WHERE key=?", (key,)).fetchone()
    return r[0] if r else default


def set_setting(c, key, value):
    c.execute("INSERT INTO rct_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


# ---- case sets ------------------------------------------------------------------------------------

def sha_of(cases, key):
    canon = lambda d: json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((canon(cases) + "\n" + canon(key)).encode("utf-8")).hexdigest()


def _keys_in(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys_in(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys_in(v)


def _valid_date(s):
    try:
        date.fromisoformat(str(s))
        return True
    except ValueError:
        return False


def validate(cases, key):
    """Problems that make a case set unusable for any run."""
    p = []
    if not isinstance(cases, dict) or not isinstance(key, dict):
        return ["The case file and the answer key must both be JSON objects."]
    practice, scored = cases.get("practice") or [], cases.get("cases") or []
    if not scored:
        p.append("The case file has no scored cases.")
    leaked = FORBIDDEN_IN_CASES & set(_keys_in(cases))
    if leaked:
        p.append("The case file must not hold answers (found: %s)." % ", ".join(sorted(leaked)))
    ids = [c.get("id") for c in practice + scored]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) and i for i in ids):
        p.append("Case ids must be unique, non-empty text.")
    answers = key.get("answers") if isinstance(key.get("answers"), dict) else {}
    for c in practice + scored:
        cid = c.get("id")
        if not str(c.get("ad_text") or "").strip():
            p.append("%s: ad_text is empty." % cid)
        if len(str(c.get("ad_text") or "")) > 4000:
            p.append("%s: ad_text is over the 4,000 character limit." % cid)
        if not _valid_date(c.get("entry_date")):
            p.append("%s: entry_date must be YYYY-MM-DD." % cid)
        cv = c.get("cv") or {}
        if not _valid_date(cv.get("birth_date")):
            p.append("%s: cv.birth_date must be YYYY-MM-DD." % cid)
        a = answers.get(cid)
        if not isinstance(a, dict) or a.get("gold_label") not in LABELS:
            p.append("%s: the answer key needs a gold_label of %s." % (cid, " / ".join(LABELS)))
        elif not str(a.get("evidence_text") or "").strip():
            p.append("%s: the answer key needs an evidence_text." % cid)
    return p


def formal_problems(cases, key):
    """The frozen design: 32 distinct pairs, 16/16 wording, 4 provinces x 8, 16 groups x 2, at least 2 practice cases, 12/12/8 labels."""
    p = validate(cases, key)
    if p:
        return p
    scored, answers = cases["cases"], key["answers"]
    if len(scored) != N_SCORED:
        p.append("A formal set needs %d scored cases; this one has %d." % (N_SCORED, len(scored)))
    if len(cases.get("practice") or []) < N_PRACTICE:
        p.append("A formal set needs at least %d practice cases." % N_PRACTICE)
    tally = lambda k: dict(Counter((c.get("stratum") or {}).get(k) for c in scored))
    if tally("wording") != {"explicit": 16, "indirect": 16}:
        p.append("Wording must be 16 explicit and 16 indirect; found %s." % tally("wording"))
    prov, occ = tally("province"), tally("occupation")
    if len(prov) != 4 or set(prov.values()) != {8}:
        p.append("Each of 4 provinces needs 8 cases; found %s." % prov)
    if len(occ) != 16 or set(occ.values()) != {2}:
        p.append("Each of 16 occupation groups needs 2 cases; found %s." % occ)
    sources = [c.get("source_ad_id") for c in scored]
    if None in sources or len(set(sources)) != len(sources):
        p.append("Each scored case needs its own source_ad_id.")
    labels = [answers[c["id"]]["gold_label"] for c in scored]
    if sorted(labels) != sorted(["Match"] * 12 + ["Conflict"] * 12 + ["Unknown"] * 8):
        p.append("Answers must be 12 Match, 12 Conflict and 8 Unknown.")
    return p


def rehearsal_set():
    return json.loads(REHEARSAL_CASES.read_text(encoding="utf-8")), json.loads(REHEARSAL_KEY.read_text(encoding="utf-8"))


def active_set(c):
    """-> (sha, cases, key, source). An imported set if one is active, else the fictional rehearsal set."""
    sha = get_setting(c, "active_sha")
    if sha:
        r = c.execute("SELECT * FROM rct_case_sets WHERE sha=?", (sha,)).fetchone()
        if r:
            return sha, json.loads(r["cases_json"]), json.loads(r["key_json"]), "imported"
    cases, key = rehearsal_set()
    return sha_of(cases, key), cases, key, "rehearsal"


def set_for(c, sha):
    r = c.execute("SELECT * FROM rct_case_sets WHERE sha=?", (sha,)).fetchone()
    if r:
        return json.loads(r["cases_json"]), json.loads(r["key_json"])
    cases, key = rehearsal_set()
    if sha_of(cases, key) != sha:
        raise HTTPError(409, "This session's test set is no longer on the server.")
    return cases, key


def case_index(cases):
    return {x["id"]: dict(x, _practice=False) for x in cases["cases"]} | {x["id"]: dict(x, _practice=True) for x in cases.get("practice") or []}


def participant_case(x):
    """Only what a person may see. The stratum would give away which cases were rewritten."""
    return {k: x[k] for k in ("id", "job_title", "ad_text", "ad_text_en", "cv", "entry_date") if k in x}


# ---- approval -------------------------------------------------------------------------------------

def read_approval():
    try:
        a = json.loads(APPROVAL_PATH.read_text(encoding="utf-8"))
    except OSError:
        return None, ["data/study/RCT_APPROVAL.json does not exist (teacher approval has not been recorded)."]
    except ValueError:
        return None, ["RCT_APPROVAL.json is not valid JSON."]
    if not isinstance(a, dict):
        return None, ["RCT_APPROVAL.json must be a JSON object."]
    p = []
    if a.get("approved") is not True:
        p.append('RCT_APPROVAL.json must contain "approved": true.')
    for k in ("teacher_name", "approval_date", "stopping_rule", "case_set_sha256"):
        if not (isinstance(a.get(k), str) and a[k].strip()):
            p.append("RCT_APPROVAL.json missing field: %s." % k)
    if not (isinstance(a.get("recruitment_target"), int) and a["recruitment_target"] > 0):
        p.append("recruitment_target must be a positive integer.")
    if not (isinstance(a.get("allocation_seed"), int) and not isinstance(a.get("allocation_seed"), bool)):
        p.append("allocation_seed must be an integer set by the approver.")
    return a, p


def model_connected():
    from . import llm
    return bool(llm.status().get("connected"))


def formal_blockers(c):
    a, p = read_approval()
    p = list(p)
    sha, cases, key, source = active_set(c)
    if source != "imported":
        p.append("No frozen test set has been imported; only the fictional rehearsal set is on the server.")
    else:
        p += formal_problems(cases, key)
        if a and a.get("case_set_sha256") != sha:
            p.append("case_set_sha256 does not match the imported test set (it must be frozen exactly as approved).")
    if not model_connected():
        p.append("No AI model is connected, so the treatment group would not see the real product.")
    if os.environ.get("AGELENS_RCT_DURABLE") != "1":
        p.append("Storage is not marked durable (AGELENS_RCT_DURABLE=1). On a server without a persistent disk, a restart erases all answers.")
    return p


def current_mode(c):
    if get_setting(c, "mode", "simulation") == "formal" and not formal_blockers(c):
        return "formal"
    return "simulation"  # approval withdrawn or invalid: fall back safely, never run formal silently


def alloc_seed(mode):
    if mode == "simulation":
        return SIM_SEED
    return int(read_approval()[0]["allocation_seed"])


def allocate(c, mode, sha):
    n = c.execute("SELECT COUNT(*) FROM rct_participants WHERE mode=? AND case_sha=?", (mode, sha)).fetchone()[0]
    block, pos = divmod(n, BLOCK_SIZE)
    arms = list(GROUPS) * (BLOCK_SIZE // 2)
    random.Random("%s|%s|%s|%d" % (alloc_seed(mode), mode, sha, block)).shuffle(arms)
    return arms[pos], block, pos


def time_limit_s(c):
    if current_mode(c) == "simulation":
        v = get_setting(c, "sim_time_limit_s")
        if v:
            return int(v)
    return TIME_LIMIT_S


# ---- participant state ----------------------------------------------------------------------------

def participant(c, req):
    tok, code = req.headers.get("X-Participant-Token", ""), req.headers.get("X-Participant-Code", "")
    if not tok or not code:
        raise HTTPError(401, "Missing test session.")
    r = c.execute("SELECT * FROM rct_participants WHERE code=?", (code,)).fetchone()
    if not r or not secrets.compare_digest(r["token_hash"], hash_token(tok)):
        raise HTTPError(401, "Unknown test session. Enter your code again.")
    return r


def _close_expired(c, run, now):
    if run["state"] == "shown" and now > run["displayed_ms"] + run["limit_ms"] + GRACE_MS:
        c.execute("UPDATE rct_items SET state='timed_out', submitted_ms=?, elapsed_ms=?, timed_out=1 WHERE code=? AND case_id=?",
                  (run["displayed_ms"] + run["limit_ms"], run["limit_ms"], run["code"], run["case_id"]))
        return True
    return False


def advance(c, p, now=None):
    """Close anything out of time. -> (index of the case now due, its open row or None); index None = all done."""
    now = now_ms() if now is None else now
    order = json.loads(p["case_order"])
    for i, cid in enumerate(order):
        run = c.execute("SELECT * FROM rct_items WHERE code=? AND case_id=?", (p["code"], cid)).fetchone()
        if run is None:
            return i, None
        if run["state"] == "shown" and not _close_expired(c, run, now):
            return i, run
    return None, None


def session_view(c, p):
    order = json.loads(p["case_order"])
    cases, _key = set_for(c, p["case_sha"])
    practice_ids = {x["id"] for x in cases.get("practice") or []}
    n_practice = sum(1 for x in order if x in practice_ids)
    i, run = advance(c, p)
    done = i is None
    if done and p["status"] == "in_progress":
        c.execute("UPDATE rct_participants SET status='answered' WHERE code=?", (p["code"],))
    status = "answered" if done and p["status"] == "in_progress" else p["status"]
    return {"code": p["code"], "tool": p["grp"] == "treatment", "status": status, "done": done, "finished": status == "completed",
            "simulated": bool(p["simulated"]), "open_case": bool(run), "in_practice": (not done) and i < n_practice,
            "practice_total": n_practice, "scored_total": len(order) - n_practice,
            "scored_done": (len(order) if done else max(i, n_practice)) - n_practice}


def age_on(birth, on):
    b, d = date.fromisoformat(birth), date.fromisoformat(on)
    return d.year - b.year - ((d.month, d.day) < (b.month, b.day))


def tool_body(case):
    """What AgeLens is given: the same fields a person would type on Check an ad, plus the dates the CV states."""
    cv = case.get("cv") or {}
    prof = {"age": age_on(cv["birth_date"], case["entry_date"])}
    if isinstance(cv.get("years_experience"), int):
        prof["years_experience"] = cv["years_experience"]
    if cv.get("education"):
        prof["education"] = cv["education"]
    if cv.get("experience"):
        prof["occupation"] = str(cv["experience"][0])[:60]
    q = "Born %s, graduated %s, starting on %s. Does this ad's age wording fit this CV?" % (cv["birth_date"], cv.get("graduation_date") or "unknown", case["entry_date"])
    return {"text": str(case["ad_text"]), "question": q, "profile": prof}  # the original, not a translation: the rules were built on it


def tool_view(b):
    """The product's own output, reduced to what fits beside a test item. It never gives Match or Conflict."""
    ai, sm = (b.get("reports") or {}).get("ai") or {}, b.get("summary") or {}
    status = {"used": "ok", "fallback": "failed", "template": "no_model"}.get(b.get("ai_status"), "failed")
    if status == "ok" and not ai.get("available"):
        status = "no_output"
    relates = re.sub(r"\bYou entered (\d+)", r"This CV gives age \1 on the start date", sm.get("relates_en") or sm.get("relates") or "")
    relates = re.sub(r"the age you entered \((\d+)\)", r"this CV's age on the start date (\1)", relates)
    view = {"api_status": status, "states": sm.get("states_en") or sm.get("states") or "", "relates": relates}
    if status == "ok":
        view.update(stated=ai.get("stated") or [], related=ai.get("related") or [], unclear=ai.get("unclear") or [])
    else:
        view["note"] = {"failed": "The AI analysis failed on this ad. Only the fixed rules' reading is shown.",
                        "no_output": "No statement from the AI model passed the code check. Only the fixed rules' reading is shown.",
                        "no_model": "No AI model is connected on this server. Only the fixed rules' reading is shown."}[status]
    return view


# ---- export ---------------------------------------------------------------------------------------

ITEM_FIELDS = ("schema_version", "design", "mode", "case_set_sha256", "participant_id", "assigned_group", "assist", "case_id", "position", "wording", "province", "occupation",
               "gold_label", "no_age_limit", "selected_label", "correct", "displayed_at", "submitted_at", "elapsed_seconds", "client_elapsed_ms", "timeout", "missing_flag",
               "api_status", "tool_opened", "tool_wait_ms", "provider", "model", "prompt_version")
PERSON_FIELDS = ("schema_version", "design", "mode", "case_set_sha256", "participant_id", "assigned_group", "assist", "status", "n_items", "score", "search_seconds",
                 "timeout_rate", "missing_rate", "tool_used_items", "api_failed_items", "used_other_tools", "enrolled_at")
MODEL_FIELDS = ("schema_version", "case_set_sha256", "case_id", "wording", "gold_label", "label", "correct", "status", "provider", "model", "prompt_version", "latency_ms", "created_at")


def _scored_ids(cases, order):
    keep = {x["id"] for x in cases["cases"]}
    return [x for x in order if x in keep]


def export_rows(c, mode):
    items, persons = [], []
    for p in c.execute("SELECT * FROM rct_participants WHERE mode=? ORDER BY enrolled_at, code", (mode,)).fetchall():
        cases, key = set_for(c, p["case_sha"])
        idx, answers = case_index(cases), key["answers"]
        order = _scored_ids(cases, json.loads(p["case_order"]))
        base = {"schema_version": SCHEMA_VERSION, "design": DESIGN_ID, "mode": mode, "case_set_sha256": p["case_sha"], "participant_id": p["code"], "assigned_group": p["grp"],
                "assist": 1 if p["grp"] == "treatment" else 0}
        if p["status"] == "withdrawn":
            persons.append(dict(base, status="withdrawn", n_items=len(order), enrolled_at=p["enrolled_at"]))
            continue
        advance(c, p)
        row_of = {r["case_id"]: r for r in c.execute("SELECT * FROM rct_items WHERE code=?", (p["code"],))}
        right = secs = timeouts = missing = used = failed = 0
        for n, cid in enumerate(order, 1):
            run, s, a = row_of.get(cid), idx[cid].get("stratum") or {}, answers[cid]
            never = run is None or run["state"] == "shown"  # not reached, or left open by someone who stopped
            lab = None if never else run["label"]
            ok = int(lab == a["gold_label"])
            limit = TIME_LIMIT_S if run is None else run["limit_ms"] / 1000
            sec = limit if never or run["elapsed_ms"] is None else min(run["elapsed_ms"] / 1000, limit)
            to = 0 if never else run["timed_out"]
            right, secs, timeouts, missing = right + ok, secs + sec, timeouts + to, missing + int(never)
            opened = bool(run and run["tool_opened_ms"])
            used += opened
            failed += bool(run and run["api_status"] and run["api_status"] != "ok")
            wait = run["tool_returned_ms"] - run["tool_opened_ms"] if opened and run["tool_returned_ms"] else ""
            items.append(dict(base, case_id=cid, position=n, wording=s.get("wording", ""), province=s.get("province", ""), occupation=s.get("occupation", ""), gold_label=a["gold_label"],
                              no_age_limit=int(bool(a.get("no_age_limit"))), selected_label=lab or "", correct=ok, displayed_at=iso(run["displayed_ms"]) if run else "",
                              submitted_at=iso(run["submitted_ms"]) if run and run["submitted_ms"] else "", elapsed_seconds=round(sec, 3),
                              client_elapsed_ms=run["client_elapsed_ms"] if run and run["client_elapsed_ms"] is not None else "", timeout=to, missing_flag=int(never),
                              api_status=(run["api_status"] or "") if run else "", tool_opened=int(opened), tool_wait_ms=wait, provider=(run["provider"] or "") if run else "",
                              model=(run["model"] or "") if run else "", prompt_version=(run["prompt_version"] or "") if run else ""))
        n = len(order)
        persons.append(dict(base, status=p["status"], n_items=n, score=round(right / n * 100, 4), search_seconds=round(secs / n, 4), timeout_rate=round(timeouts / n, 4),
                            missing_rate=round(missing / n, 4), tool_used_items=used, api_failed_items=failed, used_other_tools=p["other_tools"] or "", enrolled_at=p["enrolled_at"]))
    return items, persons


def model_rows(c):
    sha, cases, key, _source = active_set(c)
    idx, out = case_index(cases), []
    for r in c.execute("SELECT * FROM rct_model_answers WHERE case_sha=? ORDER BY case_id", (sha,)):
        gold = key["answers"][r["case_id"]]["gold_label"]
        out.append({"schema_version": SCHEMA_VERSION, "case_set_sha256": sha, "case_id": r["case_id"], "wording": (idx[r["case_id"]].get("stratum") or {}).get("wording", ""), "gold_label": gold,
                    "label": r["label"] or "", "correct": int(r["label"] == gold), "status": r["status"], "provider": r["provider"], "model": r["model"],
                    "prompt_version": r["prompt_version"], "latency_ms": r["latency_ms"], "created_at": r["created_at"]})
    return out


def to_csv(rows, fields):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
