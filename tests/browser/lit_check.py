"""Browser check for literature section + About page. Usage: pw/python lit_check.py [port]"""
import sys, os
from playwright.sync_api import sync_playwright
port = sys.argv[1] if len(sys.argv) > 1 else '8803'
out = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'screenshots', 'lit')
os.makedirs(out, exist_ok=True)
fails = []
with sync_playwright() as p:
    b = p.chromium.launch(args=['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'])
    for name, w, h in [('desktop', 1280, 900), ('mobile', 360, 760)]:
        pg = b.new_page(viewport={'width': w, 'height': h})
        errs = []
        pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
        pg.on('pageerror', lambda e: errs.append(str(e)))
        for route, sel, tag in [('#/why', '#literature', 'literature'), ('#/about', '.ab', 'about')]:
            pg.goto(f'http://127.0.0.1:{port}/{route}'); pg.wait_for_selector(sel + ' h2, ' + sel + ' h1', timeout=8000)
            pg.wait_for_timeout(800)
            pg.locator(sel).scroll_into_view_if_needed()
            if tag == 'literature':
                pg.wait_for_selector('#literature svg.lit-svg', timeout=5000)
                pg.locator('#literature').screenshot(path=f'{out}/{tag}_{name}.png')
                pg.evaluate("document.querySelectorAll('#literature details').forEach(d=>d.open=true)")
                pg.locator('#literature').screenshot(path=f'{out}/{tag}_{name}_open.png')
            else:
                pg.screenshot(path=f'{out}/{tag}_{name}.png', full_page=True)
            ov = pg.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')
            print(name, tag, 'overflow px:', ov)
            if ov > 0: fails.append(f'{name} {tag} overflow {ov}')
        print(name, 'console errors:', errs)
        fails += [f'{name} console: {e}' for e in errs]
    b.close()
print('FAIL' if fails else 'OK', fails)
sys.exit(1 if fails else 0)
