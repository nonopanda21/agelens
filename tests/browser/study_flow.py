"""Real-browser rehearsal of the study tools, design crossover-ai-v1 (fixed template vs contextual AI, identical evidence), against a
SIMULATION-mode server on a DB COPY (default http://127.0.0.1:8866).  EVERYTHING HERE IS SIMULATED:
  * No AI model is connected or called. The 'contextual AI' tool text is written by a script (SimulatedAiDrafter).
  * The scripted participants write readings/questions from fixed sentences, choosing each key-fact sentence with probability
    P_FACT_A (template tool) or P_FACT_B (contextual tool), and add an unsupported claim with probability P_BAD_A / P_BAD_B.
    That built-in difference is an ASSUMPTION used to exercise the analysis. It is not evidence about any AI.
  * Scripted raters apply the same sentence table, with 12% noise on R2.
Usage: PW=<playwright python> $PW tests/browser/study_flow.py [base_url] [n_participants]
Env: STUDY_TOKEN (the server's AGELENS_STUDY_TOKEN), STUDY_OUT (export dir), STUDY_SEED, P_FACT_A/B, P_BAD_A/B, STUDY_SHOTS (screenshot dir)."""
import json, os, random, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8866"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 6
TOKEN = os.environ.get("STUDY_TOKEN", "demo-study-token")
ROOT = Path(__file__).resolve().parents[2]
SHOTS = Path(os.environ.get("STUDY_SHOTS", ROOT / "docs/screenshots/study"))
OUT = Path(os.environ.get("STUDY_OUT", ROOT / "data/study/simulated_example"))
SHOTS.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(int(os.environ.get("STUDY_SEED", "4242")))
P_FACT = {"template": float(os.environ.get("P_FACT_A", "0.60")), "ai": float(os.environ.get("P_FACT_B", "0.70"))}
P_BAD = {"template": float(os.environ.get("P_BAD_A", "0.25")), "ai": float(os.environ.get("P_BAD_B", "0.20"))}
CJK = re.compile(r"[㐀-鿿＀-￯]")
problems = []
ARGS = ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"]

FACTS = {
    "SIM-S01": ["The ad sets an age limit of 35.", "The ad states no exception to the limit.", "The ad does not say whether the limit is strict for this vacancy."],
    "SIM-S02": ["The usual age limit is 35.", "The limit may be relaxed to 40 with an intermediate title or 8+ years of relevant industry experience.",
                "The ad does not say whether 9 years in e-commerce operations count as relevant experience.", "The ad does not say how the relaxation is decided or checked."],
    "SIM-S03": ["Under 30 is a preference, not a stated limit.", "The ad states no maximum age.", "The ad does not say how much weight the preference carries or whether people over 30 are considered."],
    "SIM-S04": ["The age line is cut off at 28-3, so the full requirement cannot be read.", "It is unknown whether the wording is a requirement, a preference or has exceptions.", "No upper age limit can be assumed."],
}
GOODQ = {"SIM-S01": "I am 38 with eight years in procurement. The ad lists age 35 or under. Is this limit applied strictly for this vacancy?",
         "SIM-S02": "I am 38 with nine years in e-commerce operations. Do my nine years count as relevant industry experience for the relaxation to 40?",
         "SIM-S03": "I am 41 with twelve years in administration. How much weight does the preference for under 30 carry, and are older applicants reviewed?",
         "SIM-S04": "I am 36 with ten years in customer service. Could you send the complete age line and say if it is a requirement or a preference?"}
BADQ = ["Please confirm that I qualify and will be considered.", "Can you tell me more about the job?"]
UNSUP = ["I definitely qualify for the exception.", "This ad is illegal.", "Nobody over 35 is accepted."]


def watch(page, tag):
    page.on("console", lambda m: m.type == "error" and "403 (Forbidden)" not in m.text and problems.append(f"{tag} console: {m.text}"))
    page.on("pageerror", lambda e: problems.append(f"{tag} pageerror: {e}"))


def overflow(page, tag):
    w = page.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    if w[0] > w[1]:
        problems.append(f"{tag}: horizontal overflow {w}")


def nocjk(page, tag):
    t = page.inner_text("body")
    if CJK.search(t):
        problems.append(f"{tag}: CJK on screen: {CJK.search(t).group(0)}")


