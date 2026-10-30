"""Gender-requirement rules for Chinese job ads (rules only, no model). Version: gender-rules-1.0.0.

Detects an EXPLICITLY WRITTEN requirement about the applicant's gender, and nothing else. Precision is preferred to recall:
a sensitive field must not be filled by guesses. parse_gender(text) -> list of terms
  {"kind", "snippet", "start", "end", "pattern"}  with kind in
  male_only | female_only | male_preferred | female_preferred | no_gender_limit
gender_class(terms) -> male_only | female_only | male_preferred | female_preferred | no_limit | conflict | none.

Decisions (details and gold-set results: docs/GENDER_RULES.md)
 * Counted: 限男 / 仅限女 / 只招男 / 要求女性 / 性别:男 / (女) in a title / a bare 男性, 女士 as a list item ("，女性，身高160");
   preferences (女生优先, 男士为佳, 优先考虑女性); explicit "either gender" wording (男女不限, 性别不限, 男女均可, 招男女普工,
   男女各2名, 男,女 as a list, male AND female height standards); all of these mean the ad names both sexes as welcome -> no_limit.
 * Not counted: products and categories (女装, 男鞋, 母婴, 女士护理, 男科), customers or users (女性客户), colleagues and
   benefits (男员工陪产假, 女生宿舍), contact persons (王女士: 女士/先生 right after a surname-like character), 男女老少, company
   names, 宝妈 / 帅哥美女 (not a requirement), a standard for ONE sex only ("男性身高170cm以上": implicit, left out).
 * Conflict: male-only wording together with female-only wording (or a preference for the other sex), or a restriction together
   with "男女不限" -- the ad can describe separate posts or contradict itself; the class is reported as 'conflict', not guessed.
 * Every quantifier is bounded (no nested or open-ended repeats of whitespace), so time is linear in the text length.
"""
import re

RULE_VERSION = "gender-rules-1.0.0"
KINDS = ("male_only", "female_only", "male_preferred", "female_preferred", "no_gender_limit")
CLASSES = ("male_only", "female_only", "male_preferred", "female_preferred", "no_limit", "conflict", "none")

_W = r"\s{0,2}"
_NUM = r"[0-9一二两三四五六七八九十]{1,3}"
_SEP = r"[/、，,和及与或]"
_G = "(?<![子儿孙长幼次独外侄甥])[男女]"
_SFX = "[性士生]?"
# words that follow a gender word when it names a product, customer, benefit or place (not an applicant)
_AFTER_BAD = re.compile(r"^(?:宾|男|女|装|鞋|包|款|式|用|科|衣|帽|裤|袜|护|美|宿|厕|浴|更衣|洗|产品|品|表|专区|专柜|客|顾客|消费|群|市场|朋友|会员|学员|粉丝|"
                        r"患者|病人|宝宝|陪产|产假|假|健康|养生|保健|理疗|服|饰|内衣|香水|化妆|彩妆|周|节|神|老少|同事|同学|员工)")
_BEFORE_BAD = re.compile(r"(?:客户|顾客|用户|会员|学员|服务|面向|针对|对象|消费者|粉丝|同事|同组|室友|宝宝|患者|病人|孕|产后|美容|健身|瑜伽)[^，。；;、\n：:]{0,3}$")
_NOT_AFTER_GENDER = r"(?![男女])"


def _c(p):
    return re.compile(p)


