"""SQLite data-access layer.

All writes go through validated ``Profile`` models and run inside a single
transaction, so a profile is either fully saved or not saved at all.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .models import Certification, Education, Experience, Profile
from .security import hash_password, is_hashed, verify_password

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"
DEFAULT_DB_PATH = os.environ.get("PROFILE_CRAFT_DB", "profile_craft.db")


def connect(db_path: str | os.PathLike = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------- users

class UserExistsError(Exception):
    pass


def get_user_id(conn: sqlite3.Connection, username: str) -> int | None:
    row = conn.execute("SELECT user_id FROM users WHERE username = ?", (username,)).fetchone()
    return row["user_id"] if row else None


def create_user(conn: sqlite3.Connection, username: str, password: str) -> int:
    username = username.strip()
    if not username:
        raise ValueError("username must not be empty")
    if get_user_id(conn, username) is not None:
        raise UserExistsError(username)
    pw_hash = password if is_hashed(password) else hash_password(password)
    with transaction(conn):
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, pw_hash)
        )
        user_id = cur.lastrowid
        conn.execute("INSERT INTO profiles (user_id) VALUES (?)", (user_id,))
    return user_id


def authenticate(conn: sqlite3.Connection, username: str, password: str) -> int | None:
    row = conn.execute(
        "SELECT user_id, password_hash FROM users WHERE username = ?", (username.strip(),)
    ).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return row["user_id"]
    return None


# ---------------------------------------------------------------- profiles

def get_profile(conn: sqlite3.Connection, user_id: int) -> Profile:
    p = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    edu = conn.execute(
        "SELECT school, degree, graduation_year FROM education WHERE user_id = ? ORDER BY sort_order",
        (user_id,),
    ).fetchall()
    exp = conn.execute(
        "SELECT company, role, start_year, end_year, description FROM experience "
        "WHERE user_id = ? ORDER BY sort_order",
        (user_id,),
    ).fetchall()
    certs = conn.execute(
        "SELECT name FROM certifications WHERE user_id = ? ORDER BY sort_order", (user_id,)
    ).fetchall()
    return Profile(
        full_name=p["full_name"] if p else "",
        email=p["email"] if p else "",
        phone=p["phone"] if p else "",
        location=p["location"] if p else "",
        summary=p["summary"] if p else "",
        education=[Education(**dict(r)) for r in edu],
        experience=[Experience(**dict(r)) for r in exp],
        certifications=[Certification(**dict(r)) for r in certs],
    )


def save_profile(conn: sqlite3.Connection, user_id: int, profile: Profile, *, in_tx: bool = False) -> None:
    """Upsert the profile and replace its child rows atomically."""

    def _write():
        conn.execute(
            """
            INSERT INTO profiles (user_id, full_name, email, phone, location, summary, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name, email = excluded.email,
                phone = excluded.phone, location = excluded.location,
                summary = excluded.summary, updated_at = excluded.updated_at
            """,
            (user_id, profile.full_name, profile.email, profile.phone, profile.location, profile.summary),
        )
        for table in ("education", "experience", "certifications"):
            conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO education (user_id, school, degree, graduation_year, sort_order) VALUES (?, ?, ?, ?, ?)",
            [(user_id, e.school, e.degree, e.graduation_year, i) for i, e in enumerate(profile.education)],
        )
        conn.executemany(
            "INSERT INTO experience (user_id, company, role, start_year, end_year, description, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (user_id, x.company, x.role, x.start_year, x.end_year, x.description, i)
                for i, x in enumerate(profile.experience)
            ],
        )
        conn.executemany(
            "INSERT INTO certifications (user_id, name, sort_order) VALUES (?, ?, ?)",
            [(user_id, c.name, i) for i, c in enumerate(profile.certifications)],
        )
        conn.execute("UPDATE users SET updated_at = datetime('now') WHERE user_id = ?", (user_id,))

    if in_tx:
        _write()
    else:
        with transaction(conn):
            _write()
