"""Regression for age-rules-2.1.0 on short snippets taken from a hand-labelled set of real ads (docs/RULES_GOLD.md).
The labels come from one annotator and the snippets were chosen to be hard; the match rate is a guard against
regressions, not an accuracy estimate (that is in docs/RULES_GOLD.md)."""
import json
import time
import unittest
from pathlib import Path

from backend.ageparse import parse_age, ad_class, age_status

FIX = Path(__file__).parent / "fixtures" / "age_gold_snippets.jsonl"
ROWS = [json.loads(l) for l in FIX.read_text(encoding="utf-8").splitlines() if l.strip()]


class GoldSnippets(unittest.TestCase):
    def test_class_match_rate_does_not_drop(self):
        ok = sum(ad_class(parse_age(r["snippet"])) == r["class"] for r in ROWS)
        self.assertGreaterEqual(ok / len(ROWS), 0.88, "%d of %d snippets match" % (ok, len(ROWS)))

    def test_matching_snippets_have_the_gold_ages(self):
        bad = []
        for r in ROWS:
            terms = parse_age(r["snippet"])
            if ad_class(terms) != r["class"] or r["class"] in ("none", "preference", "ambiguous"):
                continue
            mx = max([t["max_age"] for t in terms if t.get("max_age")] or [None], key=lambda v: v or 0)
            mn = min([t["min_age"] for t in terms if t.get("min_age")] or [None], key=lambda v: v if v else 999)
            if (r["max_age"] and mx != r["max_age"]) or (r["min_age"] and mn != r["min_age"]):
                bad.append((r["snippet"], r["min_age"], r["max_age"], mn, mx))
        self.assertLessEqual(len(bad), 2, bad)

    def test_known_fixes(self):
        self.assertEqual(ad_class(parse_age("年龄18岁至32岁")), "range_or_min")
        self.assertEqual(ad_class(parse_age("年龄20——35岁")), "range_or_min")
        self.assertEqual(ad_class(parse_age("年满十八周岁")), "ambiguous")
        self.assertEqual(ad_class(parse_age("三十五岁以下")), "hard_cap")
        self.assertEqual(ad_class(parse_age("薪资最高6000元")), "none")
        self.assertEqual(ad_class(parse_age("底薪不低于4500元")), "none")
        self.assertEqual(ad_class(parse_age("团队年轻化，氛围好")), "none")
        self.assertEqual(age_status(parse_age("年龄不限")), "uncertain")

    def test_graduate_cohort_is_not_an_age_condition(self):
        self.assertEqual(ad_class(parse_age("2024届应届毕业生")), "none")


class NoSlowInput(unittest.TestCase):
    def test_long_runs_stay_fast(self):
        for text in ("岁" * 4000, "年龄18" + "-" * 4000 + "35岁", "年龄" + "1" * 4000 + "岁以下",
                     "90后" * 1300, "最好" * 2000 + "35岁", "（" * 2000 + "35岁以下" + "）" * 2000):
            t = time.time()
            parse_age(text)
            self.assertLess(time.time() - t, 2.0, text[:12])


if __name__ == "__main__":
    unittest.main()
