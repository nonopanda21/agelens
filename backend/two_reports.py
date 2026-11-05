"""Two reports on one pasted ad, from the same rules evidence, for the two buttons on the answer page.
'template' : a fixed form filled in mechanically from the evidence (same wording as arm 'template' in docs/EVAL_PLAN.md, no ad id).
             It does not use the person's background and makes no model call.
'ai'       : the checked model statements already in this brief, so no second paid call. Absent, it says why; nothing stands in for it.
These are examples of what each tool writes, not study data."""
import base64

from . import brief, gloss, real_context, report_pdf, study_arms

_KIND = {"cap_with_exception": "an age limit with an exception", "hard_cap": "a fixed age limit", "range_or_min": "an age range or minimum",
         "preference": "an age preference", "ambiguous": "age wording the rules could not read as a limit", "none": "no age wording"}
SHARED_NOTE = "Both reports start from the same evidence, read by the AgeLens rules; the AI report also adds counts from real recruitment data. This explains wording. It does not decide anything about you, and it is not legal advice."


def _rules_items(b, key):
    return [s for s in b["answer"].get(key) or [] if s.get("source") != "model"]


def evidence(b):
    """The shared evidence: what the rules found, in English."""
    out = []
    for key in ("explicit", "exceptions"):
        for s in _rules_items(b, key):
            q = s.get("quote_en") if s.get("quote") else None
            out.append(brief._en((s.get("text_en") or s["text"]) + (' [ad text: "%s"]' % q if q else "")))
    return out


def _wording(b):
    p = b.get("pasted") or {}
    for s in _rules_items(b, "explicit"):
        if s.get("quote") and s.get("quote_en"):
            return s["quote_en"]
    return ((p.get("conflict_en") or []) + (p.get("truncated_en") or []) + [None])[0]


def template_report(b):
    p = b.get("pasted") or {}
    w = brief._en(_wording(b) or "")
    exc = next((s.get("quote_en") for s in _rules_items(b, "exceptions") if s.get("quote") and s.get("quote_en") and "exception wording" in (s.get("text_en") or s["text"])), None)
    both = " and ".join('"%s"' % brief._en(x) for x in p.get("conflict_en") or [])
    kind = "age wording that contradicts itself" if p.get("conflict") else "cut-off age wording" if p.get("truncated") else _KIND.get(p.get("age_class"), "age wording of an unclear type")
    if not w:
        reading = "The rules found no age wording in this text. They can miss phrasing, so check the ad itself."
        question = "Hello, I am writing about this role. Does it have any age requirement? Please confirm, and tell me what information you would need from me."
    elif both:
        reading = "The ad's age wording contradicts itself: %s. The rules do not choose between them." % both
        question = "Hello, I am writing about this role. The ad says %s. Which of these applies to this role, and what information would you need from me?" % both
    elif p.get("age_class") == "ambiguous" or w.startswith("Age wording"):  # the gloss describes wording it could not translate; it is not a quote
        reading = ("The age wording is cut off, so no limit can be read from it. Ask for the full ad." if p.get("truncated")
                   else "The rules found age wording they could not read as a limit, so check the ad itself.")
        question = "Hello, I am writing about this role. Could you send the complete age requirement, and confirm whether it is a requirement or a preference?"
    elif p.get("age_class") == "none":  # the only wording found says there is no limit
        reading = 'The ad says: "%s". The rules read this as saying there is no age limit.' % w
        question = 'Hello, I am writing about this role. The ad says: "%s". Is age considered at any stage for this role, and what information would you need from me?' % w
    else:
        what = 'the exception ("%s")' % brief._en(exc) if exc else "any exception"
        w = w.split(";")[0] if exc else w  # the exception is quoted on its own; its condition may have been left out of the joined line
        reading = 'The ad says: "%s". The rules read this as %s.' % (w, kind)
        question = ('Hello, I am writing about this role. The ad says: "%s". Does %s apply to this role? '
                    "Please confirm whether the wording is a requirement or a preference, and what information you would need from me." % (w, what))
    return {"kind": "template", "title": "Fixed template report", "available": True, "written_by": "A fixed form filled in by rules. No AI. It does not use your background.",
            "reading": reading, "stated": [], "related": [], "unclear": [], "checklist": list(study_arms.CHECKLIST), "question": question}


