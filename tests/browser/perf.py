"""Performance / render-loop checks for the home page graphics (hero nebula, regional map, footer nebula).
Runs against a running server (default http://127.0.0.1:8765). Software WebGL (SwiftShader) in headless Chromium:
numbers describe THIS environment only, not a real GPU. Prints JSON lines; exit code 1 if a hard check fails."""
import json, sys, time
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
INIT = """
(()=>{ window.__raf = 0; const r = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => r((t) => { window.__raf++; cb(t); });
  window.__ctx = { made: 0, lost: 0 }; const g = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (k, o) { const c = g.call(this, k, o); if (c && /webgl/.test(k) && !this.__counted) { this.__counted = 1; window.__ctx.made++;
    const ext = c.getExtension && c.getExtension('WEBGL_lose_context'); if (ext && !ext.__w) { const lc = ext.loseContext.bind(ext); ext.loseContext = () => { window.__ctx.lost++; lc(); }; ext.__w = 1; } } return c; };
})();"""
fails = []
def out(k, v): print(json.dumps({k: v}))
def rate(pg, ms=2500):
    a = pg.evaluate("window.__raf"); pg.wait_for_timeout(ms); return round((pg.evaluate("window.__raf") - a) / (ms / 1000), 1)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1440, "height": 900}); pg.add_init_script(INIT)
    pg.goto(BASE + "/#/"); pg.wait_for_timeout(4500)
    out("hero_nebula", {"raf_per_s": rate(pg), **pg.evaluate("window.__nebula.stats()")})
    pg.evaluate("document.getElementById('footer').scrollIntoView({block:'end'})"); pg.wait_for_timeout(2500)
    out("footer_visible", {"raf_per_s": rate(pg), "hero_nebula_running": pg.evaluate("window.__nebula.stats().running"), "gfx_log": pg.evaluate("AgeLens.gfx.stats.log.slice(-3)")})
    if pg.evaluate("window.__nebula.stats().running"): fails.append("hero nebula kept running while the footer nebula was on screen")
    # quiet region (no graphics on screen): expect ~0 animation frames
    pg.evaluate("document.getElementById('fields').scrollIntoView()"); pg.wait_for_timeout(1500)
    q = rate(pg); out("no_graphics_on_screen", {"raf_per_s": q}); 
    if q > 5: fails.append(f"animation frames while no graphics visible: {q}/s")
    # regional map: collapsed -> no frames; expanded + idle -> render on demand
    btn = pg.get_by_role("button", name="Explore the regional map")
    btn.scroll_into_view_if_needed(); pg.wait_for_timeout(800)
    out("map_collapsed", {"raf_per_s": rate(pg, 1500)})
    btn.click(); pg.wait_for_timeout(4000)
    out("map_expanded_idle", {"raf_per_s": rate(pg), "webgl_contexts": pg.evaluate("window.__ctx")})
    box = pg.locator(".dt-mapholder canvas").first.bounding_box() if pg.locator(".dt-mapholder canvas").count() else None
    if box:
        a = pg.evaluate("window.__raf"); t0 = time.time()
        pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2); pg.mouse.down()
        for i in range(20): pg.mouse.move(box["x"] + box["width"] / 2 + i * 8, box["y"] + box["height"] / 2 + i * 2); pg.wait_for_timeout(40)
        pg.mouse.up(); pg.wait_for_timeout(1500)
        out("map_drag_20_moves", {"raf_frames": pg.evaluate("window.__raf") - a, "seconds": round(time.time() - t0, 1)})
    # tab hidden -> everything stops
    pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(1500)
    pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>true}); document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(800)
    h = rate(pg, 1500); out("tab_hidden", {"raf_per_s": h, "nebula_running": pg.evaluate("window.__nebula.stats().running")})
    if pg.evaluate("window.__nebula.stats().running"): fails.append("nebula kept running with the tab hidden")
    pg.evaluate("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false}); document.dispatchEvent(new Event('visibilitychange'))"); pg.wait_for_timeout(800)
    # pause motion -> stops; resume -> runs
    pg.evaluate("document.querySelector('.motion-toggle').click()"); pg.wait_for_timeout(800); paused = pg.evaluate("window.__nebula.stats().running")
    pg.evaluate("document.querySelector('.motion-toggle').click()"); pg.wait_for_timeout(800); resumed = pg.evaluate("window.__nebula.stats().running")
    out("pause_motion", {"running_when_paused": paused, "running_after_play": resumed})
    if paused or not resumed: fails.append("pause/play motion did not stop/restart the nebula")
    # leaving the page releases WebGL contexts
    before = pg.evaluate("window.__ctx"); pg.goto(BASE + "/#/explore"); pg.wait_for_timeout(1500)
    after = pg.evaluate("window.__ctx"); out("route_change", {"before": before, "after": after, "canvases_left": pg.evaluate("document.querySelectorAll('canvas').length")})
    if after["lost"] < after["made"] and pg.evaluate("document.querySelectorAll('main canvas').length") == 0 and after["made"] - after["lost"] > 0:
        fails.append(f"WebGL contexts not released on route change: made {after['made']} lost {after['lost']}")
    b.close()
out("result", {"fails": fails, "note": "software WebGL in headless Chromium; not representative of a real GPU"})
sys.exit(1 if fails else 0)
