"""Score AgeLens age rules against the blind gold set, and estimate their effect on the real 2021-2024 population.

Usage
  # 1. score one or more rule modules (same API as backend.ageparse) against the hand-labelled gold set
  python scripts/eval_rules.py --gold data/raw/gold_age_2021-2024.jsonl \
      --modules backend.ageparse[,backend.ageparse_cand_a,...] [--diff] [--json out.json]

  # 2. population mode: run each module over a seeded random sample of N real 2021-2024 ads
  python scripts/eval_rules.py --population [--n 50000] [--seed 2024] --modules backend.ageparse,... [--json out.json]

  # 3. (how the gold set was drawn; never runs any rule) draw unlabelled gold candidates
  python scripts/eval_rules.py --draw-gold --out data/raw/gold_age_candidates.jsonl [--seed 20261028]

Rule side of every comparison (same semantics as backend/realdata.py and backend/evidence.py):
  detected     = age_status(terms) != 'none'
  class        = ad_class(terms)
  max_age      = MIN(max_age) over high-confidence, non-preference terms (evidence.MAXAGE_SQL), else None
  has_exception= any term with exception_text that is not an 'unlimited' (年龄不限) term
Gold side: fields has_age_condition, class, max_age, has_exception, confidence, stratum (see docs/RULES_GOLD.md).

The population sample is cached (gzip jsonl, git-ignored data/raw/) so repeated runs skip the 14 GB pass.
Multiprocessing uses at most 6 workers (the CPU is shared).
"""
import argparse, csv, gzip, importlib, json, math, random, re, sys, time
from collections import Counter, defaultdict
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DEFAULT_CSV = ROOT / "data" / "raw" / "zhaopin_2016-2025.7.csv"
I_TITLE, I_DESC, I_YEAR = 1, 6, 17
YEARS = {2021, 2022, 2023, 2024}
N_2021_2024 = 10_054_663  # mapped 2021-2024 rows (docs/REAL_DATA_AUDIT.md); only used to pick a Bernoulli rate
CLASSES = ("hard_cap", "cap_with_exception", "range_or_min", "preference", "ambiguous", "none")
MAX_WORKERS = 6

# ------------------------------------------------------------------ gold-candidate draw (no rules are run here)
STRATA = [  # (name, regex on title+"\n"+description, ads wanted). Rarest first so they are not taken by others.
    ("cn_numeral", r"[二三四五六][十拾][一二三四五六七八九]?\s*(?:周岁|岁)|(?<![一二三四五六七八九十])十[六七八九]\s*(?:周)?岁", 25),
    # salary-like digits after a bound word, with 岁/年龄 within 100 characters (see match_stratum)
    ("salary_digits", r"(?:不超过|不得超过|最高|不低于|低于|不少于|不小于|至少|高于|小于|不高于)\s*\d{3,}", 30),
    ("range_sep", r"\d{2}\s*(?:周岁|岁)?\s*(?:至|到|～|~|——|--|－|—|－)\s*\d{2}\s*(?:周岁|岁)"
                  r"|\d{2}\s*(?:周岁|岁)\s*[-－—–~～至到]+\s*\d{2}", 35),
    ("graduate", r"应届|毕业\s*[0-9一二两三四五]\s*年|\d{2}\s*届", 30),
    ("cohort_young", r"年轻|(?<!\d)(?:[5-9]0|[5-9]5|00|05)\s*后", 30),
    ("qual_unlimited_health", r"年龄不限|不限年龄|年龄无要求|男女不限|身体健康", 25),
    ("qual_pref_relax", r"(?:岁|年龄|年纪)[^。；;\n]{0,15}(?:优先|放宽)|(?:优先|放宽)[^。；;\n]{0,10}(?:岁|年龄)", 25),
    ("qual_bounds", r"\d{2}\s*(?:周岁|岁)\s*(?:及以上|以上|及以下|以下|左右|以内|上下)", 25),
    ("exp_years", r"\d{1,2}\s*年(?:以上)?的?(?:相关|工作|行业|从业)?(?:工作)?经验|经验\s*\d{1,2}\s*年", 25),
]
STRATA_RE = [(n, re.compile(p), k) for n, p, k in STRATA]
# supplementary stratum, drawn in a second pass (--draw-extra) because the first draw held no 年龄不限 ad
EXTRA_STRATA = [("qual_age_unlimited", r"年龄不限|不限年龄|年龄无要求|年龄无限制|无年龄要求|无年龄限制|不限年纪|年龄(?:要求)?[:：]?\s*不限", 15)]
ANCHOR = re.compile(r"岁|年龄|年纪|年轻|(?<!\d)\d0后|[05]5后|应届|毕业\s*\S?\s*年|届|放宽|不限|身体健康")
STRONG = re.compile(r"岁|年龄|年纪")
WIN = 600


