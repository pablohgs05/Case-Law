from pathlib import Path

import psycopg
import pytest
from psycopg.rows import DictRow

from tests.conftest import FIXTURES, needs_database
from tests.test_seal_filter import transformation

pytestmark = needs_database

SEED = (
    Path(__file__).resolve().parents[2]
    / "pipeline"
    / "transformations"
    / "seeds"
    / "fonte.csv"
)


@pytest.fixture
def transformed(db: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db.execute("DROP TABLE IF EXISTS core.decisao_com_url")
    db.execute(f"CREATE TABLE core.decisao_com_url AS {transformation()}")
    return db


def test_the_link_is_built_from_the_identifier(
    transformed: psycopg.Connection[DictRow],
) -> None:
    with transformed.cursor() as cursor:
        cursor.execute(
            "SELECT identificador_fonte, url_fonte FROM core.decisao_com_url"
        )
        rows = cursor.fetchall()

    assert rows
    for row in rows:
        assert row["url_fonte"].endswith(f"/{row['identificador_fonte']}")
        assert "{identificador}" not in row["url_fonte"]


def test_the_court_and_the_pattern_come_from_the_seed_not_from_the_query(
    transformed: psycopg.Connection[DictRow],
) -> None:
    """
    The model names its source once and reads everything else through the join,
    so changing a court's URL pattern is a change to the seed.
    """
    with transformed.cursor() as cursor:
        cursor.execute(
            """
            UPDATE core.fonte
            SET url_documento_template = 'https://outro.exemplo/doc/{identificador}',
                tribunal_sigla = 'XXXX'
            """
        )
        cursor.execute("DROP TABLE IF EXISTS core.decisao_outro_padrao")
        cursor.execute(f"CREATE TABLE core.decisao_outro_padrao AS {transformation()}")
        cursor.execute(
            "SELECT tribunal_sigla, url_fonte FROM core.decisao_outro_padrao LIMIT 1"
        )
        row = cursor.fetchone()

    assert row is not None
    assert row["tribunal_sigla"] == "XXXX"
    assert row["url_fonte"].startswith("https://outro.exemplo/doc/")


def test_the_seed_carries_a_pattern_for_every_source() -> None:
    lines = SEED.read_text(encoding="utf-8").strip().splitlines()

    assert len(lines) > 1, "the seed has no source"
    for line in lines[1:]:
        assert "{identificador}" in line
