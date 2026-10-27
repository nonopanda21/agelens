"""CV parsing: TXT / DOCX / text-based PDF -> a few structured, editable fields.

Privacy rules (enforced here, tested in tests/test_cv.py):
  * Nothing is written to disk or the database. The upload and its extracted text live only
    in memory for the duration of the call.
  * No name, phone, email or address is extracted. Contact-like strings are redacted from any
    free text we return.
  * Age is never inferred (no birth year, graduation year or date arithmetic).
  * CV text is DATA. It is only matched against regexes; it is never executed or used as an
    instruction for anything.
"""
import io
import re
import zipfile

MAX_BYTES = 5 * 1024 * 1024
MAX_UNCOMPRESSED = 40 * 1024 * 1024   # DOCX zip-bomb guard (sum of member sizes)
MAX_ZIP_MEMBERS = 2000
MAX_PDF_PAGES = 60
MIN_TEXT_CHARS = 25
SUPPORTED = (".txt", ".docx", ".pdf")


class CVError(Exception):
    """status: HTTP status; reason: machine code the UI maps to a message."""

    def __init__(self, status, reason, message):
        super().__init__(message)
        self.status, self.reason, self.message = status, reason, message


# ---------------------------------------------------------------- text extraction

def _decode_txt(data):
    if b"\x00" in data[:2000] and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        raise CVError(422, "corrupt", "This does not look like a plain-text file.")
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_docx(data):
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise CVError(422, "corrupt", "This DOCX file is damaged or is not a real DOCX.")
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_MEMBERS or sum(i.file_size for i in infos) > MAX_UNCOMPRESSED:
        raise CVError(422, "unsafe", "This DOCX expands to an unreasonable size and was not opened.")
    if "word/document.xml" not in {i.filename for i in infos}:
        raise CVError(422, "corrupt", "This DOCX has no readable document body.")
    try:
        import docx
        doc = docx.Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs]
        for t in doc.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        return "\n".join(parts)
    except CVError:
        raise
    except Exception:
        raise CVError(422, "corrupt", "This DOCX file could not be read.")


def _extract_pdf(data):
    if not data.lstrip()[:5] == b"%PDF-":
        raise CVError(422, "corrupt", "This file is not a valid PDF.")
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                ok = reader.decrypt("")
            except Exception:
                ok = 0
            if not ok:
                raise CVError(422, "encrypted", "This PDF is password-protected.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise CVError(413, "too_long", "This PDF has more than %d pages." % MAX_PDF_PAGES)
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except CVError:
        raise
    except Exception:
        raise CVError(422, "corrupt", "This PDF could not be read; it may be damaged.")


def extract_text(filename, data):
    name = (filename or "").lower()
    ext = next((e for e in SUPPORTED if name.endswith(e)), None)
    if len(data) > MAX_BYTES:
        raise CVError(413, "too_large", "File is larger than 5 MB.")
    if not data:
        raise CVError(422, "empty", "The file is empty.")
    if ext is None:
        raise CVError(415, "unsupported", "Only TXT, DOCX and text-based PDF files are supported.")
    text = {".txt": _decode_txt, ".docx": _extract_docx, ".pdf": _extract_pdf}[ext](data)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    if len(re.sub(r"\s", "", text)) < MIN_TEXT_CHARS:
        if ext == ".pdf":
            raise CVError(422, "no_text", "No readable text found. This looks like a scanned or image-only PDF "
                                          "(OCR is not available).")
        raise CVError(422, "no_text", "No readable text found in this file.")
    return ext[1:], text


# ---------------------------------------------------------------- field heuristics

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s\-().]{7,}\d)(?!\d)")
URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def redact(s):
    s = EMAIL.sub("", s)
    s = URL.sub("", s)
    s = PHONE.sub("", s)
    return re.sub(r"\s{2,}", " ", s).strip(" ,;|-")


def _has_contact(line):
    return bool(EMAIL.search(line) or URL.search(line) or PHONE.search(line))


ZH_NUM = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
EN_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20}


def _zh_to_int(s):
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if "十" in s:
        a, _, b = s.partition("十")
        return (ZH_NUM.get(a, 1) if a else 1) * 10 + (ZH_NUM.get(b, 0) if b else 0)
    return ZH_NUM.get(s)


YEARS_PATTERNS = [
    re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b(?:\s+of)?", re.I),
    re.compile(r"\b(" + "|".join(EN_NUM) + r")\s+(?:years?|yrs?)\b", re.I),
    re.compile(r"([0-9零一二两三四五六七八九十]{1,3})\s*年(?:以上)?(?:的)?(?:[一-龥]{0,6})?(?:工作)?经[验历]"),
    re.compile(r"(?:工作|从业|经验)\s*([0-9零一二两三四五六七八九十]{1,3})\s*年"),
]


def find_years(text):
    """Largest plausible 'N years' experience phrase. Never derived from date ranges."""
    best = None
    for rx in YEARS_PATTERNS:
        for m in rx.finditer(text):
            g = m.group(1)
            n = EN_NUM.get(g.lower()) if g.lower() in EN_NUM else _zh_to_int(g)
            if n is not None and 0 < n <= 50:
                # skip phrases like "2 years ago"/"for 2 years at" are still fine; keep largest
                best = n if best is None else max(best, n)
    return best


