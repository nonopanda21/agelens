"""Small rule set for age wording in ENGLISH text, for the pasted-ad and one-line checks only (people trying the tool
often type an English ad). The real-data aggregate and the audited accuracy figures use backend/ageparse.py alone.
Terms have the same fields and snippet/offset contract as ageparse.parse_age. When in doubt a rule gives an unclear
term (flag near_miss), never a limit. near_miss() is the fallback for either language: age is mentioned but nothing
could be read, so the answer must not say "no age requirement"."""
import re

from .ageparse import _finalize, _flag, _ok, _term

RULE_VERSION = "age-en-1.1.0"

_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60}
_ONES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
_WORDS = r"(?:%s)(?:[- ](?:%s))?\b" % ("|".join(_TENS), "|".join(_ONES))
N = r"(?:\d{2,3}(?![\d,.]*\d)|%s)" % _WORDS
_AGE_NUM = re.compile(r"\d{2,3}|" + _WORDS, re.I)
OLD = r"(?:years?[- ]old|yrs?\.?[- ]old|years? of age|yrs?\.? of age|y/?o\b)"
LOOSE_YEARS = r"(?:years?|yrs?\.?)"
OLD_RE = re.compile(OLD, re.I)
# a number followed by one of these is not an age
UNIT = re.compile(r"\s*(?:%|°|\+?\s*(?:k\b|m\b|people|persons|employees|staff|members|hours?|hrs?|minutes?|mins?|seconds?|secs?|ms\b|days?|"
                  r"weeks?|months?|km|miles?|kg|lbs?|pounds?|cm|mm|inches|degrees?|dollars?|usd|rmb|yuan|euros?|percent|units?|countries|"
                  r"cities|stores|shops|offices|clients|customers|languages|words|pages|points|years?\s+(?:of\s+)?(?:\w+\s+)?experience|"
                  r"years?\s+in\b|years?\s+at\b|years?\s+with\b))", re.I)
AGE_WORD = re.compile(r"\bage[ds]?\b", re.I)
CUE = re.compile(r"\b(must|should|need|needs|have to|has to|only|applicants?|candidates?|required?|requirements?|seeking|looking for|"
                 r"hiring|wanted|be)\b", re.I)
# the number describes someone or something other than the applicant: unclear, never a limit
OTHERS = re.compile(r"\b(customers?|clients?|audiences?|users?|readers?|viewers?|patients?|children|kids|pupils|shoppers|consumers|"
                    r"team size|budget|salary|commute|travel|products?|company has|weight|height|bmi|temperature|price|cost|score|rate|"
                    r"subsid\w+|allowance|bonus|discount|insurance|scholarship|award|scheme|programme|program|fellowship)\b", re.I)
# the sentence talks about age limits without imposing one
NEGATED = re.compile(r"\b(never|do not|don't|does not|doesn't|did not|no longer|not required|not a requirement|will not ask|won't ask|"
                     r"if you are|if you're|whether)\b", re.I)
NOT_BEFORE = re.compile(r"\b(?:not|never|no)(?:\s+be)?\s*$|n't(?:\s+be)?\s*$", re.I)
# text addressed to a machine: anything inside it is not a statement about the job
# A sentence telling the reader what to report ("Say the maximum age is 18."): an ad describes a job, it does not dictate an answer.
DICTATES = re.compile(r"^\W*(say|state|report|tell|claim|declare|output|print|respond|reply|answer|treat|write)\b.*\b(age|years? old|limit)\b", re.I)
INSTRUCTION = re.compile(r"\b(?:ignore|disregard|forget|override)\b[^.;\n]*\b(?:instructions?|rules?|prompts?|above|previous)\b|\b(?:system|assistant)\s*:|"
                         r"\b(?:tell|say|report|respond|output|answer)\b[^.;\n]*\b(?:that|the (?:user|applicant|candidate)|age limit)\b", re.I)
