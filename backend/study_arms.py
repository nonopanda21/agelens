"""Aids shown to participants in the study.

Crossover design (crossover-rules-v1, the default; see docs/EVAL_PLAN.md), one condition per TASK:
kind 'none'    : condition A, the ad and background only (what a job seeker has today).
kind 'agelens' : condition B, the AgeLens evidence check for that ad: the same rules-only output the Job Seeker page shows
                 for a pasted ad (api_seeker.check_pasted with allow_model=False). Real product output, not simulated, and the
                 same whether or not a model is connected.

Legacy parallel design (parallel-llm-v0), one arm per PARTICIPANT; kept selectable, it needs a connected model:
arm 'template' : the fixed template from data/study/tasks.json (same for every task and person).
arm 'assisted' : a drafted clarification request.
    - model connected -> the adapter's provider is asked (any failure is recorded, never hidden);
    - no model        -> SimulatedProvider, ALWAYS labelled simulated. It is deterministic text built
                         from the task's own fact sheet. It says NOTHING about how a real model performs.
In formal mode a simulated provider is never used (see api_study.formal_blockers).
"""
import json
import time

from . import llm

TEMPLATE_VERSION = "template-v1"
AGELENS_AID_VERSION = "agelens-aid-v1"
ASSIST_VERSION = "assist-v0.1"
PROVIDER_OVERRIDE = None  # tests may set an object with .generate(dict) -> dict


def model_status():
    """-> {connected, label, provider}. Tolerant of the adapter's status() shape (it is being reworked)."""
    try:
        s = llm.status() or {}
    except Exception:
        s = {}
    if isinstance(s.get("model"), dict):
        s = s["model"]
    connected = bool(s.get("connected") or s.get("enabled"))
    if PROVIDER_OVERRIDE is not None:
        connected = True
    return {"connected": connected, "label": "Model connected" if connected else "Template demo",
            "provider": str(s.get("provider") or s.get("name") or ("test-override" if PROVIDER_OVERRIDE else ""))[:40]}


def template_aid(tasks_doc):
    t = tasks_doc["template_aid"]
    return {"kind": "template", "label": t["label"], "text": t["text"], "provider": "fixed-template",
            "simulated": False, "failed": False, "version": TEMPLATE_VERSION}


class SimulatedProvider:
    """Deterministic stand-in. Writes a draft from task.facts. Clearly not a model."""
    name = "SIMULATED"

    def draft(self, task):
        p, f = task["profile"], task["facts"]
        bg = "I am %s and have %s years of %s experience." % (p["age"], p["years_experience"], p["occupation"].lower())
        quote = f.get("quote_en") or f.get("quote")   # English rendering of the ad's age wording when the task has one
        lines = ["Hello, I am writing about the %s (ad %s). %s" % (task.get("job_title_en", task["job_title"]).replace(" (fictional)", ""), task["ad_id"], bg)]
        if f.get("truncated"):
            lines.append("The text of the ad I have ends at \"%s\", so I cannot see the full age requirement." % quote)
            lines.append("Could you send the complete age requirement, and tell me whether it is a requirement or a preference and whether any exceptions apply?")
        elif f.get("exception"):
            lines.append("The ad says \"%s\"." % quote)
            lines.append("I am not sure whether my experience counts as the relevant industry experience that the relaxation refers to.")
            lines.append("Could you confirm whether my %s years would qualify me for the relaxation, and what proof you would need?" % p["years_experience"])
        elif f.get("preference"):
            lines.append("The ad says \"%s\" (under %s preferred)." % (quote, f["preference"]))
            lines.append("I cannot tell from the ad how much this preference counts.")
            lines.append("Is it a preference only, and are applicants over %s reviewed in the same round?" % f["preference"])
        else:
            lines.append("The ad lists \"%s\" (age %s or under)." % (quote, f["cap"]))
            lines.append("I cannot tell from the ad whether this limit is strict for this vacancy or whether any exceptions exist.")
            lines.append("Could you tell me whether applicants who are %s are considered, and what you would look at?" % p["age"])
        return "\n".join(lines)


