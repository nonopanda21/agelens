"""Real-browser check of the seeker flow. Run with the Playwright python and a server on --base.
usage: PW_PY tests/browser/seeker_flow.py http://127.0.0.1:8804
Records observations (printed as JSON) - these are human-observation aids, separate from unit tests."""
import io, json, re, sys, time, zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8804"
OUT = Path(__file__).resolve().parents[2] / "docs" / "screenshots" / "seeker"
OUT.mkdir(parents=True, exist_ok=True)
CV = ("Operations Manager\nSummary\nOperations professional with eight years of experience in e-commerce logistics.\n"
      "Skills: Process improvement, SQL, Vendor management; Excel\nEducation\nBachelor of Business Administration\n").encode()
obs, errors = {}, []


def shot(page, name, full=True):
    page.screenshot(path=str(OUT / name), full_page=full)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def fresh(browser, w, h):
    ctx = browser.new_context(viewport={"width": w, "height": h}, accept_downloads=True)
    page = ctx.new_page()
    page.on("console", lambda m: errors.append((w, m.type, m.text)) if m.type in ("error",) else None)
    page.on("pageerror", lambda e: errors.append((w, "pageerror", str(e))))
    return ctx, page


with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
    # ---------- desktop ----------
    ctx, page = fresh(b, 1280, 900)
    page.goto(BASE + "/#/seeker"); page.wait_for_selector("#f-question")
    shot(page, "01_form_1280.png")
    obs["order_question_first"] = page.evaluate("(()=>{const q=document.getElementById('f-question'),o=document.getElementById('f-occupation'),d=document.getElementById('cv-drop');return q.compareDocumentPosition(o)&4 && o.compareDocumentPosition(d)&4})()")
    # empty question -> message, focus stays in question
    page.click("#go-btn"); obs["empty_question_msg"] = page.inner_text("#q-err"); obs["focus_after_empty"] = page.evaluate("document.activeElement.id")
    # keyboard-only completion
    page.focus("#f-question")
    page.keyboard.type("I am 38 with eight years in operations. Ads say normally under 35, exceptions possible. What should I clarify?")
    page.keyboard.press("Tab"); page.keyboard.press("Tab"); page.keyboard.type("Operations manager")   # first Tab = 'Use an example' button
    page.keyboard.press("Tab"); page.keyboard.type("38")
    page.keyboard.press("Tab"); page.keyboard.type("8")
    page.keyboard.press("Tab"); page.keyboard.press("ArrowDown")   # select: choose first region with the keyboard
    obs["region_via_keyboard"] = page.input_value("#f-region")
    page.focus("#go-btn"); page.keyboard.press("Enter")
    page.wait_for_selector(".answer-sec", timeout=20000)
    obs["answer_headings"] = page.eval_on_selector_all(".answer-sec h3", "els=>els.map(e=>e.textContent)")
    obs["focus_after_answer"] = page.evaluate("document.activeElement.tagName+':'+document.activeElement.textContent.slice(0,20)")
    obs["tags_seen"] = sorted(set(page.eval_on_selector_all(".tag", "els=>els.map(e=>e.textContent)")))
    obs["badges"] = page.eval_on_selector_all(".answer-head .badge", "els=>els.map(e=>e.textContent)")
    obs["quotes"] = page.eval_on_selector_all(".quote", "els=>els.length")
    shot(page, "02_answer_1280.png"); shot(page, "02b_answer_viewport_1280.png", full=False)
    # download markdown
    with page.expect_download() as dl:
        page.click("text=Download brief (Markdown)")
    p = Path(dl.value.path()); md = p.read_text(encoding="utf-8")
    obs["md_labels"] = [s for s in ("Demo · Synthetic data", "Template demo", "What does the ad explicitly say?", "[Ad text]", "[Rules]", "[You said]") if s in md]
    obs["md_has_data_version"] = "data version" in md
    obs["md_cjk_chars"] = len(re.findall(r"[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]", md))   # English-only brief (backend)
    obs["answer_cjk"] = len(re.findall(r"[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]", page.evaluate("document.body.innerText")))
    # print rendering
    page.emulate_media(media="print"); page.evaluate("document.body.classList.add('print-brief')")
    shot(page, "03_print_view_1280.png"); obs["print_hidden_nav"] = page.evaluate("getComputedStyle(document.querySelector('.nav')).display")
    page.evaluate("document.body.classList.remove('print-brief')"); page.emulate_media(media="screen")
    # evidence page via link
    page.click(".stmts a[href^='#/evidence/']"); page.wait_for_selector(".ev-sec")
    obs["evidence_cjk"] = len(re.findall(r"[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]", page.evaluate("document.body.innerText")))
    shot(page, "04_evidence_1280.png"); page.go_back(); page.wait_for_selector(".answer-sec")
    obs["state_kept_after_evidence"] = page.input_value("#f-question")[:20]

    # ---------- CV upload: file chooser + drag/drop + failures ----------
    page.goto(BASE + "/#/seeker"); page.wait_for_selector("#cv-drop")
    page.set_input_files("#cv-file", {"name": "cv.txt", "mimeType": "text/plain", "buffer": CV})
    page.wait_for_selector("#cv-review"); shot(page, "05_cv_review_1280.png")
    obs["cv_fields"] = {k: page.input_value("#cvx-" + k) for k in ("occupation", "years", "skills", "education")}
    page.fill("#cvx-occupation", "Operations lead (edited)")
    page.click("text=Confirm and use these")
    obs["cv_applied_occupation"] = page.input_value("#f-occupation")
    # drag & drop
    page.evaluate("""() => { const dt = new DataTransfer(); dt.items.add(new File(['Analyst\\nSkills: SQL, Excel\\nTen years of experience in analysis.'], 'dropped.txt', {type:'text/plain'}));
        const z = document.getElementById('cv-drop');
        z.dispatchEvent(new DragEvent('dragenter', {dataTransfer: dt, bubbles: true, cancelable: true}));
        z.dispatchEvent(new DragEvent('dragover', {dataTransfer: dt, bubbles: true, cancelable: true}));
        window.__over = z.classList.contains('over');
        z.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true})); }""")
    obs["drag_over_class"] = page.evaluate("window.__over")
    page.wait_for_selector("#cv-review"); obs["dropped_file_occupation"] = page.input_value("#cvx-occupation")
    shot(page, "06_cv_dropped_1280.png")
    # failure: corrupt docx -> manual entry
    page.set_input_files("#cv-file", {"name": "broken.docx", "mimeType": "application/octet-stream", "buffer": b"not a zip at all"})
    page.wait_for_selector("#cv-out .problem"); obs["cv_fail_text"] = page.inner_text("#cv-out .problem")[:160]
    shot(page, "07_cv_failure_1280.png")
    page.click("text=Enter it manually"); obs["manual_focus"] = page.evaluate("document.activeElement.id")
    # unsupported type + zip bomb
    page.set_input_files("#cv-file", {"name": "pic.png", "mimeType": "image/png", "buffer": b"\x89PNG"})
    page.wait_for_selector("#cv-out .problem"); obs["cv_unsupported"] = page.inner_text("#cv-out .problem p")
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "<a/>"); z.writestr("big.bin", b"\0" * (41 * 1024 * 1024))
    page.set_input_files("#cv-file", {"name": "bomb.docx", "mimeType": "application/octet-stream", "buffer": bio.getvalue()})
    page.wait_for_selector("#cv-out .problem"); obs["cv_bomb"] = page.inner_text("#cv-out .problem p")[:120]

    # ---------- empty result + broaden ----------
    page.goto(BASE + "/#/seeker"); page.wait_for_selector("#f-question")
    page.fill("#f-question", "Is there anything for a baker in Tibet?"); page.fill("#f-occupation", "baker"); page.select_option("#f-region", index=1)
    page.click("#adv summary"); page.fill("#f-term", "zzzz-no-such-title"); page.click("#go-btn"); page.wait_for_selector("#answer .problem.soft")
    obs["empty_state"] = page.inner_text("#answer .problem.soft")[:200]; shot(page, "08_empty_1280.png")
    page.click("text=Drop the occupation text"); page.wait_for_selector(".answer-sec, #answer .problem.soft", timeout=20000)
    obs["after_broaden"] = page.eval_on_selector_all(".answer-note", "els=>els.map(e=>e.textContent.slice(0,80))")[:2]

    # ---------- forced server error + retry ----------
    page.goto(BASE + "/#/seeker"); page.wait_for_selector("#f-question")
    page.fill("#f-question", "What should I ask about the age limit?"); page.fill("#f-occupation", "运营"); page.select_option("#f-region", "")
    page.route("**/api/brief", lambda r: r.fulfill(status=500, content_type="application/json", body='{"error":"Internal error."}'))
    page.click("#go-btn"); page.wait_for_selector("#answer .problem")
    obs["server_error"] = page.inner_text("#answer .problem")[:200]; shot(page, "09_server_error_1280.png")
    page.unroute("**/api/brief"); page.click("#answer .problem button:has-text(\"Try again\")")
    try: page.wait_for_selector(".answer-sec", timeout=15000)
    except Exception:
        shot(page, "zz_debug.png"); print("DEBUG", page.inner_text("#answer")[:600]); raise
    obs["retry_recovered"] = True
    page.route("**/api/brief", lambda r: r.fulfill(status=200, content_type="text/html", body="<html>oops</html>"))
    page.click("#go-btn"); page.wait_for_selector("#answer .problem"); obs["parse_failure"] = page.inner_text("#answer .problem h3")
    page.unroute("**/api/brief")
    page.route("**/api/ads?**", lambda r: r.abort())
    page.click("#go-btn"); page.wait_for_selector("#answer .problem"); obs["unreachable"] = page.inner_text("#answer .problem h3")
    page.unroute("**/api/ads?**")
    page.route("**/api/ads?**", lambda r: r.fulfill(status=401, content_type="application/json", body='{"error":"x"}'))
    page.click("#go-btn"); page.wait_for_selector("#answer .problem"); obs["session"] = page.inner_text("#answer .problem h3")
    page.unroute("**/api/ads?**")

    # ---------- duplicate submit with idempotency key ----------
    page.click("#go-btn"); page.wait_for_selector(".cards .card", timeout=20000)
    page.locator(".cards .card input[type=checkbox]").first.check()
    posts = []
    def on_req(route):
        if route.request.method == "POST":
            posts.append(route.request.headers.get("x-idempotency-key"))
            time.sleep(0.6)
        route.continue_()
    page.route("**/api/requests", on_req)
    page.wait_for_selector("#submit-btn")
    page.click("#submit-btn"); 
    try: page.click("#submit-btn", timeout=500)
    except Exception: pass
    obs["submit_disabled_in_flight"] = page.evaluate("document.getElementById('submit-btn') ? document.getElementById('submit-btn').disabled : 'replaced'")
    page.wait_for_selector("text=Request submitted", timeout=20000)
    obs["post_count"] = len(posts); obs["idempotency_key_sent"] = bool(posts and posts[0] and len(posts[0]) >= 16)
    shot(page, "10_submitted_1280.png")
    page.unroute("**/api/requests")
    # 409 path (mock): existing request number shown
    page.reload(); page.wait_for_selector("#f-question")
    page.fill("#f-question", "dup test"); page.click("#go-btn"); page.wait_for_selector(".cards .card", timeout=20000)
    page.locator(".cards .card input[type=checkbox]").first.check()
    page.route("**/api/requests", lambda r: r.fulfill(status=409, content_type="application/json", body='{"error":"Already submitted as AL-2026-0042","code":"AL-2026-0042"}'))
    page.click("#submit-btn"); page.wait_for_selector("text=AL-2026-0042")
    obs["duplicate_409"] = page.inner_text("#review")[:160]; shot(page, "11_duplicate_409_1280.png")
    obs["overflow_1280"] = overflow(page)
    ctx.close()

    # ---------- mobile 360 ----------
    ctx, page = fresh(b, 360, 740)
    page.goto(BASE + "/#/seeker"); page.wait_for_selector("#f-question"); shot(page, "20_form_360.png")
    obs["overflow_360_form"] = overflow(page)
    page.fill("#f-question", "I am 38 and the ad says under 35. What do I ask?"); page.fill("#f-occupation", "运营"); page.select_option("#f-region", label="Shanghai")
    page.click("#go-btn"); page.wait_for_selector(".answer-sec", timeout=20000)
    shot(page, "21_answer_360.png"); page.locator("#answer").scroll_into_view_if_needed(); page.evaluate("window.scrollBy(0,380)"); shot(page, "21b_answer_viewport_360.png", full=False); obs["overflow_360_answer"] = overflow(page)
    page.set_input_files("#cv-file", {"name": "cv.txt", "mimeType": "text/plain", "buffer": CV}); page.wait_for_selector("#cv-review")
    shot(page, "22_cv_review_360.png"); obs["overflow_360_cv"] = overflow(page)
    page.goto(BASE + "/#/seeker"); page.wait_for_selector("#f-question"); page.click("#go-btn")  # state persisted question
    first = page.evaluate("document.querySelector('.stmts a') ? 1 : 0")
    page.goto(BASE + "/#/evidence/nonexistent-id"); page.wait_for_selector(".evidence-page .problem"); shot(page, "23_evidence_missing_360.png")
    obs["evidence_missing"] = page.inner_text(".evidence-page .problem h3"); obs["overflow_360_evidence_missing"] = overflow(page)
    ctx.close(); b.close()

print(json.dumps(obs, ensure_ascii=False, indent=1))
js = [e for e in errors if e[1] == "pageerror" or "Failed to load resource" not in e[2]]
print("JS/PAGE ERRORS:", json.dumps(js, ensure_ascii=False))
print("HTTP-status console lines (from deliberately forced failures):", len(errors) - len(js))