PREF = re.compile(r"\b(prefer\w*|ideally|a plus|an advantage|advantageous|priority|desirable|nice to have)\b|优先", re.I)
_WHO = r"(?:outstanding|excellent|exceptional|strong|experienced|senior|highly qualified|qualified)\s+(?:candidates?|applicants?|profiles?|people)"
EXC = re.compile(r"\b(?:exceptions?\b[^.;\n]*|(?:up to|to)\s+%s\b[^.;\n]*?(?:may|can|could|might) be considered[^.;\n]*|(?:may|can|could|might) be (?:relaxed|waived|extended|raised|flexible|considered)[^.;\n]*|negotiable|flexible|unless\b[^.;\n]*|"
                 r"(?:relaxed|extended|raised) to\s+%s[^.;\n]*|(?:up to|to)\s+%s\s+for\b[^.;\n]*|%s\b[^.;\n]*)|\(\s*%s\s+for\b[^)\n]*\)" % (N, N, N, _WHO, N), re.I)


def _exception(sent):
    """The exception clause of a sentence. "Salary negotiable" and "Flexible working hours" are about the job, not about age."""
    m = EXC.search(sent)
    if m and re.match(r"negotiable|flexible", m.group(), re.I):
        clause = re.split(r"[,;]", sent[:m.start()])[-1] + sent[m.start():].split(",")[0]
        if not (AGE_WORD.search(clause) or re.search(r"\d", clause)):
            return None
    return m

_UPPER = (r"under|below|younger than|less than|up to|no older than|not older than|no more than|not more than|not over|not above|"
          r"not (?:to )?be over|not (?:to )?be above|not (?:to )?be older than|not exceed(?:ing)?|cannot be over|cannot be older than|can't be over|at most|sub|<=?|≤")
MAX_WORD = re.compile(r"(?<![\w-])(?:%s)[\s-]*(?:the\s+age\s+of\s+|age\s+)?%s(?:'?s\b)?(?:\s*%s)?" % (_UPPER, N, OLD), re.I)
MAX_AFTER = re.compile(r"\b%s\s*(?:%s\s*|%s\s*)?(?:or|and|&)\s*(?:younger|under|below|less)\b" % (N, OLD, LOOSE_YEARS), re.I)
MAX_NAMED = re.compile(r"\b(?:(?:maximum|max\.?|upper)\s+age(?:\s+limit)?|age\s+(?:limit|cap|ceiling)|age\s+(?:maximum|max\.?))(?:\s+(?:is|of))?\s*:?\s*(?:set\s+at\s+|at\s+)?%s"
                       r"|\bage\s*:?\s*%s\s*(?:max\.?|maximum)\b|\b(?:max\.?|maximum)\s+%s\s*(?:%s|%s)|\b%s\s*(?:%s\s*|%s\s*)(?:max\.?|maximum)\b" % (N, N, N, OLD, LOOSE_YEARS, N, OLD, LOOSE_YEARS), re.I)
MAX_NEG = re.compile(r"\b(?:no one|nobody|no applicants?|no candidates?)\s+(?:is\s+)?(?:over|above|older than)\s+%s"
                     r"|\b(?:do not|don't|please don't)\s+apply\s+if\s+(?:you are|you're)\s+(?:over|above|older than)\s+%s"
                     r"|\b(?:over|above|older than)\s+%s(?:\s*%s)?(?:'?s)?\s+(?:need not|should not|cannot|can't|do not|don't|will not|won't|are not|not|excluded|ineligible|rejected|will be (?:rejected|excluded)|(?:is|are) not)\b" % (N, N, N, OLD), re.I)
_DASH = r"(?:-|–|—|−|~|～|to|and|through)"
RANGE = [re.compile(r"\b%s\s*(?:and|or)\s*(?:under|below)\s+%s" % (N, N), re.I),
         re.compile(r"\b(?:over|above|at least|older than)\s+%s(?:\s*%s)?\s*(?:and|but|,|&)\s*(?:under|below|younger than|not over|not above)\s+%s" % (N, OLD, N), re.I),
         re.compile(r"\b(?:must|should)\s+be\s+%s\s*%s\s*%s\b" % (N, _DASH, N), re.I),
         re.compile(r"\bage[ds]?\s*:?\s*(?:range|group|bracket|band)?\s*:?\s*(?:is\s+|of\s+)?(?:between\s+|from\s+)?%s\s*%s\s*%s" % (N, _DASH, N), re.I),
         re.compile(r"\b(?:between\s+|from\s+)?%s\s*%s\s*%s\s*(?:%s|%s\b(?!\s+(?:of\s+)?(?:\w+\s+)?(?:experience|in\b|at\b|with\b)))" % (N, _DASH, N, OLD, LOOSE_YEARS), re.I)]
