# Budget record

Total team budget: US$200 (SPEC2 section 12).

## 1. Plan (PLANNED, not spent)
| Line | Basis | Planned US$ |
|---|---|---|
| Two AI memberships | 2 x $20/month x 2 months | 80 |
| API tokens | pilot calls once a model is connected | 50 |
| Survey / participant costs | only if the teacher approves a real study | 50 |
| Reserve | | 20 |
| Total | | 200 |

## 2. INCURRED spend
To be filled by the team from receipts. Nothing is recorded here by us.
- What we can say about the build: the AgeLens software built so far connected no paid API (no model provider is implemented; AI status is disabled, "Template demo"). Whether any team member's membership was used for coding assistance, and its cost, is for the team to state - not known to this document.
- Incurred total: __ (team to fill). Biggest single item: __ (team to fill).

## 3. Public prices checked (retrieved 2026-10-23)
Prices change; re-check before buying.
- Claude consumer plans - https://claude.com/pricing (anthropic.com/pricing redirects there) - verified: Free $0; Pro $20/month billed monthly, or $17/month on annual billing ($200 up front); Max from $100/month. Only Pro matches the $20 membership line.
- Claude API - same page - verified: per million tokens, input/output: Fable 5.1 $10/$50; Opus 5.5 $4/$20; Sonnet 5.5 $2/$10; Haiku 5.5 $0.10/$0.50 (prompts up to 100K) ; batch listed at 50% off. Model names as the page lists them.
- OpenAI API - https://developers.openai.com/api/docs/pricing (platform.openai.com/docs/pricing redirects there) - verified: e.g. gpt-5.4-mini $0.75/$4.50, gpt-5.4-nano $0.20/$1.25, gpt-4.1-mini $0.40/$1.60 per million tokens (many other models listed).
- ChatGPT consumer plans - https://openai.com/chatgpt/pricing/ - NOT verified (HTTP 403 on fetch).
- Not checked: any other vendor, any survey/participant platform fees, any education discount.
- The team must confirm which memberships it actually holds; this document does not assume any.
- Order of magnitude (arithmetic, not a forecast): at $2 in / $10 out per million tokens, a call with 3,000 input and 1,000 output tokens costs about $0.016, so $50 would cover roughly 3,000 such calls. Actual usage is unknown.

## 4. Questions for the teacher (also in docs/PENDING_TEACHER.md)
1. May course budget be spent on AI memberships, or only API tokens?
2. Do personal memberships the team already holds count toward the $200?
3. Are API calls allowed with synthetic/ad data only, and with participant data?
4. Are participant payments permitted, and at what level? Is a consent/ethics step needed first?
5. Must spend be reimbursed, receipted, or logged in a specific format?
6. Is a connected-model arm required for the final, or is a simulated-only evaluation accepted?

## 5. Budget-driven trade-offs
| Trade-off | Reason | Consequence |
|---|---|---|
| No model connected; UI shows "Template demo" | No approved key/spend decision yet | The LLM arm of the planned evaluation cannot be run; briefs are rules-based |
| Formal trial not started | No connected model, no teacher approval of assignment, power analysis, ethics wording | Only clearly labelled simulated sessions to test the system |
| Simulated data only | No real ad data approved or imported | No accuracy figures on real ads |
| Participant budget held back | Needs teacher approval | No paid participants so far (confirm) |

## 6. Spend log template
| Date | Item | Category (membership / API / participants / reserve) | Planned US$ | Actual US$ | Receipt ref | Who paid | Approved by | Note |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

For API usage also record: model, prompt version, tokens in/out, latency, failures, billed cost.

## 7. Rule
Nothing is purchased automatically. No agent, script or code in this repo may buy, subscribe, or enter payment details. A human team member decides each purchase and logs it above. API keys, if ever added, stay in server config only.
