"""Design crossover-ai-v1 (docs/EVAL_PLAN.md): participant view, blinded rubric scoring and anonymous export for
'fixed template versus contextual AI assistance, identical evidence'. Called from api_study (which owns routing, the formal gate
and the tables); all functions take the api_study module as `S` so there is no import cycle.
Safety rules are the ones in api_study: raters never get the tool, arm, participant code or other raters' scores; participants never
get scores or arm names (Tool A / Tool B only); a SIMULATED session is exported only as SIMULATED, never as an AI result."""
import hashlib
import json

from . import study_arms, study_stats

TOOL_SOURCE = {"fixed-template": "fixed-template", "SIMULATED-script": "SIMULATED-script"}
TOOL_NAMES = {"A": "template", "B": "ai_contextual"}
QS = ("q1", "q2", "q3", "q4")
UNSUPPORTED_MAX = 10


def join_answer(reading, question):
    return "Reading:\n%s\n\nQuestion:\n%s" % (reading, question)


def fact_ids(task):
    return [f["id"] for f in task.get("key_facts") or []]


# ---- participant side ---------------------------------------------------------------------------
def start_view(c, p, task, run, remaining, total, payload):
    try:
        tool = json.loads(run["aid_text"]) if run["aid_text"] else {}
    except ValueError:
        tool = {}
    tool.pop("notice", None)   # the SIMULATED notice is shown for the whole session (sim_notice), identically for both tools, so it cannot reveal the arm
    ev = study_arms.evidence_package(task)
    done = run["state"] == "submitted"
    return {"task": payload, "position": run["position"], "total": total, "remaining_ms": remaining, "limit_ms": run["limit_ms"], "state": run["state"],
            "reading": (run["reading"] or "") if done else "", "question": (run["question_text"] or "") if done else "",
            "evidence": {"rule_version": ev["rule_version"], "wording_line": ev["wording_line"], "items": ev["items"]},
            "aid": {"kind": "tool", "label": "Tool A" if run["position"] <= total // 2 else "Tool B", "failed": bool(run["model_failure"]), "tool": tool,
                    "sim_notice": study_arms.SIM_NOTICE if p["simulated"] else None}}


def reveal(d, p):
    """Shown only after the last task: which tool was A and which was B for this participant."""
    def txt(cond):
        if d["conditions"][cond]["kind"] == "template":
            return "a fixed question template, filled in mechanically from the evidence."
        return ("contextual AI assistance. In this rehearsal it was SIMULATED: no AI model was used and a script wrote the text." if p["simulated"]
                else "contextual AI assistance: a model read your background and the same evidence.")
    return {"A": txt(p["arm"][0]), "B": txt(p["arm"][1])}


# ---- rubric scoring -----------------------------------------------------------------------------
def _norm(r):
    """DB row -> {facts:{F1:0/1}, q1..q4, unsupported}"""
    return dict({"facts": json.loads(r["facts"]), "unsupported": r["unsupported"]}, **{q: r[q] for q in QS})


def fields_differ(a, b):
    out = [k for k in sorted(a["facts"]) if a["facts"][k] != b["facts"].get(k)]
    out += [q for q in QS if a[q] != b[q]]
    if a["unsupported"] != b["unsupported"]:
        out.append("unsupported")
    return out


def _median3(v):
    return sorted(v)[1]


def resolve(sc):
    """sc: {rater: normalised score} -> (resolution, final|None, disagreement 0/1/'')"""
    if "R1" not in sc or "R2" not in sc:
        return "unscored", None, ""
    if not fields_differ(sc["R1"], sc["R2"]):
        return "agree", sc["R1"], 0
    if "R3" not in sc:
        return "unresolved", None, 1
    rs = [sc[x] for x in ("R1", "R2", "R3")]
    fin = {"facts": {k: 1 if sum(r["facts"][k] for r in rs) * 2 > 3 else 0 for k in rs[0]["facts"]},
           "unsupported": _median3([r["unsupported"] for r in rs])}
    for q in QS:
        fin[q] = 1 if sum(r[q] for r in rs) * 2 > 3 else 0
    return "adjudicated", fin, 1


