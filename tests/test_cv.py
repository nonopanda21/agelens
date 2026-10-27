import io
import unittest

import docx
from pypdf import PdfWriter

from backend import cv

SAMPLE = """Operations Manager
Email: jane@example.com  Phone: +86 138 0000 1234
Summary
Operations professional with eight years of experience in e-commerce logistics.
Skills: Process improvement, SQL, Vendor management; Excel
Education
Bachelor of Business Administration, 2009
Experience
2015-2023 Shanghai Foo Ltd
"""


def make_docx(text):
    d = docx.Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    b = io.BytesIO()
    d.save(b)
    return b.getvalue()


def make_pdf(text):
    stream = "BT /F1 12 Tf 50 750 Td " + " ".join("(%s) Tj 0 -16 Td" % l.replace("(", "").replace(")", "")
                                                    for l in text.split("\n") if l) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            "<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += ("%d 0 obj\n%s\nendobj\n" % (i, o)).encode()
    x = len(out)
    out += ("xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)).encode()
    out += b"".join(("%010d 00000 n \n" % o).encode() for o in offs)
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)).encode()
    return out


def check_fields(t, r):
    f = r["fields"]
    t.assertEqual(f["occupation"], "Operations Manager")
    t.assertEqual(f["years_experience"], 8)
    t.assertIn("SQL", f["skills"])
    t.assertIn("Excel", f["skills"])
    t.assertNotIn("2009", str(f))        # graduation year dropped
    blob = str(r)
    t.assertNotIn("jane@example.com", blob)
    t.assertNotIn("138 0000", blob)
    t.assertNotIn("age", f)               # never infer age
    t.assertFalse(r["stored"])


class CVTests(unittest.TestCase):
    def test_txt(self):
        r = cv.parse_cv("cv.txt", SAMPLE.encode())
        check_fields(self, r)
        self.assertEqual(r["file_kind"], "txt")

    def test_docx(self):
        check_fields(self, cv.parse_cv("cv.docx", make_docx(SAMPLE)))

    def test_pdf_text(self):
        r = cv.parse_cv("cv.pdf", make_pdf(SAMPLE.replace("@", " at ").replace("+", "")))
        self.assertEqual(r["file_kind"], "pdf")
        self.assertEqual(r["fields"]["years_experience"], 8)

    def test_chinese_years_and_gb18030(self):
        t = "运营经理\n拥有八年运营经验，熟悉供应链管理和数据分析。\n技能：数据分析、供应链、Excel\n"
        r = cv.parse_cv("简历.txt", t.encode("gb18030"))
        self.assertEqual(r["fields"]["years_experience"], 8)
        self.assertEqual(r["fields"]["occupation"], "运营经理")
        self.assertIn("供应链", r["fields"]["skills"])

    def err(self, name, data):
        with self.assertRaises(cv.CVError) as c:
            cv.parse_cv(name, data)
        return c.exception

    def test_errors(self):
        self.assertEqual(self.err("a.txt", b"x" * (cv.MAX_BYTES + 1)).reason, "too_large")
        self.assertEqual(self.err("a.exe", b"hello world hello world hello world").reason, "unsupported")
        self.assertEqual(self.err("a.docx", b"not a zip at all").reason, "corrupt")
        self.assertEqual(self.err("a.pdf", b"%PDF-1.4 garbage garbage").reason, "corrupt")
        self.assertEqual(self.err("a.txt", b"").reason, "empty")
        w = PdfWriter()
        w.add_blank_page(612, 792)
        b = io.BytesIO()
        w.write(b)
        e = self.err("scan.pdf", b.getvalue())
        self.assertEqual(e.reason, "no_text")
        self.assertIn("scanned", e.message)

    def test_docx_bomb(self):
        import zipfile
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("word/document.xml", "<a/>")
            z.writestr("big.bin", b"\0" * (cv.MAX_UNCOMPRESSED + 1024))
        self.assertLess(len(b.getvalue()), cv.MAX_BYTES)
        self.assertEqual(self.err("a.docx", b.getvalue()).reason, "unsafe")

    def test_no_age_from_dates(self):
        r = cv.parse_cv("c.txt", b"Analyst\nWorked 2005-2020 at a company. Born 1985. Graduated 2007.\nSkills: SQL\n")
        self.assertIsNone(r["fields"]["years_experience"])
        self.assertNotIn("1985", str(r))


if __name__ == "__main__":
    unittest.main()
