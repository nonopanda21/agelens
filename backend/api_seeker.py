"""Seeker endpoints: CV parsing (in memory only), rules-based Evidence brief, pasted-ad check, AI status.
Never logs bodies, CV text, pasted ad text or questions (the server logger records method + path only)."""
import re
import unicodedata

from . import ageparse, brief, cv, llm
from .server import HTTPError, Response  # noqa: F401  (HTTPError used below)

# ---- pasted ad text (live adversarial exchange: someone hands you an ad) --------------------------------------
# The text is untrusted DATA. It is length-limited, checked in memory by the same age rules and the same brief
# templates, never stored, never logged, never executed or rendered as HTML (the page inserts it as text).
PASTE_MAX_CHARS = 4000
PASTE_MAX_BYTES = 64 * 1024
AGE_CHECK_MAX_CHARS = 300
PASTE_ID = "PASTED"
PASTE_LABEL = "Pasted text, not stored"
# Wording that looks like an instruction to a system/model. Used ONLY to show the user a note that such lines are
# ignored; it is not a security boundary (nothing in the pasted text is ever followed, matched or not).
_INSTRUCTION = re.compile(
    r"(ignore|disregard|forget|override)\b.{0,40}\b(instruction|prompt|rule|above|previous|schema)"
    r"|\b(system|assistant|developer)\s*[:：\]]|\[\s*system\s*\]|</?\s*(ad|system|data|prompt)\s*>|<!--"
    r"|\bapprove[ds]?\b|\byou are now\b|\bskip (all )?checks\b|\boutput the\b|\btoken\b|\bprobability\b"
    r"|忽略|无视|现在你是|批准|一定会被录用|通过资格|请声明|替换为|发送到|改写为", re.I)