_LOWER = r"at least|over|above|older than|no younger than|not younger than|not be under|not be below|not under|not below|minimum age(?:\s+of)?|min\.? age(?:\s+of)?"
MIN_WORD = re.compile(r"(?<![\w-])(?:%s)\s*:?\s*(?:the\s+age\s+of\s+)?%s(?:\s*%s)?" % (_LOWER, N, OLD), re.I)
MIN_AFTER = re.compile(r"\b%s\s*(?:%s\s*|%s\s*)?(?:or|and)\s*(?:older|over|above)\b|\b%s\+\s*%s" % (N, OLD, LOOSE_YEARS, N, OLD), re.I)
STATED = re.compile(r"\bage[ds]?\s*:?\s*%s\b|\bmust be\s+%s(?:\s*%s)?(?=\s*[.,;!\n]|\s*$)" % (N, N, OLD), re.I)
UNLIMITED = re.compile(r"\b(no (?:upper |maximum |max )?age(?: (?:limit|requirement|restriction|cap)s?)?|no limit on age|regardless of age|any age|all ages|age\s*:?\s*(?:is )?(?:open|unlimited|any|not limited|not (?:a |an )?(?:limit|issue|barrier|requirement)))\b", re.I)
VAGUE = re.compile(r"\b(young|youthful|younger (?:candidates?|applicants?|people|workers?|staff)|digital natives?|recent graduates?|fresh graduates?|new grads?)\b", re.I)
BORN = re.compile(r"\b(born (?:after|since|in or after|in|from) (?:19|20)\d\d|millennials?|gen(?:eration)?[- ]z|post-[789]0s)\b", re.I)
CUT_TAIL = re.compile(r"(?:\b(?:under|below|younger than|no older than|aged?|age limit|maximum age)\s*:?\s*\d?)$", re.I)
# near_miss signals: Chinese with odd spacing or unreadable numbers, and any plain mention of an applicant's age
NEAR = re.compile(r"年\s*[龄齡]|年\s*纪|(?<![0-9])\d+\s*(?:周\s*)?[岁歲](?!月)|[岁歲](?!月)|\bage[ds]?\b(?!\s+(?:of\s+[a-z]|care\b))|"
                  r"\byears?[- ]old\b(?!\s+(?:company|firm|business|brand|startup|start-up|organi[sz]ation))|\bretire\w*\b|"
                  r"\b(?:under|over|below|above)[ -]\d{2}(?!\d)(?!\s*(?:%|k\b|m\b|people|persons|employees|staff|members|hours?|hrs?|minutes?|days?|weeks?|months?|km|miles?|kg|"
                  r"dollars?|usd|rmb|yuan|percent|units?|countries|cities|stores|shops|offices|clients|customers|languages|branches|locations|outlets|sites|projects|products|partners|brands|markets|teams|years?\s+(?:of\s+)?(?:\w+\s+)?experience))", re.I)
# Chinese product or audience lines the Chinese rules read as a limit on the applicant (pasted and one-line checks only)
ZH_AUDIENCE = re.compile(r"(?:适合|针对|面向|服务于?)[^，,。；;\n]{0,20}(?:产品|护肤|化妆品|保险|服装|课程|客群|市场|读者|观众|粉丝)")
_FW = {c: c - 0xFEE0 for c in list(range(0xFF10, 0xFF1A)) + list(range(0xFF21, 0xFF3B)) + list(range(0xFF41, 0xFF5B))}
_WRAP = re.compile(r"(?<=[a-z:])[ \t]*\n[ \t\n]*(?=\d)", re.I)


def _num(s):
    s = s.lower().replace("-", " ")
    if s[0].isdigit():
        return int(s)
    p = s.split()
    return _TENS[p[0]] + (_ONES[p[1]] if len(p) > 1 else 0)


def _ages(s):
    return [_num(x) for x in _AGE_NUM.findall(s)]