_CN_PHONE = re.compile(r"[零〇一二三四五六七八九幺](?:[\s\-]*[零〇一二三四五六七八九幺]){6,}")
_CONTACT_NAME = re.compile(r"((?:面试)?联系人[】\]]?\s*[:：]?\s*)[\u4e00-\u9fff]{2,3}(?=主任|经理|女士|先生|小姐|老师|\s|$|[，,。；;（(])")


def mask_more(text):
    """Extra masking on top of realdata.mask_contacts: phone numbers spelled in Chinese numerals and contact-person names."""
    text = _CN_PHONE.sub("[phone]", text)
    return _CONTACT_NAME.sub(lambda m: m.group(1) + "[name]", text)


def match_stratum(name, rx, text):
    """Span of the first match of a stratum regex in `text`, or None."""
    for m in rx.finditer(text):
        if name != "salary_digits" or STRONG.search(text[max(0, m.start() - 100):m.end() + 100]):
            return m.span()
    return None


def window(text, primary=None):
    """At most WIN characters of `text`, centred on the age-relevant part (primary span, else age anchors)."""
    if len(text) <= WIN:
        return text
    spans = [m.span() for m in STRONG.finditer(text)] or [m.span() for m in ANCHOR.finditer(text)]
    if primary:
        near = [s for s in spans if abs(s[0] - primary[0]) < WIN // 2 - 20]
        spans = [primary] + near
    if not spans:
        return text[:WIN]
    # the WIN-window that covers the most anchors, among windows centred on each anchor
    best, bstart = -1, 0
    for a, _ in spans[:200]:
        st = max(0, min(a - WIN // 2, len(text) - WIN))
        cov = sum(1 for x, y in spans if st <= x and y <= st + WIN)
        if primary and not (st <= primary[0] and primary[1] <= st + WIN):
            continue
        if cov > best:
            best, bstart = cov, st
    return text[bstart:bstart + WIN]


def _rows(csv_path):
    """Yield (row_index, year, title, description) for 2021-2024 rows. row_index counts data rows from 0."""
    csv.field_size_limit(sys.maxsize)
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        next(r)
        for i, row in enumerate(r):
            ys = row[I_YEAR].strip() if len(row) > I_YEAR else ""
            if len(ys) == 4 and ys.isdigit() and int(ys) in YEARS:
                yield i, int(ys), row[I_TITLE].strip(), row[I_DESC]
            if i and i % 1_000_000 == 0:
                print(f"  {i:,} rows read", file=sys.stderr, flush=True)


def draw_gold(csv_path, out, seed, n_uniform=150, p_uniform=4e-5, p_target=0.03, reservoir=400,
              pop_n=50_000, pop_seed=2024, pop_cache=None):
    """One streaming pass. Uniform: Bernoulli(p_uniform) then `n_uniform` drawn. Targeted: Bernoulli(p_target)
    prefilter, a seeded reservoir per stratum, then STRATA counts drawn without overlap. Optionally also fills the
    population cache (Bernoulli(1.1*pop_n/N) with its own seed) in the same pass."""
    from backend.realdata import mask_contacts  # imports ageparse but never calls it
    rng, prng = random.Random(seed), random.Random(pop_seed)
    p_pop = min(1.0, 1.1 * pop_n / N_2021_2024)
    uni, res, seen, pop = [], {n: [] for n, _, _ in STRATA}, Counter(), []
    for i, y, title, desc in _rows(csv_path):
        if pop_cache is not None and prng.random() < p_pop:
            pop.append((i, y, title + "\n" + desc))
        u = rng.random()
        if u < p_uniform:
            uni.append((i, y, title, desc))
        if u >= 1 - p_target:  # disjoint from the uniform draw region
            text = title + "\n" + desc
            for name, rx, _ in STRATA_RE:
                if match_stratum(name, rx, text):
                    seen[name] += 1
                    box = res[name]
                    if len(box) < reservoir:
                        box.append((i, y, title, desc))
                    else:
                        j = rng.randrange(seen[name])
                        if j < reservoir:
                            box[j] = (i, y, title, desc)
    drng = random.Random(seed + 1)
    drng.shuffle(uni)
    items, taken, texts = [], set(), set()  # texts: drop exact duplicate reposts within the targeted strata
    for i, y, t, d in uni[:n_uniform]:
        full = mask_more(mask_contacts(t + "\n" + d))
        items.append({"id": i, "year": y, "stratum": "random", "text": window(full)})
        taken.add(i); texts.add(items[-1]["text"])
    for name, rx, k in STRATA_RE:
        box = sorted(res[name])
        drng.shuffle(box)
        got = 0
        for i, y, t, d in box:
            if got >= k:
                break
            if i in taken:
                continue
            full = mask_more(mask_contacts(t + "\n" + d))
            sp = match_stratum(name, rx, full)
            if not sp:
                continue
            w = window(full, sp)
            if w in texts:
                continue
            items.append({"id": i, "year": y, "stratum": name, "text": w})
            taken.add(i); texts.add(w)
            got += 1
    Path(out).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items), encoding="utf-8")
    info = {"seed": seed, "uniform_candidates": len(uni), "stratum_matches_in_prefilter": dict(seen),
            "counts": dict(Counter(x["stratum"] for x in items))}
    if pop_cache is not None:
        prng2 = random.Random(pop_seed + 1)
        prng2.shuffle(pop)
        _write_pop(pop_cache, pop[:pop_n])
        info["population_cached"] = min(pop_n, len(pop))
    print(json.dumps(info, ensure_ascii=False, indent=1))
    return info


def draw_extra(csv_path, out, seed, exclude, p_target=0.03, reservoir=300):
    """Second pass for EXTRA_STRATA: same Bernoulli prefilter design with its own seed, ids already drawn excluded."""
    from backend.realdata import mask_contacts  # imports ageparse but never calls it
    rng = random.Random(seed)
    res, seen = {n: [] for n, _, _ in EXTRA_STRATA}, Counter()
    rxs = [(n, re.compile(p), k) for n, p, k in EXTRA_STRATA]
    for i, y, title, desc in _rows(csv_path):
        if rng.random() >= p_target or i in exclude:
            continue
        text = title + "\n" + desc
        for name, rx, _ in rxs:
            if rx.search(text):
                seen[name] += 1
                box = res[name]
                if len(box) < reservoir:
                    box.append((i, y, title, desc))
                else:
                    j = rng.randrange(seen[name])
                    if j < reservoir:
                        box[j] = (i, y, title, desc)
    drng, items, texts = random.Random(seed + 1), [], set()
    for name, rx, k in rxs:
        box = sorted(res[name])
        drng.shuffle(box)
        for i, y, t, d in box:
            if len(items) >= k:
                break
            full = mask_more(mask_contacts(t + "\n" + d))
            m = rx.search(full)
            if not m:
                continue
            w = window(full, m.span())
            if w in texts:
                continue
            items.append({"id": i, "year": y, "stratum": name, "text": w}); texts.add(w)
    Path(out).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items), encoding="utf-8")
    print(json.dumps({"seed": seed, "matches_in_prefilter": dict(seen), "drawn": len(items)}, ensure_ascii=False))


