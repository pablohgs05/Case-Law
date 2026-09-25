"""
The list of courts a search can be narrowed to, run against PostgreSQL.

A fake database returns whatever rows the test hands it, so it could prove
neither that a court with no decision is left out nor that one with many
appears once. These send the real statement to the real tables.
"""

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.db import get_connection
from app.main import app
from tests.conftest import FIXTURES, needs_database
from tests.test_seal_filter import transformation

pytestmark = needs_database

SEEDS = Path(__file__).resolve().parents[2] / "pipeline" / "transformations" / "seeds"

TJDFT = {
    "abbreviation": "TJDFT",
    "name": "Tribunal de Justiça do Distrito Federal e dos Territórios",
}

COURTS = {
    "STF": "Supremo Tribunal Federal",
    "STJ": "Superior Tribunal de Justiça",
    "TRF1": "Tribunal Regional Federal da 1ª Região",
}

# What the model writes and the search reads. Decisions built from the model
# carry more columns than the fixture table, so both sides name these.
COLUMNS = (
    "fonte_codigo, identificador_fonte, tribunal_sigla, data_referencia, ementa, "
    "turma_recursal, possui_inteiro_teor, url_fonte, link_valido, ementa_busca"
)


@pytest.fixture
def db_rolled_back(
    db: psycopg.Connection[DictRow],
) -> Iterator[psycopg.Connection[DictRow]]:
    """
    Every row a test adds exists only inside its transaction. The rollback sits
    in the teardown so a failing test cannot leave courts behind for the ones
    that count the fixture.
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


def register(db: psycopg.Connection[DictRow], abbreviation: str) -> None:
    db.execute(
        "INSERT INTO core.tribunal (sigla, nome) VALUES (%s, %s)",
        (abbreviation, COURTS[abbreviation]),
    )


def decide(
    db: psycopg.Connection[DictRow],
    abbreviation: str,
    identifier: str,
    link_reachable: bool | None = True,
) -> None:
    ementa = f"CIVIL. Dano moral configurado. Decisão {identifier}."
    db.execute(
        f"INSERT INTO core.decisao ({COLUMNS}) VALUES ("
        "  %(source)s, %(identifier)s, %(court)s, '2026-03-10', %(ementa)s,"
        "  FALSE, FALSE, 'https://example.com/' || %(identifier)s, %(link)s,"
        "  TO_TSVECTOR('portugues_sem_acento', %(ementa)s)"
        ")",
        {
            "source": f"{abbreviation.lower()}-teste",
            "identifier": identifier,
            "court": abbreviation,
            "ementa": ementa,
            "link": link_reachable,
        },
    )


def listed(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/courts")
    assert response.status_code == 200, response.text
    return response.json()["courts"]


def abbreviations(client: TestClient) -> list[str]:
    return [court["abbreviation"] for court in listed(client)]


def test_a_collection_with_no_decisions_answers_an_empty_list(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    db_rolled_back.execute("DELETE FROM core.decisao")

    response = client.get("/courts")

    assert response.status_code == 200
    assert response.json() == {"courts": []}


def test_a_court_registered_without_decisions_is_left_out(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    register(db_rolled_back, "TRF1")

    assert "TRF1" not in abbreviations(client)


def test_a_court_with_a_decision_carries_its_abbreviation_and_name(
    client: TestClient,
) -> None:
    assert listed(client) == [TJDFT]


def test_many_decisions_from_one_court_list_it_once(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    with db_rolled_back.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM core.decisao WHERE tribunal_sigla = 'TJDFT'"
        )
        row = cursor.fetchone()

    assert row is not None and row["total"] > 1, "the fixture stopped repeating TJDFT"
    assert abbreviations(client).count("TJDFT") == 1


def test_two_courts_with_decisions_are_both_listed(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    register(db_rolled_back, "STJ")
    decide(db_rolled_back, "STJ", "2000001")
    decide(db_rolled_back, "STJ", "2000002")

    assert listed(client) == [
        {"abbreviation": "STJ", "name": COURTS["STJ"]},
        TJDFT,
    ]


def test_a_court_appears_on_the_next_request_after_its_first_decision(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    register(db_rolled_back, "TRF1")
    assert "TRF1" not in abbreviations(client)

    decide(db_rolled_back, "TRF1", "3000001")

    assert "TRF1" in abbreviations(client)


def test_courts_are_ordered_by_abbreviation(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    Registered in reverse, and named so that ordering by name would put STJ
    ("Superior") before STF ("Supremo"): only the abbreviation gives this order.
    """
    for abbreviation in ("TRF1", "STJ", "STF"):
        register(db_rolled_back, abbreviation)
        decide(db_rolled_back, abbreviation, f"{abbreviation}-1")

    first = abbreviations(client)

    assert first == ["STF", "STJ", "TJDFT", "TRF1"]
    assert abbreviations(client) == first


