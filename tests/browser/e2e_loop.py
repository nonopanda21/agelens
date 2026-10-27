"""End-to-end browser test of the full seeker -> reviewer -> seeker loop, driven only through the UI (automation task T02).
usage: ~/agelens-tools/pw/bin/python tests/browser/e2e_loop.py
Starts its OWN server (temp copy of data/agelens.db via AGELENS_DB, a free port in 8822-8829, AGELENS_REVIEWER_TOKEN),
and stops only that server. Screenshots: docs/screenshots/e2e/. Exit code 1 on any failed check.
Steps: seeker asks (example question) -> evidence + answer -> download brief -> select evidence -> submit for human review;
reviewer (separate browser context) signs in with the token -> asks for more information; seeker answers in My requests;
reviewer saves a draft (seeker must NOT see it) -> publishes facts vs to-verify; seeker sees ONLY the published reply;
reviewer closes; seeker sees Closed."""
import os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots" / "e2e"
SHOTS.mkdir(parents=True, exist_ok=True)
RVTOK = "e2e-reviewer-token-" + str(os.getpid())
DRAFT = "DRAFT-ONLY-7731: unpublished reviewer wording that the seeker must never see."
FACT = "The ad text says applicants should normally be under 35."
VERIFY = "Who decides on exceptions, and on what basis, is not stated in the ad."
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not extra else " -- " + str(extra)[:400]), flush=True)


def free_port():
    for p in range(8822, 8830):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise SystemExit("no free port in 8822-8829")


