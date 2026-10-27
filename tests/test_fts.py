"""Full-text index for the free-text search filter: results must equal the old LIKE substring search, and the index must
stay in sync with inserts, deletes and text updates (external-content FTS5 + triggers)."""
import sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
from backend import db, evidence as ev  # noqa: E402
import import_csv  # noqa: E402

DEMO = ROOT / "data" / "demo" / "demo_ads.csv"


def like_ids(q):
    with db.connect() as c:
        s = "%" + q + "%"
        return {r[0] for r in c.execute("SELECT id FROM ads WHERE title LIKE ? OR description LIKE ?", (s, s))}


def fts_ids(q):
    out, page = set(), 1
    while True:
        r = ev.search_ads({"q": q, "include_demo": True}, page=page, page_size=100)
        out |= {a["id"] for a in r["items"]}
        if page * 100 >= r["total"]:
            return out, r["total"]
        page += 1


class FullTextSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="agelens_fts_")
        cls.prev = db.DB_PATH
        db.DB_PATH = Path(cls.tmp) / "fts.db"
        import_csv.import_file(DEMO, demo=True, chunk=100, quiet=True)

    @classmethod
    def tearDownClass(cls):
        db.DB_PATH = cls.prev

    def test_same_results_as_like(self):
        for q in ["35岁以下", "可放宽", "工作经验", "岁以下，", "不限年龄", "Excel", "zzz-no-such-text"]:
            ids, total = fts_ids(q)
            self.assertEqual(ids, like_ids(q), q); self.assertEqual(total, len(ids), q)

    def test_index_exists_and_is_used(self):
        fts_ids("35岁以下")
        with db.connect() as c:
            self.assertIsNotNone(c.execute("SELECT 1 FROM sqlite_master WHERE name='ads_fts'").fetchone())
            plan = " ".join(r[-1] for r in c.execute("EXPLAIN QUERY PLAN SELECT id FROM ads a WHERE a.rowid IN (SELECT rowid FROM ads_fts WHERE ads_fts MATCH '\"35岁以下\"')"))
        self.assertIn("ads_fts", plan)

    def test_short_query_falls_back_to_like(self):
        ids, _ = fts_ids("35")            # 2 characters: trigram cannot match, LIKE path is used
        self.assertEqual(ids, like_ids("35"))

    def test_triggers_keep_index_in_sync(self):
        fts_ids("abc")  # ensure index + triggers exist
        with db.connect() as c:
            b = c.execute("SELECT batch_id, raw_id FROM ads LIMIT 1").fetchone()
            c.execute("INSERT INTO ads(id,batch_id,raw_id,title,description,is_demo) VALUES ('ad_ftstest',?,?,'Sync check','唯一测试短语甲乙丙',1)", (b[0], b[1]))
            c.commit()
        self.assertEqual(fts_ids("唯一测试短语")[0], {"ad_ftstest"})
        with db.connect() as c:
            c.execute("UPDATE ads SET description='已更新的独特文本' WHERE id='ad_ftstest'"); c.commit()
        self.assertEqual(fts_ids("唯一测试短语")[0], set()); self.assertEqual(fts_ids("已更新的独特")[0], {"ad_ftstest"})
        with db.connect() as c:
            c.execute("DELETE FROM ads WHERE id='ad_ftstest'"); c.commit()
        self.assertEqual(fts_ids("已更新的独特")[0], set())

    def test_quotes_in_query_are_safe(self):
        ids, _ = fts_ids('岁以下" OR "x')   # must be treated as a literal phrase, never as FTS syntax
        self.assertEqual(ids, like_ids('岁以下" OR "x'))


if __name__ == "__main__":
    unittest.main()
