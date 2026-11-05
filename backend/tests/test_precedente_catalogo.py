"""
The precedent catalogue's key, against PostgreSQL.

What this protects is the composite key. Súmula 7 of the STJ and Súmula 7 of
the STF are different precedents with different wording, and a key that forgot
the court would let one overwrite the other — after which the system attributes
the wrong text to thousands of citations without anything failing.
"""

import psycopg
import pytest
from psycopg.rows import DictRow

from tests.conftest import needs_database

pytestmark = needs_database


def catalogue(
    db: psycopg.Connection[DictRow],
    court: str = "STJ",
    kind: str = "sumula",
    number: int = 7,
    text: str = "A pretensão de simples reexame de prova não enseja recurso especial.",
    origin: str = "reconstruido",
) -> None:
    db.execute(
        "INSERT INTO core.precedente (corte, tipo, numero, enunciado, origem)"
        " VALUES (%s, %s, %s, %s, %s)",
        (court, kind, number, text, origin),
    )


def rows(db: psycopg.Connection[DictRow]) -> list[DictRow]:
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM core.precedente ORDER BY corte, tipo, numero")
        return cursor.fetchall()


def test_the_same_precedent_cannot_be_written_twice(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    catalogue(db_rolled_back)

    with pytest.raises(psycopg.errors.UniqueViolation):
        catalogue(db_rolled_back)


def test_two_courts_can_settle_the_same_number(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    """
    The one this file exists for. Súmula 7/STJ bars re-examining evidence;
    Súmula 7/STF says something else entirely. A key of (tipo, numero) alone
    would keep one and lose the other, and every citation of the lost one
    would come back carrying the survivor's text.
    """
    catalogue(
        db_rolled_back,
        court="STJ",
        number=7,
        text="Reexame de prova não enseja recurso.",
    )
    catalogue(
        db_rolled_back, court="STF", number=7, text="Outro enunciado, de outra corte."
    )

    held = rows(db_rolled_back)

    assert [row["corte"] for row in held] == ["STF", "STJ"]
    assert held[0]["enunciado"] != held[1]["enunciado"]


def test_the_number_alone_is_not_the_key_either(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    """Súmula 630 and Tema 630 are different things of the same court."""
    catalogue(
        db_rolled_back, kind="sumula", number=630, text="Enunciado da súmula 630."
    )
    catalogue(db_rolled_back, kind="tema", number=630, text="Tese firmada no tema 630.")

    assert len(rows(db_rolled_back)) == 2


def test_running_the_collection_again_cannot_duplicate_a_row(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    """
    The catalogue is rebuilt whole on every run. Duplication is impossible by
    construction rather than by the loader being careful, which is the point:
    a loader can be changed, and the key cannot be worked around.
    """
    catalogue(
        db_rolled_back,
        number=83,
        text="Não se conhece do recurso especial pela divergência.",
    )

    for _ in range(3):
        with pytest.raises(psycopg.errors.UniqueViolation):
            catalogue(db_rolled_back, number=83, text="Qualquer outro texto.")
        db_rolled_back.rollback()
        catalogue(
            db_rolled_back,
            number=83,
            text="Não se conhece do recurso especial pela divergência.",
        )

    assert len(rows(db_rolled_back)) == 1


def test_a_precedent_without_a_text_is_not_a_precedent(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    """
    The enunciado is the product. Without it a row carries a number and a
    court and says nothing, and the screen would show a citation it cannot
    explain. The model audits this at a floor of 40 characters; here the
    column simply refuses a null.
    """
    with pytest.raises(psycopg.errors.NotNullViolation):
        db_rolled_back.execute(
            "INSERT INTO core.precedente (corte, tipo, numero, enunciado, origem)"
            " VALUES ('STJ', 'sumula', 999, NULL, 'reconstruido')"
        )


def test_the_catalogue_carries_no_link_of_its_own(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    """
    A deviation worth pinning rather than hiding. The card asks every
    precedent to carry `url_fonte`, and none does: no public catalogue of
    súmulas exists to link to, so the screen builds the official address from
    the precedent's own numbering instead. If a source is ever found, this
    test is the one that should start failing.
    """
    catalogue(db_rolled_back)

    assert rows(db_rolled_back)[0]["url_fonte"] is None