def _from_model(task, out):
    """Turn a validated adapter output into a plain-text draft (best effort)."""
    parts = []
    for key in ("clarification_questions", "uncertainties"):
        v = out.get(key) if isinstance(out, dict) else None
        if isinstance(v, list):
            parts += [str(x).strip() for x in v if str(x).strip()]
    return "\n".join(parts).strip()


def assisted_aid(task, simulation_ok=True):
    """-> aid dict. 'failed' True means the model call failed (aid text then empty and the failure is logged)."""
    t0 = time.time()
    ms = model_status()
    base = {"kind": "assisted", "label": "Drafted help", "version": ASSIST_VERSION}
    if ms["connected"]:
        try:
            prov = PROVIDER_OVERRIDE or llm.get_provider()
            inp = {"question": task["question"], "confirmed_profile": task["profile"],
                   "evidence": [{"id": task["ad_id"], "original_text": task["ad_text"], "source": "study-fictional", "date": None, "extracted_age_terms": []}],
                   "scope": {"purpose": "study-draft", "fictional": True}}
            raw = prov.generate(inp)
            try:
                clean, _ = llm.validate_output(raw, [task["ad_id"]])
            except Exception:
                clean = raw if isinstance(raw, dict) else {}
            text = _from_model(task, clean)
            if not text:
                raise ValueError("empty model output")
            return dict(base, text=text, provider="model", simulated=False, failed=False, latency_ms=int((time.time() - t0) * 1000))
        except Exception as e:
            return dict(base, text="", provider="model", simulated=False, failed=True, error=type(e).__name__, latency_ms=int((time.time() - t0) * 1000))
    if simulation_ok:
        return dict(base, text=SimulatedProvider().draft(task), provider="SIMULATED", simulated=True, failed=False, latency_ms=0)
    return dict(base, text="", provider="none", simulated=False, failed=True, error="NoModelConnected", latency_ms=0)


def no_aid():
    """Condition A: no aid panel content; the participant has the ad, the gloss and the background only."""
    return {"kind": "none", "label": "Ad only", "text": "", "provider": "none", "simulated": False, "failed": False, "version": AGELENS_AID_VERSION}


def agelens_aid(task):
    """Condition B: AgeLens's own rules-only evidence check of the task ad, as plain text in the product's five headings.
    Deterministic for a given ad text, question, profile and rule version. A failure is recorded, never hidden."""
    t0 = time.time()
    base = {"kind": "agelens", "label": "AgeLens evidence check", "version": AGELENS_AID_VERSION, "simulated": False}
    try:
        from . import api_seeker  # late import: api_seeker pulls in the brief/evidence modules
        b = api_seeker.check_pasted({"text": task["ad_text"], "question": task["question"], "profile": task["profile"]}, allow_model=False)
        lines, pz = [], b.get("pasted") or {}
        # the same notes the Job Seeker page shows above the answer
        # English only: the rules read the Chinese ad text, the aid shows the English glosses (quote_en / text_en)
        if pz.get("truncated"):
            lines += ["Note: the text seems to stop in the middle of an age condition (" + (pz.get("truncated_en") or ["cut-off age wording"])[0] + "). No age limit was read from the cut-off part. Ask for the full ad.", ""]
        if pz.get("conflict"):
            lines += ["Note: the ad's age wording contradicts itself (" + " and ".join(pz.get("conflict_en") or ["two different age statements"]) + "). Both parts are shown; AgeLens does not choose one.", ""]
        for hd in b["headings"]:
            items = b["answer"].get(hd["key"]) or []
            if not items:
                continue
            lines.append(hd["title"])
            for st in items:
                q = st.get("quote_en") if st.get("quote") else None
                lines.append("- " + (st.get("text_en") or st["text"]) + (" [ad text: " + q + "]" if q else ""))
            lines.append("")
        rv = (b.get("pasted") or {}).get("rule_version") or ""
        return dict(base, text="\n".join(lines).strip(), provider="agelens-rules " + rv, failed=False, latency_ms=int((time.time() - t0) * 1000))
    except Exception as e:
        return dict(base, text="", provider="agelens-rules", failed=True, error=type(e).__name__, latency_ms=int((time.time() - t0) * 1000))


