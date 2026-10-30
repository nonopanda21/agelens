"""Real-browser run of the study tools against a SIMULATION-mode server (default http://127.0.0.1:8806).
Everything it creates is simulated: participants, raters' behaviour and answers are scripted placeholders.
Crossover design (default): scripted writers produce a good request with probability P_GOOD_A on ad-only tasks and P_GOOD_B
on AgeLens tasks (env, defaults .40 / .65). That built-in difference is an ASSUMPTION used to exercise the analysis; it is not
evidence about AgeLens. Run it only against a simulation-mode server on its own DB copy (never the main server).
Usage: PW=<playwright python> $PW tests/browser/study_flow.py [base_url] [n_participants]
Env: AGELENS_STUDY_TOKEN value is passed as STUDY_TOKEN (default demo-study-token)."""
import json, os, random, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8806"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 8
TOKEN = os.environ.get("STUDY_TOKEN", "demo-study-token")
ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs/screenshots/study"
OUT = Path(os.environ.get("STUDY_OUT", ROOT / "data/study/simulated_example"))
SHOTS.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(int(os.environ.get("STUDY_SEED", "4242")))
P_GOOD = {"none": float(os.environ.get("P_GOOD_A", "0.40")), "agelens": float(os.environ.get("P_GOOD_B", "0.65"))}
problems = []
ARGS = ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"]

GOOD = ("Hello, I am writing about the {job} (ad {ad}). I am {age} with {yrs} years of experience. The ad says \"{quote}\". "
        "I cannot tell from the ad whether this is strict or whether an exception applies to me. Could you tell me how this wording is applied and what you would need from me?")
BAD = ["I am too old so I will be rejected. This ad is illegal and discriminatory.", "Please tell me more about the job.",
       "The ad says the limit is 35 and I qualify for the exception, please confirm I can apply."]


def watch(page, tag):
    page.on("console", lambda m: m.type == "error" and "403 (Forbidden)" not in m.text and problems.append(f"{tag} console: {m.text}"))
    page.on("pageerror", lambda e: problems.append(f"{tag} pageerror: {e}"))


def overflow(page, tag):
    w = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    if w[0] > w[1]:
        problems.append(f"{tag}: horizontal overflow {w}")


def participant(pw, i, shoot=False):
    b = pw.chromium.launch(args=ARGS)
    for vp, tagv in (({"width": 1280, "height": 900}, "1280"),) + ((({"width": 360, "height": 780}, "360"),) if shoot else ()):
        ctx = b.new_context(viewport=vp)
        page = ctx.new_page(); watch(page, f"p{i}-{tagv}")
        page.goto(BASE + "/#/study"); page.wait_for_selector("text=Information and consent")
        if shoot:
            page.screenshot(path=str(SHOTS / f"study-intro-{tagv}.png"), full_page=True); overflow(page, "intro " + tagv)
        if tagv == "360":
            ctx.close(); continue
        # keyboard: tab to checkbox, space, then Begin via Enter
        page.focus("#st-agree"); page.keyboard.press("Space")
        page.keyboard.press("Tab"); assert page.evaluate("document.activeElement.textContent") == "Begin", "keyboard focus order"
        page.keyboard.press("Enter")
        for k in range(4):
            page.wait_for_selector("#st-answer"); page.wait_for_timeout(150)
            title = page.inner_text("h1"); aid_head = page.inner_text(".st-aid h2")
            kind = ("none" if "No extra help" in aid_head else "agelens" if "AgeLens" in aid_head
                    else "assisted" if "Drafted" in page.inner_text(".st-aid .badge") else "template")
            ad = page.inner_text(".st-adtext")
            if shoot and k == 0:
                page.screenshot(path=str(SHOTS / f"study-task-{kind}-1280.png"), full_page=True)
                page.set_viewport_size({"width": 360, "height": 780}); page.wait_for_timeout(200)
                page.screenshot(path=str(SHOTS / f"study-task-{kind}-360.png"), full_page=True); overflow(page, "task 360")
                page.set_viewport_size({"width": 1280, "height": 900})
            r = rng.random()
            if kind in P_GOOD:  # crossover: scripted quality difference (assumption, see header)
                if r < P_GOOD[kind]:
                    page.fill("#st-answer", GOOD.format(job="position", ad=re.search(r"SIM-S0\d", page.inner_text(".st-ad")).group(0), age=38, yrs=8, quote=(ad.split("\n")[-2:-1] or [ad])[0][:30]))
                else:
                    page.fill("#st-answer", rng.choice(BAD))
            elif kind == "assisted" and r < 0.8:
                page.once("dialog", lambda d: d.accept())
                page.click("text=Insert into my answer")
            elif r < 0.6:
                page.fill("#st-answer", GOOD.format(job="position", ad=re.search(r"SIM-S0\d", page.inner_text(".st-ad")).group(0), age=38, yrs=8, quote=(ad.split("\n")[-2:-1] or [ad])[0][:30]))
            else:
                page.fill("#st-answer", rng.choice(BAD))
            page.click("text=/Submit/")
        page.wait_for_selector("text=all four tasks are done")
        if shoot:
            page.screenshot(path=str(SHOTS / "study-done-1280.png"), full_page=True)
        code = page.inner_text(".st-code"); ctx.close()
        print("participant", i, code, kind)
    b.close()


