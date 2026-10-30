# Literature verification record (agent L, round 2; Lin section updated 2026-10-28 from the full text)

Accessed 2026-10-23 (US Central time). Fetched content was treated as untrusted data.

## 1. Lin (2025), 经济学（季刊） / China Economic Quarterly. Verified from the full text on 2026-10-28

- Citation: 林文炼 (Lin Wenlian), 《年龄歧视导致了失业：一个断点回归设计》, 经济学（季刊）2025, 25(1): 103–120, DOI 10.13821/j.cnki.ceq.2025.01.07. English title as printed on p. 120: "Age Discrimination Causes Unemployment: A Regression Discontinuity Design". Author: Sun Yat-sen University (Shenzhen). JEL J70, J71, J64. Peer-reviewed journal article (three referees are thanked, p. 103).
- What was read on 2026-10-28:
  - the full article PDF (CNKI download, 18 pages, printed pp. 103–120), supplied by the team in `data/raw/motivation/Design Pitch/` (git-ignored);
  - text extracted with `pdftotext`;
  - pp. 105, 106, 111 and 120 rendered as images and looked at (Fig. 1, Fig. 2, the English abstract).
- **Not read:** the online appendix (附录 I–III; 附表 A1–A4; 附图 A1–A2). It holds the robustness tables, the placebo tables and the 2022–2024 recheck figure. Claims that rest only on the appendix are marked below.
- Earlier record (2026-10-23): only the CNKI abstract was readable, so the card was marked "To be verified". That state is replaced by this section.

**Design and data**
- **Ads** (Section 2, pp. 105–106):
  - 59.69 million postings, 2016–2021, from the RESSET (锐思) database covering 51job, Liepin, BOSS Zhipin, Zhaopin and 58.com (footnote p. 105);
  - age limits parsed from text patterns such as "X岁以下" and "不超过X岁";
  - a recheck on 41.59 million postings, Jan 2022 to Apr 2024, from 51job, Liepin and Zhaopin (p. 106; the figure itself, 附图 A1, is in the appendix and was not seen).
- **People** (Section 3, pp. 107–108):
  - the paper calls it the "2015 population census": 2,003,563 raw records, then working-age people only (men 16–59, women 16–54), excluding records without household information;
  - outcome: "lost job for an employer reason" (因单位原因失去工作: the employer ended the relationship), a 0/1 variable for every working-age respondent, multiplied by 100;
  - design: local linear (quadratic) regression discontinuity in age in months around 35. Bandwidths are MSE-optimal (Calonico et al. 2014): 45 (58) months, giving 205,967 (267,139) people. County fixed effects; SEs clustered by county.
  - Note (our outside knowledge, not stated in the paper): China's 2015 survey was the 1% population sample survey, often called a mini-census. The paper's wording is kept.

**Findings, with pages**