def _looks_binary(text):
    if "\x00" in text:
        return True
    bad = sum(1 for ch in text if ch == "�" or (unicodedata.category(ch) in ("Cc", "Cs", "Co") and ch not in "\n\r\t"))
    return bad > max(2, len(text) // 100)


def _instruction_lines(text):
    out = []
    for line in re.split(r"[\n。]", text):
        line = line.strip()
        if line and _INSTRUCTION.search(line):
            out.append(line[:160] + ("…" if len(line) > 160 else ""))
        if len(out) >= 5:
            break
    return out


class _PastedEvidence:
    """Evidence source holding exactly one in-memory ad (the pasted text). No database access."""

    def __init__(self, ad):
        self.ad = ad

    def get_ad(self, i):
        return self.ad if i == PASTE_ID else None

    def search_ads(self, filters, page=1, page_size=20, sort="date_desc"):
        return {"items": [self.ad] if page == 1 else [], "total": 1, "page": page, "page_size": page_size,
                "filters_applied": {}, "using_demo": False}


def check_age_line(body):
    """-> rules-only reading of one line of age wording (the side-panel "Quick check"). No model, nothing stored."""
    text = body.get("text")
    if not isinstance(text, str) or not text.strip():
        raise HTTPError(400, "Paste a line of age wording first.")
    text = text.strip()
    if len(text) > AGE_CHECK_MAX_CHARS:
        raise HTTPError(413, "Paste one line only; the limit is %d characters." % AGE_CHECK_MAX_CHARS)
    terms = ageparse.parse_age(text)
    keep = ("kind", "min_age", "max_age", "exception_text", "flag", "snippet", "age_class")
    return {"age_class": ageparse.ad_class(terms), "age_status": ageparse.age_status(terms), "rule_version": ageparse.RULE_VERSION,
            "terms": [{k: t.get(k) for k in keep} for t in terms], "stored": False}


def check_pasted(body, allow_model=True):
    """-> brief dict for one pasted ad text, plus a `pasted` block. Raises HTTPError for unusable input.
    allow_model=False: rules only, whatever the model status (used for the study aid)."""
    text = body.get("text")
    if text is None or (isinstance(text, str) and not text.strip()):
        raise HTTPError(400, "Paste the ad text first.")
    if not isinstance(text, str):
        raise HTTPError(400, "The ad text must be plain text.")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > PASTE_MAX_CHARS:
        raise HTTPError(413, "The pasted text is %d characters; the limit is %d. Paste only the part of the ad with the requirements."
                        % (len(text), PASTE_MAX_CHARS))
    if _looks_binary(text):
        raise HTTPError(422, "This does not look like ad text (it contains binary or control characters). Copy the text of the ad itself.")
    if not str(body.get("question") or "").strip():
        raise HTTPError(400, "A question is required to build an Evidence brief.")
    terms = ageparse.parse_age(text)
    ad = {"id": PASTE_ID, "title": "Pasted ad text", "company": None, "occupation": None, "province": None, "city": None,
          "posted_date": None, "source": PASTE_LABEL, "is_demo": False, "description": text, "age_terms": terms,
          "age_status": ageparse.age_status(terms), "age_class": ageparse.ad_class(terms), "snippet_highlight": ""}
    b = brief.build_brief({"question": body.get("question"), "profile": body.get("profile"), "evidence_ids": [PASTE_ID]},
                          _PastedEvidence(ad), allow_model=allow_model)
    b["data_label"] = PASTE_LABEL
    b["using_demo"] = False
    b["scope"].update(basis="pasted text", data_version=None, stored=False)
    for st in b["answer"]["cannot"]:
        if st["text"].startswith("Only 1 ad matched"):
            st["text"] = "This answer covers only the one pasted ad. It says nothing about other ads or the job market."
    b["next_steps"] = [s for s in b["next_steps"] if "Broaden" not in s]
    trunc = [t["snippet"] for t in terms if "truncated" in (t.get("flag") or "")]
    conflict = [t["snippet"] for t in terms if "conflict" in (t.get("flag") or "")]
    b["pasted"] = {"label": PASTE_LABEL, "stored": False, "chars": len(text), "max_chars": PASTE_MAX_CHARS,
                   "age_status": ad["age_status"], "age_class": ad["age_class"], "rule_version": ageparse.RULE_VERSION,
                   "instruction_like": _instruction_lines(text), "truncated": trunc[:1],
                   "conflict": list(dict.fromkeys(conflict))[:3],
                   "note": "Instructions inside ads are ignored: the pasted text is read as data only, and nothing in it changes how AgeLens answers."}
    note = ["> **%s.** %s" % (PASTE_LABEL, b["pasted"]["note"])]
    if b["pasted"]["instruction_like"]:
        note.append("> Wording that looks like an instruction was found and NOT followed (quoted as text only): "
                    + "; ".join("`%s`" % x.replace("`", "'") for x in b["pasted"]["instruction_like"]))
    b["markdown"] = brief.to_markdown(b).replace("\n## ", "\n" + "\n".join(note) + "\n\n## ", 1)
    return b


def register(router):
    @router.post("/api/cv/parse")
    def cv_parse(req):
        data = req.body or b""
        name = req.headers.get("X-Filename", "")
        try:
            from urllib.parse import unquote
            name = unquote(name)
        except Exception:
            pass
        try:
            return cv.parse_cv(name[:200], data)
        except cv.CVError as e:
            return e.status, {"error": e.message, "reason": e.reason, "continue_manually": True}

    @router.post("/api/brief")
    def make_brief(req):
        body = req.json()
        if not str(body.get("question") or "").strip():
            raise HTTPError(400, "A question is required to build an Evidence brief.")
        try:
            return brief.build_brief(body)
        except ImportError:
            raise HTTPError(503, "The evidence search module is not available yet.")

    @router.post("/api/paste/check")
    def paste_check(req):
        if len(req.body or b"") > PASTE_MAX_BYTES:
            raise HTTPError(413, "The pasted text is too long; the limit is %d characters." % PASTE_MAX_CHARS)
        return check_pasted(req.json())

    @router.post("/api/age/check")
    def age_check(req):
        if len(req.body or b"") > 8 * 1024:
            raise HTTPError(413, "Paste one line only; the limit is %d characters." % AGE_CHECK_MAX_CHARS)
        return check_age_line(req.json() or {})

    @router.get("/api/ai/status")
    def ai_status(req):
        return llm.status()

    @router.get("/api/seeker/aliases")
    def aliases(req):
        return {"aliases": brief.ALIASES}
