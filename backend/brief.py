"""Rules/template Evidence brief (SPEC 4.3). No AI: every sentence comes from fixed templates filled
with counts and quotes computed from the stored ads. Nothing here states a legal conclusion, a hiring
probability, or that any employer discriminates. The user's age is used only to compare with a
stated cap in a neutral factual sentence.
"""
import datetime
import time
from collections import Counter

from . import gloss, llm

LABEL = "Evidence summary — rules-based"
DEMO_LABEL = "Demo · Synthetic data"
ANSWER_HEADINGS = [
    ("explicit", "What does the ad explicitly say?"),
    ("exceptions", "What exceptions exist?"),
    ("relates", "How does this relate to your question?"),
    ("cannot", "What can't be determined yet?"),
    ("ask", "What you could ask next"),
]
MIN_ADS = 5          # fewer matched ads than this -> "insufficient evidence": no aggregate claims
MAX_IDS = 40         # cap evidence_ids listed per finding (counts always show the full number)
FETCH_PAGE = 50
FETCH_PAGES = 6      # analyse at most 300 ads; truncation is reported
SECTIONS = [
    {"n": 1, "key": "question_background", "title": "Your question & confirmed background"},
    {"n": 2, "key": "findings", "title": "What the evidence says"},
    {"n": 3, "key": "unclear", "title": "What remains unclear"},
    {"n": 4, "key": "questions", "title": "Questions to ask"},
    {"n": 5, "key": "next_steps", "title": "Suggested next steps"},
    {"n": 6, "key": "scope", "title": "Data scope"},
]
# English search words -> Chinese substrings that occur in ad titles / occupations. Used by the UI to
# suggest (never silently apply) a search term; the user sees and can edit it.
ALIASES = {
    "operations": ["运营"], "operation": ["运营"], "operations manager": ["运营"], "sales": ["销售"],
    "engineer": ["工程师"], "engineering": ["工程师"], "software": ["软件", "开发"], "developer": ["开发"],
    "administration": ["行政"], "administrative": ["行政"], "admin": ["行政"], "accountant": ["会计"],
    "accounting": ["会计"], "finance": ["财务"], "hr": ["人事", "人力资源"], "human resources": ["人力资源"],
    "marketing": ["市场", "营销"], "customer service": ["客服"], "designer": ["设计"], "design": ["设计"],
    "logistics": ["物流"], "procurement": ["采购"], "purchasing": ["采购"], "product": ["产品"],
    "teacher": ["教师", "老师"], "driver": ["司机"], "assistant": ["助理"], "manager": ["经理"], "supervisor": ["主管"],
}


def _int(v, lo, hi):
    try:
        n = int(str(v).strip())
        return n if lo <= n <= hi else None
    except (TypeError, ValueError):
        return None


def clean_profile(p):
    p = p if isinstance(p, dict) else {}
    s = lambda k, n=200: (str(p.get(k) or "").strip()[:n])
    skills = p.get("skills") or []
    if isinstance(skills, str):
        skills = [x for x in skills.replace("\n", ",").split(",")]
    skills = [str(x).strip()[:60] for x in skills if str(x).strip()][:20]
    return {"age": _int(p.get("age"), 14, 80), "occupation": s("occupation", 80),
            "years_experience": _int(p.get("years_experience"), 0, 60), "skills": skills,
            "region": s("region", 40), "education": s("education", 80)}


def _ads(n):
    return "%d ad%s" % (n, "" if n == 1 else "s")


def _ids(ads):
    return list(dict.fromkeys(a["id"] for a in ads))[:MAX_IDS]


def _all_terms(ads):
    return [t for a in ads for t in _terms(a)]


def _title_en(a):
    t = a.get("title_en") or (a.get("title") if a.get("title") and not gloss.has_cjk(a.get("title")) else None)
    return t or a.get("id") or "untitled ad"


def _finding(fid, statement, ads, kind, num=None, den=None, statement_en=None):
    f = {"id": fid, "statement": statement, "evidence_ids": _ids(ads), "kind": kind,
         "evidence_total": len({a["id"] for a in ads})}
    f["statement_en"] = gloss.en_text(statement_en or statement, _all_terms(ads))
    if den is not None:
        f["counts"] = {"numerator": num, "denominator": den}
    return f


def _terms(ad):
    return ad.get("age_terms") or []


def _flagged(t, name):
    return name in (t.get("flag") or "").split(",")


def _usable(t):
    """Terms the rules flagged as contradictory or cut off never count as a stated limit (both parts are quoted instead)."""
    return not (_flagged(t, "conflict") or _flagged(t, "truncated"))


def _conflict_snippets(ad):
    """Snippets of terms the rules flagged as contradicting each other within one ad (e.g. 年龄不限 + 35岁以下)."""
    return list(dict.fromkeys(t["snippet"] for t in _terms(ad) if _flagged(t, "conflict") and t.get("snippet")))[:3]


def _quoted(snips):
    return " and ".join("“%s”" % x for x in snips)


# job titles that name a person ("as an operations manager"); anything else is a field ("in procurement")
ROLE_WORDS = ("manager", "engineer", "specialist", "officer", "assistant", "lead", "director", "analyst", "designer", "accountant",
              "teacher", "driver", "supervisor", "clerk", "consultant", "developer", "representative", "executive", "coordinator",
              "administrator", "nurse", "technician", "worker", "operator", "agent", "buyer", "planner", "architect", "head",
              "keeper", "programmer", "scientist", "writer", "editor", "cashier", "chef", "cook", "receptionist", "trainer", "tutor")