def parse_score(body, task):
    ids = fact_ids(task)
    facts = body.get("facts")
    if not isinstance(facts, dict) or any(not isinstance(facts.get(i), bool) for i in ids):
        raise S_().HTTPError(400, "Mark every key fact as stated correctly or not.")
    out = {"facts": {i: 1 if facts[i] else 0 for i in ids}}
    for q in QS:
        if not isinstance(body.get(q), bool):
            raise S_().HTTPError(400, "Answer all four question criteria with yes or no.")
        out[q] = 1 if body[q] else 0
    u = body.get("unsupported")
    if isinstance(u, bool) or not isinstance(u, int) or not 0 <= u <= UNSUPPORTED_MAX:
        raise S_().HTTPError(400, "Enter the number of unsupported statements (0-%d)." % UNSUPPORTED_MAX)
    out["unsupported"], out["notes"] = u, str(body.get("notes") or "")[:500]
    return out


def S_():
    from . import api_study
    return api_study


def _store(c, table, key_cols, key_vals, s):
    c.execute("INSERT INTO %s(%s,facts,q1,q2,q3,q4,unsupported,notes,scored_at) VALUES(%s) ON CONFLICT(%s) DO UPDATE SET facts=excluded.facts,q1=excluded.q1,q2=excluded.q2,q3=excluded.q3,q4=excluded.q4,unsupported=excluded.unsupported,notes=excluded.notes,scored_at=excluded.scored_at"
              % (table, ",".join(key_cols), ",".join("?" * (len(key_cols) + 8)), ",".join(key_cols)),
              tuple(key_vals) + (json.dumps(s["facts"]), s["q1"], s["q2"], s["q3"], s["q4"], s["unsupported"], s["notes"], S_().iso()))


def _cal_items(doc):
    return doc["calibration_ai"]


def _cal_got(c, rater):
    return {r["cal_id"]: r for r in c.execute("SELECT * FROM study_calibration_ai WHERE rater=?", (rater,))}


def scorable(c, sim):
    return c.execute("SELECT r.item_key, r.task_id, r.reading, r.question_text FROM study_task_runs r JOIN study_participants p USING(code) "
                     "WHERE r.state='submitted' AND r.answer_chars>0 AND p.simulated=? AND p.status!='withdrawn'", (sim,)).fetchall()


def _item(S, doc, row):
    t = S.task_by_id(doc, row["task_id"])
    return {"task": S.task_payload(t, english=True, facts=True), "reading": row["reading"] or "", "question": row["question_text"] or ""}


def _scores(c, key):
    return {r["rater"]: _norm(r) for r in c.execute("SELECT * FROM study_scores_ai WHERE item_key=?", (key,))}


def disagreement_keys(c, sim):
    out = []
    for it in scorable(c, sim):
        sc = _scores(c, it["item_key"])
        if "R1" in sc and "R2" in sc and fields_differ(sc["R1"], sc["R2"]):
            out.append(it["item_key"])
    return out


def rater_status(S, req):
    rater = S.require_study(req, S.RATERS)
    doc = S.load_tasks()
    with S.conn() as c:
        got = _cal_got(c, rater)
        mode = S.current_mode(c)
        sim = 1 if mode == "simulation" else 0
        n_items = len(scorable(c, sim))
        mine = c.execute("SELECT COUNT(*) FROM study_scores_ai s WHERE rater=? AND item_key IN (SELECT item_key FROM study_task_runs r JOIN study_participants p USING(code) WHERE p.simulated=?)", (rater, sim)).fetchone()[0]
        return {"rater": rater, "mode": mode, "banner": S.BANNER if sim else None, "calibration_done": len(got) >= len(_cal_items(doc)),
                "calibration_items": len(_cal_items(doc)), "calibration_scored": len(got), "scorable_items": n_items, "scored_by_me": mine,
                "rubric": doc["rubric_ai"]}


def calibration(S, req):
    rater = S.require_study(req, S.RATERS)
    doc = S.load_tasks()
    with S.conn() as c:
        got = _cal_got(c, rater)
    items = [dict({"id": i["id"], "reading": i["reading"], "question": i["question"],
                   "task": S.task_payload(S.task_by_id(doc, i["task_id"]), english=True, facts=True)}, scored=i["id"] in got) for i in _cal_items(doc)]
    return {"items": items, "done": len(got) >= len(items)}


def _flat(s):
    d = dict(s["facts"]); d.update({q: s[q] for q in QS}); d["unsupported"] = s["unsupported"]
    return d


