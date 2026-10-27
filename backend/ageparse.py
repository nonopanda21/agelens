"""Rule-based extraction of age wording from Chinese job-ad text.

Flags recruitment WORDING for a human to interpret. It is not a legal conclusion.
Every term keeps the exact original phrase (`snippet`) and offsets into the UNALTERED description:
    description[start_offset:end_offset] == snippet
Round 2 adds `age_class` (hard_cap | cap_with_exception | preference | range_or_min | ambiguous | none) per term
and per ad, a 'preference' term kind (e.g. 35岁以下优先: NOT a hard limit), truncated-text detection (flag 'truncated',
never invents a cap) and conflict detection (flag 'conflict': both terms kept, demoted to low confidence).
Work-experience phrases (工作经验3-5年, 5年以上工作经验) are never age: every numeric rule needs 岁/周岁
or an explicit 年龄 prefix, and a following 年/个月 vetoes the prefix-only form.
"""
import re

RULE_VERSION = "age-rules-2.0.0"

AGE = r"(\d{2})"
UNIT = r"\s*(?:周岁|岁)"
SEP = r"\s*(?:-|~|～|—|–|－|－|至|到|~)\s*"
NOTUNIT = r"(?!\s*(?:年|个月|月|k|K|w|W|元|\d|%|人|天|小时))"
PRE = r"(?:年龄|年纪)\s*(?:要求|范围|限制)?\s*[:：]?\s*(?:在|为|限)?\s*"

RANGE = [
    re.compile(AGE + SEP + AGE + UNIT + r"(?:之间|区间|范围)?"),
    re.compile(PRE + AGE + SEP + AGE + NOTUNIT),
    re.compile(r"(?:年满|满)\s*" + AGE + UNIT + r"\s*(?:至|到|-|~)\s*" + AGE + UNIT),
]
MAX = [
    re.compile(r"(?:不超过|不得超过|不大于|不高于|最高|不要超过|低于|小于)\s*" + AGE + r"\s*(?:周岁|岁)?(?:\s*\(含\)|（含）)?"),
    re.compile(AGE + UNIT + r"\s*(?:\(含\)|（含）)?\s*(?:及以下|以下|以内|之内|之下|为限)"),
    re.compile(r"(?:限|仅限)\s*" + AGE + UNIT + r"(?!\s*以上)"),
    re.compile(PRE + AGE + r"\s*(?:周岁|岁)?\s*(?:及以下|以下|以内|之内)"),
    re.compile(r"(?:不满)\s*" + AGE + UNIT),
]
MIN = [
    re.compile(r"(?:不低于|不小于|不少于|年满|满|至少)\s*" + AGE + UNIT + r"(?!\s*(?:至|到|-|~|以下|以内))(?:\s*(?:及以上|以上))?"),
    re.compile(AGE + UNIT + r"\s*(?:\(含\)|（含）)?\s*(?:及以上|以上|起)"),
    re.compile(PRE + AGE + r"\s*(?:周岁|岁)?\s*(?:及以上|以上)"),
]
UNLIMITED = re.compile(r"(?:不限年龄|年龄不限|年龄无限制|年龄无要求|无年龄(?:限制|要求)|年龄(?:要求)?不限|年龄(?:上)?(?:没有|无)(?:限制|要求)|不限年纪)")
EXCEPT = re.compile(
    r"[^，,、；;。\n]*?(?:优秀|突出|特殊|特别|有经验|能力强|资深|条件好|条件优越)[^，,、；;。\n]*?(?:可|可以|能|予以|酌情|适当|亦可|也可)?[^，,、；;。\n]*?(?:放宽|不限|破格|考虑|优先)[^，,、；;。\n]*"
    r"|[^，,、；;。\n]*?(?:年龄|岁)[^，,、；;。\n]*?(?:可|可以|能|予以|酌情|适当)[^，,、；;。\n]*?(?:放宽|放宽至|适当放宽)[^，,、；;。\n]*"
    r"|[^，,、；;。\n]*?(?:酌情|适当|可适当|可以适当)放宽[^，,、；;。\n]*")
