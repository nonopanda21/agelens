# Heterogeneity in stated age and gender wording (Zhaopin ads, 2021-2024)

Describes **how advertisements are worded**. It does not show who was hired, who applied, or whether a stated limit was enforced.
Data: `data/real/hetero_zhaopin_2021-2024.json` (built by `scripts/real_hetero.py`), 10,058,826 ads; age rules `age-rules-2.1.0`, gender rules
`gender-rules-1.0.0`. Overall: explicit age requirement 24.6% (2,471,243), age cap 6.0% (605,073), any age wording 26.3%.

## Experience bands (source column 要求经验)
| Band | Source values | Ads | Share of ads |
|---|---|---|---|
| No experience required | 不限, 无经验, 无 | 3,193,773 | 31.8% |
| Under 1 year | 1年以下 | 231,969 | 2.3% |
| 1–3 years | 1-3年 | 3,065,816 | 30.5% |
| 3–5 years | 3-5年 | 1,848,041 | 18.4% |
| 5+ years | 5-10年, 10年以上 | 972,309 | 9.7% |
| Not stated | empty or any other value | 746,918 | 7.4% |

不限 ("not limited") and 无经验 ("no experience") both mean the ad asks for none, so they are one band. 10年以上 is under 1.5% of ads and is merged with 5-10年.

## 1. Age wording by required experience
| Band | Explicit age requirement | Age cap | Any age wording | Max age 35 | Max age 45 | Max age at most 35 |
|---|---|---|---|---|---|---|
| No experience required | 33.8% | 5.2% | 36.8% | 26.0% | 18.6% | 47.7% |
| Under 1 year | 25.3% | 5.7% | 27.3% | 31.2% | 12.9% | 56.3% |
| 1–3 years | 17.7% | 6.2% | 18.7% | 35.2% | 14.4% | 53.9% |
| 3–5 years | 15.5% | 6.8% | 16.2% | 30.8% | 21.3% | 37.8% |
| 5+ years | 18.0% | 8.1% | 18.8% | 14.6% | 34.0% | 16.0% |
| Not stated | 44.0% | 4.3% | 46.8% | 14.9% | 25.2% | 26.5% |

Max-age columns are shares of the ads that state a maximum age (each ad at its evidence max age; 2,409,770 ads in all). Reading: explicit age wording is most common in
ads asking for no experience (33.8%) and least common at 3–5 years (15.5%), but the **cap share rises with required experience**
(5.2% to 8.1%), and the typical maximum age moves up: the share of stated maxima at 35 or below falls from about half (47.7–56.3%) to 16.0% at 5+ years, where 45 is the most common
single limit (34.0%). "Not stated" experience looks like the no-experience group in its high explicit share (44.0%).

## 2. Occupation within bands (explicit age requirement share; occupations with at least 5,000 ads in the band; "Other" excluded)
| Band | Highest 5 | Lowest 5 |
|---|---|---|
| No experience required | Logistics & warehousing 54.0%, Manufacturing 50.2%, Customer service 43.6%, Sales 34.3%, Administration 32.6% | Education & training 11.5%, Finance 11.5%, Legal & compliance 11.5%, Engineering 10.4%, Design 9.4% |
| Under 1 year | Logistics & warehousing 37.6%, Customer service 34.2%, Manufacturing 33.5%, Sales 30.8%, Administration 26.0% | Marketing 14.9%, Education & training 12.5%, Finance 11.3%, Engineering 10.2%, Design 7.7% |
| 1–3 years | Customer service 25.6%, Sales 24.3%, Administration 23.4%, Logistics & warehousing 23.4%, Manufacturing 20.6% | Education & training 10.9%, Legal & compliance 10.0%, Data analysis 8.2%, Engineering 8.0%, Design 6.2% |
| 3–5 years | Administration 26.2%, Customer service 21.4%, Sales 20.6%, Logistics & warehousing 18.2%, Operations 17.4% | Legal & compliance 11.5%, Healthcare & nursing 11.0%, Engineering 7.8%, Design 6.1%, Data analysis 4.9% |
| 5+ years | Administration 28.0%, Sales 20.3%, Operations 20.1%, Finance 20.1%, Education & training 18.9% | Legal & compliance 14.2%, Healthcare & nursing 13.3%, Procurement 13.0%, Engineering 11.8%, Design 8.8% |
| Not stated | Logistics & warehousing 65.1%, Manufacturing 58.7%, Administration 46.2%, Customer service 44.9%, Human resources 34.8% | Healthcare & nursing 15.7%, Finance 14.3%, Engineering 12.6%, Education & training 9.5%, Design 8.8% |

