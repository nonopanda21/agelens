"""Regional + industry map v2 (home 'data' section): browser checks and screenshots.
Usage: ~/agelens-tools/pw/bin/python tests/browser/map_v2.py [base-url]   (default http://127.0.0.1:8841)
Software WebGL (SwiftShader) in headless Chromium; timings describe this environment only.
Exercises: lazy init on scroll, every metric, two industries, selection via map click / ranked list / heatmap cell /
keyboard, reset, dot-strip hover sync, 2D fallback with WebGL disabled, 360 px mobile (no horizontal overflow),
reduced motion, console errors, CJK text in the map UI. Screenshots -> docs/screenshots/map_v2/. Exit 1 on a failed check."""
import json, os, re, sys
from playwright.sync_api import sync_playwright
OPEN_MORE = "new MutationObserver(() => document.querySelectorAll('details.mp-more:not([data-t])').forEach((d) => { d.open = true; d.dataset.t = '1'; })).observe(document, {childList: true, subtree: true})"  # the map's extra views sit under "More views" (closed by default); these checks need them open

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8841"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "screenshots", "map_v2")
os.makedirs(OUT, exist_ok=True)
ARGS = ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"]
NO_WEBGL = """(()=>{ const g = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (k, o) { if (/webgl/.test(k)) return null; return g.call(this, k, o); }; })();"""
CJK = re.compile(r"[㐀-鿿]")
fails, res = [], {}


def check(cond, msg):
    if not cond:
        fails.append(msg)
    return cond


def shot(pg, name, sel=None):
    p = os.path.join(OUT, name)
    (pg.locator(sel).first.screenshot(path=p) if sel else pg.screenshot(path=p))


def watch(pg, tag):
    errs = []
    pg.on("console", lambda m: errs.append(f"{tag}: {m.text}") if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(f"{tag}: {e}"))
    return errs


def st(pg):
    return pg.evaluate("AgeLens._mapView.state()")


def open_map(pg, wait=4500):
    pg.goto(BASE + "/#/"); pg.wait_for_timeout(1200)
    res.setdefault("lazy", {})[pg.viewport_size["width"]] = pg.evaluate("!!window.AgeLens._mapView")
    pg.evaluate("document.getElementById('data-map-panel').scrollIntoView({block:'start'})")
    pg.wait_for_function("window.AgeLens._mapView && AgeLens._mapView.state()", timeout=20000)
    pg.wait_for_timeout(wait)


def cjk_in_map(pg):
    """CJK characters in visible map UI text (quoted evidence is not part of the map, so the allowance is zero)."""
    return pg.evaluate("""() => { const el = document.querySelector('.dt'); if (!el) return -1;
        const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n = 0, s = '';
        while (w.nextNode()) { const t = w.currentNode; const m = t.textContent.match(/[\\u3400-\\u9fff]/g); if (m) { n += m.length; s += t.textContent.slice(0, 20) + '|'; } }
        return n ? n + ' ' + s : 0; }""")


