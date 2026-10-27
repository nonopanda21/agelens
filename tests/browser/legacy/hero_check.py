"""Real-browser checks for the home hero (run with the Playwright python). Usage: hero_check.py PORT
Software WebGL (SwiftShader): timings are NOT representative of a real GPU."""
import sys, json, os
from playwright.sync_api import sync_playwright
PORT = sys.argv[1] if len(sys.argv) > 1 else '8801'
URL = f'http://127.0.0.1:{PORT}/'
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'screenshots', 'hero')
ARGS = ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader']
res = {}
def new(p, w, h, **kw):
    b = p.chromium.launch(args=ARGS)
    c = b.new_context(viewport={'width': w, 'height': h}, **kw)
    pg = c.new_page(); errs = []
    pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: errs.append(str(e)))
    return b, c, pg, errs
def shot(pg, name): pg.screenshot(path=f'{OUT}/{name}.png')
def stage(pg, i): pg.click(f'#lt-{["question","wording","clarify"][i]}'); pg.wait_for_timeout(1800)
with sync_playwright() as p:
    for w, h, tag in ((1280, 800, 'd1280'), (360, 740, 'm360')):
        b, c, pg, errs = new(p, w, h)
        pg.goto(URL); pg.wait_for_selector('.hero-scene[data-state]'); pg.wait_for_timeout(500)
        pg.wait_for_function("document.querySelector('.hero-scene').dataset.state!=='loading'", timeout=15000)
        res[tag + '_state'] = pg.eval_on_selector('.hero-scene', 'e=>e.dataset.state')
        pg.wait_for_timeout(300); shot(pg, f'{tag}_intro_early'); pg.wait_for_timeout(3500)
        for i, n in enumerate(('1_question', '2_wording', '3_clarify')):
            stage(pg, i); shot(pg, f'{tag}_stage{n}')
        res[tag + '_overflow'] = pg.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth')
        if tag == 'd1280':
            # keyboard
            pg.focus('#lt-question'); pg.keyboard.press('ArrowRight'); a = pg.eval_on_selector('#lt-wording', 'e=>e.getAttribute("aria-selected")')
            pg.keyboard.press('End'); b3 = pg.eval_on_selector('#lt-clarify', 'e=>e.getAttribute("aria-selected")')
            pg.keyboard.press('Home'); b1 = pg.eval_on_selector('#lt-question', 'e=>e.getAttribute("aria-selected")')
            res['keyboard'] = [a, b3, b1, pg.evaluate('document.activeElement.id'), pg.inner_text('.lp-live')]
            # mouse
            pg.mouse.move(600, 300); pg.mouse.move(700, 350, steps=8); pg.wait_for_timeout(400); shot(pg, 'd1280_mouse')
            # gfx start/stop on scroll
            def st(): return pg.evaluate('({run:AgeLens.gfx.running("hero"),log:AgeLens.gfx.stats.log.slice(-4),lens:window.__lens&&window.__lens.stats()})')
            pg.wait_for_timeout(500); res['gfx_visible'] = st()
            pg.evaluate('document.getElementById("steps").scrollIntoView()'); pg.wait_for_timeout(800); res['gfx_scrolled_away'] = st(); shot(pg, 'd1280_scrolled_steps')
            pg.evaluate('window.scrollTo(0,0)'); pg.wait_for_timeout(800); res['gfx_back'] = st()
            pg.evaluate('window.scrollTo(0,160)'); pg.wait_for_timeout(500); shot(pg, 'd1280_scroll_recede'); pg.evaluate('window.scrollTo(0,0)'); pg.wait_for_timeout(500)
            # cost: count frames and cpu over 3 s while running
            s0 = pg.evaluate('window.__lens.stats()'); pg.mouse.move(650, 300); pg.wait_for_timeout(3000); pg.mouse.move(700, 380, steps=20); s1 = pg.evaluate('window.__lens.stats()')
            res['cost_3s'] = {'frames': s1['frames'] - s0['frames'], 'cpu_ms': round(s1['cpuMs'] - s0['cpuMs'], 1), 'per_frame_ms': s1['perFrameMs'], 'particles': s1['particles']}
            # pause button
            pg.click('.lens-pause'); pg.wait_for_timeout(600); res['paused_running'] = pg.evaluate('AgeLens.gfx.running("hero")'); res['paused_label'] = pg.inner_text('.lens-pause')
            stage(pg, 1); shot(pg, 'd1280_paused_stage2')
            pg.click('.lens-pause'); pg.wait_for_timeout(600); res['resumed_running'] = pg.evaluate('AgeLens.gfx.running("hero")')
            # home page below hero
            pg.evaluate('window.scrollTo(0,0)'); pg.screenshot(path=f'{OUT}/d1280_home_full.png', full_page=True)
            res['links'] = pg.evaluate('[...document.querySelectorAll(".hero-actions a")].map(a=>a.getAttribute("href"))')
            pg.click('text=See how it works'); pg.wait_for_timeout(1200); res['scrolled_to_steps'] = pg.evaluate('Math.round(document.getElementById("steps").getBoundingClientRect().top)')
            pg.goto(URL + '#/explore'); pg.wait_for_timeout(800); res['leave_running'] = pg.evaluate('AgeLens.gfx.running("hero")')
        else:
            pg.evaluate('window.scrollTo(0,0)'); pg.screenshot(path=f'{OUT}/m360_home_full.png', full_page=True)
            res['m360_particles'] = pg.evaluate('window.__lens&&window.__lens.stats().particles')
        res[tag + '_errors'] = errs; b.close()
    # reduced motion
    b, c, pg, errs = new(p, 1280, 800, reduced_motion='reduce')
    pg.goto(URL); pg.wait_for_function("document.querySelector('.hero-scene').dataset.state!=='loading'", timeout=15000); pg.wait_for_timeout(800)
    res['reduced_running'] = pg.evaluate('AgeLens.gfx.running("hero")'); shot(pg, 'd1280_reduced_stage1'); stage(pg, 1); shot(pg, 'd1280_reduced_stage2'); stage(pg, 2); shot(pg, 'd1280_reduced_stage3')
    res['reduced_frames'] = pg.evaluate('window.__lens.stats().frames'); res['reduced_errors'] = errs; b.close()
    # forced fallback: block three
    for w, h, tag in ((1280, 800, 'd1280'), (360, 740, 'm360')):
        b, c, pg, errs = new(p, w, h)
        pg.route('**/vendor/three/**', lambda r: r.abort())
        pg.goto(URL); pg.wait_for_function("document.querySelector('.hero-scene').dataset.state!=='loading'", timeout=15000); pg.wait_for_timeout(600)
        res[tag + '_fallback_state'] = pg.eval_on_selector('.hero-scene', 'e=>e.dataset.state'); shot(pg, f'{tag}_fallback_stage1'); stage(pg, 2); shot(pg, f'{tag}_fallback_stage3')
        res[tag + '_fallback_overflow'] = pg.evaluate('document.documentElement.scrollWidth-document.documentElement.clientWidth')
        res[tag + '_fallback_errors'] = [e for e in errs if 'Failed to load resource' not in e]; b.close()
print(json.dumps(res, indent=1, ensure_ascii=False))