def calibration_score(S, req):
    rater = S.require_study(req, S.RATERS)
    doc = S.load_tasks()
    item = next((i for i in _cal_items(doc) if i["id"] == req.params["cid"]), None)
    if not item:
        raise S.HTTPError(404, "Unknown calibration item.")
    s = parse_score(req.json(), S.task_by_id(doc, item["task_id"]))
    with S.conn() as c:
        _store(c, "study_calibration_ai", ("rater", "cal_id"), (rater, item["id"]), s)
    ref = item["reference"]
    refflat = dict(ref["facts"]); refflat.update(ref["q"]); refflat["unsupported"] = ref["unsupported"]
    mine = _flat(s)
    match = {k: mine[k] == refflat[k] for k in refflat}
    return {"reference": refflat, "rationale": item["rationale"], "match": match, "agreed": sum(match.values()), "of": len(match)}


def calibration_summary(S, req):
    rater = S.require_study(req, S.RATERS)
    doc = S.load_tasks()
    with S.conn() as c:
        rows = _cal_got(c, rater)
    agree = total = 0
    for it in _cal_items(doc):
        r = rows.get(it["id"])
        if not r:
            continue
        ref = dict(it["reference"]["facts"]); ref.update(it["reference"]["q"]); ref["unsupported"] = it["reference"]["unsupported"]
        mine = _flat(_norm(r))
        for k, v in ref.items():
            total += 1; agree += mine.get(k) == v
    full = len(rows) >= len(_cal_items(doc))
    pct = agree / total if total else 0
    return {"agreement": round(pct, 3), "judgements": total, "severe_mismatches": 0, "target_met": bool(full and pct >= 0.9)}


def rater_next(S, req):
    rater = S.require_study(req, S.RATERS)
    doc = S.load_tasks()
    with S.conn() as c:
        if len(_cal_got(c, rater)) < len(_cal_items(doc)):
            raise S.HTTPError(409, "Finish the calibration set first (Scoring > Calibration).")
        sim = 1 if S.current_mode(c) == "simulation" else 0
        mine = {r["item_key"] for r in c.execute("SELECT item_key FROM study_scores_ai WHERE rater=?", (rater,))}
        pool = scorable(c, sim)
        if rater == "R3":
            dk = set(disagreement_keys(c, sim))
            pool = [it for it in pool if it["item_key"] in dk]
        pool = [it for it in pool if it["item_key"] not in mine]
        if not pool:
            return {"item": None, "remaining": 0}
        pool.sort(key=lambda it: hashlib.sha256((rater + it["item_key"]).encode()).hexdigest())
        it = pool[0]
        return {"item": dict({"item_key": it["item_key"]}, **_item(S, doc, it)), "remaining": len(pool)}


def rater_score(S, req):
    rater = S.require_study(req, S.RATERS)
    body = req.json()
    key = str(body.get("item_key") or "")
    doc = S.load_tasks()
    with S.conn() as c:
        if len(_cal_got(c, rater)) < len(_cal_items(doc)):
            raise S.HTTPError(409, "Finish the calibration set first.")
        sim = 1 if S.current_mode(c) == "simulation" else 0
        ok = [it for it in scorable(c, sim) if it["item_key"] == key]
        if not ok:
            raise S.HTTPError(404, "That item is not available for scoring.")
        s = parse_score(body, S.task_by_id(doc, ok[0]["task_id"]))
        if rater == "R3" and key not in set(disagreement_keys(c, sim)):
            raise S.HTTPError(403, "R3 scores only items where R1 and R2 disagree.")
        if c.execute("SELECT 1 FROM study_scores_ai WHERE item_key=? AND rater=?", (key, rater)).fetchone():
            raise S.HTTPError(409, "You already scored this item; scores are not edited after submission.")
        _store(c, "study_scores_ai", ("item_key", "rater"), (key, rater), s)
        return {"ok": True}


def disagreements(S, req):
    S.require_study(req, S.RATERS)
    with S.conn() as c:
        sim = 1 if S.current_mode(c) == "simulation" else 0
        log = []
        for key in disagreement_keys(c, sim):
            sc = _scores(c, key)
            log.append({"item": key, "fields": fields_differ(sc["R1"], sc["R2"]), "r3_done": "R3" in sc})
        return {"rule": S.load_tasks()["rubric_ai"]["disagreement_rule"], "n": len(log), "open": sum(1 for x in log if not x["r3_done"]), "log": log}