def _experience_sentence(years, occupation):
    """'I have 8 years of experience as an operations manager.' Neutral, English only; None without years."""
    if years is None:
        return None
    yrs = "%d year%s of experience" % (years, "" if years == 1 else "s")
    occ = (occupation or "").strip()
    if not occ or gloss.has_cjk(occ):
        return "I have %s in this kind of work." % yrs
    words = [w if (w.isupper() and len(w) > 1) else w.lower() for w in occ.split()]
    alpha = [w for w in words if w.strip("()").isalpha()]
    phrase = " ".join(words)
    if alpha and alpha[-1].strip("()") in ROLE_WORDS:
        first = words[0]
        vowel = first[0] in "AEFHILMNORSX" if (first.isupper() and len(first) > 1) else first[0] in "aeiou"   # "an HR …", "an operations …"
        return "I have %s as %s %s." % (yrs, "an" if vowel else "a", phrase)
    return "I have %s in %s." % (yrs, phrase)


def _questions(ads, n, with_max, exc_ads, amb, profile):
    """Neutral questions for the employer. One ad -> 'The ad ...'; several -> 'similar ads ...' (the question goes to one employer)."""
    one = n == 1
    qs = []
    if with_max:
        qs.append({"text": ("The ad states a maximum age of %d. Is that a firm requirement for this role, or does it vary by candidate?" % _max_age(with_max[0])) if one
                   else "Several similar ads state a maximum age. For this role, is any stated age a firm requirement, or does it vary by candidate?",
                   "evidence_ids": _ids(with_max)})
    if exc_ads:
        qs.append({"text": "The ad says some requirements may be relaxed. What criteria are used, and who decides?" if one
                   else "Some similar ads say requirements may be relaxed. For this role, what criteria are used, and who decides?", "evidence_ids": _ids(exc_ads)})
    conf_ads = [a for a in ads if _conflict_snippets(a)]
    if conf_ads:
        t = ("The ad's age wording contradicts itself (%s). Which of these applies to this role?" if one
             else "One similar ad's age wording contradicts itself (%s). For this role, which applies?") % _quoted(_conflict_snippets(conf_ads[0]))
        qs.append({"text": t, "evidence_ids": _ids(conf_ads), "text_en": gloss.en_text(t, _terms(conf_ads[0]))})
    if amb:
        qs.append({"text": "Some age wording in the ad is unclear. Could you clarify what it means for this role?" if one
                   else "Some similar ads word age unclearly. For this role, is there an age requirement, and what does it mean?", "evidence_ids": _ids(amb)})
    qs.append({"text": "At which stage of the process (screening, interview, offer) are age-related requirements applied, if at all?", "evidence_ids": _ids(with_max or ads)})
    exp = _experience_sentence(profile["years_experience"], profile["occupation"])
    qs.append({"text": (exp[:-1] + ". Which parts of that experience matter most for this role?") if exp else "Which skills and experience matter most for this role?", "evidence_ids": []})
    return qs


def _employer_question(ads, n, with_max, exc_ads, amb, profile):
    """The ONE question the answer leads with: the person's experience (never their age) + the most useful neutral ask.
    It goes to one employer, so with several similar ads it never cites the other ads."""
    one = n == 1
    conf = [a for a in ads if _conflict_snippets(a)]
    cut = [a for a in ads if any(_flagged(t, "truncated") for t in _terms(a))]
    exp = _experience_sentence(profile["years_experience"], profile["occupation"])
    consider = "or can experience like mine be considered?" if exp else "or does it vary by candidate?"
    caps = sorted({t["max_age"] for t in _terms(ads[0]) if t.get("max_age") is not None and t.get("kind") in ("max", "range") and _usable(t)}) if one else []
    if one and len(caps) > 1 and not conf:
        core = "The ad states different maximum ages (%s). Which one applies to this role, and is it firm %s" % (", ".join(str(c) for c in caps), consider)
    elif one and conf:
        core = "The ad's age wording contradicts itself (%s). Which of these applies to this role?" % _quoted(_conflict_snippets(conf[0]))
    elif one and cut and not with_max:
        core = "The age requirement in the ad seems to be cut off. Could you tell me the full requirement for this role?"
    elif with_max and exc_ads:
        core = ("The ad states a maximum age of %d and says exceptions are possible. Is the age a firm requirement for this role, %s" % (_max_age(with_max[0]), consider)) if one \
            else "For this role, is there an age requirement, and if so, is it firm %s" % consider
    elif with_max:
        core = ("The ad states a maximum age of %d. Is that a firm requirement for this role, %s" % (_max_age(with_max[0]), consider)) if one \
            else "For this role, is there an age requirement, and if so, is it firm %s" % consider
    elif exc_ads:
        core = "The ad says some requirements may be relaxed. What criteria are used for this role, and who decides?" if one \
            else "Are any requirements for this role relaxed for some candidates? If so, what criteria are used, and who decides?"
    elif amb:
        core = "Some age wording in the ad is unclear. Could you clarify whether there is an age requirement for this role?" if one \
            else "Could you clarify whether there is an age requirement for this role?"
    else:
        core = "At which stage of the process (screening, interview, offer) are age-related requirements applied for this role, if at all?"
    text = (exp + " " + core) if exp else core
    return {"text": text, "text_en": gloss.en_text(text, _all_terms(conf[:1] or with_max[:1] or exc_ads[:1] or ads[:1]))}


