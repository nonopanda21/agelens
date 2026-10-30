# SIMULATED dry run, 2026-10-29 (crossover-ai-v1) - NOT A RESULT

**No AI model was used.** The "contextual AI" tool text was written by a script (`SimulatedAiDrafter` in `backend/study_arms.py`). Participants, raters and their answers were scripted by `tests/browser/study_flow.py` (6 simulated participants x 4 tasks, 3 scripted raters, real UI, port 8866, a copy of the database). The scripted writers choose key-fact sentences with probability 0.60 (template tool) or 0.70 (contextual tool): that difference is an ASSUMPTION built in to exercise the analysis. Completion times are seconds of browser automation and mean nothing.

This tests the machinery only (allocation, blinding, scoring, export, paired analysis). It says NOTHING about AI effectiveness. Every file here is prefixed SIMULATED_ and carries `data_label = SIMULATED`.