def _sentences(text):
    for m in re.finditer(r"[^.!?;\n。；！？]+[.!?;。；！？]?", text):
        if m.group().strip():
            yield m.start(), m.group()


def _numbers(sent, base, skip=None):
    """-> [(term, span)] numeric age terms of one sentence, offsets into the whole text. A number out of range, about
    someone else or in a sentence that does not impose it becomes an unclear term, never a limit. `skip`: the span of an
    exception clause, whose numbers belong to the exception."""
    found, taken = [], [skip] if skip else []

    def add(kind, m, mn=None, mx=None, trusted=False):
        span = (base + m.start(), base + m.end())
        ages = [a for a in (mn, mx) if a is not None]
        cut = r",|;|\band\b|\bbut\b"  # "under 40 and have customer skills" is about the applicant
        near = re.split(cut, sent[:m.start()])[-1] + m.group() + re.split(cut, sent[m.end():])[0]
        if (not all(_ok(a) for a in ages) or OTHERS.search(near) or (kind == "range" and mn >= mx)
                or (not trusted and NEGATED.search(sent))):
            found.append((_term("ambiguous", None, None, "low", None, "near_miss"), span))
        else:
            found.append((_term(kind, mn, mx, "low" if kind == "min" and mn <= 18 else "high"), span))

    def free(m):
        if any(m.start() < e and m.end() > s for s, e in taken):
            return False
        taken.append(m.span())
        return True

    for pat in RANGE:
        for m in pat.finditer(sent):
            a = _ages(m.group())
            if len(a) >= 2 and free(m):
                add("range", m, a[0], a[1])
    for m in MAX_NEG.finditer(sent):
        if free(m):
            add("max", m, None, _ages(m.group())[0], trusted=True)
    for pat in (MAX_NAMED, MAX_AFTER):
        for m in pat.finditer(sent):
            if free(m):
                add("max", m, None, _ages(m.group())[0])
    for pat in (MIN_AFTER,):
        for m in pat.finditer(sent):
            if not re.search(r"\b(?:under|below|younger than)\s*$", sent[:m.start()], re.I) and free(m):
                add("min", m, _ages(m.group())[0])
    for m in MIN_WORD.finditer(sent):
        has_old = OLD_RE.search(m.group())
        if UNIT.match(sent[m.end():]) and not has_old:
            continue
        if re.match(r"over|above|older", m.group(), re.I) and re.search(r"\b(?:not|no)(?:\s+(?:to\s+)?be)?\s*$", sent[:m.start()], re.I):
            continue                        # "not above 35" is an upper limit: MAX_WORD below reads it
        negated = m.group().lower().startswith("not")
        if (has_old or negated or "age" in m.group().lower() or AGE_WORD.search(sent[:m.start()])
                or re.search(r"\b(?:must|should|need to|has to|have to)\s+be\s*$", sent[:m.start()], re.I)
                or re.search(r"\b(?:under|below|younger than)\s+\d", sent, re.I)) and free(m):
            add("min", m, _ages(m.group())[0], trusted=negated)
    for m in MAX_WORD.finditer(sent):
        rest, before = sent[m.end():], sent[:m.start()]
        has_old = OLD_RE.search(m.group())
        if UNIT.match(rest) and not has_old:
            continue
        if NOT_BEFORE.search(before):       # "must not be under 35" handled above; "no under 35s" stays unclear
            if free(m):
                found.append((_term("ambiguous", None, None, "low", None, "near_miss"), (base + m.start(), base + m.end())))
            continue
        if (has_old or AGE_WORD.search(before) or "age" in m.group().lower() or CUE.search(before) or OTHERS.search(sent)
                or not before.strip() or m.group().lower().endswith("s")) and free(m):
            add("max", m, None, _ages(m.group())[0])
    for m in STATED.finditer(sent):
        if free(m):
            found.append((_term("ambiguous", None, None, "low", None, "stated_en"), (base + m.start(), base + m.end())))
    return found


