# SIMULATED evaluation rehearsal, 2026-11-04 - NOT A RESULT

**No person took part.** 24 "participants" were role-played by `gpt-5.4-mini` (8 personas) through the crossover design on a local server; `gpt-6-luna` (prompt `explain_v3`) wrote the AI tool's text. Model raters scored the answers: `gpt-5.4` and `gpt-5.5`, with `gpt-4.1` resolving disagreements. Not approved by the teacher. It must not be reported as evidence that AI help works or does not work for people.

Limits that matter:
- Role-played readers can read the ad unaided, so scores start high. Real job seekers may behave very differently.
- No rater reached the 0.90 calibration target (best 0.879), and the third rater was needed on 152 of 192 items. The rubric or the raters need work before a real study.
- A first scoring pass was discarded: a script error passed the question inside the reading field. Only `SIMULATED_rescored.json` is valid.
- The personal-template arm ran outside the platform on all four tasks, not in a randomised order, so its comparison is descriptive.

| Mean per participant | Fixed template | AI | Template naming the person's situation |
|---|---|---|---|
| Key facts correct | 0.790 | 0.873 | 0.921 |
| Actionable question | 0.500 | 0.812 | 0.698 |
| Unsupported claims per task | 0.479 | 0.229 | 0.250 |

AI minus fixed template: accuracy +0.083 (95% CI 0.042 to 0.130, p 0.001), which misses the +0.10 threshold, so the pre-specified rule gives "no evidence of benefit"; actionable +0.312 (CI 0.104 to 0.521); unsupported -0.250 (CI -0.438 to -0.062). AI minus personal template, same tasks: accuracy -0.033 (CI -0.073 to 0.009), actionable +0.104 (CI -0.042 to 0.250), unsupported -0.083 (CI -0.271 to 0.104); no clear difference.
