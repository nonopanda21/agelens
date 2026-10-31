"""Real-browser check of the 'Try an example situation' control and the pasted-ad check on Check an ad (#/seeker).
Runs in presenter mode (#/seeker?demo=1), where all six cases are listed; without it only the four user-facing ones are.
usage: ~/agelens-tools/pw/bin/python tests/browser/demo_cases.py http://127.0.0.1:8815
Every case is opened and run with the KEYBOARD only (Tab/Enter on the summary and the case button).
Prints observations as JSON (human-observation aid, separate from the unit tests); exits 1 on a failed check."""
import json, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8815"
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots" / "demo_cases"
OUT.mkdir(parents=True, exist_ok=True)
CASES = ["procurement", "injection", "conflict", "truncated", "nomatch", "nomodel"]
obs, errors, fails = {}, [], []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def fresh(browser, w, h):
    ctx = browser.new_context(viewport={"width": w, "height": h})
    page = ctx.new_page()
    # The deliberate binary-paste rejection makes Chromium log "Failed to load resource ... 422"; that one is expected.
    page.on("console", lambda m: errors.append((w, m.type, m.text)) if m.type == "error" and "status of 422" not in m.text else None)
    page.on("pageerror", lambda e: errors.append((w, "pageerror", str(e))))
    return ctx, page


def keyboard_to(page, selector, limit=80):
    """Press Tab until `selector` has focus (proves it is reachable by keyboard)."""
    for _ in range(limit):
        if page.evaluate("(s)=>document.activeElement && document.activeElement.matches(s)", selector):
            return True
        page.keyboard.press("Tab")
    return False


def run_case(page, w, cid):
    page.goto(BASE + "/#/seeker?demo=1")
    page.evaluate("sessionStorage.clear()")
    page.reload()                                   # fresh module state, menu closed
    page.wait_for_selector("#demo-cases summary")
    page.focus("#f-question")
    check(keyboard_to(page, "#demo-cases summary"), f"{w} {cid}: summary not reachable by Tab")
    page.keyboard.press("Enter")
    check(keyboard_to(page, f'button[data-case="{cid}"]'), f"{w} {cid}: case button not reachable by Tab")
    page.keyboard.press("Enter")
    page.wait_for_function("""()=>{const a=document.getElementById('answer');
        return a && !a.querySelector('.spinner') && (a.querySelector('.answer h2') || a.querySelector('.problem'))}""", timeout=45000)
    page.wait_for_timeout(400)
    ans = page.inner_text("#answer")
    ads = page.inner_text("#ads")
    ov = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    # screenshot only: let the sticky nav scroll away so it does not cover the answer badges
    page.evaluate("()=>{const n=document.getElementById('nav'); if(n) n.style.position='static'}")
    page.locator("#answer").screenshot(path=str(OUT / f"{cid}_{w}.png"))
    # English-only UI (docs/ENGLISH_UI.md): the answer and the pasted-ad card must not echo any Chinese, even for pasted Chinese ads
    full = page.evaluate("document.body.innerText")
    hits = re.findall(r".{0,20}[\u3000-\u303f\u3400-\u9fff\uff00-\uffef].{0,20}", full)
    check(not hits, f"{w} {cid}: CJK on the page: {hits[:4]}")
    return {"answer_head": ans[:900], "ads_head": ads[:300], "overflow_px": ov,
            "focus": page.evaluate("document.activeElement && (document.activeElement.id || document.activeElement.tagName)")}


