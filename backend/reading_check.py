"""The AI normalises one pasted ad's age wording behind the rules. What the rules read stands; a checked reading can only fill a gap they
left (no reading, or a missed exception). If the two conflict, both are shown and neither is chosen.
The model's reading is used only after code checks it: its quotes must occur word for word in the ad, outside any instruction-like
sentence, and its ages must be written in that quote. Everything shown is fixed wording plus those checked values, and an English quote.
If the rules and the AI make the same mistake, this cannot see it."""
import re

from . import ageparse, ageparse_en, gloss, llm

KINDS = ("max", "min", "range", "preference", "no_limit", "none", "unclear")
READ_BY = "model-reading-checked"  # marks a term in the answer's provenance; it never reaches the published counts
NOTE = "AgeLens does not choose between them. Read the original line yourself and ask the employer."


def _age(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and 14 <= v <= 80 else None


def _sentence_of(quote, text):
    i = text.find(quote)
    start = max(text.rfind(c, 0, i) for c in ".。;；!！?？\n") + 1
    return text[start:].lstrip()


def _usable_quote(q, text):
    """The quote if it is the ad's own words and not part of an instruction to a reader or a system."""
    if not isinstance(q, str) or not 2 <= len(q.strip()) <= 200:
        return None
    q = q.strip()
    if q not in text or llm.INSTRUCTION.search(q) or llm._quotes_instruction([q], {"original_text": text}):
        return None
    return None if ageparse_en.DICTATES.search(_sentence_of(q, text)) else q


def check(raw, text):
    """-> the checked reading {"kind","min_age","max_age","quote","exception_quote"}, or None if it fails any check."""
    if not isinstance(raw, dict) or raw.get("kind") not in KINDS:
        return None
    kind, lo, hi = raw["kind"], _age(raw.get("min_age")), _age(raw.get("max_age"))
    quote, exc = _usable_quote(raw.get("quote"), text), _usable_quote(raw.get("exception_quote"), text)
    if kind in ("max", "min", "range", "preference", "no_limit") and not quote:
        return None
    if kind == "no_limit" or kind in ("none", "unclear"):
        lo = hi = None
    elif (kind == "max" and hi is None) or (kind == "min" and lo is None) or (kind == "range" and (lo is None or hi is None or lo >= hi)) or (kind == "preference" and lo is None and hi is None):
        return None
    if kind == "max":
        lo = None
    elif kind == "min":
        hi = None
    if any(a is not None and str(a) not in quote for a in (lo, hi)):
        return None
    return {"kind": kind, "min_age": lo, "max_age": hi, "quote": quote, "exception_quote": exc}


def _rule_readings(terms):
    out = set()
    for t in terms:
        k, lo, hi = t.get("kind"), t.get("min_age"), t.get("max_age")
        if "unlimited" in (t.get("flag") or ""):
            out.add(("no_limit", None, None))
        elif k in ("max", "min", "range", "preference"):
            out.add((k, lo, hi))
    return out


def _say(kind, lo, hi):
    return {"max": lambda: "a maximum age of %s" % hi, "min": lambda: "a minimum age of %s" % lo, "range": lambda: "an age range of %s to %s" % (lo, hi),
            "preference": lambda: "an age preference, not a requirement (%s)" % ("%s to %s" % (lo, hi) if lo and hi else "up to %s" % hi if hi else "%s or over" % lo),
            "no_limit": lambda: "no age limit", "none": lambda: "no age wording", "unclear": lambda: "age wording it could not read with confidence"}[kind]()


def _english(q):
    return q if q and not gloss.has_cjk(q) else None


def compare(raw, text, terms):
    """-> {"status", "checked", "title", "lines", "note"}, or None when the model gave no reading.
    status: agree (nothing to show); fills_gap (the rules read nothing, or missed an exception: the checked reading is used);
    differ (two readings, shown side by side); unchecked (it failed the check, so only the rules count)."""
    if raw is None:
        return None
    ai = check(raw, text)
    quiet = {"title": None, "lines": [], "note": None}
    if not ai:
        return dict(quiet, status="unchecked", checked=None)
    rules = _rule_readings(terms)
    mine = (ai["kind"], ai["min_age"], ai["max_age"])
    if mine in rules or (ai["kind"] == "preference" and ("preference", None, ai["max_age"]) in rules):
        same = True
    elif ai["kind"] == "range":
        same = {("min", ai["min_age"], None), ("max", None, ai["max_age"])} <= rules
    elif rules:
        same = False
    else:
        same = ai["kind"] in ("none", "unclear")
    has_rule_exc = any(t.get("exception_text") or (t.get("kind") == "relaxable" and "unlimited" not in (t.get("flag") or "")) for t in terms)
    if same:
        return dict(quiet, status="fills_gap" if ai["exception_quote"] and not has_rule_exc and rules else "agree", checked=ai)
    if not rules:
        return dict(quiet, status="fills_gap", checked=ai)
    q = _english(ai["quote"])
    return {"status": "differ", "checked": ai, "title": "This wording can be read more than one way.",
            "lines": ["One reading: %s." % "; ".join(_say(*r) for r in sorted(rules, key=str)), "Another reading: %s%s." % (_say(*mine), ' ("%s")' % q if q else "")], "note": NOTE}


def filled_terms(rc, terms, text):
    """The rules' terms with a checked reading filling the gap, or None when there is nothing to fill. Rule terms are never overridden."""
    if not rc or rc["status"] != "fills_gap":
        return None
    ai = rc["checked"]
    if _rule_readings(terms):  # a limit the rules read, plus the exception they missed
        out = [dict(t) for t in terms]
        for t in out:
            if t.get("kind") in ("max", "range", "min"):
                t["exception_text"] = ai["exception_quote"]
                t["flag"] = ",".join(x for x in (t.get("flag"), "ai_read") if x)
                return out
        return None
    i = text.find(ai["quote"])
    kind = {"no_limit": "relaxable"}.get(ai["kind"], ai["kind"])
    new = {"kind": kind, "min_age": ai["min_age"], "max_age": ai["max_age"], "confidence": "high", "exception_text": ai["exception_quote"], "snippet": ai["quote"],
           "flag": "unlimited,ai_read" if ai["kind"] == "no_limit" else "ai_read", "start_offset": i, "end_offset": i + len(ai["quote"]), "rule_version": READ_BY}
    return ageparse._finalize([t for t in terms if t.get("kind") != "ambiguous"] + [new])
