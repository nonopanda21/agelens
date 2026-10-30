"""Rule-based extraction of age wording from Chinese job-ad text.

Flags recruitment WORDING for a human to interpret. It is not a legal conclusion.
Every term keeps the exact original phrase (`snippet`) and offsets into the UNALTERED description:
    description[start_offset:end_offset] == snippet
Round 2 adds `age_class` (hard_cap | cap_with_exception | preference | range_or_min | ambiguous | none) per term
and per ad, a 'preference' term kind (e.g. 35岁以下优先: NOT a hard limit), truncated-text detection (flag 'truncated',
never invents a cap) and conflict detection (flag 'conflict': both terms kept, demoted to low confidence).
Work-experience phrases (工作经验3-5年, 5年以上工作经验) are never age: every numeric rule needs 岁/周岁
or an explicit 年龄 prefix, and a following 年/个月 vetoes the prefix-only form.

CANDIDATE B (recall-first, "age-rules-2.1.0"). Changes against age-rules-2.0.0 are marked in comments:
  [F1] salary / other digits read as an age (最高6000元 -> 60, 不低于4500 -> 45, 不低于25岁 -> max 25)
  [F2] ranges with unusual separators or 岁 on both ends (18岁至32岁, 20——35岁, 18一35岁, 25岁-40岁)
  [F3] team / company wording flagged as age wording (团队年轻化, 90后小伙伴, 平均年龄)
  [F4] graduate-cohort wording (应届, 毕业3年以内, 22届): NOT an age term; reported by parse_cohort() only
  [R]  further recall: Chinese numerals, 岁内, （含35周岁）, ≤/＜, 上限, "35岁以上勿扰", line-break splits,
       birth-year conditions (1985年以后出生), stated age (年龄：30岁), 九零后
Public API and term fields are unchanged; parse_cohort() is an extra function.
"""
import re

RULE_VERSION = "age-rules-2.1.0"

# [F1] the age number must end there: no digit directly after it, and not the tail of a 3+-digit number
#      (4500 / 6000 no longer give 45 / 60). One digit before is allowed: a glued list number ("116-35岁" = 1、16-35岁).
# [R]  Chinese-numeral ages (十八, 三十五, 四十) are accepted in the same group and converted by _num().
_CN_AGE = r"[一二三四五六七]?十[一二三四五六七八九]?"
AGE = (r"((?<!\d\d)\d{2}(?!\d)|(?<![一二三四五六七八九十百千万零〇两])" + _CN_AGE
       + r"(?![一二三四五六七八九十百千万零〇]))")
UNIT = r"\s*(?:岁周岁|周岁|岁|週歲|歲)"   # [R] also the doubled typo 35岁周岁以下
# [F2] any dash-like character, repeated (——, --, ―, ～, 〜, ∼, －, −), plus 至 / 到 and the typed-dash 一 (18一35岁)
_DASH = r"[-‐‑‒–—―−﹣－─~～〜∼_]"
SEP = r"\s*(?:" + _DASH + r"(?:\s{0,3}" + _DASH + r"){0,5}|至|到|一)\s*"   # also "18- -35岁", "21_65周岁"
# [R] no "\d" here: AGE already refuses a following digit, and "年龄：25-30 2、学历" (next list item) must still match
NOTUNIT = r"(?!\s*(?:年|个月|月|k|K|w|W|元|%|人|天|小时|万|千|块|cm|CM|厘米|公斤|kg|KG|斤|届|级|号|期))"
# [F3] "平均年龄" describes the team, never the applicant; [R] HTML tags between 年龄： and the number are skipped
PRE = r"(?<!平均)(?:年龄|年纪|年齡)\s*(?:要求|范围|限制|段|上限|区间|需求|条件|状况)?\s*[:：]?(?:\s|<[^<>]{0,12}>)*(?:在|为|限|需在|须在)?\s*"
_INCL = r"(?:\s*[（(]\s*不?含[^）)]{0,6}[）)])?"   # [R] 35周岁（含）以下, 35周岁(含35周岁)以下
# [R] second age of a 年龄-prefixed range may be glued to the next list number: "年龄：28-452、学历" -> 28-45
AGE_END = r"((?<!\d\d)\d{2}(?:(?!\d)|(?=\d[、.．)）]))|" + _CN_AGE + r"(?![一二三四五六七八九十百千万零〇]))"

