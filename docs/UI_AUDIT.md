# UI audit against the Web Interface Guidelines (task T04)

Date: 2026-10-24. Auditor: agent Q (QA + fixes). Rules: `docs/web-interface-guidelines.md` (Vercel Web Interface Guidelines).
Scope: `frontend/pages/*.js`, `frontend/js/*.js`, `frontend/css/*.css`, plus `frontend/index.html`.

## Method

- Read the page code against each rule group, with most attention on Accessibility, Focus and Forms.
- Ran a script in real Chromium (`tests/browser/a11y_check.py`, which starts its own server). It checks 12 route states at 1280 and 360 px: the home page, explore, the empty and filled seeker page, evidence, the requests list and detail, reviewer sign-in and detail, study, score and about. For each state it looks for:
  - interactive elements with no accessible name
  - `<img>` without alt, and `<svg>`/`<canvas>` that are neither hidden nor named
  - focusable elements inside `aria-hidden`
  - duplicate ids and ARIA references to ids that do not exist
  - text contrast below 4.5:1 (3:1 for large text), measured against solid and gradient backgrounds
  - keyboard: 150 Tab presses per state, checking for a visible focus ring and for keyboard traps
- Limits: the script is not axe-core, nothing was installed, and no screen reader was used. Gradient-filled text (`background-clip:text`) cannot be measured; the script counts it as "unknown" (5 elements on home).

Script results: **before the fixes, 8 high-severity findings** (2 unnamed inputs ×2 widths, 2 inputs with invisible focus ×2 widths, plus 1 broken `aria-describedby` ×2 widths that the first version of the script did not count). **After the fixes: 0.** Code reading found the other items below.

## Summary

| Severity | Found | Fixed | Not fixed |
|---|---|---|---|
| High | 6 | 6 | 0 |
| Medium | 8 | 2 | 6 (2 are in files the lead owns) |
| Low | 9 | 1 | 8 |

## High

| # | Where | Rule | Finding | Status |
|---|---|---|---|---|
| H1 | `frontend/pages/explore.js:74-81` | Form controls need a label or `aria-label` | The "Stated max age" from/to inputs had only a placeholder as their name. The two date inputs had no name at all, because the visible group `<label>` was not tied to any control. | **Fixed.** Each input now has an `aria-label`. Each pair is a `role="group"` labelled by its visible heading (`#ex-age-l`, `#ex-date-l`). |
| H2 | `frontend/css/base.css:60` | Interactive elements need visible focus | Date inputs showed no focus ring. Chromium puts focus on an internal sub-field, so `input:focus` does not match. | **Fixed.** Added a `:focus-within` ring for date and time inputs. |
| H3 | `frontend/pages/reviewer.js:29,43` + `frontend/js/app.js:7-11` | ARIA references must resolve | The reviewer token field's `aria-describedby="rvhelp"` pointed at an id that did not exist. `AgeLens.h('p.hint#rvhelp')` turned `hint#rvhelp` into a class name, so the help text was never read. | **Fixed** at the source: `AgeLens.h` now supports `tag.class#id`. |
| H4 | `frontend/pages/reviewer.js:72`, `frontend/pages/score.js:38` | Use semantic HTML before ARIA (ARIA misuse) | `role="tablist"`/`role="tab"` was used on filter buttons that have no tab panels, no `aria-controls` and no arrow-key handling. Screen readers announced tabs that do not work like tabs. | **Fixed.** They are now `role="group"` with `aria-pressed` buttons. The CSS selectors moved from `[aria-selected]` to `[aria-pressed]` (`reviewer.css:75,77`, `study.css:30`, `theme-x.css:97`), so the look is unchanged. |
| H5 | `frontend/pages/reviewer.js:99-112` | Focus management; Escape closes overlays | In the inline confirm (`alertdialog`), Cancel removed the focused button, so focus fell back to `<body>`. Escape did nothing, and the dialog's name was a generic "Confirm". | **Fixed.** Cancel and Escape return focus to the button that opened the confirm. The dialog is named after its action and described by its message. |
| H6 | `frontend/pages/reviewer.js:166-171` | Errors inline; focus the first error on submit | The "Review and publish" validation showed an error, but focus stayed on the button and the fields had no `aria-invalid`. | **Fixed.** Empty fields get `aria-invalid="true"`, and the first one receives focus. |

Checked and clean (0 findings in code and script): buttons without names; `<img>` without alt (the app has none); canvases (all `aria-hidden`, with text alternatives such as the map region table, the lens tab panels and the literature table, and the figure SVG has `role="img"` plus title/desc); focusable elements inside `aria-hidden` (the marquee clones use `tabindex=-1`); keyboard traps; text contrast below 4.5:1 on measurable backgrounds; skip link present; form errors on the seeker, requests and study pages already use `role="alert"` or `aria-live`.

## Medium

