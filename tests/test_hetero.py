"""Heterogeneity pipeline: scripts/real_hetero.py (shape, sums, resumable cube) and GET /api/stats/hetero.
Uses a tiny CSV and temp dirs only; never reads data/raw or data/real."""
import csv, json, os, sys, tempfile, threading, time, unittest, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TMP = tempfile.mkdtemp(prefix="agelens_hetero_")
os.environ["AGELENS_DB"] = os.path.join(_TMP, "t.db")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))

from backend import db, api_hetero  # noqa: E402
import real_hetero as rh  # noqa: E402

# (title, city, description, experience, year)
ADS = [
    ("销售经理", "北京", "年龄35岁以下，限男。", "不限", "2022"),
    ("销售代表", "北京市", "要求：年龄22-30岁，男女不限。", "无经验", "2022"),
    ("会计", "广州", "35岁以下优先，女生优先。", "1-3年", "2023"),
    ("会计", "深圳", "年龄不超过40岁。", "3-5年", "2023"),
    ("仓库管理员", "延边", "年龄18-45周岁，限女。", "1年以下", "2021"),
    ("项目经理", "上海", "五年以上经验。", "10年以上", "2024"),
    ("护士", "成都", "年龄45岁以下。应届毕业生。", "", "2024"),
    ("前台接待", "日本", "年龄30岁以下。", "5-10年", "2022"),   # no province: counted in totals, not in the province table
    ("销售经理", "北京", "年龄40岁以下。", "不限", "2019"),       # outside the years
    ("女装导购", "杭州", "负责女装销售，联系王女士。", "不限", "2022"),  # product and contact: no gender requirement
]
HEADER = ["企业名称", "招聘岗位", "工作城市", "工作区域", "最低月薪", "最高月薪", "职位描述", "学历要求", "要求经验", "招聘人数",
          "招聘类别", "初级分类", "来源平台", "公司地点", "工作地点", "招聘发布日期", "招聘结束日期", "招聘发布年份", "招聘结束年份", "来源", ""]