def _summary(ads, n, status, with_max, exc_ads, profile):
    """Three short lines for the top of the answer: what the ad(s) state, how that relates to the person, the question.
    Never says whether the person qualifies."""
    one = n == 1
    age = profile["age"]
    if n == 0:
        states = "No similar ads were found, so there is no ad wording to report."
    elif one:
        a = ads[0]
        mx, mn = _max_age(a), _min_age(a)
        caps = sorted({t["max_age"] for t in _terms(a) if t.get("max_age") is not None and t.get("kind") in ("max", "range") and _usable(t)})
        if _conflict_snippets(a):
            states = "The ad's age wording contradicts itself: it contains %s." % _quoted(_conflict_snippets(a))
        elif len(caps) > 1:
            states = "The ad states different maximum ages (%s)." % ", ".join(str(c) for c in caps)
        elif mx is not None or mn is not None:
            parts = (["a maximum age of %d" % mx] if mx is not None else []) + (["a minimum age of %d" % mn] if mn is not None else [])
            states = "The ad states %s%s." % (" and ".join(parts), " and adds exception wording" if _exceptions(a) else "")
        elif any(_flagged(t, "truncated") for t in _terms(a)):
            states = "The ad's age wording seems to be cut off, so no age limit was read from it."
        elif any(_flagged(t, "unlimited") for t in _terms(a)):
            states = "The ad says there is no age limit."
        elif a.get("age_status") == "uncertain":
            states = "The ad mentions age, but not as a clear limit."
        else:
            states = "No age requirement was found in the ad."
    else:
        states = "Of %d similar ads, %d state an age requirement" % (n, status["explicit"])
        if with_max:
            counts = Counter(_max_age(a) for a in with_max)
            top, c = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            if len(counts) == 1:
                states += "; the stated maximum is %d" % top
            elif c > 1 and list(counts.values()).count(c) == 1:
                states += "; the most common maximum is %d (%s)" % (top, _ads(c))
            else:
                states += "; stated maximums range from %d to %d" % (min(counts), max(counts))
        states += "; %d mention exceptions." % len(exc_ads) if exc_ads else "."
    mixed = one and ads and (_conflict_snippets(ads[0]) or len({t["max_age"] for t in _terms(ads[0]) if t.get("max_age") is not None and t.get("kind") in ("max", "range") and _usable(t)}) > 1)
    if age is None:
        relates = "You did not give your age, so the stated limits are not compared with it. Age never hides ads."
    elif mixed:
        relates = "You entered %d. The ad gives more than one age limit, so only the employer can say which one applies, if any." % age
    elif not with_max:
        relates = "No stated maximum age to compare with the age you entered (%d)." % age
    elif one:
        mx = _max_age(with_max[0])
        relates = "You entered %d; the stated maximum is %d. Only the employer can say how the limit is applied%s." % (
            age, mx, " and whether the exception wording covers you" if _exceptions(with_max[0]) else "")
    else:
        lower = sum(1 for a in with_max if _max_age(a) < age)
        share = ("all %d ads" % len(with_max)) if lower == len(with_max) and lower > 1 else ("%d of the %d ads" % (lower, len(with_max)))
        relates = "You entered %d: %s that state a maximum give one below that. Only employers can say how their limits are applied." % (age, share)
    terms = _all_terms(ads)
    return {"states": states, "states_en": gloss.en_text(states, terms), "relates": relates, "relates_en": gloss.en_text(relates, terms)}


def _max_age(ad):
    vals = [t["max_age"] for t in _terms(ad) if t.get("max_age") is not None and t.get("kind") in ("max", "range") and _usable(t)]
    return min(vals) if vals else None


def _min_age(ad):
    vals = [t["min_age"] for t in _terms(ad) if t.get("min_age") is not None and t.get("kind") in ("min", "range") and _usable(t)]
    return max(vals) if vals else None


def _exceptions(ad):
    # "年龄不限" (flag 'unlimited') says there is no age limit; it is not exception wording.
    ts = [t for t in _terms(ad) if not _flagged(t, "unlimited")]
    return [t.get("exception_text") for t in ts if t.get("exception_text")] + \
           ([t.get("snippet") for t in ts if t.get("kind") == "relaxable" and t.get("snippet")])


def _load(ev, body, filters):
    ids = body.get("evidence_ids")
    if isinstance(ids, list) and ids:
        ads = [a for a in (ev.get_ad(str(i)) for i in ids[:50]) if a]
        return ads, len(ads), "selected", {"selected_ids": [a["id"] for a in ads]}, any(a.get("is_demo") for a in ads)
    ads, total, applied, demo = [], 0, {}, False
    for page in range(1, FETCH_PAGES + 1):
        r = ev.search_ads(filters, page=page, page_size=FETCH_PAGE, sort="date_desc")
        total, applied, demo = r["total"], r.get("filters_applied", filters), r.get("using_demo", False)
        ads += r["items"]
        if len(ads) >= total or not r["items"]:
            break
    return ads, total, "search", applied, demo


DETAIL_N = 60        # ads whose full text is loaded (quotes need it); search summaries carry no description
MODEL_ADS = 12       # at most this many ads (those with age conditions first) are sent to a model
MODEL_CHARS = 1500   # characters of each ad's text sent to a model