RANGE = [
    # [F2] first 岁 optional: 18岁至32岁, 25岁-40岁, 18周岁～35周岁; also 18-35岁内
    re.compile(AGE + r"(?:" + UNIT + r")?" + _INCL + SEP + AGE + UNIT + r"(?:之间|区间|范围|以内|之内|内)?"),
    re.compile(PRE + AGE + r"(?:" + UNIT + r")?" + _INCL + SEP + AGE_END + NOTUNIT),
    re.compile(r"(?:年满|满)\s*" + AGE + UNIT + SEP + AGE + UNIT),
    # [R] 18＜年龄＜35, 18≤年龄≤35
    re.compile(AGE + r"(?:" + UNIT + r")?\s*(?:<=|≤|<|＜)\s*(?:年龄|年纪)\s*(?:<=|≤|<|＜)\s*" + AGE),
]
# [R] explicit refusals: "35岁以上勿扰" is a cap, "18岁以下勿扰" / "未满18周岁不予录用" a minimum
_REFUSE = r"\s*(?:的|者|人员|人士)?\s*(?:请)?(?:勿扰|免谈|不予?考虑|谢绝|勿投|勿应聘|莫扰|不予?录用|不招|不要)"
NEG = [
    (re.compile(AGE + UNIT + _INCL + r"\s*(及?以上|及?以下)" + _REFUSE), None),
    (re.compile(r"(?:超过|大于|高于)\s*" + AGE + UNIT + _REFUSE), "max"),
    (re.compile(r"(?:未满|不满|小于|低于)\s*" + AGE + UNIT + _REFUSE), "min"),
]
MAX = [
    # [F1] 低于/小于 not when part of 不低于/不小于 (that is a MINIMUM); NOTUNIT after the number; unit captured in
    # group 2 -- a unit-less match also needs 年龄/年纪 just before it (checked in parse_age).
    # [R] 不能超过, 不超, 最大, ≤, ＜, 上限
    re.compile(r"(?:不超过|不得超过|不能超过|不可超过|不超|不大于|不高于|最高|最大|不要超过|(?<![不未])低于|(?<![不未])小于"
               r"|小于等于|≤|<=|＜|<|上限(?:为|是)?)\s*" + AGE + r"\s*(周岁|岁|週歲|歲)?(?:\s*\(含\)|\s*（含）)?" + NOTUNIT
               + r"(?!\s*(?:[-‐‑‒–—―−﹣－─~～〜∼]|至|到)\s*\d)"),   # [R] 年龄上限18-45 is a range, not max 18
    # [R] 岁内 / 及下 and the （含…） forms
    re.compile(AGE + UNIT + _INCL + r"\s*(?:及以下|或以下|以下|以内|之内|之下|为限|及下|一下|内)"),   # [R] 或以下, typo 一下
    re.compile(r"(?:限|仅限|限于)\s*" + AGE + UNIT + r"(?!\s*(?:以上|及以上))"),
    re.compile(PRE + AGE + r"\s*(?:周岁|岁)?" + _INCL + r"\s*(?:及以下|以下|以内|之内|内)"),
    # [R] 未满 as well as 不满; NN <= 18 is a legal-minimum prohibition (min, handled in parse_age)
    re.compile(r"(?:不满|未满)\s*" + AGE + UNIT),
]
MIN = [
    # [R] 大于 / ≥
    re.compile(r"(?:不低于|不小于|不少于|大于等于|≥|>=|年满|满|至少|大于)\s*" + AGE + UNIT
               + r"(?!\s*(?:至|到|-|~|以下|以内))(?:\s*(?:及以上|以上))?"),
    re.compile(AGE + UNIT + _INCL + r"\s*(?:及以上|或以上|以上|起)"),
    re.compile(PRE + AGE + r"\s*(?:周岁|岁)?\s*(?:及以上|以上)"),
]
UNLIMITED = re.compile(r"(?:不限年龄|年龄不限|年龄无限制|年龄无要求|无年龄(?:限制|要求)|年龄(?:要求)?不限|年龄(?:上)?(?:没有|无)(?:限制|要求)|不限年纪)")
EXCEPT = re.compile(
    r"[^，,、；;。\n]*?(?:优秀|突出|特殊|特别|有经验|能力强|资深|条件好|条件优越)[^，,、；;。\n]*?(?:可|可以|能|予以|酌情|适当|亦可|也可)?[^，,、；;。\n]*?(?:放宽|不限|破格|考虑|优先)[^，,、；;。\n]*"
    r"|[^，,、；;。\n]*?(?:年龄|岁)[^，,、；;。\n]*?(?:可|可以|能|予以|酌情|适当)[^，,、；;。\n]*?(?:放宽|放宽至|适当放宽)[^，,、；;。\n]*"
    r"|[^，,、；;。\n]*?(?:酌情|适当|可适当|可以适当)放宽[^，,、；;。\n]*"
    # [R] "（身体健康可放宽到50岁内）": a relaxation that names a new age is an exception, not a second cap
    r"|[^，,、；;。\n（(]*?放宽(?:年龄)?(?:到|至|为)\s*\d{2}\s*(?:周岁|岁)[^，,、；;。\n）)]*")
