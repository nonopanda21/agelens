#!/usr/bin/env python3
"""AgeLens server.
  python3 app.py [--port 8765]   local mode: binds to 127.0.0.1 only, no invite gate (development, classroom demo).
  python3 app.py --public        public demo (docs/DEPLOY.md): binds 0.0.0.0 on $PORT, every API call needs an invite code,
                                 secrets come only from the environment, and an empty database is filled with the
                                 simulated dataset. Refuses to start if the configuration is incomplete."""
import argparse
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def free_port(start):
    for p in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    raise SystemExit("No free port found near %d" % start)


def prepare_public():
    os.environ["AGELENS_PUBLIC"] = "1"
    from backend import api_access, db  # imported after AGELENS_PUBLIC is set
    problems = api_access.check_config()
    if problems:
        raise SystemExit("Public mode refused:\n  - " + "\n  - ".join(problems))
    db.init_schema()
    with db.connect() as c:
        n = c.execute("SELECT COUNT(*) FROM ads").fetchone()[0]
    if n == 0:  # a fresh or wiped disk: rebuild the same reproducible simulated dataset (seeded, labelled is_demo=1)
        print("Empty database: importing the simulated dataset…", flush=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "import_csv.py"), "--source", "sim"], check=True, cwd=ROOT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--public", action="store_true", help="public demo with invite codes (see docs/DEPLOY.md)")
    ap.add_argument("--host", default=None, help="public mode only; default 0.0.0.0 (the host's proxy). Use 127.0.0.1 to rehearse locally")
    a = ap.parse_args()
    if a.public:
        prepare_public()
        from backend import server
        server.serve(a.host or "0.0.0.0", int(os.environ.get("PORT", a.port)))
    else:
        from backend import server
        server.serve("127.0.0.1", free_port(a.port))
