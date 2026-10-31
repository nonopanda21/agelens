"""Old Explore links (1280/360): #/explore and #/explore?province=… were removed and must land on the Overview's data map, with no console errors and no overflow."""
import sys, json
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8802'
errs = []; res = {}; fails = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for vw, vh, tag in ((1280, 900, 'd'), (360, 760, 'm')):
        for link in ('/#/explore', '/#/explore?province=' + '广东'):
            page = b.new_page(viewport={'width': vw, 'height': vh})
            page.add_init_script("sessionStorage.setItem('al_splash_seen','1')")
            page.on('console', lambda m: errs.append((tag, m.text)) if m.type == 'error' else None)
            page.on('pageerror', lambda e: errs.append((tag, str(e))))
            page.goto(BASE + link, wait_until='networkidle'); page.wait_for_selector('#data .dt', timeout=20000); page.wait_for_timeout(1200)
            key = f'{tag} {link}'
            res[key] = {'hash': page.evaluate('location.hash'),
                        'data_top': round(page.evaluate("document.getElementById('data').getBoundingClientRect().top")),
                        'nav_explore': page.locator('[data-nav="explore"]').count(),
                        'overflow': page.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')}
            r = res[key]
            if r['hash'] not in ('#/', ''): fails.append(key + ': not redirected to the Overview')
            if abs(r['data_top']) > vh: fails.append(key + ': data map not scrolled into view')
            if r['nav_explore']: fails.append(key + ': Explore still in the menu')
            if r['overflow'] > 0: fails.append(key + ': horizontal overflow')
            page.close()
    b.close()
print(json.dumps(res, ensure_ascii=False)); print('ERR', errs); print('FAILS', fails)
sys.exit(1 if fails or errs else 0)
