"""
The search's decisions counted by judging body and by reporting judge.

The promise is that every slice opens onto exactly the decisions that produced
it — the named ones through the search's own filter, the folded rest through
the exclusion filter — and that the slices add up to the search's total. So
these compare each count with what `/decisions` answers for the same slice.
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

# (court, judging body, reporting judge, how many). Two spellings of one judge
# on purpose, a missing and a blank value on purpose, and a tie between C and D.
SPREAD: list[tuple[str, str | None, str | None, int]] = [
    ("STJ", "CORTE ESPECIAL", "JOÃO SILVA", 5),
    ("STJ", "TERCEIRA TURMA", "JOAO SILVA", 3),
    ("STJ", "TERCEIRA TURMA", "MARIA SOUZA", 1),
    ("STJ", "QUARTA TURMA", "MARIA SOUZA", 2),
    ("TRF1", "SEXTA TURMA", "PEDRO LIMA", 2),
    ("TRF1", "PRIMEIRA TURMA", "ANA COSTA", 1),
    ("TRF1", None, "ANA COSTA", 1),
    ("TRF1", "   ", None, 1),
]
TOTAL = sum(n for *_, n in SPREAD)


def concentration(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/indicators/concentration", params={"q": TERM, **params})
    assert response.status_code == 200, response.text
    return response.json()


def searched(client: TestClient, **params: Any) -> int:
    response = client.get("/decisions", params={"q": TERM, "page_size": 1, **params})
    assert response.status_code == 200, response.text
    return int(response.json()["total"])


@pytest.fixture
def spread(db_rolled_back: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    register(db_rolled_back, "TRF1")

    for index, (court, body, judge, how_many) in enumerate(SPREAD):
        for n in range(how_many):
            identifier = f"{court}-{index}-{n}"
            decide(db_rolled_back, court, identifier)
            db_rolled_back.execute(
                "UPDATE core.decisao SET orgao_julgador = %s, relator = %s "
                "WHERE identificador_fonte = %s",
                (body, judge, identifier),
            )
    return db_rolled_back


@pytest.fixture
def client(spread: psycopg.Connection[DictRow]) -> Any:
    from app.db import get_connection
    from app.main import app

    app.dependency_overrides[get_connection] = lambda: spread
    yield TestClient(app)
    app.dependency_overrides.clear()


DIMENSIONS = [
    ("judging_bodies", "orgao_julgador", "orgao_julgador_excluido"),
    ("reporting_judges", "relator", "relator_excluido"),
]


def test_the_cut_is_the_search_s_own(client: TestClient) -> None:
    body = concentration(client)

    assert body["total"] == TOTAL == searched(client)


@pytest.mark.parametrize("dimension", ["judging_bodies", "reporting_judges"])
@pytest.mark.parametrize("limit", [1, 2, 5, 20])
def test_the_slices_add_up_to_the_total(
    client: TestClient, dimension: str, limit: int
) -> None:
    body = concentration(client, limit=limit)
    part = body[dimension]

    counted = sum(group["decisions"] for group in part["groups"])
    rest = part["other"]["decisions"] if part["other"] else 0

    assert counted + rest == body["total"]
    assert len(part["groups"]) <= limit


def test_the_largest_groups_come_first_and_the_rest_is_one_group(
    client: TestClient,
) -> None:
    body = concentration(client, limit=2)
    bodies = body["judging_bodies"]

    assert [(g["name"], g["decisions"]) for g in bodies["groups"]] == [
        ("CORTE ESPECIAL", 5),
        ("TERCEIRA TURMA", 4),
    ]
    # QUARTA TURMA, SEXTA TURMA and PRIMEIRA TURMA, plus the missing and the
    # blank value, which name no group.
    assert bodies["other"] == {"groups": 3, "decisions": 7, "share": 43.8}
    assert bodies["missing"] == 2
    assert body["limit"] == 2


def test_a_tie_is_broken_by_name_so_the_rest_is_always_the_same(
    client: TestClient,
) -> None:
    bodies = concentration(client, limit=4)["judging_bodies"]

    assert [g["name"] for g in bodies["groups"]] == [
        "CORTE ESPECIAL",
        "TERCEIRA TURMA",
        "QUARTA TURMA",
        "SEXTA TURMA",
    ]


def test_the_share_is_over_the_whole_cut(client: TestClient) -> None:
    """
    5 of 16, not 5 of the 14 that carry a judging body: the missing values are
    part of the cut the reader searched.
    """
    first = concentration(client)["judging_bodies"]["groups"][0]

    assert first["share"] == 31.2


def test_a_judge_is_named_exactly_as_the_source_wrote_it(client: TestClient) -> None:
    """
    Merging the two spellings would count eight decisions that no option of
    the search's filter returns together.
    """
    judges = concentration(client, limit=20)["reporting_judges"]["groups"]

    assert {"name": "JOÃO SILVA", "decisions": 5, "share": 31.2} in judges
    assert {"name": "JOAO SILVA", "decisions": 3, "share": 18.8} in judges


def test_nothing_left_over_answers_no_other_group(client: TestClient) -> None:
    body = concentration(client, tribunal=["STJ"], limit=5)

    assert body["judging_bodies"]["other"] is None
    assert body["judging_bodies"]["missing"] == 0


def test_missing_values_are_counted_not_dropped(client: TestClient) -> None:
    body = concentration(client, limit=20)

    for dimension, expected_missing in (("judging_bodies", 2), ("reporting_judges", 1)):
        part = body[dimension]
        assert part["missing"] == expected_missing
        assert part["other"]["groups"] == 0
        assert part["other"]["decisions"] == expected_missing
        assert all(group["name"].strip() for group in part["groups"])


@pytest.mark.parametrize(("dimension", "filter_name", "_"), DIMENSIONS)
@pytest.mark.parametrize("limit", [2, 20])
def test_each_named_group_opens_exactly_its_decisions(
    client: TestClient, dimension: str, filter_name: str, _: str, limit: int
) -> None:
    for group in concentration(client, limit=limit)[dimension]["groups"]:
        assert searched(client, **{filter_name: [group["name"]]}) == group["decisions"]


@pytest.mark.parametrize(("dimension", "_", "exclusion"), DIMENSIONS)
@pytest.mark.parametrize("limit", [1, 2, 3, 20])
def test_the_other_group_opens_exactly_its_decisions(
    client: TestClient, dimension: str, _: str, exclusion: str, limit: int
) -> None:
    part = concentration(client, limit=limit)[dimension]
    ranked = [group["name"] for group in part["groups"]]

    assert part["other"] is not None
    assert searched(client, **{exclusion: ranked}) == part["other"]["decisions"]


@pytest.mark.parametrize(
    "params",
    [
        {"tribunal": ["TRF1"]},
        {"tribunal": ["STJ"], "relator": ["MARIA SOUZA"]},
        {"orgao_julgador": ["TERCEIRA TURMA", "QUARTA TURMA"]},
        {"relator": ["JOÃO SILVA", "PEDRO LIMA"]},
        {"date_from": "2026-01-01", "date_to": "2026-12-31"},
        {"date_from": "2027-01-01"},
        {"tribunal": ["NAOEXISTE"]},
    ],
    ids=[
        "court",
        "court and judge",
        "two bodies",
        "two judges",
        "period",
        "empty period",
        "unknown court",
    ],
)
def test_the_filters_narrow_the_indicator_and_the_slices_alike(
    client: TestClient, params: dict[str, Any]
) -> None:
    body = concentration(client, limit=1, **params)

    assert body["total"] == searched(client, **params)

    for dimension, filter_name, exclusion in DIMENSIONS:
        part = body[dimension]
        for group in part["groups"]:
            slice_params = {**params, filter_name: [group["name"]]}
            assert searched(client, **slice_params) == group["decisions"]
        if part["other"]:
            ranked = [group["name"] for group in part["groups"]]
            rest = searched(client, **params, **{exclusion: ranked})
            assert rest == part["other"]["decisions"]


def test_a_search_with_no_match_answers_zeros(client: TestClient) -> None:
    response = client.get(
        "/indicators/concentration", params={"q": "palavraquenaoexisteemlugarnenhum"}
    )

    assert response.status_code == 200
    empty: dict[str, Any] = {"groups": [], "other": None, "missing": 0}
    assert response.json() == {
        "total": 0,
        "limit": 5,
        "judging_bodies": empty,
        "reporting_judges": empty,
    }


@pytest.mark.parametrize("limit", [0, 21])
def test_a_limit_out_of_range_is_refused(client: TestClient, limit: int) -> None:
    response = client.get(
        "/indicators/concentration", params={"q": TERM, "limit": limit}
    )

    assert response.status_code == 422


def test_an_inverted_period_is_refused_as_the_search_refuses_it(
    client: TestClient,
) -> None:
    params = {"date_from": "2026-12-31", "date_to": "2026-01-01"}

    response = client.get("/indicators/concentration", params={"q": TERM, **params})

    assert response.status_code == 400
    assert (
        response.json() == client.get("/decisions", params={"q": TERM, **params}).json()
    )


def test_the_exclusion_filter_ignores_blank_values(client: TestClient) -> None:
    assert searched(client, relator_excluido=["  "]) == TOTAL


def test_the_endpoint_is_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/indicators/concentration"]["get"]
    names = {parameter["name"] for parameter in operation["parameters"]}

    assert {"q", "tribunal", "orgao_julgador", "relator", "limit"} <= names
    search = schema["paths"]["/decisions"]["get"]
    search_names = {parameter["name"] for parameter in search["parameters"]}
    assert {"orgao_julgador_excluido", "relator_excluido"} <= search_names
