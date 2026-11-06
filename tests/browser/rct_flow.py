"""Real browser run of the randomized test on a SIMULATION server with the fictional rehearsal set. Scripted testers; nothing here is evidence.
Usage: PW=<playwright python> $PW tests/browser/rct_flow.py [base_url]    Env: STUDY_TOKEN, RCT_OUT (export dir), RCT_N (testers per width)"""
import json, os, random, sys, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8877"
TOK = os.environ.get("STUDY_TOKEN", "demo-study-token")
OUT = Path(os.environ.get("RCT_OUT", "/tmp"))
checks, fails = 0, []


def ok(cond, what):
    global checks
    checks += 1
    if not cond:
        fails.append(what)
        print("FAIL", what)


def desk(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "X-Study-Token": TOK})
    return json.loads(urllib.request.urlopen(r).read())


def answer(pg, label):
    pg.check("input[name=rct-label][value=%s]" % label)
    pg.click("#rct-submit")


def tester(ctx, rng, tag):
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(BASE + "/#/study")
    pg.wait_for_selector("#rct-begin")
    ok("SIMULATED" in pg.inner_text(".st-banner"), tag + " banner")
    pg.click("#rct-begin")
    ok(pg.locator(".notice.error").is_visible(), tag + " consent needed")
    pg.check("#rct-agree")
    pg.click("#rct-begin")
    pg.wait_for_selector("#rct-go")
    has_tool = "You can use AgeLens" in pg.inner_text("h1")
    pg.click("#rct-go")
    pg.wait_for_selector("#rct-submit")
    ok(pg.locator("#rct-tool").count() == (1 if has_tool else 0), tag + " tool only in treatment")
    # refresh must not reset the clock or change the case
    title = pg.inner_text("#rct-ad")
    pg.wait_for_timeout(2300)
    pg.reload()
    pg.wait_for_selector("#rct-clock")
    sec = int(pg.inner_text("#rct-clock").split(":")[1]) + 60 * int(pg.inner_text("#rct-clock").split(":")[0])
    ok(pg.inner_text("#rct-ad") == title, tag + " same case after refresh")
    ok(sec <= 118, tag + " clock kept after refresh, %ds" % sec)
    pg.click("#rct-submit")
    ok("Choose an answer" in pg.inner_text(".notice.error"), tag + " must choose")
    if has_tool:
        pg.click("#rct-tool")
        pg.wait_for_selector(".rct-tool-out", timeout=60000)
        t = pg.inner_text(".rct-tool-out")
        ok("The decision is yours" in t, tag + " tool shown")
        ok("No AI model" in t or "What the ad says" in t, tag + " tool states its source")
        pg.reload()
        pg.wait_for_selector(".rct-tool-out")
        ok(pg.locator("#rct-tool").count() == 0, tag + " tool output kept after refresh")
    answer(pg, "Conflict")
    pg.wait_for_function("document.querySelector('#rct-submit') && !document.querySelector('input[name=rct-label]:checked')")
    answer(pg, "Match")
    pg.wait_for_selector("text=Practice is over")
    pg.click("#rct-go")
    n = 0
    while True:
        pg.wait_for_selector("#rct-submit, [data-other]")
        if pg.locator("[data-other]").count():
            break
        n += 1
        ok(("Case %d of 6" % n) in pg.inner_text(".st-head h1"), tag + " progress %d" % n)
        body = pg.inner_text("body")
        for leak in ("gold", "Correct", "explicit", "indirect"):
            ok(leak not in body, tag + " no leak " + leak)
        if has_tool and n % 2:
            pg.click("#rct-tool")
            pg.wait_for_selector(".rct-tool-out", timeout=60000)
        answer(pg, rng.choice(["Match", "Conflict", "Unknown"]))
        pg.wait_for_function("n => !document.querySelector('.st-head h1') || !document.querySelector('.st-head h1').textContent.includes('Case ' + n + ' of')", arg=n)
    ok(n == 6, tag + " six cases")
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), tag + " no overflow")
    pg.click("[data-other=no]")
    pg.wait_for_selector("#rct-again")
    ok(not errs, tag + " console clean: %s" % errs[:2])
    pg.close()
    return has_tool


