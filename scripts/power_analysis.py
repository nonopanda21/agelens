#!/usr/bin/env python3
"""Power / minimum-detectable-effect for the AgeLens study (stdlib only, seeded). DRAFT inputs: nothing here is approved.

Design modelled: N participants split equally into two arms; every participant does the same 4 tasks.
Per-participant outcome  X_i = number of usable tasks (0..4); PRIMARY outcome = X_i/4 (usable share).
Repeated-task structure: beta-binomial. Participant i has latent usable-probability p_i ~ Beta with mean p_arm
and intra-class correlation rho between tasks of the same participant (rho = 1/(a+b+1)); X_i | p_i ~ Binomial(4, p_i).
rho = 0 means the 4 tasks are independent (binomial). Larger rho = less information per participant.
Arms: template mean p0 (baseline); assisted mean p0 + delta.
Tests: PRIMARY = two-sided Welch t-test on usable shares (alpha 0.05); validated against a randomisation test (--validate).
SECONDARY = Fisher exact test on 'usable on >= 3 of 4 tasks' (power computed EXACTLY from the beta-binomial pmf).
Usage: python3 scripts/power_analysis.py [--quick] [--validate] [--out data/study]
"""
import argparse, json, math, random, sys
from pathlib import Path

ALPHA = 0.05
K = 4  # tasks per participant


# ---------- distributions ----------
def _betacf(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-30 else 1e-30); h = d
    for m in range(1, 200):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c; c = c if abs(c) > 1e-30 else 1e-30
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c; c = c if abs(c) > 1e-30 else 1e-30
        de = d * c; h *= de
        if abs(de - 1) < 1e-12:
            break
    return h


def betainc(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbeta) * _betacf(a, b, x) / a
    return 1 - math.exp(lbeta) * _betacf(b, a, 1 - x) / b


def t_two_sided_p(t, df):
    return betainc(df / 2, 0.5, df / (df + t * t))


def welch_p(x, y):
    n1, n2 = len(x), len(y)
    m1, m2 = sum(x) / n1, sum(y) / n2
    v1 = sum((u - m1) ** 2 for u in x) / (n1 - 1); v2 = sum((u - m2) ** 2 for u in y) / (n2 - 1)
    se2 = v1 / n1 + v2 / n2
    if se2 <= 0:
        return 1.0 if m1 == m2 else 0.0
    t = (m2 - m1) / math.sqrt(se2)
    df = se2 ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1) or 1e-300)
    return t_two_sided_p(t, df)


def fisher_p(a, n1, b, n2):
    """Two-sided Fisher exact p (sum of tables no more likely than observed). a/n1 events in arm 1, b/n2 in arm 2."""
    m = a + b; n = n1 + n2
    lo, hi = max(0, m - n2), min(m, n1)
    pm = lambda k: math.comb(n1, k) * math.comb(n2, m - k) / math.comb(n, m)
    p0 = pm(a)
    return min(1.0, sum(pm(k) for k in range(lo, hi + 1) if pm(k) <= p0 * (1 + 1e-9)))


def wilson(x, n, z=1.959964):
    if n == 0: return (float("nan"), float("nan"))
    p = x / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - w, c + w


def newcombe_diff(x1, n1, x2, n2):
    """Newcombe hybrid-score CI for p2 - p1 (method 10, Newcombe 1998)."""
    l1, u1 = wilson(x1, n1); l2, u2 = wilson(x2, n2)
    d = x2 / n2 - x1 / n1; p1, p2 = x1 / n1, x2 / n2
    return d, d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2), d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)


# ---------- beta-binomial ----------
def ab(p, rho):
    s = (1 - rho) / rho
    return p * s, (1 - p) * s


def bb_pmf(p, rho, k=K):
    if rho <= 1e-9:
        return [math.comb(k, j) * p ** j * (1 - p) ** (k - j) for j in range(k + 1)]
    a, b = ab(p, rho)
    lb = lambda x, y: math.lgamma(x) + math.lgamma(y) - math.lgamma(x + y)
    return [math.comb(k, j) * math.exp(lb(j + a, k - j + b) - lb(a, b)) for j in range(k + 1)]


def draw(rng, p, rho, n):
    out = []
    for _ in range(n):
        q = rng.betavariate(*ab(p, rho)) if rho > 1e-9 else p
        out.append(sum(rng.random() < q for _ in range(K)))
    return out


def power_primary(n_total, p0, delta, rho, sims, seed):
    rng = random.Random(seed); n = n_total // 2; hit = 0
    for _ in range(sims):
        x = draw(rng, p0, rho, n); y = draw(rng, min(0.999, p0 + delta), rho, n)
        hit += welch_p(x, y) < ALPHA
    return hit / sims


