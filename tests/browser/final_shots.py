"""Delivery screenshots (desktop 1440x900 @2x and mobile 360x780 @2x) into docs/screenshots/final/.
Usage: AGELENS_REVIEWER_TOKEN=<token> ~/agelens-tools/pw/bin/python tests/browser/final_shots.py http://127.0.0.1:PORT"""
import os, sys, json, urllib.request
from playwright.sync_api import sync_playwright
BASE = sys.argv[1]; OUT = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "screenshots", "final"); TOK = os.environ.get("AGELENS_REVIEWER_TOKEN", "")
ad = json.load(urllib.request.urlopen(BASE + "/api/ads?age_class=cap_with_exception&page_size=1"))["items"][0]["id"]
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
    for tag, vp, mob in (("desktop", {"width": 1440, "height": 900}, False), ("mobile", {"width": 360, "height": 780}, True)):
        pg = b.new_page(viewport=vp, device_scale_factor=2, is_mobile=mob, has_touch=mob)
        pg.on("pageerror", lambda x: errs.append(str(x)[:140])); pg.on("console", lambda m: errs.append(m.text[:140]) if m.type == "error" else None)
        pg.goto(BASE + "/#/"); pg.wait_for_timeout(5000); pg.screenshot(path=f"{OUT}/{tag}_01_home_hero.png")
        for sec in ("how", "marquee", "data", "literature", "steps", "footer"):
            pg.evaluate(f"document.getElementById('{sec}').scrollIntoView({{block:'start'}})"); pg.wait_for_timeout(1800)
            pg.screenshot(path=f"{OUT}/{tag}_02_home_{sec}.png")
        pg.goto(BASE + "/#/seeker"); pg.wait_for_timeout(1200); pg.screenshot(path=f"{OUT}/{tag}_03_seeker.png", full_page=True)
        pg.goto(BASE + f"/#/evidence/{ad}"); pg.wait_for_timeout(1200); pg.screenshot(path=f"{OUT}/{tag}_04_evidence.png", full_page=True)
        pg.goto(BASE + "/#/reviewer"); pg.wait_for_timeout(800)
        if TOK:
            pg.locator("input").first.fill(TOK); pg.get_by_role("button").filter(has_text="Sign in").first.click(); pg.wait_for_timeout(1200)
        pg.screenshot(path=f"{OUT}/{tag}_06_reviewer.png")
        pg.goto(BASE + "/#/about"); pg.wait_for_timeout(800); pg.screenshot(path=f"{OUT}/{tag}_07_about.png")
        pg.close()
    b.close()
print("errors:", errs[:5]); print("files:", len(os.listdir(OUT)))
