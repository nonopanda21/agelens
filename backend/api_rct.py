"""Routes for the randomized evaluation. The rules are in backend/rct.py and docs/EVAL_PLAN.md."""
import json
import os
import random
import secrets
import time

from . import api_study, llm, rct
from .server import HTTPError, Response, hash_token

BENCH_PROMPT = llm.PROMPT_DIR / "rct_benchmark_v1.txt"


def public_config(c):
    mode = rct.current_mode(c)
    sha, cases, _key, source = rct.active_set(c)
    return {"design": rct.DESIGN_ID, "mode": mode, "simulated": mode == "simulation", "banner": rct.BANNER if mode == "simulation" else None, "code_required": mode == "formal",
            "set_source": source, "set_version": cases.get("version"), "n_scored": len(cases["cases"]), "n_practice": len(cases.get("practice") or []), "time_limit_s": rct.time_limit_s(c),
            "labels": list(rct.LABELS), "consent_version": rct.CONSENT_VERSION}


def _benchmark_case(case, provider=None):
    """One independent model answer, away from any person's time. -> (label | None, status, latency_ms, provider name, model, prompt version)"""
    provider = provider or llm.get_provider()
    version, system = "rct_benchmark_v1", "\n".join(x for x in BENCH_PROMPT.read_text(encoding="utf-8").splitlines() if not x.startswith("#")).strip()
    if isinstance(provider, llm.TemplateProvider):
        return None, "no_model", 0, provider.name, None, version
    if llm.over_daily_limit():
        return None, "daily_limit", 0, provider.name, provider.model, version
    cv = case.get("cv") or {}
    user = "AD:\n%s\n\nCV:\n%s\n\nEntry date: %s" % (case["ad_text"], json.dumps(cv, ensure_ascii=False), case["entry_date"])
    t0 = time.time()
    try:
        out = provider.generate(None, system=system, user=user)
        label = out.get("label") if isinstance(out, dict) else None
        status = "ok" if label in rct.LABELS else "bad_label"
        reason = None if status == "ok" else "bad_label"
    except llm.ProviderError as e:
        label, status, reason = None, "failed", str(e)
    ms = int((time.time() - t0) * 1000)
    llm.log_call(provider.name, provider.model, version, ms, "ok" if status == "ok" else "error", reason, getattr(provider, "last_meta", None))
    return (label if status == "ok" else None), status, ms, provider.name, provider.model, version