PORT = free_port()
BASE = f"http://127.0.0.1:{PORT}"
tmp = tempfile.mkdtemp(prefix="agelens_e2e_")
shutil.copy(ROOT / "data" / "agelens.db", os.path.join(tmp, "e2e.db"))
env = dict(os.environ, AGELENS_DB=os.path.join(tmp, "e2e.db"), AGELENS_REVIEWER_TOKEN=RVTOK)
srv = subprocess.Popen([str(ROOT / ".venv/bin/python"), "app.py", "--port", str(PORT)], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
errors, bad_http = [], []
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=1); break
        except Exception:
            if srv.poll() is not None:
                raise SystemExit("server exited early")
            time.sleep(0.2)
    else:
        raise SystemExit("server did not start")

    with sync_playwright() as pw:
        br = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])

        def page_of(ctx, label):
            p = ctx.new_page()
            p.on("console", lambda m: errors.append((label, m.text)) if m.type == "error" else None)
            p.on("pageerror", lambda e: errors.append((label, "pageerror " + str(e))))
            p.on("response", lambda r: bad_http.append((label, r.status, r.url)) if r.status >= 400 else None)
            return p

        def shot(p, name):
            p.evaluate("()=>{const n=document.getElementById('nav'); if(n) n.style.position='static'}")
            p.screenshot(path=str(SHOTS / name), full_page=True)
            p.evaluate("()=>{const n=document.getElementById('nav'); if(n) n.style.position=''}")

        sctx = br.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True, reduced_motion="reduce")
        rctx = br.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
        sp, rp = page_of(sctx, "seeker"), page_of(rctx, "reviewer")

        # ---------- 1. seeker: example question -> evidence -> brief
        sp.goto(BASE + "/#/seeker"); sp.wait_for_selector("#go-btn")
        sp.click("button:has-text('Use an example')")
        check("example fills the question", "38" in sp.input_value("#f-question"))
        shot(sp, "01_seeker_form.png")
        sp.click("#go-btn")
        sp.wait_for_selector("#answer .answer-title", timeout=45000)
        sp.wait_for_selector("#ads .card")
        ans = sp.inner_text("#answer")
        check("answer shows the five answer-first headings",
              all(s in ans for s in ("explicitly", "exceptions", "relate", "determined", "ask")), ans[:300])
        check("answer labelled Demo · Synthetic data", "Demo · Synthetic data" in ans)
        check("evidence cards listed", sp.locator("#ads .card").count() >= 2)
        with sp.expect_download() as dl:
            sp.click("button:has-text('Download brief (Markdown)')")
        md = Path(dl.value.path()).read_text(encoding="utf-8")
        check("brief downloads as Markdown with evidence ids", md.startswith("#") and "ad_" in md, md[:200])
        shot(sp, "02_seeker_answer.png")

        # ---------- 2. select evidence -> submit for human review
        boxes = sp.locator("#ads .card input[type=checkbox]")
        boxes.nth(0).check(); boxes.nth(1).check()
        sp.wait_for_selector("#submit-btn")
        check("selected evidence panel shows 2 of 10", "Selected evidence (2 of 10)" in sp.inner_text("#review"))
        sp.fill("#clar", "I am 38 with eight years in operations. The ads say normally under 35 with exceptions. Would my experience count as an exception?")
        shot(sp, "03_seeker_select.png")
        sp.click("#submit-btn")
        sp.wait_for_selector("#review a:has-text('Open my request')", timeout=20000)
        code = sp.inner_text("#review strong").strip()
        check("request submitted with a request number", code.startswith("AL-"), code)
        shot(sp, "04_seeker_submitted.png")

        # ---------- 3. reviewer (separate context): sign in, ask for more information
        rp.goto(BASE + "/#/reviewer"); rp.wait_for_selector("#rvtok")
        rp.fill("#rvtok", RVTOK); rp.click("button:has-text('Sign in')")
        rp.wait_for_selector(f".rv-item:has-text('{code}')")
        rp.click(f".rv-item:has-text('{code}')"); rp.wait_for_selector(".rv-body .rq-tl")
        body = rp.inner_text(".rv-body")
        check("reviewer sees question, consented background, 2 evidence ads", "exception" in body.lower() and "Operations manager" in body and "Evidence (2)" in body, body[:400])
        shot(rp, "05_reviewer_detail.png")
        rp.fill("#infobody", "Which city would you work in, and do you hold any certificates the ad might treat as an exception?")
        rp.click("button:has-text('Ask for more information')")
        rp.wait_for_function("document.querySelector('.rv-body')?.innerText.includes('Reviewer asked for more information')")
        check("status -> Needs information", "Needs information" in rp.inner_text(".rv-body header"))

        # ---------- 4. seeker answers in My requests
        sp.goto(BASE + "/#/requests"); sp.wait_for_selector(f".rq-item:has-text('{code}')")
        sp.click(f".rq-item:has-text('{code}')"); sp.wait_for_selector("#ans")
        check("seeker sees the reviewer's question", "certificates" in sp.inner_text(".rq").lower())
        sp.fill("#ans", "Shanghai. I hold a PMP certificate.")
        shot(sp, "06_seeker_needs_info.png")
        sp.click("button:has-text('Send answer')")
        sp.wait_for_function("document.body.innerText.includes('Waiting for a human reviewer')")
        check("answer sent -> waiting again", "You answered" in sp.inner_text(".rq-tl"))

        # ---------- 5. reviewer saves a draft; seeker must not see it
        rp.reload(); rp.wait_for_selector("#rbody")
        check("reviewer sees the seeker's answer", "PMP" in rp.inner_text(".rv-body"))
        rp.fill("#rbody", DRAFT)
        rp.fill("#rfacts", FACT)
        rp.fill("#rverify", VERIFY)
        rp.click("button:has-text('Save draft')")
        rp.wait_for_function("document.querySelector('.rv-reply .rq-status')?.innerText.startsWith('Draft saved')")
        shot(rp, "07_reviewer_draft.png")
        sp.reload(); sp.wait_for_selector(".rq-tl")
        check("seeker does NOT see the saved draft", DRAFT not in sp.content() and FACT not in sp.content())

        # ---------- 6. reviewer publishes (facts vs to-verify)
        final = "Thanks. The ad states a normal upper limit of 35 and says exceptions are possible; it does not say what qualifies."
        rp.fill("#rbody", final)
        rp.click("button:has-text('Review and publish')"); rp.wait_for_selector(".rv-confirm")
        rp.click(".rv-confirm button:has-text('Publish reply')")
        rp.wait_for_function("document.querySelector('.rv-body')?.innerText.includes('A reply has been published')")
        check("reviewer status -> Replied", "Replied" in rp.inner_text(".rv-body header"))
        shot(rp, "08_reviewer_published.png")

        sp.reload(); sp.wait_for_selector(".rq-reply")
        t, html = sp.inner_text(".rq"), sp.content()
        check("seeker sees the published reply", final in t)
        check("facts and to-verify shown separately", "Facts directly supported" in t and "need further verification" in t and FACT in t and VERIFY in t, t[:600])
        check("seeker sees ONLY the published text (draft absent)", DRAFT not in html and "DRAFT-ONLY" not in html)
        shot(sp, "09_seeker_reply.png")

        # ---------- 7. reviewer closes
        rp.click("button:has-text('Close request')"); rp.wait_for_selector(".rv-confirm")
        rp.click(".rv-confirm button:has-text('Close request')")
        rp.wait_for_function("document.querySelector('.rv-body')?.innerText.includes('This request is closed')")
        sp.reload(); sp.wait_for_selector(".rq-tl")
        check("seeker sees Closed", "Closed" in sp.inner_text(".rq-head"))
        tl = sp.inner_text(".rq-tl").lower()
        check("seeker timeline complete", all(x in tl for x in ("submitted", "asked for more", "answered", "reply published", "closed")), tl)
        shot(sp, "10_seeker_closed.png")

        check("no console errors", not errors, errors)
        check("no 4xx/5xx responses", not bad_http, bad_http)
        br.close()
except Exception as e:  # any timeout or crash is a failure, not a pass
    check("run completed without exception", False, repr(e))
finally:
    srv.terminate()
    try:
        srv.wait(timeout=5)
    except subprocess.TimeoutExpired:
        srv.kill()
    log = srv.stderr.read().decode(errors="replace") if srv.stderr else ""
    shutil.rmtree(tmp, ignore_errors=True)
check("server log has no request or draft text", "DRAFT-ONLY" not in log and "PMP" not in log)
fails = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
sys.exit(1 if fails else 0)
