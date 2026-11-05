"""
Which passage the snippet is cut around, against PostgreSQL.

A reader who arrives from an indicator wants to see what produced the label,
not where their own words happen to fall. Measured over decisions that carry a
written thesis, the search terms put 31,5% of snippets in "questão em
discussão" — the question the court faced — and 2,25% on the thesis it
settled. The terms sit where the dispute is framed; the answer is written in
normative language that often does not repeat them.
"""

import re
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = needs_database

TERM = "dano moral"

EMENTA = (
    "CIVIL. Responsabilidade por dano moral. "
    "I. CASO EM EXAME 1. Apelação contra sentença de improcedência. "
    "II. QUESTÃO EM DISCUSSÃO 2. A questão consiste em saber se a falha na "
    "prestação do serviço bancário impõe o reconhecimento de dano moral in re "
    "ipsa. "
    "III. RAZÕES DE DECIDIR 3. Incide a Súmula n. 83 do STJ, pois o acórdão "
    "recorrido se alinha à jurisprudência desta Corte. "
    "IV. DISPOSITIVO 4. Recurso conhecido e desprovido."
)


def written(db: psycopg.Connection[DictRow], identifier: str) -> None:
    decide(db, "STJ", identifier)
    db.execute(
        "UPDATE core.decisao"
        " SET ementa = %s,"
        "     ementa_busca = TO_TSVECTOR('portugues_sem_acento', %s),"
        "     decisao_texto = 'Recurso conhecido e desprovido.',"
        "     resultado = 'negado'"
        " WHERE identificador_fonte = %s",
        (EMENTA, EMENTA, identifier),
    )


@pytest.fixture
def written_decisions(
    db_rolled_back: psycopg.Connection[DictRow],
) -> psycopg.Connection[DictRow]:
    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    written(db_rolled_back, "com-tese")
    return db_rolled_back


@pytest.fixture
def client(written_decisions: psycopg.Connection[DictRow]) -> Any:
    from app.db import get_connection
    from app.main import app

    app.dependency_overrides[get_connection] = lambda: written_decisions
    yield TestClient(app)
    app.dependency_overrides.clear()


def snippet(client: TestClient, **params: Any) -> str:
    response = client.get("/decisions", params={"q": TERM, "page_size": 1, **params})
    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert results, "a busca não trouxe nada para conferir"
    return str(results[0]["snippet"])


def plain(marked: str) -> str:
    """The snippet as the court wrote it: marks off, fragments apart."""
    return re.sub(r"</?mark>", "", marked)


def test_every_snippet_exists_word_for_word_in_the_ementa(client: TestClient) -> None:
    """
    The test the card calls deciding. A snippet that reads as quotable and is
    not in the acórdão can end up in a petition — so each fragment is looked
    for, verbatim, in the court's own text.
    """
    for highlight in (None, "resultado", "aderencia"):
        params = {"highlight": highlight} if highlight else {}
        for fragment in plain(snippet(client, **params)).split(" … "):
            assert fragment.strip() in EMENTA, (highlight, fragment)


def test_the_outcome_indicator_points_at_the_dispositive(client: TestClient) -> None:
    marked = snippet(client, highlight="resultado")

    assert "<mark>desprovido</mark>" in marked
    assert "consiste em saber" not in plain(marked)


def test_the_adherence_indicator_points_at_the_citation(client: TestClient) -> None:
    marked = snippet(client, highlight="aderencia")

    assert "<mark>Súmula</mark>" in marked or "<mark>Incide</mark>" in marked
    assert "83" in plain(marked)


def test_a_plain_search_still_highlights_what_was_typed(client: TestClient) -> None:
    """
    The behaviour that must not regress: without an indicator the reader wants
    to see where their own words are.
    """
    marked = snippet(client)

    assert "<mark>" in marked
    assert re.search(r"<mark>[Dd]ano</mark>|<mark>moral</mark>", marked), marked


def test_the_question_is_what_the_search_terms_find(client: TestClient) -> None:
    """
    The bias this subtask exists to correct, pinned so it cannot be called a
    coincidence: searching for the subject lands on the section where the
    court frames the dispute, which is the one place the terms repeat.
    """
    assert "consiste em saber" in plain(snippet(client))


def test_an_unknown_criterion_is_refused_rather_than_ignored(
    client: TestClient,
) -> None:
    """
    Silently falling back to the query would make a wrong indicator name read
    as a working one, and nobody would find out from the answer.
    """
    response = client.get(
        "/decisions", params={"q": TERM, "page_size": 1, "highlight": "volume"}
    )

    assert response.status_code == 422
