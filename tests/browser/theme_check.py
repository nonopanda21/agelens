"""Theme check for inner pages: screenshots at 1280 and 360, console errors, horizontal overflow.
Usage: ~/agelens-tools/pw/bin/python tests/browser/theme_check.py [base_url]
Writes PNGs to docs/screenshots/theme/ and prints a summary."""
import json, sys, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8811"
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots" / "theme"
OUT.mkdir(parents=True, exist_ok=True)

ad_id = json.load(urllib.request.urlopen(BASE + "/api/ads"))["items"][0]["id"]
ROUTES = [("home", "#/"), ("seeker", "#/seeker"), ("evidence", "#/evidence/" + ad_id),
          ("requests", "#/requests"), ("reviewer", "#/reviewer"), ("study", "#/study"), ("score", "#/study/score"), ("about", "#/about"), ("access", "#/access"), ("pro", "#/pro")]

problems = []


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def shoot(page, name, w):
    page.wait_for_timeout(900)
    ov = overflow(page)
    if ov > 0:
        wide = page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
            .slice(0, 5).map(e => e.tagName + '.' + e.className)""")
        problems.append(f"{name}@{w}: horizontal overflow {ov}px {wide}")
    page.screenshot(path=str(OUT / f"{name}-{w}.png"), full_page=True)


with sync_playwright() as p:
    br = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
    for w in (1280, 360):
        ctx = br.new_context(viewport={"width": w, "height": 900 if w > 400 else 780}, reduced_motion="reduce")
        page = ctx.new_page()
        errs = []
        page.on("console", lambda m: m.type == "error" and errs.append(m.text))
        page.on("pageerror", lambda e: errs.append(str(e)))
        for name, h in ROUTES:
            page.goto(BASE + "/" + h)
            page.wait_for_load_state("networkidle")
            shoot(page, name, w)
            if name == "seeker":
                page.get_by_role("button", name="Fill in an example question").first.click()
                page.wait_for_timeout(300)
                go = page.locator("#go-btn")
                go.click()
                page.wait_for_timeout(2500)
                page.wait_for_load_state("networkidle")
                shoot(page, "seeker-result", w)
        # sticky header check on an inner page
        page.goto(BASE + "/#/about"); page.wait_for_timeout(600)
        pos = page.evaluate("getComputedStyle(document.getElementById('nav')).position")
        bg = page.evaluate("getComputedStyle(document.getElementById('nav')).backgroundColor")
        if pos != "sticky":
            problems.append(f"nav position on inner page is {pos}")
        # keyboard focus visible on first focusable in main
        page.keyboard.press("Tab"); page.keyboard.press("Tab")
        foc = page.evaluate("(()=>{const a=document.activeElement;const s=getComputedStyle(a);return a.tagName+' outline:'+s.outlineStyle+' '+s.outlineWidth})()")
        print(f"[{w}] nav={pos} bg={bg} focus={foc}")
        for e in errs:
            problems.append(f"console@{w}: {e[:200]}")
        ctx.close()
    br.close()

print("screenshots:", OUT)
print("PROBLEMS:" if problems else "No problems found.")
for x in problems:
    print(" -", x)
