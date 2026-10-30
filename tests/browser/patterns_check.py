"""Patterns section (home, #patterns): renders from /api/stats/hetero?source=real, has no CJK, no horizontal overflow at 390 px,
and degrades silently (section absent, no console error) when the endpoint is missing.
Own server (free port 8880-8889, temp copy of data/agelens.db). The endpoint is answered from data/real/_fixture_hetero.json by
Playwright route interception when the server does not serve it yet; the 'missing' case aborts the route with a 404.
Usage: ~/agelens-tools/pw/bin/python tests/browser/patterns_check.py    Screenshots: docs/screenshots/patterns/. Exit 1 on failure."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots" / "patterns"; SHOTS.mkdir(parents=True, exist_ok=True)
FIX = (ROOT / "data/real/_fixture_hetero.json").read_text()
CJK = r"/[⺀-⿟　-〿぀-ヿ㄀-ㄯ㆐-ㇿ㐀-䶿一-鿿豈-﫿︰-﹏＀-￯]/"
results = []


def check(name, cond, extra=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + ("" if cond else " -- " + str(extra)[:300]), flush=True)


port = next(p for p in range(8880, 8890) if socket.socket().connect_ex(("127.0.0.1", p)) != 0)
tmp = tempfile.mkdtemp(prefix="agelens_pt_"); shutil.copy(ROOT / "data/agelens.db", tmp + "/p.db")
env = dict(os.environ, AGELENS_DB=tmp + "/p.db", AGELENS_REAL_FIXTURE=os.environ.get("AGELENS_REAL_FIXTURE", "1"))
srv = subprocess.Popen([str(ROOT / ".venv/bin/python"), "app.py", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
BASE = f"http://127.0.0.1:{port}"
try:
    for _ in range(300):
        try: urllib.request.urlopen(BASE + "/api/health", timeout=1); break
        except Exception: time.sleep(0.2)
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        for mode in ("data", "missing"):
            for w, hgt in ((1280, 900), (390, 844)):
                ctx = b.new_context(viewport={"width": w, "height": hgt}); pg = ctx.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and mode == "data" else None)
                if mode == "data":
                    pg.route("**/api/stats/hetero*", lambda r: r.fulfill(status=200, content_type="application/json", body=FIX))
                else:
                    pg.route("**/api/stats/hetero*", lambda r: r.fulfill(status=404, content_type="application/json", body='{"error":"none"}'))
                pg.goto(BASE + "/#/", wait_until="networkidle"); pg.wait_for_timeout(1200)
                n = pg.locator("#patterns .pt").count()
                tag = f"{mode} {w}px"
                if mode == "data":
                    check(f"{tag}: section renders", n == 1)
                    pg.locator("#patterns").scroll_into_view_if_needed(); pg.wait_for_timeout(600)
                    check(f"{tag}: 5+ charts", pg.locator("#patterns figure.pt-fig").count() >= 5, pg.locator("#patterns figure.pt-fig").count())
                    pg.select_option("#pt-band", index=0); pg.wait_for_timeout(200)
                    check(f"{tag}: band select redraws", pg.locator("#pt-occ").count() == 1)
                    check(f"{tag}: no CJK in section", not pg.evaluate("(() => { const R=" + CJK + "; return R.test(document.querySelector('#patterns').innerText + document.querySelector('#patterns').innerHTML) })()"))
                    pg.locator("#patterns").screenshot(path=str(SHOTS / f"patterns_{w}.png"))
                    toc = pg.locator(".mv-toc"); toc.scroll_into_view_if_needed(); pg.wait_for_timeout(500); toc.screenshot(path=str(SHOTS / f"toc_{w}.png"))
                    check(f"{tag}: no console/page errors", not errs, errs)
                else:
                    check(f"{tag}: section absent without endpoint", n == 0)
                    check(f"{tag}: no page errors", not errs, errs)
                ov = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                check(f"{tag}: no horizontal overflow", ov <= 0, ov)
                ctx.close()
        b.close()
finally:
    srv.terminate()
sys.exit(0 if all(results) else 1)
