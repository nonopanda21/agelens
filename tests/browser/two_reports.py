"""The two report buttons on a pasted ad, at 1280 and 360. Needs a server: python3 tests/browser/two_reports.py [base_url] [shots_dir]
With no model connected the AI button must be disabled and say why; with one, both reports open and download."""
import json, sys, urllib.request
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8871"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else None
AD = "采购专员。任职要求：年龄35岁以下，条件优秀者可放宽至40岁。"
fails = []
connected = json.load(urllib.request.urlopen(BASE + "/api/ai/status"))["connected"]
def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok: fails.append(name)
with sync_playwright() as p:
    b = p.chromium.launch()
    for w, h in ((1280, 900), (360, 740)):
        ctx = b.new_context(viewport={"width": w, "height": h}, accept_downloads=True); pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE + "/#/seeker"); pg.wait_for_selector("#f-adtext"); pg.fill("#f-adtext", AD)
        pg.locator("#f-age").fill("38")
        with pg.expect_response("**/api/paste/check", timeout=60000):
            pg.click("#paste-btn")
        pg.wait_for_selector(".tr-btn", timeout=10000)
        tpl, ai = pg.locator(".tr-btn").nth(0), pg.locator(".tr-btn").nth(1)
        check(f"{w} labels", "Fixed template report" in tpl.inner_text() and "AI report" in ai.inner_text())
        check(f"{w} panel closed at first", pg.locator("#tr-panel").is_hidden())
        tpl.click(); t = pg.inner_text("#tr-panel")
        check(f"{w} template opens", "No AI" in t and "Checklist" in t and "The ad says:" in t and tpl.get_attribute("aria-expanded") == "true")
        check(f"{w} template ignores the person", "38" not in pg.inner_text(".tr-q"))
        with pg.expect_download() as d:
            pg.click("text=Download this report (Markdown)")
        check(f"{w} template download", d.value.suggested_filename == "agelens-template-report.md")
        if connected:
            check(f"{w} AI enabled", ai.is_enabled())
            ai.click(); t = pg.inner_text("#tr-panel")
            check(f"{w} AI opens", "AI model" in t and "Checklist" not in t and "Evidence from the rules" in t and ai.get_attribute("aria-expanded") == "true" and tpl.get_attribute("aria-expanded") == "false")
            with pg.expect_download() as d:
                pg.click("text=Download this report (Markdown)")
            check(f"{w} AI download", d.value.suggested_filename == "agelens-ai-report.md")
        else:
            check(f"{w} AI disabled with a reason", ai.is_disabled() and "no AI model" in pg.inner_text(".tr"))
        check(f"{w} no raw objects", "[object" not in pg.inner_text(".tr") and "null" not in pg.inner_text("#tr-panel"))
        check(f"{w} no overflow", not pg.evaluate("document.documentElement.scrollWidth > innerWidth"))
        check(f"{w} no Chinese in reports", not pg.evaluate("/[\\u4e00-\\u9fff]/.test(document.querySelector('.tr').innerText)"))
        check(f"{w} no page errors", not errs)
        if SHOTS:
            pg.locator(".tr").screenshot(path=f"{SHOTS}/tr_{w}.png")
        ctx.close()
    b.close()
print("FAILS", fails)
sys.exit(1 if fails else 0)
