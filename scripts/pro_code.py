#!/usr/bin/env python3
"""Pro codes (stage 1 of the paid plan: no money involved; backend/api_pro.py, docs/PRO.md). Stdlib only.

The list lives in the git-ignored file data/pro_codes.local.json (sha256, label, credits, expiry; never the code). Locally the
server reads that file directly; on a public host paste the `env` output into the AGELENS_PRO_CODES environment variable.
A new code is printed ONCE.

  python3 scripts/pro_code.py new --label "Teacher" --credits 5 --expires 2026-12-15
  python3 scripts/pro_code.py list
  python3 scripts/pro_code.py revoke pro_ab12cd
  python3 scripts/pro_code.py env
"""
import argparse, datetime, hashlib, json, re, secrets, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "data" / "pro_codes.local.json"
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def new_code():
    body = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return "PRO-%s-%s" % (body[:4], body[4:])


def sha(code):
    return hashlib.sha256(re.sub(r"\s+", "", code).upper().encode()).hexdigest()


def load(p):
    return json.loads(p.read_text()) if p.exists() else []


def save(p, items):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, ensure_ascii=False, indent=1) + "\n")
    p.chmod(0o600)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", type=Path, default=DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("--label", required=True); n.add_argument("--credits", type=int, default=5)
    n.add_argument("--expires", required=True, help="YYYY-MM-DD, last valid day (UTC)")
    sub.add_parser("list"); r = sub.add_parser("revoke"); r.add_argument("id"); sub.add_parser("env")
    a = ap.parse_args()
    items = load(a.file)
    if a.cmd == "new":
        datetime.date.fromisoformat(a.expires)
        if not 1 <= a.credits <= 1000:
            sys.exit("credits: 1-1000")
        if not 1 <= len(a.label) <= 60:
            sys.exit("label: 1-60 characters (a name for the code; no email or phone)")
        code = new_code()
        items.append({"id": "pro_" + secrets.token_hex(3), "label": a.label, "credits": a.credits, "expires": a.expires, "sha256": sha(code),
                      "created": datetime.date.today().isoformat()})
        save(a.file, items)
        print("New Pro code for %r (%d report credits, valid through %s):\n\n    %s\n" % (a.label, a.credits, a.expires, code))
        print("It is shown only now. Local server: active at once. Public host: paste `python3 scripts/pro_code.py env` into AGELENS_PRO_CODES.")
    elif a.cmd == "list":
        if not items: print("No Pro codes yet in %s" % a.file)
        for it in items:
            print("%-11s %3d credits  through %s  %s" % (it["id"], it["credits"], it["expires"], it["label"]))
    elif a.cmd == "revoke":
        keep = [it for it in items if it["id"] != a.id]
        if len(keep) == len(items): sys.exit("No code with id %s" % a.id)
        save(a.file, keep); print("Removed %s. On a public host paste the new `env` value into AGELENS_PRO_CODES." % a.id)
    elif a.cmd == "env":
        print(json.dumps([{k: it[k] for k in ("id", "label", "credits", "expires", "sha256")} for it in items], ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