# =====================================================================================================
# Design crossover-ai-v1 (decided 2026-10-29, docs/EVAL_PLAN.md): fixed template versus contextual AI assistance, identical evidence.
#   condition A = arm 'template'      : a static question template and checklist filled mechanically from the evidence package.
#   condition B = arm 'ai_contextual' : a model reads the profile and the SAME evidence and drafts a reading, what is explicit /
#                                       unclear, and a targeted question. Its output goes through llm.run_explanation (evidence check).
#   (optional, not in the primary design) arm 'ad_only' = no_aid().
# NO MODEL IS CONNECTED in this build. Without one, arm 'ai_contextual' is not runnable for real:
#   * formal mode is refused (api_study.formal_blockers);
#   * a SIMULATED dry run is allowed: SimulatedAiDrafter writes deterministic script text, labelled SIMULATED everywhere.
#     It is never an AI result and says nothing about AI performance.
# =====================================================================================================
import re

AI_DESIGN_ID = "crossover-ai-v1"
TEMPLATE_AI_VERSION = "template-ai-v1"
AI_ARM_VERSION = "ai-contextual-v1"
SIM_NOTICE = "SIMULATED: No AI model was used; text drafted by a script for the rehearsal."
SIM_PROVIDER = "SIMULATED-script"
CHECKLIST = ["Is the wording a fixed requirement or a preference?",
             "Is there an exception, and who decides it?",
             "What information or proof would the employer need from me?",
             "Is the full age wording visible in the ad?"]
# Output the AI arm must never contain (the prompt forbids it; this is a second, code-level check).
_FORBIDDEN = re.compile(r"\b(you|i)\s+(definitely\s+|certainly\s+|will\s+|do\s+|would\s+)?(qualify|are eligible|am eligible|will be (hired|rejected))\b"
                        r"|\b(is|are)\s+(illegal|unlawful|discriminatory)\b", re.I)
def violates(text):
    """True if any non-question sentence of `text` promises eligibility/outcome or makes a legal accusation (questions such as 'Do I qualify?' are fine)."""
    for sent in re.split(r"(?<=[.!?])\s+", text or ""):
        if not sent.strip().endswith("?") and _FORBIDDEN.search(sent):
            return True
    return False


_AGE_LINE = re.compile(r"(\bage\b|\bunder\s+\d+|\d+\s+or\s+under)", re.I)
_TYPE_WORDS = {"hard_cap": "a fixed age limit", "preference": "an age preference", "ambiguous": "age wording the rules could not read in full"}


def _role(task):
    return (task.get("job_title_en") or task.get("job_title") or "role").replace(" (fictional)", "").strip()


def age_sentence(ad_text_en):
    """Mechanical rule: the first line of the English ad that mentions age and contains a digit, numbering and trailing ';' removed."""
    for line in (ad_text_en or "").split("\n"):
        if _AGE_LINE.search(line) and re.search(r"\d", line):
            s = re.sub(r"^\s*\d+\.\s*", "", line).strip().rstrip(";.").strip()
            return s[0].upper() + s[1:] if s else s
    return ""


def evidence_package(task):
    """The SHARED evidence package (identical for both tools): what the rules (age-rules-2.1.0) found in the ad. Rules only; no model.
    Deterministic. -> {rule_version, age_class, wording, items[], truncated, exception, exception_quote}"""
    from . import api_seeker  # late import
    b = api_seeker.check_pasted({"text": task["ad_text"], "question": task["question"], "profile": task["profile"]}, allow_model=False)
    pz = b.get("pasted") or {}
    items, exc_quote, exc = [], None, False
    for key in ("explicit", "exceptions"):
        for st in b["answer"].get(key) or []:
            txt = st.get("text_en") or st["text"]
            q = st.get("quote_en") if st.get("quote") else None
            if key == "exceptions" and "exception wording" in txt:
                exc, exc_quote = True, q
            items.append(txt + (' [ad text: "%s"]' % q if q else ""))
    trunc = bool(pz.get("truncated"))
    if trunc:
        items.append("The text appears to stop in the middle of an age condition (%s). No age limit was read from the cut-off part." % ((pz.get("truncated_en") or ["cut-off age wording"])[0]))
    wording = age_sentence(task.get("ad_text_en"))
    return {"rule_version": pz.get("rule_version"), "age_class": pz.get("age_class"), "wording": wording,
            "wording_line": 'Age wording found in the ad: "%s"' % wording if wording else "No age wording was found in the ad.",
            "items": items, "truncated": trunc, "exception": exc, "exception_quote": exc_quote}


