"""The power table on #/status must match the simulation output it quotes, and the sentences must match the table."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "frontend/pages/status.js").read_text(encoding="utf-8")
RX = r"^\| (\d+) \| \+?(-?\d+) \| \+?(-?\d+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|"


def pct(x):
    return "%d%%" % round(float(x) * 100)


class StatusPower(unittest.TestCase):
    def setUp(self):
        self.rows = {(int(n), int(g), int(t)): (z, r, j) for n, g, t, z, r, j in re.findall(RX, (ROOT / "data/study/power_rct.md").read_text(), re.M)}

    def test_table(self):
        for n in sorted({k[0] for k in self.rows}):
            r = self.rows
            self.assertIn("[%d, '%s', '%s', '%s', '%s', '%s']" % (n, pct(r[n, 0, 0][1]), pct(r[n, 10, -10][1]), pct(r[n, 15, -10][1]), pct(r[n, 20, -10][1]), pct(r[n, 15, -10][2])), PAGE)

    def test_sentences(self):
        r = self.rows
        self.assertIn("20 points meets the accuracy rule %s of the time, 15 points %s, and 10 points %s" % (pct(r[40, 20, -10][1]), pct(r[40, 15, -10][1]), pct(r[40, 10, -10][1])), PAGE)
        self.assertIn("only about %s" % pct(r[40, 15, -10][2]), PAGE)
        self.assertLess(max(float(v[1]) for k, v in r.items() if k[1] == 10), 0.5)
        self.assertLessEqual(max(float(v[1]) for k, v in r.items() if k[1] == 0), 0.03)


if __name__ == "__main__":
    unittest.main()