EXC_VETO = re.compile(r"学历|学位|专业|经验|证书|户籍|性别|薪资|薪酬|身高")
# [R] Chinese-numeral generations (九零后, 八五后)
GENERATION = re.compile(r"(?<![\d年月日])(?:[5-9]0|[5-9]5|0[05]|10|[五六七八九][零〇五]|零零|零五)后(?![续勤])")
VAGUE = re.compile(r"年富力强|年轻化|年轻人|年轻有为|年纪轻|年龄偏小|年龄适中|年龄相仿|形象年轻|年龄偏年轻|年龄偏大")
BARE = re.compile(r"年龄\s*(?:要求|限制)")
ABOUT = re.compile(AGE + UNIT + r"\s*(?:左右|上下|前后)|" + PRE + AGE + r"\s*(?:左右|上下)")   # [R] 年龄30左右
# [R] a bare stated age ("年龄：30岁") with no qualifier: kept as low-confidence ambiguous wording
STATED = re.compile(PRE + AGE + UNIT + r"(?!\s*(?:以|及|左右|上下|前后|起|内|之|[-~～—至到]))")
# [R] birth-date conditions (1985年以后出生): age wording, but the cut-off age depends on the posting date -> ambiguous
BIRTH = re.compile(r"(?<!\d)(?:19[5-9]\d|20[01]\d)\s*年(?:\s*\d{1,2}\s*月(?:\s*\d{1,2}\s*日)?)?\s*(?:\(含\)|（含）)?"
                   r"\s*(?:及?以后|之后|以前|之前|后|前)?\s*(?:出生|生人)")
# [R] retirement-distance conditions ("距法定退休年龄10年以上") are an indirect age cap -> ambiguous
RETIRE = re.compile(r"(?:距|距离)\s*(?:法定)?\s*退休(?:年龄)?\s*(?:不少于|不低于|至少|还有|有)?\s*\d{1,2}\s*年")
# [F3] low-confidence generation / vague terms describing the team or company, not the applicant, are dropped...
TEAM = re.compile(r"团队|同事|小伙伴|伙伴|员工|氛围|平均年龄|公司|我们|大家庭|集体|成员|老板|领导|队伍|店长|副总|企业|文化|"
                  r"主力|居多|为主|占比|部门|管理层|骨干|一群|都是|也能|也可以")
# ...unless the same stretch also states a requirement or invitation to the applicant
REQ = re.compile(r"要求|限|以下|以内|优先|欢迎|招聘|招收|招募|应聘|希望|需|须|适合|寻找|面向|诚聘|招|期待|渴望|期望")
# [R] a number inside the relaxation clause ("可放宽到50岁内") belongs to the exception, not a second limit
RELAX_BEFORE = re.compile(r"放宽(?:年龄)?(?:到|至|为)?\s*$")
# [R] ages of pupils / customers are not a condition on the applicant ("针对18-35岁女性用户", "教授16-18岁学生")
CUST_AFTER = re.compile(r"\s*(?:的)?\s*(?:儿童|孩子|小孩|宝宝|幼儿|小朋友|青少年|少儿|青少儿|用户|客户|人群|学员|患者|顾客|消费者|老人|会员|学龄)")
AUD_BEFORE = re.compile(r"(?:面向|针对|教授|辅导|专注于?)[^，,。；;]{0,6}$")
# [F4] graduate-cohort wording, reported separately by parse_cohort(); never part of parse_age()
COHORT = re.compile(r"应届(?:毕业)?生?|往届(?:毕业)?生?|毕业(?:当年|\s*[一二三两1-5]\s*年(?:以内|之内|内))"
                    r"|(?<![\d第])(?:20)?[12]\d(?:\s*[/、,，-]\s*(?:20)?[12]\d)*\s*届(?:毕业生|应届生?|学生|大学生|校招|生)?")