with sync_playwright() as p:
    b = p.chromium.launch()
    rng = random.Random(1)
    seen = set()
    for w, hgt in ((1280, 900), (360, 780)):
        for i in range(int(os.environ.get("RCT_N", 4))):
            ctx = b.new_context(viewport={"width": w, "height": hgt})
            seen.add(tester(ctx, rng, "%d/%d" % (w, i)))
            ctx.close()
    ok(seen == {True, False}, "both groups seen")
    # time out: the clock reaches zero and the next case appears
    desk("/api/rct/admin/time-limit", {"seconds": 3})
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.goto(BASE + "/#/study")
    pg.wait_for_selector("#rct-begin")
    pg.check("#rct-agree")
    pg.click("#rct-begin")
    pg.wait_for_selector("#rct-go")
    pg.click("#rct-go")
    pg.wait_for_selector("#rct-submit")
    t1 = pg.inner_text("#rct-ad")
    pg.wait_for_function("t => document.querySelector('#rct-ad') && document.querySelector('#rct-ad').textContent !== t", arg=t1, timeout=9000)
    ok(True, "time out moved on")
    ctx.close()
    desk("/api/rct/admin/time-limit", {"seconds": 0})
    # desk
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "/#/study/admin")
    pg.wait_for_selector("#rct-token")
    pg.fill("#rct-token", "wrong")
    pg.click("#rct-signin")
    pg.wait_for_selector(".notice.error")
    pg.fill("#rct-token", TOK)
    pg.click("#rct-signin")
    pg.wait_for_selector("#rct-mode")
    ok(pg.inner_text("#rct-mode") == "Simulation", "desk in simulation")
    text = pg.inner_text("#rct-blockers")
    for w in ("RCT_APPROVAL.json", "AGELENS_RCT_DURABLE"):
        ok(w in text, "blocker " + w)
    ok("score" not in pg.inner_text("#rct-counts").lower(), "no scores on the desk")
    for t in ("items", "persons"):
        with pg.expect_download() as d:
            pg.click("[data-export=simulation-%s]" % t)
        d.value.save_as(OUT / ("rct_%s.csv" % t))
    ok("simulation" in (OUT / "rct_persons.csv").read_text().splitlines()[1], "export row")
    pg.fill("#rct-ncodes", "2")
    pg.click("#rct-mkcodes")
    pg.wait_for_selector("#rct-codes:not([hidden])")
    ok(pg.inner_text("#rct-codes").startswith("P-"), "codes made")
    code = pg.inner_text("#rct-codes").split()[0]
    pg.click("#rct-bench")
    pg.wait_for_selector("text=AI answers finished", timeout=60000)
    ok("no_model" in pg.inner_text("#rct-msg"), "AI without a model is reported")
    # a real-looking Chinese set goes through the import, and the code logs in; it is fictional
    ok(not errs, "desk console clean %s" % errs[:2])
    ctx.close()
    ctx = b.new_context(viewport={"width": 360, "height": 780})
    pg = ctx.new_page()
    pg.goto(BASE + "/#/study")
    pg.wait_for_selector("#rct-code")
    pg.fill("#rct-code", code)
    pg.check("#rct-agree")
    pg.click("#rct-begin")
    pg.wait_for_selector("#rct-go")
    ok(code in pg.inner_text("body"), "issued code works")
    # coming back on another device keeps the group
    first = pg.inner_text("h1")
    ctx.close()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.goto(BASE + "/#/study")
    pg.wait_for_selector("#rct-code")
    pg.fill("#rct-code", code)
    pg.click("#rct-begin")
    pg.wait_for_selector("#rct-go")
    pg.click("#rct-go")
    pg.wait_for_selector("#rct-submit")
    ok((pg.locator("#rct-tool").count() == 1) == ("can use" in first), "same group on return")
    ctx.close()
    b.close()

print("%d/%d checks passed" % (checks - len(fails), checks))
sys.exit(1 if fails else 0)