| # | Where | Rule | Finding | Status |
|---|---|---|---|---|
| M1 | `frontend/css/base.css:62-63` | Sticky headers must not cover the focused element | When tabbing backwards or jumping to a heading, the target could end up under the sticky header. | **Fixed:** `scroll-padding-top` (84 px, or 104 px on mobile). |
| M2 | `frontend/pages/score.js:66` | Focus the first error on submit | "Answer all four criteria" did not move focus. | **Fixed:** focus moves to the first unanswered criterion. |
| M3 | `frontend/pages/seeker.js:571` | Use `aria-live` for async updates, in proportion | `#answer` is a polite live region, so a screen reader may read the whole generated answer on every update. | Not fixed. Focus already moves to the answer heading, and removing the region could drop announcements. This needs a screen-reader test first. |
| M4 | `frontend/css/theme-x.css:91` | Focus indicator contrast | The 3 px focus outline on inputs is `rgba(37,99,235,.22)`, about 1.3:1. | Not fixed. The border also turns `#2563EB` (5.2:1 on white), and that change carries the focus indication. |
| M5 | `frontend/css/base.css:54` | Key entries clear on mobile | At 360 px the nav is one horizontally scrolling row. "My requests", "Reviewer" and the motion toggle start off-screen with no visual cue. | Not fixed. This is a design decision by the lead. The links are reachable by swipe and keyboard. |
| M6 | `frontend/js/charts.js:61,114` | Non-text contrast (WCAG 1.4.11) | The bar fill `#BFD2FA` on white/silver is about 1.5:1. | Not fixed. Every value is also printed as text and in `aria-label`s, and changing it would change the palette. |
| M7 | `frontend/pages/home_hero.js:13` (**for the lead**) | `<button>` for actions, `<a>` for navigation | "See how it works" is `<a href="#">`, with an onclick that scrolls. | Not fixed (the lead owns the file). Suggest `href="#lens"` or a `<button>`. |
| M8 | `frontend/css/home-x.css:8,49` (**for the lead**) | Text contrast | Gradient text (`.xgrad` headline line, `.xh-scroll-t` "SCROLL") cannot be measured by script. The light end of the gradient may fall below 3:1 on the light hero. | Not verified (lead-owned). Check by eye or sample pixels. The scroll cue itself has an accessible name. |

## Low

| # | Where | Rule | Finding | Status |
|---|---|---|---|---|
| L1 | `seeker.js:539,553,557`, `explore.js:70` | Placeholders end with `…` and show the pattern | Placeholders read "e.g. operations manager", "from", "to". | Not fixed (copy only). |
| L2 | `seeker.js` fields | Inputs need `autocomplete` and a meaningful `name` | Most fields have an id but no `name`, and only 3 set `autocomplete`. | Not fixed. There is no native form submit, and these are profile fields, not login fields. |
| L3 | `frontend/index.html` | `touch-action: manipulation`; `<meta name="theme-color">` | Both are missing. | Not fixed (cosmetic). |
| L4 | `about.js:24`, `home_literature.js:32,43` | Links | External links open a new tab with no indication. | Not fixed. |
| L5 | `seeker.js` (whole page) | URL reflects state | The seeker's question and results are not in the URL (Explore filters are). | Not fixed on purpose. A question containing age and background should not end up in URLs, history or logs. |
| L6 | `score.js:150` | Destructive actions need confirmation | Uses a blocking `confirm()`, unlike the inline confirm elsewhere. | Not fixed. It is acceptable, and it only applies to simulated data. |
| L7 | `seeker.css:53`, `base.css:21`, `theme-x.css:37` | Never `outline:none` without a replacement | These remove the outline on programmatic-focus targets (`main`, the answer heading, both `tabindex=-1`). | Not fixed on purpose. They are not interactive. |
| L8 | `charts.js:17`, `explore.js:5`, `mapcore.js:8` | Use `Intl.NumberFormat` | `toLocaleString('en-US')` is hard-coded. | Not fixed. It matches the all-English UI, and dates in `requests.js:21` already use the locale. |
| L9 | `frontend/css/study.css` (end) | Visual: spacing | The "DRAFT — awaiting approval" badge touched the consent heading. | **Fixed:** added a margin. |

## Related fixes made in the same QA pass (not guideline findings)

- `seeker.js`: the region menu, match reasons, card meta lines and evidence references are now in English through `AgeLens.labels`. The original Chinese stays as muted `.zh-orig` or `lang="zh-CN"` evidence text, and filters still send the original values. In `backend/brief.py`, "You said: … looking in 上海" now reads "looking in Shanghai".
- `about.js`: the Lin (2025) citation now uses the English journal name, with the original marked as `.zh-orig`. The privacy line said a CV "is not stored unless you choose to save it", which contradicted the actual behaviour (a CV is never stored). Corrected.
- Layout: the demo-case buttons are an even grid at 360 px. Explore's Apply/Reset sit side by side on their own row, and the date inputs are no longer clipped (a double-width cell on desktop, stacked on mobile). The Explore intro uses `p.lead`, with no visual change because the theme already styled it as a lead.