# ------------------------------------------------------------------ population sample
def _write_pop(path, rows):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for i, y, text in rows:
            f.write(json.dumps({"id": i, "year": y, "text": text}, ensure_ascii=False) + "\n")


def pop_sample(csv_path, n, seed, cache):
    if cache and Path(cache).exists():
        with gzip.open(cache, "rt", encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        if len(rows) >= n:
            return rows[:n]
    prng = random.Random(seed)
    p = min(1.0, 1.1 * n / N_2021_2024)
    pop = [(i, y, t + "\n" + d) for i, y, t, d in _rows(csv_path) if prng.random() < p]
    random.Random(seed + 1).shuffle(pop)
    pop = pop[:n]
    if cache:
        _write_pop(cache, pop)
    return [{"id": i, "year": y, "text": t} for i, y, t in pop]


_MOD = None


def _init(modname):
    global _MOD
    _MOD = importlib.import_module(modname)


def _cls_chunk(texts):
    out = []
    for t in texts:
        terms = _MOD.parse_age(t)
        out.append((_MOD.ad_class(terms), _MOD.age_status(terms), _rule_max(terms)))
    return out


def run_population(modules, rows, workers):
    res = {}
    texts = [r["text"] for r in rows]
    chunks = [texts[i:i + 1000] for i in range(0, len(texts), 1000)]
    for mod in modules:
        t0 = time.time()
        with get_context("fork").Pool(min(MAX_WORKERS, max(1, workers)), initializer=_init, initargs=(mod,)) as pool:
            outs = [x for part in pool.map(_cls_chunk, chunks) for x in part]
        cls = Counter(c for c, _, _ in outs)
        st = Counter(s for _, s, _ in outs)
        n = len(outs)
        res[mod] = {"n": n, "class_counts": {c: cls.get(c, 0) for c in CLASSES},
                    "status_counts": dict(st), "flagged": n - st.get("none", 0),
                    "flagged_share": (n - st.get("none", 0)) / n if n else None,
                    "flagged_share_ci": wilson(n - st.get("none", 0), n),
                    "explicit_share": st.get("explicit", 0) / n if n else None,
                    "cap_share": (cls.get("hard_cap", 0) + cls.get("cap_with_exception", 0)) / n if n else None,
                    "n_max_age": sum(1 for _, _, m in outs if m is not None), "seconds": round(time.time() - t0, 1),
                    "_classes": [c for c, _, _ in outs]}
    if len(modules) > 1:
        base = res[modules[0]]["_classes"]
        for mod in modules[1:]:
            mv = Counter((a, b) for a, b in zip(base, res[mod]["_classes"]) if a != b)
            res[mod]["moves_vs_" + modules[0]] = {f"{a} -> {b}": k for (a, b), k in mv.most_common(15)}
    for mod in modules:
        res[mod].pop("_classes")
    return res


# ------------------------------------------------------------------ scoring
def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def _rule_max(terms):
    xs = [t["max_age"] for t in terms if t.get("max_age") is not None and t.get("confidence") == "high"
          and t.get("kind") != "preference"]
    return min(xs) if xs else None


def rule_view(mod, text):
    terms = mod.parse_age(text)
    return {"class": mod.ad_class(terms), "status": mod.age_status(terms), "max_age": _rule_max(terms),
            "has_exception": any(t.get("exception_text") and "unlimited" not in (t.get("flag") or "") for t in terms),
            "snippets": sorted({t.get("snippet", "") for t in terms})[:3]}


def rate(k, n):
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None, "ci95": wilson(k, n)}


