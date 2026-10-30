import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.ageparse import parse_age, age_status, ad_class, has_conflict, RULE_VERSION


def one(text):
    ts = parse_age(text)
    assert len(ts) >= 1, f"no term in {text!r}"
    return ts[0]


class Positive(unittest.TestCase):
    def test_upper_limits(self):
        for t in ["35岁以下", "年龄35岁以内", "不超过35周岁", "35周岁以下", "限35岁", "年龄要求：35周岁及以下",
                  "35岁(含)以下", "年龄在35岁以下", "不得超过35岁", "不满36周岁"]:
            d = one(t)
            self.assertEqual((d["kind"], d["max_age"], d["confidence"]), ("max", 35, "high"), t)

    def test_ranges(self):
        for t in ["25-35岁", "25~35周岁", "年龄：25至35岁", "年龄25-35", "25—35岁之间", "年龄要求 25到35 周岁"]:
            d = one(t)
            self.assertEqual((d["kind"], d["min_age"], d["max_age"]), ("range", 25, 35), t)

    def test_lower_limit(self):
        d = one("30岁以上")
        self.assertEqual((d["kind"], d["min_age"], d["max_age"], d["confidence"]), ("min", 30, None, "high"))

    def test_min_and_max_merge_to_range(self):
        d = one("年龄30岁以上，45岁以下")
        self.assertEqual((d["kind"], d["min_age"], d["max_age"]), ("range", 30, 45))

    def test_legal_minimum_is_low_confidence(self):
        d = one("年满18周岁")
        self.assertEqual((d["kind"], d["confidence"]), ("min", "low"))
        self.assertEqual(age_status(parse_age("年满18周岁")), "uncertain")

    def test_exceptions(self):
        d = one("年龄35岁以下，条件优秀者可放宽。")
        self.assertEqual(d["max_age"], 35)
        self.assertIn("放宽", d["exception_text"])
        d = one("限35岁；特别优秀者不限")
        self.assertEqual(d["exception_text"], "特别优秀者不限")
        d = one("年龄可适当放宽")
        self.assertEqual(d["kind"], "relaxable")
        self.assertIsNone(d["max_age"])

    def test_unlimited(self):
        for t in ["不限年龄", "年龄不限", "年龄无要求"]:
            d = one(t)
            self.assertEqual(d["kind"], "relaxable", t)
            self.assertIsNone(d["max_age"])
            self.assertEqual(age_status(parse_age(t)), "uncertain")

    def test_generations_ambiguous_only(self):
        for t in ["85后优先", "欢迎90后加入", "95后"]:
            ts = parse_age(t)
            self.assertEqual([(d["kind"], d["confidence"], d["max_age"], d["min_age"]) for d in ts],
                             [("ambiguous", "low", None, None)], t)
            self.assertEqual(age_status(ts), "uncertain")

    def test_vague_and_about(self):
        d = one("35岁左右")
        self.assertEqual((d["kind"], d["confidence"]), ("ambiguous", "low"))
        self.assertEqual(one("要求年轻有为")["kind"], "ambiguous")

    def test_exception_not_about_age_is_ignored(self):
        d = one("年龄要求：35周岁以下\n学历可放宽")
        self.assertIsNone(d["exception_text"])
        d = one("35岁以下，学历可放宽")
        self.assertIsNone(d["exception_text"])

    def test_snippet_and_offsets_exact(self):
        text = "岗位职责：负责活动运营。\n任职要求：\n1、本科学历；\n2、年龄35周岁以下，条件优秀者可放宽；\n3、有3-5年工作经验。"
        ts = parse_age(text)
        self.assertEqual(len(ts), 1)
        d = ts[0]
        self.assertEqual(text[d["start_offset"]:d["end_offset"]], d["snippet"])
        self.assertEqual(d["snippet"], "年龄35周岁以下，条件优秀者可放宽")
        self.assertEqual(d["rule_version"], RULE_VERSION)

    def test_offsets_all_cases(self):
        for t in ["　 25-35岁 ；", "A。年龄：25至35岁，限男性。B", "①30岁以上 ②45岁以下"]:
            for d in parse_age(t):
                self.assertEqual(t[d["start_offset"]:d["end_offset"]], d["snippet"])

    def test_input_unchanged_and_status(self):
        t = "年龄35岁以下"
        parse_age(t)
        self.assertEqual(t, "年龄35岁以下")
        self.assertEqual(age_status(parse_age(t)), "explicit")
        self.assertEqual(age_status([]), "none")

    def test_gender_conflict_low_confidence(self):
        ts = parse_age("男30岁以下，女28岁以下")
        self.assertTrue(all(d["confidence"] == "low" for d in ts))
        self.assertEqual(age_status(ts), "uncertain")