# ---- export -------------------------------------------------------------------------------------
EXPORT_FIELDS = {
    "version": "export-ai-v1",
    "note": "Anonymous: participant codes only; no free text (readings, questions and rater notes are NOT exported; only lengths). SIMULATED exports carry simulated=1, data_label SIMULATED and a banner: no AI model was used. Formal exports never contain simulated rows.",
    "task_level": {
        "participant_code": "random code, no link to identity", "sequence": "AB-S1 | AB-S2 | BA-S1 | BA-S2 (A = fixed template, B = contextual AI; letters in order of use)",
        "condition": "A | B", "tool": "template | ai_contextual", "tool_source": "fixed-template | SIMULATED-script | model:<name>",
        "no_model_used": "1 if the contextual-AI text for this task was written by a script (rehearsal); such rows say nothing about AI",
        "data_label": "SIMULATED | FORMAL", "simulated": "1 = simulated session", "task_id": "T1..T4", "task_kind": "age_cap | qualification_exception | age_preference | incomplete_evidence", "position": "order shown (1-4)",
        "attempted": "1 if started", "submitted": "1 if saved", "missing": "1 if not submitted OR empty (accuracy 0, not actionable)", "timed_out": "", "late": "",
        "elapsed_s": "server-measured seconds from task open to submit", "completion_time_s": "elapsed_s capped at the time limit; limit if started but not submitted",
        "time_limit_s": "", "reading_chars": "", "question_chars": "", "aid_inserted": "1 if the participant used the draft button", "model_failure": "1 if the tool could not produce a draft",
        "r1_facts..r3_unsupported": "each rater's fact bits (e.g. 101), question bits q1-q4 (e.g. 1101) and unsupported count; blank = not scored",
        "disagreement": "1 if R1 and R2 differ on any fact bit, q bit or unsupported count", "resolution": "agree | adjudicated | unresolved | unscored | missing",
        "final_facts": "final fact bits", "final_n_facts": "key facts of the task", "final_facts_correct": "", "final_accuracy": "PRIMARY, per task: facts correct / n facts (0 if missing)",
        "final_q": "final q1-q4 bits", "final_actionable": "1 if q1-q4 all 1 (0 if missing)", "final_unsupported": "SAFETY, per task: unsupported statement count (0 if missing)",
        "participant_status": "", "dropout": ""},
    "participant_level": {
        "participant_code": "", "sequence": "", "first_condition": "A or B (period 1)", "simulated": "", "data_label": "", "block_no": "", "tasks_attempted": "", "tasks_submitted": "", "tasks_missing": "",
        "acc_template / acc_ai / diff_acc": "PRIMARY: mean accuracy over the participant's template tasks, AI tasks; diff = AI - template (blank if any task unscored/unresolved)",
        "act_* / diff_act": "secondary: actionable question share", "uns_* / diff_uns": "safety: mean unsupported claims per task", "time_* / diff_time": "secondary: mean completion time (s) per task",
        "model_failures": "", "participant_status": "", "dropout": ""},
}


def _bits(d, ids):
    return "".join(str(d["facts"][i]) for i in ids)


