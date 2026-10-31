"""Real-browser rehearsal of the PUBLIC demo (app.py --public, invite codes; docs/DEPLOY.md). Self-contained: starts its own
server on 127.0.0.1 (never 0.0.0.0) with a fresh temp database (filled from the simulated dataset at start, as on the host),
fresh test invite codes and random secrets, then checks at 1280 and 360 px:
  gate on every route; wrong code refused; viewer code opens the site, nav shows "label · viewer", Reviewer link hidden;
  "Check one line" works; a personal code keeps a request across browsers; a shared code does not;
  a reviewer code opens the reviewer workspace without the shared token; sign out returns to the gate.
Fails (exit 1) on failed checks, console/page errors (expected 401 lines filtered) or horizontal overflow.
Usage: ~/agelens-tools/pw/bin/python tests/browser/public_demo.py     Screenshots: docs/screenshots/public/."""
import json, os, re, secrets, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / ".venv/bin/python")
SHOTS = ROOT / "docs" / "screenshots" / "public"
SHOTS.mkdir(parents=True, exist_ok=True)
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not extra else " -- " + str(extra)[:300]), flush=True)


def free_port():
    for p in range(8860, 8870):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise SystemExit("no free port in 8860-8869")


tmp = tempfile.mkdtemp(prefix="agelens_public_")
inv = os.path.join(tmp, "invites.json")


