"""/api/stats/matrix: province x occupation cells from one grouped query, with row/column totals.
Checks: cells sum to overview totals; row/column totals agree with cells and with by_province/by_occupation;
filters are respected; an empty filter scope returns empty cells; the HTTP route answers."""
import json, os, sys, tempfile, threading, unittest, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TMP = tempfile.mkdtemp(prefix="agelens_matrix_")
os.environ["AGELENS_DB"] = os.path.join(_TMP, "t.db")  # must precede backend imports
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))

from backend import db, evidence as ev  # noqa: E402
import import_csv  # noqa: E402

DEMO = ROOT / "data" / "demo" / "demo_ads.csv"
KEYS = ("ads", "explicit", "cap", "age_wording", "with_exception", "preference", "n_max_age")


def _use_db():
    db.DB_PATH = Path(os.path.join(_TMP, "t.db"))


class Matrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _use_db()
        for suf in ("", "-wal", "-shm"):
            try: os.remove(str(db.DB_PATH) + suf)
            except FileNotFoundError: pass
        import_csv.import_file(DEMO, demo=True, chunk=100, quiet=True)

    def setUp(self):
        _use_db()  # other test modules may repoint db.DB_PATH

    def test_cells_sum_to_overview(self):
        m, o = ev.matrix({}), ev.overview({})
        self.assertTrue(m["cells"])
        self.assertEqual(sum(c["ads"] for c in m["cells"]), o["unique_ads"])
        self.assertEqual(m["total"]["ads"], o["unique_ads"])
        self.assertEqual(sum(c["explicit"] for c in m["cells"]), o["explicit_count"])
        self.assertEqual(sum(c["age_wording"] for c in m["cells"]), o["age_wording_count"])
        self.assertEqual(sum(c["with_exception"] for c in m["cells"]), o["exception_count"])
        cls = o["age_class_counts"]
        self.assertEqual(sum(c["cap"] for c in m["cells"]), cls["hard_cap"] + cls["cap_with_exception"])
        self.assertEqual(sum(c["preference"] for c in m["cells"]), cls["preference"])
        self.assertEqual(m["label"], ev.LABEL)

    def test_cells_unique_and_totals_consistent(self):
        m = ev.matrix({})
        keys = [(c["province"], c["occupation"]) for c in m["cells"]]
        self.assertEqual(len(keys), len(set(keys)))
        for r in m["provinces"]:
            for k in KEYS:
                self.assertEqual(r[k], sum(c[k] for c in m["cells"] if c["province"] == r["province"]), (r["province"], k))
        for r in m["occupations"]:
            self.assertEqual(r["ads"], sum(c["ads"] for c in m["cells"] if c["occupation"] == r["occupation"]))
        # agrees with the existing per-province endpoint (same definitions)
        bp = {r["province"]: r for r in ev.by_province({})}
        for r in m["provinces"]:
            if r["province"] is None:
                continue
            self.assertEqual(r["ads"], bp[r["province"]]["ads"])
            self.assertEqual(r["age_wording"], bp[r["province"]]["age_wording"])
            self.assertEqual(r["with_exception"], bp[r["province"]]["with_exception"])
            self.assertEqual(r["median_max_age"], bp[r["province"]]["median_max_age"])
        for c in m["cells"]:
            self.assertLessEqual(c["age_wording"], c["ads"]); self.assertLessEqual(c["cap"], c["ads"])
            self.assertEqual(c["median_max_age"] is None, c["n_max_age"] == 0)

    def test_filters_respected(self):
        full = ev.matrix({})
        occ = full["occupations"][0]["occupation"]
        m = ev.matrix({"occupation": occ})
        self.assertTrue(m["cells"])
        self.assertTrue(all(c["occupation"] == occ for c in m["cells"]) or all(occ in (c["occupation"] or "") for c in m["cells"]))
        self.assertEqual(m["total"]["ads"], ev.overview({"occupation": occ})["unique_ads"])
        prov = full["provinces"][0]["province"]
        mp = ev.matrix({"province": prov})
        self.assertEqual({c["province"] for c in mp["cells"]}, {prov})
        self.assertEqual(mp["total"]["ads"], full["provinces"][0]["ads"])
        me = ev.matrix({"age_status": "explicit"})
        self.assertEqual(me["total"]["ads"], me["total"]["explicit"])

    def test_empty_scope(self):
        m = ev.matrix({"q": "no-such-text-zzqx-0001"})
        self.assertEqual(m["cells"], []); self.assertEqual(m["provinces"], []); self.assertEqual(m["occupations"], [])
        self.assertEqual(m["total"]["ads"], 0); self.assertIsNone(m["total"]["median_max_age"])
        self.assertEqual(ev.matrix({"include_demo": "false"})["cells"], [])  # no real rows imported

    def test_http_route(self):
        from http.server import ThreadingHTTPServer
        from backend import server
        server.load_routes()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            occ = ev.matrix({})["occupations"][0]["occupation"]
            url = f"http://127.0.0.1:{httpd.server_address[1]}/api/stats/matrix?occupation=" + urllib.parse.quote(occ)
            with urllib.request.urlopen(url) as r:
                d = json.loads(r.read().decode())
            self.assertEqual(d["total"]["ads"], ev.overview({"occupation": occ})["unique_ads"])
            self.assertIn("cells", d); self.assertIn("provinces", d); self.assertIn("occupations", d)
        finally:
            httpd.shutdown(); httpd.server_close()


if __name__ == "__main__":
    unittest.main()
