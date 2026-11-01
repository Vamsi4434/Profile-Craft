"""Batch ETL: legacy JSON user export -> validated, normalized SQLite.

    python -m profile_craft.pipeline.etl data/sample_users.json --db profile_craft.db

Stages
------
Extract    read the JSON export (``{username: {password, profile}}``)
Transform  validate each record with Pydantic, normalize fields
           (``duration`` text -> start/end years), hash plaintext passwords
Load       idempotent upsert per user inside one transaction; invalid records
           go to a rejects file with the reason, and every run is audited in
           the ``etl_runs`` table.
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .. import db
from ..models import Profile
from ..security import hash_password, is_hashed

log = logging.getLogger("profile_craft.etl")


@dataclass
class Record:
    username: str
    password_hash: str
    profile: Profile


@dataclass
class Reject:
    username: str
    reason: str


@dataclass
class RunStats:
    read: int = 0
    loaded: int = 0
    rejected: list[Reject] = field(default_factory=list)


# ------------------------------------------------------------------ extract

def extract(path: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object keyed by username")
    yield from data.items()


# ---------------------------------------------------------------- transform

def transform(username: str, raw: dict[str, Any]) -> Record:
    username = (username or "").strip()
    if not username:
        raise ValueError("missing username")
    password = raw.get("password") or raw.get("password_hash")
    if not password:
        raise ValueError("missing password")
    profile_raw = raw.get("profile") or {}
    # Drop blank child rows the old UI sometimes saved.
    for key, required in (("education", "school"), ("experience", "company"), ("certifications", "name")):
        profile_raw[key] = [r for r in profile_raw.get(key, []) if (r or {}).get(required)]
    profile = Profile.model_validate(profile_raw)
    pw_hash = password if is_hashed(password) else hash_password(password)
    return Record(username=username, password_hash=pw_hash, profile=profile)


# --------------------------------------------------------------------- load

def load(conn: sqlite3.Connection, rec: Record) -> None:
    with db.transaction(conn):
        conn.execute(
            """
            INSERT INTO users (username, password_hash) VALUES (?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash, updated_at = datetime('now')
            """,
            (rec.username, rec.password_hash),
        )
        user_id = db.get_user_id(conn, rec.username)
        db.save_profile(conn, user_id, rec.profile, in_tx=True)


# --------------------------------------------------------------- orchestrate

def _reason(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
    return str(exc)


def run(source: Path, conn: sqlite3.Connection, rejects_path: Path | None = None) -> RunStats:
    db.init_db(conn)
    started = datetime.now(UTC).isoformat(timespec="seconds")
    stats = RunStats()

    for username, raw in extract(source):
        stats.read += 1
        try:
            load(conn, transform(username, raw))
            stats.loaded += 1
        except (ValidationError, ValueError, sqlite3.IntegrityError) as exc:
            stats.rejected.append(Reject(username=username, reason=_reason(exc)))
            log.warning("rejected %s: %s", username, _reason(exc))

    if rejects_path and stats.rejected:
        rejects_path.parent.mkdir(parents=True, exist_ok=True)
        with rejects_path.open("w", encoding="utf-8") as fh:
            for r in stats.rejected:
                fh.write(json.dumps(r.__dict__) + "\n")

    finished = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO etl_runs (source, started_at, finished_at, records_read, records_loaded, records_rejected) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (str(source), started, finished, stats.read, stats.loaded, len(stats.rejected)),
    )
    conn.commit()
    log.info("read=%d loaded=%d rejected=%d", stats.read, stats.loaded, len(stats.rejected))
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load a Profile Craft JSON export into SQLite.")
    parser.add_argument("source", type=Path, help="path to the JSON export")
    parser.add_argument("--db", default=db.DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument("--rejects", type=Path, default=Path("data/rejects.jsonl"))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stats = run(args.source, db.connect(args.db), args.rejects)
    print(f"Read {stats.read} | loaded {stats.loaded} | rejected {len(stats.rejected)}")
    if stats.rejected:
        print(f"Rejected records written to {args.rejects}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