The same ordering repeats in every band: operational and service occupations (logistics, manufacturing, customer service, sales, administration) at the top; design,
engineering and data work at the bottom. Caps (not shown here) are highest in administration at 3–5 and 5+ years (10.1% and 10.4%).
By province (`by_experience_province`), no-experience ads with an explicit age requirement range from 22.3% (Hainan) to 43.7% (Chongqing); at 5+ years from 11.5% (Shanghai) to 27.2% (Heilongjiang),
among provinces with at least 5,000 ads in the band.

## 3. Explicitly written gender requirements
| Class | Ads | Share |
|---|---|---|
| Male only | 1,047 | 0.010% |
| Female only | 1,556 | 0.015% |
| Male preferred | 3 | 0.00003% |
| Female preferred | 5 | 0.00005% |
| Conflict (both sexes in separate posts or contradictory) | 756 | 0.008% |
| "Either sex" wording (男女不限, 性别不限, ...) | 702,963 | 6.99% |
| No gender wording | 9,352,496 | 92.98% |

Explicit single-sex requirements are **rare in these platform ads**: about 2,600 of 10 million (0.026%), with 8 preferences. They are too few to compare occupations
(the largest share, female-only in administration, is 0.09% of that occupation's ads). The "either sex" statement is common and varies with the band: 11.7% of no-experience ads, 16.7% of experience-not-stated ads,
3.9% at 1–3 years, 2.1% at 5+ years; by occupation 14.7% in logistics, 12.6% in customer service, 10.9% in manufacturing, 1.2% in engineering. The platform may filter single-sex wording; this data cannot show whether it does.

## 4. Age wording by gender class
| Gender class | Ads | Explicit age requirement | Age cap | Any age wording |
|---|---|---|---|---|
| Male only | 1,047 | 76.7% | 28.0% | 81.6% |
| Female only | 1,556 | 63.0% | 19.2% | 65.7% |
| Either sex stated | 702,963 | 76.4% | 8.5% | 81.0% |
| Conflict | 756 | 75.0% | 13.5% | 84.5% |
| No gender wording | 9,352,496 | 20.7% | 5.8% | 22.2% |
Ads that write any gender wording also write age wording far more often (76-82% against 22%): the two kinds of wording co-occur (this does not say why). Among ads that restrict gender, the
age cap share is 28.0% (male only) and 19.2% (female only) against 5.8% with no gender wording. The gender classes with few ads (male/female preferred) are not reported as shares.

## Limits (all apply)
* **Platform ads, wording not outcomes.** Nothing here says who was hired or whether a stated limit was applied; the platform may moderate wording.
* **Ads repeat.** The same vacancy can be posted several times or in several cities, so counts are ads, not distinct jobs or employers.
* **Keyword rules for occupation.** Occupation is guessed from the job title only; 27.9% of ads are "Other" and excluded from rankings; cities are mapped to provinces by name lists.
* **Experience bands** merge source values (see the table above); the source column is as entered by the employer.
* **Gender rules**: one annotator, 415-ad gold set with only 24 restriction/preference items, final scores tuned on the gold errors (see `docs/GENDER_RULES.md`). Implicit signals (a single-sex height standard, 宝妈) are not counted; "either sex" includes heights listed for both sexes.
* **Age rules**: `age-rules-2.1.0`, one annotator on the age gold set (`docs/RULES_2_1_0.md`); graduate-cohort wording is not an age condition (645,871 ads carry it, reported separately as `cohort`).
* Differences between bands and occupations are descriptive and unadjusted: bands and occupations overlap (entry-level logistics ads are both).
