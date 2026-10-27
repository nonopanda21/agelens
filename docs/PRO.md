# AgeLens Pro: stage 1 (no payment)

Status 2026-10-27: implemented and tested locally. On the public demo it works once `AGELENS_PRO_CODES` is set on the host. No money is involved, and no AI model is called.

## Free and Pro

| Feature | Free | Pro |
|---|---|---|
| Overview, data explorer, map, original ad text, Quick check | ✓ | ✓ |
| Job Seeker answer on the page and its Markdown download; Ask a human reviewer | ✓ | ✓ |
| Full report **preview**: the 10 section titles and the summary numbers | ✓ | ✓ |
| **Full Word report** | — | ✓, one credit each |

The report (`backend/report.py`, `report-v1`) is a Word file of about 4–8 pages. It is built from the same request as the Job Seeker answer, by the same rules and with no model, so the same request always gives the same report. Its contents:
- the cover: your question, the background you entered, the data label and the disclaimer;
- the summary numbers;
- the five answer sections, each with the ads' own wording quoted;
- a comparison of your region and occupation with the whole simulated dataset;
- the questions to send, plus an editable draft message;
- an evidence appendix listing every ad and its age wording, quoted verbatim;
- method and limits.

It never says whether someone qualifies, never predicts an outcome and never calls a practice illegal. A unit test checks this.

## How it works
- **Pro codes.** Codes look like `PRO-XXXX-XXXX` and are made with `scripts/pro_code.py`.
  - The list holds only sha256 hashes, plus a label, the credits and an expiry date.
  - Locally the server reads `data/pro_codes.local.json`, which is git-ignored.
  - On a host it reads the environment variable `AGELENS_PRO_CODES`, which holds the output of `pro_code.py env`.
- **Credits belong to the code.** Every browser that enters the same code shares them. The browser keeps a Pro session token (header `X-Pro-Token`; only its hash is stored), never the code.
- **The server decides.** `POST /api/report`:
  - returns 402 without Pro, and 403 when no credits are left;
  - takes the credit in the same database transaction that checks the balance, so four simultaneous clicks on the last credit give exactly one report (tested);
  - charges nothing for an empty or failed report.
- **Limits.**
  - Wrong codes: 10 per client per 5 minutes.
  - Report builds: 20 per minute in total.
  - Revoking a code (`pro_code.py revoke`, then update the environment variable) stops it at once.
- **Free host limitation.** On Render's free plan the disk is wiped at every restart, so the count of used credits starts again from zero. That is acceptable for a demo, but not for real payments (stage 2/3 need a persistent database; see the plan in the conversation log).

## Use
```bash
python3 scripts/pro_code.py new --label "Teacher" --credits 5 --expires 2026-12-15   # prints the code once
python3 scripts/pro_code.py list
python3 scripts/pro_code.py env        # value for AGELENS_PRO_CODES on Render (Environment → add → Save)
```

## Verified
- `tests/test_pro.py`, 16 tests:
  - the preview is free, the report needs Pro, and free features are unaffected;
  - redeem and status work; wrong and expired codes get the same answer; wrong codes are rate-limited; revocation, sign-out and hash-only storage work;
  - one credit is taken per report, credits are shared across browsers and run out, an empty report costs nothing, and the last credit cannot be spent twice (4 concurrent requests);
  - the report's sections, data labels and verbatim quotes are present, it contains no outcome or legal claims, and it is deterministic.
- `tests/browser/pro_flow.py`, 27/27 at 1280 and 360 px: preview → wrong code → code → two Word downloads (verified as .docx) → credits 2 → 1 → 0 → button disabled → wallet shown on the Pro page → Pro removed from the browser.
- The report was rendered to PDF with LibreOffice and checked by eye (7 pages for 10 ads).
