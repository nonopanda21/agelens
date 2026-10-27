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
        quote = f.get("quote")
        lines = ["Hello, I am writing about the %s (ad %s). %s" % (task["job_title"].replace(" (fictional)", ""), task["ad_id"], bg)]
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
        if pz.get("truncated"):
            lines += ["Note: the text seems to stop in the middle of an age condition (" + pz["truncated"][0] + "). No age limit was read from the cut-off part. Ask for the full ad.", ""]
        if pz.get("conflict"):
            lines += ["Note: the ad's age wording contradicts itself (" + " and ".join(pz["conflict"]) + "). Both parts are shown; AgeLens does not choose one.", ""]
        for hd in b["headings"]:
            items = b["answer"].get(hd["key"]) or []
            if not items:
                continue
            lines.append(hd["title"])
            for st in items:
                lines.append("- " + st["text"] + (" [ad text: " + st["quote"] + "]" if st.get("quote") else ""))
            lines.append("")
        rv = (b.get("pasted") or {}).get("rule_version") or ""
        return dict(base, text="\n".join(lines).strip(), provider="agelens-rules " + rv, failed=False, latency_ms=int((time.time() - t0) * 1000))
    except Exception as e:
        return dict(base, text="", provider="agelens-rules", failed=True, error=type(e).__name__, latency_ms=int((time.time() - t0) * 1000))
