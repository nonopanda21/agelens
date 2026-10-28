"""Real Zhaopin data helpers (backend/realdata.py) and the aggregator (scripts/real_aggregate.py).
Uses an in-test CSV fixture in a temp dir; never reads data/raw. The last test imports the same ads into a temp DB with
the project importer and checks that evidence.matrix() gives the same cells, so the per-ad semantics match."""
import csv, json, os, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TMP = tempfile.mkdtemp(prefix="agelens_realdata_")
os.environ.setdefault("AGELENS_DB", os.path.join(_TMP, "t.db"))  # must precede backend imports (if first)
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))

from backend import realdata as rd  # noqa: E402
import real_aggregate as ra  # noqa: E402

HEADER = ["企业名称", "招聘岗位", "工作城市", "工作区域", "最低月薪", "最高月薪", "职位描述", "学历要求", "要求经验", "招聘人数",
          "招聘类别", "初级分类", "来源平台", "公司地点", "工作地点", "招聘发布日期", "招聘结束日期", "招聘发布年份", "招聘结束年份",
          "来源", ""]
# (title, city, description, year)
ADS = [
    ("销售经理", "北京", "岗位要求：年龄35岁以下，条件优秀者可放宽。联系电话13812345678", "2022"),
    ("销售代表", "北京市", "要求：年龄22-30岁，有经验者优先。", "2022"),
    ("会计", "广州", "35岁以下优先，持有初级证书。", "2023"),
    ("会计", "深圳", "年龄不超过40岁。", "2023"),
    ("仓库管理员", "延边", "年龄18-45周岁，身体健康。", "2021"),
    ("项目经理", "上海", "负责项目推进，五年以上经验。", "2024"),
    ("护士", "成都", "年龄45岁以下。", "2024"),
    ("前台接待", "日本", "年龄30岁以下。", "2022"),       # no province: excluded from cells, counted in meta
    ("Java开发工程师", "杭州", "熟悉Spring。不限年龄。", "2022"),
    ("销售经理", "北京", "年龄40岁以下。", "2019"),         # outside the year range
    ("客服专员", "郑州", "邮箱 hr@example.com 年龄18岁以上。", "2021"),
    ("平面设计师", "苏州市", "35周岁以下。", "2022"),
]


def write_fixture(path, ads=ADS):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for i, (t, c, d, y) in enumerate(ads):
            row = [""] * 21
            row[0], row[1], row[2], row[6], row[15], row[17], row[19] = f"公司{i}", t, c, d, f"{y}-03-01 ", y, "智联招聘"
            w.writerow(row)


class CityToProvince(unittest.TestCase):
    def test_municipalities(self):
        for c in ("北京", "北京市", "上海", "上海市", "天津市", "重庆"):
            self.assertEqual(rd.city_to_province(c), c.rstrip("市"))

    def test_prefectures_and_suffixes(self):
        cases = {"广州": "广东", "苏州市": "江苏", "吉林市": "吉林", "吉林": "吉林", "朝阳": "辽宁", "海南州": "青海",
                 "海南": "海南", "西咸新区": "陕西", "石河子市": "新疆", "仙桃市": "湖北", "洋浦市/洋浦经济开发区": "海南",
                 "浦东新区": "上海", "香港": "香港", "澳门": "澳门", "莱芜": "山东", " 成都 ": "四川"}
        for c, p in cases.items():
            self.assertEqual(rd.city_to_province(c), p, c)

    def test_autonomous_prefectures(self):
        cases = {"延边": "吉林", "延边朝鲜族自治州": "吉林", "黔东南苗族侗族自治州": "贵州", "阿克苏地区": "新疆",
                 "凉山彝族自治州": "四川", "锡林郭勒盟": "内蒙古", "兴安盟": "内蒙古", "大兴安岭": "黑龙江", "湘西": "湖南"}
        for c, p in cases.items():
            self.assertEqual(rd.city_to_province(c), p, c)

    def test_unknown(self):
        for c in ("日本", "全国", "其他", "国外", "城区", "", None, "官网：www.example.cn", "Atlantis"):
            self.assertIsNone(rd.city_to_province(c), c)

    def test_province_names_are_canonical(self):
        from backend.evidence import PROVINCES
        names = {p["name"] for p in PROVINCES}
        self.assertTrue(set(rd.CITY_PROVINCE.values()) <= names)