# preference wording: "35岁以下优先", "优先考虑35岁以下", "年轻有活力优先"
PREF_AFTER = re.compile(r"\s*(?:者|的|人员|人士|应聘者|候选人)?\s*(?:均?可)?\s*(?:优先|更佳|为宜|最佳|更优|佳)")
# [R] 最好 / 最好是 before the number is a preference too
# [R] ...but not the 优先 that closes a previous clause ("有客服经验优先  年龄18-40岁" is not a preference)
PREF_BEFORE = re.compile(r"(?:(?<![者验的历业士生人])优先(?:考虑|录用|选择)?|倾向于?|最好(?:是)?)\s*(?:年龄)?\s*(?:在|为)?\s*$")
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
# [R] an age clause split by a line break ("年龄：\n25-35岁", "35岁\n以下", "25-\n35岁") is read as one sentence
_JOIN_L = re.compile(r"(?:(?:年龄|年纪)\s*(?:要求|范围|限制)?\s*[:：]?\s*(?:在|为|限|不超过|不得超过|不大于)?"
                     r"|(?<!\d)\d{2}\s*(?:周岁|岁)|(?<!\d)\d{2}\s*[-~～—至到])\s*$")
_JOIN_R = re.compile(r"[\s　]*(?:\d{2}|[一二三四五六七]?十|以|及|内|\(含|（含|[-~～—至到])")
_GAP = re.compile(r"[\s　]*\Z")
# [speed] a sentence with none of these characters cannot yield a term (every rule needs one of them)
_TRIG = re.compile(r"[岁歲龄齡纪后轻富青生休]")

_CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _num(s):
    """[R] '35' / '３５' / '三十五' / '十八' -> int."""
    if s[0] in _CN or s[0] == "十":
        a, _, b = s.partition("十")
        return _CN.get(a, 1) * 10 + _CN.get(b, 0)
    return int(s)


def _ok(n):
    return 16 <= n <= 70


def _segments(text):
    """[R] raw sentence spans, with spans joined across a bare line break when an age clause continues."""
    segs = [m.span() for m in _SENT.finditer(text)]
    if len(segs) < 2:
        return segs
    out = [segs[0]]
    for a, b in segs[1:]:
        pa, pb = out[-1]
        if _GAP.match(text, pb, a) and _JOIN_L.search(text, pa, pb) and _JOIN_R.match(text, a):
            out[-1] = (pa, b)
        else:
            out.append((a, b))
    return out


def _sentences(text):
    for base, end in _segments(text):
        seg = text[base:end]
        cuts = [0] + [x.start() for x in _LISTSPLIT.finditer(seg) if x.start() > 0] + [len(seg)]
        for a, b in zip(cuts, cuts[1:]):
            s = seg[a:b]
            lead = _MARK.match(s).end()
            e = len(s.rstrip())
            if e > lead:
                yield from _bounded(base + a + lead, base + a + e, text)


_CHUNK = 200
_CUT = re.compile(r"[，,、\s　]")


