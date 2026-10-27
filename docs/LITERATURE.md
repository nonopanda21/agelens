# Literature verification record (agent L, round 2)

Accessed 2026-10-23 (US Central time). Fetched content was treated as untrusted data.

## 1. Lin (2025), 经济学（季刊） / China Economic Quarterly

- Citation as given: 林文炼 (Lin Wenlian), 《年龄歧视导致了失业：一个断点回归设计》, 经济学（季刊）2025, 25(1): 103-120, DOI 10.13821/j.cnki.ceq.2025.01.07. Affiliation on CNKI: 中山大学商学院.
- Accessed:
  - `https://doi.org/10.13821/j.cnki.ceq.2025.01.07` -> 302 to `chndoi.org/Resolution/Handler?doi=...`: DOI is registered (title, author, registered 2025-02-19). Resolution lists link.cnki.net and link.oversea.cnki.net.
  - `link.cnki.net` not reachable from this machine (timeout / HTTP 418). `link.oversea.cnki.net` redirected to the CNKI overseas abstract page (HTTP 200): title, author, abstract (Chinese), keywords (年龄歧视; 35岁失业; 断点回归), table of contents, pages 103-120.
  - Full text (PDF/CAJ/HTML) needs a CNKI download/login; NOT accessed. A web search surfaced a PKU-hosted PDF (`nsd.pku.edu.cn/pub/chnsd/docs/20250227142400481236.pdf`, reportedly an appendix) but it returned HTTP 404.
- Abstract (Chinese, CNKI), paraphrased: design is a regression discontinuity around the 35-year age limit that firms use in recruiting; data are from the 2015 population census (abstract wording); controlling for productivity factors, respondents just over 35 who were unemployed "due to their employer" rise from 0.40% to 0.54%; the main reason is employers' negative age stereotypes; anchoring effect between age discrimination and hiring decisions; heterogeneity by region, individual and time.
- Table of contents (CNKI): 基准回归, 图形分析, 稳健性检验, 连续性条件检验, 安慰剂检验, 机制检验, 拓展检验. Figure numbers and plotted values were NOT seen.

| Claim | Status |
|---|---|
| Title, author, journal, volume/issue/pages, DOI | verified (CNKI/CNDOI metadata) |
| RD at age 35, 2015 census data | abstract-only |
| Unemployed-due-to-employer share 0.40% -> 0.54% just over 35 | abstract-only (exact definition of the outcome, sample, bandwidth, SEs NOT verified) |
| Mechanism (negative age stereotypes), anchoring, heterogeneity | abstract-only |
| Any figure/table | NOT verified; no figure is drawn |

Who should check: a team member with CNKI access (university library) must read the full text and confirm the sample (census vs 1% sample survey), outcome definition, estimate, and the figure number to redraw.

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
- Lin (2025): no figure; card shows a "To be verified" state.

This literature shows why age thresholds matter. It is not an evaluation of AgeLens.
