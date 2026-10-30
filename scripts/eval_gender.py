#!/usr/bin/env python3
"""Score backend/genderparse.py against the blind gold set (data/raw/gold_gender_2021-2024.jsonl, git-ignored).

  python scripts/eval_gender.py [--gold PATH] [--module backend.genderparse | path/to/module.py] [--errors]

Metrics, each as precision / recall with Wilson 95% intervals, on the random stratum, the targeted strata and all items:
  directional = a restriction or preference (male_only, female_only, male_preferred, female_preferred; 'conflict' counts as flagged)
  any_wording = any explicit gender wording incl. "either gender" (gold label != none; prediction != none)
  class accuracy = exact class match.
"""
import argparse, importlib, importlib.util, json, math, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DIRECTIONAL = {"male_only", "female_only", "male_preferred", "female_preferred"}


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(c - h, 4), round(c + h, 4)


def ratio(k, n):
    return {"k": k, "n": n, "value": round(k / n, 4) if n else None, "ci95": wilson(k, n)}


def load_module(spec):
    if spec.endswith(".py"):
        s = importlib.util.spec_from_file_location("gmod", spec)
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        return m
    return importlib.import_module(spec)


def score(items, mod):
    out = {}
    for name, sel in (("random", lambda g: g["stratum"] == "random"), ("targeted", lambda g: g["stratum"] != "random"), ("all", lambda g: True)):
        rows = [(g, mod.gender_class(mod.parse_gender(g["text"]))) for g in items if sel(g)]
        r = {"items": len(rows), "classes_gold": dict(Counter(g["label"] for g, _ in rows))}
        for key, pos in (("directional", lambda c: c in DIRECTIONAL), ("any_wording", lambda c: c != "none")):
            gp = lambda g, p: pos(g["label"] if True else p)  # noqa: E731
            tp = sum(1 for g, p in rows if pos(g["label"]) and (pos(p) or (key == "directional" and p == "conflict")))
            flagged = sum(1 for g, p in rows if pos(p) or (key == "directional" and p == "conflict"))
            actual = sum(1 for g, p in rows if pos(g["label"]))
            r[key] = {"precision": ratio(tp, flagged), "recall": ratio(tp, actual)}
        r["class_accuracy"] = ratio(sum(1 for g, p in rows if g["label"] == p), len(rows))
        out[name] = r
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", default=str(ROOT / "data" / "raw" / "gold_gender_2021-2024.jsonl"))
    ap.add_argument("--module", default="backend.genderparse")
    ap.add_argument("--errors", action="store_true")
    a = ap.parse_args()
    items = [json.loads(l) for l in open(a.gold, encoding="utf-8")]
    mod = load_module(a.module)
    print(json.dumps({"rule_version": mod.RULE_VERSION, **score(items, mod)}, ensure_ascii=False, indent=1))
    if a.errors:
        for g in items:
            ts = mod.parse_gender(g["text"])
            p = mod.gender_class(ts)
            if p != g["label"]:
                print(g["gold_id"], g["label"], "->", p, g["confidence"], [t["snippet"] for t in ts][:2])


if __name__ == "__main__":
    main()
