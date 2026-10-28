#!/usr/bin/env bash
# Run before `git push`: if this passes, what Render will build has been rehearsed here.
#   bash scripts/check_before_push.sh          # everything (about 10 minutes)
#   bash scripts/check_before_push.sh --quick  # unit tests + Render rehearsal only (about 2 minutes)
# Stops at the first failure and says "DO NOT PUSH". Starts its own servers on 127.0.0.1 only and stops them again;
# it never touches the main database or the server on port 8765.
set -u
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PW=~/agelens-tools/pw/bin/python
QUICK=${1:-}
fail() { echo; echo "✗ $1"; echo "DO NOT PUSH until this is fixed."; exit 1; }
step() { echo; echo "== $1"; }

step "1/4 nothing sensitive is tracked by git"
bad=$(git ls-files | grep -E '\.db($|-)|reviewer_token$|study_token$|invites\.local\.json$|pro_codes\.local\.json$|server\.log$|^data/uploads/|^\.venv/|^\.claude/' || true)
[ -z "$bad" ] || fail "tracked files that must not be published: $bad"
echo "ok"

step "2/4 unit tests"
.venv/bin/python -m unittest discover -s tests 2>&1 | tail -3 | grep -q "^OK" || fail "unit tests failed (run: .venv/bin/python -m unittest discover -s tests)"
echo "ok"

step "3/4 Render rehearsal: committed files only, fresh venv, python app.py --public"
TMP=$(mktemp -d); trap 'kill $SRV 2>/dev/null; rm -rf "$TMP"' EXIT
git ls-files -z | rsync -a --from0 --files-from=- ./ "$TMP/app/" || fail "could not copy the committed files"
if ! git diff --quiet || ! git diff --cached --quiet; then echo "note: uncommitted changes are NOT in this rehearsal (commit first to include them)"; fi
python3 -m venv "$TMP/app/.venv" >/dev/null && "$TMP/app/.venv/bin/pip" install -q -r "$TMP/app/requirements.txt" >/dev/null 2>&1 || fail "pip install -r requirements.txt failed in a fresh venv"
PORT=8890
(cd "$TMP/app" && env -u AGELENS_INVITES -u AGELENS_REVIEWER_TOKEN -u AGELENS_STUDY_TOKEN -u AGELENS_PRO_CODES AGELENS_DB="$TMP/r.db" PORT=$PORT \
  .venv/bin/python app.py --public --host 127.0.0.1 > "$TMP/server.log" 2>&1) &
SRV=$!
for _ in $(seq 1 60); do curl -s -o /dev/null "http://127.0.0.1:$PORT/api/health" && break; sleep 0.5; done
curl -s "http://127.0.0.1:$PORT/api/health" | grep -q '"ads": 960' || { tail -5 "$TMP/server.log"; fail "the public server did not start or did not rebuild the 960 simulated ads"; }
[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/")" = 200 ] || fail "home page not served"
[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/overview")" = 200 ] || fail "open demo: /api/overview should be 200"
[ "$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' "http://127.0.0.1:$PORT/api/report")" = 402 ] || fail "/api/report without Pro should be 402"
[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/reviewer/requests")" = 401 ] || fail "reviewer API should be closed"
curl -s -D - -o /dev/null "http://127.0.0.1:$PORT/" | grep -qi "x-robots-tag: noindex" || fail "public headers missing"
kill $SRV 2>/dev/null; wait $SRV 2>/dev/null
echo "ok (started, rebuilt 960 ads, open demo, Pro locked, reviewer closed, headers present)"

if [ "$QUICK" = "--quick" ]; then echo; echo "✓ quick checks passed. For the full set, run without --quick."; exit 0; fi

step "4/4 browser checks (own servers on 127.0.0.1)"
[ -x "$PW" ] || fail "Playwright environment not found at $PW"
for t in sweep public_demo pro_flow; do
  printf "%-12s " "$t"; out=$(timeout 900 "$PW" "tests/browser/$t.py" 2>&1 | tail -1); echo "$out"
  echo "$out" | grep -qE "^([0-9]+)/\1 checks passed" || fail "$t failed (run: $PW tests/browser/$t.py)"
done
printf "%-12s " "a11y_check"; out=$(timeout 900 "$PW" tests/browser/a11y_check.py http://127.0.0.1:8765 2>&1 | grep "high-severity"); echo "$out"
echo "$out" | grep -q "findings: 0" || fail "accessibility check found high-severity problems"

echo; echo "✓ all checks passed: safe to git push."
