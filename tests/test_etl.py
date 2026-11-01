import json

from profile_craft import analytics, db
from profile_craft.pipeline import etl


def test_pipeline_loads_valid_and_rejects_invalid(conn, sample_json, tmp_path):
    rejects = tmp_path / "rejects.jsonl"
    stats = etl.run(sample_json, conn, rejects)

    assert stats.read == 6
    assert stats.loaded == 3
    rejected = {r.username for r in stats.rejected}
    assert rejected == {"bad-email@example.com", "bad-dates@example.com", "no-password@example.com"}

    lines = [json.loads(line) for line in rejects.read_text().splitlines()]
    assert all(line["reason"] for line in lines)


def test_pipeline_hashes_plaintext_passwords(conn, sample_json):
    etl.run(sample_json, conn)
    hashes = [r[0] for r in conn.execute("SELECT password_hash FROM users")]
    assert all(h.startswith("scrypt$") for h in hashes)
    assert db.authenticate(conn, "demo@profilecraft.dev", "demo1234") is not None


def test_pipeline_is_idempotent(conn, sample_json):
    etl.run(sample_json, conn)
    first = conn.execute("SELECT COUNT(*) FROM certifications").fetchone()[0]
    etl.run(sample_json, conn)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM certifications").fetchone()[0] == first
    assert len(analytics.etl_runs(conn)) == 2


def test_blank_child_rows_are_dropped(conn, sample_json):
    etl.run(sample_json, conn)
    uid = db.get_user_id(conn, "priya@example.com")
    profile = db.get_profile(conn, uid)
    assert [c.name for c in profile.certifications] == ["AWS Certified Data Engineer - Associate"]
    assert profile.education[0].graduation_year == 2023  # parsed from "Class of 2023"


def test_analytics_queries(conn, sample_json):
    etl.run(sample_json, conn)
    comp = analytics.profile_completeness(conn)
    assert comp.iloc[0]["username"] == "demo@profilecraft.dev"
    assert comp.iloc[0]["completeness_pct"] == 100.0

    certs = analytics.top_certifications(conn)
    assert certs.iloc[0]["users"] == 2

    years = analytics.experience_years(conn)
    assert set(years["username"]) == {"demo@profilecraft.dev", "priya@example.com"}