class OccupationOf(unittest.TestCase):
    CASES = {
        "销售": ["销售经理", "销售代表", "大客户经理", "医药代表", "外贸业务员", "电话销售", "置业顾问", "招商经理", "销售工程师"],
        "工程技术": ["Java开发工程师", "电气工程师", "软件测试工程师", "运维工程师", "前端开发工程师", "机械设计工程师", "施工员",
                     "机电工程师", "结构设计师"],
        "采购": ["采购专员", "采购经理", "采购工程师"],
        "客户服务": ["客服专员", "在线客服", "售后服务专员", "电话客服"],
        "物流仓储": ["仓库管理员", "物流专员", "叉车司机", "快递员", "报关员"],
        "财务": ["会计", "出纳", "财务经理", "审计专员", "税务会计", "销售会计"],
        "运营管理": ["运营专员", "电商运营", "门店店长", "运营经理"],
        "市场营销": ["市场专员", "新媒体运营", "品牌经理", "文案策划", "活动策划"],
        "生产制造": ["普工", "质检员", "工艺工程师", "车间主任", "焊工", "维修电工", "数控车工"],
        "行政": ["行政专员", "前台接待", "办公室文员", "总经理助理", "董事长秘书"],
        "人力资源": ["人事专员", "招聘专员", "HRBP", "薪酬绩效专员", "人事行政主管", "培训专员"],
        "设计": ["平面设计师", "UI设计师", "室内设计师", "电商美工", "视频剪辑"],
        "数据分析": ["数据分析师", "商业分析专员", "报表专员"],
        "教育培训": ["英语老师", "课程顾问", "培训讲师", "班主任", "教务专员"],
        "医疗护理": ["护士", "内科医生", "康复治疗师", "药剂师"],
        "法务合规": ["法务专员", "律师助理", "合规专员", "专利代理人"],
        "其他": ["项目经理", "总经理", "保安", "司机", "厨师", "区域经理", "", "实习生", "保洁员"],
    }

    def test_categories(self):
        for cat, titles in self.CASES.items():
            for t in titles:
                self.assertEqual(rd.occupation_of(t), cat, t)

    def test_tricky(self):
        self.assertEqual(rd.occupation_of("机电工程师"), "工程技术")       # 机电工程 must not hit 电工
        self.assertEqual(rd.occupation_of("汽车工程师"), "工程技术")       # 汽车工程 must not hit 车工
        self.assertNotEqual(rd.occupation_of("阴极保护工程师"), "医疗护理")  # 保护工程 must not hit 护工
        self.assertEqual(rd.occupation_of("医疗器械销售"), "销售")
        self.assertEqual(rd.occupation_of(None), "其他")

    def test_only_known_categories(self):
        for titles in self.CASES.values():
            for t in titles:
                self.assertIn(rd.occupation_of(t), rd.OCCUPATIONS + (rd.OTHER,))


class MaskContacts(unittest.TestCase):
    def test_mobile(self):
        self.assertEqual(rd.mask_contacts("请联系13812345678王经理"), "请联系[phone]王经理")
        self.assertEqual(rd.mask_contacts("电话：138-1234-5678"), "电话：[phone]")
        self.assertEqual(rd.mask_contacts("+86 13912345678"), "[phone]")

    def test_landline_and_400(self):
        self.assertEqual(rd.mask_contacts("座机010-12345678转123"), "座机[tel]")
        self.assertEqual(rd.mask_contacts("（0571）87654321"), "[tel]")
        self.assertEqual(rd.mask_contacts("热线400-123-4567"), "热线[tel]")
        self.assertEqual(rd.mask_contacts("电话：87654321"), "电话：[tel]")

    def test_email(self):
        self.assertEqual(rd.mask_contacts("简历发送至 hr.zhang@example.com.cn 谢谢"), "简历发送至 [email] 谢谢")

    def test_keeps_age_and_money(self):
        s = "年龄35岁以下，月薪8000-12000元，2023年起，工作经验3-5年"
        self.assertEqual(rd.mask_contacts(s), s)
        self.assertEqual(rd.mask_contacts(""), "")
        self.assertIsNone(rd.mask_contacts(None))


