"""Analysis of the randomized test: two one-regressor OLS models with robust (HC1, as Stata's vce(robust)) standard errors, a randomization
check, and the success rule fixed in docs/EVAL_PLAN.md. Standard library only."""
import math
import random

GAIN_POINTS = 10.0
ALPHA = 0.05


def _betacf(a, b, x):
    qab, qap, qam, c, d = a + b, a + 1, a - 1, 1.0, 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) > 1e-30 else 1e-30)
    h = d
    for m in range(1, 300):
        aa = m * (b - m) * x / ((qam + 2 * m) * (a + 2 * m))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c
        c = c if abs(c) > 1e-30 else 1e-30
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + 2 * m) * (qap + 2 * m))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + aa / c
        c = c if abs(c) > 1e-30 else 1e-30
        step = d * c
        h *= step
        if abs(step - 1) < 1e-12:
            break
    return h


def t_two_sided_p(t, df):
    x = df / (df + t * t)
    if x <= 0:
        return 0.0
    a, b = df / 2, 0.5
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)) if x < 1 else 0.0
    return front * _betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - front * _betacf(b, a, 1 - x) / b


def t_crit(df, alpha=ALPHA):
    lo, hi = 0.0, 1000.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if t_two_sided_p(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return hi


def ols(y, x):
    """y = a + b x with HC1 robust standard errors and a 95% t interval. -> dict"""
    n = len(y)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((v - mx) ** 2 for v in x)
    if n < 3 or sxx == 0:
        return None
    b = sum((p - mx) * (q - my) for p, q in zip(x, y)) / sxx
    a = my - b * mx
    meat = sum(((p - mx) * (q - a - b * p)) ** 2 for p, q in zip(x, y))
    se = math.sqrt(n / (n - 2) * meat) / sxx
    tc = t_crit(n - 2)
    return {"n": n, "intercept": a, "coef": b, "se": se, "ci_low": b - tc * se, "ci_high": b + tc * se, "p": t_two_sided_p(b / se, n - 2) if se else (0.0 if b else 1.0)}


def randomization_p(y, x, draws=20000, seed=20261105):
    """Reassign the groups at random, with the same sizes, and see how often the difference is as large."""
    n1 = sum(x)
    if not n1 or n1 == len(x):
        return None
    total = sum(y)
    gap = lambda s: s / n1 - (total - s) / (len(y) - n1)
    seen = gap(sum(q for p, q in zip(x, y) if p))
    rng, idx, hits = random.Random(seed), list(range(len(y))), 0
    for _ in range(draws):
        if abs(gap(sum(y[i] for i in rng.sample(idx, n1)))) >= abs(seen) - 1e-12:
            hits += 1
    return (hits + 1) / (draws + 1)


def decide(acc, tim):
    """The order fixed before any data: accuracy first; time only counts after accuracy passes."""
    if not acc:
        return {"accuracy_pass": False, "time_pass": False, "claim": "Not enough data to fit the model."}
    a = acc["coef"] >= GAIN_POINTS and acc["ci_low"] > 0
    t = bool(tim) and tim["ci_high"] < 0
    if a and t:
        claim = "More accurate and faster."
    elif a:
        claim = "More accurate. No claim about speed."
    elif t:
        claim = "Accuracy rule not met. Faster, reported as a secondary finding only: the rule tests time after accuracy."
    else:
        claim = "Neither rule met. This does not show the tool has no effect."
    return {"accuracy_pass": a, "time_pass": a and t, "claim": claim}


def _mean(v):
    return sum(v) / len(v) if v else None


def analyse(persons, items=None, model=None):
    """persons, items and model are the exported CSV rows (dicts of strings)."""
    kept = [p for p in persons if p.get("status") != "withdrawn"]
    x = [int(p["assist"]) for p in kept]
    score, secs = [float(p["score"]) for p in kept], [float(p["search_seconds"]) for p in kept]
    acc, tim = ols(score, x), ols(secs, x)
    group = {}
    for g, a in (("control", 0), ("treatment", 1)):
        ps = [p for p in persons if int(p["assist"]) == a]
        k = [p for p in ps if p.get("status") != "withdrawn"]
        group[g] = {"assigned": len(ps), "withdrawn": len(ps) - len(k), "analysed": len(k), "did_not_finish": sum(1 for p in k if p.get("status") != "completed"),
                    "mean_score": _mean([float(p["score"]) for p in k]), "mean_seconds": _mean([float(p["search_seconds"]) for p in k]),
                    "timeout_rate": _mean([float(p["timeout_rate"]) for p in k]), "missing_rate": _mean([float(p["missing_rate"]) for p in k]),
                    "said_used_other_tools": sum(1 for p in k if p.get("used_other_tools") == "yes")}
    out = {"groups": group, "accuracy": acc, "time": tim, "accuracy_randomization_p": randomization_p(score, x), "time_randomization_p": randomization_p(secs, x), "decision": decide(acc, tim)}
    if items:
        rows = [r for r in items]
        sub = {}
        for wording in ("explicit", "indirect"):
            sub[wording] = {g: _mean([int(r["correct"]) * 100 for r in rows if r["wording"] == wording and r["assigned_group"] == g]) for g in ("control", "treatment")}
        errors = {}
        for g in ("control", "treatment"):
            mine = [r for r in rows if r["assigned_group"] == g]
            nolimit, unknown = [r for r in mine if r["no_age_limit"] == "1"], [r for r in mine if r["gold_label"] == "Unknown"]
            errors[g] = {"no_limit_called_conflict": _mean([int(r["selected_label"] == "Conflict") for r in nolimit]), "unknown_given_a_definite_answer": _mean([int(r["selected_label"] in ("Match", "Conflict")) for r in unknown])}
        out.update(by_wording=sub, errors=errors)
    if model:
        ok = [r for r in model if r["status"] == "ok"]
        out["ai_alone"] = {"answered": len(ok), "failed": len(model) - len(ok), "score": _mean([int(r["correct"]) * 100 for r in model]), "control_score": group["control"]["mean_score"],
                           "by_wording": {w: _mean([int(r["correct"]) * 100 for r in model if r["wording"] == w]) for w in ("explicit", "indirect")}, "model": sorted({r["model"] for r in model})}
    return out


def render(o, label):
    f = lambda v, d=2: "n/a" if v is None else ("%.*f" % (d, v))
    L = ["# AgeLens randomized test: %s" % label, ""]
    L += ["| | Control | Treatment |", "|---|---:|---:|"]
    for k, t in (("assigned", "Assigned"), ("withdrawn", "Withdrew (answers deleted)"), ("analysed", "Analysed"), ("did_not_finish", "Did not finish (kept, counted wrong)"), ("mean_score", "Mean score"), ("mean_seconds", "Mean seconds per case"),
                 ("timeout_rate", "Time-out rate"), ("missing_rate", "Missing rate"), ("said_used_other_tools", "Said they used other tools")):
        c, tr = o["groups"]["control"][k], o["groups"]["treatment"][k]
        L.append("| %s | %s | %s |" % (t, c if isinstance(c, int) else f(c), tr if isinstance(tr, int) else f(tr)))
    L += ["", "| Effect | Estimate | Robust SE | 95% CI | Randomization p |", "|---|---:|---:|---|---:|"]
    for t, r, rp in (("Score, points (beta)", o["accuracy"], o["accuracy_randomization_p"]), ("Seconds per case (theta)", o["time"], o["time_randomization_p"])):
        L.append("| %s | n/a | n/a | n/a | n/a |" % t if not r else "| %s | %s | %s | %s to %s | %s |" % (t, f(r["coef"]), f(r["se"]), f(r["ci_low"]), f(r["ci_high"]), f(rp, 4)))
    d = o["decision"]
    L += ["", "**Accuracy rule (gain at least %g points, CI above 0): %s. Time rule (CI below 0, tested after accuracy): %s.**" % (GAIN_POINTS, "met" if d["accuracy_pass"] else "not met", "met" if d["time_pass"] else "not met"), "", "**Claim allowed: %s**" % d["claim"]]
    if "by_wording" in o:
        L += ["", "Supplementary, not for a headline claim:", ""]
        for w, v in o["by_wording"].items():
            L.append("- %s cases: control %s, treatment %s" % (w, f(v["control"]), f(v["treatment"])))
        for g, v in o["errors"].items():
            L.append("- %s: called a no-limit ad Conflict %s; gave a definite answer on Unknown cases %s" % (g, f(v["no_limit_called_conflict"]), f(v["unknown_given_a_definite_answer"])))
    if "ai_alone" in o:
        a = o["ai_alone"]
        L += ["", "AI alone (%s): %s of the cases right, %d answered, %d failed; control group %s. Not participants." % (", ".join(map(str, a["model"])), f(a["score"]), a["answered"], a["failed"], f(a["control_score"]))]
    return "\n".join(L) + "\n"
