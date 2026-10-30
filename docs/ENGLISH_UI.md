# English-only UI

Requirement: the website shows **no Chinese characters anywhere**. That covers visible text and the `title`, `aria-label`,
`placeholder` and `alt` attributes. Until round 5, Chinese appeared on purpose as quoted evidence (`.orig`, `.ex-snip`,
`.ex-ad-t`, `.ev-title`, `.rq-ev-title`, `.st-adtext`, `mark.age`, `.zh-orig`, `lang="zh*"`), and the browser tests allowed it
there. That exception is gone. The Chinese text stays in the data. The rules read it, and filters still send the Chinese
values to the API. Only what is rendered is English.

## How the frontend gets English

The backend adds English display fields (see the contract in the backend agent's `docs/ENGLISH.md` / `backend/gloss.py`).
The frontend reads them through `AgeLens.labels` (`frontend/js/labels.js`), and each helper has a fallback that is English too:

| Helper | Reads | Fallback when the field is missing |
|---|---|---|
| `termGloss(t)` | `gloss_en` | rules-based sentence from `kind` / `min_age` / `max_age` ("Maximum age 35; may be relaxed for some candidates (the ad does not say how)") |
| `exception(t)` | `exception_en` | "Exceptions are possible; the ad does not say who decides or how" (only when `exception_text` exists) |
| `adTitle(ad)` | `title_en` | "<English occupation> job ad", else "Job ad <id>" |
| `company(ad)` / `city(ad)` | `company_en` / `city_en` | left out (evidence page: "Fictional company (name not shown in English)") |
| `place(ad)` | `city_en` + translated province | province only |
| `ageLine(ad)` | `age_sentence_en` | `termGloss` of the first term |
| `quote(st)` | `quote_en` | "Original wording not shown" |
| `occ` / `prov` / `source` | lookup maps | "Other occupation" / "Unlisted region" / "Imported source", never the Chinese value |
| `orig()` | (none) | always `null`: originals are no longer shown |

Safety net: `AgeLens.h` (frontend/js/app.js) passes every text child and every `title` / `aria-label` / `placeholder` /
`alt` value through `AgeLens.noCJK`. Any Chinese that still gets through, such as a backend sentence like "contradicts itself (“…”)",
becomes "[original wording not shown]". Each such case is logged in `AgeLens.scrubLog`, which `sweep.py` and `no_cjk_crawl.py`
print, so a missing English field shows up in the tests instead of on screen. Input and textarea values are never changed.

## What changed, page by page

- **Evidence** (`pages/evidence.js`): the title is `title_en`. "The ad in English" shows `description_en` with `age_sentence_en` highlighted as `mark.age`.
  Without `description_en`, a note says the English text is not available yet. Conditions show "In plain English" (`gloss_en`) and "Exception" (`exception_en`), and no Chinese
  snippet. The raw source row is no longer listed. A line says it is kept on the server in its original language (its field names are Chinese too).
  Company, location and source are English only.
- **Explore** (`pages/explore.js`): list titles use `title_en`, and the snippet uses `age_sentence_en` or `gloss_en`. The meta line is English (company only if `company_en`).
- **Job Seeker** (`pages/seeker.js`): statement quotes use `quote_en`, or a muted "Original wording not shown" line. Cards use `title_en` and the English age line.
  The selected-evidence list in the review panel uses `title_en`. Pasted-ad notes use `truncated_en` / `conflict_en`, or a count ("2 conflicting passages").
  Injected instruction lines in Chinese are counted, not quoted. The pasted text is not echoed back. Demo-case notes and questions are English.
  The three paste demo ads are Chinese because the rules read Chinese. They are loaded behind the textarea, not typed into it, and the placeholder says a fictional Chinese
  ad is loaded. The title search box shows the English word (for example "Procurement") and maps it to the Chinese title word internally. The paste placeholder is English.
- **My requests / Reviewer** (`pages/requests.js`, `pages/reviewer.js`): evidence snapshots show `title_en`, `description_en` with `age_sentence_en`
  highlighted, and `gloss_en` per term. Snapshots stored before the English fields existed show "Original wording not shown: this ad was saved
  without an English version", followed by the rules-based gloss.
- **Study / Score** (`pages/study.js`, used by `score.js`): the ad shows `ad_text_en`. Until a task has it, the study team's English `gloss` stands in.
  The job title is `job_title_en`. The rater sees English.
- **Quick check** (`js/sidekit.js`): the chips have English labels ("Under 35, up to 40 for strong candidates", "Under 35 preferred", "Age 25 to 40").
  *Choice and reason:* the rules read Chinese wording, so a working example has to be a Chinese line. A click sends that line to the checker
  directly and does not put it in the input box. The page never shows Chinese, and the result is labelled "Example: <English label>".
  Text the user types or pastes still goes through the box as usual. The result shows `gloss_en` (fallback: rules-based gloss) and `exception_en`. It never shows the quote.
- **Home motivation** (`pages/home_motivation.js`): the ad clipping now quotes the English line ("Under 35; may be relaxed for outstanding
  candidates.") as the ad excerpt, captioned as a translation. Copy that promised "quotes the age wording exactly as written" (home "how",
  motivation decision 1, Job Seeker submit hint) now says the age sentence is shown whole, in English.
- **About** (`pages/about.js`): "Zhaopin" only. The Chinese journal and author names were removed, and the synthetic-data paragraph explains that ads are shown in English.
- Figures (`frontend/figures/*.svg`), `home_literature.js`, `access.js`, `pro.js`, the home sections and `js/mapcore.js` had no visible Chinese.

## What remains in the source, and why

Chinese literals remain in the JS source only as **lookup keys** that are never rendered: the occupation and source maps in `labels.js`
and `home_marquee.js`, the `'其他'` ("Other") key in `app.js` / `mapcore.js`, the province `<option value>` of the demo cases, the three Quick
check example lines (stored as `\u` escapes), and the paste demo ads in `seeker.js`. They must match the Chinese data and the rules.

## Tests

- `tests/browser/sweep.py`: zero CJK in any text node (visible or hidden) or in title / aria-label / placeholder / alt, on every route at 1280
  and 360 px. It also checks that the downloaded Markdown brief has no CJK, and prints the safety-net log.
- `tests/browser/labels_check.py`: the evidence allowance was removed.
- `tests/browser/no_cjk_crawl.py` (new): every route at 1280 and 390 px, one evidence page, one request, a Job Seeker search, all six demo
  cases and the three Quick check examples. Counts CJK in `document.body.innerText`, `document.title` and the four attributes.
- `demo_cases.py` checks no CJK on the page for each case. `seeker_flow.py` records `md_cjk_chars` / `answer_cjk` / `evidence_cjk`. `map_v2.py`
  dropped its `lang="zh"` skip. `study_flow.py` no longer assumes a multi-line Chinese ad.