EXC_VETO = re.compile(r"学历|学位|专业|经验|证书|户籍|性别|薪资|薪酬|身高")
GENERATION = re.compile(r"(?<![\d年月日])(?:[5-9]0|[5-9]5|0[05]|10)后(?![一-鿿A-Za-z]{0,0}[续勤])")
VAGUE = re.compile(r"年富力强|年轻化|年轻人|年轻有为|年纪轻|年龄偏小|年龄适中|年龄相仿|形象年轻|年龄偏年轻|年龄偏大")
BARE = re.compile(r"年龄\s*(?:要求|限制)")
ABOUT = re.compile(AGE + UNIT + r"\s*(?:左右|上下|前后)")

# preference wording: "35岁以下优先", "优先考虑35岁以下", "年轻有活力优先"
PREF_AFTER = re.compile(r"\s*(?:者|的|人员|人士|应聘者|候选人)?\s*(?:均?可)?\s*(?:优先|更佳|为宜|最佳|更优|佳)")
PREF_BEFORE = re.compile(r"(?:优先(?:考虑|录用|选择)?|倾向于?)\s*(?:年龄)?\s*(?:在|为)?\s*$")
PREF_VAGUE = [
    re.compile(r"(?:年轻|年纪轻|年龄(?:偏)?(?:小|轻)|青年)[^，,。；;！!\n]{0,8}?优先"),
    re.compile(r"优先(?:考虑|录用)?\s*(?:年轻|年纪轻|青年)[^，,。；;\n]{0,6}"),
]
# text that stops mid age clause at the very end of the description
TRUNC_TAIL = re.compile(
    r"(?:(?:年龄|年纪)\s*(?:要求|范围|限制)?\s*[:：]?\s*(?:在|为|限|不超过|不得超过|不超|不大于)?\s*"
    r"(?:\d{1,2}\s*(?:(?:周岁|岁)\s*(?:\(含\)|（含）)?\s*(?:及以|以|及|不|不超)|$)|$)"
    r"|(?:仅限|限)\s*\d{1,2}\s*(?:(?:周岁|岁)\s*(?:及以|以|及)|$)"
    r"|(?:不超过|不得超过|不大于)\s*\d{0,2}"
    r"|\d{1,2}\s*(?:周岁|岁)\s*(?:\(含\)|（含）)?\s*(?:及以|以|及))\s*$")
GENDER = re.compile(r"[男女]")

_SENT = re.compile(r"[^。；;！!？?\n\r]+")
_MARK = re.compile(r"^[\s　]*(?:[①-⑩]|[（(]?\d{1,2}(?:[)）、]|[.．](?!\d))\s*|[-•·●▪*]\s*)?[\s　]*")
_LISTSPLIT = re.compile(r"(?=[①-⑩])")


def _ok(n):
    return 16 <= n <= 70


def _sentences(text):
    for m in _SENT.finditer(text):
        base, seg = m.start(), m.group()
        cuts = [0] + [x.start() for x in _LISTSPLIT.finditer(seg) if x.start() > 0] + [len(seg)]
        for a, b in zip(cuts, cuts[1:]):
            s = seg[a:b]
            lead = _MARK.match(s).end()
            e = len(s.rstrip())
            if e > lead:
                yield base + a + lead, base + a + e


def _narrow(text, s, e, spans):
    """For long run-on sentences, shrink to the comma clauses holding the matched spans."""
    if e - s <= 90:
        return s, e
    bounds, last = [], s
    for m in re.finditer(r"[，,]", text[s:e]):
        bounds.append((last, s + m.start())); last = s + m.end()
    bounds.append((last, e))
    lo, hi = e, s
    for a, b in bounds:
        if any(x < b and y > a for x, y in spans):
            lo, hi = min(lo, a), max(hi, b)
    while lo < hi and text[lo] in " 　": lo += 1
    return (lo, hi) if lo < hi else (s, e)


def _find(pats, sent, taken):
    for p in pats:
        for m in p.finditer(sent):
            sp = m.span()
            if any(sp[0] < t1 and sp[1] > t0 for t0, t1 in taken):
                continue
            yield m


def _term(kind, mn, mx, conf="high", exc=None, flag=None):
    return {"kind": kind, "min_age": mn, "max_age": mx, "confidence": conf, "exception_text": exc, "flag": flag}


def _is_pref(sent, span):
    return bool(PREF_AFTER.match(sent[span[1]:span[1] + 14]) or PREF_BEFORE.search(sent[max(0, span[0] - 12):span[0]]))


