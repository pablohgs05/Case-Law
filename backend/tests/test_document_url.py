from pathlib import Path

import psycopg
import pytest
from psycopg.rows import DictRow

from tests.conftest import FIXTURES, needs_database
from tests.test_seal_filter import MODEL, transformation

pytestmark = [needs_database, pytest.mark.integration]

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


def test_the_link_is_built_from_the_document_key(
    transformed: psycopg.Connection[DictRow],
) -> None:
    """
    The key that opens the document is not the key that identifies the record:
    the TJDFT routes on the uuid, the STJ on its own id.
    """
    with transformed.cursor() as cursor:
        cursor.execute(
            "SELECT fonte_codigo, identificador_fonte, identificador_documento, "
            "url_fonte FROM core.decisao_com_url"
        )
        rows = cursor.fetchall()

    assert rows
    assert {row["fonte_codigo"] for row in rows} == {"tjdft-jurisdf", "stj-espelhos"}
    for row in rows:
        assert row["identificador_documento"] in row["url_fonte"]
        assert "{documento}" not in row["url_fonte"]

    tjdft = [r for r in rows if r["fonte_codigo"] == "tjdft-jurisdf"]
    assert tjdft
    for row in tjdft:
        assert row["identificador_documento"] != row["identificador_fonte"]
        assert row["identificador_fonte"] not in row["url_fonte"]


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
            SET url_documento_template = 'https://outro.exemplo/doc/{documento}',
                tribunal_sigla = 'XXXX'
            """
        )
        cursor.execute("DROP TABLE IF EXISTS core.decisao_outro_padrao")
        cursor.execute(f"CREATE TABLE core.decisao_outro_padrao AS {transformation()}")
        cursor.execute(
            "SELECT tribunal_sigla, identificador_documento, url_fonte "
            "FROM core.decisao_outro_padrao LIMIT 1"
        )
        row = cursor.fetchone()

    assert row is not None
    assert row["tribunal_sigla"] == "XXXX"
    assert row["url_fonte"] == (
        f"https://outro.exemplo/doc/{row['identificador_documento']}"
    )


def test_the_seed_carries_a_pattern_for_every_source() -> None:
    lines = SEED.read_text(encoding="utf-8").strip().splitlines()

    assert len(lines) > 1, "the seed has no source"
    for line in lines[1:]:
        assert "{documento}" in line


def test_a_record_with_no_identifier_gets_no_link(
    db: psycopg.Connection[DictRow],
) -> None:
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db.execute(
        'INSERT INTO raw.acordao_tjdft (identificador, "dataJulgamento", ementa, '
        '"segredoJustica", _dlt_load_id) '
        "VALUES (NULL, '2026-03-20', 'Ementa sem identificador.', FALSE, '1789000000.0')"
    )
    db.execute("DROP TABLE IF EXISTS core.decisao_sem_id")
    db.execute(f"CREATE TABLE core.decisao_sem_id AS {transformation()}")

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT url_fonte FROM core.decisao_sem_id WHERE identificador_fonte IS NULL"
        )
        rows = cursor.fetchall()

    assert rows, "the record without an identifier did not reach the transformation"
    for row in rows:
        assert row["url_fonte"] is None


def test_a_link_that_could_not_be_built_never_reaches_a_server(
    db: psycopg.Connection[DictRow],
) -> None:
    model = MODEL.read_text(encoding="utf-8")
    audits = model.split("audits (", 1)[1].split("\n  )", 1)[0]

    assert "not_null" in audits
    assert "url_fonte" in audits
    assert "identificador_fonte" in audits
