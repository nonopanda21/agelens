"""Real-browser run of Pro stage 1 (pages/pro.js, backend/api_pro.py) on its own server (127.0.0.1, temp DB with the simulated
dataset, a 2-credit test Pro code). At 1280 and 360: Job Seeker answer -> "Full report" -> free preview (10 sections, summary)
-> wrong code refused -> right code -> report downloads as a Word file -> credits count down -> at 0 the button is disabled;
the Pro page shows the wallet and removes Pro from the browser. Fails on failed checks, console errors (expected 4xx filtered)
or horizontal overflow. Usage: ~/agelens-tools/pw/bin/python tests/browser/pro_flow.py   Screenshots: docs/screenshots/pro/."""
import hashlib, io, json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request, zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / ".venv/bin/python")
SHOTS = ROOT / "docs" / "screenshots" / "pro"
SHOTS.mkdir(parents=True, exist_ok=True)
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not extra else " -- " + str(extra)[:300]), flush=True)


def free_port():
    for p in range(8875, 8885):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise SystemExit("no free port")


CODES = {1280: "PRO-TEST-1280", 360: "PRO-TEST-0360"}
ENTRIES = [{"id": "pro_%d" % w, "label": "Test %d" % w, "credits": 2, "expires": "2099-12-31", "sha256": hashlib.sha256(c.encode()).hexdigest()} for w, c in CODES.items()]
tmp = tempfile.mkdtemp(prefix="agelens_pro_")
PORT = free_port()
BASE = f"http://127.0.0.1:{PORT}"
env = dict(os.environ, AGELENS_DB=os.path.join(tmp, "pro.db"), AGELENS_PRO_CODES=json.dumps(ENTRIES))
subprocess.run([PY, "scripts/import_csv.py", "--source", "sim"], cwd=ROOT, env=env, check=True, capture_output=True)
srv = subprocess.Popen([PY, "app.py", "--port", str(PORT)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
EXPECTED = ("401", "402", "403", "Failed to load resource")
try:
    for _ in range(100):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=1); break
        except Exception:
            time.sleep(0.2)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        errs = []
        for w in (1280, 360):
            tag = f"@{w}"
            ctx = b.new_context(viewport={"width": w, "height": 900}, accept_downloads=True)
            ctx.add_init_script("sessionStorage.setItem('al_splash_seen','1')")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and not any(x in m.text for x in EXPECTED) else None)
            pg.goto(BASE + "/#/seeker"); pg.wait_for_selector("#go-btn")
            pg.click("button:has-text('Use an example')"); pg.click("#go-btn"); pg.wait_for_selector(".answer-sec", timeout=60000)
            pg.click("button.pro-open"); pg.wait_for_selector(".pro-toc li")
            check(f"{tag}: free preview lists the 10 sections", pg.locator(".pro-toc li").count() == 10)
            check(f"{tag}: free preview shows summary numbers", "ads" in pg.inner_text(".pro-sum"))
            check(f"{tag}: no Pro yet -> code form, no generate button", pg.locator(".pro-panel .pro-code").count() == 1 and pg.locator("text=Generate the full report").count() == 0)
            pg.wait_for_timeout(300); pg.locator("#pro-panel").screenshot(path=str(SHOTS / f"panel_locked_{w}.png"))
            pg.fill("#pro-code-panel", "pro-wron-gxxx"); pg.click(".pro-panel .pro-code button"); pg.wait_for_selector(".pro-code .rq-status.error")
            check(f"{tag}: wrong code refused", "not valid" in pg.inner_text(".pro-code .rq-status"))
            pg.fill("#pro-code-panel", CODES[w].lower()); pg.click(".pro-panel .pro-code button"); pg.wait_for_selector("text=Generate the full report")
            check(f"{tag}: unlocked with 2 credits", "2 of 2" in pg.inner_text(".pro-action"))
            for left in (1, 0):
                with pg.expect_download(timeout=60000) as d:
                    pg.click("button:has-text('Generate the full report')")
                f = d.value.path()
                data = Path(f).read_bytes()
                ok = data[:2] == b"PK" and "word/document.xml" in zipfile.ZipFile(io.BytesIO(data)).namelist()
                check(f"{tag}: report downloaded as a Word file ({d.value.suggested_filename})", ok and d.value.suggested_filename.endswith(".docx"))
                pg.wait_for_selector(f"text={left} of 2 report credits left")
                check(f"{tag}: credits now {left}", True)
            check(f"{tag}: at 0 the button is disabled", pg.locator("button:has-text('No report credits left')").is_disabled())
            pg.locator("#pro-panel").screenshot(path=str(SHOTS / f"panel_used_{w}.png"))
            pg.goto(BASE + "/#/pro"); pg.wait_for_selector(".pro-wallet dl")
            check(f"{tag}: Pro page shows the wallet", "0 of 2 left" in pg.inner_text(".pro-wallet"))
            ov = pg.evaluate("document.documentElement.scrollWidth - innerWidth")
            check(f"{tag}: no horizontal overflow on the Pro page", ov <= 0, ov)
            pg.wait_for_timeout(500); pg.screenshot(path=str(SHOTS / f"pro_page_{w}.png"), full_page=True)
            pg.click("text=Remove Pro from this browser"); pg.wait_for_selector(".pro-wallet form.pro-code")
            check(f"{tag}: Pro removed from the browser", pg.evaluate("localStorage.getItem('al_pro')") is None)
            ctx.close()
        check("no console/page errors", not errs, errs)
        b.close()
finally:
    srv.terminate(); srv.wait(timeout=10)
    shutil.rmtree(tmp, ignore_errors=True)

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
sys.exit(1 if bad else 0)