def build_export(S, c, scope):
    sim = 1 if scope == "simulated" else 0
    doc = S.load_tasks()
    dsg = S.design(doc)
    kinds = {t["id"]: t["kind"] for t in doc["tasks"]}
    nfacts = {t["id"]: fact_ids(t) for t in doc["tasks"]}
    plist = c.execute("SELECT * FROM study_participants WHERE simulated=? ORDER BY enrolled_at, code", (sim,)).fetchall()
    t_now = S.now_ms()
    task_rows, part_rows = [], []
    label = "SIMULATED" if sim else "FORMAL"
    for p in plist:
        runs = {r["task_id"]: r for r in c.execute("SELECT * FROM study_task_runs WHERE code=?", (p["code"],))}
        dropout = int(p["status"] == "withdrawn" or (p["status"] != "completed" and t_now - p["last_activity_ms"] > S.INACTIVE_MIN * 60000))
        order = json.loads(p["task_order"])
        mine, attempted, submitted, fails = [], 0, 0, 0
        for pos, tid in enumerate(order, 1):
            r = runs.get(tid)
            cond = S.condition_of(dsg, p["arm"], tid)
            ids = nfacts[tid]
            row = {"participant_code": p["code"], "sequence": p["arm"], "condition": cond, "tool": TOOL_NAMES[cond], "tool_source": "", "no_model_used": "", "data_label": label,
                   "simulated": sim, "task_id": tid, "task_kind": kinds[tid], "position": pos, "attempted": int(bool(r)),
                   "submitted": int(bool(r and r["state"] in ("submitted", "withdrawn"))), "missing": 1, "timed_out": "", "late": "", "elapsed_s": "", "completion_time_s": "",
                   "time_limit_s": "", "reading_chars": "", "question_chars": "", "aid_inserted": "", "model_failure": ""}
            for rt in ("r1", "r2", "r3"):
                row.update({rt + "_facts": "", rt + "_q": "", rt + "_unsupported": ""})
            row.update({"notes_present": "", "disagreement": "", "resolution": "missing", "final_facts": "", "final_n_facts": len(ids), "final_facts_correct": "",
                        "final_accuracy": 0.0, "final_q": "", "final_actionable": 0, "final_unsupported": 0})
            if r:
                attempted += 1
                prov = r["aid_provider"] or ""
                row.update({"tool_source": prov if prov.startswith("model") else TOOL_SOURCE.get(prov, prov), "no_model_used": 1 if r["aid_simulated"] else 0,
                            "timed_out": r["timed_out"], "late": r["late"], "time_limit_s": r["limit_ms"] // 1000, "aid_inserted": r["aid_inserted"], "model_failure": r["model_failure"]})
                fails += r["model_failure"] or 0
                row["completion_time_s"] = float(r["limit_ms"] // 1000)
                if r["state"] in ("submitted", "withdrawn"):
                    submitted += 1
                    row["elapsed_s"] = round((r["elapsed_ms"] or 0) / 1000, 1)
                    row["completion_time_s"] = min(row["elapsed_s"], float(r["limit_ms"] // 1000))
                    row["reading_chars"], row["question_chars"] = len((r["reading"] or "").strip()), len((r["question_text"] or "").strip())
                    row["missing"] = 1 if not r["answer_chars"] else 0
                if p["status"] != "withdrawn" and not row["missing"]:
                    sc = _scores(c, r["item_key"])
                    for rt in ("R1", "R2", "R3"):
                        if rt in sc:
                            k = rt.lower()
                            row[k + "_facts"], row[k + "_q"], row[k + "_unsupported"] = _bits(sc[rt], ids), "".join(str(sc[rt][q]) for q in QS), sc[rt]["unsupported"]
                    row["notes_present"] = int(any((x["notes"] or "").strip() for x in c.execute("SELECT notes FROM study_scores_ai WHERE item_key=?", (r["item_key"],))))
                    res, fin, dis = resolve(sc)
                    row["resolution"], row["disagreement"] = res, dis
                    if fin:
                        ok = sum(fin["facts"][i] for i in ids)
                        row.update({"final_facts": _bits(fin, ids), "final_facts_correct": ok, "final_accuracy": round(ok / len(ids), 4),
                                    "final_q": "".join(str(fin[q]) for q in QS), "final_actionable": int(all(fin[q] for q in QS)), "final_unsupported": fin["unsupported"]})
                    else:
                        row.update({"final_accuracy": "", "final_actionable": "", "final_unsupported": ""})
            row["participant_status"], row["dropout"] = p["status"], dropout
            task_rows.append(row); mine.append(row)
        part_rows.append(dict({"participant_code": p["code"], "sequence": p["arm"], "first_condition": p["arm"][0], "simulated": sim, "data_label": label, "block_no": p["block_no"],
                               "tasks_attempted": attempted, "tasks_submitted": submitted, "tasks_missing": sum(1 for r in mine if r["missing"])},
                              **study_stats.person_columns(mine), model_failures=fails, participant_status=p["status"], dropout=dropout))
    meta = {"schema": EXPORT_FIELDS["version"], "scope": scope, "design": S.design_id(doc), "simulated": sim == 1, "banner": S.BANNER if sim else None,
            "simulated_notice": study_arms.SIM_NOTICE if sim else None, "generated_at": S.iso(), "tasks_version": doc["version"], "tasks_sha256": S.tasks_sha256(),
            "rubric_version": doc["rubric_ai"]["version"], "decision_rules": dsg.get("decision_rules"), "claim": dsg.get("claim"),
            "allocation": "permuted blocks of %d, seeded (%s)" % (S.BLOCK_SIZE, "SIM seed %d" % S.SIM_SEED if sim else "seed from APPROVAL.json"),
            "model": study_arms.model_status(), "n_participants": len(plist)}
    return {"meta": meta, "participants": part_rows, "tasks": task_rows,
            "scores": [{"participant_code": r["participant_code"], "task_id": r["task_id"], **{k: r[k] for k in r if k[:1] == "r" and k[1:2] in "123" and k[2:3] == "_"}} for r in task_rows if r["resolution"] != "missing"]}
