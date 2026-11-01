"""SQL analytics over the profile data, returned as pandas DataFrames."""

from __future__ import annotations

import sqlite3

import pandas as pd

PROFILE_COMPLETENESS = """
WITH counts AS (
    SELECT
        u.user_id,
        u.username,
        (SELECT COUNT(*) FROM education      e WHERE e.user_id = u.user_id) AS n_education,
        (SELECT COUNT(*) FROM experience     x WHERE x.user_id = u.user_id) AS n_experience,
        (SELECT COUNT(*) FROM certifications c WHERE c.user_id = u.user_id) AS n_certifications
    FROM users u
)
SELECT
    c.username,
    c.n_education,
    c.n_experience,
    c.n_certifications,
    ROUND(100.0 * (
        (p.full_name <> '') + (p.email <> '') + (p.phone <> '') + (p.location <> '') +
        (p.summary <> '') + (c.n_education > 0) + (c.n_experience > 0) + (c.n_certifications > 0)
    ) / 8, 1) AS completeness_pct
FROM counts c
JOIN profiles p USING (user_id)
ORDER BY completeness_pct DESC, c.username
"""

TOP_CERTIFICATIONS = """
SELECT name AS certification, COUNT(DISTINCT user_id) AS users
FROM certifications
GROUP BY LOWER(name)
ORDER BY users DESC, certification
LIMIT :limit
"""

EXPERIENCE_YEARS = """
SELECT
    u.username,
    SUM(COALESCE(x.end_year, CAST(strftime('%Y', 'now') AS INTEGER)) - x.start_year) AS years_experience,
    COUNT(*) AS roles
FROM experience x
JOIN users u USING (user_id)
WHERE x.start_year IS NOT NULL
GROUP BY u.user_id
ORDER BY years_experience DESC
"""

ETL_RUNS = """
SELECT run_id, source, started_at, records_read, records_loaded, records_rejected
FROM etl_runs
ORDER BY run_id DESC
LIMIT 20
"""


def profile_completeness(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(PROFILE_COMPLETENESS, conn)


def top_certifications(conn: sqlite3.Connection, limit: int = 10) -> pd.DataFrame:
    return pd.read_sql_query(TOP_CERTIFICATIONS, conn, params={"limit": limit})


def experience_years(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(EXPERIENCE_YEARS, conn)


def etl_runs(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(ETL_RUNS, conn)
