# Export schema (export-v1) — anonymous

Endpoint: `GET /api/study/export?scope=simulated|formal&format=json|csv&level=task|participant` (needs the local study token; demo-grade).
Operator desk: `#/study/score` > Operator. Simulated files are named `SIMULATED_*`, the CSV starts with a `# SIMULATION — not study data` line and every row has `simulated=1`.
The `formal` scope is refused by the server unless the formal-mode gate is open (see docs/EVAL_PROTOCOL.md section 8) and never contains simulated rows.

Privacy: participant codes only (random; `SIM-` prefix = simulated). **No free text is exported**: participant answers and rater notes stay in the database; only answer length and `notes_present` are exported. No names, emails, IPs or user agents are collected.

## Task level (one row per participant x task; CSV `level=task`, JSON `tasks`)
participant_code, arm (template|assisted), simulated (1/0), task_id (T1-T4), task_kind, position (1-4 order shown), attempted, submitted, missing (no submitted/non-empty answer -> counted NOT usable), timed_out, late (>5 s after limit), elapsed_s (server-measured), time_limit_s, answer_chars, aid_inserted, aid_provider (fixed-template|SIMULATED|model|none), aid_simulated, model_failure, r1_c1..r1_c4, r1_severe, r2_*, r3_* (1 = met / severe present, 0 = not; blank = not scored; c1 background, c2 citation, c3 uncertainty, c4 specific question), notes_present, disagreement (R1 vs R2 differ on any field), resolution (agree|adjudicated|unresolved|unscored|missing), final_c1..final_c4, final_severe (R1=R2, else majority of R1,R2,R3), final_usable (1 iff final c1-c4 all 1 and severe 0; 0 if missing; blank if unresolved/unscored), participant_status (enrolled|in_progress|completed|withdrawn), dropout.

## Participant level (`level=participant`, JSON `participants`)
participant_code, arm, simulated, block_no, tasks_attempted, tasks_submitted, tasks_missing, n_usable (0-4; blank if any task unresolved/unscored), usable_share (n_usable/4; PRIMARY outcome), usable_ge3 (secondary), total_elapsed_s, model_failures, participant_status, dropout.
Dropout rule (pre-specified): withdrawn, or not completed and no activity for more than 60 minutes.

## JSON envelope
`meta` {schema, scope, simulated, banner, generated_at, tasks_version, tasks_sha256, rubric_version, allocation, model, n_participants}, `participants`, `tasks`, `scores`.

## Offline scoring
`scoring_template.csv` is the paper/spreadsheet equivalent of the scoring form (one row per item and rater, same 4 criteria + severe flag). Offline sheets must be keyed by `item_key` or participant code only and kept blind to arm.

## export-v2 additions (2026-10-27, crossover design `crossover-rules-v1`)
Task level: `condition` (A = ad only, B = AgeLens evidence check; blank in the legacy design); `arm` holds the sequence (AB-S1 | AB-S2 | BA-S1 | BA-S2). Participant level: `sequence`, `first_condition`, `usable_share_A`, `usable_share_B`, `diff_B_minus_A` (PRIMARY outcome; blank if any task is unresolved or unscored). `meta` adds `design` and the pre-registered `threshold`. `aid_provider` is `agelens-rules <rule version>` on B tasks and `none` on A tasks. Aid text and answers are never exported.