with sync_playwright() as p:
    b = p.chromium.launch(args=ARGS)
    allerr = []

    # ---------------- desktop 3D @2x ----------------
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    ctx.add_init_script(OPEN_MORE); pg = ctx.new_page(); allerr += watch(pg, "desktop")
    pg.goto(BASE + "/#/"); pg.wait_for_timeout(1500)
    check(not pg.evaluate("!!window.AgeLens._mapView"), "map initialised before it was scrolled into view")
    check(pg.get_attribute(".dt-collapse", "aria-expanded") == "true", "map panel is not open by default")
    # intro frame sequence: scroll in and capture the rise + bar growth
    pg.evaluate("document.getElementById('data-map-panel').scrollIntoView({block:'start'})")
    pg.wait_for_function("window.AgeLens._mapView && AgeLens._mapView.stats() && AgeLens._mapView.stats().intro !== 'pending'", timeout=20000)
    for i, t in enumerate((0, 350, 350, 450, 600)):
        pg.wait_for_timeout(t); shot(pg, f"intro_{i}.png", ".mp-stage")
    pg.wait_for_timeout(2500)
    s = st(pg); stats = pg.evaluate("AgeLens._mapView.stats()")
    res["engine"] = s["engine"]; res["intro"] = stats["intro"]; res["draws_after_intro"] = stats["draws"]
    check(s["engine"] == "3d", "3D engine did not start under SwiftShader")
    check(stats["intro"] == "done", "intro did not finish")
    shot(pg, "desktop_default_aw.png", ".dt-panel")
    res["cjk_map_ui"] = cjk_in_map(pg); check(res["cjk_map_ui"] == 0, f"CJK text in map UI: {res['cjk_map_ui']}")

    # every metric: state, legend and spread change; tween frames run then stop
    res["metrics"] = {}
    for key, label in (("ads", "Ad count"), ("aw", "Any age wording"), ("cap", "Explicit cap"), ("exc", "Mentions an exception"), ("med", "Median max age")):
        pg.evaluate("document.getElementById('data-map-panel').scrollIntoView({block:'start'})"); pg.wait_for_timeout(200)
        f0 = pg.evaluate("AgeLens._mapView.stats().frames")
        pg.locator(".mp-metrics .mp-segbtn", has_text=label).click(); pg.wait_for_timeout(1300)
        s = st(pg); sp = s["spread"]
        res["metrics"][key] = {"hi": sp and sp["hi"], "lo": sp and sp["lo"], "range": sp and round(sp["range"], 3), "n": sp and sp["n"],
                               "tween_frames": pg.evaluate("AgeLens._mapView.stats().frames") - f0,
                               "legend": pg.inner_text(".mp-leg-bar")}
        check(s["metric"] == key, f"metric {key} not applied")
        check(pg.get_attribute(f".mp-metrics [data-v={key}]", "aria-pressed") == "true", f"metric button {key} not pressed")
        check("discrimination rate" not in pg.inner_text(".mp-mdesc").lower(), "metric text calls the share a discrimination rate")
        if key == "cap":
            shot(pg, "desktop_metric_cap.png", ".mp-main")
    # metric tween frame sequence (aw -> exc)
    pg.locator(".mp-metrics .mp-segbtn", has_text="Any age wording").click(); pg.wait_for_timeout(1300)
    pg.locator(".mp-metrics .mp-segbtn", has_text="Mentions an exception").click()
    for i in range(4):
        pg.wait_for_timeout(200); shot(pg, f"tween_{i}.png", ".mp-stage")
    pg.wait_for_timeout(800)
    pg.locator(".mp-metrics .mp-segbtn", has_text="Any age wording").click(); pg.wait_for_timeout(1000)

    # render on demand: idle (before the idle orbit could start) draws nothing
    pg.mouse.move(5, 5); pg.wait_for_timeout(1800); d0 = pg.evaluate("AgeLens._mapView.stats().draws"); pg.wait_for_timeout(1500)
    res["idle_draws_1500ms"] = pg.evaluate("AgeLens._mapView.stats().draws") - d0
    check(res["idle_draws_1500ms"] <= 2, f"map kept drawing while idle: {res['idle_draws_1500ms']}")

    # industries
    res["industries"] = {}
    for name in ("Procurement", "Healthcare & nursing"):
        pg.locator(".mp-chip", has_text=name).click(); pg.wait_for_timeout(1200)
        s = st(pg)
        res["industries"][name] = {"industry_value": s["industry"], "hi": s["spread"] and s["spread"]["hi"], "lo": s["spread"] and s["spread"]["lo"],
                                   "range": s["spread"] and round(s["spread"]["range"], 3), "n": s["spread"] and s["spread"]["n"],
                                   "caution": pg.locator(".mp-spread .mp-caution").count()}
        check(s["industry"] is not None, f"industry {name} not applied")
        check(pg.locator(".mp-chip[aria-pressed=true]").inner_text().startswith(name), f"chip {name} not pressed")
    shot(pg, "desktop_industry_healthcare.png", ".dt-panel")
    pg.locator(".mp-chip", has_text="All industries").click(); pg.wait_for_timeout(1000)
    check(st(pg)["industry"] is None, "All industries did not reset")

    # select via ranked list -> fly-to
    first = pg.locator(".mp-rankbtn").nth(0); target = first.get_attribute("data-prov")
    fl0 = pg.evaluate("AgeLens._mapView.stats().flies")
    first.click(); pg.wait_for_timeout(1300)
    check(st(pg)["selected"] == target, "ranked list click did not select")
    check(pg.evaluate("AgeLens._mapView.stats().flies") > fl0, "no fly-to after ranked list selection")
    res["detail_rows"] = pg.locator(".mp-occbtn").count()
    check(res["detail_rows"] >= 5, "detail panel has no industry breakdown")
    shot(pg, "desktop_selected.png", ".mp-main")
    # reset
    pg.locator(".mp-reset").click(); pg.wait_for_timeout(1100)
    check(st(pg)["selected"] is None, "Reset view did not clear the selection")

    # select via map click (3D pick)
    tgt = "四川"
    xy = pg.evaluate(f"AgeLens._mapView._debug().screenOf('{tgt}')")
    box = pg.locator(".mp-stage").bounding_box()
    pg.mouse.click(box["x"] + xy[0], box["y"] + xy[1]); pg.wait_for_timeout(1300)
    res["map_click_selected"] = st(pg)["selected"]
    check(res["map_click_selected"] is not None, "map click selected nothing")
    pg.locator(".mp-reset").click(); pg.wait_for_timeout(900)

    # hover sync: dot strip -> map hover
    dot = pg.locator(".mp-dot").nth(3); dn = dot.get_attribute("data-prov")
    dot.hover(); pg.wait_for_timeout(400)
    check(st(pg)["hover"] == dn and pg.evaluate("AgeLens._mapView._debug().state().hover") == dn, "dot hover did not sync to the map")
    shot(pg, "desktop_dot_hover.png", ".mp-left")
    pg.mouse.move(5, 5)

    # heatmap cell -> both selectors
    cell = pg.locator(".mp-hm tbody tr").nth(2).locator(".mp-hm-cell").nth(1)
    cp = cell.get_attribute("data-prov"); cell.click(); pg.wait_for_timeout(1300)
    s = st(pg); check(s["selected"] == cp and s["industry"] is not None, "heatmap cell did not set industry + region")
    res["heatmap_click"] = {"industry": s["industry"], "selected": s["selected"]}
    shot(pg, "desktop_heatmap.png", ".mp-heat")
    pg.locator(".mp-chip", has_text="All industries").click(); pg.wait_for_timeout(600)

    # keyboard: Tab into the map, arrows by rank, Enter selects, Esc resets
    pg.locator(".mp-stage").focus()
    ranked = st(pg)["ranked"]
    pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(300)
    check(st(pg)["hover"] == ranked[1], "arrow keys did not step by rank")
    pg.keyboard.press("Enter"); pg.wait_for_timeout(1200)
    check(st(pg)["selected"] == ranked[1], "Enter did not select")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(900)
    check(st(pg)["selected"] is None, "Escape did not reset")
    # Tab order reaches the stage from the control above it
    pg.locator(".mp-chip").last.focus(); found = False
    for _ in range(4):
        pg.keyboard.press("Tab")
        if pg.evaluate("document.activeElement && document.activeElement.classList.contains('mp-stage')"): found = True; break
    check(found, "Tab does not reach the map stage")

    # idle orbit: starts only after the idle delay, stops at once on interaction
    pg.mouse.move(5, 5); pg.wait_for_timeout(9500)
    o1 = pg.evaluate("AgeLens._mapView._debug().state()")
    res["idle_orbit_started"] = o1["orbiting"] or o1["orbitMs"] > 0
    pg.locator(".mp-stage").focus(); pg.keyboard.press("Shift+ArrowLeft"); pg.wait_for_timeout(120)
    res["orbit_after_input"] = pg.evaluate("AgeLens._mapView._debug().state().orbiting")
    check(not res["orbit_after_input"], "idle orbit did not stop on input")

    # collapse stops rendering; expand resumes
    pg.locator(".dt-collapse").click(); pg.wait_for_timeout(400)
    d0 = pg.evaluate("AgeLens._mapView.stats().draws"); pg.wait_for_timeout(1200)
    res["draws_while_collapsed"] = pg.evaluate("AgeLens._mapView.stats().draws") - d0
    check(res["draws_while_collapsed"] == 0, "map drew while collapsed")
    pg.locator(".dt-collapse").click(); pg.wait_for_timeout(600)

    # route change disposes
    pg.goto(BASE + "/#/about"); pg.wait_for_timeout(1200)
    res["canvases_after_leave"] = pg.evaluate("document.querySelectorAll('main canvas').length")
    check(res["canvases_after_leave"] == 0, "canvas left after route change")
    ctx.close()

    # ---------------- 2D fallback (WebGL disabled) ----------------
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_init_script(NO_WEBGL)
    ctx.add_init_script(OPEN_MORE); pg = ctx.new_page(); allerr += watch(pg, "2d")
    open_map(pg, 1500)
    s = st(pg); res["fallback_engine"] = s["engine"]
    check(s["engine"] == "2d", "2D fallback not used without WebGL")
    check("WebGL is not available" in pg.inner_text(".mp-note"), "no notice about the 2D fallback")
    for label in ("Explicit cap", "Median max age", "Any age wording"):
        pg.locator(".mp-metrics .mp-segbtn", has_text=label).click(); pg.wait_for_timeout(300)
    pg.locator(".mp-chip", has_text="Sales").click(); pg.wait_for_timeout(500)
    check(st(pg)["industry"] is not None and pg.locator(".mp-dot").count() > 3 and pg.locator(".mp-hm-cell").count() > 50, "2D: selectors/spread/heatmap missing")
    path = pg.locator(".mp-path[data-name='四川']"); bb = path.bounding_box()
    pg.mouse.click(bb["x"] + bb["width"] * 0.5, bb["y"] + bb["height"] * 0.5); pg.wait_for_timeout(900)
    res["fallback_map_click"] = st(pg)["selected"]
    check(res["fallback_map_click"] is not None, "2D map click selected nothing")
    pg.locator(".mp-stage").focus(); pg.keyboard.press("Escape"); pg.keyboard.press("ArrowRight"); pg.keyboard.press("Enter"); pg.wait_for_timeout(800)
    check(st(pg)["selected"] == st(pg)["ranked"][0], "2D keyboard selection failed")
    pg.locator(".mp-hm-cell:not(.nd)").nth(5).click(); pg.wait_for_timeout(800)
    check(st(pg)["selected"] is not None, "2D heatmap click failed")
    shot(pg, "fallback_2d.png", ".dt-panel")
    res["cjk_map_ui_2d"] = cjk_in_map(pg); check(res["cjk_map_ui_2d"] == 0, "CJK text in 2D map UI")
    ctx.close()

    # ---------------- mobile 360 ----------------
    ctx = b.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2, is_mobile=True, has_touch=True)
    ctx.add_init_script(OPEN_MORE); pg = ctx.new_page(); allerr += watch(pg, "mobile")
    open_map(pg, 4000)
    res["mobile_engine"] = st(pg)["engine"]
    res["mobile_overflow_px"] = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check(res["mobile_overflow_px"] <= 0, f"horizontal overflow at 360px: {res['mobile_overflow_px']}px")
    shot(pg, "mobile_controls.png")
    pg.evaluate("document.querySelector('.mp-stage').scrollIntoView({block:'center'})"); pg.wait_for_timeout(600); shot(pg, "mobile_map.png")
    pg.locator(".mp-rankbtn").nth(1).tap(); pg.wait_for_timeout(1300)
    check(st(pg)["selected"] is not None, "mobile: ranked list tap did not select")
    pg.evaluate("document.querySelector('.mp-detail').scrollIntoView()"); pg.wait_for_timeout(300); shot(pg, "mobile_detail.png")
    pg.evaluate("document.querySelector('.mp-heat').scrollIntoView()"); pg.wait_for_timeout(300); shot(pg, "mobile_heatmap.png")
    res["mobile_overflow_after"] = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check(res["mobile_overflow_after"] <= 0, "horizontal overflow at 360px after interaction")
    ctx.close()

    # ---------------- reduced motion ----------------
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
    ctx.add_init_script(OPEN_MORE); pg = ctx.new_page(); allerr += watch(pg, "reduced")
    open_map(pg, 1200)
    stt = pg.evaluate("AgeLens._mapView.stats()")
    res["reduced"] = {"intro": stt["intro"], "tweens": stt["tweensRun"], "frames": stt["frames"]}
    check(stt["intro"] == "done" and stt["tweensRun"] == 0, "reduced motion still animated the intro")
    pg.locator(".mp-metrics .mp-segbtn", has_text="Explicit cap").click(); pg.wait_for_timeout(300)
    pg.locator(".mp-rankbtn").first.click(); pg.wait_for_timeout(300)
    stt = pg.evaluate("AgeLens._mapView.stats()")
    check(stt["tweensRun"] == 0, "reduced motion: tweens ran on metric change / fly-to")
    pg.mouse.move(5, 5); pg.wait_for_timeout(9000)
    check(not pg.evaluate("AgeLens._mapView._debug().state().orbiting"), "reduced motion: idle orbit ran")
    shot(pg, "reduced_motion.png", ".mp-main")
    ctx.close()
    b.close()

res["console_errors"] = allerr
check(not allerr, f"console errors: {allerr[:3]}")
print(json.dumps(res, ensure_ascii=True, indent=1))
print(json.dumps({"fails": fails}))
sys.exit(1 if fails else 0)
