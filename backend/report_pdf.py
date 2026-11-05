"""A plain PDF of a report, with the standard library only. Built in memory from the report's Markdown and never stored.
Uses the built-in Helvetica fonts (nothing embedded), so text is limited to the Windows-1252 set; this report is English only."""
import re

from . import gloss

W, H, LEFT, RIGHT, TOP, BOTTOM = 595, 842, 56, 56, 64, 64  # A4, in points
SIZES = {"title": 18, "h2": 12.5, "body": 10.5, "small": 8.5}
FOOT = "AgeLens explains wording. It does not decide anything about you, and it is not legal advice."
_W = dict(zip(map(chr, range(32, 127)), (278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, *[556] * 10, 278, 278, 584, 584, 584, 556, 1015,
                                         667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611,
                                         278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278,
                                         556, 500, 722, 500, 500, 500, 334, 260, 334, 584)))


def _width(s, size, bold=False):
    return sum(_W.get(c, 556) for c in s) * size / 1000.0 * (1.07 if bold else 1)


def _wrap(text, size, room, bold=False):
    lines, cur = [], ""
    for word in text.split():
        while _width(word, size, bold) > room:  # a very long word, such as a pasted URL
            n = len(word)
            while n > 1 and _width(word[:n], size, bold) > room:
                n -= 1
            if cur:
                lines.append(cur)
                cur = ""
            lines.append(word[:n])
            word = word[n:]
        trial = (cur + " " + word) if cur else word
        if _width(trial, size, bold) <= room:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def _pdf_text(s):
    raw = gloss.strip_cjk(s).encode("cp1252", "replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _layout(markdown):
    """-> pages, each a list of (x, y, font, size, text)."""
    pages, page, y = [], [], H - TOP
    room = W - LEFT - RIGHT

    def put(text, size, font="F1", indent=0, before=0, after=0, first=None):
        nonlocal page, y
        y -= before
        for i, line in enumerate(_wrap(text, size, room - indent, font == "F2")):
            if y < BOTTOM + size:
                pages.append(page)
                page, y = [], H - TOP
            if i == 0 and first:
                page.append((LEFT + indent - 11, y, font, size, first))
            page.append((LEFT + indent, y, font, size, line))
            y -= size * 1.42
        y -= after

    for raw in markdown.split("\n"):
        line = raw.strip()
        if not line:
            continue
        plain = line.replace("**", "").replace("`", "")
        if line.startswith("# "):
            put(plain[2:], SIZES["title"], "F2", after=6)
        elif line.startswith("## "):
            put(plain[3:], SIZES["h2"], "F2", before=10, after=2)
        elif line.startswith("- "):
            put(plain[2:], SIZES["body"], indent=14, after=2, first="•")
        elif line.startswith("> "):
            put(plain[2:], SIZES["body"], "F2" if line.startswith("> **") else "F1", indent=8, after=2)
        else:
            put(plain, SIZES["body"], after=3)
    pages.append(page)
    return pages


def build(markdown):
    """-> PDF bytes."""
    pages = _layout(markdown)
    n = len(pages)
    objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
            3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
            5: b"<< /Title (AgeLens report) /Producer (AgeLens) >>"}
    kids = []
    for i, page in enumerate(pages):
        ops = [b"BT"]
        foot = [(LEFT, 40, "F1", SIZES["small"], FOOT), (W - RIGHT - 40, 40, "F1", SIZES["small"], "Page %d of %d" % (i + 1, n))]
        for x, y, font, size, text in page + foot:
            ops.append(("/%s %s Tf 1 0 0 1 %.2f %.2f Tm (" % (font, size, x, y)).encode() + _pdf_text(text) + b") Tj")
        ops.append(b"ET")
        stream = b"\n".join(ops)
        pid, cid = 6 + 2 * i, 7 + 2 * i
        objs[cid] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        objs[pid] = ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents %d 0 R >>" % (W, H, cid)).encode()
        kids.append("%d 0 R" % pid)
    objs[2] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join(kids), n)).encode()
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for k in sorted(objs):
        offsets[k] = len(out)
        out += b"%d 0 obj\n" % k + objs[k] + b"\nendobj\n"
    xref = len(out)
    size = max(objs) + 1
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    for k in range(1, size):
        out += b"%010d 00000 n \n" % offsets[k]
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 5 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (size, xref)
    return bytes(out)
