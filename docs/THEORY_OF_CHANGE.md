# Theory of change

Shown on the home page as Figure 3 (`frontend/pages/home_motivation.js`). Revised position of the team, 2026-10-29.

## Problem and focus
High mid-career earnings can coexist with difficulty getting a new job. The focus is workers who are changing jobs or returning to work.

## What AgeLens is
An evidence-grounded clarification assistant for mid-career jobseekers. Given a user's background and one job ad, it identifies age conditions and exceptions, explains what remains uncertain, and prepares a targeted clarification request. It uses fixed rules and templates; no AI model is connected.

## The chain
1. Hard-to-read age wording.
2. Better interpretation: AgeLens reads the ad and lists what is explicit and what is unclear.
3. Cheaper to ask: a targeted question is ready to send.
4. Better-informed application decision.

## What the evidence suggests
These findings motivate the approach but do not establish its effectiveness (details and limits: `docs/LITERATURE.md`).
- Feng et al. (2026), NBER WP 35709: older applicants can face a disadvantage in entry-level hiring on one Chinese platform, while experience helps in higher-level positions.
- Lin (2025): in China, job loss for an employer reason jumps at age 35 in the 2015 census.
- Neumark, Burn, Button (2019), NBER WP 21669: in a US resume experiment, callbacks fall with age, more clearly for women.
- Burn, Firoozi, Ladd, Neumark (2022), NBER WP 30287: ageist wording in ads lowers the share of applicants over 40.
- Belot, Kircher, Muller (2019), IZA DP 10068: in a UK lab study, tailored search information raised interviews for some jobseekers.

## What we have NOT shown
- That AgeLens changes interviews, hiring or employment.
- That employers answer clarification requests.
- That the tool removes a binding age limit. It cannot.

## Worked example
A 38-year-old applicant sees "normally under 35; exceptions possible". AgeLens marks the cap at 35 as explicit and the exception as unclear, then drafts a neutral question: does eight years of operations experience qualify for the advertised exception? The employer decides what happens next. The question may get no answer, and the answer may be no.

## Claim size
The initial claim is improved decision support. Employer response is needed for any employment benefit. Hiring effects and wider economic effects are left for future evaluation.

## Heterogeneity
Stated age requirements vary by occupation, required experience and location, alongside explicitly written gender requirements. This describes patterns in advertisements, not differences in hiring outcomes (home page, "How age requirements vary across ads").
