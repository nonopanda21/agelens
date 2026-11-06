#!/usr/bin/env python3
"""Simulated power of the randomized test: the chance of meeting the full rule, not only of beating zero.
Every input is an assumption (no pilot exists). Replace --score-sd and --time-sd with pilot values.

  python scripts/rct_power.py [--sims 4000] [--score-sd 20] [--time-sd 25] [--out data/study/power_rct.md]

Pass = beta >= 10 and its robust 95% CI above 0. Joint pass = also theta's robust 95% CI below 0. People vary as normal draws, scores
clipped to 0-100 and times to 0-120, around a control mean of 60 points and 60 seconds. One-regressor OLS on a balanced design.
"""
import argparse, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend.rct_stats import GAIN_POINTS, t_crit  # noqa: E402

NS = (20, 30, 40, 60, 80, 126, 200)
SCENARIOS = [(0, 0), (5, -5), (10, -5), (10, -10), (15, -10), (20, -10)]
CONTROL_SCORE, CONTROL_TIME = 60.0, 60.0


def diff_ci(a, b, tc):
    n1, n0 = len(a), len(b)
    m1, m0 = sum(a) / n1, sum(b) / n0
    v1, v0 = sum((x - m1) ** 2 for x in a), sum((x - m0) ** 2 for x in b)
    n = n1 + n0
    se = (n / (n - 2) * (v1 / n1 ** 2 + v0 / n0 ** 2)) ** 0.5  # HC1 for one binary regressor
    return m1 - m0, m1 - m0 - tc * se, m1 - m0 + tc * se


def run(n, gain, save, score_sd, time_sd, sims, rng, tc):
    zero = rule = joint = 0
    clip = lambda v, hi: max(0.0, min(hi, v))
    for _ in range(sims):
        h = n // 2
        s1 = [clip(rng.gauss(CONTROL_SCORE + gain, score_sd), 100) for _ in range(h)]
        s0 = [clip(rng.gauss(CONTROL_SCORE, score_sd), 100) for _ in range(h)]
        t1 = [clip(rng.gauss(CONTROL_TIME + save, time_sd), 120) for _ in range(h)]
        t0 = [clip(rng.gauss(CONTROL_TIME, time_sd), 120) for _ in range(h)]
        b, lo, _hi = diff_ci(s1, s0, tc)
        _t, _lo, hi = diff_ci(t1, t0, tc)
        zero += lo > 0
        ok = b >= GAIN_POINTS and lo > 0
        rule += ok
        joint += ok and hi < 0
    return zero / sims, rule / sims, joint / sims


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sims", type=int, default=4000)
    ap.add_argument("--score-sd", type=float, default=20)
    ap.add_argument("--time-sd", type=float, default=25)
    ap.add_argument("--seed", type=int, default=20261105)
    ap.add_argument("--out", default=str(ROOT / "data" / "study" / "power_rct.md"))
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    L = ["# Simulated power, randomized test (assumptions, not data)", "",
         "`scripts/rct_power.py`, %d simulated studies per row, seed %d. Score SD %g points and time SD %g seconds are assumptions; there is no pilot. Control mean 60 points, 60 seconds." % (a.sims, a.seed, a.score_sd, a.time_sd),
         "", "| N | True gain (points) | True time change (s) | CI above 0 | Accuracy rule | Both rules |", "|---:|---:|---:|---:|---:|---:|"]
    for n in NS:
        tc = t_crit(n - 2)
        for gain, save in SCENARIOS:
            z, r, j = run(n, gain, save, a.score_sd, a.time_sd, a.sims, rng, tc)
            L.append("| %d | %+g | %+g | %.3f | %.3f | %.3f |" % (n, gain, save, z, r, j))
    text = "\n".join(L) + "\n"
    Path(a.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