class Measures(unittest.TestCase):
    def test_cap_with_exception(self):
        m, mx, cls = rd.ad_measures("销售经理", "年龄35岁以下，条件优秀者可放宽。")
        self.assertEqual(cls, "cap_with_exception")
        self.assertEqual((m["explicit"], m["cap"], m["age_wording"], m["with_exception"], m["preference"], mx), (1, 1, 1, 1, 0, 35))

    def test_preference_has_no_max_age(self):
        m, mx, cls = rd.ad_measures("会计", "35岁以下优先")
        self.assertEqual((cls, m["preference"], m["cap"], mx), ("preference", 1, 0, None))

    def test_none(self):
        m, mx, cls = rd.ad_measures("项目经理", "负责项目推进")
        self.assertEqual((cls, sum(m.values()), mx), ("none", 0, None))


class Aggregator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp(prefix="agelens_realagg_"))
        cls.csv = cls.dir / "fixture.csv"
        write_fixture(cls.csv)
        cls.out = cls.dir / "matrix.json"
        cls.m = ra.main(["--years", "2021-2024", "--csv", str(cls.csv), "--out", str(cls.out), "--workers", "2"])
        cls.data = json.loads(cls.out.read_text(encoding="utf-8"))

    def test_shape(self):
        d = self.data
        self.assertEqual(set(d), {"cells", "provinces", "occupations", "total", "filters_applied", "using_demo", "label", "meta"})
        self.assertFalse(d["using_demo"])
        self.assertEqual(d["label"], "Real data · Zhaopin job ads 2021–2024")
        keys = {"ads", "explicit", "cap", "age_wording", "with_exception", "preference", "n_max_age", "median_max_age"}
        for c in d["cells"]:
            self.assertEqual(set(c), keys | {"province", "occupation"})
        for p in d["provinces"]:
            self.assertEqual(set(p), keys | {"province"})
        for o in d["occupations"]:
            self.assertEqual(set(o), keys | {"occupation"})
        self.assertEqual(set(d["total"]), keys)
        for k in ("source", "years", "rows_in_file", "rows_in_years", "rows_used", "rows_no_province", "rows_other_occupation",
                  "distinct_cities_unmapped", "rule_version", "generated_at", "method", "by_year"):
            self.assertIn(k, d["meta"])
        self.assertEqual(set(d["meta"]["by_year"][0]), {"year", "ads", "age_wording", "explicit", "cap", "with_exception", "median_max_age"})

    def test_counts(self):
        d, mt = self.data, self.data["meta"]
        self.assertEqual(mt["rows_in_file"], len(ADS))
        self.assertEqual(mt["rows_in_years"], len(ADS) - 1)          # the 2019 row is out of range
        self.assertEqual(mt["rows_no_province"], 1)                   # 日本
        self.assertEqual(mt["rows_used"], len(ADS) - 2)
        self.assertEqual(mt["rows_other_occupation"], 1)              # 项目经理
        self.assertEqual(mt["distinct_cities_unmapped"], ["日本"])
        self.assertEqual(d["total"]["ads"], mt["rows_used"])
        self.assertEqual(sum(c["ads"] for c in d["cells"]), d["total"]["ads"])
        self.assertEqual(sum(p["ads"] for p in d["provinces"]), d["total"]["ads"])
        self.assertEqual(sum(y["ads"] for y in mt["by_year"]), d["total"]["ads"])
        bj = next(p for p in d["provinces"] if p["province"] == "北京")
        self.assertEqual((bj["ads"], bj["cap"], bj["with_exception"], bj["n_max_age"], bj["median_max_age"]), (2, 1, 1, 2, 32.5))
        gd = next(p for p in d["provinces"] if p["province"] == "广东")   # 35岁以下优先 (preference) + 不超过40岁 (cap)
        self.assertEqual((gd["ads"], gd["preference"], gd["cap"], gd["n_max_age"], gd["median_max_age"]), (2, 1, 1, 1, 40))
        self.assertEqual(mt["ads_with_max_age"], d["total"]["n_max_age"])
        self.assertEqual(sum(mt["max_age_counts"].values()), mt["ads_with_max_age"])
        # 35: 北京 35岁以下 + 苏州 35周岁以下; 30: top of 北京 22-30岁; 40: 深圳; 45: 延边 18-45 + 成都. Excluded: 广州 35岁以下优先
        # (preference), 日本 30岁以下 (no province), the 2019 ad (out of range).
        self.assertEqual(mt["max_age_counts"], {"30": 1, "35": 2, "40": 1, "45": 2})
        self.assertEqual(sum(sum(v.values()) for v in mt["max_age_counts_by_year"].values()), mt["ads_with_max_age"])
        self.assertEqual(set(mt["max_age_counts_by_year"]), {"2021", "2022", "2023", "2024"})
        self.assertIn("其他", {o["occupation"] for o in d["occupations"]})
        self.assertNotIn(None, {c["province"] for c in d["cells"]})

    def test_no_text_leaks(self):
        raw = self.out.read_text(encoding="utf-8")
        for t, c, desc, y in ADS:
            self.assertNotIn(desc[:8], raw)
        for s in ("13812345678", "example.com", "公司0", "条件优秀者"):
            self.assertNotIn(s, raw)

    def test_cube_roundtrip(self):
        cube, stats = ra.stream_cube(self.csv, None, 2, progress=False)
        p = self.dir / "cube.json"
        ra.save_cube(cube, stats, p)
        cube2, stats2 = ra.load_cube(p)
        a = ra.build_matrix(cube, [2021, 2022, 2023, 2024], stats, generated_at="x")
        b = ra.build_matrix(cube2, [2021, 2022, 2023, 2024], stats2, generated_at="x")
        self.assertEqual(a, b)
        self.assertEqual(a["cells"], self.data["cells"])
        self.assertEqual(a["meta"]["distinct_cities_unmapped"], ["日本"])

    def test_median_counter_matches_statistics(self):
        import statistics
        from collections import Counter
        for xs in ([35], [35, 40], [30, 35, 35, 40], [18, 45, 45], list(range(20, 60, 3))):
            self.assertEqual(ra.median_counter(Counter(xs)), statistics.median(xs))
        self.assertIsNone(ra.median_counter(Counter()))

    def test_parse_years(self):
        self.assertEqual(ra.parse_years("2021-2024"), [2021, 2022, 2023, 2024])
        self.assertEqual(ra.parse_years("2022"), [2022])

    def test_same_as_evidence_matrix(self):
        """Import the same in-range, mapped ads (text = title + newline + description) with the project importer into a
        temp DB and compare evidence.matrix() with the aggregate: per-ad semantics must agree."""
        from backend import db, evidence as ev
        import import_csv
        old = db.DB_PATH
        db.DB_PATH = self.dir / "eq.db"
        try:
            src = self.dir / "eq.csv"
            with open(src, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["title", "company", "province", "city", "category", "description"])
                for i, (t, c, d, y) in enumerate(ADS):
                    p = rd.city_to_province(c)
                    if p is None or not 2021 <= int(y) <= 2024:
                        continue
                    w.writerow([t, f"公司{i}", p, c, rd.occupation_of(t), rd.ad_text(t, d)])
            import_csv.import_file(src, quiet=True)
            m = ev.matrix({"include_demo": "false"})
        finally:
            db.DB_PATH = old
        self.assertEqual(m["total"], self.data["total"])
        self.assertEqual(m["cells"], self.data["cells"])
        self.assertEqual(m["provinces"], self.data["provinces"])
        self.assertEqual(m["occupations"], self.data["occupations"])


if __name__ == "__main__":
    unittest.main()