def test_every_listed_abbreviation_is_one_the_search_filters_by(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    register(db_rolled_back, "STJ")
    decide(db_rolled_back, "STJ", "2000001")

    for abbreviation in abbreviations(client):
        response = client.get(
            "/decisions", params={"q": "dano moral", "tribunal": abbreviation}
        )
        body = response.json()

        assert response.status_code == 200
        assert body["total"] > 0, f"{abbreviation} is listed but the search finds none"
        assert {result["court"] for result in body["results"]} == {abbreviation}


def rebuild_from_raw(db: psycopg.Connection[DictRow]) -> None:
    """Rebuild the decisions the way the pipeline does, through the real model."""
    db.execute("DELETE FROM core.decisao")
    db.execute(
        f"INSERT INTO core.decisao ({COLUMNS}) "
        f"SELECT {COLUMNS} FROM ({transformation()}) AS modelo"
    )


def test_a_court_whose_every_decision_is_sealed_is_not_offered(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    Sealed decisions never enter the collection, so a court with nothing else
    has nothing to search. Built through the model's own filter: a copy of it
    here would keep passing after the real one was removed.
    """
    db_rolled_back.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    rebuild_from_raw(db_rolled_back)
    assert abbreviations(client) == ["TJDFT"]

    db_rolled_back.execute('UPDATE raw.acordao_tjdft SET "segredoJustica" = TRUE')
    rebuild_from_raw(db_rolled_back)

    assert abbreviations(client) == []


def test_a_court_is_listed_whatever_its_links_answer(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    An unreachable link is shown on the card, not hidden from the search, so it
    does not hide the court either.
    """
    register(db_rolled_back, "STJ")
    decide(db_rolled_back, "STJ", "2000001", link_reachable=False)

    assert "STJ" in abbreviations(client)


def test_an_abbreviation_with_no_registered_court_is_not_listed(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    Every item carries a name, and the name comes from the court table. The test
    below keeps the seeds from producing a decision like this one.
    """
    decide(db_rolled_back, "STJ", "2000001")

    assert "STJ" not in abbreviations(client)


def test_every_source_points_to_a_registered_court() -> None:
    with (SEEDS / "fonte.csv").open(encoding="utf-8") as sources:
        pointed = {row["tribunal_sigla"] for row in csv.DictReader(sources)}
    with (SEEDS / "tribunal.csv").open(encoding="utf-8") as courts:
        registered = {row["sigla"] for row in csv.DictReader(courts)}

    assert pointed <= registered, (
        f"sources point to unregistered {pointed - registered}"
    )


def test_the_fixture_court_matches_the_seed() -> None:
    with (SEEDS / "tribunal.csv").open(encoding="utf-8") as courts:
        seeded = {row["sigla"]: row["nome"] for row in csv.DictReader(courts)}

    assert seeded[TJDFT["abbreviation"]] == TJDFT["name"]
