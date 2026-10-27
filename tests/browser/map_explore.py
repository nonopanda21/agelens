"""Explore page screenshots + checks (1280/360): overflow, console errors, list links to #/evidence/<id>, filter by province link."""
import sys, os, json
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8802'
OUT = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'screenshots', 'map')
errs = []; res = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    for vw, vh, tag in ((1280, 900, 'd'), (360, 760, 'm')):
        page = b.new_page(viewport={'width': vw, 'height': vh})
        page.on('console', lambda m: errs.append((tag, m.text)) if m.type == 'error' else None)
        page.on('pageerror', lambda e: errs.append((tag, str(e))))
        page.goto(BASE + '/#/explore?province=' + '广东', wait_until='networkidle'); page.wait_for_selector('.ex-ads li'); page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(OUT, f'{tag}_explore.png'), full_page=True)
        res[tag + '_overflow'] = page.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')
        res[tag + '_first_link'] = page.get_attribute('.ex-ads li a.ex-ad-t', 'href')
        res[tag + '_rows'] = page.locator('.ex-ads li').count()
        page.close()
    print(json.dumps(res, ensure_ascii=False)); print('ERR', errs)
