import pytest

from profile_craft import db
from profile_craft.models import Certification, Education, Experience, Profile


def test_create_and_authenticate(conn):
    uid = db.create_user(conn, "ana", "password1")
    assert db.authenticate(conn, "ana", "password1") == uid
    assert db.authenticate(conn, "ANA", "password1") == uid  # usernames are case-insensitive
    assert db.authenticate(conn, "ana", "wrong") is None


def test_password_is_not_stored_in_plaintext(conn):
    db.create_user(conn, "ana", "password1")
    stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert "password1" not in stored


def test_duplicate_user_rejected(conn):
    db.create_user(conn, "ana", "password1")
    with pytest.raises(db.UserExistsError):
        db.create_user(conn, "ana", "other")


def test_profile_round_trip_and_replace(conn):
    uid = db.create_user(conn, "ana", "password1")
    p = Profile(
        full_name="Ana", email="ana@example.com",
        education=[Education(school="U", degree="BS", graduation_year=2020)],
        experience=[Experience(company="A", role="DE", start_year=2021)],
        certifications=[Certification(name="AWS"), Certification(name="dbt")],
    )
    db.save_profile(conn, uid, p)
    assert db.get_profile(conn, uid) == p

    p2 = p.model_copy(update={"certifications": [Certification(name="Spark")]})
    db.save_profile(conn, uid, p2)
    assert [c.name for c in db.get_profile(conn, uid).certifications] == ["Spark"]
    assert conn.execute("SELECT COUNT(*) FROM certifications").fetchone()[0] == 1


def test_deleting_user_cascades(conn):
    uid = db.create_user(conn, "ana", "password1")
    db.save_profile(conn, uid, Profile(certifications=[Certification(name="AWS")]))
    conn.execute("DELETE FROM users WHERE user_id = ?", (uid,))
    assert conn.execute("SELECT COUNT(*) FROM certifications").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0
