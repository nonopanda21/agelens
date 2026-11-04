"""The power tables on #/status must match the simulation output they quote."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "frontend/pages/status.js").read_text(encoding="utf-8")


def pct(x):
    return "%d%%" % round(float(x) * 100)


class StatusPower(unittest.TestCase):
    def test_main_table(self):
        rows = {}
        for n, eff, _, ben in re.findall(r"^\| (\d+) \| \+([\d.]+) \| ([\d.]+) \| ([\d.]+) \|", (ROOT / "data/study/power_ai.md").read_text(), re.M):
            rows.setdefault(int(n), {})[eff] = pct(ben)
        for n, r in rows.items():
            self.assertIn("[%d, '%s', '%s', '%s', '%s']" % (n, r["0.00"], r["0.10"], r["0.15"], r["0.20"]), PAGE)

    def test_sensitivity_table(self):
        rows = re.findall(r"^\| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|", (ROOT / "data/study/power_ai_sensitivity.md").read_text(), re.M)
        self.assertEqual(len(rows), 5)
        for *_, a, b, c in rows:
            self.assertIn("'%s', '%s', '%s']" % (pct(a), pct(b), pct(c)), PAGE)


if __name__ == "__main__":
    unittest.main()