def write_csv(path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for i, (t, c, d, e, y) in enumerate(ADS):
            row = [""] * 21
            row[0], row[1], row[2], row[6], row[8], row[17] = f"公司{i}", t, c, d, e, y
            w.writerow(row)


def _fixture():
    row = {"band": "No experience required", "ads": 10, "explicit": 3, "cap": 2, "age_wording": 4, "with_exception": 0, "preference": 1,
           "n_max_age": 3, "max_age_counts": {"35": 3}}
    g = {"ads": 10, "male_only": 1, "female_only": 1, "male_preferred": 0, "female_preferred": 0, "no_limit": 4, "conflict": 0, "none": 4}
    return {"meta": {"years": [2021, 2022, 2023, 2024], "rows_used": 10, "age_rule_version": "x", "gender_rule_version": "y",
                     "experience_bands": ["No experience required"], "experience_mapping": {}, "generated": "2026-01-01",
                     "source": "test", "caveat": "Counts of how ads are worded, not hiring outcomes"},
            "by_experience": [row], "by_experience_occupation": [], "by_experience_province": [],
            "gender": {"by_class": [], "by_occupation": [dict(g, occupation="Sales")], "by_experience": [dict(g, band="x")], "age_by_gender": []},
            "cohort": {"graduate_cohort_ads": 1}}


class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.csv = Path(_TMP) / "mini.csv"
        write_csv(cls.csv)
        cls.cube, cls.stats = rh.stream_cube(cls.csv, [2021, 2022, 2023, 2024], workers=1, batch=3)
        cls.res = rh.build(cls.cube, [2021, 2022, 2023, 2024], cls.stats, generated="2026-01-01")

    def test_band_mapping(self):
        for v, b in (("不限", "No experience required"), ("无经验", "No experience required"), ("1年以下", "Under 1 year"),
                     ("1-3年", "1–3 years"), ("3-5年", "3–5 years"), ("5-10年", "5+ years"), ("10年以上", "5+ years"),
                     ("", "Not stated"), ("whatever", "Not stated")):
            self.assertEqual(rh.band_of(v), b)

    def test_totals_and_years(self):
        m = self.res["meta"]
        self.assertEqual(m["rows_used"], 9)               # the 2019 row is left out
        self.assertEqual(m["rows_with_province"], 8)      # 日本 has no province
        self.assertEqual(sum(r["ads"] for r in self.res["by_experience"]), 9)
        self.assertEqual([r["band"] for r in self.res["by_experience"]], rh.BANDS)
        self.assertEqual(m["age_rule_version"], rh.AGE_VERSION)
        self.assertEqual(m["gender_rule_version"], rh.GENDER_VERSION)

    def test_age_counts(self):
        by = {r["band"]: r for r in self.res["by_experience"]}
        self.assertEqual(by["No experience required"]["ads"], 3)
        self.assertEqual(by["No experience required"]["age_wording"], 2)
        self.assertEqual(by["Under 1 year"]["explicit"], 1)

    def test_gender_counts_and_no_text(self):
        g = {r["gender_class"]: r["ads"] for r in self.res["gender"]["by_class"]}
        self.assertEqual(g.get("male_only"), 1)
        self.assertEqual(g.get("female_only"), 1)
        self.assertEqual(g.get("female_preferred"), 1)
        self.assertEqual(g.get("no_limit"), 1)
        self.assertEqual(sum(g.values()), 9)              # 女装导购 and 王女士 are not requirements
        for r in self.res["gender"]["by_occupation"]:
            self.assertEqual(r["ads"], sum(r[c] for c in rh.GENDER_CLASSES))
        blob = json.dumps(self.res, ensure_ascii=False)
        self.assertNotIn("王女士", blob); self.assertNotIn("年龄", blob)
        self.assertEqual(self.res["cohort"]["graduate_cohort_ads"], 1)

    def test_english_names_only(self):
        blob = json.dumps({k: v for k, v in self.res.items() if k != "meta"}, ensure_ascii=False)
        self.assertFalse(any("一" <= ch <= "鿿" for ch in blob))
        self.assertTrue(all(r["province"] for r in self.res["by_experience_province"]))

    def test_cube_roundtrip(self):
        p = Path(_TMP) / "cube.json"
        rh.save_cube(self.cube, self.stats, p)
        cube2, d = rh.load_cube(p)
        res2 = rh.build(cube2, [2021, 2022, 2023, 2024], d["stats"], generated="2026-01-01")
        self.assertEqual(json.dumps(res2, sort_keys=True), json.dumps(self.res, sort_keys=True))


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.DB_PATH = Path(os.environ["AGELENS_DB"])
        import import_csv
        import_csv.import_file(ROOT / "data" / "demo" / "demo_ads.csv", demo=True, chunk=100, quiet=True)
        from http.server import ThreadingHTTPServer
        from backend import server
        server.load_routes()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.real = Path(_TMP) / "real"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in ("AGELENS_REAL_DIR", "AGELENS_REAL_FIXTURE")}
        os.environ["AGELENS_REAL_DIR"] = str(self.real)
        os.environ.pop("AGELENS_REAL_FIXTURE", None)
        self.real.mkdir(exist_ok=True)
        for f in self.real.iterdir(): f.unlink()
        api_hetero._CACHE.clear()

    def tearDown(self):
        for k, v in self._env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_missing_file_is_404_with_error(self):
        st, d = self.get("/api/stats/hetero?source=real")
        self.assertEqual(st, 404); self.assertIn("error", d)
        self.real.rmdir()                                   # a missing directory behaves the same
        self.assertEqual(self.get("/api/stats/hetero?source=real")[0], 404)
        self.assertEqual(self.get("/api/health")[0], 200)  # the server keeps working

    def test_serves_file_shape(self):
        (self.real / "hetero_zhaopin_2021-2024.json").write_text(json.dumps(_fixture()), encoding="utf-8")
        st, d = self.get("/api/stats/hetero?source=real")
        self.assertEqual(st, 200)
        for k in ("meta", "by_experience", "by_experience_occupation", "by_experience_province", "gender", "cohort"):
            self.assertIn(k, d)
        for k in ("by_class", "by_occupation", "by_experience", "age_by_gender"):
            self.assertIn(k, d["gender"])
        self.assertEqual(self.get("/api/stats/hetero")[0], 200)
        self.assertEqual(self.get("/api/stats/hetero?source=demo")[0], 400)

    def test_fixture_only_with_env_and_bad_file(self):
        (self.real / "_fixture_hetero.json").write_text(json.dumps(_fixture()), encoding="utf-8")
        self.assertEqual(self.get("/api/stats/hetero?source=real")[0], 404)
        os.environ["AGELENS_REAL_FIXTURE"] = "1"
        self.assertEqual(self.get("/api/stats/hetero?source=real")[0], 200)
        (self.real / "hetero_bad.json").write_text("{not json", encoding="utf-8")
        os.utime(self.real / "hetero_bad.json", (time.time() + 5, time.time() + 5))
        self.assertEqual(self.get("/api/stats/hetero?source=real")[0], 404)


if __name__ == "__main__":
    unittest.main()
