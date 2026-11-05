"""What the real recruitment counts say around one pasted ad: for the AI report's "real data" section.
Numbers come from the published aggregates (data/real) by plain lookup; no model writes or sees them. Province x occupation is the
finest level kept, so there is nothing per city. Only fixed wording, category names and numbers reach the page, never ad text.
These are counts of how ads were worded. Nothing here says what an employer does, or whether a person qualifies."""
import re

from . import api_data, api_hetero, gloss, realdata

MIN_ADS = 1000  # below this a share is too noisy to quote
NOTE = ("Counted by code from real recruitment data (2021–2024), not written by AI. These are counts of how ads were worded. "
        "They are not hiring or rejection rates, and they do not tell you what this employer will do.")
_EN_OCC = (("销售", r"\bsales\b"), ("市场营销", r"\bmarketing\b"), ("运营管理", r"\boperations?\b"), ("采购", r"\b(procurement|purchasing|buyer)\b"),
           ("客户服务", r"\bcustomer (service|support)\b"), ("物流仓储", r"\b(logistics|warehouse)\b"), ("财务", r"\b(finance|financial|account(ant|ing)|cashier)\b"),
           ("行政", r"\b(administrative|administration|admin|office assistant)\b"), ("人力资源", r"\b(hr|human resources?|recruiter|recruiting)\b"),
           ("数据分析", r"\bdata anal"), ("设计", r"\bdesigner\b"), ("工程技术", r"\b(engineer|engineering|developer|programmer)\b"),
           ("教育培训", r"\b(teacher|tutor|trainer|instructor)\b"), ("医疗护理", r"\b(nurse|doctor|medical|physician)\b"),
           ("法务合规", r"\b(legal|lawyer|compliance)\b"), ("生产制造", r"\b(manufacturing|production|factory|assembly)\b"))


def _occupation_of(text):
    t = (text or "").strip()
    if not t:
        return None
    if gloss.has_cjk(t):
        occ = realdata.occupation_of(t)
        return None if occ == realdata.OTHER else occ
    return next((occ for occ, rx in _EN_OCC if re.search(rx, t, re.I)), None)


def _job_line(ad_text):
    """The ad's title: its first line or sentence. The body mentions many jobs ("report to the sales manager")."""
    head = (ad_text or "").strip().split("\n")[0]
    return re.split(r"[.。;；!！?？]", head)[0][:80]


def _pct(part, whole):
    return "%.1f%%" % (100.0 * part / whole)


def _median(row):
    m = row.get("median_max_age")
    return int(m) if m and row.get("n_max_age", 0) >= MIN_ADS else None


def build(ad_text, profile, age_class=None, has_exception=False):
    """-> {"scope", "facts": [...], "suggestions": [...], "note"}, or None when there is no data or the group is too small to describe."""
    data = api_data.load_real()
    if not data:
        return None
    profile = profile or {}
    occ = _occupation_of(_job_line(ad_text)) or _occupation_of(profile.get("occupation"))
    prov = profile.get("region") or None
    occ_row = next((r for r in data["occupations"] if r["occupation"] == occ), None) if occ else None
    prov_row = next((r for r in data["provinces"] if r["province"] == prov), None) if prov else None
    cell = next((c for c in data["cells"] if c["province"] == prov and c["occupation"] == occ), None) if occ_row and prov_row else None
    occ_en, prov_en = gloss.occupation_en(occ) if occ_row else None, gloss.province_en(prov) if prov_row else None

    if cell and cell["ads"] >= MIN_ADS:
        row, scope = cell, "%s ads in %s" % (occ_en, prov_en)
    elif occ_row and occ_row["ads"] >= MIN_ADS:
        row, scope = occ_row, "%s ads" % occ_en
    elif prov_row and prov_row["ads"] >= MIN_ADS:
        row, scope = prov_row, "ads in %s" % prov_en
    else:
        return None

    total = data["total"]
    share = row["age_wording"] / row["ads"]
    facts = ["Of {:,} {}, {} mention age, compared with {} of all ads.".format(row["ads"], scope, _pct(row["age_wording"], row["ads"]), _pct(total["age_wording"], total["ads"]))]
    median = _median(row)
    if median:
        facts.append("Where these ads state a maximum age, the median is %d." % median)
    exc = row["with_exception"] / row["explicit"] if row["explicit"] else None
    if exc is not None and row["explicit"] >= MIN_ADS:
        facts.append("%s of the ads stating an age requirement also mention an exception." % _pct(row["with_exception"], row["explicit"]))
    low = None
    if occ_row:  # how far the same occupation varies by region
        here = [(c["age_wording"] / c["ads"], c["province"]) for c in data["cells"] if c["occupation"] == occ and c["ads"] >= MIN_ADS]
        if len(here) >= 2:
            low, high = min(here), max(here)
            facts.append("By region, %s ads mentioning age range from %.1f%% in %s to %.1f%% in %s." % (occ_en, low[0] * 100, gloss.province_en(low[1]), high[0] * 100, gloss.province_en(high[1])))
    bands = (api_hetero.load_hetero() or {}).get("by_experience") or []
    none, senior = next((b for b in bands if b["band"] == "No experience required"), None), next((b for b in bands if b["band"] == "5+ years"), None)
    if none and senior:
        facts.append("Across all ads, %s of those requiring no experience mention age, and %s of those asking for 5+ years." % (_pct(none["age_wording"], none["ads"]), _pct(senior["age_wording"], senior["ads"])))

    tips = []
    if age_class and age_class != "none":
        tips.append("Most %s do not mention age, so it is reasonable to ask how this wording is applied." % scope if share < .5
                    else "Age wording is common in %s, so comparing several ads will tell you more than this one." % scope)
    else:
        tips.append("Silence does not prove there is no condition: %s of %s do mention age." % (_pct(row["age_wording"], row["ads"]), scope))
    if exc is not None and exc < .1:
        tips.append("Few ads like this offer an exception. Ask what would count as one before relying on it." if has_exception
                    else "Exceptions are uncommon in ads like this, so ask directly rather than assume there is flexibility.")
    age = profile.get("age")
    if median and isinstance(age, int) and age > median:
        tips.append("At %d, you are above the median stated maximum for this group. That says nothing about your fit for a job. If you are comparing roles, it may help to look at several ads%s." % (
            age, ", including other regions (wording varies, as above)" if low else ""))
    return {"scope": scope, "facts": facts, "suggestions": tips, "note": NOTE}