def _with_details(ev, ads):
    """Search summaries have no `description`. Load full ad text for the most relevant ads so quotes can be
    attached (and verified to occur literally in the text)."""
    if not hasattr(ev, "get_ad"):
        return ads
    order = sorted(range(len(ads)), key=lambda i: (ads[i].get("description") is not None, 0 if _terms(ads[i]) else 1, i))
    for i in order[:DETAIL_N]:
        a = ads[i]
        if a.get("description"):
            continue
        try:
            d = ev.get_ad(a["id"])
        except Exception:
            d = None
        if d:
            for k in ("description", "age_class", "data_version", "url"):
                if d.get(k) is not None:
                    a[k] = d[k]
    return ads


def build_brief(body, ev=None, allow_model=True):
    """allow_model=False keeps the brief rules-only even when a model is connected (the study aid must not vary)."""
    if ev is None:
        from . import evidence as ev  # lazy: agent A's module may land after this one
    question = str(body.get("question") or "").strip()[:2000]
    profile = clean_profile(body.get("profile"))
    filters = body.get("filters")
    filters = dict(filters) if isinstance(filters, dict) else {}
    if not filters and not body.get("evidence_ids"):  # direct API use: derive from profile, and say so
        if profile["region"]:
            filters["province"] = profile["region"]
        if profile["occupation"]:
            filters["occupation"] = ALIASES.get(profile["occupation"].lower(), [profile["occupation"]])[0]
    ads, total, mode, applied, demo = _load(ev, body, filters)
    ads = _with_details(ev, ads)
    n = len(ads)
    age = profile["age"]

    status = Counter(a.get("age_status") if a.get("age_status") in ("explicit", "uncertain") else "none" for a in ads)
    insufficient = n < MIN_ADS
    findings, unclear, questions = [], [], []

    # ---- 2. what the evidence says ----
    if n == 0:
        pass
    else:
        by = {k: [a for a in ads if (a.get("age_status") if a.get("age_status") in ("explicit", "uncertain") else "none") == k]
              for k in ("explicit", "uncertain", "none")}
        if not insufficient:
            findings.append(_finding(
                "F1", "Of %d matched ads, %d state an explicit age condition, %d %s age-related wording that needs "
                      "interpretation, and %d had no explicit age condition detected."
                      % (n, status["explicit"], status["uncertain"], "contains" if status["uncertain"] == 1 else "contain", status["none"]), ads, "overview", status["explicit"], n))
            maxes = Counter()
            with_max = [a for a in ads if _max_age(a) is not None]
            for a in with_max:
                maxes[_max_age(a)] += 1
            if with_max:
                top = ", ".join("%d (%s)" % (k, _ads(v)) for k, v in sorted(maxes.items(), key=lambda kv: (-kv[1], kv[0]))[:5])
                findings.append(_finding("F2", "Among the %d ads that state a maximum age, the stated maximums are: %s."
                                         % (len(with_max), top), with_max, "max_age", len(with_max), n))
                a35 = [a for a in with_max if _max_age(a) == 35]
                if a35:
                    findings.append(_finding("F3", "%d of %d ads with a stated maximum age give 35 as the maximum."
                                             % (len(a35), len(with_max)), a35, "threshold_35", len(a35), len(with_max)))
            with_min = [a for a in ads if _min_age(a) is not None]
            if with_min:
                findings.append(_finding("F4", "%s state%s a minimum age." % (_ads(len(with_min)), "s" if len(with_min) == 1 else ""), with_min, "min_age", len(with_min), n))
            exc = [a for a in ads if _exceptions(a)]
            if exc:
                quotes = list(dict.fromkeys(q for a in exc for q in _exceptions(a)))[:3]
                findings.append(_finding("F5", "%d of %d ads include wording that suggests some requirements may be relaxed, "
                                         "for example: %s." % (len(exc), n, "; ".join("“%s”" % q for q in quotes)),
                                         exc, "exceptions", len(exc), n))
            if age is not None and with_max:
                lower = [a for a in with_max if _max_age(a) < age]
                findings.append(_finding(
                    "F6", "Of the %d ads that state a maximum age, %d have a stated maximum below the age you entered (%d) and %d have "
                          "a stated maximum equal to or above it." % (len(with_max), len(lower), age, len(with_max) - len(lower)),
                    with_max, "profile_comparison", len(lower), len(with_max)))
            if status["none"]:
                findings.append(_finding("F7", "%d of %d ads had no explicit age condition detected. This describes the "
                                         "wording found by the rules only; it does not say how the employer decides."
                                         % (status["none"], n), by["none"], "no_condition", status["none"], n))
        # per-ad factual sentences (also the only findings when evidence is thin)
        shown = 0
        for a in sorted(ads, key=lambda x: (_max_age(x) is None, x.get("posted_date") or ""), reverse=False):
            mx, mn = _max_age(a), _min_age(a)
            if mx is None and mn is None:
                continue
            if shown >= (10 if insufficient else 5):
                break
            title = a.get("title") or a["id"]
            parts = []
            if mx is not None:
                parts.append("a maximum of %d" % mx)
            if mn is not None:
                parts.append("a minimum of %d" % mn)
            tail = " and ".join(parts) + ("; you entered %d" % age if age is not None else "") + "."
            s, s_en = "This ad (%s) states %s" % (title, tail), "This ad (%s) states %s" % (_title_en(a), tail)
            ex = _exceptions(a)
            if ex:
                more = " The ad also says “%s”, which suggests exceptions may be possible — ask how they are decided."
                s, s_en = s + more % ex[0], s_en + more % ex[0]
            findings.append(_finding("A%d" % (shown + 1), s, [a], "ad_fact", statement_en=s_en))
            shown += 1

    # ---- 3. unclear ----
    if n == 0:
        unclear.append("No ads matched these filters, so this brief cannot say anything about them. Broaden the search yourself if you wish.")
    elif insufficient:
        unclear.append("Only %d ad%s matched (fewer than %d): this is too few to describe any pattern, so no aggregate statements are made."
                       % (n, "" if n == 1 else "s", MIN_ADS))
    exc_ads = [a for a in ads if _exceptions(a)]
    if exc_ads:
        unclear.append("Exception wording (for example “%s”) does not say who qualifies or how it is decided." % _exceptions(exc_ads[0])[0])
    amb = [a for a in ads if any(t.get("kind") == "ambiguous" or t.get("confidence") == "low" for t in _terms(a))]
    if amb:
        unclear.append("%s %s wording the rules could not interpret with confidence; read the original text." % (_ads(len(amb)), "contains" if len(amb) == 1 else "contain"))
    if status["uncertain"] and not amb:
        unclear.append("%s %s age-related wording marked uncertain." % (_ads(status["uncertain"]), "has" if status["uncertain"] == 1 else "have"))
    if status["none"] and n:
        unclear.append("Ads with no explicit age condition detected may still apply requirements that are not written in the ad.")
    missing = []
    if age is None:
        missing.append("age")
    if not profile["occupation"]:
        missing.append("occupation")
    if profile["years_experience"] is None:
        missing.append("years of experience")
    if not profile["region"]:
        missing.append("region")
    if not profile["skills"]:
        missing.append("skills / experience")
    if missing:
        unclear.append("Profile fields not provided: %s. %s" % (", ".join(missing),
                       "Without age, ad age limits are shown but not compared with you." if "age" in missing else "This limits how closely the evidence can be matched to you."))
    if demo:
        unclear.append("These ads are demonstration data, not a real sample.")
    nodate = sum(1 for a in ads if not a.get("posted_date"))
    if nodate:
        unclear.append("%d of %d ads have no posting date." % (nodate, n))
    if mode == "search" and total > n:
        unclear.append("%d ads matched but only the %d most recent were analysed." % (total, n))

    # ---- 4. questions (neutral) ----
    with_max_all = [a for a in ads if _max_age(a) is not None]
    questions = _questions(ads, n, with_max_all, exc_ads, amb, profile)

    # ---- 5. next steps ----
    steps = ["Open the original ads you care about and read the full Chinese text around the highlighted wording."]
    if n == 0 or insufficient:
        steps.append("Use the explicit 'Broaden region' or 'Broaden occupation' options on the search page, then regenerate this brief.")
    steps += ["Choose the ads that matter most and ask the questions above when you contact the recruiter.",
              "If you want a second opinion, send selected evidence and your question for human review (you choose which profile fields to share)."]

    # ---- 6. scope ----
    dates = sorted(a["posted_date"] for a in ads if a.get("posted_date"))
    versions = sorted({t.get("rule_version") for a in ads for t in _terms(a) if t.get("rule_version")})
    scope = {"basis": "selected evidence" if mode == "selected" else "search", "filters_applied": applied,
             "matched_total": total, "ads_analysed": n, "ads_with_stated_max_age": len(with_max_all),
             "date_min": dates[0] if dates else None, "date_max": dates[-1] if dates else None,
             "ads_missing_date": nodate, "using_demo": bool(demo), "missing_profile_fields": missing,
             "rule_versions": versions, "generation_mode": "rules"}
    limitations = ["Rules detect wording in ads; they can miss or misread phrasing, so check the original text.",
                   "Counts describe only the ads in this scope, not the whole job market.",
                   "This summary is not legal advice and does not predict any hiring outcome."]

    model_ads = sorted(ads, key=lambda a: (not _terms(a), 0 if a.get("description") else 1))[:MODEL_ADS]
    for q in questions:
        q.setdefault("text_en", gloss.en_text(q["text"], _all_terms(ads)))
    llm_input = llm.build_input(question, profile, model_ads, scope, max_chars=MODEL_CHARS)
    answer, index = _answer(ads, llm_input, profile, question, n, insufficient, status, with_max_all, exc_ads, amb, questions, demo)
    scope["data_version"] = _data_version(ev)
    mstat = llm.status()
    res = llm.run_explanation(llm_input) if allow_model and mstat["connected"] and n else {"ran": False, "ok": False, "reason": "not_configured" if not (allow_model and mstat["connected"]) else "no_evidence"}
    ai_status, note, report = "template", llm.failure_text("not_configured"), None
    if res["ran"] and res["ok"]:
        ai_status, note, report = "used", "Model-written statements below are labelled “Model inference” or “Ad text” and were checked by code against the ad texts. The check is not a guarantee; confirm against the original wording.", res["report"]
        for st in res["statements"]:
            m = dict(st, id="M%d" % (len(answer[st["section"]]) + 1), source="model")
            tt = _all_terms([a for a in ads if a["id"] in (st.get("evidence_ids") or [])])
            m["text_en"] = gloss.en_text(m.get("text") or "", tt)
            if m.get("quote"):
                m["quote_en"] = gloss.quote_en(m["quote"], tt)
            answer[st["section"]].append(m)
        for ev_id in {i for st in res["statements"] for i in st["evidence_ids"]}:
            index.setdefault(ev_id, _index_entry(next((a for a in ads if a["id"] == ev_id), {"id": ev_id})))
    elif res["ran"]:
        ai_status, note = "fallback", llm.failure_text(res["reason"])
    elif mstat["connected"]:
        note = "Model not run — no matched ads to explain."
    brief = {
        "label": LABEL, "generation_mode": "rules+model" if ai_status == "used" else "rules", "ai_status": ai_status,
        "ai_reason": mstat["reason"], "ai_note": note, "ai_report": report, "prompt_version": mstat["prompt_version"] if ai_status == "used" else None,
        "model": {"connected": mstat["connected"], "label": mstat["label"], "ran": bool(res["ran"] and res["ok"]), "note": note},
        "data_label": DEMO_LABEL if demo else None,
        "needs_human_confirmation": True,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "headings": [{"key": k, "title": t.replace("does the ad", "do the ads") if n > 1 else t} for k, t in ANSWER_HEADINGS], "answer": answer, "evidence_index": index,
        "sections": SECTIONS, "insufficient": insufficient, "using_demo": bool(demo),
        "question_background": {"question": question, "profile": profile, "missing_fields": missing,
                                "question_missing": not question},
        "summary": _summary(ads, n, status, with_max_all, exc_ads, profile),
        "employer_question": _employer_question(ads, n, with_max_all, exc_ads, amb, profile) if n else None,
        "findings": findings, "unclear": unclear, "unclear_en": [gloss.en_text(u, _all_terms(exc_ads or ads)) for u in unclear],
        "questions": questions, "next_steps": steps, "scope": scope,
        "limitations": limitations,
        "disclaimer": "This summary organises ad wording as evidence. It is not legal advice, does not say whether you are eligible, and does not predict hiring outcomes. Age is used only to explain conditions.",
    }
    brief["markdown"] = to_markdown(brief)
    return brief


