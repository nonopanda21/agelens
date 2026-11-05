"""Quick fill from one sentence, and the PDF report."""
import base64
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("AGELENS_DB", os.path.join(tempfile.mkdtemp(), "t.db"))
from backend import api_seeker, llm, profile_text as P, report_pdf  # noqa: E402


class QuickFill(unittest.TestCase):
    def test_sentences(self):
        cases = {"I'm 38, 9 years in marketing, based in Guangzhou, bachelor's degree": {"age": 38, "years_experience": 9, "occupation": "marketing", "region": "广东"},
                 "38 years old. 12 years of experience as an operations manager in Shanghai": {"age": 38, "years_experience": 12, "occupation": "operations manager", "region": "上海"},
                 "我今年42岁，做销售工作15年，在北京，本科": {"age": 42, "years_experience": 15, "occupation": "销售", "region": "北京"},
                 "Age: 45. I am an accountant.": {"age": 45, "occupation": "accountant"}}
        for text, want in cases.items():
            got = P.parse(text)["fields"]
            for k, v in want.items():
                self.assertEqual(got.get(k), v, (text, k, got))

    def test_years_are_not_an_age(self):
        for text in ("I have 15 years of experience", "I'm 15 years into marketing", "9 years in sales"):
            self.assertIsNone(P.parse(text)["fields"].get("age"), text)

    def test_impossible_age_is_left_out(self):
        self.assertNotIn("age", P.parse("I am 99 and work in sales")["fields"])

    def test_nothing_found(self):
        self.assertEqual(P.parse("hello there")["fields"], {})
        self.assertEqual(P.parse(None)["fields"], {})

    def test_contact_details_do_not_come_back(self):
        got = str(P.parse("I'm 38, call 13800138000 or me@example.com, I work in sales")["fields"])
        self.assertNotIn("13800138000", got)
        self.assertNotIn("example.com", got)


@unittest.skipUnless(shutil.which("pdftotext"), "needs pdftotext")
class Pdf(unittest.TestCase):
    def text_of(self, data):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "r.pdf")
            with open(f, "wb") as fh:
                fh.write(data)
            return subprocess.run(["pdftotext", "-layout", f, "-"], capture_output=True, check=True).stdout.decode("utf-8")

    def test_reads_back(self):
        t = self.text_of(report_pdf.build("# AgeLens: AI report\n\n**Label.** Written by (code).\n\n## Heading\n\n- A bullet with “quotes” – and a dash.\n\n> Note"))
        for want in ("AgeLens: AI report", "Label. Written by (code).", "Heading", "•", "A bullet with “quotes” – and a dash.", "Note", "Page 1 of 1", "not legal advice"):
            self.assertIn(want, t)

    def test_long_report_paginates(self):
        data = report_pdf.build("# T\n\n" + "\n".join("- line %d " % i + "word " * 40 for i in range(120)))
        self.assertIn("Page 2 of", self.text_of(data))

    def test_chinese_and_long_words_do_not_break_it(self):
        t = self.text_of(report_pdf.build("# T\n\n中文 text " + "x" * 400))
        self.assertIn("[Chinese text]", t)

    def test_both_reports_carry_a_pdf(self):
        with mock.patch.object(llm, "get_provider", return_value=llm.TemplateProvider()):
            r = api_seeker.check_pasted({"text": "Sales role. Must be under 35.", "question": "q", "profile": {}})["reports"]["template"]
        self.assertTrue(base64.b64decode(r["pdf"]).startswith(b"%PDF-"))
        self.assertIn("Under 35", self.text_of(base64.b64decode(r["pdf"])))


if __name__ == "__main__":
    unittest.main()
