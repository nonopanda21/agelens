"""Plain-English display glosses for age wording. Rules only, deterministic, no model.

The age rules (backend/ageparse.py) read the ORIGINAL Chinese text; nothing here changes what they find. This module only
turns what they found into English for display, so the website can show no Chinese at all:

    term_en(term)        -> "Age 35 or under; may be relaxed for outstanding candidates"
    exception_en(text)   -> "may be relaxed to 40 for exceptional candidates"   (generic keyword rules; else "an exception clause")
    class_en(age_class)  -> "Cap with an exception"
    quote_en(quote, terms) -> English rendering of a quoted snippet (the gloss of the terms read from it)
    en_text(text, terms) -> the same sentence with every Chinese “quote” replaced by its gloss and any other Chinese removed

A gloss describes what the rules read; it is not a translation of the whole sentence and never says whether anyone
qualifies. The original wording stays in the existing fields (snippet, quote, exception_text).
"""
import re

CJK = re.compile(r"[㐀-鿿豈-﫿　-〿＀-￯]")
CJK_RUN = re.compile(r"[㐀-鿿豈-﫿　-〿＀-￯][㐀-鿿豈-﫿　-〿＀-￯\d\s\-~～—–]*")

FALLBACK = "Age wording that the rules could not read as a number"
NO_EN = "Wording in the original ad text that has no English rendering here"
CHINESE_TEXT = "[Chinese text]"

CLASS_EN = {"hard_cap": "Hard cap", "cap_with_exception": "Cap with an exception", "preference": "Preference, not a rule",
            "range_or_min": "Range or minimum", "ambiguous": "Unclear wording", "none": "No age wording"}
OCC_EN = {"销售": "Sales", "工程技术": "Engineering", "采购": "Procurement", "客户服务": "Customer service", "物流仓储": "Logistics & warehousing",
          "财务": "Finance", "运营管理": "Operations", "市场营销": "Marketing", "生产制造": "Manufacturing", "行政": "Administration",
          "人力资源": "Human resources", "设计": "Design", "数据分析": "Data analysis", "教育培训": "Education & training",
          "医疗护理": "Healthcare & nursing", "法务合规": "Legal & compliance", "其他": "Other"}
# short occupation words a user may type (e.g. from a Chinese CV) -> English
_WORD_EN = dict(OCC_EN, **{"运营": "Operations", "客服": "Customer service", "物流": "Logistics", "人事": "Human resources",
                           "工程": "Engineering", "市场": "Marketing", "法务": "Legal", "教育": "Education", "医疗": "Healthcare"})
SOURCE_EN = {"合成示例数据": "Simulated data (fictional)", "智联招聘": "Zhaopin"}

# ------------------------------------------------------------------ helpers


def has_cjk(s):
    return bool(s) and isinstance(s, str) and bool(CJK.search(s))


def _n(v):
    try:
        n = int(v)
        return n if 0 < n < 130 else None
    except (TypeError, ValueError):
        return None


def _flags(t):
    return {x.strip() for x in str(t.get("flag") or "").split(",") if x.strip()}


def _cap(s):
    return s[:1].upper() + s[1:] if s else s


def strip_cjk(s, repl=CHINESE_TEXT):
    """Remove Chinese from free text (user input, unknown values): known occupation words are translated, other runs replaced."""
    if not isinstance(s, str) or not has_cjk(s):
        return s
    if s.strip() in _WORD_EN:
        return _WORD_EN[s.strip()]
    out = CJK_RUN.sub(lambda m: _WORD_EN.get(m.group().strip(), repl) + (" " if m.group().endswith(" ") else ""), s)
    out = re.sub(r"(\[Chinese text\][\s,，;；]*){2,}", repl + " ", out)
    return re.sub(r"\s{2,}", " ", out).strip()


# ------------------------------------------------------------------ exception clauses

_WHO = [
    (re.compile(r"特别优秀|特殊优秀|尤其优秀|特别突出|非常优秀|十分优秀"), "exceptional candidates"),
    (re.compile(r"条件优秀|条件好|条件优越|条件特别好|优秀"), "outstanding candidates"),
    (re.compile(r"能力突出|能力强|能力优秀|能力特别|突出"), "candidates with strong ability"),
    (re.compile(r"资深"), "senior candidates"),
    (re.compile(r"(\d{1,2})\s*年(?:及)?以上[^，,。；;]*?经验"), "candidates with {0}+ years of relevant experience"),
    (re.compile(r"职称"), "candidates with a professional title"),
    (re.compile(r"硕士|博士|研究生"), "candidates with a postgraduate degree"),
    (re.compile(r"有经验|经验丰富|相关经验"), "experienced candidates"),
    (re.compile(r"特殊|特别"), "special cases"),
]
_TO = re.compile(r"(?:放宽|放宽至|放宽到|放宽为)\s*(?:至|到)?\s*(\d{2})\s*(?:周岁|岁)?")