_dv_cache = {}


def _data_version(ev):
    """Data version as reported by the evidence module (agent A2 adds data_version to overview); None if absent."""
    try:
        key = id(ev)
        hit = _dv_cache.get(key)
        if hit and time.time() - hit[0] < 60:
            return hit[1]
        v = ev.overview({}).get("data_version") if hasattr(ev, "overview") else None
        _dv_cache[key] = (time.time(), v)
        return v
    except Exception:
        return None


def _index_entry(a):
    company_en = a.get("company_en") or (a.get("company") if a.get("company") and not gloss.has_cjk(a.get("company")) else None)
    return {"title": a.get("title"), "company": a.get("company"), "source": a.get("source"), "posted_date": a.get("posted_date"),
            "province": a.get("province"), "is_demo": bool(a.get("is_demo")),
            "title_en": _title_en(a), "company_en": company_en, "province_en": gloss.province_en(a.get("province")),
            "source_en": gloss.source_en(a.get("source"), bool(a.get("is_demo")))}


def _quote(ad, snippet):
    """A quote is only attached if it literally occurs in the ad text."""
    return snippet if snippet and snippet in (ad.get("description") or "") else None


def _answer(ads, llm_input, profile, question, n, insufficient, status, with_max, exc_ads, amb, questions, demo):
    A = {k: [] for k, _ in ANSWER_HEADINGS}
    counter = {k: 0 for k in A}

    def add(sec, typ, text, ads_=(), quote=None, counts=None):
        counter[sec] += 1
        terms = _all_terms(ads_)
        st = {"id": sec[0].upper() + str(counter[sec]), "type": typ, "text": text, "source": "rules",
              "evidence_ids": list(dict.fromkeys(a["id"] for a in ads_))[:MAX_IDS],
              # display text without Chinese: quoted ad wording is replaced by its gloss; user input keeps its English parts
              "text_en": gloss.strip_cjk(text) if typ == "user_stated" else gloss.en_text(text, terms)}
        if quote:
            st["quote"] = quote
            st["quote_en"] = gloss.quote_en(quote, terms)
        if counts:
            st["counts"] = {"numerator": counts[0], "denominator": counts[1]}
        A[sec].append(st)

    # ---- explicit
    if n == 0:
        add("explicit", "rules", "No similar ads were found, so there is no ad wording to report.")
    else:
        if not insufficient:
            add("explicit", "rules", "Of %d similar ads, %d state an age requirement, %d %s age unclearly, and in %d no age requirement was found."
                % (n, status["explicit"], status["uncertain"], "words" if status["uncertain"] == 1 else "word", status["none"]), ads, counts=(status["explicit"], n))
            if with_max:
                mx = Counter(_max_age(a) for a in with_max)
                top = ", ".join("%d (%s)" % (k, _ads(v)) for k, v in sorted(mx.items(), key=lambda kv: (-kv[1], kv[0]))[:5])
                add("explicit", "rules", "Among the %d ads that state a maximum age, the stated maximums are: %s." % (len(with_max), top), with_max, counts=(len(with_max), n))
        shown = 0
        for a in sorted(ads, key=lambda x: (_max_age(x) is None and _min_age(x) is None, _max_age(x) or 99)):
            terms = [t for t in _terms(a) if t.get("kind") in ("max", "min", "range") and t.get("snippet") and _usable(t)]
            if not terms or shown >= (10 if insufficient else 6):
                continue
            t = terms[0]
            mx, mn = _max_age(a), _min_age(a)
            parts = (["a maximum age of %d" % mx] if mx is not None else []) + (["a minimum age of %d" % mn] if mn is not None else [])
            add("explicit", "ad_fact", "This ad states %s." % " and ".join(parts), [a], quote=_quote(a, t["snippet"]))
            shown += 1
        conf_ads = [x for x in ads if _conflict_snippets(x)]
        for a in conf_ads[:3]:
            add("explicit", "ad_fact", "This ad's age wording contradicts itself: it contains %s. The rules do not choose between them." % _quoted(_conflict_snippets(a)), [a])
        for a in [x for x in ads if x.get("age_status") == "uncertain" and x not in conf_ads][:3]:
            t = next((t for t in _terms(a) if t.get("snippet")), None)
            if any(_flagged(x, "truncated") for x in _terms(a)):
                line = "This ad's age wording seems to be cut off, so no age limit was read from it."
            elif any(_flagged(x, "unlimited") for x in _terms(a)):
                line = "This ad says there is no age limit."
            else:
                line = "This ad mentions age, but not as a clear number."
            add("explicit", "ad_fact", line, [a], quote=_quote(a, t and t["snippet"]))
        if not shown and not status["uncertain"]:
            add("explicit", "rules", "None of the similar ads states an age requirement that the rules could find (read the ads to be sure).", ads)
    # ---- exceptions
    pref = [a for a in ads if a.get("age_class") == "preference" or any(t.get("kind") == "relaxable" and not _flagged(t, "unlimited") for t in _terms(a))]
    if exc_ads and not insufficient:
        add("exceptions", "rules", "%d of %d ads %s wording that suggests some requirements may be relaxed." % (len(exc_ads), n, "includes" if len(exc_ads) == 1 else "include"), exc_ads, counts=(len(exc_ads), n))
    for a in exc_ads[:6]:
        if a.get("age_class") == "preference":
            continue
        q = _exceptions(a)[0]
        add("exceptions", "ad_fact", "The ad adds exception wording next to its age wording. It does not say who qualifies or how that is decided.", [a], quote=_quote(a, q))
    for a in [x for x in pref if x.get("age_class") == "preference" or x not in exc_ads][:4]:
        t = next((t for t in _terms(a) if t.get("snippet")), None)
        add("exceptions", "ad_fact", "This ad words its age wording as a preference or something that can be relaxed, not as a fixed limit.", [a], quote=_quote(a, t and t["snippet"]))
    if not A["exceptions"]:
        add("exceptions", "rules", ("No exception or relaxation wording was found in the ad." if n == 1 else "No exception or relaxation wording was found in the similar ads.") if n else "No similar ads were found, so no exceptions can be reported.", ads)
    # ---- relates
    if question:
        add("relates", "user_stated", "You asked: “%s”" % (question[:240] + ("…" if len(question) > 240 else "")))
    bits = [("age %d" % profile["age"]) if profile["age"] is not None else None, profile["education"] or None,
            ("%d years of experience" % profile["years_experience"]) if profile["years_experience"] is not None else None,
            profile["occupation"] or None, ("looking in %s" % _region_en(profile["region"])) if profile["region"] else None]
    bits = [b for b in bits if b]
    if bits:
        add("relates", "user_stated", "You said: " + ", ".join(bits) + ".")
    age = profile["age"]
    conf_ads = [a for a in ads if _conflict_snippets(a)]
    if age is not None and with_max:
        lower = [a for a in with_max if _max_age(a) < age]
        if not insufficient:
            add("relates", "rules", "Of the %d ads that state a maximum age, %d state a maximum below the age you entered (%d) and %d %s a maximum equal to or above it. This explains the wording only; it does not say whether you could apply or be considered."
                % (len(with_max), len(lower), age, len(with_max) - len(lower), "states" if len(with_max) - len(lower) == 1 else "state"), with_max, counts=(len(lower), len(with_max)))
        for a in sorted(lower, key=_max_age)[:3]:
            ex = _exceptions(a)
            add("relates", "rules", "This ad states a maximum of %d and you entered %d%s" % (_max_age(a), age, "; it also mentions exception wording, so ask how that is decided." if ex else "; ask how this limit is applied."), [a])
    elif age is None:
        add("relates", "rules", "You did not give an age, so ad age limits are shown but not compared with you.")
    elif n and not conf_ads:
        add("relates", "rules", ("The ad does not state a maximum age" if n == 1 else "None of the similar ads states a maximum age") + ", so there is no age limit to compare with the age you entered.", ads)
    if age is not None and conf_ads:
        add("relates", "rules", "%s contradictory age wording, so %s not compared with the age you entered (%d)." % (
            "This ad has" if len(conf_ads) == 1 else "%d ads have" % len(conf_ads), "it is" if len(conf_ads) == 1 else "they are", age), conf_ads)
    add("relates", "rules", "Your age is used only to explain conditions. No ads are hidden or ranked by it.")
    # ---- cannot
    for u in [x for x in _unclear_from(n, insufficient, exc_ads, amb, status, profile, demo)]:
        add("cannot", "rules", u, [])
    said = set()
    for e in llm_input["evidence"]:
        c = llm.ad_conflicts(e)
        if c:
            ad = next(a for a in ads if a["id"] == e["id"])
            add("cannot", "rules", "This ad's own age wording is contradictory: it %s. Ask the employer which applies." % "; ".join(c), [ad])
            said.add(ad["id"])
    for a in [x for x in ads if _conflict_snippets(x) and x["id"] not in said][:6]:
        add("cannot", "rules", "This ad's own age wording is contradictory: it contains %s. Ask the employer which applies." % _quoted(_conflict_snippets(a)), [a])
    if exc_ads:
        add("cannot", "rules", "Whether an exception would apply to you is not stated in any ad; only the employer can say.", exc_ads)
    add("cannot", "rules", "How age wording is used in screening or selection is not stated in the ads.")
    # ---- ask
    for q in questions:
        add("ask", "rules", q["text"], [x for x in ads if x["id"] in q["evidence_ids"]])
    ids = {i for sec in A.values() for st in sec for i in st["evidence_ids"]}
    index = {a["id"]: _index_entry(a) for a in ads if a["id"] in ids}
    return A, index


