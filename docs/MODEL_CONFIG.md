# Model configuration and prompt versions

Default: **Template demo** - no model, no network call. `GET /api/ai/status` returns `{connected:false,label:"Template demo",...}`; the UI says "Model not run — Template demo".

## Pipeline (backend/brief.py, backend/llm.py)
1. Evidence extraction: rules/DB (ageparse, evidence).
2. Situational explanation: the rules/template answer is always built; if a provider is connected its statements are added.
3. Citation and contradiction check in code (`llm.validate_output`): every cited id must be in the input; every quote (the `quote` field and any quoted text inside a statement) must occur literally in a cited ad's text; age-like numbers (14-75) in ad_fact/model_inference statements must be among the rules-extracted terms of the cited ads (raw ad text is not enough, so an injected "maximum age 30" sentence cannot become a fact); user_stated numbers must be ones the user entered; legal/probability/eligibility/accusation wording is dropped; an age preference described as a cap is dropped; a statement about an ad with contradictory terms that does not say so is dropped; an exception present in an ad but omitted by the model is flagged (the rules answer already carries it).
4. Human confirmation: every brief carries `needs_human_confirmation:true` and tells the reader to check the original text.

**The self-check is not a correctness guarantee.** It catches only the failures listed above. A model can still write a misleading but well-cited sentence. Statements are typed ad_fact / user_stated / rules / model_inference and shown with those labels.

## Server-side configuration (environment only; never in front-end, exports or logs)
| Variable | Meaning |
|---|---|
| `AGELENS_LLM_PROVIDER` | `template` (default), `anthropic` or `openai`; if unset, chosen from whichever key is present (`anthropic` first) |
| `AGELENS_LLM_API_KEY`, or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | key (never returned by any endpoint, never in errors or the log table) |
| `AGELENS_LLM_MODEL` | model id (required; no default is hard-coded) |
| `AGELENS_LLM_TIMEOUT` | seconds, default 30 (use 40 for `gpt-6-luna`, which took 5 to 13 s in testing; the page waits 45 s) |
| `AGELENS_LLM_BASE_URL` | override of the provider's default endpoint |
| `AGELENS_LLM_MAX_CALLS_PER_DAY` | stops model calls for the UTC day after this many; the rules answer keeps working. Unset = no limit. Set it on any public server |
| `AGELENS_LLM_PRICE_IN_PER_MTOK`, `AGELENS_LLM_PRICE_OUT_PER_MTOK` | USD per million tokens; cost is stored only if both are set AND the API returned token counts |

Connected only when provider, key and model id are all set. Both providers use urllib; unit tests inject a mocked HTTP layer. The OpenAI provider was run for real on a local server on 2026-11-03 with `gpt-4o-mini`, `gpt-4.1`, `gpt-5.4-mini` and `gpt-6-luna` (chosen). The Anthropic provider has never been run against the real API.

## Data boundary
Ads and CVs are DATA. They are sent only as JSON string fields inside a `BEGIN_DATA_JSON ... END_DATA_JSON` block in the user message (`<`/`>` escaped); the instructions live in the system prompt. Only the question, the user-confirmed structured profile (age, occupation, years, skills/summary lines, region, education) and at most 12 ads (first 1500 chars each) are sent. CV files and full CV text never reach the adapter.

## Prompts
`backend/prompts/explain_v3.txt`, header `# prompt_version: explain_v3` (older versions kept for the record); recorded with every call. Change = new file (`explain_v2.txt`) + `PROMPT_FILE`.

## model_calls table (created if absent, in the app DB)
`ts, provider, model, prompt_version, latency_ms, status (ok|failed), failure_reason, input_tokens, output_tokens, cost_usd`. Never stores question, CV or ad text. Cost is NULL unless computed from real token usage x configured price.

## Failure behaviour
Timeout, network error, HTTP error, unreadable or malformed reply: the rules answer is shown with "Model not run — <reason>, so this is the rules-based answer."