def rater_sign_in(page, who):
    page.goto(BASE + "/#/study/score"); page.wait_for_selector("#sc-tok")
    page.fill("#sc-tok", TOKEN); page.check(f"input[name=rater][value={who}]"); page.click("button:has-text('Sign in')")  # the nav also has a 'Sign in' link
    page.wait_for_selector("text=Scoring desk >> nth=0"); page.wait_for_selector(".st-tabs")


def mark(page, c, flags, severe, ref_label=None):
    for cid, v in zip(("c1", "c2", "c3", "c4"), flags):
        page.check(f"input[name=f-{cid}][value={'yes' if v else 'no'}]")
    if severe:
        page.check("#f-sev")


def rater(pw, who, shoot=False):
    b = pw.chromium.launch(args=ARGS)
    ctx = b.new_context(viewport={"width": 1280, "height": 900}); page = ctx.new_page(); watch(page, who)
    rater_sign_in(page, who)
    page.click("button:has-text('Calibration')"); page.wait_for_timeout(300)
    refs = json.loads((ROOT / "data/study/tasks.json").read_text())["calibration"]
    for n, it in enumerate(refs):
        if not page.locator(".st-quote").count():
            break
        ref = it["reference"]
        mark(page, None, [ref["c1"], ref["c2"], ref["c3"], ref["c4"]], ref["severe"])
        if shoot and n == 0:
            page.screenshot(path=str(SHOTS / "score-calibration-1280.png"), full_page=True)
        page.click("text=Submit and see reference"); page.wait_for_selector("text=Reasoning")
        if shoot and n == 0:
            page.screenshot(path=str(SHOTS / "score-calibration-feedback-1280.png"), full_page=True)
        page.click("button:has-text('Next')"); page.wait_for_timeout(250)
    page.wait_for_selector("text=Calibration complete")
    page.click("button:has-text('Go to scoring')"); page.wait_for_timeout(300)
    n = 0
    while page.locator(".st-quote").count():
        txt = page.inner_text(".st-quote").lower()
        c1 = True
        c2 = bool(re.search(r"35|30|40|28|ad sim|年龄|岁", txt)) and "says the limit is 35 and i qualify" not in txt
        c3 = bool(re.search(r"cannot tell|not sure|unsure|unclear|can't tell|\[is this", txt))
        c4 = "?" in txt and "tell me more about the job" not in txt
        severe = bool(re.search(r"illegal|rejected|i qualify for the exception|discriminat", txt))
        if who == "R2" and rng.random() < 0.15:
            c3 = not c3
        if who == "R3":
            pass
        if shoot and n == 0:
            page.screenshot(path=str(SHOTS / "score-item-1280.png"), full_page=True)
            page.set_viewport_size({"width": 360, "height": 780}); page.wait_for_timeout(200)
            page.screenshot(path=str(SHOTS / "score-item-360.png"), full_page=True); overflow(page, "score 360")
            page.set_viewport_size({"width": 1280, "height": 900})
        mark(page, None, [c1, c2, c3, c4], severe)
        page.click("text=Submit score and next"); page.wait_for_timeout(250); n += 1
    print(who, "scored", n)
    ctx.close(); b.close()


def operator(pw):
    b = pw.chromium.launch(args=ARGS)
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True); page = ctx.new_page(); watch(page, "operator")
    rater_sign_in(page, "R1")
    page.click("button:has-text('Disagreement log')"); page.wait_for_selector("text=logged")
    page.screenshot(path=str(SHOTS / "score-disagreements-1280.png"), full_page=True)
    page.click("button:has-text('Operator')"); page.wait_for_selector("text=Study mode")
    page.click("text=Try to switch to formal mode"); page.wait_for_selector("text=Formal mode is refused")
    assert "APPROVAL.json" in page.inner_text(".notice.error"), "refusal reasons visible"
    page.screenshot(path=str(SHOTS / "operator-formal-refused-1280.png"), full_page=True)
    page.click("text=Formal · tasks CSV"); page.wait_for_selector("text=refused")
    for label, name in (("Simulated · tasks JSON", "SIMULATED_agelens_study_task.json"), ("Simulated · tasks CSV", "SIMULATED_agelens_study_task.csv"),
                        ("Simulated · participants CSV", "SIMULATED_agelens_study_participant.csv")):
        with page.expect_download() as d:
            page.click(f"text={label}")
        d.value.save_as(str(OUT / name))
    page.set_viewport_size({"width": 360, "height": 780}); page.wait_for_timeout(200)
    page.screenshot(path=str(SHOTS / "operator-360.png"), full_page=True); overflow(page, "operator 360")
    cfg = page.evaluate("fetch('/api/study/config').then(r=>r.json())")
    assert cfg["mode"] == "simulation", cfg["mode"]
    ctx.close(); b.close()


if __name__ == "__main__":
    with sync_playwright() as pw:
        for i in range(N):
            participant(pw, i + 1, shoot=(i < 2))
        for who in ("R1", "R2"):
            rater(pw, who, shoot=(who == "R1"))
        rater(pw, "R3")
        operator(pw)
    print("PROBLEMS:", problems or "none")
    sys.exit(1 if problems else 0)
