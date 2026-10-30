"""Pure statistics for the crossover-ai-v1 evaluation (docs/EVAL_PLAN.md). Stdlib only, seeded, no database.
Unit of analysis = PARTICIPANT: for each outcome, D = mean over the participant's 2 contextual-AI tasks minus mean over the 2 fixed-template tasks.
Used by api_study/study_ai (export columns), scripts/analyze_study_ai.py (analysis) and the tests.
Anything computed from a SIMULATED export is a software test, never a result."""
import itertools
import math
import random

SEED = 20261023
EXACT_MAX_N = 16          # exact sign-flip enumeration up to 2^16; Monte Carlo above
MC_FLIPS = 100000
BOOT = 20000
MIN_EFFECT = 0.10         # pre-specified minimum meaningful difference in interpretation accuracy
# outcome -> (task-row field, participant column stem)
OUTCOMES = {"accuracy": ("final_accuracy", "acc"), "actionable": ("final_actionable", "act"),
            "unsupported": ("final_unsupported", "uns"), "time": ("completion_time_s", "time")}


def mean(v):
    return sum(v) / len(v) if v else float("nan")


def person_columns(rows):
    """rows: one participant's task rows (dicts with condition A=template / B=contextual AI and the outcome fields).
    -> columns acc_template, acc_ai, diff_acc, ... ; '' when any needed task value is unknown (unscored/unresolved)."""
    cols = {}
    for name, (field, stem) in OUTCOMES.items():
        vals = {}
        for cond, tag in (("A", "template"), ("B", "ai")):
            v = [r[field] for r in rows if r["condition"] == cond]
            vals[tag] = round(mean(v), 4) if v and all(x != "" for x in v) else ""
        cols["%s_template" % stem], cols["%s_ai" % stem] = vals["template"], vals["ai"]
        cols["diff_" + stem] = round(vals["ai"] - vals["template"], 4) if vals["ai"] != "" and vals["template"] != "" else ""
    return cols


def boot_ci(v, B=BOOT, seed=SEED):
    rng = random.Random(seed)
    m = sorted(mean([rng.choice(v) for _ in v]) for _ in range(B))
    return m[int(0.025 * B)], m[int(0.975 * B) - 1]


def signflip_p(v, seed=SEED + 2, exact_max=EXACT_MAX_N, M=MC_FLIPS):
    """Two-sided sign-flip randomisation test of H0: mean difference = 0. -> (p, method)."""
    n, obs = len(v), abs(mean(v))
    if n <= exact_max:
        tot = hit = 0
        for signs in itertools.product((1, -1), repeat=n):
            tot += 1
            hit += abs(sum(s * x for s, x in zip(signs, v)) / n) >= obs - 1e-12
        return hit / tot, "exact (2^%d sign patterns)" % n
    rng = random.Random(seed)
    c = sum(abs(mean([x if rng.random() < 0.5 else -x for x in v])) >= obs - 1e-12 for _ in range(M))
    return (c + 1) / (M + 1), "Monte Carlo (%d random sign flips)" % M


def paired(d):
    """Paired differences (one per participant) -> mean, SD, 95% percentile-bootstrap CI, sign-flip p."""
    d = [float(x) for x in d]
    if len(d) < 2:
        return {"n": len(d), "error": "need at least 2 participants"}
    lo, hi = boot_ci(d)
    p, how = signflip_p(d)
    m = mean(d)
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))
    return {"n": len(d), "mean": round(m, 4), "sd": round(sd, 4), "ci95": [round(lo, 4), round(hi, 4)], "p": round(p, 4), "p_method": how}


def holm(ps):
    """Holm step-down adjustment. ps: {name: p} -> {name: adjusted p}."""
    order = sorted(ps, key=lambda k: ps[k])
    out, run, m = {}, 0.0, len(order)
    for i, k in enumerate(order):
        run = max(run, min(1.0, (m - i) * ps[k]))
        out[k] = round(run, 4)
    return out


