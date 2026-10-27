"""Route sweep (automation task T03): every main route at 1280 and 360 px in real Chromium.
usage: ~/agelens-tools/pw/bin/python tests/browser/sweep.py
Starts its OWN server (temp copy of data/agelens.db, free port in 8822-8829, AGELENS_REVIEWER_TOKEN) and stops only that server.
Fails (exit 1) on: console errors / page errors, unexpected 4xx/5xx responses, horizontal overflow, or CJK text outside
elements that hold quoted ad text / original values. Screenshots: docs/screenshots/sweep/<route>_<width>.png.
Evidence holders (CJK allowed): .orig .ex-snip .ex-ad-t .ev-title .rq-ev-title .st-adtext mark.age .zh-orig .quote and any
element marked lang="zh*" (verbatim Chinese ad wording quoted inside English prose; the UI marks it so screen readers switch voice).
The literal brand/legal footnotes have no CJK, so any other CJK is a UI-label leak."""
import json, os, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots" / "sweep"
SHOTS.mkdir(parents=True, exist_ok=True)
RVTOK = "sweep-reviewer-token-" + str(os.getpid())
EVIDENCE = '.orig, .ex-snip, .ex-ad-t, .ev-title, .rq-ev-title, .st-adtext, mark.age, .zh-orig, .quote, [lang^="zh"]'
CJK_JS = r"""(ev) => {
  const R = /[㐀-鿿豈-﫿　-〿＀-￯]/;
  const out = [];
  const inEv = (el) => !!(el && el.closest && el.closest(ev));
  const vis = (el) => el.closest('option') ? true : (el.checkVisibility ? el.checkVisibility({ checkVisibilityCSS: true }) : !!el.getClientRects().length);
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) { const el = n.parentElement; if (!el || el.closest('script,style') || inEv(el) || !vis(el)) continue;
    if (R.test(n.nodeValue)) out.push('<' + el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/).join('.') : '') + '> ' + n.nodeValue.trim().slice(0, 60)); }
  document.querySelectorAll('[title],[aria-label],[placeholder],[alt]').forEach((el) => { if (inEv(el) || !vis(el)) return;
    for (const a of ['title', 'aria-label', 'placeholder', 'alt']) { const v = el.getAttribute(a); if (v && R.test(v)) out.push('@' + a + ' ' + v.slice(0, 60)); } });
  return out;
}"""
results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond or not extra else " -- " + str(extra)[:500]), flush=True)


def free_port():
    for p in range(8822, 8830):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise SystemExit("no free port in 8822-8829")


PORT = free_port()
BASE = f"http://127.0.0.1:{PORT}"


def api(path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=dict({"Content-Type": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


tmp = tempfile.mkdtemp(prefix="agelens_sweep_")
shutil.copy(ROOT / "data" / "agelens.db", os.path.join(tmp, "sweep.db"))
env = dict(os.environ, AGELENS_DB=os.path.join(tmp, "sweep.db"), AGELENS_REVIEWER_TOKEN=RVTOK)
srv = subprocess.Popen([str(ROOT / ".venv/bin/python"), "app.py", "--port", str(PORT)], cwd=ROOT, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=1); break
        except Exception:
            if srv.poll() is not None:
                raise SystemExit("server exited early")
            time.sleep(0.2)
    # content so #/requests, #/reviewer and #/evidence are not empty
    ads = api("/api/ads?page_size=2")["items"]
    ev_id = ads[0]["id"]
    made = api("/api/requests", {"question": "The ad says under 35 with exceptions. I am 38 in procurement. What should I clarify?",
                                 "profile": {"age": 38, "occupation": "Procurement", "years_experience": 8, "region": ads[0]["province"]},
                                 "consent": {"fields": ["age", "occupation", "years_experience", "region"]},
                                 "evidence": [api("/api/ads/" + a["id"]) for a in ads], "scope": {"matched_total": 2}},
               {"X-Idempotency-Key": "sweep-" + str(os.getpid())})
    tokens = json.dumps({made["code"]: made["token"]})
    ROUTES = [("home", "#/"), ("explore", "#/explore"), ("seeker", "#/seeker"), ("evidence", "#/evidence/" + ev_id),
              ("requests", "#/requests"), ("request_detail", "#/requests/" + made["code"]), ("reviewer", "#/reviewer"),
              ("study", "#/study"), ("score", "#/study/score"), ("about", "#/about"), ("access", "#/access"), ("pro", "#/pro")]

    with sync_playwright() as pw:
        br = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
        for w, hgt in ((1280, 900), (360, 780)):
            ctx = br.new_context(viewport={"width": w, "height": hgt})
            ctx.add_init_script("try{localStorage.setItem('al_owner_tokens', %s); sessionStorage.setItem('al_reviewer_token', %s)}catch(e){}"
                                % (json.dumps(tokens), json.dumps(RVTOK)))
            page = ctx.new_page()
            cur = {"route": None}
            errs, bad = [], []
            page.on("console", lambda m: errs.append((cur["route"], m.text)) if m.type == "error" else None)
            page.on("pageerror", lambda e: errs.append((cur["route"], "pageerror " + str(e))))
            page.on("response", lambda r: bad.append((cur["route"], r.status, r.url)) if r.status >= 400 else None)
            for name, h in ROUTES:
                cur["route"] = name
                n_err, n_bad = len(errs), len(bad)
                page.goto(BASE + "/" + h)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1200)
                if name == "seeker":  # also sweep a filled result page (answer, cards, review panel)
                    page.click("button:has-text('Use an example')"); page.click("#go-btn")
                    page.wait_for_selector("#ads .card", timeout=45000)
                    page.check("#ads .card input[type=checkbox]"); page.wait_for_timeout(400)
                if name == "home":   # scroll through so lazy sections (marquee, data overview, footer) render
                    for y in range(0, 12000, 700):
                        page.evaluate(f"window.scrollTo(0,{y})"); page.wait_for_timeout(60)
                    # back to the top before the full-page shot, so the hero is not caught mid scroll-exit (faded)
                    page.evaluate("window.scrollTo({top:0,behavior:'instant'})"); page.wait_for_timeout(500)
                ov = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                cjk = page.evaluate(CJK_JS, EVIDENCE)
                page.evaluate("()=>{const n=document.getElementById('nav'); if(n) n.style.position='static'}")
                page.screenshot(path=str(SHOTS / f"{name}_{w}.png"), full_page=True)
                tag = f"{name} @{w}"
                check(f"{tag}: no console/page errors", len(errs) == n_err, errs[n_err:])
                check(f"{tag}: no 4xx/5xx", len(bad) == n_bad, bad[n_bad:])
                check(f"{tag}: no horizontal overflow", ov <= 0, f"{ov}px")
                leak = page.evaluate("document.body.innerText.match(/\\[object [A-Za-z]+\\]|undefined|NaN%/g)")
                check(f"{tag}: no [object ...] / undefined / NaN% in page text", not leak, leak)
                check(f"{tag}: no CJK outside evidence", not cjk, cjk[:10])
            ctx.close()
        br.close()
except Exception as e:
    check("sweep completed without exception", False, repr(e))
finally:
    srv.terminate()
    try:
        srv.wait(timeout=5)
    except subprocess.TimeoutExpired:
        srv.kill()
    shutil.rmtree(tmp, ignore_errors=True)
fails = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} checks passed")
sys.exit(1 if fails else 0)