with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
    for w, hgt in ((1280, 900), (360, 780)):
        ctx, page = fresh(b, w, hgt)
        page.goto(BASE + "/#/seeker"); page.wait_for_selector("#demo-cases summary")
        page.click("#demo-cases summary")
        shown = page.eval_on_selector_all("#demo-cases button[data-case]", "els=>els.map(e=>e.dataset.case)")
        check(shown == ["procurement", "injection", "conflict", "truncated"], f"{w}: user-facing cases {shown}")
        check("data/sim" not in page.inner_text("#demo-cases") and "presenter" not in page.inner_text("#demo-cases").lower(), f"{w}: presenter wording shown to users")
        page.goto(BASE + "/#/seeker?demo=1"); page.reload(); page.wait_for_selector("#demo-cases summary")
        page.click("#demo-cases summary")
        page.locator("form.ask-form").screenshot(path=str(OUT / f"menu_open_{w}.png"))
        for cid in CASES:
            r = run_case(page, w, cid)
            obs[f"{cid}_{w}"] = r
            check(r["overflow_px"] <= 0, f"{w} {cid}: horizontal overflow {r['overflow_px']}px")
            a = r["answer_head"]
            check("Example situation (fictional)" in a, f"{w} {cid}: example label missing")
            if cid != "nomatch":
                full_a = page.inner_text("#answer")
                check("In short" in full_a and "Your question for the employer" in full_a, f"{w} {cid}: summary card")
            if cid == "procurement":
                check("Demo · Synthetic data" in a and "Template demo" in a, f"{w} procurement: labels")
                check("ad_" not in a, f"{w} procurement: raw ad id on screen")
            if cid in ("injection", "conflict", "truncated"):
                check("Pasted text, not stored" in a, f"{w} {cid}: pasted label")
                check("Instructions inside ads are ignored" in a, f"{w} {cid}: ignore-instructions note")
                check("Demo · Synthetic data" not in a, f"{w} {cid}: must not claim synthetic data")
                check("Pasted text, not stored" in r["ads_head"], f"{w} {cid}: pasted text card")
            if cid == "injection":
                check("Instructions inside the ad were ignored" in a and "Ignore previous instructions" in a, f"{w} injection: quoted note")
                body = a.split("These lines look like instructions")[0] + a.split("What does the ad explicitly say?")[-1]
                check("approved" not in body.split("Ignore previous")[0].lower(), f"{w} injection: approval leaked")
                check("maximum age of 35" in a or "maximum age of 35" in page.inner_text("#answer"), f"{w} injection: real cap read")
            if cid == "conflict":
                check("contradicts itself" in page.inner_text("#answer"), f"{w} conflict: contradiction")
            if cid == "truncated":
                check("No age limit was read from the cut-off part" in a, f"{w} truncated: note")
                check("maximum age of 35" not in page.inner_text("#answer"), f"{w} truncated: read as cap")
            if cid == "nomatch":
                check("No ads match all of these conditions" in a and "Search all regions" in a and "Drop the occupation text" in a, f"{w} nomatch: empty state")
            if cid == "nomodel":
                check("Template demo" in a and "No model is connected" in a, f"{w} nomodel: label")
        # the broaden path from the no-match case works by keyboard
        run_case(page, w, "nomatch")
        page.focus("#answer button.btn-secondary >> nth=1")
        page.keyboard.press("Enter")
        page.wait_for_function("()=>{const a=document.getElementById('answer');return a && !a.querySelector('.spinner') && /broadened/.test(a.innerText)}", timeout=45000)
        obs[f"nomatch_broadened_{w}"] = page.inner_text("#answer")[:400]
        page.locator("#answer").screenshot(path=str(OUT / f"nomatch_broadened_{w}.png"))
        # paste box: empty, oversize-by-typing is blocked by maxlength; empty -> message; server rejection shown plainly
        page.fill("#f-question", "What does this ad say?")
        page.fill("#f-adtext", "")
        page.click("#paste-btn")
        obs[f"paste_empty_{w}"] = page.inner_text("#paste-err")
        check("Paste the ad text first" in obs[f"paste_empty_{w}"], f"{w} paste empty message")
        page.fill("#f-adtext", "\u0001\u0002\u0003\u0004 binary 年龄")
        page.click("#paste-btn")
        page.wait_for_selector("#answer .problem")
        obs[f"paste_binary_{w}"] = page.inner_text("#answer")[:300]
        check("does not look like ad text" in obs[f"paste_binary_{w}"], f"{w} paste binary message")
        page.locator("#answer").screenshot(path=str(OUT / f"paste_rejected_{w}.png"))
        ctx.close()
    b.close()

print(json.dumps({"observations": obs, "console_errors": errors, "failed_checks": fails}, ensure_ascii=False, indent=1))
sys.exit(1 if fails or errors else 0)