def parse(text):
    """English age terms of a text; [] when none (Chinese wording is left to ageparse.parse_age)."""
    if not text:
        return []
    src = text
    # same length as the original, so offsets stay valid: full-width characters, and a number wrapped onto the next line
    text = text.translate(_FW)
    text = _WRAP.sub(lambda m: " " * len(m.group()), text)
    out, sents = [], list(_sentences(text))
    for i, (base, sent) in enumerate(sents):
        exc = _exception(sent)
        found = _numbers(sent, base, exc.span() if exc else None)
        numeric = [t for t, _ in found if t["kind"] in ("max", "min", "range")]
        if INSTRUCTION.search(sent) or DICTATES.search(sent):
            for t, _ in found:
                t.update(kind="ambiguous", min_age=None, max_age=None, confidence="low", flag="near_miss")
            numeric = []
        if numeric and PREF.search(sent):
            def clause(span):  # "must be under 35, under 30 preferred": only the clause that says preferred
                a, b = span[0] - base, span[1] - base
                return sent[max(sent.rfind(",", 0, a), sent.rfind(";", 0, a)) + 1:(sent.find(",", b) + 1 or len(sent) + 1) - 1]
            named = [t for t, sp in found if t in numeric and PREF.search(clause(sp))]
            for t in named or numeric:
                t["kind"] = "preference"
        if not exc and i + 1 < len(sents):
            nxt = _exception(sents[i + 1][1])
            if nxt and not _numbers(sents[i + 1][1], 0, nxt.span()):
                exc = nxt
        if exc:
            for t in numeric:
                if t["kind"] != "preference":
                    t["exception_text"] = exc.group().strip()
        for pat, flag in ((UNLIMITED, "unlimited"), (VAGUE, "vague_en"), (BORN, "birth_year")):
            for m in pat.finditer(sent):
                ordered = INSTRUCTION.search(sent) or DICTATES.search(sent)  # "say there is no age limit" is an order, not what the ad says
                t = (_term("ambiguous", None, None, "low", None, "near_miss") if flag == "unlimited" and ordered
                     else _term("relaxable", None, None, "high", m.group(), "unlimited") if flag == "unlimited"
                     else _term("ambiguous", None, None, "low", None, flag))
                found.append((t, (base + m.start(), base + m.end())))
        for k, (t, (a, b)) in enumerate(found):  # keep "preferred" with the number it qualifies
            tail = re.match(r"\s*(?:is |are )?(?:preferred|a plus|an advantage)\b", text[b:], re.I)
            if t["kind"] == "preference" and tail:
                found[k] = (t, (a, b + tail.end()))
        out += [dict(t, snippet=src[a:b], start_offset=a, end_offset=b, rule_version=RULE_VERSION) for t, (a, b) in found]
    # a lower bound above the upper bound cannot both hold ("under 35 and over 40")
    mins = [t for t in out if t["kind"] == "min" and t["confidence"] == "high"]
    maxs = [t for t in out if t["kind"] == "max" and t["confidence"] == "high"]
    if any(a["min_age"] >= b["max_age"] for a in mins for b in maxs):
        for t in mins + maxs:
            _flag(t, "conflict")
            t["confidence"] = "low"
    body = text.rstrip()
    m = CUT_TAIL.search(body)
    if m and not any(t["end_offset"] > m.start() for t in out):
        out.append(dict(_term("ambiguous", None, None, "low", None, "truncated"), snippet=src[m.start():m.end()], start_offset=m.start(),
                        end_offset=m.end(), rule_version=RULE_VERSION))
    return _finalize(out)


def near_miss(text):
    """-> an unclear term if the text mentions age in a way no rule could read, else None."""
    m = NEAR.search((text or "").translate(_FW))
    if not m:
        return None
    return _finalize([dict(_term("ambiguous", None, None, "low", None, "near_miss"), snippet=text[m.start():m.end()], start_offset=m.start(),
                           end_offset=m.end(), rule_version=RULE_VERSION)])[0]


def demote_zh_audience(text, terms):
    """A limit read from a Chinese product or audience line ("适合35岁以下女性的护肤产品") becomes unclear."""
    for m in ZH_AUDIENCE.finditer(text):
        for t in terms:
            if t["kind"] in ("max", "min", "range") and m.start() <= t["start_offset"] < m.end():
                t.update(kind="ambiguous", min_age=None, max_age=None, confidence="low", exception_text=None, flag="near_miss")
    return terms