def exception_en(text):
    """Generic English rendering of an exception clause, built from keyword rules. Unsure -> "an exception clause"."""
    if not text or not isinstance(text, str):
        return ""
    s = text.strip()
    if not s:
        return ""
    if not has_cjk(s):            # already English (or digits only): never echo arbitrary text back
        return "an exception clause"
    who = None
    for pat, en in _WHO:
        m = pat.search(s)
        if m:
            who = en.format(*m.groups()) if m.groups() else en
            break
    to = _TO.search(s)
    if to and 16 <= int(to.group(1)) <= 70:
        verb = "may be relaxed to %s" % to.group(1)
    elif re.search(r"不限|不受限|无限制", s):
        return "no age limit for " + who if who else "no age limit"
    elif "破格" in s:
        verb = "exceptions may be made"
    elif "放宽" in s:
        verb = "may be relaxed case by case" if "酌情" in s else ("may be relaxed somewhat" if "适当" in s else "may be relaxed")
    elif "考虑" in s:
        verb = "may be considered"
    elif "优先" in s:
        return (who + " preferred") if who else "preferred"
    else:
        return "an exception clause"
    return verb + (" for " + who if who else "")


# ------------------------------------------------------------------ terms

_GEN = re.compile(r"(?<![\d年月日])([5-9]0|[5-9]5|0[05]|10)后")
_VAGUE = [("年富力强", "in the prime of life"), ("年轻化", "a younger team"), ("年轻有为", "young and promising"),
          ("年轻有活力", "young and energetic"), ("年轻人", "young people"), ("年纪轻", "young"), ("年龄偏小", "on the young side"),
          ("年龄偏年轻", "on the young side"), ("年龄适中", "a moderate age"), ("年龄相仿", "a similar age"),
          ("形象年轻", "a youthful appearance"), ("年龄偏大", "on the older side"), ("年轻", "young"), ("青年", "young")]


def _generation(code):
    y = int(code)
    year = (2000 + y) if y <= 10 else (1900 + y)
    return "people born in the %ds" % year if y % 10 == 0 else "people born in or after %d" % year


def _ambiguous_en(t, snip, mx):
    if mx is not None:
        return "Around age %d (approximate wording, not a firm limit)" % mx
    m = _GEN.search(snip)
    if m:
        return "Generation wording (%s), not a stated age limit" % _generation(m.group(1))
    for zh, en in _VAGUE:
        if zh in snip:
            return "Vague age wording (%s), not a number" % en
    if "面谈" in snip or "面议" in snip:
        return "An age requirement is mentioned but left to the interview"
    if re.search(r"(?:年龄|年纪)[^，,。；;]{0,8}\d", snip):
        return "Age wording with a number the rules could not read as a limit"
    if re.search(r"年龄\s*(?:要求|限制)", snip):
        return "An age requirement is mentioned without a number"
    return FALLBACK


def term_en(t, note_conflict=True):
    """One age term (a dict as stored in age_terms / returned by ageparse) -> plain English. Never "you qualify" language."""
    if not isinstance(t, dict):
        return FALLBACK
    kind = t.get("kind")
    mn, mx = _n(t.get("min_age")), _n(t.get("max_age"))
    fl = _flags(t)
    snip = t.get("snippet") if isinstance(t.get("snippet"), str) else ""
    exc = t.get("exception_text") if isinstance(t.get("exception_text"), str) else None
    if "truncated" in fl:
        return "Age wording cut off in the text; no limit could be read"
    if kind == "relaxable":
        if "unlimited" in fl:
            base = "No age limit"
        else:
            e = exception_en(exc or snip)
            base = ("Age requirement " + e) if e.startswith("may") or e.startswith("exceptions") else (
                _cap(e) if e and e != "an exception clause" else "Age wording with an exception clause")
    elif kind == "max" and mx is not None:
        base = "Age %d or under" % mx
    elif kind == "min" and mn is not None:
        base = "Age %d or over" % mn
    elif kind == "range" and mn is not None and mx is not None:
        base = "Ages %d–%d" % (mn, mx)
    elif kind == "preference":
        if mn is not None and mx is not None:
            base = "Ages %d–%d preferred" % (mn, mx)
        elif mx is not None:
            base = "Age %d or under preferred" % mx
        elif mn is not None:
            base = "Age %d or over preferred" % mn
        else:
            base = "Younger applicants preferred"
    elif kind == "ambiguous":
        base = _ambiguous_en(t, snip, mx)
    else:
        return FALLBACK
    if exc and kind in ("max", "min", "range"):
        base += "; " + exception_en(exc)
    if "conflict" in fl and note_conflict:
        base += " (contradicted by other age wording in the same ad)"
    return base


def class_en(age_class):
    return CLASS_EN.get(age_class or "none", "Unclear wording")