def template_tool(task, ev):
    """Arm 'template': identical structure for every task; only the slots are filled, from the evidence package alone.
    It does not use the job seeker's profile and does no reasoning about context."""
    role, w = _role(task), ev["wording"] or "(no age wording found)"
    kind = _TYPE_WORDS.get(ev["age_class"], "age wording of an unclear type")
    exc = 'the exception ("%s")' % ev["exception_quote"] if ev["exception_quote"] else ("the exception named in the ad" if ev["exception"] else "any exception")
    reading = 'The ad says: "%s". The rules read this as %s.' % (w, kind)
    question = ('Hello, I am writing about the %s (ad %s). The ad says: "%s". Does %s apply to the %s? '
                "Please confirm whether the wording is a requirement or a preference, and what information you would need from me." % (role, task["ad_id"], w, exc, role))
    return {"reading": reading, "explicit": [], "unclear": [], "checklist": list(CHECKLIST), "question": question}


class SimulatedAiDrafter:
    """Deterministic SCRIPT standing in for the contextual AI arm during rehearsals. It reads the task's fact sheet and profile,
    so it can sound contextual. It is NOT a model, makes no call, and its text is never evidence about an AI."""
    name = SIM_PROVIDER

    def draft(self, task):
        p, f = task["profile"], task["facts"]
        yrs, occ, age = p["years_experience"], p["occupation"].lower(), p["age"]
        q = f.get("quote_en") or f.get("quote") or ""
        who = "I am %s with %s years in %s" % (age, yrs, occ)
        if f.get("truncated"):
            reading = "The text of the ad stops in the middle of the age line (\"%s\"), so the full age requirement cannot be read. No limit should be assumed from it." % q
            explicit = ["The age line is cut off: \"%s\"." % q]
            unclear = ["The upper age limit is not visible.", "It is not visible whether the wording is a requirement, a preference, or has exceptions."]
            question = "%s. The age line in the ad I have ends at \"%s\". Could you send the complete age requirement and say whether it is a requirement or a preference?" % (who, q)
        elif f.get("exception"):
            reading = ("The ad gives an age of %s as the usual limit and says it may be relaxed to %s for candidates with an intermediate title or %s+ years of relevant industry experience. "
                       "You have %s years in %s and no professional title, and the ad does not say whether that experience counts." % (f["cap"], f["relaxed_cap"], 8, yrs, occ))
            explicit = ["The usual limit is %s (\"generally\")." % f["cap"], "The limit may be relaxed to %s with an intermediate or higher title, or 8+ years of relevant industry experience." % f["relaxed_cap"]]
            unclear = ["Whether %s counts as relevant industry experience is not stated." % occ, "How the relaxation is decided and how experience is checked is not stated."]
            question = ("%s and no professional title. The ad says the limit may be relaxed to %s for candidates with 8+ years of relevant industry experience. "
                        "Do my %s years in %s count as relevant industry experience for the relaxation, and how is that checked?" % (who, f["relaxed_cap"], yrs, occ))
        elif f.get("preference"):
            reading = ("The ad says \"%s\", which is worded as a preference, not as a stated limit. No maximum age is given. "
                       "The ad does not say how much weight the preference carries or whether applicants over %s are considered." % (q, f["preference"]))
            explicit = ["\"%s\" is a preference." % q, "No maximum age is stated."]
            unclear = ["How much weight the preference carries is not stated.", "Whether applicants over %s are considered in the same round is not stated." % f["preference"]]
            question = ("%s. The ad says \"%s\". How much weight does this preference carry in screening, and are applicants over %s with experience like mine reviewed in the same round?"
                        % (who, q.lower() if q.startswith("Under") else q, f["preference"]))
        else:
            reading = ("The ad sets an age limit of %s (\"%s\") and states no exception. You are %s, which is above the stated figure; the ad does not say how strictly the limit is applied." % (f["cap"], q, age))
            explicit = ["The ad says \"%s\"." % q, "No exception or relaxation is mentioned."]
            unclear = ["Whether the limit is applied strictly to this vacancy is not stated."]
            question = "%s. The ad lists \"%s\". Is this limit applied strictly for this vacancy, and are applications from people with my background reviewed?" % (who, q)
        return {"reading": reading, "explicit": explicit, "unclear": unclear, "checklist": [], "question": question, "notice": SIM_NOTICE}