def _about(b):
    """What the person shared, in their own terms, so they can see what the report rests on. Only what they gave; never Chinese on this page."""
    qb = b.get("question_background") or {}
    p = qb.get("profile") or {}
    bits = ["you are %d" % p["age"] if p.get("age") is not None else None,
            "you have %s of experience" % ("1 year" if p.get("years_experience") == 1 else "%s years" % p["years_experience"]) if p.get("years_experience") is not None else None,
            "your role is %s" % p["occupation"] if p.get("occupation") and not gloss.has_cjk(p["occupation"]) else None,
            "you are looking in %s" % gloss.province_en(p["region"]) if p.get("region") else None]
    bits = [x for x in bits if x]
    q = qb.get("question") or ""
    out = ["You told us " + (", ".join(bits[:-1]) + " and " + bits[-1] if len(bits) > 1 else bits[0]) + "."] if bits else [
        "You did not share your age or experience, so this report stays general. Add them above if you want a closer reading."]
    if q and not qb.get("question_default") and not gloss.has_cjk(q):
        out.append("You asked: " + q)
    return out


def ai_report(b, ad_text=None):
    base = {"kind": "ai", "title": "AI report", "written_by": "An AI model, then checked by code. The check catches listed failures, not every misleading sentence."}
    if b.get("ai_status") != "used":
        return dict(base, available=False, reason=(b.get("ai_note") or "No AI model is connected, so there is no AI report."))
    by = {}
    for key in ("explicit", "exceptions", "relates", "cannot", "ask"):
        by[key] = [brief._en(s.get("text_en") or s["text"]) for s in b["answer"].get(key) or [] if s.get("source") == "model"]
    if not any(by.values()):
        return dict(base, available=False, reason="No statement from the AI model passed the code check, so there is no AI report for this ad.")
    removed = len(((b.get("ai_report") or {}).get("dropped")) or [])
    return dict(base, available=True, reading="", stated=by["explicit"] + by["exceptions"], related=by["relates"], unclear=by["cannot"], checklist=[],
                question=by["ask"][0] if by["ask"] else None, removed=removed, reading_check=b.get("reading_check"), about=_about(b),
                context=real_context.build(ad_text, (b.get("question_background") or {}).get("profile"), (b.get("pasted") or {}).get("age_class"),
                                           bool(_rules_exception(b))))


def _rules_exception(b):
    return [s for s in _rules_items(b, "exceptions") if s.get("quote") and "exception wording" in (s.get("text_en") or s["text"])]


def _markdown(r, ev, label):
    L = ["# AgeLens: %s" % r["title"], "", "**%s.** %s" % (label, r["written_by"]), "", SHARED_NOTE, ""]
    rc = r.get("reading_check")
    if rc and rc["status"] in ("differ", "ai_only"):
        L += ["> **%s**" % rc["title"]] + ["> %s" % x for x in rc["lines"]] + (["> %s" % rc["note"]] if rc.get("note") else []) + [""]
    if r.get("about"):
        L += ["## What you told us", ""] + [x + "\n" for x in r["about"]]
    if r.get("reading"):
        L += ["## Reading", "", r["reading"], ""]
    for title, key in (("What the ad states", "stated"), ("How it relates to you", "related"), ("What the ad leaves open", "unclear"), ("Checklist", "checklist")):
        if r.get(key):
            L += ["## " + title, ""] + ["- " + x for x in r[key]] + [""]
    ctx = r.get("context")
    if ctx:
        L += ["## What real recruitment data shows", ""] + ["- " + x for x in ctx["facts"]] + ["", "## Suggestions", ""] + ["- " + x for x in ctx["suggestions"]] + ["", ctx["note"], ""]
    L += ["## Question for the employer", "", r.get("question") or "No question passed the code check.", ""]
    if r.get("removed"):
        L += ["The code check removed %d AI statement(s) from this report." % r["removed"], ""]
    L += ["## Evidence from the rules (the same in both reports)", ""] + (["- " + x for x in ev] or ["- The rules found no age wording."]) + [""]
    return "\n".join(L)


def build(b, ad_text=None, rules_only=None):
    """rules_only: the brief before any model reading. The template report and the shared evidence come from it, so "No AI" stays true."""
    base = rules_only or b
    ev = evidence(base)
    out = {"note": SHARED_NOTE, "evidence": ev}
    for name, r in (("template", template_report(base)), ("ai", ai_report(b, ad_text))):
        if r["available"]:
            r["markdown"] = _markdown(r, ev, b.get("data_label") or "")
            r["filename"] = "agelens-%s-report.md" % name
            r["pdf"] = base64.b64encode(report_pdf.build(r["markdown"])).decode("ascii")  # built per answer, never stored
            r["pdf_filename"] = "agelens-%s-report.pdf" % name
        out[name] = r
    return out
