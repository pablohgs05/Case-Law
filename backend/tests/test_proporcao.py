"""
The search's decisions counted by what the court decided, against PostgreSQL.

The promise is the denominator. A share is taken over the decisions whose
dispositive stated an outcome, not over the cut, and the two only stay honest
if the endpoint reports both — so these count them against the real statement
over the real tables.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = needs_database

TERM = "dano moral"


def share(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/indicators/outcome-share", params={"q": TERM, **params})
    assert response.status_code == 200, response.text
    return response.json()


def searched(client: TestClient, **params: Any) -> int:
    response = client.get("/decisions", params={"q": TERM, "page_size": 1, **params})
    assert response.status_code == 200, response.text
    return int(response.json()["total"])


@pytest.fixture
def mixed(db_rolled_back: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    """
    Four readings and one the dispositive never stated, so the denominator is
    smaller than the cut and a share taken over the wrong one is visible.
    """
    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    register(db_rolled_back, "TRF1")

    spread = [
        ("STJ", "negado", 4),
        ("STJ", "provido", 2),
        ("STJ", "parcialmente_provido", 1),
        ("STJ", None, 3),
        ("TRF1", "negado", 2),
    ]
    for court, outcome, how_many in spread:
        for n in range(how_many):
            identifier = f"{court}-{outcome}-{n}"
            decide(db_rolled_back, court, identifier)
            db_rolled_back.execute(
                "UPDATE core.decisao SET resultado = %s WHERE identificador_fonte = %s",
                (outcome, identifier),
            )
    return db_rolled_back


@pytest.fixture
def client(mixed: psycopg.Connection[DictRow]) -> Any:
    from app.db import get_connection
    from app.main import app

    app.dependency_overrides[get_connection] = lambda: mixed
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_the_parts_add_up_to_the_denominator(client: TestClient) -> None:
    body = share(client)

    counted = sum(row["decisions"] for row in body["outcomes"])

    assert counted == body["classified"]
    assert body["classified"] + body["unclassified"] == body["total"]


def test_the_cut_is_the_search_s_own(client: TestClient) -> None:
    """
    The two read through the same builder. A count that disagreed with the
    number beside the results would make one of the two a lie, and the reader
    has no way to tell which.
    """
    assert share(client)["total"] == searched(client)


def test_the_denominator_is_smaller_than_the_cut_when_something_went_unread(
    client: TestClient,
) -> None:
    """
    Taking the share over the cut instead would read 33,3% denied where 40,0%
    were, and the error grows with whatever the courts stop declaring.
    """
    body = share(client)

    assert body["total"] == 12
    assert body["classified"] == 9
    assert body["unclassified"] == 3

    denied = next(row for row in body["outcomes"] if row["outcome"] == "negado")
    assert denied["decisions"] == 6
    assert denied["share"] == pytest.approx(66.7, abs=0.1)


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"tribunal": ["STJ"]},
        {"tribunal": ["STJ", "TRF1"]},
        {"tribunal": ["NAOEXISTE"]},
    ],
    ids=["all", "one court", "two courts", "unknown court"],
)
def test_a_filter_narrows_the_indicator_and_the_search_alike(
    client: TestClient, params: dict[str, Any]
) -> None:
    body = share(client, **params)

    assert body["total"] == searched(client, **params)
    assert body["classified"] + body["unclassified"] == body["total"]


def test_a_search_with_no_match_answers_zeros(client: TestClient) -> None:
    response = client.get(
        "/indicators/outcome-share", params={"q": "palavraquenaoexisteemlugarnenhum"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"total": 0, "classified": 0, "unclassified": 0, "outcomes": []}


def test_a_cut_nothing_could_be_read_from_is_an_answer_not_an_error(
    client: TestClient, mixed: psycopg.Connection[DictRow]
) -> None:
    """
    Every decision matched and none stated an outcome. The denominator is zero
    and the cut is not: the screen has to be able to say which of the two it is.
    """
    mixed.execute("UPDATE core.decisao SET resultado = NULL")

    body = share(client)

    assert body["total"] == 12
    assert body["classified"] == 0
    assert body["unclassified"] == 12
    assert all(row["decisions"] == 0 for row in body["outcomes"])
    assert all(row["share"] == 0 for row in body["outcomes"])


def test_every_outcome_the_model_records_is_answered_even_at_zero(
    client: TestClient, mixed: psycopg.Connection[DictRow]
) -> None:
    """
    A category missing from the cut would take its slice off the chart, and an
    absent slice reads the same as one nobody drew.
    """
    mixed.execute(
        "UPDATE core.decisao SET resultado = 'negado' WHERE resultado IS NOT NULL"
    )

    outcomes = {row["outcome"]: row["decisions"] for row in share(client)["outcomes"]}

    assert outcomes == {"negado": 9, "provido": 0, "parcialmente_provido": 0}


def test_the_endpoint_is_documented(client: TestClient) -> None:
    described = client.get("/openapi.json").json()["paths"]["/indicators/outcome-share"]

    assert described["get"]["summary"]
    assert "200" in described["get"]["responses"]


@pytest.mark.parametrize(
    "outcome,expected", [("negado", 6), ("provido", 2), ("parcialmente_provido", 1)]
)
def test_selecting_a_category_returns_exactly_its_decisions(
    client: TestClient, outcome: str, expected: int
) -> None:
    original = share(client)
    category = next(row for row in original["outcomes"] if row["outcome"] == outcome)
    assert searched(client, resultado=[outcome]) == category["decisions"] == expected
    assert expected < original["total"]
    for endpoint in ("volume-by-court", "volume-by-period", "outcome-share"):
        response = client.get(
            f"/indicators/{endpoint}", params={"q": TERM, "resultado": outcome}
        )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == expected


@pytest.mark.parametrize(
    "values,expected",
    [
        (["negado", "provido"], 8),
        ([" negado ", "negado", "", "  "], 6),
        (["inexistente"], 0),
        (["negado", "inexistente"], 6),
        (["", "  "], 12),
    ],
)
def test_outcome_values_are_a_union_without_duplicates(
    client: TestClient, values: list[str], expected: int
) -> None:
    assert searched(client, resultado=values) == expected
    assert share(client, resultado=values)["total"] == expected


def test_outcome_adds_to_every_existing_filter(
    client: TestClient, mixed: psycopg.Connection[DictRow]
) -> None:
    mixed.execute(
        """UPDATE core.decisao SET orgao_julgador = 'CORTE ESPECIAL', relator = 'RELATOR A', classe_cnj = 198, data_referencia = '2026-03-31', data_publicacao = '2026-04-01' WHERE tribunal_sigla = 'STJ' AND resultado = 'negado'"""
    )
    params: dict[str, Any] = {
        "tribunal": ["STJ"],
        "orgao_julgador": ["CORTE ESPECIAL"],
        "relator": ["RELATOR A"],
        "classe_cnj": [198],
        "date_from": "2026-03-31",
        "date_to": "2026-03-31",
        "published_from": "2026-04-01",
        "published_to": "2026-04-01",
        "resultado": ["negado"],
    }
    assert searched(client, **params) == 4
    for endpoint in ("volume-by-court", "volume-by-period", "outcome-share"):
        response = client.get(f"/indicators/{endpoint}", params={"q": TERM, **params})
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 4
    for change in (
        {"resultado": ["provido"]},
        {"tribunal": ["TRF1"]},
        {"orgao_julgador": ["OUTRO ORGAO"]},
        {"relator": ["OUTRO RELATOR"]},
        {"classe_cnj": [213]},
        {"date_from": "2026-04-01", "date_to": "2026-04-01"},
        {"published_from": "2026-04-02", "published_to": "2026-04-02"},
        {"q": "termoausentezzzz"},
    ):
        narrowed = {"q": TERM, **params, **change}
        response = client.get("/decisions", params=narrowed)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 0
        temporal = client.get("/indicators/volume-by-period", params=narrowed)
        assert temporal.status_code == 200, temporal.text
        assert temporal.json()["total"] == 0


@pytest.mark.parametrize(
    "endpoint",
    [
        "/decisions",
        "/indicators/volume-by-court",
        "/indicators/volume-by-period",
        "/indicators/outcome-share",
    ],
)
def test_outcome_is_documented_as_a_repeatable_optional_parameter(
    client: TestClient, endpoint: str
) -> None:
    parameters = client.get("/openapi.json").json()["paths"][endpoint]["get"][
        "parameters"
    ]
    outcome = next(p for p in parameters if p["name"] == "resultado")
    assert not outcome.get("required", False)
    assert outcome["description"]
    assert any(schema.get("type") == "array" for schema in outcome["schema"]["anyOf"])
