#!/usr/bin/env python3
"""Benchmark: free-text search with LIKE scan vs the FTS5 trigram index, on a temporary copy scaled up to N ads.
Usage: .venv/bin/python scripts/bench_search.py [N]   (never touches data/agelens.db; uses a temp file)."""
import os, random, shutil, sqlite3, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
tmp = Path(tempfile.mkdtemp(prefix="agelens_bench_")) / "b.db"
shutil.copy(ROOT / "data" / "agelens.db", tmp)
c = sqlite3.connect(tmp)
base = c.execute("SELECT batch_id, raw_id, title, description FROM ads").fetchall()
rnd = random.Random(7); rows = []
for i in range(N - len(base)):
    b = base[rnd.randrange(len(base))]; rows.append((f"bench_{i}", b[0], b[1], b[2], b[3] + f" #{i}"))
c.executemany("INSERT INTO ads(id,batch_id,raw_id,title,description,is_demo) VALUES (?,?,?,?,?,1)", rows); c.commit()
t0 = time.time()
c.execute("CREATE VIRTUAL TABLE ads_fts USING fts5(title, description, content='ads', content_rowid='rowid', tokenize='trigram')")
c.execute("INSERT INTO ads_fts(ads_fts) VALUES ('rebuild')"); c.commit(); build = time.time() - t0
def timeit(sql, args, k=5):
    best = 1e9
    for _ in range(k):
        t = time.perf_counter(); n = c.execute(sql, args).fetchone()[0]; best = min(best, time.perf_counter() - t)
    return best * 1000, n
print(f"ads: {c.execute('SELECT COUNT(*) FROM ads').fetchone()[0]:,}   index build: {build:.1f} s   db size: {os.path.getsize(tmp)/1e6:.0f} MB")
for q in ["35岁以下", "可适当放宽", "工作经验", "procurement"]:
    lm, ln = timeit("SELECT COUNT(*) FROM ads WHERE title LIKE ? OR description LIKE ?", (f"%{q}%", f"%{q}%"))
    fm, fn = timeit("SELECT COUNT(*) FROM ads WHERE rowid IN (SELECT rowid FROM ads_fts WHERE ads_fts MATCH ?)", (f'"{q}"',))
    print(f"{q:>12}: LIKE {lm:8.1f} ms ({ln:,} rows)   FTS {fm:7.1f} ms ({fn:,} rows)   same={ln == fn}")
c.close(); shutil.rmtree(tmp.parent)