TITLE_WORDS = re.compile(
    r"\b(manager|engineer|operations?|specialist|analyst|developer|designer|sales|accountant|administrator|"
    r"coordinator|director|executive|assistant|consultant|supervisor|officer|lead|marketing|recruiter|"
    r"technician|architect|planner|buyer|clerk|representative)\b|"
    r"(经理|工程师|运营|专员|主管|总监|销售|行政|会计|设计师|开发|助理|顾问|文员|客服|采购|策划|编辑|司机|店长)", re.I)
TITLE_LABEL = re.compile(r"^\s*(?:current\s+)?(?:job\s+)?(?:title|position|occupation|role|target(?:\s+role)?|objective|"
                         r"职位|职业|岗位|求职意向|目标岗位)\s*[:：]\s*(.{2,70})$", re.I)
SKILL_LABEL = re.compile(r"^\s*(?:(?:core|key|technical|professional)\s+)?(?:skills?|competenc(?:y|ies)|"
                         r"专业技能|技能|核心技能)\s*[:：]?\s*(.*)$", re.I)
HEADING = re.compile(r"^\s*(?:summary|profile|objective|experience|work experience|employment|education|projects?|"
                     r"certifications?|languages?|interests|references|skills?|个人简介|工作经历|教育背景|项目经验|自我评价)\s*[:：]?\s*$", re.I)
SUMMARY_LABEL = re.compile(r"^\s*(?:professional\s+)?(?:summary|profile|about me|个人简介|自我评价)\s*[:：]?\s*(.*)$", re.I)
DEGREE = re.compile(r"(bachelor|master|mba|ph\.?d|doctorate|associate|diploma|本科|硕士|博士|大专|专科)[^\n,;，；。]{0,40}", re.I)


def find_occupation(lines):
    for ln in lines[:40]:
        m = TITLE_LABEL.match(ln)
        if m and not _has_contact(m.group(1)):
            return redact(m.group(1))[:70]
    for ln in lines[:14]:
        s = ln.strip(" \t•-*·")
        if 2 <= len(s) <= 60 and not _has_contact(s) and not HEADING.match(s) and TITLE_WORDS.search(s) \
                and len(YEAR.findall(s)) == 0 and not s.endswith((".", "。")):
            return s
    return None


def find_skills(lines):
    skills = []
    for i, ln in enumerate(lines):
        m = SKILL_LABEL.match(ln)
        if not m:
            continue
        chunk = [m.group(1)] if m.group(1).strip() else []
        for nxt in lines[i + 1:i + 8]:
            if not nxt.strip() or HEADING.match(nxt):
                break
            chunk.append(nxt)
        for piece in re.split(r"[,;，；、|/•·\n]+", "\n".join(chunk)):
            p = redact(piece.strip(" \t•-*·"))
            if 1 < len(p) <= 40 and p.lower() not in {s.lower() for s in skills}:
                skills.append(p)
        if skills:
            break
    return skills[:20]


def find_summary(lines):
    for i, ln in enumerate(lines):
        m = SUMMARY_LABEL.match(ln)
        if m:
            chunk = [m.group(1)] if m.group(1).strip() else []
            for nxt in lines[i + 1:i + 6]:
                if not nxt.strip() or HEADING.match(nxt) or re.match(r"\s*[\w \u4e00-\u9fa5]{2,25}[:：]", nxt):
                    break
                chunk.append(nxt.strip())
            s = redact(" ".join(chunk))
            if s:
                return s[:500]
    return ""


def find_education(text):
    m = DEGREE.search(text)
    if not m:
        return None
    return redact(YEAR.sub("", m.group(0))).strip(" -(,")[:60] or None  # graduation years removed on purpose


def extract_fields(text):
    lines = [l.rstrip() for l in text.split("\n")]
    warnings = []
    fields = {
        "occupation": find_occupation(lines) or "",
        "years_experience": find_years(text),
        "skills": find_skills(lines),
        "summary": find_summary(lines),
    }
    edu = find_education(text)
    if edu:
        fields["education"] = edu
    if not fields["occupation"]:
        warnings.append("Could not find a job title; please type your occupation.")
    if fields["years_experience"] is None:
        warnings.append("No explicit 'N years of experience' phrase found; please enter your years of experience.")
    if not fields["skills"]:
        warnings.append("No skills section found; add skills or experience manually.")
    warnings.append("Age is never read or guessed from a CV; enter it yourself if you want it compared.")
    return fields, warnings


def parse_cv(filename, data):
    """-> {ok, fields, warnings, file_kind, stored:False}; raises CVError."""
    kind, text = extract_text(filename, data)
    fields, warnings = extract_fields(text)
    if len(text) > 200_000:
        warnings.insert(0, "Very long document; only common patterns were scanned.")
    return {"ok": True, "fields": fields, "warnings": warnings, "file_kind": kind,
            "stored": False, "chars_read": len(text)}