# 1. either gender / both genders named as welcome ------------------------------------------------------------------------
_PAIR = f"{_G}{_SFX}{_W}{_SEP}?{_W}{_G}{_SFX}"
_NO_LIMIT = [
    ("pair_unlimited", _c(f"{_PAIR}{_W}(?:均|皆|都|兼)?{_W}(?:不限制|无限制|不限|不拘|不论|可以|均可|皆可|都可|兼可|兼招|均招|皆宜|均宜|可)")),
    ("unlimited_gender", _c(f"不限{_W}(?:性别|男女)|性别{_W}(?:要求)?{_W}[:：]?{_W}(?:不限|无要求|无限制|不拘|均可|不限制)")),
    ("recruit_both", _c(f"招(?:聘|收)?{_W}男{_W}[/、]?{_W}女|男{_W}[/、]?{_W}女{_W}(?=[普操]?工)")),
    ("each_n", _c(f"男{_W}女{_W}各{_W}(?:{_NUM}){_W}[名人位个]?")),
    ("counts", _c(f"男{_W}{_NUM}{_W}[名人位]{_W}[，,、]?{_W}女{_W}{_NUM}")),
    ("field_pair", _c(f"性别{_W}[:：]?{_W}{_PAIR}")),
    ("pair_adjacent", _c(f"男[性士生]{_W}女[性士生]|女[性士生]{_W}男[性士生]|男女[性士生]")),
    ("pair_paren", _c(f"(?<![子生]){_G}{_W}[（(]{_W}{_G}{_W}[）)]")),
    ("pair_list", _c(f"(?<![男女]){_G}{_SFX}{_W}[/、，,]{_W}{_G}(?![性士生]?[装鞋包款式用科衣帽裤袜宿厕浴孩])(?![性士生]?[、，,]{_W}(?:儿童|少|老|小孩|童))")),
]
# 2. preferences -----------------------------------------------------------------------------------------------------------
_PREF = [
    ("pref_after", _c(f"(?<![男女])(?<![男女][、/]){_G}{_SFX}(?:员工|应聘者|求职者)?{_W}(?:优先|为佳|更佳|最佳|尤佳|更好|更合适|更适合|更优)(?![男女])")),
    ("pref_before", _c(f"(?<!可)优先(?:考虑|录用|录取|聘用)?{_W}{_G}[性士生](?!身高)")),
    ("pref_verb", _c(f"(?:最好|倾向于?|偏好|偏向|欢迎){_W}{_G}[性士生](?![男女])")),
]
# 3. restrictions -----------------------------------------------------------------------------------------------------------
_ONLY = [
    ("only_verb", _c(f"(?<![不无未])(?:仅限|只限|限|仅招聘|只招聘|仅招|只招|仅要|只要|仅收|只收){_W}{_G}(?:性|士|生|子|孩子?|工|员工)?{_NOT_AFTER_GENDER}")),
    ("require", _c(f"(?:要求|须为|必须是|必须为|需为|应为){_W}[:：]?{_W}{_G}{_SFX}(?=[\\s，,。；;、）)】]|$)")),
    ("gender_field", _c(f"性别{_W}(?:要求)?{_W}[:：]?{_W}{_G}{_SFX}(?=[\\s，,。；;、）)】]|身高|年龄|体重|\\d|$)")),
    ("title_paren", _c(f"(?<![子生男女])[（(【\\[]{_W}{_G}{_SFX}{_W}[）)】\\]]")),
    ("recruit_n", _c(f"(?:招|招聘|招收){_W}{_G}[性士生工]?{_W}{_NUM}{_W}[名人位个]")),
    ("bare_item", _c(f"(?<![一-鿿A-Za-z]){_G}[性士生]?(?=\\s{{0,1}}[，,。；;]|\\s{{0,1}}、(?![男女儿老少童小])|$)")),
]
# 4. a standard for each sex (height etc.): both sexes named -> inclusive wording --------------------------------------------
_STD = [_c(f"({_G}){_SFX}{_W}[:：]?{_W}(?:身高|1[4-9]\\d(?:\\.\\d)?\\s{{0,1}}(?:cm|CM|厘米|公分|以上|及以上|以下|左右)|1[.、]\\d)"),
        _c(f"(?:身高|体重|年龄){_W}[:：]?{_W}({_G}){_SFX}"),
        _c(f"[（(]({_G})[）)]{_W}[:：]?{_W}身高"),
        _c(f"\\d{{3}}(?:\\.\\d)?\\s{{0,1}}(?:公分|cm|CM|厘米|米)?\\s{{0,1}}(?:以上|及以上|以内)?\\s{{0,1}}[（(]({_G})[）)]"),
        _c(f"身高{_W}[:：]?{_W}[（(]({_G})[）)]"), _c(f"[（(]({_G})[）)]{_W}[:：]?{_W}1[4-9]\\d")]


def _ctx_ok(text, s, e):
    if _AFTER_BAD.match(text[e:e + 4]):
        return False
    return not _BEFORE_BAD.search(text[max(0, s - 10):s])


def _kind_of(pat, m):
    s = m.group(0)
    if pat.startswith("pref"):
        g = next(ch for ch in s if ch in "男女")
        return "male_preferred" if g == "男" else "female_preferred"
    g = next((ch for ch in s if ch in "男女"), None)
    if pat in ("only_verb", "require", "gender_field", "title_paren", "recruit_n", "bare_item"):
        return "male_only" if g == "男" else "female_only"
    return "no_gender_limit"


def parse_gender(text):
    """Terms for explicit gender wording about the applicant in `text`, in text order."""
    if not text or ("男" not in text and "女" not in text and "性别" not in text):
        return []
    taken, out = [], []

    def free(s, e):
        return all(e <= a or s >= b for a, b in taken)

    def add(pat, kind, m, check):
        s, e = m.span()
        if len(taken) >= 200 or not free(s, e) or (check and not _ctx_ok(text, s, e)):
            return
        taken.append((s, e))
        out.append({"kind": kind, "snippet": text[max(0, s - 12):e + 12].replace("\n", " "), "start": s, "end": e, "pattern": pat})

    seen = {}
    for rx in _STD:  # a standard for each sex (height ...): both sexes named -> inclusive wording, taken first
        for m in rx.finditer(text):
            g = next(x for x in m.groups() if x)
            if _ctx_ok(text, *m.span()):
                seen.setdefault(g, []).append(m)
    if len(seen) == 2:
        spans = [m for ms in seen.values() for m in ms]
        for m in spans:
            taken.append(m.span())
        m = min(spans, key=lambda x: x.start())
        s, e = m.span()
        out.append({"kind": "no_gender_limit", "snippet": text[max(0, s - 12):e + 12].replace("\n", " "), "start": s, "end": e,
                    "pattern": "sex_specific_standards"})
    for pat, rx in _NO_LIMIT:
        for m in rx.finditer(text):
            add(pat, "no_gender_limit", m, pat == "pair_paren")
    for pat, rx in _PREF:
        for m in rx.finditer(text):
            add(pat, _kind_of(pat, m), m, True)
    for pat, rx in _ONLY:
        for m in rx.finditer(text):
            add(pat, _kind_of(pat, m), m, True)
    out.sort(key=lambda t: t["start"])
    return out


def gender_class(terms):
    kinds = {t["kind"] for t in terms}
    male = {"male_only", "male_preferred"} & kinds
    female = {"female_only", "female_preferred"} & kinds
    only = {"male_only", "female_only"} & kinds
    if male and female:
        return "conflict"
    if only:
        return "conflict" if "no_gender_limit" in kinds else next(iter(only))
    if male or female:
        return next(iter(male or female))
    return "no_limit" if "no_gender_limit" in kinds else "none"