def _bounded(a, b, text):
    """[S] pathological input guard: a run longer than _CHUNK characters with no sentence stop (a 4,000-character
    paste of one repeated character, say) is cut at commas or spaces, so every regex works on a short string and time
    stays linear in the length. An age clause is far shorter than _CHUNK, so real ads are not affected."""
    while b - a > _CHUNK:
        k = max((m.end() for m in _CUT.finditer(text, a + _CHUNK // 2, a + _CHUNK)), default=a + _CHUNK)
        yield a, k
        a = k
    if b > a:
        yield a, b


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


def _audience(sent, span):
    """[R] the number describes pupils / customers, not the applicant."""
    return bool(CUST_AFTER.match(sent, span[1]) or AUD_BEFORE.search(sent[max(0, span[0] - 10):span[0]]))


def _relaxed(sent, span):
    return bool(RELAX_BEFORE.search(sent[max(0, span[0] - 8):span[0]]))


def _team_talk(sent, span):
    """[F3] generation / vague wording in a stretch about the team or company, with no requirement wording."""
    win = sent[max(0, span[0] - 15):span[1] + 15]
    return bool(TEAM.search(win)) and not REQ.search(win)


def parse_age(text):
    """Return list of age terms (dicts) in document order. Never mutates `text`."""
    if not text:
        return []
    out = []
    for s, e in _sentences(text):
        sent = text[s:e]
        if not _TRIG.search(sent):
            # [speed] only a trailing exception for the previous sentence's term can live here
            if not (out and out[-1].get("_sent_end") is not None and 0 <= s - out[-1]["_sent_end"] <= 3):
                continue
        taken, found = [], []  # found: (term, span)
        neg_spans = []

        def add(term, span):
            taken.append(span); found.append((term, span))

        for m in _find(RANGE, sent, taken):
            a, b = _num(m.group(1)), _num(m.group(2))
            if _ok(a) and _ok(b) and a <= b and not _audience(sent, m.span()) and not _relaxed(sent, m.span()):
                add(_term("range", a, b), m.span())
        # [R] refusals before MAX/MIN, so "35岁以上勿扰" is not read as a minimum and "不满18周岁勿扰" not as max 17
        for pat, kind in NEG:
            for m in _find([pat], sent, taken):
                n = _num(m.group(1))
                k = kind or ("max" if "上" in m.group(2) else "min")
                if not _ok(n):
                    continue
                if k == "max":
                    add(_term("max", None, n), m.span())
                else:
                    add(_term("min", n, None, "low" if n <= 18 else "high"), m.span())
                neg_spans.append(m.span())
        for m in _find(MAX, sent, taken):
            n = _num(m.group(1))
            if not _ok(n) or _audience(sent, m.span()) or _relaxed(sent, m.span()):
                continue
            # [F1] unit-less "最高/不超过 NN" counts only right after 年龄/年纪 (not 长期服务奖最高6000元)
            if m.re is MAX[0] and m.group(2) is None \
                    and not re.search(r"年龄|年纪|年齡", sent[max(0, m.start() - 12):m.start()]):
                continue
            if m.re is MAX[4]:
                if n <= 18:                                          # [R] 未满18周岁: legal minimum
                    add(_term("min", n, None, "low"), m.span())
                    continue
                n -= 1
            add(_term("max", None, n), m.span())
        for m in _find(MIN, sent, taken):
            n = _num(m.group(1))
            if _ok(n) and not _relaxed(sent, m.span()):
                add(_term("min", n, None, "low" if n <= 18 else "high"), m.span())
        for m in _find([ABOUT], sent, taken):
            n = _num(m.group(1) or m.group(2))
            if _ok(n):
                add(_term("ambiguous", None, n, "low"), m.span())
        # [R] a refusal cap made redundant by a range in the same sentence (18-26岁，30岁以上勿扰) is dropped,
        # so it does not create a false "two different caps" conflict
        rng_max = [t["max_age"] for t, _ in found if t["kind"] == "range"]
        if rng_max and neg_spans:
            found = [(t, sp) for t, sp in found
                     if not (sp in neg_spans and t["kind"] == "max" and t["max_age"] >= max(rng_max))]
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
            if not _team_talk(sent, m.span()):                      # [F3]
                add(_term("ambiguous", None, None, "low"), m.span())
        for m in VAGUE.finditer(sent):
            if not any(m.start() < t1 and m.end() > t0 for t0, t1 in taken) and not _team_talk(sent, m.span()):  # [F3]
                add(_term("ambiguous", None, None, "low"), m.span())
        for m in _find([BIRTH], sent, taken):                       # [R]
            add(_term("ambiguous", None, None, "low", None, "birth_year"), m.span())
        for m in _find([RETIRE], sent, taken):                      # [R]
            add(_term("ambiguous", None, None, "low", None, "retirement"), m.span())
        for m in _find([STATED], sent, taken):                      # [R]
            if _ok(_num(m.group(1))):
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
            # [R] an ambiguous term (e.g. a birth date) inside the relaxation clause no longer blocks the exception
            if txt and not EXC_VETO.search(txt) and not any(m.start() < t1 and m.end() > t0 and t["kind"] not in ("relaxable", "ambiguous") for t, (t0, t1) in found):
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


def parse_cohort(text):
    """[F4] Graduate-cohort wording (应届生, 毕业2年内, 2022届) as separate terms.

    Not an age condition, so it is NOT returned by parse_age() and never changes ad_class / age_status; it is an
    indirect proxy that callers may report on its own. Terms have kind 'cohort', flag 'graduate_cohort',
    age_class 'none', no ages, and the same snippet/offset contract as parse_age()."""
    if not text:
        return []
    out = []
    for m in COHORT.finditer(text):
        a, b = m.span()
        out.append(dict(_term("cohort", None, None, "low", None, "graduate_cohort"), snippet=text[a:b],
                        start_offset=a, end_offset=b, rule_version=RULE_VERSION, age_class="none"))
    return out


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
    if k == "cohort":                                               # [F4] only from parse_cohort()
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