def enrich_term(t):
    """Add display fields to one term dict in place (gloss_en, class_en, exception_en). Returns it."""
    if isinstance(t, dict):
        t["gloss_en"] = term_en(t)
        if t.get("age_class"):
            t["class_en"] = class_en(t["age_class"])
        exc = t.get("exception_text")
        t["exception_en"] = (_cap(exception_en(exc)) if exc and not ("unlimited" in _flags(t)) else
                             ("No age limit" if exc else None))
    return t


# ------------------------------------------------------------------ quotes and sentences

def quote_en(quote, terms=None):
    """English rendering of a quoted snippet: the gloss of the terms the rules read from it."""
    if not quote or not isinstance(quote, str):
        return None
    terms = [t for t in (terms or []) if isinstance(t, dict)]
    out = []
    for t in terms:
        if t.get("snippet") == quote:
            out.append(term_en(t, note_conflict=False))     # the sentence around a quote already says it contradicts
    if not out:
        for t in terms:
            if t.get("exception_text") == quote:
                out.append(_cap(exception_en(quote)) if "unlimited" not in _flags(t) else "No age limit")
    if not out:
        from . import ageparse     # rules read the Chinese quote; only the English result is shown
        out = [term_en(t, note_conflict=False) for t in ageparse.parse_age(quote)]
    if not out:
        e = exception_en(quote)
        out = [_cap(e)] if e and e != "an exception clause" else [NO_EN if has_cjk(quote) else quote]
    return "; ".join(dict.fromkeys(out))


_QUOTED = re.compile(r"“([^”]*)”")


def en_text(text, terms=None):
    """A sentence with every Chinese “quote” replaced by its English gloss; any other Chinese is removed."""
    if not isinstance(text, str) or not has_cjk(text):
        return text
    out = _QUOTED.sub(lambda m: "“%s”" % quote_en(m.group(1), terms) if has_cjk(m.group(1)) else m.group(0), text)
    return strip_cjk(out)


# ------------------------------------------------------------------ places, occupations, sources

def province_en(name):
    if not name:
        return None
    from .evidence import PROVINCES
    for p in PROVINCES:
        if name in (p["name"], p["full"], p["en"]):
            return p["en"]
    return strip_cjk(name)


def occupation_en(v):
    if not v:
        return None
    return OCC_EN.get(v) or strip_cjk(v)


def source_en(v, is_demo=False):
    if not v:
        return None
    if v in SOURCE_EN:
        return SOURCE_EN[v]
    if "智联" in v:
        return "Zhaopin"
    if has_cjk(v):
        return "Simulated data (fictional)" if is_demo else "Imported data"
    return v


def city_en(v):
    """Pinyin for the simulated ads' cities (and anything else with an English name); else the Chinese is removed."""
    if not v:
        return None
    return _city_table().get(v) or _city_table().get(re.sub(r"[市区县]$", "", v)) or strip_cjk(v)


_CITY = None


def _city_table():
    global _CITY
    if _CITY is None:
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            import make_sim_data as g
            _CITY = dict(g.CITY_EN)
        except Exception:
            _CITY = {}
        try:
            from .evidence import PROVINCES
            for p in PROVINCES:
                _CITY.setdefault(p["name"], p["en"])
        except Exception:
            pass
    return _CITY


def enrich_ad(d):
    """Add English display fields to an ad summary / detail dict in place. Stored English columns win; the rest is derived."""
    if not isinstance(d, dict):
        return d
    demo = bool(d.get("is_demo"))
    for t in d.get("age_terms") or []:
        enrich_term(t)
    if not d.get("title_en"):
        d["title_en"] = (d.get("title") if d.get("title") and not has_cjk(d.get("title")) else
                         ("Untitled ad" if not d.get("title") else "Ad title in Chinese (no English version stored)"))
    if not d.get("company_en"):
        d["company_en"] = (d.get("company") if d.get("company") and not has_cjk(d["company"]) else
                           ("Company name in Chinese (no English version stored)" if d.get("company") else None))
    if not d.get("city_en"):
        d["city_en"] = city_en(d.get("city"))
    d["province_en"] = province_en(d.get("province"))
    d["occupation_en"] = occupation_en(d.get("occupation"))
    d["source_en"] = source_en(d.get("source"), demo)
    d["age_class_en"] = class_en(d.get("age_class")) if "age_class" in d else None
    if "snippet_highlight" in d:
        hi = d.get("snippet_highlight")
        d["snippet_highlight_en"] = quote_en(hi, d.get("age_terms")) if hi else None
    sents = d.get("age_sentence_en")
    if isinstance(sents, str) and "\n" in sents:
        d["age_sentences_en"] = [s for s in sents.split("\n") if s]
        d["age_sentence_en"] = d["age_sentences_en"][0]
    elif "age_sentence_en" in d:
        d["age_sentences_en"] = [sents] if sents else []
    return d