def power_fisher_ge3_exact(n_total, p0, delta, rho):
    n = n_total // 2
    q0 = sum(bb_pmf(p0, rho)[3:]); q1 = sum(bb_pmf(min(0.999, p0 + delta), rho)[3:])
    b = lambda q: [math.comb(n, k) * q ** k * (1 - q) ** (n - k) for k in range(n + 1)]
    b0, b1 = b(q0), b(q1)
    return sum(b0[i] * b1[j] for i in range(n + 1) for j in range(n + 1) if fisher_p(i, n, j, n) < ALPHA)


def mde(n_total, p0, rho, sims, seed, target=0.8):
    lo, hi = 0.0, 0.999 - p0
    if power_primary(n_total, p0, hi, rho, sims, seed) < target: return None
    for _ in range(7):
        mid = (lo + hi) / 2
        if power_primary(n_total, p0, mid, rho, sims, seed) >= target: hi = mid
        else: lo = mid
    return round(hi, 3)


def validate(sims=300, perms=1000):
    """Welch vs randomisation test agreement at N=24 (reality check of the Welch approximation)."""
    rng = random.Random(99); n = 12; ag = hw = hp = 0
    for _ in range(sims):
        x = draw(rng, 0.35, 0.2, n); y = draw(rng, 0.65, 0.2, n); pool = x + y
        obs = abs(sum(y) - sum(x)); c = 0
        for _ in range(perms):
            rng.shuffle(pool); c += abs(sum(pool[n:]) - sum(pool[:n])) >= obs
        pp = (c + 1) / (perms + 1); pw = welch_p(x, y)
        hw += pw < ALPHA; hp += pp < ALPHA; ag += (pw < ALPHA) == (pp < ALPHA)
    return {"scenario": "N=24, p0=.35, delta=.30, rho=.2", "sims": sims, "power_welch": hw / sims, "power_randomisation": hp / sims, "decision_agreement": ag / sims}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true"); ap.add_argument("--validate", action="store_true"); ap.add_argument("--out", default="data/study")
    a = ap.parse_args()
    sims = 400 if a.quick else 2000
    Ns = [16, 24, 32, 40, 48, 64, 96]; P0 = [0.20, 0.35, 0.50]; RHO = [0.0, 0.2, 0.4]; DEL = [0.15, 0.25, 0.35, 0.45]
    res = {"status": "DRAFT inputs - assumptions need teacher approval; SIMULATION-BASED (seeded), not data", "alpha": ALPHA, "target_power": 0.8,
           "sims_per_cell": sims, "tasks_per_participant": K, "outcome": "usable share = usable tasks / 4 (Welch t, two-sided); secondary: Fisher exact on >=3/4 usable (exact power)",
           "power": [], "mde": []}
    for N in Ns:
        for p0 in P0:
            for rho in RHO:
                seed = hash((N, p0, rho)) & 0xFFFF if False else int(N * 1000 + p0 * 100 + rho * 10)
                row = {"N": N, "per_arm": N // 2, "p0": p0, "rho": rho, "mde_80": mde(N, p0, rho, sims, seed)}
                for d in DEL:
                    if p0 + d < 0.999:
                        row["power_d%02d" % round(d * 100)] = round(power_primary(N, p0, d, rho, sims, seed + 1), 3)
                        row["fisher_ge3_d%02d" % round(d * 100)] = round(power_fisher_ge3_exact(N, p0, d, rho), 3)
                res["power"].append(row)
        print("N", N, "done", file=sys.stderr)
    if a.validate:
        res["validation"] = validate(150 if a.quick else 300)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / "power_results.json").write_text(json.dumps(res, indent=1))
    md = ["# Power / MDE table (SIMULATION-BASED, DRAFT assumptions)", "", "MDE = smallest true difference in mean usable share (assisted - template) with 80% power, two-sided alpha .05, Welch t on participant usable share. p0 = template per-task usable probability; rho = within-participant task correlation. '-' = not reachable below 100%.", "",
          "| N (per arm) | p0 | rho | MDE (80%) | power at +.15 | +.25 | +.35 | +.45 |", "|---|---|---|---|---|---|---|---|"]
    for r in res["power"]:
        md.append("| %d (%d) | %.2f | %.1f | %s | %s |" % (r["N"], r["per_arm"], r["p0"], r["rho"], r["mde_80"] if r["mde_80"] is not None else "-",
                  " | ".join(str(r.get("power_d%02d" % d, "-")) for d in (15, 25, 35, 45))))
    (out / "power_table.md").write_text("\n".join(md) + "\n")
    print(json.dumps({"validation": res.get("validation")}, indent=1))
    n24 = [r for r in res["power"] if r["N"] == 24]
    for r in n24:
        print("N=24 p0=%.2f rho=%.1f MDE80=%s power(+.25)=%s fisher>=3(+.25)=%s" % (r["p0"], r["rho"], r["mde_80"], r.get("power_d25"), r.get("fisher_ge3_d25")))


if __name__ == "__main__":
    main()
