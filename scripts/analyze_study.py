#!/usr/bin/env python3
"""Analysis of an AgeLens study export (task-level JSON from /api/study/export). Stdlib only, seeded.
Unit of analysis = PARTICIPANT (usable share of 4 tasks), never the pooled 4 answers.
  PRIMARY    : difference in mean usable share (assisted - template); percentile bootstrap 95% CI (10,000 resamples,
               resampling participants within arm, seed 20261023); two-sided randomisation (permutation) test, 20,000 shuffles.
               Welch t p-value also shown (the power analysis assumed it).
  SECONDARY  : usable on >=3 of 4 tasks: risk difference with Newcombe hybrid-score 95% CI; Fisher exact two-sided p.
  AGREEMENT  : Cohen's kappa (R1 vs R2, items scored by both, before adjudication) per criterion + severe flag, with raw agreement.
  SENSITIVITY: completers only (all 4 tasks submitted); excluding participants with unresolved scores is the primary rule.
CROSSOVER design (meta.design crossover-rules-v1, the planned design; docs/EVAL_PLAN.md):
  PRIMARY    : per participant D = usable share on AgeLens tasks (B) - usable share on ad-only tasks (A), 2 tasks each.
               Mean D; percentile bootstrap 95% CI over participants (20,000 resamples, seed 20261023); two-sided sign-flip
               randomisation test (20,000 flips); paired t p also shown. Pre-registered threshold applied verbatim from
               meta.threshold: MET only if mean D >= min_effect AND CI lower bound > ci_lower_gt.
  ORDER      : order-balanced estimate (mean of the AB-group and BA-group means of D) and the order difference with a
               bootstrap CI (a large difference signals a period or carryover effect).
  SENSITIVITY: period 1 only (first two tasks: A in AB group vs B in BA group), a between-participant comparison free of
               carryover, low power; completers only.
  SECONDARY  : per-criterion and severe-error rates by condition (task level, descriptive: tasks are not independent).
Output is stamped SIMULATED when meta.simulated is true; a SIMULATED output is a software test, never a result.
Usage: python3 scripts/analyze_study.py EXPORT.json [--json out.json]"""
import argparse, json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from power_analysis import fisher_p, newcombe_diff, welch_p  # noqa: E402

SEED = 20261023
FIELDS = ("c1", "c2", "c3", "c4", "severe")


def mean(v): return sum(v) / len(v) if v else float("nan")


def boot_ci(x, y, B=10000, rng=None):
    rng = rng or random.Random(SEED); d = []
    for _ in range(B):
        a = [rng.choice(x) for _ in x]; b = [rng.choice(y) for _ in y]
        d.append(mean(b) - mean(a))
    d.sort(); return d[int(0.025 * B)], d[int(0.975 * B) - 1]


def perm_p(x, y, M=20000, rng=None):
    rng = rng or random.Random(SEED + 1); pool = x + y; n = len(x)
    obs = abs(mean(y) - mean(x)); c = 0
    for _ in range(M):
        rng.shuffle(pool); c += abs(mean(pool[n:]) - mean(pool[:n])) >= obs - 1e-12
    return (c + 1) / (M + 1)


def boot_mean_ci(v, B=20000, rng=None):
    rng = rng or random.Random(SEED); m = []
    for _ in range(B):
        m.append(mean([rng.choice(v) for _ in v]))
    m.sort(); return m[int(0.025 * B)], m[int(0.975 * B) - 1]


def signflip_p(v, M=20000, rng=None):
    rng = rng or random.Random(SEED + 2); obs = abs(mean(v)); c = 0
    for _ in range(M):
        c += abs(mean([x if rng.random() < 0.5 else -x for x in v])) >= obs - 1e-12
    return (c + 1) / (M + 1)


def paired_t_p(v):
    from power_analysis import t_two_sided_p
    n = len(v); m = mean(v); sd = (sum((x - m) ** 2 for x in v) / (n - 1)) ** 0.5
    return 1.0 if sd == 0 and m == 0 else (0.0 if sd == 0 else t_two_sided_p(m / (sd / n ** 0.5), n - 1))