def kappa(a, b):
    n = len(a)
    if n == 0:
        return None, None
    po = sum(i == j for i, j in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (None if pe == 1 else round((po - pe) / (1 - pe), 3)), round(po, 3)


def _bits(s):
    return [int(ch) for ch in str(s)] if s != "" and s is not None else None


def agreement(tasks):
    """R1 vs R2 before adjudication: fact bits and q bits (kappa + raw), unsupported counts (exact agreement, mean absolute difference)."""
    fa, fb, qa, qb, ua, ub = [], [], [], [], [], []
    for t in tasks:
        if t.get("r1_facts", "") == "" or t.get("r2_facts", "") == "":
            continue
        fa += _bits(t["r1_facts"]); fb += _bits(t["r2_facts"])
        qa += _bits(t["r1_q"]); qb += _bits(t["r2_q"])
        ua.append(int(t["r1_unsupported"])); ub.append(int(t["r2_unsupported"]))
    out = {}
    for name, a, b in (("fact_bits", fa, fb), ("question_criteria", qa, qb)):
        k, po = kappa(a, b)
        out[name] = {"n_judgements": len(a), "kappa": k, "raw_agreement": po}
    out["unsupported_count"] = {"n_items": len(ua), "exact_agreement": round(sum(x == y for x, y in zip(ua, ub)) / len(ua), 3) if ua else None,
                                "mean_abs_difference": round(sum(abs(x - y) for x, y in zip(ua, ub)) / len(ua), 3) if ua else None}
    return out


def analyse(doc):
    """doc = task-level export (meta, participants, tasks) of design crossover-ai-v1 -> result dict."""
    meta, parts, tasks = doc["meta"], doc["participants"], doc["tasks"]
    sim = bool(meta.get("simulated"))
    out = {"design": meta.get("design"), "simulated": sim,
           "label": ("SIMULATED: software test only. No AI model was used. Not study data, not a result, says nothing about AI." if sim
                     else "FORMAL export (read docs/EVAL_PLAN.md before interpreting)"),
           "meta": {k: meta.get(k) for k in ("schema", "scope", "generated_at", "tasks_version", "rubric_version")}}
    ok = [p for p in parts if p.get("diff_acc", "") != ""]
    seqs = sorted({p["sequence"] for p in parts})
    out["n"] = {"enrolled": len(parts), "analysed_primary": len(ok), "withdrawn": sum(1 for p in parts if p["participant_status"] == "withdrawn"),
                "dropouts": sum(1 for p in parts if p["dropout"]), "incomplete": sum(1 for p in parts if p["tasks_submitted"] < 4),
                "excluded_unscored_or_unresolved": sum(1 for p in parts if p.get("diff_acc", "") == "" and p["participant_status"] != "withdrawn"),
                "by_sequence": {s: sum(1 for p in ok if p["sequence"] == s) for s in seqs}}
    res = {}
    for name, (_, stem) in OUTCOMES.items():
        d = [p["diff_" + stem] for p in parts if p.get("diff_" + stem, "") != ""]
        r = paired(d)
        if "error" not in r:
            r["mean_template"] = round(mean([p[stem + "_template"] for p in parts if p.get("diff_" + stem, "") != ""]), 4)
            r["mean_ai"] = round(mean([p[stem + "_ai"] for p in parts if p.get("diff_" + stem, "") != ""]), 4)
        res[name] = r
    out["outcomes"] = res
    pr = res["accuracy"]
    if "error" in pr:
        out["primary_decision"] = "Not computable: " + pr["error"]
    else:
        benefit = pr["mean"] >= MIN_EFFECT - 1e-12 and pr["ci95"][0] > 0 and pr["p"] < 0.05
        out["primary_decision"] = ("EVIDENCE OF BENEFIT (accuracy): mean difference %+.3f >= +%.2f, CI lower bound %.3f > 0, p %.4f < 0.05" % (pr["mean"], MIN_EFFECT, pr["ci95"][0], pr["p"]) if benefit
                                   else "NO EVIDENCE OF BENEFIT (accuracy): needs mean difference >= +%.2f AND CI lower bound > 0 AND p < 0.05; got %+.3f, CI [%.3f, %.3f], p %.4f. This is not evidence that the AI does not help."
                                   % (MIN_EFFECT, pr["mean"], *pr["ci95"], pr["p"]))
        out["primary_benefit"] = benefit
    sec = {k: res[k]["p"] for k in ("actionable", "unsupported", "time") if "error" not in res[k]}
    out["secondary_holm_adjusted_p"] = holm(sec)
    us = res["unsupported"]
    out["safety_signal"] = bool("error" not in us and us["ci95"][0] > 0)
    out["safety_note"] = ("SAFETY SIGNAL: the contextual arm added unsupported claims (CI lower bound > 0)." if out["safety_signal"]
                          else "No safety signal under the pre-specified rule (CI lower bound of the unsupported-claims difference is not above 0); with a small N this is weak reassurance.")
    a_first = [p["diff_acc"] for p in ok if p.get("first_condition") == "A"]; b_first = [p["diff_acc"] for p in ok if p.get("first_condition") == "B"]
    if a_first and b_first:
        out["order_check_descriptive"] = {"mean_diff_template_first": round(mean(a_first), 4), "mean_diff_ai_first": round(mean(b_first), 4),
                                          "n": [len(a_first), len(b_first)], "note": "A large gap suggests a period or carryover effect; descriptive only."}
    by = {}
    for t in tasks:
        if t.get("condition") and t.get("final_accuracy", "") != "":
            b = by.setdefault((t["task_id"], t["tool"]), [])
            b.append(t["final_accuracy"])
    out["accuracy_by_task_and_tool_DESCRIPTIVE"] = {"%s/%s" % k: {"tasks": len(v), "mean": round(mean(v), 3)} for k, v in sorted(by.items())}
    out["inter_rater_R1_R2"] = agreement(tasks)
    out["scoring_status"] = {"items_disagreement": sum(1 for t in tasks if t["disagreement"] == 1), "unresolved": sum(1 for t in tasks if t["resolution"] == "unresolved"),
                             "adjudicated": sum(1 for t in tasks if t["resolution"] == "adjudicated"), "missing_answers": sum(1 for t in tasks if t["missing"] == 1),
                             "timed_out": sum(1 for t in tasks if t["timed_out"] == 1), "model_failures": sum(int(t["model_failure"] or 0) for t in tasks)}
    return out


def render(o):
    L = ["=" * 78, o["label"], "=" * 78, "Design %s | export %s | tasks %s | rubric %s" % (o["design"], o["meta"]["generated_at"], o["meta"]["tasks_version"], o["meta"]["rubric_version"]), ""]
    n = o["n"]
    L.append("Participants: enrolled %d, analysed (primary) %d, withdrawn %d, dropouts %d, incomplete %d, excluded %d; by sequence %s"
             % (n["enrolled"], n["analysed_primary"], n["withdrawn"], n["dropouts"], n["incomplete"], n["excluded_unscored_or_unresolved"], n["by_sequence"]))
    L.append("")
    names = {"accuracy": "PRIMARY  interpretation accuracy (share of key facts)", "unsupported": "SAFETY   unsupported claims per task (lower is better)",
             "actionable": "SECOND.  actionable question (share of tasks)", "time": "SECOND.  completion time (seconds per task)"}
    for k in ("accuracy", "unsupported", "actionable", "time"):
        r = o["outcomes"][k]
        if "error" in r:
            L.append("%s: %s" % (names[k], r["error"])); continue
        ctx = "contextual (SIMULATED script, not an AI)" if o["simulated"] else "contextual AI"
        L.append(("%s\n   template %.3f   " + ctx + " %.3f   mean difference (contextual - template) %+.3f   95%% CI [%.3f, %.3f]   p %.4f (%s)   n=%d")
                 % (names[k], r["mean_template"], r["mean_ai"], r["mean"], r["ci95"][0], r["ci95"][1], r["p"], r["p_method"], r["n"]))
    L += ["", "Decision (primary): " + o["primary_decision"], o["safety_note"], "Secondary p, Holm-adjusted over actionable/unsupported/time: %s" % o["secondary_holm_adjusted_p"]]
    if "order_check_descriptive" in o:
        r = o["order_check_descriptive"]; L.append("Order check (descriptive): mean accuracy difference, template first %+.3f, AI first %+.3f, n=%s" % (r["mean_diff_template_first"], r["mean_diff_ai_first"], r["n"]))
    L += ["", "Accuracy by task and tool (descriptive, tasks are not independent): %s" % o["accuracy_by_task_and_tool_DESCRIPTIVE"], "", "Inter-rater (R1 vs R2, before adjudication):"]
    ag = o["inter_rater_R1_R2"]
    for k in ("fact_bits", "question_criteria"):
        L.append("  %-18s n=%-4d kappa=%s raw agreement=%s" % (k, ag[k]["n_judgements"], ag[k]["kappa"], ag[k]["raw_agreement"]))
    u = ag["unsupported_count"]; L.append("  unsupported_count  n=%-4s exact agreement=%s mean abs difference=%s" % (u["n_items"], u["exact_agreement"], u["mean_abs_difference"]))
    L += ["", "Scoring status: %s" % o["scoring_status"], "",
          "This is %s. It makes no claim about interviews, hiring, employment or GDP." % ("a SIMULATED software test; no AI model was used and the numbers are NOT results" if o["simulated"] else "an analysis of the exported data")]
    return "\n".join(L)
