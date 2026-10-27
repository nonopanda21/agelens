#!/usr/bin/env python3
"""Invite codes for the public demo (backend/api_access.py, docs/DEPLOY.md). Stdlib only.

The list of codes lives in a LOCAL file (default data/invites.local.json, git-ignored) and is pasted into the host's
AGELENS_INVITES environment variable. The local file stores each code's sha256, label, role and limits, never the code:
a new code is printed ONCE, so copy it then.

  python3 scripts/invite.py new --role viewer --label "Teacher" --personal --expires 2026-12-15 --uses 1
  python3 scripts/invite.py new --role viewer --label "SEPOL class" --expires 2026-12-15 --uses 60      # shared code
  python3 scripts/invite.py new --role reviewer --label "Team reviewer A" --personal --expires 2026-12-15
  python3 scripts/invite.py list
  python3 scripts/invite.py revoke inv_k3x9          # then paste the new value and redeploy: its sessions stop at once
  python3 scripts/invite.py env                      # prints the AGELENS_INVITES value to paste
  python3 scripts/invite.py secrets                  # prints fresh random values for AGELENS_REVIEWER_TOKEN / _STUDY_TOKEN
"""
import argparse, datetime, hashlib, json, re, secrets, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "data" / "invites.local.json"
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L


def new_code():
    body = "".join(secrets.choice(ALPHABET) for _ in range(8))  # 31^8 ≈ 8.5e11 combinations, plus rate limiting
    return "AL-%s-%s" % (body[:4], body[4:])


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
    n = sub.add_parser("new"); n.add_argument("--role", choices=("viewer", "reviewer"), required=True); n.add_argument("--label", required=True)
    n.add_argument("--personal", action="store_true", help="one person; requests are kept on the code")
    n.add_argument("--expires", required=True, help="YYYY-MM-DD, last valid day (UTC)"); n.add_argument("--uses", type=int, default=0, help="max redemptions (0 = no limit)")
    sub.add_parser("list"); r = sub.add_parser("revoke"); r.add_argument("id"); sub.add_parser("env"); sub.add_parser("secrets")
    a = ap.parse_args()
    if a.cmd == "secrets":
        print("AGELENS_REVIEWER_TOKEN=" + secrets.token_urlsafe(24)); print("AGELENS_STUDY_TOKEN=" + secrets.token_urlsafe(24))
        print("(paste into the host's environment settings; do not commit them)"); return
    items = load(a.file)
    if a.cmd == "new":
        datetime.date.fromisoformat(a.expires)
        if not 1 <= len(a.label) <= 60:
            sys.exit("label: 1-60 characters (a name for the code, e.g. 'Teacher' or 'SEPOL class'; no email or phone)")
        code = new_code()
        entry = {"id": "inv_" + secrets.token_hex(3), "role": a.role, "label": a.label, "personal": a.personal, "expires": a.expires,
                 "max_uses": a.uses, "sha256": sha(code), "created": datetime.date.today().isoformat()}
        items.append(entry); save(a.file, items)
        print("New %s code for %r (%s, valid through %s%s):\n\n    %s\n" % (a.role, a.label, "personal" if a.personal else "shared", a.expires,
              ", max %d uses" % a.uses if a.uses else "", code))
        print("It is shown only now. Then run `python3 scripts/invite.py env` and paste the value into AGELENS_INVITES on the host.")
    elif a.cmd == "list":
        if not items: print("No codes yet in %s" % a.file)
        for it in items:
            print("%-11s %-8s %-8s through %s  uses<=%s  %s" % (it["id"], it["role"], "personal" if it["personal"] else "shared", it["expires"], it["max_uses"] or "∞", it["label"]))
    elif a.cmd == "revoke":
        keep = [it for it in items if it["id"] != a.id]
        if len(keep) == len(items): sys.exit("No code with id %s" % a.id)
        save(a.file, keep); print("Removed %s. Paste the new `env` value into AGELENS_INVITES and redeploy; its sessions stop at once." % a.id)
    elif a.cmd == "env":
        print(json.dumps([{k: it[k] for k in ("id", "role", "label", "personal", "expires", "max_uses", "sha256")} for it in items], ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
