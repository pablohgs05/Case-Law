"""
The class the court filed the case under, resolved against the national table.

The TJDFT sends the code. The STJ sends a name, and names the class by the
whole ladder — "AGRAVO REGIMENTAL NO RECURSO ESPECIAL" — where the national
table only holds the pieces. These pin the two rules that bridge the gap, and
the one that keeps a repeated name from multiplying a decision.
"""

from typing import Any

import psycopg
import pytest
from psycopg.rows import DictRow

from tests.conftest import FIXTURES, needs_database
from tests.test_seal_filter import transformation

pytestmark = needs_database


@pytest.fixture
def transformed(
    db_rolled_back: psycopg.Connection[DictRow],
) -> psycopg.Connection[DictRow]:
    db_rolled_back.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db_rolled_back.execute("DROP TABLE IF EXISTS core.decisao_classe")
    db_rolled_back.execute(f"CREATE TABLE core.decisao_classe AS {transformation()}")
    return db_rolled_back


def classe(db: psycopg.Connection[DictRow], identifier: str) -> Any:
    row = db.execute(
        "SELECT classe_cnj FROM core.decisao_classe WHERE identificador_fonte = %s",
        (identifier,),
    ).fetchone()
    assert row is not None, identifier
    return row["classe_cnj"]


def test_a_name_the_table_holds_outright_resolves_to_its_code(
    transformed: psycopg.Connection[DictRow],
) -> None:
    assert classe(transformed, "8000001") == 213


def test_the_class_is_the_outermost_piece_of_the_ladder(
    transformed: psycopg.Connection[DictRow],
) -> None:
    """
    "AGRAVO REGIMENTAL NO RECURSO ESPECIAL" is an Agravo Regimental, filed
    inside a Recurso Especial. Reading the name from the other end would file
    268.298 decisions under the appeal they were raised against.
    """
    assert classe(transformed, "8000002") == 1321


def test_a_name_two_courts_share_resolves_to_the_court_that_judged_it(
    transformed: psycopg.Connection[DictRow],
) -> None:
    """
    "Ação Rescisória" exists under three codes, one per court. 88 names repeat
    this way. Without the preference the answer would be whichever code sorted
    first, which is the first instance's.
    """
    assert classe(transformed, "8000003") == 1669


def test_a_name_the_table_does_not_hold_stays_null(
    transformed: psycopg.Connection[DictRow],
) -> None:
    """
    0,5% of the collection, and null is the answer. Falling back to the
    commonest class would file them under a class nobody chose.
    """
    row = transformed.execute(
        "SELECT classe_cnj FROM core.decisao_classe "
        "WHERE identificador_documento = '202600611244'"
    ).fetchone()

    assert row is None or row["classe_cnj"] is None


def test_a_repeated_name_never_multiplies_a_decision(
    transformed: psycopg.Connection[DictRow],
) -> None:
    """
    The bridge is a join on the name, and 88 names are not unique. A join that
    kept the duplicates would hand the screen the same decision three times and
    break every count that the search and the indicators promise to agree on.
    """
    counted = transformed.execute(
        "SELECT fonte_codigo, identificador_fonte, COUNT(*) AS vezes "
        "FROM core.decisao_classe GROUP BY 1, 2 HAVING COUNT(*) > 1"
    ).fetchall()

    assert counted == []


def test_the_tjdft_keeps_sending_its_own_code(
    transformed: psycopg.Connection[DictRow],
) -> None:
    """The bridge is for the STJ only: the TJDFT already sends the code."""
    row = transformed.execute(
        "SELECT COUNT(*) AS com_classe FROM core.decisao_classe "
        "WHERE fonte_codigo = 'tjdft-jurisdf' AND classe_cnj IS NOT NULL"
    ).fetchone()

    assert row is not None
    assert row["com_classe"] > 0
