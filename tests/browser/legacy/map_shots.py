"""LEGACY (map v1: .dt-toggle, #mp-region no longer exist; superseded by tests/browser/map_v2.py). Map/data browser checks: screenshots (1280 + 360), console errors, overflow, keyboard, 2D fallback, render-count when collapsed.
Run: <pw python> tests/browser/map_shots.py [base_url]   (server must be running; default http://127.0.0.1:8802)"""
import sys, json, os
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8802'
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'screenshots', 'map')
ARGS = ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader']
res = {}
errs = []

def wire(page, tag):
    page.on('console', lambda m: errs.append((tag, m.type, m.text)) if m.type in ('error', 'warning') else None)
    page.on('pageerror', lambda e: errs.append((tag, 'pageerror', str(e))))

def shot(page, name, el=None):
    path = os.path.join(OUT, name + '.png')
    (el or page).screenshot(path=path)

def overflow(page):
    return page.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')

with sync_playwright() as p:
    b = p.chromium.launch(args=ARGS)
    for vw, vh, tag in ((1280, 900, 'd'), (360, 760, 'm')):
        ctx = b.new_context(viewport={'width': vw, 'height': vh}, device_scale_factor=1)
        page = ctx.new_page(); wire(page, tag)
        page.goto(BASE + '/#/', wait_until='networkidle')
        page.wait_for_selector('#data .dt-toggle')
        page.locator('#data').scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        shot(page, f'{tag}_1_collapsed', page.locator('#data'))
        res[f'{tag}_overflow_collapsed'] = overflow(page)
        # collapsed => no frames. Load, then collapse and count.
        page.click('#data .dt-toggle'); page.wait_for_selector('.mp-canvas', timeout=20000)
        page.wait_for_timeout(2500)
        page.locator('#data .dt-panel').scroll_into_view_if_needed(); page.wait_for_timeout(800)
        shot(page, f'{tag}_2_expanded_count', page.locator('#data .dt-panel'))
        res[f'{tag}_overflow_expanded'] = overflow(page)
        page.click('.mp-segbtn[data-v="share"]'); page.wait_for_timeout(1200)
        shot(page, f'{tag}_3_share', page.locator('#data .dt-panel'))
        # select via dropdown
        page.select_option('#mp-region', label=None, value='广东'); page.wait_for_timeout(800)
        shot(page, f'{tag}_4_selected', page.locator('#data .dt-panel'))
        if tag == 'd':
            # keyboard
            page.focus('.mp-stage')
            for k in ['ArrowLeft', 'ArrowLeft', 'ArrowDown', '+', ']', ']']:
                page.keyboard.press(k)
            page.wait_for_timeout(500)
            shot(page, 'd_5_keyboard', page.locator('.mp-stage'))
            page.keyboard.press('Enter'); page.wait_for_timeout(300)
            res['kbd_selected_text'] = page.inner_text('.mp-detail h3')
            page.keyboard.press('0')
            # hover
            box = page.locator('.mp-stage').bounding_box()
            page.mouse.move(box['x'] + box['width'] * 0.55, box['y'] + box['height'] * 0.55); page.wait_for_timeout(500)
            shot(page, 'd_6_hover', page.locator('.mp-stage'))
        # frame counting: expanded & visible vs collapsed
        res[f'{tag}_stats_expanded'] = page.evaluate('AgeLens._lastStats ? 0 : 0')
        ctx.close()
    # frame/dispose measurements (desktop). Software WebGL (SwiftShader): numbers are NOT representative of a real GPU.
    ctx = b.new_context(viewport={'width': 1280, 'height': 900}); page = ctx.new_page(); wire(page, 'x')
    page.goto(BASE + '/#/', wait_until='networkidle'); page.wait_for_selector('#data .dt-toggle')
    page.click('#data .dt-toggle'); page.wait_for_selector('.mp-canvas', timeout=20000); page.wait_for_timeout(2500)
    S = "AgeLens._mapView.stats()"
    st = page.evaluate(S); res['build_ms'] = st['buildMs']; res['frames_after_open'] = st['frames']; res['draws_after_open'] = st['draws']
    def frames(): return page.evaluate("(()=>{const s=AgeLens._mapView.stats();return [s.frames,s.draws]})()")
    f0 = frames(); page.wait_for_timeout(2500); f1 = frames()
    res['expanded_visible_idle_2.5s_frames_draws'] = [f1[0]-f0[0], f1[1]-f0[1]]
    page.click('#data .dt-toggle'); page.wait_for_timeout(400)
    f0 = frames(); page.wait_for_timeout(2500); f1 = frames()
    res['collapsed_2.5s_frames_draws'] = [f1[0]-f0[0], f1[1]-f0[1]]
    page.click('#data .dt-toggle'); page.wait_for_timeout(1200)
    page.evaluate('window.scrollTo(0,0)'); page.wait_for_timeout(600)
    f0 = frames(); page.mouse.move(100, 100); page.wait_for_timeout(2500); f1 = frames()
    res['expanded_offscreen_2.5s_frames_draws'] = [f1[0]-f0[0], f1[1]-f0[1]]
    page.locator('#data .dt-panel').scroll_into_view_if_needed(); page.wait_for_timeout(800)
    box = page.locator('.mp-stage').bounding_box()
    f0 = frames(); page.mouse.move(box['x'] + 300, box['y'] + 200); page.mouse.down()
    for i in range(20): page.mouse.move(box['x'] + 300 + i * 8, box['y'] + 200 + i * 2); page.wait_for_timeout(16)
    page.mouse.up(); page.wait_for_timeout(1500); f1 = frames()
    st = page.evaluate(S)
    res['drag_20_moves_frames_draws'] = [f1[0]-f0[0], f1[1]-f0[1]]
    res['avg_draw_ms_swiftshader'] = round(st['drawMsSum'] / max(1, st['draws']), 1)
    # wheel zoom requires focus
    page.locator('.mp-stage').scroll_into_view_if_needed(); box = page.locator('.mp-stage').bounding_box(); page.evaluate('window.scrollBy(0,-120)'); box = page.locator('.mp-stage').bounding_box(); page.mouse.click(box['x'] + 30, box['y'] + 240); d0 = page.evaluate("AgeLens._mapView._debug().camera.position.length()")
    page.mouse.move(box['x'] + 300, box['y'] + 200); page.mouse.wheel(0, -400); page.wait_for_timeout(800)
    res['wheel_zoom_changed_distance'] = [round(d0, 1), round(page.evaluate("AgeLens._mapView._debug().camera.position.length()"), 1)]
    # limits: zoom way in/out
    for i in range(30): page.keyboard.press('+')
    res['min_dist'] = round(page.evaluate("AgeLens._mapView._debug().camera.position.length()"), 1)
    for i in range(60): page.keyboard.press('-')
    res['max_dist'] = round(page.evaluate("AgeLens._mapView._debug().camera.position.length()"), 1)
    page.keyboard.press('0')
    # WebGL context loss => automatic 2D
    page.evaluate("(()=>{const c=document.querySelector('.mp-canvas');const g=c.getContext('webgl2')||c.getContext('webgl');g.getExtension('WEBGL_lose_context').loseContext();})()")
    page.wait_for_timeout(800)
    res['after_context_loss_svg'] = page.locator('.mp-svg').count(); res['after_context_loss_note'] = page.inner_text('.mp-note')
    # toggle back to 3D, then dispose via route change; read counters captured before dispose
    page.click('.mp-segbtn[data-v="3d"]'); page.wait_for_selector('.mp-canvas', timeout=20000); page.wait_for_timeout(1500)
    page.evaluate("window.__st=AgeLens._mapView.stats()")
    page.evaluate("location.hash='#/explore'"); page.wait_for_timeout(800)
    res['dispose_counters'] = page.evaluate("({created:window.__st.created,disposed:window.__st.disposed,flag:window.__st.disposedAll,before:window.__st.infoBefore,after:window.__st.infoAfter})")
    res['canvases_left'] = page.locator('canvas').count()
    ctx.close()
    # 2D fallback (WebGL disabled by script) + context loss test
    for vw, vh, tag in ((1280, 900, 'd'), (360, 760, 'm')):
        ctx = b.new_context(viewport={'width': vw, 'height': vh}); page = ctx.new_page(); wire(page, tag + '2d')
        page.add_init_script("""const g=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(t,...a){if(/webgl/.test(t))return null;return g.call(this,t,...a)};""")
        page.goto(BASE + '/#/', wait_until='networkidle'); page.wait_for_selector('#data .dt-toggle')
        page.click('#data .dt-toggle'); page.wait_for_selector('.mp-svg', timeout=20000); page.wait_for_timeout(800)
        page.locator('#data .dt-panel').scroll_into_view_if_needed(); page.wait_for_timeout(500)
        shot(page, f'{tag}_7_fallback2d', page.locator('#data .dt-panel'))
        page.click('.mp-path[data-name="广东"]', force=True); page.wait_for_timeout(300)
        res[f'{tag}_2d_click_selected'] = page.inner_text('.mp-detail h3')
        page.click('.mp-segbtn[data-v="share"]'); page.wait_for_timeout(300)
        shot(page, f'{tag}_8_fallback2d_share', page.locator('#data .dt-panel'))
        res[f'{tag}_2d_overflow'] = overflow(page)
        res[f'{tag}_note'] = page.inner_text('.mp-note')
        ctx.close()
    print(json.dumps(res, ensure_ascii=False, indent=1))
    print('CONSOLE:', errs)
    b.close()