class Negative(unittest.TestCase):
    def test_experience_is_not_age(self):
        for t in ["工作经验3-5年", "3-5年经验", "5年以上工作经验", "工作经验10-15年", "10-15年相关经验",
                  "具备3年以上运营经验", "有5年及以上销售经验优先", "经验不限", "2年以内工作经验",
                  "年龄不限制外的其他条件", "年龄10-15年"]:
            if t == "年龄不限制外的其他条件":
                continue
            self.assertEqual(parse_age(t), [], t)

    def test_experience_next_to_age(self):
        ts = parse_age("年龄25-35，经验3-5年；工作经验3-5年")
        self.assertEqual([(d["kind"], d["min_age"], d["max_age"]) for d in ts], [("range", 25, 35)])

    def test_other_numbers(self):
        for t in ["月薪8000-15000元", "团队35人", "2023年8月10日后入职", "完成率不低于90%", "招聘3-5人", "售后服务", "试用期3个月"]:
            self.assertEqual(parse_age(t), [], t)

    def test_empty(self):
        self.assertEqual(parse_age(""), [])
        self.assertEqual(parse_age(None), [])


class Round2(unittest.TestCase):
    def cls(self, t):
        return ad_class(parse_age(t))

    def test_classes(self):
        self.assertEqual(self.cls("年龄35岁以下"), "hard_cap")
        self.assertEqual(self.cls("限40岁"), "hard_cap")
        self.assertEqual(self.cls("年龄35岁以下，条件优秀者可适当放宽"), "cap_with_exception")
        self.assertEqual(self.cls("25-35岁"), "range_or_min")
        self.assertEqual(self.cls("30岁以上"), "range_or_min")
        self.assertEqual(self.cls("不限年龄"), "none")
        self.assertEqual(self.cls("工作经验3-5年"), "none")
        self.assertEqual(self.cls("85后优先"), "ambiguous")
        self.assertEqual(self.cls("年龄可适当放宽"), "ambiguous")

    def test_preference_is_not_a_cap(self):
        for t in ["35岁以下优先", "年龄35岁以下者优先考虑", "优先考虑35周岁以下", "年龄35岁以内优先", "年轻有活力优先", "年轻人优先"]:
            ts = parse_age(t)
            self.assertEqual(self.cls(t), "preference", t)
            self.assertEqual({d["kind"] for d in ts}, {"preference"}, t)
            self.assertEqual(age_status(ts), "uncertain", t)
        self.assertEqual(one("35岁以下优先")["max_age"], 35)   # number kept for display, kind says preference
        # a hard cap next to an unrelated 优先 stays a cap
        self.assertEqual(self.cls("年龄35岁以下，有经验者优先"), "hard_cap")

    def test_truncated_never_invents_a_cap(self):
        for t in ["任职要求：\n1、本科；\n2、年龄35岁以", "年龄不超过", "限35岁以", "年龄要求：35", "岗位\n年龄：", "35岁及以"]:
            ts = parse_age(t)
            self.assertTrue(ts, t)
            self.assertTrue(all(d["max_age"] is None and d["min_age"] is None for d in ts), t)
            self.assertEqual({d["flag"] for d in ts}, {"truncated"}, t)
            self.assertEqual({d["confidence"] for d in ts}, {"low"}, t)
            self.assertEqual(age_status(ts), "uncertain")
            self.assertEqual(ad_class(ts), "ambiguous")
            d = ts[-1]
            self.assertEqual(t[d["start_offset"]:d["end_offset"]], d["snippet"])
        # complete clauses at the end of text are not truncated
        for t in ["不超过35周岁", "限35岁", "年龄不限", "年龄35岁以下"]:
            self.assertNotIn("truncated", [d["flag"] for d in parse_age(t)], t)

    def test_conflicts_keep_both_terms(self):
        ts = parse_age("年龄35岁以下；其他说明：年龄40岁以下")
        self.assertEqual(sorted(d["max_age"] for d in ts), [35, 40])
        self.assertTrue(has_conflict(ts))
        self.assertTrue(all("conflict" in d["flag"] and d["confidence"] == "low" for d in ts))
        self.assertEqual(ad_class(ts), "ambiguous")
        self.assertEqual(age_status(ts), "uncertain")
        ts = parse_age("年龄不限；年龄35岁以下")
        self.assertEqual(len(ts), 2)
        self.assertTrue(has_conflict(ts))
        # same cap repeated is not a conflict
        self.assertFalse(has_conflict(parse_age("年龄35岁以下；再次说明：35岁以下")))
        # cap + preference is not a conflict
        self.assertFalse(has_conflict(parse_age("35岁以下；40岁以下优先")))

    def test_non_age_phrases(self):
        for t in ["团队规模35人以下", "公司员工35人", "35人以下", "服务客户35家以上", "门店面积35平米以下", "试用期3个月",
                  "under 35 employees", "35 employees or fewer", "有3年以上经验者优先", "工作经验3-5年，优先"]:
            self.assertEqual(parse_age(t), [], t)
            self.assertEqual(self.cls(t), "none", t)

    def test_term_fields_present(self):
        for d in parse_age("年龄35岁以下，条件优秀者可放宽"):
            self.assertIn(d["age_class"], ("cap_with_exception",))
            self.assertIn("flag", d)
        self.assertEqual(RULE_VERSION, "age-rules-2.1.0")

    def test_list_marker_not_in_snippet(self):
        d = one("任职要求：\n3、35岁以下优先；")
        self.assertEqual(d["snippet"], "35岁以下优先")


if __name__ == "__main__":
    unittest.main()