| Claim | Where | Status |
|---|---|---|
| 18.95% of postings state an age limit, 17.47% an upper limit, 16.35% a lower limit | p. 105, Fig. 1a (p. 106) | verified in text |
| On all five sites, "under 35" is the most common upper limit | p. 105, Fig. 1b (p. 106) | verified in text and figure |
| Share of capped postings with "under 35": 51job 30.74%, Liepin 32.06%, Zhaopin 27.88% (2016–2021); 28.06%, 31.64%, 27.09% (2022–2024) | p. 106 | verified in text; the shares for BOSS Zhipin, 58.com and "all" are not printed in the text, only shown as bars |
| Mean outcome just under 35: 0.3970%; just over: 0.5066% (raw difference 0.1096) | Table 1, p. 108 | verified |
| RD jump at 35: 0.1403 (SE 0.0594), p < 0.05; with controls 0.1396 (0.0594); quadratic 0.1838 (0.0771), with controls 0.1811 (0.0771) | Table 2, pp. 109–110 | verified |
| "Just over 35" = 0.3970 + 0.1403 = 0.5373%, an increase of 35.34% | p. 109 | verified (the abstract rounds this to 0.40% → 0.54%) |
| Fig. 2 plots binned residualised outcomes with fitted lines and 95% CIs; a jump at 0 in all four panels | Fig. 2, p. 111 | seen (image). Not redrawn: there are no printed bin values. |
| No manipulation at 35 (density test T = 1.006, p = 0.315); covariate means and SDs mostly continuous. Married, household size and rooms show some jumps; adding them barely changes the estimate. | pp. 111–112, Table 3; footnote p. 112 | verified in text (the density figure 附图 A2 and Table A2 are appendix-only) |
| Placebo: no significant jump at other ages from 21 to 49. No jump at 25 or 30 for the same birth cohorts in the 2005/2010 censuses. No jump in other non-work reasons (own reasons, housework, study, disability, retirement, etc.). | p. 113 | verified in text (tables in the appendix) |
| Robustness: other bandwidths (30–50 / 50–70 months), triangular kernel, city FE or no FE, quarterly running variable, donut, excluding people unable or unwilling to work | p. 110 | described in text; results are in Appendix II, not read |
| Mechanism: in cities whose ads link the 35 cap to words for health, appearance, complaining or lack of ambition, or new technology, the jump is significant. Positive-stereotype words (reliable, communication, experience) go with no significant jump. No support for a pure "youth preference". | Table 4 (p. 114), Table 5 (pp. 115–116) | verified. City-level keyword correlation. The author notes city-level unobservables (footnote p. 115). |
| Heterogeneity: significant in cities with more 35 caps (0.2008); for high school or less (0.1675***), within that for men (0.2374**) and married men (0.2634***); not significant for college or more (−0.0569, SE 0.1854), women (0.0760) or the less-capped cities (0.0787) | Table 6, p. 117 | verified |
| Time: 2005 census 0.2570***; 2010 census 0.0607 (n.s.) | Table 6, p. 117 | verified |
| Whether the anchor at 35 comes from civil-service age limits: no direct evidence | p. 117 | verified (the author says so) |

**Limits relevant to AgeLens.**
- The outcome is a dismissal share among all working-age people. It is not an unemployment rate, and it is not about hiring.
- The absolute jump is small (0.14 percentage points) even though the relative change is about 35%.
- The effect is not significant for college graduates, who are a large part of AgeLens's intended users.
- The stereotype mechanism is a city-level correlation.
- The paper does not study job seekers reading ads.

**Pitch cross-check.**
- Design Pitch slide 1 cites "Fig. 2(a); Table 2(1)" for "+0.14 pp", which is consistent with Table 2 col. 1. Its scatter appears re-plotted from the figure (digitised; not verified here).
- Slide 2 redraws Fig. 1(b) with shares for all six groups (e.g. 24.3%, 26.8%, 20.7%). Only the 30.7 / 32.1 / 27.9 values are printed in the text. The others must have been read off the bars (digitised).

## 2. Feng, Lefgren, Liu, Platt, Xia (2026), NBER Working Paper 35709

- Title: "Signals, Steps, and Setbacks: Age Discrimination in a Laddered Labor Market". Authors confirmed in NBER page metadata AND on the PDF title page: Shuaizhang Feng (Jinan University), Lars Lefgren (BYU, NBER), Jieyi Liu (Jinan University), Brennan Platt (BYU), Xiaoyu Xia (University of Essex). September 2026; JEL J71; DOI 10.3386/w35709. The PDF states it has not been peer-reviewed (working paper).
- Accessed: `https://www.nber.org/papers/w35709` (HTTP 200) and full PDF `https://www.nber.org/system/files/working_papers/w35709/w35709.pdf` (43 pages; read with pdftotext, pages 24-25 rendered and looked at).
- Data/design (read in text, Section 3-4): large Chinese online recruitment platform. Postings: all full-time postings Aug-Sep 2022 requiring at least a 3-year college degree, 510,425 postings after exclusions. Applicants: 15,000 randomly selected job seekers aged 21-45 with bachelor's degrees in Guangdong, final 11,607 applicants and 333,705 applications (Jul-Sep 2022). 15% of postings state an upper age limit (mean 36.3); 35 is the most common (36% of limited postings). Entry-level = fewer than 3 years' experience required; managerial = 3 or more.
- Design: regression discontinuity in applicant age (months) relative to the posted maximum age (MSE-optimal bandwidths 28/24/53 months).