def score(items, preds):
    tp = sum(1 for g, p in zip(items, preds) if g["has_age_condition"] and p["status"] != "none")
    fp = sum(1 for g, p in zip(items, preds) if not g["has_age_condition"] and p["status"] != "none")
    fn = sum(1 for g, p in zip(items, preds) if g["has_age_condition"] and p["status"] == "none")
    prec, rec = rate(tp, tp + fp), rate(tp, tp + fn)
    f1 = (2 * prec["rate"] * rec["rate"] / (prec["rate"] + rec["rate"])) if prec["rate"] and rec["rate"] else 0.0
    # secondary view: detected = ad_class != 'none' (age_status calls 年龄不限 'uncertain', ad_class calls it 'none')
    tp2 = sum(1 for g, p in zip(items, preds) if g["has_age_condition"] and p["class"] != "none")
    fp2 = sum(1 for g, p in zip(items, preds) if not g["has_age_condition"] and p["class"] != "none")
    fn2 = sum(1 for g, p in zip(items, preds) if g["has_age_condition"] and p["class"] == "none")
    conf = {g: {p: 0 for p in CLASSES} for g in CLASSES}
    for g, p in zip(items, preds):
        conf[g["class"]][p["class"]] += 1
    ok = sum(conf[c][c] for c in CLASSES)
    per = {}
    for c in CLASSES:
        col = sum(conf[g][c] for g in CLASSES)
        row = sum(conf[c].values())
        per[c] = {"precision": rate(conf[c][c], col), "recall": rate(conf[c][c], row), "gold_n": row, "pred_n": col}
    mx = [(g, p) for g, p in zip(items, preds) if g.get("max_age") is not None]
    mx_ok = sum(1 for g, p in mx if p["max_age"] == g["max_age"])
    exc = [(g, p) for g, p in zip(items, preds) if g["has_age_condition"]]
    exc_ok = sum(1 for g, p in exc if bool(g.get("has_exception")) == p["has_exception"])
    hi = [(g, p) for g, p in zip(items, preds) if g.get("confidence") == "high"]
    strata = defaultdict(lambda: {"n": 0, "gold_pos": 0, "fp": 0, "fn": 0, "class_wrong": 0})
    for g, p in zip(items, preds):
        s = strata[g["stratum"]]
        s["n"] += 1; s["gold_pos"] += bool(g["has_age_condition"])
        s["fp"] += (not g["has_age_condition"]) and p["status"] != "none"
        s["fn"] += g["has_age_condition"] and p["status"] == "none"
        s["class_wrong"] += g["class"] != p["class"]
    return {"n": len(items), "gold_positive": sum(1 for g in items if g["has_age_condition"]),
            "prevalence": rate(sum(1 for g in items if g["has_age_condition"]), len(items)),
            "detection": {"tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": round(f1, 4)},
            "detection_by_class": {"tp": tp2, "fp": fp2, "fn": fn2, "precision": rate(tp2, tp2 + fp2), "recall": rate(tp2, tp2 + fn2)},
            "class_accuracy": rate(ok, len(items)),
            "class_accuracy_high_conf_gold": rate(sum(1 for g, p in hi if g["class"] == p["class"]), len(hi)),
            "max_age_exact": rate(mx_ok, len(mx)),
            "exception_agreement_on_gold_positive": rate(exc_ok, len(exc)),
            "per_class": per, "confusion_gold_rows_pred_cols": conf, "per_stratum": dict(sorted(strata.items()))}