def _unclear_from(n, insufficient, exc_ads, amb, status, profile, demo):
    out = []
    if n == 0:
        out.append("No ads matched these filters, so nothing can be said about them. Broaden the search yourself if you wish.")
    elif insufficient:
        out.append("Only %d ad%s matched (fewer than %d): too few to describe any pattern, so no aggregate statements are made." % (n, "" if n == 1 else "s", MIN_ADS))
    if amb:
        out.append("%s %s wording the rules could not interpret with confidence; read the original text." % (_ads(len(amb)), "contains" if len(amb) == 1 else "contain"))
    if status["none"] and n:
        out.append("Where no age requirement was found, the employer may still apply requirements that are not written in the ad.")
    if demo:
        out.append("These example ads are fictional, not real postings.")
    return out


def _region_en(region):
    """English display name for a province value (the original value is still what filters use)."""
    from .evidence import PROVINCES
    for p in PROVINCES:
        if region in (p["name"], p["full"]):
            return p["en"]
    return region


TAG = {"ad_fact": "Ad wording (translated)", "user_stated": "You said", "rules": "AgeLens rules", "model_inference": "Model inference"}


def _en(s):
    """Last guard for the English exports: no Chinese characters leave in Markdown or Word."""
    return gloss.strip_cjk(s) if isinstance(s, str) else s


