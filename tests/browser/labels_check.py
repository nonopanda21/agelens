"""English-label check: counts CJK characters anywhere on the main routes. The UI is English-only (docs/ENGLISH_UI.md), so
there is NO evidence exception any more: quoted ad text, titles, highlights and original values must all be English.
Usage: <pw python> tests/browser/labels_check.py [BASE] [TAG]
  BASE defaults to http://127.0.0.1:8812 (a server started with AGELENS_REVIEWER_TOKEN set, see below).
  TAG  names the screenshot set (docs/screenshots/labels/<TAG>_*.png), default 'after'.
Reviewer token: env AGELENS_REVIEWER_TOKEN (must match the server's).
Counted: visible text nodes, <option> text, SVG <title> tooltips, and title/aria-label/placeholder/alt attributes.
Input and textarea values (what a user types or pastes) are not page text and are not counted.
Exit code 1 if any route has any CJK."""
import json, os, sys, urllib.request
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8812'
TAG = sys.argv[2] if len(sys.argv) > 2 else 'after'
OUT = os.path.join(ROOT, 'docs', 'screenshots', 'labels'); os.makedirs(OUT, exist_ok=True)
RVTOK = os.environ.get('AGELENS_REVIEWER_TOKEN', '')
EVIDENCE = ''  # no exception: was '.orig, .ex-snip, .ex-ad-t, .ev-title, .rq-ev-title, .st-adtext, mark.age, .zh-orig, [lang^="zh"]'

COUNT_JS = r"""(ev) => {
  const CJK = /[\u2e80-\u2fdf\u3000-\u303f\u3040-\u30ff\u3100-\u312f\u3190-\u31ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufe30-\ufe4f\uff00-\uffef]/g;
  const out = { text: 0, attr: 0, samples: [] };
  const inEv = (el) => !!(ev && el && el.closest && el.closest(ev));
  const visible = (el) => { if (!el) return false; if (el.closest('option, title')) return true; return el.checkVisibility ? el.checkVisibility({ checkVisibilityCSS: true }) : !!el.getClientRects().length; };
  const add = (kind, el, s) => { const n = (s.match(CJK) || []).length; if (!n) return; out[kind] += n; if (out.samples.length < 12) out.samples.push(kind + ' <' + el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ').join('.') : '') + '> ' + s.trim().slice(0, 60)); };
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; while ((n = w.nextNode())) { const el = n.parentElement; if (!el || el.closest('script, style') || inEv(el) || !visible(el)) continue; add('text', el, n.nodeValue); }
  document.querySelectorAll('[title], [aria-label], [placeholder], [alt]').forEach((el) => { if (inEv(el)) return; ['title', 'aria-label', 'placeholder', 'alt'].forEach((a) => { const v = el.getAttribute(a); if (v) add('attr', el, v); }); });
  return out;
}"""


def api(path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=dict({'Content-Type': 'application/json'}, **(headers or {})))
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


report, errors = {}, []


def measure(page, key):
    page.wait_for_timeout(500)
    r = page.evaluate(COUNT_JS, EVIDENCE)
    prev = report.get(key)
    if prev:  # keep the worst state seen for this route
        r = {'text': max(prev['text'], r['text']), 'attr': max(prev['attr'], r['attr']), 'samples': prev['samples'] + [s for s in r['samples'] if s not in prev['samples']][:12]}
    report[key] = r


def shot(page, name, full=True):
    page.screenshot(path=os.path.join(OUT, f'{TAG}_{name}.png'), full_page=full)


# a request with two evidence ads, so #/requests and #/reviewer have real content
ads = api('/api/ads?page_size=2')['items']
ev = [api('/api/ads/' + a['id']) for a in ads]
made = api('/api/requests', {'question': 'The ad says under 35 with exceptions. I am 38 in procurement. What should I clarify?',
                             'profile': {'age': 38, 'occupation': 'Procurement', 'years_experience': 8}, 'consent': {'fields': ['age', 'occupation', 'years_experience']},
                             'evidence': ev, 'scope': {'matched_total': 2}}, {'X-Idempotency-Key': 'labels-check-' + TAG + '-' + ads[0]['id']})
code, tok = made['code'], made.get('token')

