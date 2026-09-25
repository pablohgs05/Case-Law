from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api.decisions import DEFAULT_ORDER, ORDERINGS, _page_sql
from app.db import get_connection
from app.main import app
from tests.conftest import needs_database

pytestmark = [needs_database, pytest.mark.integration]

TERM = "fiduciária OR apelação"


@pytest.fixture
def client(db: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def dates(client: TestClient, **params: str | int) -> list[str]:
    body = client.get("/decisions", params={"q": TERM, **params}).json()
    return [r["decided_on"] for r in body["results"]]


def identifiers(client: TestClient, **params: str | int) -> list[str]:
    body = client.get("/decisions", params={"q": TERM, **params}).json()
    return [r["identifier"] for r in body["results"]]


def test_both_orderings_are_accepted(client: TestClient) -> None:
    for order in ORDERINGS:
        response = client.get("/decisions", params={"q": TERM, "order": order})
        assert response.status_code == 200, order


def test_relevance_is_what_you_get_without_asking(client: TestClient) -> None:
    assert DEFAULT_ORDER == "relevance"
    assert dates(client) == dates(client, order="relevance")


def test_ordering_by_date_puts_the_most_recent_first(client: TestClient) -> None:
    served = dates(client, order="date")

    assert served
    assert served == sorted(served, reverse=True)


def test_the_two_orderings_are_not_the_same_answer(client: TestClient) -> None:
    """
    Guards the guard: if the fixture ever stops telling them apart, the tests
    above pass while the parameter does nothing.
    """
    assert (
        dates(client, order="date") != dates(client, order="relevance")
        or len(dates(client)) < 2
    )


def test_a_value_nobody_offers_is_refused_without_a_stack_trace(
    client: TestClient,
) -> None:
    for order in ("xpto", "", "relevancia", "DATE", "date; DROP TABLE core.decisao"):
        response = client.get("/decisions", params={"q": TERM, "order": order})

        assert 400 <= response.status_code < 500, order
        assert response.status_code != 500


def test_the_refusal_says_which_values_exist(client: TestClient) -> None:
    body = client.get("/decisions", params={"q": TERM, "order": "xpto"}).json()

    assert "relevance" in str(body)
    assert "date" in str(body)


def test_every_ordering_ends_on_the_same_tiebreak(client: TestClient) -> None:
    """
    A page boundary that falls inside a tie repeats or drops a decision when
    the reader turns the page.
    """
    for clause in ORDERINGS.values():
        assert clause.strip().endswith("identificador_fonte DESC")


def test_the_ordering_is_chosen_from_a_closed_set_not_built_from_input(
    client: TestClient,
) -> None:
    for clause in ORDERINGS.values():
        sql = _page_sql("", clause)
        assert clause.strip() in sql
        assert "%(order)s" not in sql


def test_paging_keeps_the_ordering(client: TestClient) -> None:
    primeira = dates(client, order="date", page=1, page_size=2)
    segunda = dates(client, order="date", page=2, page_size=2)

    assert primeira == sorted(primeira, reverse=True)
    if segunda:
        assert primeira[-1] >= segunda[0]
