-- AgeLens schema. Owner of changes: lead (additive changes by agents must be noted in DEVELOPMENT_LOG.md).
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS import_batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT NOT NULL,
  imported_at TEXT NOT NULL,
  raw_rows INTEGER NOT NULL DEFAULT 0,
  unique_ads INTEGER NOT NULL DEFAULT 0,
  duplicates INTEGER NOT NULL DEFAULT 0,
  mapping_json TEXT,          -- CSV column -> canonical field
  log_json TEXT,              -- encoding, date format, missing-value counts, warnings
  rule_version TEXT,
  is_demo INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS raw_ads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL REFERENCES import_batches(id),
  source_row INTEGER NOT NULL,  -- 1-based data row number in the source file
  raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ads (
  id TEXT PRIMARY KEY,          -- stable id: 'ad_' + first 12 hex of sha1 of normalised dedupe key
  batch_id INTEGER NOT NULL REFERENCES import_batches(id),
  raw_id INTEGER NOT NULL REFERENCES raw_ads(id),   -- first raw record kept
  duplicate_count INTEGER NOT NULL DEFAULT 0,       -- additional raw rows folded into this ad
  title TEXT, company TEXT,
  occupation TEXT,              -- cleaned category / keyword text
  province TEXT, city TEXT,     -- province uses canonical short name matching frontend/geo (e.g. 上海, 广东)
  posted_date TEXT,             -- ISO YYYY-MM-DD or NULL
  source TEXT, url TEXT,
  description TEXT,             -- original Chinese text, never altered
  age_status TEXT NOT NULL DEFAULT 'none',  -- 'explicit' | 'uncertain' | 'none'
  is_demo INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_ads_province ON ads(province);
CREATE INDEX IF NOT EXISTS ix_ads_occupation ON ads(occupation);
CREATE INDEX IF NOT EXISTS ix_ads_date ON ads(posted_date);
CREATE INDEX IF NOT EXISTS ix_ads_status ON ads(age_status);

CREATE TABLE IF NOT EXISTS age_terms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ad_id TEXT NOT NULL REFERENCES ads(id),
  kind TEXT NOT NULL,           -- 'max' | 'min' | 'range' | 'relaxable' | 'ambiguous'
  min_age INTEGER, max_age INTEGER,
  snippet TEXT NOT NULL,        -- exact original sentence/phrase
  start_offset INTEGER, end_offset INTEGER,   -- position of snippet in ads.description
  exception_text TEXT,          -- e.g. 条件优秀者可放宽
  confidence TEXT NOT NULL DEFAULT 'high',    -- 'high' | 'low'
  rule_version TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_terms_ad ON age_terms(ad_id);
CREATE INDEX IF NOT EXISTS ix_terms_max ON age_terms(max_age);

CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL UNIQUE,    -- public request number, e.g. AL-2026-0001
  owner_token_hash TEXT NOT NULL,   -- sha256 of seeker's owner token
  status TEXT NOT NULL DEFAULT 'pending',  -- pending | needs_info | replied | closed
  question TEXT NOT NULL,
  profile_json TEXT NOT NULL,       -- snapshot of shared background fields only
  evidence_json TEXT NOT NULL,      -- snapshot of selected ads (text + age terms) at submit time
  scope_json TEXT,                  -- retrieval scope snapshot
  is_demo INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  published_at TEXT, closed_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id INTEGER NOT NULL REFERENCES requests(id),
  author TEXT NOT NULL,         -- 'seeker' | 'reviewer'
  kind TEXT NOT NULL,           -- 'question' | 'info_request' | 'answer' | 'draft' | 'reply'
  body TEXT NOT NULL,
  facts_json TEXT,              -- reviewer reply: facts directly supported by ad text
  to_verify_json TEXT,          -- reviewer reply: judgements needing further verification
  published INTEGER NOT NULL DEFAULT 0,   -- drafts are always 0 and never shown to seekers
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_msg_req ON messages(request_id);
