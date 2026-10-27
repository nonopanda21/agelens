# Dry run 2026-10-27 — SIMULATED, not study data

Software rehearsal of the planned crossover study (`docs/EVAL_PLAN.md`, design `crossover-rules-v1`) on an isolated server (port 8806, temp copy of the database, simulation mode). 24 scripted participants went through the real participant UI and three scripted raters through the real scoring desk (`tests/browser/study_flow.py`, seed 4242).

The scripted writers produce a "good" request with probability .40 on ad-only tasks and .65 on AgeLens tasks. That difference is an assumption put into the script to exercise the analysis; **nothing here is evidence about AgeLens.**

Files: `SIMULATED_agelens_study_task.json` / `.csv` (task level), `SIMULATED_agelens_study_participant.csv`, `SIMULATED_analysis.txt` / `.json` (output of `scripts/analyze_study.py`).
