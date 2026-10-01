"""
The search's decisions counted by court, run against PostgreSQL.

The promise is agreement: the counts have to add up to the same total the
search reports for the same parameters. Only the real statement over the real
tables can show that, since it is the WHERE clause the two share that makes it
true.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = [needs_database, pytest.mark.integration]

TERM = "dano moral"


def volume(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/indicators/volume-by-court", params={"q": TERM, **params})
    assert response.status_code == 200, response.text
    return response.json()


def searched(client: TestClient, **params: Any) -> int:
    response = client.get("/decisions", params={"q": TERM, "page_size": 1, **params})
    assert response.status_code == 200, response.text
    return int(response.json()["total"])


@pytest.fixture
def spread(db_rolled_back: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    """
    Three courts, uneven on purpose so an order by count means something, and
    spread over three months so a period that drops one end counts differently
    from one that keeps it.
    """
    db_rolled_back.execute("DELETE FROM core.decisao")
    for abbreviation, count in (("STF", 1), ("STJ", 3), ("TRF1", 2)):
        register(db_rolled_back, abbreviation)
        for n in range(count):
            decide(db_rolled_back, abbreviation, f"{abbreviation}{n:04d}")
            db_rolled_back.execute(
                "UPDATE core.decisao SET data_referencia = %s "
                "WHERE identificador_fonte = %s",
                (f"2026-0{n + 2}-10", f"{abbreviation}{n:04d}"),
            )
    return db_rolled_back


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"tribunal": ["STJ"]},
        {"tribunal": ["STJ", "TRF1"]},
        {"tribunal": ["NAOEXISTE"]},
        {"date_from": "2026-02-01", "date_to": "2026-02-28"},
        {"date_from": "2026-03-01"},
        {"date_to": "2026-03-31"},
        {"date_from": "2030-01-01"},
    ],
    ids=[
        "all",
        "one court",
        "two courts",
        "unknown court",
        "one month",
        "open ended start",
        "open ended finish",
        "out of range",
    ],
)
def test_the_counts_add_up_to_what_the_search_reports(
    client: TestClient, spread: psycopg.Connection[DictRow], params: dict[str, Any]
) -> None:
    body = volume(client, **params)

    assert sum(court["decisions"] for court in body["courts"]) == body["total"]
    assert body["total"] == searched(client, **params)


def test_the_busiest_court_comes_first(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    body = volume(client)

    assert [court["abbreviation"] for court in body["courts"]] == ["STJ", "TRF1", "STF"]
    assert [court["decisions"] for court in body["courts"]] == [3, 2, 1]


def test_a_court_carries_its_registered_name(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    by_abbreviation = {c["abbreviation"]: c["name"] for c in volume(client)["courts"]}

    assert by_abbreviation["STJ"] == "Superior Tribunal de Justiça"


def test_a_court_nobody_registered_is_still_counted(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    """
    The list of courts leaves an unregistered one out, because every item there
    carries a name. Here it cannot be left out: dropping it would break the one
    thing this endpoint promises, which is that the counts add up. It falls back
    to the abbreviation for a name.
    """
    decide(spread, "STF", "ORFAO001")
    spread.execute(
        "UPDATE core.decisao SET tribunal_sigla = 'XXXX' WHERE identificador_fonte = 'ORFAO001'"
    )

    body = volume(client)
    found = {c["abbreviation"]: c for c in body["courts"]}

    assert "XXXX" in found
    assert found["XXXX"]["name"] == "XXXX"
    assert sum(c["decisions"] for c in body["courts"]) == body["total"]
    assert body["total"] == searched(client)


def test_a_search_with_no_match_answers_an_empty_list(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    response = client.get(
        "/indicators/volume-by-court", params={"q": "zzzznaoexistezzz"}
    )

    assert response.status_code == 200
    assert response.json() == {"total": 0, "courts": []}


def test_a_period_that_ends_before_it_starts_is_refused(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    """The narrowing is shared with the search, so its refusals are too."""
    response = client.get(
        "/indicators/volume-by-court",
        params={"q": TERM, "date_from": "2026-03-31", "date_to": "2026-03-01"},
    )

    assert response.status_code == 400


def test_the_endpoint_is_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/indicators/volume-by-court"]["get"]
    body = operation["responses"]["200"]["content"]["application/json"]["schema"]
    named = schema["components"]["schemas"][body["$ref"].rsplit("/", 1)[-1]]

    assert set(named["properties"]) == {"total", "courts"}
    assert {p["name"] for p in operation["parameters"]} >= {
        "q",
        "tribunal",
        "date_from",
        "date_to",
        "published_from",
        "published_to",
    }