def kappa(a, b):
    n = len(a)
    if n == 0: return None, None
    po = sum(i == j for i, j in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (None if pe == 1 else round((po - pe) / (1 - pe), 3)), round(po, 3)


def analyse(doc):
    if str(doc["meta"].get("design") or "").startswith("crossover-ai"):   # 2026-10-29 design: scripts/analyze_study_ai.py
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from backend import study_stats
        return study_stats.analyse(doc)
    if str(doc["meta"].get("design") or "").startswith("crossover"):
        return analyse_crossover(doc)
    meta, parts, tasks = doc["meta"], doc["participants"], doc["tasks"]
    out = {"meta": {k: meta.get(k) for k in ("schema", "scope", "simulated", "generated_at", "tasks_version", "rubric_version")}}
    out["label"] = "SIMULATED — software test only, not study data, not a result" if meta.get("simulated") else "FORMAL export (check PREREGISTRATION before interpreting)"
    arms = {"template": [], "assisted": []}; excl = {"template": 0, "assisted": 0}
    for p in parts:
        if p["usable_share"] == "": excl[p["arm"]] += 1
        else: arms[p["arm"]].append(p)
    out["n"] = {a: {"randomised": sum(1 for p in parts if p["arm"] == a), "analysed": len(arms[a]), "excluded_unresolved_or_unscored": excl[a],
                    "dropouts": sum(1 for p in parts if p["arm"] == a and p["dropout"]), "withdrawn": sum(1 for p in parts if p["arm"] == a and p["participant_status"] == "withdrawn"),
                    "incomplete": sum(1 for p in parts if p["arm"] == a and p["tasks_submitted"] < 4), "model_failures": sum(p["model_failures"] for p in parts if p["arm"] == a)} for a in arms}
    x = [p["usable_share"] for p in arms["template"]]; y = [p["usable_share"] for p in arms["assisted"]]
    if len(x) >= 2 and len(y) >= 2:
        lo, hi = boot_ci(x, y)
        out["primary"] = {"outcome": "mean participant usable share (usable tasks / 4)", "template_mean": round(mean(x), 3), "assisted_mean": round(mean(y), 3),
                          "difference": round(mean(y) - mean(x), 3), "ci95_percentile_bootstrap": [round(lo, 3), round(hi, 3)], "p_randomisation_two_sided": round(perm_p(x, y), 4),
                          "p_welch_t_two_sided": round(welch_p(x, y), 4), "n": [len(x), len(y)],
                          "note": "participant is the unit; with n this small the CI is wide and bootstrap coverage is approximate"}
        x3 = sum(p["usable_ge3"] for p in arms["template"]); y3 = sum(p["usable_ge3"] for p in arms["assisted"])
        d, l, u = newcombe_diff(x3, len(x), y3, len(y))
        out["secondary_ge3"] = {"template": "%d/%d" % (x3, len(x)), "assisted": "%d/%d" % (y3, len(y)), "risk_difference": round(d, 3), "ci95_newcombe_hybrid_score": [round(l, 3), round(u, 3)], "p_fisher_exact_two_sided": round(fisher_p(x3, len(x), y3, len(y)), 4)}
        cx = [p["usable_share"] for p in arms["template"] if p["tasks_submitted"] == 4]; cy = [p["usable_share"] for p in arms["assisted"] if p["tasks_submitted"] == 4]
        if len(cx) >= 2 and len(cy) >= 2:
            out["sensitivity_completers_only"] = {"n": [len(cx), len(cy)], "difference": round(mean(cy) - mean(cx), 3), "ci95_percentile_bootstrap": [round(v, 3) for v in boot_ci(cx, cy, 5000)]}
    else:
        out["primary"] = {"error": "Need at least 2 analysable participants per arm."}
    # descriptive per-task (pooled tasks are NOT independent; description only)
    kinds = {}
    for t in tasks:
        if t["final_usable"] != "": kinds.setdefault((t["task_kind"], t["arm"]), []).append(t["final_usable"])
    out["descriptive_by_task_kind_NOT_INFERENTIAL"] = {"%s/%s" % k: "%d/%d" % (sum(v), len(v)) for k, v in sorted(kinds.items())}
    ag = {}
    for f in FIELDS:
        a, b = [], []
        for t in tasks:
            if t["r1_" + f] != "" and t["r2_" + f] != "": a.append(t["r1_" + f]); b.append(t["r2_" + f])
        k, po = kappa(a, b); ag[f] = {"n_items": len(a), "kappa": k, "raw_agreement": po}
    out["inter_rater_R1_R2"] = ag
    out["scoring_status"] = {"items_disagreement": sum(1 for t in tasks if t["disagreement"] == 1), "unresolved": sum(1 for t in tasks if t["resolution"] == "unresolved"),
                             "adjudicated": sum(1 for t in tasks if t["resolution"] == "adjudicated"), "missing_answers": sum(1 for t in tasks if t["missing"] == 1),
                             "timed_out": sum(1 for t in tasks if t["timed_out"] == 1)}
    return out


def agreement(tasks):
    ag = {}
    for f in FIELDS:
        a, b = [], []
        for t in tasks:
            if t["r1_" + f] != "" and t["r2_" + f] != "": a.append(t["r1_" + f]); b.append(t["r2_" + f])
        k, po = kappa(a, b); ag[f] = {"n_items": len(a), "kappa": k, "raw_agreement": po}
    return ag


def analyse_crossover(doc):
    meta, parts, tasks = doc["meta"], doc["participants"], doc["tasks"]
    thr = meta.get("threshold") or {"min_effect": 0.20, "ci_lower_gt": 0.0}
    out = {"design": meta.get("design"), "meta": {k: meta.get(k) for k in ("schema", "scope", "simulated", "generated_at", "tasks_version", "rubric_version")},
           "label": "SIMULATED — software test only, not study data, not a result" if meta.get("simulated") else "FORMAL export (check PREREGISTRATION before interpreting)",
           "threshold": thr}
    ok = [p for p in parts if p.get("diff_B_minus_A", "") != ""]
    seqs = sorted({p["sequence"] for p in parts})
    out["n"] = {"enrolled": len(parts), "analysed": len(ok), "excluded_unresolved_or_unscored": sum(1 for p in parts if p.get("diff_B_minus_A", "") == "" and p["participant_status"] != "withdrawn"),
                "withdrawn": sum(1 for p in parts if p["participant_status"] == "withdrawn"), "dropouts": sum(1 for p in parts if p["dropout"]),
                "incomplete": sum(1 for p in parts if p["tasks_submitted"] < 4), "by_sequence": {s: sum(1 for p in ok if p["sequence"] == s) for s in seqs}}
    D = [p["diff_B_minus_A"] for p in ok]
    if len(D) < 2:
        out["primary"] = {"error": "Need at least 2 analysable participants."}
        return out
    lo, hi = boot_mean_ci(D)
    md = mean(D)
    met = md >= thr["min_effect"] - 1e-12 and lo > thr["ci_lower_gt"]
    out["primary"] = {"outcome": "D = usable share on AgeLens tasks - usable share on ad-only tasks (per participant, 2 tasks each)",
                      "mean_A": round(mean([p["usable_share_A"] for p in ok]), 3), "mean_B": round(mean([p["usable_share_B"] for p in ok]), 3),
                      "mean_D": round(md, 3), "ci95_percentile_bootstrap": [round(lo, 3), round(hi, 3)], "p_signflip_two_sided": round(signflip_p(D), 4),
                      "p_paired_t_two_sided": round(paired_t_p(D), 4), "n": len(D),
                      "D_distribution": {str(v): sum(1 for x in D if abs(x - v) < 1e-9) for v in (-1.0, -0.5, 0.0, 0.5, 1.0)},
                      "threshold_met": met,
                      "decision": ("MET: mean D %+.3f >= %+.2f and CI lower bound %.3f > %.2f" if met else "NOT MET: needs mean D >= %+.2f and CI lower bound > %.2f; got mean D %+.3f, lower bound %.3f")
                      % ((md, thr["min_effect"], lo, thr["ci_lower_gt"]) if met else (thr["min_effect"], thr["ci_lower_gt"], md, lo))}
    ab = [p["diff_B_minus_A"] for p in ok if p["first_condition"] == "A"]; ba = [p["diff_B_minus_A"] for p in ok if p["first_condition"] == "B"]
    if len(ab) >= 2 and len(ba) >= 2:
        l2, h2 = boot_ci(ba, ab, 10000)  # mean(ab) - mean(ba)
        out["order"] = {"mean_D_AB_group": round(mean(ab), 3), "mean_D_BA_group": round(mean(ba), 3), "order_balanced_effect": round((mean(ab) + mean(ba)) / 2, 3),
                        "order_difference_AB_minus_BA": round(mean(ab) - mean(ba), 3), "ci95": [round(l2, 3), round(h2, 3)], "n": [len(ab), len(ba)],
                        "note": "AB group meets AgeLens second; a positive difference can mean learning over the session or that AgeLens first carries over to the ad-only tasks"}
        p1a = [p["usable_share_A"] for p in ok if p["first_condition"] == "A"]; p1b = [p["usable_share_B"] for p in ok if p["first_condition"] == "B"]
        l3, h3 = boot_ci(p1a, p1b, 10000)
        out["sensitivity_period1_only"] = {"ad_only_first": round(mean(p1a), 3), "agelens_first": round(mean(p1b), 3), "difference": round(mean(p1b) - mean(p1a), 3),
                                           "ci95_percentile_bootstrap": [round(l3, 3), round(h3, 3)], "n": [len(p1a), len(p1b)], "note": "between participants, no carryover possible, low power"}
    comp = [p["diff_B_minus_A"] for p in ok if p["tasks_submitted"] == 4]
    if len(comp) >= 2:
        out["sensitivity_completers_only"] = {"n": len(comp), "mean_D": round(mean(comp), 3), "ci95_percentile_bootstrap": [round(v, 3) for v in boot_mean_ci(comp, 5000)]}
    by = {}
    for t in tasks:
        if t.get("condition") and t["final_usable"] != "":
            b = by.setdefault(t["condition"], {"n": 0, "usable": 0, **{f: 0 for f in FIELDS}})
            b["n"] += 1; b["usable"] += t["final_usable"]
            for f in FIELDS:
                b[f] += t["final_" + f] or 0
    out["by_condition_task_level_NOT_INFERENTIAL"] = {c: {"tasks": v["n"], **{k: "%d/%d" % (v[k], v["n"]) for k in ("usable",) + FIELDS}} for c, v in sorted(by.items())}
    kinds = {}
    for t in tasks:
        if t.get("condition") and t["final_usable"] != "": kinds.setdefault((t["task_kind"], t["condition"]), []).append(t["final_usable"])
    out["descriptive_by_task_kind_NOT_INFERENTIAL"] = {"%s/%s" % k: "%d/%d" % (sum(v), len(v)) for k, v in sorted(kinds.items())}
    out["inter_rater_R1_R2"] = agreement(tasks)
    out["scoring_status"] = {"items_disagreement": sum(1 for t in tasks if t["disagreement"] == 1), "unresolved": sum(1 for t in tasks if t["resolution"] == "unresolved"),
                             "adjudicated": sum(1 for t in tasks if t["resolution"] == "adjudicated"), "missing_answers": sum(1 for t in tasks if t["missing"] == 1),
                             "timed_out": sum(1 for t in tasks if t["timed_out"] == 1)}
    return out


def render_crossover(o):
    L = ["=" * 78, o["label"], "=" * 78, "Design %s | export %s | tasks %s | rubric %s" % (o["design"], o["meta"]["generated_at"], o["meta"]["tasks_version"], o["meta"]["rubric_version"]), ""]
    n = o["n"]
    L.append("Participants: enrolled %d, analysed %d, withdrawn %d, dropouts %d, incomplete %d, excluded (unscored/unresolved) %d; by sequence %s"
             % (n["enrolled"], n["analysed"], n["withdrawn"], n["dropouts"], n["incomplete"], n["excluded_unresolved_or_unscored"], n["by_sequence"]))
    p = o["primary"]; L.append("")
    if "error" in p:
        L.append(p["error"]); return "\n".join(L)
    L += ["PRIMARY (within participant): usable share  ad only (A) %.3f   AgeLens (B) %.3f" % (p["mean_A"], p["mean_B"]),
          "  mean D (B - A) = %+.3f, 95%% CI [%.3f, %.3f] (percentile bootstrap), n = %d" % (p["mean_D"], *p["ci95_percentile_bootstrap"], p["n"]),
          "  sign-flip randomisation p = %.4f ; paired t p = %.4f ; D distribution %s" % (p["p_signflip_two_sided"], p["p_paired_t_two_sided"], p["D_distribution"]),
          "  PRE-REGISTERED THRESHOLD: " + p["decision"]]
    if "order" in o:
        r = o["order"]
        L += ["ORDER: mean D  AB group %+.3f  BA group %+.3f ; order-balanced effect %+.3f ; difference %+.3f CI %s n=%s"
              % (r["mean_D_AB_group"], r["mean_D_BA_group"], r["order_balanced_effect"], r["order_difference_AB_minus_BA"], r["ci95"], r["n"])]
        s = o["sensitivity_period1_only"]
        L.append("SENSITIVITY period 1 only: ad-only first %.3f vs AgeLens first %.3f, diff %+.3f CI %s n=%s" % (s["ad_only_first"], s["agelens_first"], s["difference"], s["ci95_percentile_bootstrap"], s["n"]))
    if "sensitivity_completers_only" in o:
        c = o["sensitivity_completers_only"]; L.append("SENSITIVITY completers only: mean D %+.3f CI %s n=%d" % (c["mean_D"], c["ci95_percentile_bootstrap"], c["n"]))
    L += ["", "By condition (task level, descriptive): %s" % o["by_condition_task_level_NOT_INFERENTIAL"],
          "By task kind/condition (descriptive): %s" % o["descriptive_by_task_kind_NOT_INFERENTIAL"], "", "Inter-rater (R1 vs R2, before adjudication):"]
    L += ["  %-7s n=%-3d kappa=%s raw agreement=%s" % (f, v["n_items"], v["kappa"], v["raw_agreement"]) for f, v in o["inter_rater_R1_R2"].items()]
    L += ["", "Scoring status: %s" % o["scoring_status"], "",
          "This is %s. It reports effect size, CI, sample size and dropouts; it makes no employment, hiring or legal claim." % ("a SIMULATED software test" if o["meta"]["simulated"] else "an analysis of the exported data")]
    return "\n".join(L)


def render(o):
    if str(o.get("design") or "").startswith("crossover-ai"):
        from backend import study_stats
        return study_stats.render(o)
    if str(o.get("design") or "").startswith("crossover"):
        return render_crossover(o)
    L = ["=" * 78, o["label"], "=" * 78, "Export: %s | tasks %s | rubric %s" % (o["meta"]["generated_at"], o["meta"]["tasks_version"], o["meta"]["rubric_version"]), ""]
    for a, v in o["n"].items(): L.append("%-9s randomised %d, analysed %d, dropouts %d (withdrawn %d), incomplete %d, model failures %d, excluded(unscored) %d" % (a, v["randomised"], v["analysed"], v["dropouts"], v["withdrawn"], v["incomplete"], v["model_failures"], v["excluded_unresolved_or_unscored"]))
    p = o["primary"]; L.append("")
    if "error" in p: L.append(p["error"])
    else:
        L += ["PRIMARY (participant level): mean usable share  template %.3f  assisted %.3f" % (p["template_mean"], p["assisted_mean"]),
              "  difference (assisted - template) = %+.3f, 95%% CI [%.3f, %.3f] (percentile bootstrap)" % (p["difference"], *p["ci95_percentile_bootstrap"]),
              "  randomisation test p = %.4f ; Welch t p = %.4f ; n = %s" % (p["p_randomisation_two_sided"], p["p_welch_t_two_sided"], p["n"])]
        s = o["secondary_ge3"]
        L += ["SECONDARY usable on >=3/4: template %s, assisted %s; risk difference %+.3f, 95%% CI [%.3f, %.3f] (Newcombe hybrid score); Fisher exact p = %.4f" % (s["template"], s["assisted"], s["risk_difference"], *s["ci95_newcombe_hybrid_score"], s["p_fisher_exact_two_sided"])]
        if "sensitivity_completers_only" in o: c = o["sensitivity_completers_only"]; L.append("SENSITIVITY completers only: diff %+.3f CI %s n=%s" % (c["difference"], c["ci95_percentile_bootstrap"], c["n"]))
    L += ["", "Inter-rater (R1 vs R2, before adjudication):"] + ["  %-7s n=%-3d kappa=%s raw agreement=%s" % (f, v["n_items"], v["kappa"], v["raw_agreement"]) for f, v in o["inter_rater_R1_R2"].items()]
    L += ["", "Scoring status: %s" % o["scoring_status"], "Usable by task kind/arm (descriptive, tasks not independent): %s" % o["descriptive_by_task_kind_NOT_INFERENTIAL"], "",
          "This is %s. It reports effect size, CI, sample size and dropouts; it makes no employment, hiring or legal claim." % ("a SIMULATED software test" if o["meta"]["simulated"] else "an analysis of the exported data")]
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("export"); ap.add_argument("--json")
    a = ap.parse_args()
    o = analyse(json.loads(Path(a.export).read_text()))
    print(render(o))
    if a.json: Path(a.json).write_text(json.dumps(o, indent=1, ensure_ascii=False))
