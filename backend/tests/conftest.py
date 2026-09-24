import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import DictRow, dict_row

FIXTURES = Path(__file__).parent / "fixtures"

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")

needs_database = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set TEST_DATABASE_URL to run the tests that talk to PostgreSQL",
)


@pytest.fixture(scope="session")
def prepared_database() -> Iterator[str]:
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        for name in ("schema.sql", "decisions.sql"):
            conn.execute((FIXTURES / name).read_text(encoding="utf-8"))
    yield TEST_DATABASE_URL


@pytest.fixture
def db(prepared_database: str) -> Iterator[psycopg.Connection[DictRow]]:
    with psycopg.connect(prepared_database, row_factory=dict_row) as conn:
        yield conn