def parse_age(text):
    """Return list of age terms (dicts) in document order. Never mutates `text`."""
    if not text:
        return []
    out = []
    for s, e in _sentences(text):
        sent = text[s:e]
        taken, found = [], []  # found: (term, span)

        def add(term, span):
            taken.append(span); found.append((term, span))

        for m in _find(RANGE, sent, taken):
            a, b = int(m.group(1)), int(m.group(2))
            if _ok(a) and _ok(b) and a <= b:
                add(_term("range", a, b), m.span())
        for m in _find(MAX, sent, taken):
            n = int(m.group(1))
            if not _ok(n):
                continue
            if "不满" in m.group():
                n -= 1
            add(_term("max", None, n), m.span())
        for m in _find(MIN, sent, taken):
            n = int(m.group(1))
            if _ok(n):
                add(_term("min", n, None, "low" if n <= 18 else "high"), m.span())
        for m in _find([ABOUT], sent, taken):
            n = int(m.group(1))
            if _ok(n):
                add(_term("ambiguous", None, n, "low"), m.span())
        # numeric wording followed/preceded by 优先: a preference, not a hard limit
        for i, (t, sp) in enumerate(list(found)):
            if t["kind"] in ("max", "min", "range") and _is_pref(sent, sp):
                found[i] = (dict(t, kind="preference"), sp)
        for pat in PREF_VAGUE:
            for m in pat.finditer(sent):
                if not any(m.start() < t1 and m.end() > t0 for t0, t1 in taken):
                    add(_term("preference", None, None, "low"), m.span())
        for m in UNLIMITED.finditer(sent):
            add(_term("relaxable", None, None, "high", m.group(), "unlimited"), m.span())
        for m in GENERATION.finditer(sent):
            add(_term("ambiguous", None, None, "low"), m.span())
        for m in VAGUE.finditer(sent):
            if not any(m.start() < t1 and m.end() > t0 for t0, t1 in taken):
                add(_term("ambiguous", None, None, "low"), m.span())

        # merge a lone min + max in one sentence into a range
        mins = [f for f in found if f[0]["kind"] == "min" and f[0]["confidence"] == "high"]
        maxs = [f for f in found if f[0]["kind"] == "max"]
        if len(mins) == 1 and len(maxs) == 1 and mins[0][0]["min_age"] <= maxs[0][0]["max_age"]:
            rng = _term("range", mins[0][0]["min_age"], maxs[0][0]["max_age"])
            sp = (min(mins[0][1][0], maxs[0][1][0]), max(mins[0][1][1], maxs[0][1][1]))
            found = [f for f in found if f not in (mins[0], maxs[0])] + [(rng, sp)]
        # conflicting numbers for different genders: keep but flag low confidence
        if "男" in sent and "女" in sent and len({f[0]["max_age"] for f in found if f[0]["max_age"]}) > 1:
            for t, _ in found:
                t["confidence"] = "low"

        exc = None
        for m in EXCEPT.finditer(sent):
            txt = m.group().strip(" ，,、:：")
            if txt and not EXC_VETO.search(txt) and not any(m.start() < t1 and m.end() > t0 and t["kind"] != "relaxable" for t, (t0, t1) in found):
                exc = (txt, m.span())
                break
        numeric = [f for f in found if f[0]["kind"] in ("range", "max", "min")]
        if exc:
            if numeric:
                for t, _ in numeric:
                    t["exception_text"] = exc[0]
            elif ("年龄" in sent or "岁" in sent):
                found.append((_term("relaxable", None, None, "high", exc[0]), exc[1]))
            elif out and out[-1].get("_sent_end") is not None and 0 <= s - out[-1]["_sent_end"] <= 3 \
                    and out[-1]["kind"] in ("range", "max", "min") and not out[-1]["exception_text"]:
                out[-1]["exception_text"] = exc[0]
        if not found and BARE.search(sent):
            m = BARE.search(sent)
            found.append((_term("ambiguous", None, None, "low"), m.span()))
        if not found:
            continue
        spans = [(s + a, s + b) for _, (a, b) in found]
        ss, ee = _narrow(text, s, e, spans)
        # attached exception text may live in a neighbouring clause: widen to include it
        if exc and numeric and not (ss <= s + exc[1][0] and s + exc[1][1] <= ee):
            ss, ee = min(ss, s + exc[1][0]), max(ee, s + exc[1][1])
        for t, _ in sorted(found, key=lambda f: f[1][0]):
            d = dict(t)
            d.update(snippet=text[ss:ee], start_offset=ss, end_offset=ee, rule_version=RULE_VERSION, _sent_end=e)
            out.append(d)
    for d in out:
        d.pop("_sent_end", None)
    out = _truncation(text, out)
    # one row per distinct (kind, ages, snippet)
    seen, uniq = set(), []
    for d in out:
        k = (d["kind"], d["min_age"], d["max_age"], d["start_offset"], d["end_offset"], d["exception_text"])
        if k not in seen:
            seen.add(k); uniq.append(d)
    return _finalize(uniq)