def make(*args):
    out = subprocess.run([PY, "scripts/invite.py", "--file", inv, "new", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return re.search(r"AL-[A-Z0-9]{4}-[A-Z0-9]{4}", out).group(0)


CODES = {"teacher": make("--role", "viewer", "--label", "Teacher", "--personal", "--expires", "2099-12-31"),
         "class": make("--role", "viewer", "--label", "SEPOL class", "--expires", "2099-12-31"),
         "rev": make("--role", "reviewer", "--label", "Reviewer A", "--personal", "--expires", "2099-12-31")}
PORT = free_port()
BASE = f"http://127.0.0.1:{PORT}"
env = dict(os.environ, AGELENS_DB=os.path.join(tmp, "public.db"), PORT=str(PORT),
           AGELENS_INVITES=subprocess.run([PY, "scripts/invite.py", "--file", inv, "env"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
           AGELENS_REVIEWER_TOKEN=secrets.token_urlsafe(24), AGELENS_STUDY_TOKEN=secrets.token_urlsafe(24))
srv = subprocess.Popen([PY, "app.py", "--public", "--host", "127.0.0.1"], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
EXPECTED = ("401", "Failed to load resource")
try:
    for _ in range(100):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=1); break
        except Exception:
            if srv.poll() is not None:
                raise SystemExit("server exited early")
            time.sleep(0.2)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        errs = []

        def page(ctx):
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and not any(x in m.text for x in EXPECTED) else None)
            return pg

        def open_quick_check(pg):  # an edge tab on wide screens, an item in the Menu on phones
            if pg.is_visible(".sk-tab"):
                pg.click(".sk-tab")
            else:
                pg.click(".nav-menu"); pg.click(".nav-qc")

        def enter(pg, code):
            pg.fill("#inv-code", code.lower()); pg.click("form.inv-form button[type=submit]")

        for w in (1280, 360):
            tag = f"@{w}"
            mk = lambda: b.new_context(viewport={"width": w, "height": 900})
            ctx = mk(); ctx.add_init_script("sessionStorage.setItem('al_splash_seen','1')"); pg = page(ctx)
            for route in ("#/", "#/findings", "#/requests", "#/reviewer", "#/study"):
                pg.goto(BASE + "/" + route); pg.wait_for_selector(".inv-form")
            check(f"{tag}: every route shows the invite page first", pg.locator(".inv-form").count() == 1)
            check(f"{tag}: no identity chip and no Reviewer link before entering", pg.evaluate("document.querySelector('.nav-access').hidden && document.querySelector('.nav-reviewer').hidden"))
            pg.wait_for_timeout(500); pg.screenshot(path=str(SHOTS / f"gate_{w}.png"), full_page=True)
            enter(pg, "AL-WRON-GXXX"); pg.wait_for_selector(".inv-form .rq-status.error")
            check(f"{tag}: wrong code refused", "not valid" in pg.inner_text(".inv-form .rq-status"))
            enter(pg, CODES["teacher"]); pg.wait_for_selector(".nav-access:not([hidden])", state="attached")
            pg.goto(BASE + "/#/"); pg.wait_for_selector(".xh", timeout=15000)
            check(f"{tag}: viewer code opens the site", pg.locator(".inv-form").count() == 0)
            check(f"{tag}: nav shows label · role", pg.evaluate("document.querySelector('.nav-access').textContent") == "Teacher · viewer")  # inside the Menu on phones
            check(f"{tag}: Reviewer link hidden for viewers", pg.evaluate("document.querySelector('.nav-reviewer').hidden"))
            check(f"{tag}: session keeps no invite code", CODES["teacher"].lower() not in (pg.evaluate("localStorage.getItem('al_session')") or "").lower())
            pg.wait_for_timeout(800); pg.screenshot(path=str(SHOTS / f"home_{w}.png"))
            pg.goto(BASE + "/#/about"); pg.wait_for_selector("main h1", timeout=15000)
            open_quick_check(pg); pg.click(".sk-chip >> nth=0"); pg.wait_for_selector(".sk-cls")
            check(f"{tag}: Check one line works behind the gate", pg.inner_text(".sk-cls") == "Cap with an exception")
            pg.keyboard.press("Escape")
            # a request sent with the personal code opens in another browser with the same code
            ad = pg.evaluate("AgeLens.api('/api/ads?page_size=1').then(r=>r.items[0])")
            made = pg.evaluate("(ad)=>AgeLens.api('/api/requests',{json:{question:'Is the stated age a hard cap? (%s)',evidence:[ad]}}).then(r=>{AgeLens.ownerTokens.add(r.code,r.token);return r})" % w, ad)
            check(f"{tag}: personal-code request kept on the code", made["on_invite"] is True)
            ctx2 = mk(); ctx2.add_init_script("sessionStorage.setItem('al_splash_seen','1')"); pg2 = page(ctx2)
            pg2.goto(BASE + "/#/requests"); pg2.wait_for_selector(".inv-form"); enter(pg2, CODES["teacher"]); pg2.wait_for_selector(".nav-access:not([hidden])", state="attached")
            pg2.goto(BASE + "/#/requests"); pg2.wait_for_selector(".rq-item")
            check(f"{tag}: same personal code in another browser lists the request", made["code"] in pg2.inner_text(".rq-list") and pg2.locator(".rq-acc").count() >= 1)
            pg2.goto(BASE + "/#/requests/" + made["code"]); pg2.wait_for_selector(".rq-head")
            check(f"{tag}: and opens it without the local key", made["code"] in pg2.inner_text(".rq-head"))
            pg2.screenshot(path=str(SHOTS / f"request_other_browser_{w}.png"), full_page=True)
            ctx2.close()
            # shared code: a request is NOT visible to another holder of the same code
            ctx3 = mk(); pg3 = page(ctx3); pg3.goto(BASE + "/"); pg3.wait_for_selector(".inv-form"); enter(pg3, CODES["class"]); pg3.wait_for_selector(".nav-access:not([hidden])", state="attached")
            shared = pg3.evaluate("(ad)=>AgeLens.api('/api/requests',{json:{question:'Shared code question (%s)',evidence:[ad]}})" % w, ad)
            ctx4 = mk(); pg4 = page(ctx4); pg4.goto(BASE + "/"); pg4.wait_for_selector(".inv-form"); enter(pg4, CODES["class"]); pg4.wait_for_selector(".nav-access:not([hidden])", state="attached")
            st = pg4.evaluate("(c)=>AgeLens.api('/api/requests/'+c).then(()=>200).catch(e=>e.status)", shared["code"])
            check(f"{tag}: shared code never shows another person's request", shared["on_invite"] is False and st in (401, 404), st)
            ctx3.close(); ctx4.close()
            # reviewer code: workspace without the shared token
            ctx5 = mk(); pg5 = page(ctx5); pg5.goto(BASE + "/#/reviewer"); pg5.wait_for_selector(".inv-form"); enter(pg5, CODES["rev"]); pg5.wait_for_selector(".nav-access:not([hidden])", state="attached")
            pg5.goto(BASE + "/#/reviewer"); pg5.wait_for_selector(".rv-queue .rv-item, .rv-queue", timeout=15000); pg5.wait_for_timeout(600)
            check(f"{tag}: reviewer code opens the workspace without the token form", pg5.locator("#rvtok").count() == 0 and not pg5.evaluate("document.querySelector('.nav-reviewer').hidden"))
            check(f"{tag}: reviewer sees the new requests", made["code"] in pg5.inner_text(".rv-queue"))
            pg5.screenshot(path=str(SHOTS / f"reviewer_{w}.png"), full_page=True)
            ctx5.close()
            # sign out
            pg.goto(BASE + "/#/access"); pg.wait_for_selector(".inv-card")
            pg.click("text=Sign out of this browser"); pg.wait_for_selector(".inv-form")
            check(f"{tag}: sign out returns to the invite page", pg.evaluate("document.querySelector('.nav-access').hidden"))
            ov = pg.evaluate("document.documentElement.scrollWidth - innerWidth")
            check(f"{tag}: no horizontal overflow", ov <= 0, ov)
            ctx.close()
        check("no console/page errors", not errs, errs)
        b.close()
finally:
    srv.terminate(); srv.wait(timeout=10)
    shutil.rmtree(tmp, ignore_errors=True)

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
sys.exit(1 if bad else 0)
