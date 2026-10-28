# The motivation

Source for the home section "The motivation" (`frontend/pages/home_motivation.js`, order 25). Written 2026-10-28.

Sources:
- **Pitch**: the team's design pitch (`Design Pitch.pdf`, Group Delta, SEPOL 425, 10.23). It has 7 pages: a title page and 6 numbered slides. "Slide n" below is the printed number: 1 literature, 2 recruitment evidence and target users, 3 existing products, 4 mechanism and impact, 5 evaluation risks, 6 feasibility.
- **Lin (2025)**: 林文炼, 年龄歧视导致了失业：一个断点回归设计, China Economic Quarterly 25(1): 103–120, DOI 10.13821/j.cnki.ceq.2025.01.07. Read in full; see `docs/LITERATURE.md` §1.
- **Feng et al. (2026)**: NBER Working Paper 35709. Not peer-reviewed. Page numbers are the paper's printed pages; the PDF page is one higher.

The PDFs are kept in `data/raw/motivation/` (git-ignored) and are not copied into the repository.

## 1. The problem

Many Chinese job ads put an age in the requirements, and 35 is the usual number.
- Lin (2025) analyses 59.69 million postings from five job sites (2016–2021). Of these, 18.95% state an age limit, 17.47% an upper limit and 16.35% a lower limit (p. 105).
- On all five sites, "under 35" is the most common upper limit (p. 105, Fig. 1b, p. 106).
- Feng et al. (2026, p. 8) study a different platform: 15% of postings state an upper limit, and 35 is 36% of those.

Many ads soften the cap with an exception, such as "35岁以下，条件优秀者可放宽" ("Under 35; may be relaxed for outstanding candidates"), but do not say what the exception means or who decides. The users the pitch names are mid-career job seekers in engineering, operations, sales and professional services (slide 2). They need to read the age condition against their own background, target role and location (slide 2). Their typical question, from the pitch: "I am 38 with eight years in operations. Does 'normally under 35; exceptions possible' rule me out?"

The example sentence is illustrative. It is a common wording pattern, not a quote from a specific ad in either paper.

## 2. What the research shows (and its limits)

| Claim | Source (page) | Limit |
|---|---|---|
| About 1 in 5 postings states an age limit; 35 is the most common upper limit on every site studied. | Lin pp. 105–106, Fig. 1. Feng p. 8. | Counts what ads say, not who is hired. |
| Just above a posted maximum age, applications per posting fall 17% and positive replies nearly 20%. | Feng pp. 10–11, Fig. 1. | Working paper, not peer-reviewed. One platform. Applicants are bachelor's graduates in Guangdong. The paper notes that the reply gap may partly reflect who still applies (p. 10). |
| In the 2015 census, the share of working-age people who lost a job for an employer reason rises from 0.3970% just under 35 to 0.5373% just over (+0.1403 points, SE 0.0594), about 35% more. | Lin pp. 108–109, Tables 1–2 (col. 1). | Regression discontinuity: it compares people born months apart. The jump is significant for people with high school or less and not significant for college graduates (Table 6, p. 117). Present in 2005, not significant in 2010 (p. 117). Mechanism evidence is city-level and correlational (p. 115). |

What the two papers explain differently:
- Feng et al. read the pattern as statistical discrimination on a job ladder: "not out of animus" (p. 6).
- Lin attributes it to negative age stereotypes and an "anchor" at 35 (pp. 113–115).

AgeLens does not depend on either mechanism. It relies only on what both papers show: the number 35 in an ad matters.

Neither study tells us whether a given ad's exception will be applied to a given person, and neither evaluates a tool like AgeLens.

## 3. The gap

- **Employer-side tools.** Textio and Applied help employers write fairer ads, for example by flagging age-related wording for the writer. Details and verification status are in `docs/COMPETITORS.md`.
- **Seeker-side tools.** Job boards (LinkedIn Jobs in our comparison) help seekers search and set alerts. The pitch also names Jobscan, which matches resume keywords to job descriptions (slide 3; not verified by us).
- **What the reader of one ad needs:**
  - what this ad's age line says, in its own words;
  - which part is a rule, which is an exception and which is simply unknown, for their own background;
  - a clear question to send the employer before deciding.

## 4. Why AgeLens is designed this way

| Decision | Reason | Source |
|---|---|---|
| Quote the original words next to every finding | The meaning sits in the exact wording. A paraphrase can drop "可放宽" (may be relaxed), and that clause is what a 38-year-old needs to see. | Pitch slide 3: "connect original ad excerpts … making supporting evidence and remaining uncertainty explicit". |
| Separate explicit / exception / unclear | A hard cap, an exception and a soft preference lead to different next steps. Posted caps are binding in practice (Feng), so it matters which one an ad states. | Feng pp. 10–11. Pitch slide 4: "Conditions, exceptions, unknowns". |
| Start from the person's question | The same line reads differently for different people. | Pitch slide 2 (need, user question) and slide 3 ("Start with the applicant's question"). |
| Prepare a question, not a verdict; never decide eligibility | Only the employer knows how its rule is applied. The tool lowers the cost of asking a clear, neutral question. | Pitch slide 4: "reduce information and preparation costs"; "A source-linked inquiry". |
| A human reviewer, and small claims | A person looks at the same evidence. Job effects take months to observe. A short pilot can only show comprehension, inquiry quality and preparation time. | Pitch slides 2–3 ("questions for human review") and slide 5 ("restrict claims to immediate task outcomes"). |

The pitch's macro pathway (slide 4) runs from better matching to less income scarring (Şahin et al. 2014; Huckfeldt 2022). The pitch itself labels these "impact pathways, not measured product effects", so the site does not present them as results.

## 5. Where AgeLens stands today (accurate version)

- AgeLens reads ads with rules. No AI model is connected, and the UI says "Template demo". The pitch's feasibility slide (6) budgets API credits for DeepSeek or Claude Haiku. That is a plan, not the current product.
- The public demo uses simulated ads. Real Zhaopin data (2016–2025.7) was received on 2026-10-28 and is being prepared for local analysis only (see DEVELOPMENT_LOG.md).
- The pitch's "connect original ad excerpts with relevant historical postings" (slide 3) is currently done over simulated postings.
- No effect on job outcomes has been tested.