with sync_playwright() as pw:
    br = pw.chromium.launch(args=['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'])
    ctx = br.new_context(viewport={'width': 1280, 'height': 900})
    if tok:
        ctx.add_init_script("try{ localStorage.setItem('al_owner_tokens', %s) }catch(e){}" % json.dumps(json.dumps({code: tok})))
    ctx.add_init_script("try{ sessionStorage.setItem('al_reviewer_token', %s) }catch(e){}" % json.dumps(RVTOK))
    page = ctx.new_page()
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append(str(e)))

    # ---- home + regional map (3D, then 2D + table)
    page.goto(BASE + '/#/', wait_until='networkidle')
    btn = page.get_by_role('button', name='Explore the regional map')  # map is open by default now
    if btn.count(): btn.click()
    page.wait_for_selector('.mp-stage canvas, .mp-stage svg', timeout=20000); page.wait_for_timeout(2500)
    st = page.locator('.mp-stage'); bb = st.bounding_box()
    page.mouse.move(bb['x'] + bb['width'] * 0.62, bb['y'] + bb['height'] * 0.55); page.wait_for_timeout(600)
    page.locator('.mp-rankbtn').nth(4).click(); page.wait_for_timeout(600)
    page.locator('.mp').scroll_into_view_if_needed(); shot(page, 'home_map3d', full=False)
    report['engine_first'] = page.evaluate('AgeLens._mapView && AgeLens._mapView.engineName()')
    measure(page, '#/ (map 3D)')
    page.click('.mp-segbtn[data-v="2d"]'); page.wait_for_selector('.mp-stage svg'); page.wait_for_timeout(800)
    page.mouse.move(bb['x'] + bb['width'] * 0.62, bb['y'] + bb['height'] * 0.55); page.wait_for_timeout(400)
    page.click('.mp-tbl summary'); page.wait_for_timeout(300)
    shot(page, 'home_map2d')
    measure(page, '#/ (map 2D + table)')
    page.evaluate("try{localStorage.removeItem('al_map_view')}catch(e){}")

    # ---- explore: province + occupation filters, then a chart bar
    page.goto(BASE + '/#/explore', wait_until='networkidle'); page.wait_for_selector('.ex-ads li'); page.wait_for_timeout(800)
    measure(page, '#/explore')
    page.select_option('#ex-prov', value='广东'); page.wait_for_timeout(1200)
    occ = page.locator('#ex-occ')
    if occ.evaluate('e => e.tagName') == 'SELECT':
        page.select_option('#ex-occ', value='销售')
    else:
        occ.fill('销售')
    page.wait_for_timeout(1500); page.wait_for_selector('.ex-ads li, .ex-list .card')
    report['explore_url_after_filters'] = page.evaluate('location.hash')
    measure(page, '#/explore')
    shot(page, 'explore_filtered')
    page.click('.ex-chip >> nth=0'); page.click('.ex-chip >> nth=0'); page.wait_for_timeout(1200)
    page.locator('.ex-chart.ex-scroll .ch-bar').nth(1).click(); page.wait_for_timeout(1500)
    report['explore_url_after_bar'] = page.evaluate('location.hash')
    measure(page, '#/explore')
    shot(page, 'explore_bar')

    # ---- evidence page
    page.goto(BASE + '/#/evidence/' + ads[0]['id'], wait_until='networkidle'); page.wait_for_selector('.ev-sec'); page.wait_for_timeout(400)
    measure(page, '#/evidence/<id>'); shot(page, 'evidence')

    # ---- requests (seeker) list + detail
    page.goto(BASE + '/#/requests', wait_until='networkidle'); page.wait_for_timeout(1000)
    measure(page, '#/requests'); shot(page, 'requests')
    page.goto(BASE + '/#/requests/' + code, wait_until='networkidle'); page.wait_for_timeout(1200)
    measure(page, '#/requests'); shot(page, 'requests_detail')

    # ---- reviewer queue + detail
    page.goto(BASE + '/#/reviewer', wait_until='networkidle'); page.wait_for_timeout(1200)
    measure(page, '#/reviewer')
    page.goto(BASE + '/#/reviewer/' + code, wait_until='networkidle'); page.wait_for_timeout(1500)
    measure(page, '#/reviewer'); shot(page, 'reviewer_detail')
    br.close()

routes = {k: v for k, v in report.items() if isinstance(v, dict)}
print(json.dumps(report, ensure_ascii=False, indent=1))
print('CONSOLE ERRORS', errors)
print('SUMMARY', {k: v['text'] + v['attr'] for k, v in routes.items()})
sys.exit(1 if any(v['text'] + v['attr'] for v in routes.values()) else 0)
