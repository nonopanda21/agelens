#!/usr/bin/env python3
"""Power of the crossover-ai-v1 primary analysis (paired accuracy difference, AI minus template). Stdlib, seeded.
ASSUMPTIONS, not data: template accuracy 0.60; person ability varies (logit SD 0.8); task fact counts T1 3, T2 4, T3 3, T4 3 (the AI tool gets set S1 or S2);
the AI effect is an additive shift of the per-fact probability. 'Benefit rule' = mean D >= +0.10 AND t-based 95% CI lower bound > 0 AND p < 0.05 (t approximation;
the real analysis uses the exact/permutation test and a bootstrap CI). Usage: python3 scripts/power_ai.py [--sims 3000] [--out data/study/power_ai.md]"""
import argparse, math, random, sys
from pathlib import Path
FACTS = {"T1": 3, "T2": 4, "T3": 3, "T4": 3}
SETS = {"S1": ("T1", "T3"), "S2": ("T2", "T4")}
T975 = {7: 2.365, 11: 2.201, 15: 2.131, 23: 2.069, 31: 2.040, 47: 2.012}
def expit(x): return 1 / (1 + math.exp(-x))
def logit(p): return math.log(p / (1 - p))
def one(n, eff, base, sd, rng, carry=0.0):
    d = []
    for i in range(n):
        a = rng.gauss(0, sd); ai_set = SETS["S1" if i % 2 else "S2"]
        acc = {}
        for t, k in FACTS.items():
            p = expit(logit(min(max(base + (eff if t in ai_set else 0), .02), .98)) + a)
            acc[t] = sum(rng.random() < p for _ in range(k)) / k
        d.append(sum(acc[t] for t in ai_set) / 2 - sum(acc[t] for t in FACTS if t not in ai_set) / 2)
    return d
def run(n, eff, sims, base=0.60, sd=0.8, seed=20261023):
    rng = random.Random(seed + n * 7 + int(eff * 1000)); hit = sig = 0; sds = []
    tcrit = T975.get(n - 1, 2.0)
    for _ in range(sims):
        d = one(n, eff, base, sd, rng); m = sum(d) / n; s = math.sqrt(sum((x - m) ** 2 for x in d) / (n - 1)); sds.append(s)
        se = s / math.sqrt(n) or 1e-9; lo = m - tcrit * se
        sig += lo > 0; hit += (m >= 0.10 - 1e-12 and lo > 0)
    return sig / sims, hit / sims, sum(sds) / sims
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--sims", type=int, default=3000); ap.add_argument("--out"); a = ap.parse_args()
    L = ["# Power, crossover-ai-v1 primary outcome (SIMULATION OF ASSUMPTIONS; no pilot data, no AI model run)", "",
         "Template accuracy 0.60, person logit SD 0.8, 13 key facts over 4 tasks, %d trials per cell. Benefit rule: mean D >= +0.10 and CI lower bound > 0 (t approximation).\n" % a.sims,
         "| N | true effect | P(CI lower bound > 0) | P(benefit rule met) | mean SD of D |", "|---|---|---|---|---|"]
    for n in (12, 16, 24, 32, 48):
        for eff in (0.0, 0.05, 0.10, 0.15, 0.20):
            sg, bn, sd = run(n, eff, a.sims); L.append("| %d | %+.2f | %.2f | %.2f | %.3f |" % (n, eff, sg, bn, sd))
    txt = "\n".join(L); print(txt)
    if a.out: Path(a.out).write_text(txt + "\n")
