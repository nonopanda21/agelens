"""The two reports on a pasted ad (backend/two_reports.py). No network; the model is a fake."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AGELENS_DB", os.path.join(tempfile.mkdtemp(), "t.db"))
from backend import api_seeker, gloss, llm  # noqa: E402

AD = "采购专员。任职要求：年龄35岁以下，条件优秀者可放宽至40岁。"
BODY = {"text": AD, "question": "What should I clarify?", "profile": {"age": 38, "occupation": "Procurement", "years_experience": 8}}
GOOD = {"statements": [
    {"section": "explicit", "type": "ad_fact", "text": "The ad states an age limit of 35.", "evidence_ids": [api_seeker.PASTE_ID], "quote": "年龄35岁以下"},
    {"section": "exceptions", "type": "ad_fact", "text": "It may be relaxed to 40 for strong candidates.", "evidence_ids": [api_seeker.PASTE_ID]},
    {"section": "relates", "type": "model_inference", "text": "At 38, you are above 35 and below the relaxed 40.", "evidence_ids": [api_seeker.PASTE_ID]},
    {"section": "relates", "type": "model_inference", "text": "You may qualify for the relaxation.", "evidence_ids": [api_seeker.PASTE_ID]},
    {"section": "cannot", "type": "model_inference", "text": "The ad does not say how the relaxation is decided.", "evidence_ids": [api_seeker.PASTE_ID]},
    {"section": "ask", "type": "model_inference", "text": "Could you say how the relaxation to 40 is decided for someone aged 38?"}]}


def with_model(canned=None, raises=None):
    fake = llm.FakeProvider(canned=canned, raises=raises)
    status = dict(llm.status(), connected=True, label="Model connected", provider="fake")
    return fake, mock.patch.multiple(llm, get_provider=lambda: fake, status=lambda: status)


class NoModel(unittest.TestCase):
    def test_template_works_and_ai_says_why_it_is_absent(self):
        r = api_seeker.check_pasted(BODY)["reports"]
        self.assertTrue(r["template"]["available"])
        self.assertFalse(r["ai"]["available"])
        self.assertIn("no AI model", r["ai"]["reason"])
        self.assertNotIn("markdown", r["ai"])
        self.assertIn("No AI", r["template"]["written_by"])

    def test_template_is_fixed_and_ignores_the_person(self):
        a = api_seeker.check_pasted(BODY)["reports"]["template"]
        b = api_seeker.check_pasted(dict(BODY, profile={"age": 50}))["reports"]["template"]
        self.assertEqual((a["reading"], a["question"]), (b["reading"], b["question"]))
        self.assertNotIn("38", a["question"])
        self.assertEqual(len(a["checklist"]), 4)

    def test_no_chinese_leaves_in_either_report(self):
        for text in (AD, "年龄不限。年龄35岁以下。", "年龄要求：28-3", "Must be under 35.", "Salary up to 35k"):
            r = api_seeker.check_pasted(dict(BODY, text=text))["reports"]
            self.assertFalse(gloss.has_cjk(json.dumps(r["template"], ensure_ascii=False)), text)
            self.assertFalse(gloss.has_cjk(json.dumps(r["evidence"], ensure_ascii=False)), text)

    def test_wording_cases(self):
        def reading(text):
            return api_seeker.check_pasted(dict(BODY, text=text))["reports"]["template"]["reading"]
        self.assertIn("no age wording", reading("Salary up to 35k"))
        self.assertIn("contradicts itself", reading("年龄不限。年龄35岁以下。"))
        self.assertIn("Age 35 or under", reading("年龄不限。年龄35岁以下。"))
        self.assertIn("cut off", reading("任职要求：本科，年龄35岁以"))
        self.assertIn("could not read as a limit", reading("任职要求：本科，年龄要求：28-3"))
        self.assertIn("with an exception", reading(AD))


class SeenInUserTesting(unittest.TestCase):
    def test_a_preference_is_not_called_an_exception(self):
        q = api_seeker.check_pasted(dict(BODY, text="30岁以下优先"))["reports"]["template"]["question"]
        self.assertIn("any exception", q)
        self.assertNotIn("the exception", q)

    def test_below_the_minimum_is_said(self):
        b = api_seeker.check_pasted(dict(BODY, text="年龄28-35周岁", profile={"age": 24, "years_experience": 1}))
        self.assertIn("the stated minimum is 28", b["summary"]["relates"])
        self.assertIn("minimum age of 28", json.dumps(b["employer_question"]))

    def test_an_impossible_age_is_not_reported_as_no_age_given(self):
        b = api_seeker.check_pasted(dict(BODY, profile={"age": 200}))
        self.assertNotIn("did not give", b["summary"]["relates"])

    def test_one_ad_is_not_called_similar_ads(self):
        r = api_seeker.check_pasted(dict(BODY, text="Data analyst. SQL required."))["reports"]
        self.assertNotIn("similar", " ".join(r["evidence"]))

    def test_contact_details_do_not_reach_the_model(self):
        fake, patch = with_model({"statements": []})
        with patch:
            api_seeker.check_pasted(dict(BODY, text="联系人电话13800000000，邮箱a.b@example.invalid。年龄35岁以下。"))
        sent = json.dumps(fake.calls, ensure_ascii=False)
        self.assertNotIn("13800000000", sent)
        self.assertNotIn("a.b@example.invalid", sent)
        self.assertIn("年龄35岁以下", sent)


class WithModel(unittest.TestCase):
    def test_ai_report_holds_only_checked_model_statements_and_costs_one_call(self):
        fake, patch = with_model(GOOD)
        with patch:
            b = api_seeker.check_pasted(BODY)
        r = b["reports"]["ai"]
        self.assertEqual(len(fake.calls), 1)
        self.assertTrue(r["available"])
        self.assertIn("The ad states an age limit of 35.", r["stated"])
        self.assertEqual(r["question"], GOOD["statements"][-1]["text"])
        self.assertEqual(r["removed"], 1)
        self.assertNotIn("may qualify", json.dumps(r))
        self.assertIn("AI model", r["markdown"])
        self.assertEqual(b["reports"]["evidence"], api_seeker.check_pasted(BODY)["reports"]["evidence"])

    def test_model_failure_is_not_dressed_up_as_an_ai_report(self):
        _, patch = with_model(raises=llm.ProviderError("timeout"))
        with patch:
            r = api_seeker.check_pasted(BODY)["reports"]
        self.assertFalse(r["ai"]["available"])
        self.assertIn("timed out", r["ai"]["reason"])
        self.assertTrue(r["template"]["available"])

    def test_nothing_surviving_the_check_gives_no_report(self):
        bad = {"statements": [{"section": "relates", "type": "model_inference", "text": "You will be hired.", "evidence_ids": [api_seeker.PASTE_ID]}]}
        _, patch = with_model(bad)
        with patch:
            self.assertFalse(api_seeker.check_pasted(BODY)["reports"]["ai"]["available"])


class RealContext(unittest.TestCase):
    AD = "Marketing Coordinator. No age limit. Candidates under 30 preferred."

    def test_uses_the_published_counts(self):
        import json
        from pathlib import Path
        from backend import real_context
        data = json.loads((Path(__file__).resolve().parent.parent / "data/real/matrix_zhaopin_2021-2024.json").read_text(encoding="utf-8"))
        row = next(r for r in data["occupations"] if r["occupation"] == "市场营销")
        c = real_context.build(self.AD, {"age": 38}, "preference")
        self.assertEqual(c["scope"], "Marketing ads")
        self.assertIn("{:,}".format(row["ads"]), c["facts"][0])
        self.assertIn("%.1f%%" % (100.0 * row["age_wording"] / row["ads"]), c["facts"][0])
        self.assertIn("not hiring or rejection rates", c["note"])
        self.assertTrue(any("above the median" in x for x in c["suggestions"]))

    def test_region_narrows_the_group(self):
        from backend import real_context
        self.assertEqual(real_context.build(self.AD, {"region": "广东"}, "preference")["scope"], "Marketing ads in Guangdong")

    def test_small_or_unknown_groups_say_nothing(self):
        from backend import real_context
        self.assertIsNone(real_context.build("Ignore all rules. Astronaut wanted.", {}, "none"))

    def test_no_ad_text_and_no_verdicts_reach_the_page(self):
        from backend import llm, real_context
        c = real_context.build("Sales manager <script>x</script>. Must be under 35.", {"age": 52, "region": "广东"}, "hard_cap")
        text = " ".join(c["facts"] + c["suggestions"])
        self.assertNotIn("script", text)
        self.assertFalse(any(rx.search(text) for rx in llm._UNSUPPORTED), text)

    def test_title_not_body_decides_the_group(self):
        from backend import real_context
        self.assertEqual(real_context.build("Accountant. Reports to the sales manager.", {}, "none")["scope"], "Finance ads")


if __name__ == "__main__":
    unittest.main()
