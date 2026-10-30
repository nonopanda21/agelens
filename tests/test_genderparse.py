"""backend/genderparse.py (gender-rules-1.0.0): regression snippets from the blind gold set, and the documented decisions."""
import json, sys, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import genderparse as gp  # noqa: E402

SNIPPETS = [json.loads(l) for l in (ROOT / "tests" / "fixtures" / "gender_gold_snippets.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def cls(t):
    return gp.gender_class(gp.parse_gender(t))


class Snippets(unittest.TestCase):
    def test_fixture_is_short_and_masked(self):
        self.assertGreaterEqual(len(SNIPPETS), 40)
        for r in SNIPPETS:
            self.assertLessEqual(len(r["snippet"]), 40)
            self.assertIn(r["label"], gp.CLASSES)
            self.assertNotRegex(r["snippet"], r"1[3-9]\d{9}|@")

    def test_snippets(self):
        bad = [(r["snippet"], r["label"], cls(r["snippet"])) for r in SNIPPETS if cls(r["snippet"]) != r["label"]]
        self.assertEqual(bad, [])

    def test_all_classes_covered(self):
        self.assertEqual({r["label"] for r in SNIPPETS}, set(gp.CLASSES))


class Decisions(unittest.TestCase):
    def test_version_and_shape(self):
        self.assertEqual(gp.RULE_VERSION, "gender-rules-1.0.0")
        t = gp.parse_gender("任职要求：限女，25岁以下")[0]
        self.assertEqual(t["kind"], "female_only")
        self.assertEqual("任职要求：限女，25岁以下"[t["start"]:t["end"]], "限女")
        self.assertIn("限女", t["snippet"])
        self.assertEqual(gp.parse_gender(""), [])
        self.assertEqual(gp.parse_gender(None), [])
        self.assertEqual(gp.gender_class([]), "none")

    def test_restrictions_and_preferences(self):
        for text, want in (("仅限男性", "male_only"), ("性别：女", "female_only"), ("前台（女）", "female_only"),
                           ("男士优先", "male_preferred"), ("优先考虑女性", "female_preferred"), ("女生优先", "female_preferred")):
            self.assertEqual(cls(text), want, text)

    def test_no_limit_wordings(self):
        for text in ("男女不限", "性别不限", "不限性别", "男女均可", "男/女不限", "招男女普工", "招聘男女各3名", "男士女士都可以"):
            self.assertEqual(cls(text), "no_limit", text)

    def test_conflict(self):
        self.assertEqual(cls("限男，限女"), "conflict")
        self.assertEqual(cls("限女，男女不限"), "conflict")
        self.assertEqual(cls("男性优先，仅限女士"), "conflict")

    def test_preference_inside_no_limit(self):
        self.assertEqual(cls("男女不限，女生优先"), "female_preferred")

    def test_not_counted(self):
        for text in ("女装销售", "男装导购，限本地", "母婴店长", "女士护理产品", "男科医院护士", "男女老少皆宜", "联系人：王女士",
                     "面向女性客户", "男同事较多", "男员工陪产假", "提供女生宿舍", "子女优先入学", "陪男女朋友", "宝妈优先",
                     "帅哥美女欢迎", "身高男性170以上"):
            self.assertEqual(cls(text), "none", text)

    def test_one_sex_standard_is_not_a_requirement(self):
        self.assertEqual(cls("女性身高165cm以上"), "none")
        self.assertEqual(cls("男性身高170cm以上，女性身高160cm以上"), "no_limit")

    def test_pathological_input_is_fast(self):
        for t in ("男、" * 20000, "性别" + " " * 50000 + "男", "限" * 30000 + "男", "（男）" * 8000):
            t0 = time.time()
            gp.parse_gender(t)
            self.assertLess(time.time() - t0, 2.0)


if __name__ == "__main__":
    unittest.main()
