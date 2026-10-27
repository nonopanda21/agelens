# Deploying the AgeLens public demo (invite codes, Render)

Status 2026-10-27: everything below up to step 3 is prepared and rehearsed locally (see "What was verified"). **Steps 1–6 need a team member**, because they create accounts and publish under your name. Nothing has been published yet.

## Two ways to run it (chosen by one environment variable)

| | open demo (default of `render.yaml`) | invite-only demo |
|---|---|---|
| set on the host | nothing | `AGELENS_INVITES` (from `scripts/invite.py env`) |
| who gets in | anyone with the link | only people with a code |
| reviewer / study desks | closed: a random token nobody knows is generated at each start (set `AGELENS_REVIEWER_TOKEN` / `AGELENS_STUDY_TOKEN` to open them) | reviewer codes open the reviewer workspace |

Pro codes (full Word report, `docs/PRO.md`): add `AGELENS_PRO_CODES` (output of `python3 scripts/pro_code.py env`) the same way. Without it, the report preview still works, but no code unlocks the report.

Switching from open to invite-only later: Render → the service → **Environment** → add `AGELENS_INVITES` → **Save**. Render restarts the service and the invite page appears. No code change is needed.

## What the public demo is

- `python app.py --public` serves the same app, with these differences from local use:
  - **every API call needs an invite code**;
  - there is no sign-up and no email;
  - secrets come only from environment variables;
  - an empty database is rebuilt from the seeded simulated dataset (960 fictional ads, all labelled "Demo · Synthetic data").
- **It refuses to start** if `AGELENS_INVITES` is set but malformed, or a token is set but shorter than 16 characters.
- **Headers:** responses carry `X-Robots-Tag: noindex`, HSTS, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`.
- **Turned off:** the diagnostics endpoint.
- **Study tools:** they stay in simulation mode. Formal mode is refused without `data/study/APPROVAL.json`, and no real participant data may be collected on the demo before teacher approval.
- **Invite codes** (`backend/api_access.py`, `scripts/invite.py`):

| Kind | For | Requests sent with it |
|---|---|---|
| personal viewer | one person, e.g. the teacher | kept on the code: the same code opens them in any browser |
| shared viewer | a group, e.g. the class | kept only in the submitting browser (people sharing a code never see each other's requests) |
| personal reviewer | a team reviewer | as personal, plus the reviewer workspace (no shared token needed) |

- **How codes are stored and revoked:**
  - Codes look like `AL-7KQ4-M9TX`.
  - Only their sha256 is stored. A new code is printed once, when you create it.
  - Expiry is checked on every request.
  - To revoke a code, remove it and redeploy. Its sessions stop immediately.
  - Wrong codes are rate-limited per client and overall.

## Free plan limits (state them if asked)

- **The instance sleeps** after about 15 minutes without visits. The next visit waits roughly 30–60 seconds while it wakes.
- **No persistent disk.** Every restart or redeploy resets the database to the simulated dataset. Requests, reviewer replies, sessions and the use counters of codes with a use limit are then lost.
  - Visitors simply enter their code again.
  - A paid instance with a disk would keep this data. That is a purchase, so it is the team's decision; AgeLens never buys anything.
- The server is Python's standard `ThreadingHTTPServer` behind Render's HTTPS proxy. That is fine for a class demo, not for heavy traffic.

## Steps for the team

### 1. Put the code on GitHub (once)
In a terminal on the machine with the project:
```bash
cd ~/agelens
git init
git config user.name  "<your name>"        # you set these; AgeLens tools never fill them in
git config user.email "<your email>"
git add -A
git status                                   # check: no data/*.db, no data/reviewer_token, no data/study/study_token, no .venv
git commit -m "AgeLens course demo"
```
- Create an **empty private repository** on github.com, for example `agelens-demo`, with no README.
- Then:
```bash
git remote add origin https://github.com/<you>/agelens-demo.git
git branch -M main
git push -u origin main                      # GitHub asks you to sign in (browser or a personal access token)
```
- `.gitignore` already excludes the databases, tokens, logs, uploads, the local invite list, the scheduler's run records and `.claude/`.
- The repository is about 110 MB, mostly `docs/screenshots/`.

### 2. (invite-only demo only) Make the secrets and the first codes (locally); skip for the open demo
```bash
python3 scripts/invite.py secrets            # two random values: keep them for step 3, do not commit them
python3 scripts/invite.py new --role viewer   --label "Teacher"         --personal --expires 2026-12-15
python3 scripts/invite.py new --role viewer   --label "SEPOL class"     --expires 2026-12-15 --uses 80
python3 scripts/invite.py new --role reviewer --label "Team reviewer A" --personal --expires 2026-12-15
python3 scripts/invite.py env                # the value for AGELENS_INVITES (hashes only)
```
- Each `new` prints the code **once**. Copy it straight into your message to that person.
- The list of hashes is kept in `data/invites.local.json`, which is git-ignored.

### 3. Create the service on Render
1. Sign up at render.com with GitHub, and allow it to see the `agelens-demo` repository.
2. **New → Blueprint**, then pick the repository. Render reads `render.yaml`, which sets the free plan, Ohio region, Python 3.12.3, `pip install -r requirements.txt`, `python app.py --public` and health check `/api/health`.
3. For the open demo, Render asks for nothing. For the invite-only demo, add these under **Environment**:
   - `AGELENS_INVITES`: the output of `invite.py env`;
   - `AGELENS_REVIEWER_TOKEN` and `AGELENS_STUDY_TOKEN`: the two values from `invite.py secrets`.
4. **Apply.** The first build takes a few minutes. The log should end with `Imported batch 1: … 960 unique ads` and `AgeLens running at http://0.0.0.0:10000`.

