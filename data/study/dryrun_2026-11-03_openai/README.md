# SIMULATED dry run with a real model, 2026-11-03 (crossover-ai-v1) - NOT A RESULT

> Superseded by `data/study/dryrun_2026-11-03_luna/`: the problems below were seen with gpt-4o-mini and prompt explain_v1.

**A real model was used here: OpenAI `gpt-4o-mini` wrote the AI-arm drafts.** The exported files and `SIMULATED_analysis.txt` say "No AI model was used". That sentence is hard-coded (`study_arms.SIM_NOTICE`) and is wrong for this run.

**There were no participants.** Eight scripted sessions submitted each tool's draft word for word. One team assistant (Claude, not blind, not independent) scored the 24 non-empty items and the same scores were entered as both R1 and R2, so the kappa of 1.0 means nothing. Calibration was filled mechanically to unlock scoring. The model runs at temperature 0 and the drafts barely vary, so the 8 sessions are repeats, not a sample, and the p-values mean nothing. Not approved by the teacher; formal mode stayed refused (403).

This tests the machinery and shows how the tool's drafts behave. It says nothing about whether AI help improves a person's reading.

## What it showed
- AI arm produced no draft on 8 of 16 task runs: T1 and T4 failed every time. The model returned a single statement with no question, and `_ai_from_statements` needs both a reading and a question. Nothing was dropped by the check; the prompt does not require all five sections.
- Mean key-fact accuracy of drafts: template 0.375, AI 0.208. The AI figure is low largely because the failed runs count as 0.
- T2: the AI draft says "you may qualify", which neither `validate_output` nor `study_arms.violates` catches. Scored as one unsupported claim (a judgment call, because of "may").
- The fixed template never meets q1 (it does not use the person's situation), so its actionable rate is 0 by construction. The template also calls T2's cap with an exception "a fixed age limit" (scored as one unsupported claim).