def _ai_from_statements(statements):
    by = {}
    for s in statements:
        by.setdefault(s["section"], []).append(s["text"].strip())
    explicit = by.get("explicit", []) + by.get("exceptions", [])
    reading = " ".join(explicit + by.get("relates", [])).strip()
    ask = by.get("ask", [])
    if not reading or not ask:
        raise ValueError("model output has no reading or no question after the evidence check")
    return {"reading": reading, "explicit": explicit, "unclear": by.get("cannot", []), "checklist": [], "question": ask[0]}


def tool_aid(task, cond_kind, ev, simulation_ok):
    """-> aid dict for design crossover-ai-v1. text = JSON of the tool output (reading/explicit/unclear/checklist/question).
    failed True means no output could be produced (recorded, never hidden). Formal mode passes simulation_ok=False."""
    t0 = time.time()
    base = {"kind": cond_kind, "version": TEMPLATE_AI_VERSION if cond_kind == "template" else AI_ARM_VERSION}
    ms = lambda: int((time.time() - t0) * 1000)
    if cond_kind == "template":
        return dict(base, label="Fixed template", text=json.dumps(template_tool(task, ev)), provider="fixed-template", simulated=False, failed=False, latency_ms=ms())
    if cond_kind == "none":
        return dict(base, label="Ad text only", text=json.dumps({"reading": "", "explicit": [], "unclear": [], "checklist": [], "question": ""}), provider="none", simulated=False, failed=False, latency_ms=0)
    base["label"] = "Contextual AI assistance"
    if model_status()["connected"]:
        try:
            from . import ageparse
            prov = PROVIDER_OVERRIDE or llm.get_provider()
            ad = {"id": task["ad_id"], "description": task["ad_text"], "source": "study-fictional", "posted_date": None, "age_terms": ageparse.parse_age(task["ad_text"])}
            inp = llm.build_input(task["question"], task["profile"], [ad], {"purpose": "study-ai-arm", "fictional": True})
            res = llm.run_explanation(inp, provider=prov)
            if not res.get("ok"):
                raise ValueError(res.get("reason") or "model_failed")
            out = _ai_from_statements(res["statements"])
            if violates(" ".join([out["reading"], out["question"]] + out["explicit"] + out["unclear"])):
                raise ValueError("forbidden_claim")
            return dict(base, text=json.dumps(out), provider="model:" + str(getattr(prov, "name", "model")), simulated=False, failed=False, latency_ms=ms())
        except Exception as e:
            return dict(base, text="", provider="model", simulated=False, failed=True, error=type(e).__name__ + ":" + str(e)[:60], latency_ms=ms())
    if simulation_ok:
        out = SimulatedAiDrafter().draft(task)
        assert not violates(out["reading"] + " " + out["question"])
        return dict(base, text=json.dumps(out), provider=SIM_PROVIDER, simulated=True, failed=False, latency_ms=0)
    return dict(base, text="", provider="none", simulated=False, failed=True, error="NoModelConnected", latency_ms=0)