### 4. Check it
- Open `https://agelens-demo.onrender.com` (Render shows the exact address). You should see the invite page.
- Enter the teacher code. The overview should show "Teacher · viewer" at the right of the nav.
- Try Explore, Quick check and a Job Seeker answer.
- Enter the reviewer code in a private window. The Reviewer link should appear.

### 5. Send the codes
- **One personal message per person,** with the link and their code. For example:

  > AgeLens course demo: https://agelens-demo.onrender.com — invite code AL-XXXX-XXXX (valid until 15 Dec). All data is simulated; please do not enter real personal information. The first load can take up to a minute.

- **Do not post personal codes in group chats.** Use the shared code for groups.

### 6. Change or revoke codes later
```bash
python3 scripts/invite.py list
python3 scripts/invite.py revoke inv_xxxxxx
python3 scripts/invite.py env                # paste into AGELENS_INVITES on Render → Save → it redeploys
```

## Updating the site
`git add -A && git commit -m "…" && git push`. Render redeploys automatically (`autoDeploy: true`). On the free plan, the redeploy resets the demo data.

## Rehearse locally before pushing
```bash
~/agelens-tools/pw/bin/python tests/browser/public_demo.py     # own server on 127.0.0.1, fresh DB, test codes, 1280 + 360 px
.venv/bin/python -m unittest tests.test_access
```
To try it by hand, use `--host 127.0.0.1`. On a shared machine, never bind 0.0.0.0 by hand.
```bash
export AGELENS_INVITES="$(python3 scripts/invite.py env)" AGELENS_REVIEWER_TOKEN=... AGELENS_STUDY_TOKEN=... PORT=8870
AGELENS_DB=/tmp/agelens-public.db .venv/bin/python app.py --public --host 127.0.0.1
```

## What was verified (2026-10-27)

- **Clean copy:**
  - A copy containing only the files git would publish (440 files) was used, with a fresh virtual environment.
  - `pip install -r requirements.txt` installed the pinned `pypdf 6.21.2` and `python-docx 1.2.0`.
  - Without configuration, `app.py --public` refused to start and listed the three problems. With configuration, it rebuilt the database (960 ads) and served the site on 127.0.0.1.
  - Without a code, `/api/overview` returned 401 with `invite_required`. The security headers were present.
- **Tests:**
  - Unit tests in `tests/test_access.py` (16) cover the gate, the open paths, code normalisation, identical answers for wrong/expired/used-up codes, the per-client limit, sign-out, revocation, expired sessions, diagnostics being off, hash-only storage, viewer vs reviewer access, the study desk still needing its token, personal vs shared codes, the start-up configuration check, and local mode being unchanged.
  - Browser test `tests/browser/public_demo.py`: 33/33 at 1280 and 360 px.
- **Not verified:**
  - The Render build and start themselves (no Render account here).
  - Render's proxy headers. `X-Forwarded-For` is used for the per-client limit and is assumed to be set by Render.
  - Load or performance from outside.