def participant(pw, i, shoot=False):
    b = pw.chromium.launch(args=ARGS)
    ctx = b.new_context(viewport={"width": 1280, "height": 900}); page = ctx.new_page(); watch(page, f"p{i}")
    page.goto(BASE + "/#/study"); page.wait_for_selector("text=Information and consent")
    banner = page.inner_text(".st-banner")
    if "SIMULATED" not in banner or "No AI model was used" not in banner:
        problems.append("intro banner lacks the SIMULATED / no-AI notice: " + banner)
    if shoot:
        page.screenshot(path=str(SHOTS / "ai-intro-1280.png"), full_page=True)
    page.focus("#st-agree"); page.keyboard.press("Space")
    page.keyboard.press("Tab"); assert page.evaluate("document.activeElement.textContent") == "Begin", "keyboard focus order"
    page.keyboard.press("Enter")
    for k in range(4):
        page.wait_for_selector("#st-reading"); page.wait_for_timeout(150)
        nocjk(page, f"p{i} task{k}")
        if "SIMULATED" not in page.inner_text(".st-banner") or "SIMULATED" not in page.inner_text(".st-aid"):
            problems.append("task screen lacks the SIMULATED notice")
        label = page.inner_text(".st-aid h2")
        arm = "template" if page.locator("text=Checklist to confirm with the employer").count() else "ai"   # what a participant can see; used only to pick the scripted quality
        ad = re.search(r"SIM-S0\d", page.inner_text(".st-ad")).group(0)
        if shoot and k == 0:
            page.screenshot(path=str(SHOTS / "ai-task-1280.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 800}); page.wait_for_timeout(200)
            page.screenshot(path=str(SHOTS / "ai-task-390.png"), full_page=True); overflow(page, "task 390")
            page.set_viewport_size({"width": 1280, "height": 900})
        sents = [f for f in FACTS[ad] if rng.random() < P_FACT[arm]]
        bad = rng.random() < P_BAD[arm]
        if bad:
            sents.append(rng.choice(UNSUP))
        if rng.random() < 0.3 and page.locator("text=Use the tool's draft as my starting point").count():
            page.once("dialog", lambda d: d.accept()); page.click("text=Use the tool's draft as my starting point")
            page.fill("#st-reading", page.input_value("#st-reading") + " " + " ".join(sents))
        else:
            page.fill("#st-reading", " ".join(sents))
        page.fill("#st-question", GOODQ[ad] if rng.random() < (0.55 if arm == "template" else 0.7) else rng.choice(BADQ))
        page.click("text=/Submit/")
    page.wait_for_selector("text=all four tasks are done")
    rev = page.inner_text("main") if page.locator("main").count() else page.inner_text("body")
    if "Which tool was which" not in rev or "SIMULATED" not in rev:
        problems.append("completion screen did not reveal the tools with the SIMULATED note")
    if shoot:
        page.screenshot(path=str(SHOTS / "ai-done-1280.png"), full_page=True)
    code = page.inner_text(".st-code"); ctx.close(); b.close()
    print("participant", i, code)


def rater_sign_in(page, who):
    page.goto(BASE + "/#/study/score"); page.wait_for_selector("#sc-tok")
    page.fill("#sc-tok", TOKEN); page.check(f"input[name=rater][value={who}]"); page.click("button:has-text('Sign in')")
    page.wait_for_selector("text=Scoring desk >> nth=0"); page.wait_for_selector(".st-tabs")


def mark(page, facts, qs, unsup):
    for fid, v in facts.items():
        page.check(f"input[name=f-{fid}][value={'yes' if v else 'no'}]")
    for q, v in qs.items():
        page.check(f"input[name=f-{q}][value={'yes' if v else 'no'}]")
    page.fill("#f-unsup", str(unsup))


def judge(text_r, text_q, ad, who):
    facts = {f"F{i + 1}": (s.lower() in text_r.lower()) for i, s in enumerate(FACTS[ad])}
    if who == "R2":
        for k in facts:
            if rng.random() < 0.12:
                facts[k] = not facts[k]
    if text_q == GOODQ[ad]:
        qs = {"q1": True, "q2": True, "q3": True, "q4": True}
    elif text_q == BADQ[0]:
        qs = {"q1": False, "q2": True, "q3": True, "q4": False}
    else:
        qs = {"q1": False, "q2": False, "q3": True, "q4": True}
    unsup = sum(1 for u in UNSUP if u in text_r) + (1 if text_q == BADQ[0] else 0)
    if who == "R2" and rng.random() < 0.1:
        unsup += 1
    return facts, qs, unsup


def rater(pw, who, shoot=False):
    b = pw.chromium.launch(args=ARGS)
    ctx = b.new_context(viewport={"width": 1280, "height": 900}); page = ctx.new_page(); watch(page, who)
    rater_sign_in(page, who)
    doc = json.loads((ROOT / "data/study/tasks.json").read_text())
    page.click("button:has-text('Calibration')"); page.wait_for_timeout(300)
    for n, it in enumerate(doc["calibration_ai"]):
        if not page.locator(".st-quote").count():
            break
        ref = it["reference"]
        mark(page, {k: bool(v) for k, v in ref["facts"].items()}, {k: bool(v) for k, v in ref["q"].items()}, ref["unsupported"])
        if shoot and n == 0:
            page.screenshot(path=str(SHOTS / "ai-score-calibration-1280.png"), full_page=True)
        page.click("text=Submit and see reference"); page.wait_for_selector("text=Reasoning")
        page.click("button:has-text('Next')"); page.wait_for_timeout(250)
    page.wait_for_selector("text=Calibration complete")
    page.click("button:has-text('Go to scoring')"); page.wait_for_timeout(300)
    n = 0
    while page.locator(".st-quote").count():
        qs_ = page.locator(".st-quote"); text_r, text_q = qs_.nth(0).inner_text(), qs_.nth(1).inner_text()
        nocjk(page, f"{who} item")
        body_txt = page.inner_text("body")
        for leak in ("Tool A", "Tool B", "ai_contextual", "Fixed template", "Contextual AI", "Checklist to confirm"):
            if leak in body_txt:
                problems.append(f"rater screen leaks '{leak}'")
        ad = re.search(r"SIM-S0\d", page.inner_text(".st-ad")).group(0)
        if shoot and n == 0:
            page.screenshot(path=str(SHOTS / "ai-score-item-1280.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 800}); page.wait_for_timeout(200)
            page.screenshot(path=str(SHOTS / "ai-score-item-390.png"), full_page=True); overflow(page, "score 390")
            page.set_viewport_size({"width": 1280, "height": 900})
        mark(page, *judge(text_r, text_q, ad, who))
        page.click("text=Submit score and next"); page.wait_for_timeout(250); n += 1
    print(who, "scored", n)
    ctx.close(); b.close()


def operator(pw):
    b = pw.chromium.launch(args=ARGS)
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True); page = ctx.new_page(); watch(page, "operator")
    rater_sign_in(page, "R1")
    page.click("button:has-text('Disagreement log')"); page.wait_for_selector("text=logged")
    page.click("button:has-text('Operator')"); page.wait_for_selector("text=Study mode")
    page.click("text=Try to switch to formal mode"); page.wait_for_selector("text=Formal mode is refused")
    refusal = page.inner_text(".notice.error")
    if "APPROVAL.json" not in refusal or "No AI model is connected" not in refusal:
        problems.append("formal refusal must name both the approval file and the missing AI model: " + refusal)
    page.screenshot(path=str(SHOTS / "ai-operator-formal-refused-1280.png"), full_page=True)
    page.click("text=Formal · tasks CSV"); page.wait_for_selector("text=refused")
    for label, name in (("Simulated · tasks JSON", "SIMULATED_agelens_study_task.json"), ("Simulated · tasks CSV", "SIMULATED_agelens_study_task.csv"),
                        ("Simulated · participants CSV", "SIMULATED_agelens_study_participant.csv")):
        with page.expect_download() as d:
            page.click(f"text={label}")
        d.value.save_as(str(OUT / name))
    cfg = page.evaluate("fetch('/api/study/config').then(r=>r.json())")
    assert cfg["mode"] == "simulation" and cfg["design"] == "crossover-ai-v1", cfg
    ctx.close(); b.close()


if __name__ == "__main__":
    with sync_playwright() as pw:
        for i in range(N):
            participant(pw, i + 1, shoot=(i == 0))
        for who in ("R1", "R2"):
            rater(pw, who, shoot=(who == "R1"))
        rater(pw, "R3")
        operator(pw)
    print("PROBLEMS:", problems or "none")
    sys.exit(1 if problems else 0)