def to_markdown(b):
    L = ["# AgeLens brief", ""]
    badges = [b["data_label"]] if b.get("data_label") else []
    badges.append(b["model"]["label"] if not b["model"]["ran"] else "Model connected (output checked by code, not guaranteed)")
    L += ["**" + " · ".join(_en(x) for x in badges) + "**", "", "*" + b["disclaimer"] + "*", ""]
    if b["model"]["note"]:
        L += ["> " + b["model"]["note"], ""]
    pasted = b.get("scope", {}).get("basis") == "pasted text"
    if b["insufficient"] and not pasted:
        L += ["> **Few similar ads** (fewer than %d): no claims about patterns are made." % MIN_ADS, ""]
    sm, eq = b.get("summary"), b.get("employer_question")
    if sm:
        L += ["## In short", "", "- " + _en(sm.get("states_en") or sm["states"]), "- " + _en(sm.get("relates_en") or sm["relates"])]
        if eq:
            L += ["- Your question for the employer: " + _en(eq.get("text_en") or eq["text"])]
        L.append("")
    idx = b["evidence_index"]
    for h in b["headings"]:
        L += ["## " + h["title"], ""]
        for st in b["answer"][h["key"]]:
            tag = TAG[st["type"]]
            tail = " [%d of %d ads]" % (st["counts"]["numerator"], st["counts"]["denominator"]) if st.get("counts") else ""
            L.append("- **[%s]** %s%s" % (tag, _en(st.get("text_en") or st["text"]), tail))
            if st.get("quote"):
                L.append("  > Ad wording, in English: %s" % _en(st.get("quote_en") or gloss.quote_en(st["quote"])).replace("\n", " "))
            if st["evidence_ids"] == ["PASTED"]:
                L.append("  - Source: the ad you pasted")
            elif st["evidence_ids"]:
                refs = []
                for i in st["evidence_ids"][:5]:
                    e = idx.get(i, {})
                    src = e.get("source_en") or gloss.source_en(e.get("source"), e.get("is_demo")) or "source n/a"
                    title = e.get("title_en")
                    refs.append("%s%s (%s%s)" % (i, (" · " + _en(title)) if title else "", _en(src), ", " + e["posted_date"] if e.get("posted_date") else ""))
                L.append("  - Evidence: " + "; ".join(refs) + (" and %d more" % (len(st["evidence_ids"]) - 5) if len(st["evidence_ids"]) > 5 else ""))
        L.append("")
    s = b["scope"]
    L += ["## Scope and provenance", "",
          "- Data: %s; data version: %s; rule versions: %s" % (_en(b["data_label"] or "imported data"), _en(s.get("data_version") or "not reported"), ", ".join(s["rule_versions"]) or "n/a"),
          ("- Ads read: 1 (the ad you pasted)" if pasted else "- Similar ads found: %s; read for this brief: %s" % (s["matched_total"], s["ads_analysed"])),
          "- Posting dates: %s" % ((s["date_min"] + " to " + s["date_max"]) if s["date_min"] else "not available"),
          "- Generated: %s (%s)%s" % (b["generated_at"], b["generation_mode"], "; prompt " + b["prompt_version"] if b.get("prompt_version") else ""),
          "- Ad wording is shown as an English gloss of what the rules read; " + ("the pasted text was read in memory and not stored." if pasted else "the original Chinese text is kept in the ad record."),
          "- Tags: Ad wording (translated) = what an ad says, in English; You said = from your input; AgeLens rules = counts and templates computed by fixed rules, not AI" + ("; Model inference = a model's reading, checked by code but not guaranteed." if b["model"]["ran"] else "."),
          "- This brief needs human confirmation against the original ad text before you rely on it.", ""]
    return "\n".join(L)
