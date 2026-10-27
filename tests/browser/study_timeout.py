"""Countdown reaches zero -> answer auto-submitted with timed_out flag (SIMULATION server only). Uses a 6 s limit then resets it."""
import os, sys, json, urllib.request
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8806"
TOK = os.environ.get("STUDY_TOKEN", "demo-study-token")
def set_limit(s):
    r = urllib.request.Request(BASE + "/api/study/sim-time-limit", data=json.dumps({"seconds": s}).encode(), headers={"X-Study-Token": TOK, "Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r).read())["time_limit_s"]
print("limit set", set_limit(6))
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(); p = b.new_page(); errs = []
        p.on("console", lambda m: m.type == "error" and errs.append(m.text)); p.goto(BASE + "/#/study"); p.check("#st-agree"); p.click("text=Begin")
        p.wait_for_selector("#st-answer"); p.fill("#st-answer", "Half-written request about the age wording")
        p.wait_for_selector("text=Time is up", timeout=15000); print("auto-submitted:", p.inner_text(".notice"), "| console errors:", errs or "none")
        b.close()
finally:
    print("limit reset", set_limit(None))
