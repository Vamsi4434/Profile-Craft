-- Profile Craft: normalized relational schema (SQLite)
-- One user -> one profile -> many education / experience / certification rows.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash  TEXT    NOT NULL,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id    INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    full_name  TEXT NOT NULL DEFAULT '',
    email      TEXT NOT NULL DEFAULT '',
    phone      TEXT NOT NULL DEFAULT '',
    location   TEXT NOT NULL DEFAULT '',
    summary    TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS education (
    education_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    school          TEXT    NOT NULL,
    degree          TEXT    NOT NULL,
    graduation_year INTEGER CHECK (graduation_year IS NULL OR graduation_year BETWEEN 1950 AND 2100),
    sort_order      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS experience (
    experience_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    company       TEXT    NOT NULL,
    role          TEXT    NOT NULL,
    start_year    INTEGER,
    end_year      INTEGER,               -- NULL = current role
    description   TEXT    NOT NULL DEFAULT '',
    sort_order    INTEGER NOT NULL DEFAULT 0,
    CHECK (end_year IS NULL OR start_year IS NULL OR end_year >= start_year)
);

CREATE TABLE IF NOT EXISTS certifications (
    certification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name             TEXT    NOT NULL,
    sort_order       INTEGER NOT NULL DEFAULT 0
);

-- Audit table for batch ingestion runs (see profile_craft/pipeline/etl.py)
CREATE TABLE IF NOT EXISTS etl_runs (
    run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source           TEXT    NOT NULL,
    started_at       TEXT    NOT NULL,
    finished_at      TEXT    NOT NULL,
    records_read     INTEGER NOT NULL,
    records_loaded   INTEGER NOT NULL,
    records_rejected INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_education_user      ON education(user_id);
CREATE INDEX IF NOT EXISTS idx_experience_user     ON experience(user_id);
CREATE INDEX IF NOT EXISTS idx_certifications_user ON certifications(user_id);
CREATE INDEX IF NOT EXISTS idx_certifications_name ON certifications(name COLLATE NOCASE);