def _fmt_rate(r):
    if r["rate"] is None:
        return "n/a (0 items)"
    lo, hi = r["ci95"]
    return f"{100 * r['rate']:.1f}% ({r['k']}/{r['n']}; 95% CI {100 * lo:.1f}-{100 * hi:.1f}%)"


def report(name, sc, title):
    L = [f"  [{title}] n={sc['n']}, gold positive={sc['gold_positive']} (prevalence {_fmt_rate(sc['prevalence'])})"]
    d = sc["detection"]
    L += [f"    detection  TP={d['tp']} FP={d['fp']} FN={d['fn']}",
          f"      precision {_fmt_rate(d['precision'])}", f"      recall    {_fmt_rate(d['recall'])}",
          f"      F1 {d['f1']:.3f}",
          f"    detection by class != none: TP={sc['detection_by_class']['tp']} FP={sc['detection_by_class']['fp']} "
          f"FN={sc['detection_by_class']['fn']}; precision {_fmt_rate(sc['detection_by_class']['precision'])}; "
          f"recall {_fmt_rate(sc['detection_by_class']['recall'])}",
          f"    class accuracy          {_fmt_rate(sc['class_accuracy'])}",
          f"    class acc (high-conf gold) {_fmt_rate(sc['class_accuracy_high_conf_gold'])}",
          f"    max-age exact match     {_fmt_rate(sc['max_age_exact'])}",
          f"    exception agreement     {_fmt_rate(sc['exception_agreement_on_gold_positive'])}",
          "    per class (precision | recall):"]
    for c in CLASSES:
        pc = sc["per_class"][c]
        pr = "n/a" if pc["precision"]["rate"] is None else f"{100 * pc['precision']['rate']:.0f}% ({pc['precision']['k']}/{pc['precision']['n']})"
        rc = "n/a" if pc["recall"]["rate"] is None else f"{100 * pc['recall']['rate']:.0f}% ({pc['recall']['k']}/{pc['recall']['n']})"
        L.append(f"      {c:<19} {pr:<16} | {rc}")
    L.append("    confusion (rows = gold, cols = rules): " + " ".join(f"{c[:6]:>6}" for c in CLASSES))
    for g in CLASSES:
        L.append(f"      {g:<19}" + " " * 20 + " ".join(f"{sc['confusion_gold_rows_pred_cols'][g][p]:>6}" for p in CLASSES))
    L.append("    per stratum: n / gold+ / FP / FN / class wrong")
    for s, v in sc["per_stratum"].items():
        L.append(f"      {s:<22} {v['n']:>4} {v['gold_pos']:>5} {v['fp']:>4} {v['fn']:>4} {v['class_wrong']:>5}")
    return "\n".join(L)


