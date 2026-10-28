"""Real-data matrix endpoints: /api/stats/matrix?source=real and /api/real/status.
Uses a temp DB (AGELENS_DB) and a temp real-data directory (AGELENS_REAL_DIR); never touches data/real."""
import json, os, sys, tempfile, threading, time, unittest, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TMP = tempfile.mkdtemp(prefix="agelens_realapi_")
os.environ["AGELENS_DB"] = os.path.join(_TMP, "t.db")  # must precede backend imports
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))

from backend import db, api_data  # noqa: E402
import import_csv  # noqa: E402

DEMO = ROOT / "data" / "demo" / "demo_ads.csv"
REAL = Path(_TMP) / "real"


def _matrix(label, ads, rows_used):
    row = {"ads": ads, "explicit": 1, "cap": 1, "age_wording": 2, "with_exception": 0, "preference": 0, "n_max_age": 1, "median_max_age": 35.0}
    return {"cells": [dict(row, province="广东", occupation="销售")], "provinces": [dict(row, province="广东")],
            "occupations": [dict(row, occupation="销售")], "total": dict(row), "filters_applied": {}, "using_demo": False, "label": label,
            "meta": {"source": "test", "years": [2021, 2022, 2023, 2024], "rows_used": rows_used, "generated_at": "2026-01-01T00:00:00Z",
                     "method": "test method"}}


def _write(name, obj, mtime=None):
    p = REAL / name
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


class RealApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.DB_PATH = Path(os.environ["AGELENS_DB"])
        for suf in ("", "-wal", "-shm"):
            try: os.remove(str(db.DB_PATH) + suf)
            except FileNotFoundError: pass
        import_csv.import_file(DEMO, demo=True, chunk=100, quiet=True)
        from http.server import ThreadingHTTPServer
        from backend import server
        server.load_routes()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()

    def setUp(self):
        db.DB_PATH = Path(os.environ["AGELENS_DB"])
        self._env = {k: os.environ.get(k) for k in ("AGELENS_REAL_DIR", "AGELENS_REAL_FIXTURE")}
        os.environ["AGELENS_REAL_DIR"] = str(REAL)
        os.environ.pop("AGELENS_REAL_FIXTURE", None)
        if REAL.exists():
            for f in REAL.iterdir(): f.unlink()
        else:
            REAL.mkdir()
        api_data._REAL_CACHE.clear()

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

    def test_no_file_404_and_status_unavailable(self):
        st, d = self.get("/api/stats/matrix?source=real")
        self.assertEqual(st, 404); self.assertIn("real", d["error"].lower())
        st, d = self.get("/api/real/status")
        self.assertEqual(st, 200); self.assertFalse(d["available"])
        REAL.rmdir()  # a missing directory behaves the same
        self.assertFalse(self.get("/api/real/status")[1]["available"])
        self.assertEqual(self.get("/api/stats/matrix?source=real")[0], 404)

    def test_demo_unchanged(self):
        _write("matrix_zhaopin_2021-2024.json", _matrix("Real data · test", 5, 5))
        a = self.get("/api/stats/matrix")[1]
        b = self.get("/api/stats/matrix?source=demo")[1]
        self.assertEqual(a, b)
        self.assertTrue(a["using_demo"]); self.assertNotIn("meta", a)
        self.assertEqual(self.get("/api/stats/matrix?source=bogus")[0], 400)

    def test_serves_newest_real_file_and_status(self):
        now = time.time()
        _write("matrix_old.json", _matrix("Old", 1, 11), now - 100)
        _write("matrix_zhaopin_2021-2024.json", _matrix("Real data · new", 9, 99), now)
        st, d = self.get("/api/stats/matrix?source=real")
        self.assertEqual(st, 200); self.assertEqual(d["label"], "Real data · new"); self.assertFalse(d["using_demo"])
        for k in ("cells", "provinces", "occupations", "total", "meta"):
            self.assertIn(k, d)
        st, s = self.get("/api/real/status")
        self.assertEqual(s["available"], True); self.assertEqual(s["label"], "Real data · new")
        self.assertEqual(s["rows_used"], 99); self.assertEqual(s["years"], [2021, 2022, 2023, 2024])
        self.assertEqual(s["method"], "test method"); self.assertEqual(s["generated_at"], "2026-01-01T00:00:00Z")

    def test_fixture_only_with_env(self):
        _write("_fixture_matrix.json", _matrix("Fixture", 3, 3))
        self.assertEqual(self.get("/api/stats/matrix?source=real")[0], 404)
        self.assertFalse(self.get("/api/real/status")[1]["available"])
        os.environ["AGELENS_REAL_FIXTURE"] = "1"
        st, d = self.get("/api/stats/matrix?source=real")
        self.assertEqual(st, 200); self.assertEqual(d["label"], "Fixture")
        # a real file still wins when it is newer
        _write("matrix_real.json", _matrix("Real", 4, 4), time.time() + 5)
        self.assertEqual(self.get("/api/stats/matrix?source=real")[1]["label"], "Real")

    def test_cache_keyed_by_mtime(self):
        p = _write("matrix_a.json", _matrix("First", 1, 1), time.time() - 50)
        self.assertEqual(api_data.load_real()["label"], "First")
        first = api_data.load_real()
        self.assertIs(api_data.load_real(), first)  # cached object reused
        _write("matrix_a.json", _matrix("Second", 2, 2), time.time())
        self.assertEqual(api_data.load_real()["label"], "Second")
        self.assertTrue(p.exists())

    def test_broken_file_is_unavailable(self):
        (REAL / "matrix_bad.json").write_text("{not json", encoding="utf-8")
        self.assertIsNone(api_data.load_real())
        self.assertFalse(self.get("/api/real/status")[1]["available"])
        self.assertEqual(self.get("/api/stats/matrix?source=real")[0], 404)


if __name__ == "__main__":
    unittest.main()
