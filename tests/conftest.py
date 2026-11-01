import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from profile_craft import db  # noqa: E402


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.init_db(c)
    yield c
    c.close()


@pytest.fixture
def sample_json() -> Path:
    return ROOT / "data" / "sample_users.json"


@pytest.fixture
def raw_conn() -> sqlite3.Connection:
    return sqlite3.connect(":memory:")