def load_gold(path):
    items = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").split("\n") if line.strip()]
    for g in items:
        assert g["class"] in CLASSES, (g["id"], g["class"])
    return items


def _short(text, snips, n=160):
    if snips and snips[0] and snips[0] in text:
        a = text.index(snips[0])
        return text[max(0, a - 30):a + n].replace("\n", " / ")
    m = ANCHOR.search(text)
    a = m.start() if m else 0
    return text[max(0, a - 60):a + n].replace("\n", " / ")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", default=str(ROOT / "data/raw/gold_age_2021-2024.jsonl"))
    ap.add_argument("--modules", default="backend.ageparse")
    ap.add_argument("--diff", action="store_true", help="list items where modules disagree (one module: vs gold)")
    ap.add_argument("--json", help="write all numbers to this JSON file")
    ap.add_argument("--population", action="store_true", help="population mode (seeded random sample of real ads)")
    ap.add_argument("--n", type=int, default=50_000)
    ap.add_argument("--seed", type=int, default=2024, help="population seed")
    ap.add_argument("--pop-cache", default=None, help="gzip jsonl cache (default data/raw/eval_pop_n{N}_seed{S}.jsonl.gz)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--draw-gold", action="store_true", help="draw the unlabelled gold candidates (no rules run)")
    ap.add_argument("--out", help="--draw-gold output")
    ap.add_argument("--gold-seed", type=int, default=20261028)
    ap.add_argument("--draw-extra", action="store_true", help="draw EXTRA_STRATA, excluding ids in --gold (no rules run)")
    ap.add_argument("--extra-seed", type=int, default=20261029)
    a = ap.parse_args()
    mods = [m.strip() for m in a.modules.split(",") if m.strip()]
    cache = a.pop_cache or str(ROOT / "data" / "raw" / f"eval_pop_n{a.n}_seed{a.seed}.jsonl.gz")

    if a.draw_extra:
        excl = {json.loads(x)["id"] for x in Path(a.gold).read_text(encoding="utf-8").split("\n") if x.strip()}
        draw_extra(a.csv, a.out, a.extra_seed, excl)
        return
    if a.draw_gold:
        draw_gold(a.csv, a.out, a.gold_seed, pop_n=a.n, pop_seed=a.seed, pop_cache=cache)
        return
    if a.population:
        rows = pop_sample(a.csv, a.n, a.seed, cache)
        res = run_population(mods, rows, a.workers)
        print(f"Population sample: {len(rows):,} random 2021-2024 ads (seed {a.seed})")
        for m, r in res.items():
            lo, hi = r["flagged_share_ci"]
            print(f"\n== {m}\n  flagged (status != none): {r['flagged']:,} = {100 * r['flagged_share']:.2f}% "
                  f"(95% CI {100 * lo:.2f}-{100 * hi:.2f}%); explicit {100 * r['explicit_share']:.2f}%; "
                  f"cap {100 * r['cap_share']:.2f}%; with max age {r['n_max_age']:,}  [{r['seconds']}s]")
            for c in CLASSES:
                print(f"    {c:<19} {r['class_counts'][c]:>7,}  {100 * r['class_counts'][c] / r['n']:6.2f}%")
            for k, v in r.items():
                if k.startswith("moves_vs_"):
                    print(f"  class moves vs {k[9:]}:")
                    for mv, cnt in v.items():
                        print(f"    {mv:<40} {cnt:>6,}")
        if a.json:
            Path(a.json).write_text(json.dumps({"mode": "population", "n": len(rows), "seed": a.seed, "modules": res},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
        return

    items = load_gold(a.gold)
    out = {"gold": a.gold, "n": len(items), "modules": {}}
    preds = {}
    for m in mods:
        mod = importlib.import_module(m)
        preds[m] = [rule_view(mod, g["text"]) for g in items]
        rnd = [i for i, g in enumerate(items) if g["stratum"] == "random"]
        sc_r = score([items[i] for i in rnd], [preds[m][i] for i in rnd])
        sc_a = score(items, preds[m])
        out["modules"][m] = {"rule_version": getattr(mod, "RULE_VERSION", None), "random_only": sc_r, "all": sc_a}
        print(f"\n== {m} ({getattr(mod, 'RULE_VERSION', '?')})")
        print(report(m, sc_r, "RANDOM stratum only - unbiased"))
        print(report(m, sc_a, "ALL items - targeted strata over-sample hard cases; not a prevalence estimate"))
    if a.diff:
        rows = []
        for i, g in enumerate(items):
            vs = [(preds[m][i]["class"], preds[m][i]["max_age"], preds[m][i]["status"] != "none") for m in mods]
            gold = (g["class"], g.get("max_age"), g["has_age_condition"])
            if (len(mods) > 1 and len(set(vs)) > 1) or (len(mods) == 1 and vs[0] != gold):
                rows.append({"id": g["id"], "stratum": g["stratum"], "gold": {"class": g["class"], "max_age": g.get("max_age"),
                             "has_age_condition": g["has_age_condition"], "confidence": g.get("confidence"), "note": g.get("note")},
                             "rules": {m: dict(zip(("class", "max_age", "detected"), v)) for m, v in zip(mods, vs)},
                             "text": _short(g["text"], preds[mods[0]][i]["snippets"])})
        out["diff"] = rows
        print(f"\n== diff: {len(rows)} items" + (" where modules disagree" if len(mods) > 1 else " where the rules differ from gold"))
        for r in rows:
            gd = r["gold"]
            print(f"- id {r['id']} [{r['stratum']}] gold {gd['class']} max={gd['max_age']} pos={gd['has_age_condition']} ({gd['confidence']})")
            for m, v in r["rules"].items():
                print(f"    {m}: {v['class']} max={v['max_age']} detected={v['detected']}")
            print(f"    text: {r['text']}")
            if gd.get("note"):
                print(f"    note: {gd['note']}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