def register(router):
    enabled = os.environ.get("AGELENS_RCT_ENABLED") != "0"  # on by default, in simulation mode unless every formal requirement is met

    @router.get("/api/rct/config")
    def config(req):
        if not enabled:
            return {"enabled": False}
        with rct.conn() as c:
            return dict(public_config(c), enabled=True)

    if not enabled:
        return

    @router.post("/api/rct/enrol")
    def enrol(req):
        body = req.json()
        code = str(body.get("code") or "").strip().upper()
        with rct.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            mode = rct.current_mode(c)
            if code:
                old = c.execute("SELECT * FROM rct_participants WHERE code=?", (code,)).fetchone()
                if old:  # back after closing the page: same group, same order, same clock
                    if old["status"] == "withdrawn":
                        c.rollback()
                        raise HTTPError(409, "This code has withdrawn from the test.")
                    token = secrets.token_urlsafe(18)
                    c.execute("UPDATE rct_participants SET token_hash=? WHERE code=?", (hash_token(token), code))
                    c.commit()
                    return {"code": code, "token": token, "resumed": True, "session": rct.session_view(c, old)}
                if not c.execute("SELECT 1 FROM rct_codes WHERE code=?", (code,)).fetchone():
                    c.rollback()
                    raise HTTPError(403, "That code is not on the list. Check it with the people running the test.")
            elif mode == "formal":
                c.rollback()
                raise HTTPError(403, "This test needs the code you were given.")
            if body.get("consent") is not True:
                c.rollback()
                raise HTTPError(400, "Consent is required to take part. Nothing was recorded.")
            sha, cases, _key, _source = rct.active_set(c)
            grp, block, pos = rct.allocate(c, mode, sha)
            code = code or "SIM-" + "".join(secrets.choice(rct.CODE_ALPHABET) for _ in range(6))
            scored = [x["id"] for x in cases["cases"]]
            random.Random("%s|order|%s" % (rct.alloc_seed(mode), code)).shuffle(scored)
            order = [x["id"] for x in cases.get("practice") or []] + scored
            token = secrets.token_urlsafe(18)
            c.execute("INSERT INTO rct_participants(code,token_hash,grp,mode,simulated,case_sha,block_no,block_pos,case_order,status,consent_version,consent_at,enrolled_at,last_activity_ms)"
                      " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (code, hash_token(token), grp, mode, 1 if mode == "simulation" else 0, sha, block, pos, json.dumps(order), "in_progress", rct.CONSENT_VERSION, rct.iso(), rct.iso(), rct.now_ms()))
            c.commit()
            p = c.execute("SELECT * FROM rct_participants WHERE code=?", (code,)).fetchone()
            return {"code": code, "token": token, "session": rct.session_view(c, p)}

    @router.get("/api/rct/session")
    def session(req):
        with rct.conn() as c:
            return rct.session_view(c, rct.participant(c, req))

    @router.post("/api/rct/next")
    def next_case(req):
        """Shows the case that is due. The clock starts on the first call and never restarts."""
        with rct.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            p = rct.participant(c, req)
            if p["status"] == "withdrawn":
                c.rollback()
                raise HTTPError(409, "You have withdrawn from the test.")
            now = rct.now_ms()
            i, run = rct.advance(c, p, now)
            if i is None:
                c.commit()
                return {"done": True, "session": rct.session_view(c, p)}
            order = json.loads(p["case_order"])
            cases, _key = rct.set_for(c, p["case_sha"])
            case = rct.case_index(cases)[order[i]]
            if run is None:
                c.execute("INSERT INTO rct_items(code,case_id,position,practice,displayed_ms,limit_ms) VALUES(?,?,?,?,?,?)",
                          (p["code"], order[i], i + 1, 1 if case["_practice"] else 0, now, rct.time_limit_s(c) * 1000))
                run = c.execute("SELECT * FROM rct_items WHERE code=? AND case_id=?", (p["code"], order[i])).fetchone()
            c.execute("UPDATE rct_participants SET last_activity_ms=? WHERE code=?", (now, p["code"]))
            c.commit()
            return {"done": False, "case": rct.participant_case(case), "remaining_ms": max(0, run["displayed_ms"] + run["limit_ms"] - now), "limit_ms": run["limit_ms"], "practice": bool(run["practice"]),
                    "tool": p["grp"] == "treatment", "tool_view": json.loads(run["tool_view"]) if run["tool_view"] else None, "session": rct.session_view(c, p)}

    @router.post("/api/rct/answer")
    def answer(req):
        body = req.json()
        cid, label = str(body.get("case_id") or ""), body.get("label")
        if label is not None and label not in rct.LABELS:
            raise HTTPError(400, "Choose one of: " + ", ".join(rct.LABELS) + ".")
        with rct.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            p = rct.participant(c, req)
            run = c.execute("SELECT * FROM rct_items WHERE code=? AND case_id=?", (p["code"], cid)).fetchone()
            if not run:
                c.rollback()
                raise HTTPError(409, "This case was not shown.")
            if run["state"] != "shown":  # a repeat or a late click: the first record stands
                c.commit()
                return {"ok": True, "already": True, "session": rct.session_view(c, p)}
            now = rct.now_ms()
            ms = now - run["displayed_ms"]
            cel = body.get("client_elapsed_ms")
            cel = int(cel) if isinstance(cel, (int, float)) and 0 <= cel < 10 ** 9 else None
            late = ms > run["limit_ms"] + rct.GRACE_MS
            if label is None or late:  # the clock ran out: no answer stands, and the time is the limit
                c.execute("UPDATE rct_items SET state='timed_out', submitted_ms=?, elapsed_ms=?, client_elapsed_ms=?, timed_out=1 WHERE code=? AND case_id=?",
                          (run["displayed_ms"] + run["limit_ms"], run["limit_ms"], cel, p["code"], cid))
            else:
                c.execute("UPDATE rct_items SET state='submitted', submitted_ms=?, elapsed_ms=?, client_elapsed_ms=?, label=? WHERE code=? AND case_id=?",
                          (now, min(ms, run["limit_ms"]), cel, label, p["code"], cid))
            c.execute("UPDATE rct_participants SET last_activity_ms=? WHERE code=?", (now, p["code"]))
            c.commit()
            return {"ok": True, "session": rct.session_view(c, p)}

    @router.post("/api/rct/tool")
    def tool(req):
        cid = str(req.json().get("case_id") or "")
        with rct.conn() as c:
            c.execute("BEGIN IMMEDIATE")
            p = rct.participant(c, req)
            if p["grp"] != "treatment":
                c.rollback()
                raise HTTPError(403, "AgeLens is not part of your version of this test.")
            run = c.execute("SELECT * FROM rct_items WHERE code=? AND case_id=?", (p["code"], cid)).fetchone()
            if not run or run["state"] != "shown":
                c.rollback()
                raise HTTPError(409, "This case is not open.")
            if rct.now_ms() > run["displayed_ms"] + run["limit_ms"]:
                c.rollback()
                raise HTTPError(409, "The time for this case has ended.")
            if run["tool_view"]:
                c.commit()
                return json.loads(run["tool_view"])
            opened = rct.now_ms()
            c.execute("UPDATE rct_items SET tool_opened_ms=COALESCE(tool_opened_ms,?) WHERE code=? AND case_id=?", (opened, p["code"], cid))
            cases, _key = rct.set_for(c, p["case_sha"])
            case = rct.case_index(cases)[cid]
            c.commit()
        # no database lock is held while the model runs
        from .api_seeker import check_pasted
        provider, model, version = None, None, None
        try:
            b = check_pasted(rct.tool_body(case))
            view = rct.tool_view(b)
            version = b.get("prompt_version")
            st = llm.status()
            provider, model = st.get("provider"), st.get("model")
        except HTTPError:
            raise
        except Exception:
            view = {"api_status": "failed", "states": "", "relates": "", "note": "The AI analysis failed on this ad, and nothing could be shown."}
        with rct.conn() as c:
            c.execute("UPDATE rct_items SET tool_returned_ms=?, tool_view=?, api_status=?, provider=?, model=?, prompt_version=? WHERE code=? AND case_id=?",
                      (rct.now_ms(), json.dumps(view, ensure_ascii=False), view["api_status"], provider, model, version, p["code"], cid))
            c.commit()
        return view

    @router.post("/api/rct/finish")
    def finish(req):
        used = req.json().get("used_other_tools")
        if used not in ("no", "yes"):
            raise HTTPError(400, "Please answer yes or no.")
        with rct.conn() as c:
            p = rct.participant(c, req)
            if rct.advance(c, p)[0] is not None:
                raise HTTPError(409, "There are still cases to answer.")
            c.execute("UPDATE rct_participants SET status='completed', other_tools=COALESCE(other_tools,?) WHERE code=?", (used, p["code"]))
            c.commit()
            return {"ok": True}

    @router.post("/api/rct/withdraw")
    def withdraw(req):
        with rct.conn() as c:
            p = rct.participant(c, req)
            c.execute("UPDATE rct_participants SET status='withdrawn', withdrawn_at=? WHERE code=?", (rct.iso(), p["code"]))
            c.execute("DELETE FROM rct_items WHERE code=?", (p["code"],))
            c.commit()
            return {"ok": True, "message": "You have withdrawn. Your answers were deleted; only the fact that you withdrew is kept."}

    # ---- people running the test ------------------------------------------------------------------

    @router.get("/api/rct/admin/status")
    def admin_status(req):
        api_study.require_study(req)
        with rct.conn() as c:
            sha, cases, key, source = rct.active_set(c)
            mode = rct.current_mode(c)
            # counts only: no scores or times, so nobody can watch the result and decide when to stop
            counts = [dict(r) for r in c.execute("SELECT mode, grp AS assigned_group, status, COUNT(*) AS n FROM rct_participants GROUP BY mode, grp, status ORDER BY mode, grp, status")]
            model_done = c.execute("SELECT COUNT(*) FROM rct_model_answers WHERE case_sha=? AND status='ok'", (sha,)).fetchone()[0]
            blockers = rct.formal_blockers(c)
            return dict(public_config(c), requested_mode=rct.get_setting(c, "mode", "simulation"), formal_allowed=not blockers, formal_blockers=blockers, case_set_sha256=sha, counts=counts,
                        codes_issued=c.execute("SELECT COUNT(*) FROM rct_codes").fetchone()[0], model=llm.status().get("label"), model_answers=model_done,
                        case_ids=[x["id"] for x in cases["cases"]], set_problems=rct.formal_problems(cases, key) if source == "imported" else None)

    @router.post("/api/rct/admin/mode")
    def admin_mode(req):
        api_study.require_study(req)
        want = str(req.json().get("mode") or "")
        if want not in ("simulation", "formal"):
            raise HTTPError(400, "mode must be 'simulation' or 'formal'.")
        with rct.conn() as c:
            if want == "formal":
                blockers = rct.formal_blockers(c)
                if blockers:
                    return 403, {"error": "Formal mode is refused: what a formal test requires is not in place.", "blockers": blockers, "mode": "simulation"}
            rct.set_setting(c, "mode", want)
            c.commit()
            return public_config(c)

    @router.post("/api/rct/admin/time-limit")
    def admin_limit(req):
        api_study.require_study(req)
        with rct.conn() as c:
            if rct.current_mode(c) != "simulation":
                raise HTTPError(403, "The time limit can only be changed in simulation mode.")
            v = req.json().get("seconds")
            if v in (None, "", 0):
                c.execute("DELETE FROM rct_settings WHERE key='sim_time_limit_s'")
            elif isinstance(v, int) and 2 <= v <= 3600:
                rct.set_setting(c, "sim_time_limit_s", v)
            else:
                raise HTTPError(400, "seconds must be an integer from 2 to 3600.")
            c.commit()
            return public_config(c)

    @router.post("/api/rct/admin/import")
    def admin_import(req):
        api_study.require_study(req)
        body = req.json()
        cases, key = body.get("cases"), body.get("answer_key")
        problems = rct.validate(cases, key)
        if problems:
            return 422, {"error": "This test set cannot be used.", "problems": problems[:40]}
        sha = rct.sha_of(cases, key)
        with rct.conn() as c:
            if c.execute("SELECT 1 FROM rct_participants WHERE mode='formal' LIMIT 1").fetchone():
                raise HTTPError(409, "A formal test has started, so the test set is frozen.")
            c.execute("INSERT OR REPLACE INTO rct_case_sets(sha,version,cases_json,key_json,imported_at) VALUES(?,?,?,?,?)",
                      (sha, str(cases.get("version") or "unversioned"), json.dumps(cases, ensure_ascii=False), json.dumps(key, ensure_ascii=False), rct.iso()))
            rct.set_setting(c, "active_sha", sha)
            c.commit()
            return {"ok": True, "case_set_sha256": sha, "formal_problems": rct.formal_problems(cases, key)}

    @router.post("/api/rct/admin/codes")
    def admin_codes(req):
        api_study.require_study(req)
        n = req.json().get("n")
        if not isinstance(n, int) or not 1 <= n <= 500:
            raise HTTPError(400, "n must be an integer from 1 to 500.")
        codes = ["P-" + "".join(secrets.choice(rct.CODE_ALPHABET) for _ in range(8)) for _ in range(n)]
        with rct.conn() as c:
            c.executemany("INSERT INTO rct_codes(code,created_at) VALUES(?,?)", [(x, rct.iso()) for x in codes])
            c.commit()
        return {"codes": codes}

    @router.post("/api/rct/admin/benchmark")
    def admin_benchmark(req):
        """One case per call so the page can show progress. The first answer per case stands unless a call failed."""
        api_study.require_study(req)
        cid = str(req.json().get("case_id") or "")
        with rct.conn() as c:
            sha, cases, _key, _source = rct.active_set(c)
            case = {x["id"]: x for x in cases["cases"]}.get(cid)
            if not case:
                raise HTTPError(404, "Unknown scored case.")
            old = c.execute("SELECT status FROM rct_model_answers WHERE case_sha=? AND case_id=?", (sha, cid)).fetchone()
            if old and old["status"] == "ok":
                return {"case_id": cid, "status": "ok", "already": True}
        label, status, ms, provider, model, version = _benchmark_case(case)
        with rct.conn() as c:
            c.execute("INSERT OR REPLACE INTO rct_model_answers(case_sha,case_id,label,status,provider,model,prompt_version,latency_ms,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                      (sha, cid, label, status, provider, model, version, ms, rct.iso()))
            c.commit()
        return {"case_id": cid, "status": status}  # the label stays out of the page, like the rest of the results

    @router.get("/api/rct/admin/export")
    def admin_export(req):
        api_study.require_study(req)
        scope, table = req.query.get("scope", "simulation"), req.query.get("table", "persons")
        if scope not in ("simulation", "formal"):
            raise HTTPError(400, "scope must be 'simulation' or 'formal'.")
        with rct.conn() as c:
            if table == "model":
                body = rct.to_csv(rct.model_rows(c), rct.MODEL_FIELDS)
            elif table in ("items", "persons"):
                items, persons = rct.export_rows(c, scope)
                body = rct.to_csv(items, rct.ITEM_FIELDS) if table == "items" else rct.to_csv(persons, rct.PERSON_FIELDS)
            else:
                raise HTTPError(400, "table must be items, persons or model.")
            c.commit()
        name = "agelens_rct_%s_%s_%s" % (scope, table, time.strftime("%Y%m%d-%H%M%S", time.gmtime()))
        return Response(body, 200, "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="%s.csv"' % name})
