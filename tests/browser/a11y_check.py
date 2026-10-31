"""Scripted accessibility checks (used for docs/UI_AUDIT.md, task T04). Not a replacement for axe or a screen reader.
usage: ~/agelens-tools/pw/bin/python tests/browser/a11y_check.py [--json]
Starts its OWN server (temp DB copy, free port 8822-8829) and stops only that server. Per route at 1280 and 360 px:
  - interactive elements (a[href], button, input, select, textarea, [role=button|tab|checkbox], [tabindex>=0]) without an accessible name
  - <img> without alt; <svg>/<canvas> that are neither aria-hidden nor named
  - focusable elements inside aria-hidden; tabindex > 0; duplicate ids; aria-labelledby/-describedby pointing at missing ids
  - text contrast below 4.5:1 (3:1 for >= 24px or >= 18.66px bold) against the first opaque ancestor background
    (elements over gradients/images/transparent-to-canvas are reported as 'unknown', not as failures)
  - keyboard: Tab through the first 150 stops (trap = the same element keeps focus for 3 Tab presses; 6 for date inputs with sub-fields); each focused element must show a visible change (outline or box-shadow)
Exit 1 if any high-severity issue (missing name, aria-hidden focusable, contrast < 4.5 on normal text, invisible focus)."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
RVTOK = "a11y-token-" + str(os.getpid())

AUDIT_JS = r"""() => {
  const out = { noname: [], img: [], media: [], hiddenFocusable: [], tabpos: [], dupIds: [], badRefs: [], contrast: [], unknownBg: 0 };
  const desc = (el) => { let s = el.tagName.toLowerCase(); if (el.id) s += '#' + el.id; if (typeof el.className === 'string' && el.className.trim()) s += '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.'); const t = (el.innerText || el.value || '').trim().slice(0, 40); return s + (t ? ' "' + t + '"' : ''); };
  const vis = (el) => el.checkVisibility ? el.checkVisibility({ checkVisibilityCSS: true }) : !!el.getClientRects().length;
  const name = (el) => {
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
    const lb = el.getAttribute('aria-labelledby'); if (lb) return lb.split(/\s+/).map((i) => (document.getElementById(i) || {}).textContent || '').join(' ').trim();
    if (el.labels && el.labels.length) return [...el.labels].map((l) => l.textContent).join(' ').trim();
    if (el.tagName === 'INPUT' && ['submit', 'button', 'reset'].includes(el.type)) return el.value;
    if (el.tagName === 'IMG') return el.alt || '';
    const t = (el.textContent || '').trim(); if (t) return t;
    const img = el.querySelector('img[alt]'); if (img && img.alt) return img.alt;
    return (el.getAttribute('title') || el.getAttribute('placeholder') || '').trim();
  };
  const SEL = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=tab], [role=checkbox], [role=link], [tabindex]:not([tabindex="-1"])';
  document.querySelectorAll(SEL).forEach((el) => {
    if (!vis(el) && !(el.tagName === 'INPUT' && el.type === 'file')) return;
    if (el.closest('[aria-hidden="true"]') && el.tabIndex >= 0 && !el.disabled) out.hiddenFocusable.push(desc(el));
    if (el.closest('[aria-hidden="true"]')) return;
    if (!name(el)) out.noname.push(desc(el));
    if (el.tabIndex > 0) out.tabpos.push(desc(el));
  });
  document.querySelectorAll('img').forEach((el) => { if (!el.hasAttribute('alt')) out.img.push(desc(el)); });
  document.querySelectorAll('svg, canvas').forEach((el) => { if (!vis(el) || el.closest('[aria-hidden="true"]') || el.closest('svg') !== el && el.tagName === 'svg' && el.parentElement.closest('svg')) return; if (!name(el) && !el.querySelector('title') && el.getAttribute('role') !== 'presentation') out.media.push(desc(el)); });
  const ids = {}; document.querySelectorAll('[id]').forEach((el) => { ids[el.id] = (ids[el.id] || 0) + 1; }); out.dupIds = Object.keys(ids).filter((k) => ids[k] > 1);
  document.querySelectorAll('[aria-labelledby],[aria-describedby],[aria-controls]').forEach((el) => { for (const a of ['aria-labelledby', 'aria-describedby', 'aria-controls']) { const v = el.getAttribute(a); if (v) v.split(/\s+/).forEach((i) => { if (!document.getElementById(i)) out.badRefs.push(desc(el) + ' ' + a + '=' + i); }); } });
  // contrast
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const blend = (top, bot) => { const a = top[3]; return [top[0] * a + bot[0] * (1 - a), top[1] * a + bot[1] * (1 - a), top[2] * a + bot[2] * (1 - a), 1]; };
  const firstLayer = (bi) => { let d = 0; for (let i = 0; i < bi.length; i++) { const c = bi[i]; if (c === '(') d++; else if (c === ')') d--; else if (c === ',' && d === 0) return bi.slice(0, i); } return bi; };
  const key = (c) => c.map((v) => Math.round(v)).join(',');
  /** candidate opaque background colours behind el (several for gradients); null = unknown (image) */
  const bgCands = (el) => {
    if (!el) return [[255, 255, 255, 1]];
    const cs = getComputedStyle(el);
    if (/url\(/.test(cs.backgroundImage)) return null;
    let own = [];
    const c = parse(cs.backgroundColor); if (c && c[3] > 0) own = [c];
    if (cs.backgroundImage && cs.backgroundImage !== 'none') {
      const stops = (firstLayer(cs.backgroundImage).match(/rgba?\([^)]+\)/g) || []).map(parse);
      if (stops.length) { const base = own.length && own[0][3] >= 0.99 ? own : null; const under = base || bgCands(el.parentElement); if (!under) return null;
        const below = own.length && !base ? under.map((u) => blend(own[0], u)) : under; const out = {}; stops.forEach((st) => below.forEach((u) => { const b = blend(st, u); out[key(b)] = b; })); return Object.values(out); }
    }
    if (own.length && own[0][3] >= 0.99) return own;
    const under = bgCands(el.parentElement); if (!under) return null;
    return own.length ? under.map((u) => blend(own[0], u)) : under;
  };
  const seen = new Set();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) {
    const el = n.parentElement; if (!el || !n.nodeValue.trim() || seen.has(el) || el.closest('script,style,svg,option,[aria-hidden="true"]') || !vis(el)) continue; seen.add(el);
    const cs = getComputedStyle(el); if (parseFloat(cs.opacity) === 0) continue;
    let fg = parse(cs.color); if (!fg) continue;
    const disabled = el.closest('button:disabled, input:disabled, [aria-disabled="true"]'); if (disabled) continue;
    if (fg[3] === 0) { out.unknownBg++; continue; }   // gradient text (background-clip:text)
    const cands = bgCands(el); if (!cands) { out.unknownBg++; continue; }
    let worst = 99; for (const b of cands) { const f = fg[3] < 1 ? blend(fg, b) : fg; const L1 = lum(f), L2 = lum(b); const r = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05); worst = Math.min(worst, r); }
    // effective opacity of ancestors
    let op = 1; for (let e = el; e; e = e.parentElement) op *= parseFloat(getComputedStyle(e).opacity);
    if (op < 1) worst = 1 + (worst - 1) * op;
    const size = parseFloat(cs.fontSize), bold = parseInt(cs.fontWeight) >= 700;
    const need = size >= 24 || (size >= 18.66 && bold) ? 3 : 4.5;
    if (worst < need) out.contrast.push(desc(el) + ' ratio ' + worst.toFixed(2) + ' need ' + need + ' fg ' + cs.color + ' size ' + size);
  }
  return out;
}"""

FOCUS_JS = r"""() => { const el = document.activeElement; if (!el || el === document.body) return null;
  const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
  const d = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '') + ' "' + (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 30) + '"';
  const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 1) || (cs.boxShadow && cs.boxShadow !== 'none');
  if (!el.dataset.a11yN) el.dataset.a11yN = String((window.__a11yN = (window.__a11yN || 0) + 1));
  const sub = el.tagName === 'INPUT' && /^(date|time|datetime-local|month|week)$/.test(el.type);   // several internal sub-fields per input
  return { d, uid: el.dataset.a11yN, sub, ring, visible: r.width > 0 && r.height > 0, outline: cs.outlineStyle + ' ' + cs.outlineWidth + ' ' + cs.outlineColor, shadow: cs.boxShadow.slice(0, 60), top: r.top, h: innerHeight }; }"""


def free_port():
    for p in range(8822, 8830):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise SystemExit("no free port")


PORT = free_port(); BASE = f"http://127.0.0.1:{PORT}"


def api(path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=dict({"Content-Type": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


tmp = tempfile.mkdtemp(prefix="agelens_a11y_")
shutil.copy(ROOT / "data" / "agelens.db", os.path.join(tmp, "a.db"))
srv = subprocess.Popen([str(ROOT / ".venv/bin/python"), "app.py", "--port", str(PORT)], cwd=ROOT,
                       env=dict(os.environ, AGELENS_DB=os.path.join(tmp, "a.db"), AGELENS_REVIEWER_TOKEN=RVTOK), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
report, high = {}, 0
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=1); break
        except Exception:
            time.sleep(0.2)
    ads = api("/api/ads?page_size=2")["items"]
    made = api("/api/requests", {"question": "Under 35 with exceptions; I am 38. What should I clarify?", "profile": {"age": 38}, "consent": {"fields": ["age"]},
                                 "evidence": [api("/api/ads/" + a["id"]) for a in ads]}, {"X-Idempotency-Key": "a11y-" + str(os.getpid())})
    routes = [("home", "#/"), ("why", "#/why"), ("findings", "#/findings"), ("seeker", "#/seeker"), ("seeker_result", "#/seeker"), ("evidence", "#/evidence/" + ads[0]["id"]),
              ("requests", "#/requests"), ("request_detail", "#/requests/" + made["code"]), ("reviewer_signin", "#/reviewer"), ("reviewer", "#/reviewer"),
              ("study", "#/study"), ("score", "#/study/score"), ("about", "#/about"), ("access", "#/access"), ("pro", "#/pro")]
    with sync_playwright() as pw:
        br = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        for w, hgt in ((1280, 900), (360, 780)):
            for name, h in routes:
                ctx = br.new_context(viewport={"width": w, "height": hgt}, reduced_motion="reduce")
                init = "try{localStorage.setItem('al_owner_tokens', %s)}catch(e){}" % json.dumps(json.dumps({made["code"]: made["token"]}))
                if name == "reviewer":
                    init += ";try{sessionStorage.setItem('al_reviewer_token', %s)}catch(e){}" % json.dumps(RVTOK)
                ctx.add_init_script(init)
                p = ctx.new_page(); p.goto(BASE + "/" + h); p.wait_for_load_state("networkidle"); p.wait_for_timeout(900)
                if name == "seeker_result":
                    p.click("button:has-text('Use an example')"); p.click("#go-btn"); p.wait_for_selector("#ads-more", timeout=45000); p.evaluate("document.getElementById('ads-more').open=true"); p.wait_for_selector("#ads .card", timeout=45000)
                    p.check("#ads .card input[type=checkbox]"); p.wait_for_timeout(300)
                if name == "reviewer":
                    p.wait_for_selector(".rv-item"); p.click(".rv-item"); p.wait_for_selector("#rbody")
                r = p.evaluate(AUDIT_JS)
                # keyboard walk
                p.evaluate("window.scrollTo(0,0)"); p.focus("body") if False else p.evaluate("document.activeElement && document.activeElement.blur()")
                nofocus, stops, last, same, trap = [], 0, None, 0, []
                for _ in range(150):
                    p.keyboard.press("Tab"); f = p.evaluate(FOCUS_JS)
                    if not f:
                        continue
                    stops += 1
                    same = same + 1 if f["uid"] == last else 0; last = f["uid"]
                    if same >= (5 if f["sub"] else 2) and f["d"] not in trap:
                        trap.append(f["d"])
                    if not f["ring"]:
                        nofocus.append(f["d"])
                r["focus_invisible"] = sorted(set(nofocus)); r["tab_stops"] = stops; r["keyboard_trap"] = trap
                report[f"{name}@{w}"] = r
                hi = len(r["noname"]) + len(r["hiddenFocusable"]) + len(r["contrast"]) + len(r["focus_invisible"]) + len(r["img"]) + len(r["keyboard_trap"]) + len(r["badRefs"])
                high += hi
                ctx.close()
        br.close()
finally:
    srv.terminate()
    try:
        srv.wait(timeout=5)
    except subprocess.TimeoutExpired:
        srv.kill()
    shutil.rmtree(tmp, ignore_errors=True)
if "--json" in sys.argv:
    print(json.dumps(report, ensure_ascii=False, indent=1))
else:
    for k, r in report.items():
        items = {x: r[x] for x in ("noname", "img", "media", "hiddenFocusable", "tabpos", "dupIds", "badRefs", "contrast", "focus_invisible", "keyboard_trap") if r[x]}
        print(f"{k}: tab stops {r['tab_stops']}, unknown-bg text {r['unknownBg']}" + ("" if items else " -- clean"))
        for x, v in items.items():
            print(f"   {x} ({len(v)}): " + " | ".join(v[:8]))
print(f"\nhigh-severity findings: {high}")
sys.exit(1 if high else 0)
