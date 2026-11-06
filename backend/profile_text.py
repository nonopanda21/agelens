"""Quick fill: one line about a person -> the form's background fields, by fixed rules (like the address box on a courier site).
Read in memory only, never stored, and no model sees it. Nothing here is used until it is in the form, where the person can change it."""
import re

from . import cv, realdata
from .evidence import PROVINCES

MAX_CHARS = 1000
_AGE = [re.compile(r"\b(?:i am|i'm|im|age[ds]?|age is|my age is)\s*:?\s*(\d{2})\b(?!\s*\+?\s*(?:years?|yrs?)\b(?![\s-]*old\b))", re.I),
        re.compile(r"\b(\d{2})\s*(?:-|\s)?\s*(?:years?|yrs?)[- ]old\b", re.I), re.compile(r"\b(\d{2})\s*y/?o\b", re.I), re.compile(r"(?<!\d)(\d{2})\s*(?:岁|周岁)")]
_ROLE = re.compile(r"\b(?:years?|yrs?)(?:\s+of)?(?:\s+\w+)?\s+(?:experience\s+)?(?:in|as|at)\s+(?:an?\s+|the\s+)?([a-z][a-z &/-]{2,40})"
                   r"|\b(?:work(?:ing)?|worked)\s+(?:in|as)\s+(?:an?\s+|the\s+)?([a-z][a-z &/-]{2,40})"
                   r"|\b(?:i am|i'm|im)\s+(?:an?\s+)([a-z][a-z &/-]{2,40})"
                   r"|\b\d{2}[- ]years?[- ]old\s+([a-z][a-z &/-]{2,40})"
                   r"|\b(?:looking for|seeking|want|applying for)\s+(?:an?\s+)?([a-z][a-z &/-]{2,40}?)\s+(?:jobs?|roles?|positions?)\b", re.I)
_ROLE_END = re.compile(r"\s+(?:and|with|based|living|from|for|at|who|in|near)\b.*$", re.I)
_ROLE_ZH = re.compile(r"(?:做|从事)([一-鿿]{2,10}?)(?:工作|行业|岗位|\d|[一二两三四五六七八九十]+年|$|[，,。；;])")
# major cities whose English name is not a province's
_CITY = {"guangzhou": "广东", "shenzhen": "广东", "dongguan": "广东", "foshan": "广东", "hangzhou": "浙江", "ningbo": "浙江", "nanjing": "江苏", "suzhou": "江苏", "wuxi": "江苏",
         "chengdu": "四川", "wuhan": "湖北", "changsha": "湖南", "xi'an": "陕西", "xian": "陕西", "jinan": "山东", "qingdao": "山东", "zhengzhou": "河南", "shenyang": "辽宁",
         "dalian": "辽宁", "harbin": "黑龙江", "fuzhou": "福建", "xiamen": "福建", "hefei": "安徽", "kunming": "云南", "nanning": "广西", "guiyang": "贵州", "nanchang": "江西",
         "shijiazhuang": "河北", "taiyuan": "山西", "changchun": "吉林", "lanzhou": "甘肃", "urumqi": "新疆", "haikou": "海南"}


def _age(text):
    for rx in _AGE:
        for m in rx.finditer(text):
            n = int(m.group(1))
            if 14 <= n <= 80:
                return n
    return None


def _region(text):
    low = text.lower()
    for p in PROVINCES:
        if p["name"] in text or p["full"] in text or re.search(r"\b%s\b" % re.escape(p["en"].lower()), low):
            return p["name"]
    for city, prov in _CITY.items():
        if re.search(r"\b%s\b" % re.escape(city), low):
            return prov
    for m in re.finditer(r"[一-鿿]{2,4}", text):
        for n in range(2, len(m.group()) + 1):
            prov = realdata.city_to_province(m.group()[:n])
            if prov:
                return prov
    return None


def _role(text):
    m = _ROLE.search(text)
    if m:
        role = _ROLE_END.sub("", next(g for g in m.groups() if g)).strip(" -/&")
        if 2 < len(role) <= 40 and not _region(role):  # "worked 3 years in Beijing" names a place, not a role
            return role
    m = _ROLE_ZH.search(text)
    return m.group(1) if m else None


def _years(text):
    y = cv.find_years(text)
    if y is not None:
        return y
    m = re.search(r"(?<![\d.])(\d{1,2})\s*年(?!\d)", text)  # a bare "9年" in a short line about a person; four-digit years do not match
    return int(m.group(1)) if m and 0 < int(m.group(1)) <= 50 else None


def _education(text):
    e = cv.find_education(text)
    return e.split()[0] if e and re.match(r"[一-鿿]", e) else e  # Chinese degree words end at the space


def parse(text):
    """-> {"fields": {only what was found}}. Contact details are ignored, and no free text beyond a short role or degree comes back."""
    text = cv.redact(str(text or "")[:MAX_CHARS])
    f = {"age": _age(text), "years_experience": _years(text), "occupation": _role(text), "region": _region(text), "education": _education(text)}
    return {"fields": {k: v for k, v in f.items() if v not in (None, "")}}
