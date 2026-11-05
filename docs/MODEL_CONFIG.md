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
`backend/prompts/explain_v4.txt`, header `# prompt_version: explain_v4` (older versions kept for the record); recorded with every call. Change = new file (`explain_v2.txt`) + `PROMPT_FILE`.

## The AI normalising the input
For one pasted ad, the model also returns its own reading (`reading` in `explain_v4`), in the same call. `backend/reading_check.py` accepts it only if its quotes occur word for word in the ad, outside instruction-like sentences, and its ages are written in that quote. A limit the rules read is never overridden. A checked reading only fills a gap (the rules read nothing, or missed an exception), and is tagged in the full answer. If the two conflict, the page shows both as two readings and picks neither. There is no separate AI card; the only standing disclosure is the line by the input saying the text goes to the AI provider. CVs are not sent: they stay rules only (team decision pending). The model sees the rules' terms, so it is not fully independent, and if both make the same mistake nothing is flagged. The template report and the study's evidence stay rules only; the study's AI arm ignores this field. `explain_v4` also tells the model to weave in what the person shared and not to state their age in the employer question. The study's AI arm uses the same prompt, so its questions rely on experience for rubric item q1.

## Real-data section of the AI report
`backend/real_context.py` adds counts around the pasted ad to the AI report: share of ads mentioning age, median stated maximum, exceptions, the range across regions, and two experience bands, with a few fixed suggestions. Plain lookup in `data/real`; no model writes or sees it, and only fixed wording, category names and numbers reach the page. Province x occupation is the finest level kept; there is no city data. Groups under 1,000 ads are not quoted. The occupation comes from keyword rules on the ad's title or the person's stated role, and 27.9% of all ads fall under "other", which is never quoted as a group. **The study's AI arm does not include this section**, so results from the study would not cover it.

## model_calls table (created if absent, in the app DB)
`ts, provider, model, prompt_version, latency_ms, status (ok|failed), failure_reason, input_tokens, output_tokens, cost_usd`. Never stores question, CV or ad text. Cost is NULL unless computed from real token usage x configured price.

## Failure behaviour
Timeout, network error, HTTP error, unreadable or malformed reply: the rules answer is shown with "Model not run — <reason>, so this is the rules-based answer."
