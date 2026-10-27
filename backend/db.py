"""SQLite access. One connection per call; WAL for concurrent readers."""
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.environ.get("AGELENS_DB", DATA_DIR / "agelens.db"))


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema():
    sql = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
    with connect() as conn:
        conn.executescript(sql)
