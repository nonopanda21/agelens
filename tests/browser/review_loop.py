"""Real-browser run of the full human-review loop (seeker UI + reviewer UI in separate contexts).
Run with the Playwright python: <scratchpad>/pw/bin/python tests/browser/review_loop.py
Starts its own server on port 8805 with a temp copy of the DB; kills only that server."""
import json, os, shutil, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots" / "review"
PORT, RVTOK = 8805, "demo-review-token-8805"
BASE = f"http://127.0.0.1:{PORT}"
results, problems = [], []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (" -- " + str(extra) if extra and not cond else ""))


def api(path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


tmp = tempfile.mkdtemp()
shutil.copy(ROOT / "data" / "agelens.db", tmp + "/t.db")
env = dict(os.environ, AGELENS_DB=tmp + "/t.db", AGELENS_REVIEWER_TOKEN=RVTOK)
srv = subprocess.Popen([str(ROOT / ".venv/bin/python"), "app.py", "--port", str(PORT)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
try:
    for _ in range(50):
        try:
            urllib.request.urlopen(BASE + "/api/health"); break
        except Exception:
            time.sleep(0.2)
    ads = api("/api/ads?page_size=2&include_demo=true")[1]["items"]
    ev = [api("/api/ads/" + a["id"])[1] for a in ads[:2]]
    for e in ev:
        e["is_demo"] = True
    st, made = api("/api/requests", {"question": "I am 38 with eight years of procurement experience. The ad says normally under 35 but exceptions are possible. What should I clarify?",
                                     "profile": {"age": 38, "occupation": "Procurement", "years_experience": 8}, "consent": {"fields": ["age", "occupation", "years_experience"]},
                                     "evidence": ev, "scope": {"matched_total": 2}}, {"X-Idempotency-Key": "browser-run-0001-key"})
    check("seeker request created via API", st == 201, made)
    code, tok = made["code"], made["token"]
    st2, dup = api("/api/requests", {"question": "I am 38 with eight years of procurement experience. The ad says normally under 35 but exceptions are possible. What should I clarify?",
                                     "profile": {"age": 38, "occupation": "Procurement", "years_experience": 8}, "consent": {"fields": ["age", "occupation", "years_experience"]},
                                     "evidence": ev, "scope": {"matched_total": 2}}, {"X-Idempotency-Key": "browser-run-0001-key"})
    check("duplicate key returns original code, no 2nd row", st2 == 200 and dup["code"] == code and dup["duplicate"], dup)

    with sync_playwright() as pw:
        br = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        errors = []

        def ctx(w=1280, h=900, tokens=None):
            c = br.new_context(viewport={"width": w, "height": h})
            if tokens is not None:
                c.add_init_script("try{ if(!localStorage.getItem('al_owner_tokens')) localStorage.setItem('al_owner_tokens', %s) }catch(e){}" % json.dumps(json.dumps(tokens)))
            return c

        def page_of(c, label):
            p = c.new_page()
            p.on("console", lambda m: errors.append((label, m.text)) if m.type == "error" and "Failed to load resource" not in m.text else None)
            p.on("pageerror", lambda e: errors.append((label, str(e))))
            return p

        def shot(p, name):
            p.screenshot(path=str(SHOTS / name), full_page=True)

        def overflow(p):
            return p.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")

        seeker_ctx, rv_ctx = ctx(tokens={code: tok}), ctx()
        sp, rp = page_of(seeker_ctx, "seeker"), page_of(rv_ctx, "reviewer")

        # ---- seeker: list + detail, pending
        sp.goto(BASE + "/#/requests"); sp.wait_for_selector(".rq-item")
        check("my requests lists the request with sim badge", code in sp.inner_text(".rq-list") and "Demo · Synthetic data" in sp.inner_text(".rq-list"))
        shot(sp, "requests_list_1280.png")
        sp.click(".rq-item"); sp.wait_for_selector(".rq-tl")
        check("seeker sees consent + timeline (created)", "Shared with your consent" in sp.inner_text(".rq") and "You submitted this request" in sp.inner_text(".rq-tl"))
        check("seeker pending notice", "Waiting for a human reviewer" in sp.inner_text(".rq"))
        shot(sp, "requests_pending_1280.png")

        # ---- reviewer: wrong token then right token
        rp.goto(BASE + "/#/reviewer"); rp.wait_for_selector("#rvtok")
        shot(rp, "reviewer_signin_1280.png")
        rp.fill("#rvtok", "wrong-token"); rp.click("button:has-text('Sign in')")
        rp.wait_for_selector("#rvtok"); rp.wait_for_function("document.querySelector('.rq-status.error, .rq-status.field-err')")  # the sign-in note uses field-err
        check("wrong token -> clear message on sign-in", "Sign in" in rp.inner_text(".rq-status") or "token" in rp.inner_text(".rq-status").lower(), rp.inner_text(".rq-status"))
        rp.fill("#rvtok", RVTOK); rp.click("button:has-text('Sign in')")
        rp.wait_for_selector(".rv-item")
        check("queue shows pending request with counts", code in rp.inner_text(".rv-queue") and "Pending" in rp.inner_text(".rv-tabs"))
        rp.click(f".rv-item:has-text('{code}')"); rp.wait_for_selector(".rv-body .rq-tl")
        body = rp.inner_text(".rv-body")
        check("reviewer sees consent, sim label, evidence, history", all(s in body for s in ("Shared with the seeker", "Simulated case", "Demo · Synthetic data", "Status history", "Evidence (2)")), body[:300])
        check("only consented fields shown", "Procurement" in body and "Age" in body)
        shot(rp, "reviewer_detail_1280.png")

        # ---- reviewer asks for info via UI
        rp.fill("#infobody", "Which city would you work in, and is the 35 limit stated for the whole role?")
        rp.click("button:has-text('Ask for more information')")
        rp.wait_for_function("document.querySelector('.rv-body')?.innerText.includes('Reviewer asked for more information')")
        check("info request recorded -> status Needs information", "Needs information" in rp.inner_text(".rv-body header"))

        # ---- seeker answers via UI
        sp.reload(); sp.wait_for_selector("#ans")
        check("seeker sees reviewer question + answer form", "which city" in sp.inner_text(".rq-quote").lower())
        sp.fill("#ans", "Shanghai. The limit is in the general requirements section.")
        sp.reload(); sp.wait_for_selector("#ans")
        check("seeker answer draft survives reload (session)", "Shanghai" in sp.input_value("#ans"))
        shot(sp, "requests_needs_info_1280.png")
        sp.click("button:has-text('Send answer')")
        sp.wait_for_function("document.body.innerText.includes('Waiting for a human reviewer')")
        check("seeker answer sent -> pending again", "You answered" in sp.inner_text(".rq-tl"))

        # ---- reviewer drafts, saves; seeker must not see it
        rp.reload(); rp.wait_for_selector("#rbody")
        check("reviewer sees the seeker answer", "Shanghai" in rp.inner_text(".rv-body"))
        rp.fill("#rbody", "DRAFTSECRET: The ad states a normal upper limit of 35 and mentions possible exceptions.")
        rp.fill("#rfacts", "The ad text says applicants should normally be under 35.\nThe ad text mentions exceptions are possible.")
        rp.fill("#rverify", "Who decides on exceptions and on what basis is not stated.")
        check("unsaved changes flagged", "Unsaved" in rp.inner_text(".rv-reply .rq-status"))
        rp.click("button:has-text('Save draft')")
        rp.wait_for_function("document.querySelector('.rv-reply .rq-status')?.innerText.startsWith('Draft saved')")
        sp.reload(); sp.wait_for_selector(".rq-tl")
        check("seeker page has no draft text/event", "DRAFTSECRET" not in sp.content() and "draft" not in sp.inner_text(".rq-tl").lower())
        rp.reload(); rp.wait_for_selector("#rbody")
        check("draft restored after reload", "DRAFTSECRET" in rp.input_value("#rbody"))

        # ---- publish needs confirm; error path keeps text
        rp.fill("#rrewrite", "Applicants are encouraged to apply; typical experience is 5+ years.")
        rp.route("**/publish", lambda r: r.abort())
        rp.click("button:has-text('Review and publish')"); rp.wait_for_selector(".rv-confirm")
        shot(rp, "reviewer_confirm_publish_1280.png")
        rp.click(".rv-confirm button:has-text('Publish reply')")
        rp.wait_for_function("document.querySelector('.rv-reply .rq-status.error')")
        check("network failure on publish keeps text + message", "DRAFTSECRET" in rp.input_value("#rbody") and "try again" in rp.inner_text(".rv-reply .rq-status").lower(), rp.inner_text(".rv-reply .rq-status"))
        rp.unroute("**/publish")
        st_now = api("/api/requests/" + code, None, {"X-Owner-Token": tok})[1]["status"]
        check("nothing published while confirm pending/failed", st_now == "pending", st_now)
        rp.click("button:has-text('Review and publish')"); rp.wait_for_selector(".rv-confirm")
        rp.click(".rv-confirm button:has-text('Cancel')")
        check("cancel closes confirm", rp.locator(".rv-confirm").count() == 0)
        rp.click("button:has-text('Review and publish')"); rp.wait_for_selector(".rv-confirm")
        rp.click(".rv-confirm button:has-text('Publish reply')")
        rp.wait_for_function("document.querySelector('.rv-body')?.innerText.includes('A reply has been published')")
        check("published -> status Replied, editor gone", "Replied" in rp.inner_text(".rv-body header") and rp.locator("#rbody").count() == 0)

        sp.reload(); sp.wait_for_selector(".rq-reply")
        t = sp.inner_text(".rq")
        check("seeker sees published reply with facts / verify / rewrite separate", all(s in t for s in ("Facts directly supported", "need further verification", "Suggested neutral wording", "Reply published")))
        shot(sp, "requests_replied_1280.png")

        # ---- close
        rp.click("button:has-text('Close request')"); rp.wait_for_selector(".rv-confirm")
        rp.click(".rv-confirm button:has-text('Close request')")
        rp.wait_for_function("document.querySelector('.rv-body')?.innerText.includes('This request is closed')")
        sp.reload(); sp.wait_for_selector(".rq-tl")
        check("seeker sees Closed", "Closed" in sp.inner_text(".rq-head"))
        check("seeker timeline complete", [x for x in ("submitted", "asked for more", "answered", "Reply published", "closed") if x.lower() in sp.inner_text(".rq-tl").lower()].__len__() == 5, sp.inner_text(".rq-tl"))

        # ---- expired token on reviewer side
        rp.evaluate("sessionStorage.setItem('al_reviewer_token','expired-token')")
        rp.goto(BASE + "/#/reviewer"); rp.wait_for_selector("#rvtok")
        rp.wait_for_function("document.querySelector('.rq-status.error, .rq-status.field-err')")  # the sign-in note uses field-err
        check("expired token -> sign-in with message, not blank", "Sign in" in rp.inner_text(".rq") and rp.inner_text(".rq-status").strip() != "", rp.inner_text(".rq"))
        shot(rp, "reviewer_token_expired_1280.png")
        # mid-session expiry: valid sign-in, then token turns bad, click an item
        rp.fill("#rvtok", RVTOK); rp.click("button:has-text('Sign in')"); rp.wait_for_selector(".rv-tabs")
        rp.evaluate("sessionStorage.setItem('al_reviewer_token','gone')")
        rp.click(".rv-tab:has-text('Closed')")
        rp.wait_for_selector("#rvtok")
        check("mid-session expiry -> sign-in with message", rp.locator(".rq-status.error, .rq-status.field-err").count() == 1 and rp.inner_text(".rq-status").strip() != "")

        # ---- wrong-owner / no-token browser
        for label, toks in (("no token", {}), ("wrong token", {code: "not-the-owner-token"})):
            c = ctx(tokens=toks); p = page_of(c, label)
            p.goto(BASE + "/#/requests/" + code); p.wait_for_selector(".rq-recover")
            txt = p.inner_text(".rq")
            check(f"{label}: explains key lives in submitting browser", "only in the browser where you submitted" in txt and "Check an ad" in txt)
            check(f"{label}: no request content leaked", "procurement" not in txt.lower())
            if label == "no token":
                shot(p, "requests_no_token_1280.png")
            p.goto(BASE + "/#/requests"); p.wait_for_selector(".rq-empty,.rq-list,.notice")
            c.close()
        # empty list state
        c = ctx(); p = page_of(c, "empty"); p.goto(BASE + "/#/requests"); p.wait_for_selector(".rq-empty")
        check("empty list invites action", p.locator(".rq-empty a:has-text('Check an ad')").count() == 1)
        shot(p, "requests_empty_1280.png"); c.close()

        # ---- server unreachable -> retry
        sp.route("**/api/requests/mine", lambda r: r.abort())
        sp.goto(BASE + "/#/requests"); sp.wait_for_selector(".rq-err")
        check("unreachable server -> message + Try again", "Cannot reach" in sp.inner_text(".rq-err") and sp.locator(".rq-err button").count() == 1)
        sp.unroute("**/api/requests/mine"); sp.click(".rq-err button"); sp.wait_for_selector(".rq-item")
        check("retry recovers", True)

        # ---- empty reviewer queue tab
        rp.fill("#rvtok", RVTOK) if rp.locator("#rvtok").count() else None
        if rp.locator("#rvtok").count():
            rp.click("button:has-text('Sign in')")
        rp.wait_for_selector(".rv-tabs"); rp.click(".rv-tab:has-text('Pending')")
        rp.wait_for_selector(".rv-empty")
        shot(rp, "reviewer_empty_pending_1280.png")

        # ---- mobile 360: seeker detail, reviewer detail
        mc = ctx(360, 740, tokens={code: tok}); mp = page_of(mc, "m-seeker")
        mp.goto(BASE + "/#/requests/" + code); mp.wait_for_selector(".rq-tl")
        o1 = overflow(mp); shot(mp, "requests_detail_360.png")
        mp.goto(BASE + "/#/requests"); mp.wait_for_selector(".rq-item"); o2 = overflow(mp); shot(mp, "requests_list_360.png")
        # fresh request for mobile reviewer editor
        st, m2 = api("/api/requests", {"question": "Second mobile question about an ad with a 40 year cap?", "profile": {"age": 41}, "evidence": ev[:1]})
        mr = ctx(360, 740); mrp = page_of(mr, "m-reviewer")
        mrp.goto(BASE + "/#/reviewer"); mrp.fill("#rvtok", RVTOK); mrp.click("button:has-text('Sign in')"); mrp.wait_for_selector(".rv-item")
        o3 = overflow(mrp); shot(mrp, "reviewer_queue_360.png")
        mrp.click(".rv-item"); mrp.wait_for_selector("#rbody"); o4 = overflow(mrp); shot(mrp, "reviewer_detail_360.png")
        check("no horizontal overflow at 360 (seeker detail/list, reviewer queue/detail)", max(o1, o2, o3, o4) <= 0, (o1, o2, o3, o4))
        o5 = overflow(rp); check("no horizontal overflow 1280", o5 <= 0, o5)
        check("no console errors", not errors, errors)
        br.close()
finally:
    srv.terminate(); srv.wait(timeout=5)
    log = srv.stderr.read().decode() if srv.stderr else ""
    check("server log has no request text", "DRAFTSECRET" not in log and "procurement" not in log.lower())
fails = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
sys.exit(1 if fails else 0)