| Claim | Where | Status |
|---|---|---|
| Applications drop at the posted age limit: theta = -0.161 (SE 0.043, p=0.000), pre-limit mean 0.949; text: "a 17 percent decline" | Fig 1a, Sec 4.1 | verified-in-text and in figure |
| Positive responses (callbacks): theta = -0.062 (SE 0.025, p=0.012), pre mean 0.323; text: "nearly 20 percent" | Fig 1b | verified |
| Application-level positive-response rate: theta = -0.050 (SE 0.021, p=0.018), pre mean 0.365; text: about 5 pp, "13.7 percent decline" | Fig 1c | verified |
| Text writes "0.00161 fewer applications"; Figure shows -0.161 because the outcome is multiplied by 100 (figure notes) | Sec 4.1 vs Fig 1 notes | consistent, noted |
| Firms without stated limits show a similar age decline in response rates (descriptive) | Fig 2a | verified-in-text (descriptive only) |
| Entry-level response rates fall faster with age than managerial ones; eta3 = -0.006 (SE 0.001) | Fig 2c, Eq 7 | verified-in-text |
| Both directions: older disadvantaged at entry level; younger less likely hired into managerial roles | abstract; Fig 2c | abstract plus supportive figure; the separate younger-applicant managerial result was not individually traced |
| Older applicants to entry-level jobs negatively selected (prior wage proxy) | Fig 3, Sec 4.3 | verified-in-text (qualitative) |

Limits stated by the paper itself: callback-rate differences may partly reflect selection because applicants above the limit stop applying (Sec 4.1); platform data from one province for applicants; the relation to AgeLens is only that stated age limits are binding in this setting.

## Figures in the site

- `frontend/figures/feng2026_fig1_redrawn.svg`: redrawn by the AgeLens team from Feng et al. (2026) Figure 1. NO digitisation: bars use only the printed theta and pre-limit mean (index 100 vs (mean+theta)/mean x 100 = 83.0, 80.8, 86.3). Confidence intervals and individual dots of the original are not reproduced. The "just above" level is an AgeLens computation, flagged as such in the figure.
- `frontend/figures/lin2025_redrawn.svg` (added 2026-10-28): redrawn by the AgeLens team from Lin (2025). NO digitisation; only values printed in the text are used.
  - Panel (a): share of capped postings with an "under 35" limit, for the three sites whose values are printed on p. 106 (2016–2021 and 2022–2024).
  - Panel (b): 0.3970% (Table 1, col. 1) vs 0.3970 + 0.1403 = 0.5373% (Table 2, col. 1; the sum is stated by the author on p. 109), with the SE 0.0594.
  - Not reproduced: Fig. 1's other sites and ages, and Fig. 2's binned points and confidence bands.

## 3. Three further papers (added 2026-10-29; full notes in `docs/lit_notes/`)

All three were read in full as working papers, not as the journal text. No journal volume, page or DOI is cited because none was verified.

- **Neumark, Burn, Button (2019)**, NBER Working Paper 21669 (revised November 2017). US resume correspondence study, 40,223 applications, four occupations. Callbacks fall with applicant age, with stronger and more robust evidence of age discrimination against women than against men. Limits: US only; callbacks, not hires; no ad text; not China. Notes: `docs/lit_notes/neumark_2019.md`.
- **Burn, Firoozi, Ladd, Neumark (2022)**, "Help Really Wanted? The Impact of Age Stereotypes in Job Ads on Applications from Older Workers", NBER Working Paper 30287. Randomised artificial ads for three occupations: ageist wording lowers the average age of applicants and the share over 40 (any-treatment estimate: 2.7 years and 9.4 points). Limits: measures who applies, not who is hired. **Correction:** the team's draft cited Burn, Button, Munguia Corella, Neumark for "age-stereotyped ads affect application behaviour". That paper (NBER Working Paper 26552, "Older Workers Need Not Apply?") links ad wording to employer callbacks, not to who applies. Use WP 30287 for application behaviour and mention WP 26552 only as callback evidence. Notes: `docs/lit_notes/burn_2022.md`.
- **Belot, Kircher, Muller (2019)**, IZA Discussion Paper 10068 (July 2016 version read). About 300 unemployed jobseekers in Edinburgh, lab experiment: an online tool suggesting related occupations broadened search and raised interviews (about 44% overall, only marginally significant; larger for narrow searchers unemployed longer, from a tiny base). No effect on offers or employment was shown. Nothing on age, China, ad wording or chatbots. Notes: `docs/lit_notes/belot_2019.md`.

With Feng et al. (2026) and Lin (2025) above, the five papers motivate the AgeLens approach but do not establish its effectiveness. None evaluates a clarification tool.

This literature shows why age thresholds matter. It is not an evaluation of AgeLens.
