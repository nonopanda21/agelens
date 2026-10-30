#!/usr/bin/env python3
"""Analysis of a crossover-ai-v1 export (task-level JSON from /api/study/export). Thin CLI over backend/study_stats.py.
Primary: interpretation accuracy (paired, AI minus fixed template). Safety: unsupported claims. Secondary: actionable question, completion time.
A SIMULATED export is a software test only (no AI model was used). Usage: python3 scripts/analyze_study_ai.py EXPORT.json [--json out.json] [--text out.txt]"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import study_stats  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("export"); ap.add_argument("--json"); ap.add_argument("--text")
    a = ap.parse_args()
    o = study_stats.analyse(json.loads(Path(a.export).read_text(encoding="utf-8")))
    txt = study_stats.render(o)
    print(txt)
    if a.json: Path(a.json).write_text(json.dumps(o, indent=1, ensure_ascii=False))
    if a.text: Path(a.text).write_text(txt + "\n")
