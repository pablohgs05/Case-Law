import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow, dict_row

from app.db import get_connection
from app.main import app
from app.sessions import gate

FIXTURES = Path(__file__).parent / "fixtures"

# The schemas the server applies, not copies of them: a second definition
# here would drift from the real one without a test noticing.
SCHEMAS = sorted((Path(__file__).resolve().parents[1] / "app").glob("*.sql"))

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")

needs_database = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set TEST_DATABASE_URL to run the tests that talk to PostgreSQL",
)


@pytest.fixture(autouse=True)
def signed_in_for_the_suite() -> Iterator[None]:
    """
    Every suite runs as somebody.

    The tool refuses anyone without an account, so without this each of the
    four hundred tests about searching would be a test about the login screen.
    They are about the search, so the door is propped open for them and tested
    where it belongs — `test_contas.py`, which takes the prop away first.
    """
    app.dependency_overrides[gate] = lambda: None
    yield
    app.dependency_overrides.pop(gate, None)


@pytest.fixture(scope="session")
def prepared_database() -> Iterator[str]:
    if (
        psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL).get("dbname")
        != "caselaw_test"
    ):
        raise RuntimeError(
            "TEST_DATABASE_URL must point to caselaw_test; fixtures destroy core."
        )
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        for name in ("schema.sql", "decisions.sql"):
            conn.execute((FIXTURES / name).read_text(encoding="utf-8"))
        for schema in SCHEMAS:
            conn.execute(schema.read_text(encoding="utf-8"))
    yield TEST_DATABASE_URL


@pytest.fixture
def db(prepared_database: str) -> Iterator[psycopg.Connection[DictRow]]:
    with psycopg.connect(prepared_database, row_factory=dict_row) as conn:
        yield conn


@pytest.fixture
def db_rolled_back(
    db: psycopg.Connection[DictRow],
) -> Iterator[psycopg.Connection[DictRow]]:
    """
    Every row a test adds exists only inside its transaction. The rollback sits
    in the teardown so a failing test cannot leave rows behind for the ones that
    count the fixture.
    """
    try:
        yield db
    finally:
        db.rollback()


@pytest.fixture
def client(db_rolled_back: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: db_rolled_back
    yield TestClient(app)
    app.dependency_overrides.clear()
