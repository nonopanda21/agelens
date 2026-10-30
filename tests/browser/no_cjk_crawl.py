"""No-CJK crawler (docs/ENGLISH_UI.md): visits every route at 1280 and 390 px, opens one evidence page and one request,
runs a Job Seeker search, every demo case and the Quick check, and counts CJK characters in document.body.innerText and in
title / aria-label / placeholder / alt attributes (any element, visible or not). Input / textarea VALUES are user input and
are not counted. Also reports AgeLens.scrubLog: strings the DOM builder's safety net had to clean (a missing English field).
usage: ~/agelens-tools/pw/bin/python tests/browser/no_cjk_crawl.py http://127.0.0.1:8862   (env AGELENS_REVIEWER_TOKEN = server's)
Exit 1 if any CJK is found."""
import json, os, re, sys, urllib.request
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8862"
RVTOK = os.environ.get("AGELENS_REVIEWER_TOKEN", "")
SHOTS = sys.argv[2] if len(sys.argv) > 2 else None
CJK = r"[⺀-⿟　-〿぀-ヿ㄀-ㄯ㆐-ㇿ㐀-䶿一-鿿豈-﫿︰-﹏＀-￯]"
COUNT_JS = r"""(src) => {
  const R = new RegExp(src, 'g');
  const t = (document.body.innerText.match(R) || []).length;
  const samples = (document.body.innerText.match(new RegExp('.{0,24}' + src + '+.{0,24}', 'g')) || []).slice(0, 5);
  let a = 0;
  document.querySelectorAll('[title],[aria-label],[placeholder],[alt]').forEach((el) => {
    for (const k of ['title', 'aria-label', 'placeholder', 'alt']) { const v = el.getAttribute(k); const m = v && v.match(R); if (m) { a += m.length; if (samples.length < 8) samples.push('@' + k + ' ' + v.slice(0, 40)); } } });
  const dt = (document.title.match(R) || []).length;
  const scrub = (window.AgeLens && AgeLens.scrubLog || []).splice(0).map((x) => x.where);
  return { text: t, attr: a, doc_title: dt, samples, scrubbed: scrub.length, scrub_where: [...new Set(scrub)].slice(0, 6) };
}"""


def api(path, body=None, headers=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers=dict({"Content-Type": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


ads = api("/api/ads?page_size=2")["items"]
made = api("/api/requests", {"question": "The ad says under 35 with exceptions. I am 38 in procurement. What should I clarify?",
                             "profile": {"age": 38, "occupation": "Procurement", "years_experience": 8, "region": ads[0]["province"]},
                             "consent": {"fields": ["age", "occupation", "years_experience", "region"]},
                             "evidence": [api("/api/ads/" + a["id"]) for a in ads], "scope": {"matched_total": 2}},
           {"X-Idempotency-Key": "nocjk-" + ads[0]["id"] + str(os.getpid())})
ROUTES = [("home", "#/"), ("why", "#/why"), ("findings", "#/findings"), ("explore", "#/explore"), ("seeker", "#/seeker"), ("evidence", "#/evidence/" + ads[0]["id"]),
          ("requests", "#/requests"), ("request", "#/requests/" + made["code"]), ("reviewer", "#/reviewer"),
          ("reviewer_req", "#/reviewer/" + made["code"]), ("study", "#/study"), ("score", "#/study/score"),
          ("about", "#/about"), ("access", "#/access"), ("pro", "#/pro"), ("notfound", "#/no-such-page")]
res, errs = {}, []


def rec(page, key):
    page.wait_for_timeout(500)
    r = page.evaluate(COUNT_JS, CJK)
    res[key] = r
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        page.screenshot(path=os.path.join(SHOTS, key.replace(" ", "_").replace("/", "-") + ".png"), full_page=True)


with sync_playwright() as pw:
    br = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
    for w, hh in ((1280, 900), (390, 844)):
        ctx = br.new_context(viewport={"width": w, "height": hh})
        ctx.add_init_script("try{sessionStorage.setItem('al_splash_seen','1');localStorage.setItem('al_owner_tokens', %s);sessionStorage.setItem('al_reviewer_token', %s)}catch(e){}"
                            % (json.dumps(json.dumps({made["code"]: made["token"]})), json.dumps(RVTOK)))
        page = ctx.new_page()
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        for name, h in ROUTES:
            page.goto(BASE + "/" + h); page.wait_for_load_state("networkidle"); page.wait_for_timeout(900)
            if name == "home":
                for y in range(0, 14000, 600):
                    page.evaluate(f"window.scrollTo({{top:{y},behavior:'instant'}})"); page.wait_for_timeout(50)
            if name == "explore":
                page.wait_for_selector(".ex-ads li", timeout=20000)
            rec(page, f"{name} @{w}")
        # Job Seeker: example search, then every demo case, then the review panel with a selected ad
        page.goto(BASE + "/#/seeker"); page.wait_for_selector("#f-question")
        page.click("button:has-text('Use an example')"); page.click("#go-btn")
        page.wait_for_selector("#ads .card", timeout=45000)
        page.check("#ads .card input[type=checkbox]"); page.wait_for_timeout(300)
        rec(page, f"seeker answer @{w}")
        page.click("#demo-cases summary")
        for cid in ["procurement", "injection", "conflict", "truncated", "nomatch", "nomodel"]:
            page.click(f'button[data-case="{cid}"]')
            page.wait_for_function("""()=>{const a=document.getElementById('answer');
                return a && !a.querySelector('.spinner') && (a.querySelector('.answer h2') || a.querySelector('.problem'))}""", timeout=45000)
            rec(page, f"seeker case {cid} @{w}")
        # Quick check with each example chip
        page.goto(BASE + "/#/about"); page.wait_for_load_state("networkidle")
        if w >= 1000 or page.locator(".sk-tab").is_visible():
            page.click(".sk-tab")
        else:
            page.evaluate("AgeLens.quickCheck.open()")
        for i in range(3):
            page.click(f'.sk-chip[data-ex="{i}"]'); page.wait_for_selector(".sk-res", timeout=10000); page.wait_for_timeout(200)
            rec(page, f"quickcheck ex{i} @{w}")
        ctx.close()
    br.close()

total = 0
for k, v in res.items():
    n = v["text"] + v["attr"] + v["doc_title"]; total += n
    print(f"{k:34s} CJK={n:3d}  scrubbed={v['scrubbed']:3d}" + (f"  {v['samples'][:3]}" if n else "") + (f"  safety-net: {v['scrub_where']}" if v["scrubbed"] else ""))
print("console/page errors:", errs[:10])
print("TOTAL CJK:", total)
sys.exit(1 if total else 0)