def _truncation(text, out):
    """If the description stops mid age clause, drop any cap read from the fragment and add an ambiguous term."""
    body = text.rstrip()
    m = TRUNC_TAIL.search(body)
    if not m:
        return out
    tail = m.group()
    if not (re.search(r"\d", tail) or re.search(r"[:：]\s*$|不超过?$|不得超过$|限$", tail)):
        return out
    ts, te = m.start(), len(body)
    if any(d["kind"] == "relaxable" and d["start_offset"] <= ts < d["end_offset"] for d in out):
        return out
    out = [d for d in out if not (d["start_offset"] < te and d["end_offset"] > ts)]
    cut = max(body.rfind(c, 0, ts) for c in "\n。；;，,")
    ss = cut + 1
    while ss < ts and body[ss] in " 　":
        ss += 1
    out.append(dict(_term("ambiguous", None, None, "low", None, "truncated"), snippet=body[ss:te],
                    start_offset=ss, end_offset=te, rule_version=RULE_VERSION))
    return out


def _flag(t, name):
    f = [x for x in (t.get("flag") or "").split(",") if x]
    if name not in f:
        f.append(name)
    t["flag"] = ",".join(f)


def term_class(t):
    """Class of one term. A term demoted to low confidence never counts as a hard limit."""
    hi = t.get("confidence") == "high"
    k = t.get("kind")
    if "conflict" in (t.get("flag") or "") or "truncated" in (t.get("flag") or ""):
        return "ambiguous"
    if k == "preference":
        return "preference"
    if k == "max" and hi:
        return "cap_with_exception" if t.get("exception_text") else "hard_cap"
    if k in ("range", "min") and hi:
        return "range_or_min"
    if k == "relaxable" and "unlimited" in (t.get("flag") or ""):
        return "none"
    return "ambiguous"


def _finalize(terms):
    hard = [t for t in terms if t["kind"] in ("max", "range") and t["confidence"] == "high" and t["max_age"]]
    unlimited = [t for t in terms if "unlimited" in (t.get("flag") or "")]
    numeric = [t for t in terms if t["kind"] in ("max", "range", "min") and t["confidence"] == "high"
               and (t["max_age"] or (t["min_age"] or 0) > 18)]
    bad = []
    if len({t["max_age"] for t in hard}) > 1:
        bad += hard                       # two different caps
    if unlimited and numeric:
        bad += unlimited + numeric        # 不限年龄 together with a numeric limit
    for t in bad:
        _flag(t, "conflict")
        t["confidence"] = "low"
    for t in terms:
        t["age_class"] = term_class(t)
    return terms


def has_conflict(terms):
    return any("conflict" in (t.get("flag") or "") for t in terms)


def ad_class(terms):
    """Ad-level class from its terms: cap_with_exception > hard_cap > range_or_min > preference > ambiguous > none.
    A conflicting ad is 'ambiguous' (both terms are kept and flagged)."""
    if not terms:
        return "none"
    if has_conflict(terms):
        return "ambiguous"
    cl = {term_class(t) for t in terms}
    for c in ("cap_with_exception", "hard_cap", "range_or_min", "preference", "ambiguous"):
        if c in cl:
            return c
    return "none"


def age_status(terms):
    """'explicit' = a high-confidence numeric limit (min >18, max, or range);
    'uncertain' = age wording present but no usable numeric limit (generation, vague, unlimited, bare 18+);
    'none' = no age wording found."""
    if not terms:
        return "none"
    for t in terms:
        if t["confidence"] == "high" and t["kind"] in ("max", "range", "min") and (t["max_age"] or (t["min_age"] or 0) > 18):
            return "explicit"
    return "uncertain"
