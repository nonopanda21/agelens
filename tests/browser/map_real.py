"""Home map: real-data (Zhaopin) vs simulated-demo switch (frontend/js/mapcore.js, /api/real/status, /api/stats/matrix?source=real).
Self-contained: starts its own server on 127.0.0.1 (free port 8870-8879) with a temp copy of data/agelens.db. If a real
data/real/matrix_*.json exists it is used; otherwise the fixture data/real/_fixture_matrix.json (AGELENS_REAL_FIXTURE=1).
A second server with an empty real-data dir checks that no switch is shown when real data is missing.
At 1280 and 390 (iPhone 13): switch shown, default real, badge + caption show the meta numbers, switching to simulated and
back re-renders (ranking text changes, choice kept in sessionStorage across reload), no console errors, no horizontal overflow.
Usage: ~/agelens-tools/pw/bin/python tests/browser/map_real.py      Screenshots: docs/screenshots/map_real/. Exit 1 on failure."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / ".venv/bin/python")
SHOTS = ROOT / "docs" / "screenshots" / "map_real"
SHOTS.mkdir(parents=True, exist_ok=True)
ARGS = ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"]
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not extra else " -- " + str(extra)[:300]), flush=True)


def free_port(skip=()):
    for p in range(8870, 8880):
        if p in skip:
            continue
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise SystemExit("no free port in 8870-8879")


tmp = tempfile.mkdtemp(prefix="agelens_mapreal_")
shutil.copy(ROOT / "data" / "agelens.db", os.path.join(tmp, "a.db"))
shutil.copy(ROOT / "data" / "agelens.db", os.path.join(tmp, "b.db"))
real_dir = ROOT / "data" / "real"
has_real = any(real_dir.glob("matrix_*.json"))
empty_dir = os.path.join(tmp, "empty_real"); os.mkdir(empty_dir)


def start(port, db, extra):
    env = dict(os.environ, AGELENS_DB=db, **extra)
    env.pop("PORT", None)
    if has_real:
        env.pop("AGELENS_REAL_FIXTURE", None)
    srv = subprocess.Popen([PY, "app.py", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1); return srv
        except Exception:
            if srv.poll() is not None:
                raise SystemExit("server exited early")
            time.sleep(0.2)
    raise SystemExit("server did not start")


P1 = free_port(); s1 = start(P1, os.path.join(tmp, "a.db"), {} if has_real else {"AGELENS_REAL_FIXTURE": "1"})
P2 = free_port({P1}); s2 = start(P2, os.path.join(tmp, "b.db"), {"AGELENS_REAL_DIR": empty_dir})
B1, B2 = f"http://127.0.0.1:{P1}", f"http://127.0.0.1:{P2}"


def jget(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read().decode())


def fmt(n):
    return f"{n:,}"


def open_map(pg, base):
    pg.goto(base + "/#/"); pg.wait_for_timeout(800)
    pg.evaluate("document.getElementById('data-map-panel').scrollIntoView({block:'start', behavior:'instant'})")
    pg.wait_for_function("window.AgeLens._mapView && AgeLens._mapView.state()", timeout=30000)
    pg.wait_for_timeout(2500)


def rank_text(pg):
    return pg.inner_text(".mp-rank")


def overflow(pg):
    return pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


try:
    status = jget(B1 + "/api/real/status")
    mx = jget(B1 + "/api/stats/matrix?source=real")
    meta = mx.get("meta") or {}
    n_used = meta.get("rows_used", mx["total"]["ads"])
    print("real source:", "real file" if has_real else "FIXTURE", "|", mx["label"], "| rows_used", n_used, flush=True)
    check("API: real status available", status["available"])
    with sync_playwright() as p:
        b = p.chromium.launch(args=ARGS)
        for tag, kw in (("1280", {"viewport": {"width": 1280, "height": 900}}), ("390", dict(p.devices["iPhone 13"]))):
            ctx = b.new_context(**kw)
            ctx.add_init_script("sessionStorage.setItem('al_splash_seen','1')")
            pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            open_map(pg, B1)
            check(f"@{tag}: data switch shown", pg.locator(".mp-source .mp-segbtn").count() == 2)
            st = pg.evaluate("AgeLens._mapView.state()")
            check(f"@{tag}: default source is real", st["source"] == "real", st.get("source"))
            check(f"@{tag}: real pill pressed", pg.get_attribute('.mp-source .mp-segbtn[data-v="real"]', "aria-pressed") == "true")
            badge = pg.inner_text(".mp-bar .badge")
            check(f"@{tag}: badge shows the response label", badge.strip() == mx["label"], badge)
            cap = pg.inner_text(".mp-realcap") if pg.is_visible(".mp-realcap") else ""
            check(f"@{tag}: caption shows rows_used from meta", fmt(n_used) in cap and "not hiring or unemployment rates" in cap, cap)
            leg = pg.inner_text(".mp-leg-h") if pg.locator(".mp-leg-h").count() else ""
            check(f"@{tag}: legend uses the real-data small-sample threshold (500 ads)", "fewer than 500 ads" in leg, leg)
            check(f"@{tag}: no 'simulated' wording in the real view's visible panels",
                  "simulated" not in (pg.inner_text(".mp-detail") + pg.inner_text(".mp-heat")).lower())
            check(f"@{tag}: no CJK in map UI text", not pg.evaluate("""() => { const el = document.querySelector('.mp'); const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                while (w.nextNode()) { const t = w.currentNode; if (t.parentElement.closest('[lang^="zh"],.zh-orig')) continue; if (/[\\u3400-\\u9fff]/.test(t.textContent)) return true; } return false; }"""))
            pg.locator(".mp-bar").scroll_into_view_if_needed()
            pg.screenshot(path=str(SHOTS / f"real_{tag}.png"))
            pg.locator(".mp-row2").screenshot(path=str(SHOTS / f"real_rank_{tag}.png"))
            r_real = rank_text(pg); heat_real = pg.inner_text(".mp-heat"); tbl_real = pg.evaluate("document.querySelector('.mp-table tbody').textContent")
            det_real = pg.inner_text(".mp-detail"); chips_real = pg.evaluate("document.querySelector('.mp-chips').textContent")
            # switch to simulated
            pg.click('.mp-source .mp-segbtn[data-v="demo"]')
            pg.wait_for_function("AgeLens._mapView.state().source === 'demo'", timeout=15000); pg.wait_for_timeout(1500)
            check(f"@{tag}: simulated: badge reads Demo · Synthetic data", pg.inner_text(".mp-bar .badge").strip() == "Demo · Synthetic data")
            check(f"@{tag}: simulated: caption hidden", not pg.is_visible(".mp-realcap"))
            check(f"@{tag}: simulated: ranking re-rendered", rank_text(pg) != r_real)
            check(f"@{tag}: simulated: heatmap, table, All-regions panel and chips re-rendered",
                  pg.inner_text(".mp-heat") != heat_real and pg.evaluate("document.querySelector('.mp-table tbody').textContent") != tbl_real
                  and pg.inner_text(".mp-detail") != det_real and pg.evaluate("document.querySelector('.mp-chips').textContent") != chips_real)
            check(f"@{tag}: simulated: choice stored per tab", pg.evaluate("sessionStorage.getItem('al_map_source')") == "demo")
            pg.screenshot(path=str(SHOTS / f"sim_{tag}.png"))
            # reload keeps the choice
            open_map(pg, B1)
            check(f"@{tag}: reload keeps simulated", pg.evaluate("AgeLens._mapView.state().source") == "demo")
            # back to real
            r_sim = rank_text(pg)
            pg.click('.mp-source .mp-segbtn[data-v="real"]')
            pg.wait_for_function("AgeLens._mapView.state().source === 'real'", timeout=15000); pg.wait_for_timeout(1500)
            check(f"@{tag}: back to real: ranking re-rendered and matches first real view", rank_text(pg) != r_sim and rank_text(pg) == r_real)
            # 2D engine with real data + an industry + selection still works
            pg.click('.mp-segbtn[data-v="2d"]'); pg.wait_for_selector(".mp-stage svg"); pg.wait_for_timeout(800)
            if pg.is_visible(".mp-chip-sel"):  # phones: the industry choice is a select (mapcore.js)
                pg.select_option(".mp-chip-sel", index=1)
            else:
                pg.locator(".mp-chip").nth(1).click()
            pg.wait_for_timeout(600)
            pg.locator(".mp-rankbtn").first.click(); pg.wait_for_timeout(800)
            check(f"@{tag}: 2D + industry + selection on real data", pg.evaluate("AgeLens._mapView.state().selected") is not None)
            pg.locator(".mp-main").screenshot(path=str(SHOTS / f"real_2d_{tag}.png"))
            pg.locator(".mp-heat").screenshot(path=str(SHOTS / f"real_heat_{tag}.png"))
            pg.click('.mp-segbtn[data-v="3d"]'); pg.wait_for_timeout(1500)
            ov = overflow(pg)
            check(f"@{tag}: no horizontal overflow", ov <= 0, ov)
            check(f"@{tag}: no console errors", not errs, errs)
            ctx.close()
        # no real data -> no switch, simulated
        ctx = b.new_context(viewport={"width": 1280, "height": 900}); ctx.add_init_script("sessionStorage.setItem('al_splash_seen','1')")
        pg = ctx.new_page(); errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        open_map(pg, B2)
        check("no real data: no data switch", pg.locator(".mp-source").count() == 0)
        check("no real data: simulated badge", pg.inner_text(".mp-bar .badge").strip() == "Demo · Synthetic data" and pg.evaluate("AgeLens._mapView.state().source") == "demo")
        check("no real data: no console errors", not errs, errs)
        ctx.close(); b.close()
finally:
    for s in (s1, s2):
        s.terminate()
        try: s.wait(5)
        except Exception: s.kill()
    shutil.rmtree(tmp, ignore_errors=True)

bad = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
sys.exit(1 if bad else 0)
