# Competitor comparison: Textio, Applied, one generic job-search product

Retrieval date for every fetch below: 2026-10-23. Pages were read with an automated fetch tool that summarises pages; fetched content was treated as untrusted data. "verified" = read on the official vendor site on that date. "not verified" = could not be read there, or only seen via a third party.

## 1. What each product offers (from sources)

### Textio (employer tool)
- https://textio.com (retrieved 2026-10-23) - verified. An AI suite for recruiting and performance management, sold as modular tools: job posts, recruiting communications, manager feedback; a separate product (Lavalier) covers interview intelligence. Users are employer-side: recruiters, talent acquisition, people ops, managers. Job seekers are not described as users. The page claims bias elimination in recruiting communications and cites vendor figures (e.g. "30+" models, 25% of Fortune 500 used it). Those figures are vendor claims, not verified by us.
- https://textio.com/products/library/ (2026-10-23) - verified. Textio Score rates job posts on likely appeal to applicants; a Gender meter flags skewed language; an "Age graph" shows how content appeals to different generations. Users: "recruiters and managers", people who write talent content.
- https://textio.com/blog/bias-interruption-beyond-gender (2026-10-23; the post is dated 26 March 2020, so it may be out of date) - verified. "Age graph" shows how text may land with different age groups; "age phrase highlights" flag wording the vendor's data suggests may discourage some applicants (example given: "21st Century skills"). Addressed to writers of job posts.
- Not verified: the current product-level age feature set (the 2020 post is old; /products/job-posts returned "page not here"); any evidence that the age flags are accurate (vendor data only; a search found no independent validation).

### Applied (employer hiring platform)
- https://app.beapplied.com/ (2026-10-23; www.beapplied.com redirects here) - NOT verified. The page is a login/dashboard app (title "Profile"); no marketing text could be read. https://www.appliedhq.com redirects to a domain-for-sale page and is not the vendor.
- Only a web search summary of third-party pages (TechRound, Trustpilot, directory sites, 2026-10-23) was available: UK platform that describes itself as behavioural-science-backed, with anonymised applications, skills-based work-sample assessments and structured scoring, reportedly also removing gendered language from job adverts. This is secondary information - not verified. Outcome figures ("60% would have been missed") are vendor claims repeated by others - not verified.
- Because the official site could not be read, the Applied column below is provisional and must be re-checked by a team member in a normal browser before presenting.

### Generic job-search product: LinkedIn Jobs
- Why chosen: the largest widely used general job-search service, so a seeker comparison is concrete. This is a choice, not a ranking.
- https://www.linkedin.com/help/linkedin/answer/a511279 (2026-10-23) - verified (help page). Members search for jobs matching skills and goals, apply on LinkedIn, and create up to 20 job alerts (daily/weekly, email/app). The page does not mention filters, matching or AI features.
- Not verified: any LinkedIn feature that interprets age wording in an ad; any AI job-match feature (not described on the page we read).

## 2. Comparison

| Dimension | Textio | Applied | LinkedIn Jobs | AgeLens |
|---|---|---|---|---|
| User | Employer (writer of posts) - verified | Employer/recruiter, candidates answer assessments - not verified | Job seeker (and employers) - verified (help page) | Job seeker, with a separate human reviewer role |
| Task | Improve wording of employer text; score appeal | Reduce bias in screening (provisional) | Find and apply to jobs; alerts | Understand age wording in a specific ad for a specific person; prepare what to ask |
| Workflow | Write/edit text, get score and suggestions | Anonymise, assess, score (provisional) | Search, alert, apply | Personal question -> ad evidence -> uncertainty -> clarification request -> human reply |
| Interprets age wording in one ad for one person | No: generic wording flags for writers (age graph, phrase highlights) - verified | Not evidenced | Not evidenced (not verified) | Yes, by design (rules-based now; no model connected) |
| Human review loop | Not described on pages read | Peer review of answers per third parties - not verified | Not described | Yes: seeker request, reviewer questions, published reply |
| Evidence traceability to original text | Highlights in the writer's own text | Not evidenced | Not applicable | Each finding links to ad snippet and character offsets |

## 3. AgeLens's differentiator and what is not novel
- Differentiator: the whole flow in one place - the seeker's own question and background, the ad's original wording as cited evidence, explicit uncertainty and information gaps, a drafted clarification request, and a reply from a human. Facts from the ad, the user's statements and inference are kept apart.
- Not novel: a chat-style interface; LLM summarisation or explanation (and no model is connected at present - the UI says "Template demo"); keyword highlighting of age wording (Textio-type tools do a version of it for employers).
- We do not claim that no similar product exists. We only compared the three above, and could not verify Applied's current offer or any LinkedIn age-wording feature. Whether the flow helps users is untested; see docs/EVAL_PROTOCOL.md (when present) and docs/PENDING_TEACHER.md.
