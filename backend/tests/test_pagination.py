"""
Paging the search, run against PostgreSQL.

Stability is a property of the database's plan, not of the Python around it: a
fake that answers whatever it is told proves nothing about whether two pages of
the same search overlap. These send the real statement to the real table.

The twelve decisions below tie on everything an ordering looks at — one ementa,
so `ts_rank` gives them a single rank, and one day, so the date ordering has
nothing to separate them either. Two collections carry the same six identifiers
on purpose: an ordering that breaks the tie on the identifier alone still has
six pairs left for the plan to serve in whatever order it likes.
"""

from collections.abc import Iterator
from itertools import pairwise
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api.decisions import ORDERINGS
from app.config import settings
from app.db import get_connection
from app.main import app
from tests.conftest import needs_database

pytestmark = [needs_database, pytest.mark.integration]

TERM = "usufruto"
EMENTA = "DIREITO CIVIL. Usufruto vitalício instituído por escritura pública."

TIED = f"""
INSERT INTO core.decisao (
    fonte_codigo, identificador_fonte, tribunal_sigla, data_referencia,
    ementa, turma_recursal, possui_inteiro_teor, url_fonte, ementa_busca
)
SELECT colecao.fonte,
       LPAD(serie.n::text, 7, '0'),
       colecao.tribunal,
       '2026-02-09'::date,
       '{EMENTA}',
       FALSE,
       FALSE,
       'https://example.com/' || colecao.fonte || '/' || serie.n,
       TO_TSVECTOR('portugues_sem_acento', '{EMENTA}')
FROM (VALUES ('tjdft-empate', 'TJDFT'), ('stj-empate', 'STJ'))
         AS colecao (fonte, tribunal),
     GENERATE_SERIES(1, 6) AS serie (n)
"""

TOTAL = 12


@pytest.fixture
def client(db: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    with db.cursor() as cursor:
        cursor.execute(TIED)
    app.dependency_overrides[get_connection] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        db.rollback()


def search(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/decisions", params={"q": TERM, **params})
    assert response.status_code == 200, response.text
    return response.json()


def search_response(client: TestClient, **params: Any) -> Any:
    """Whatever came back, refusal included, for the tests about refusals."""
    return client.get("/decisions", params={"q": TERM, **params})


def keys(body: dict[str, Any]) -> list[tuple[str, str]]:
    return [(result["source"], result["identifier"]) for result in body["results"]]


def walk(client: TestClient, page_size: int, **params: Any) -> list[tuple[str, str]]:
    """Every page of one search, in order, up to the first empty one."""
    served: list[tuple[str, str]] = []
    for page in range(1, TOTAL + 2):
        body = search(client, page=page, page_size=page_size, **params)
        if not body["results"]:
            break
        served.extend(keys(body))
    return served


def test_the_collection_really_ties(client: TestClient) -> None:
    """
    Guards the guard. If these ever stop tying, every test below runs over a
    collection no ordering could get wrong, and passes for the wrong reason.
    """
    body = search(client, page_size=TOTAL)

    assert body["total"] == TOTAL
    assert len({result["decided_on"] for result in body["results"]}) == 1
    assert len({identifier for _, identifier in keys(body)}) == TOTAL // 2


def test_a_page_carries_the_size_it_was_asked_for(client: TestClient) -> None:
    body = search(client, page=2, page_size=5)

    assert body["page"] == 2
    assert body["page_size"] == 5
    assert len(body["results"]) == 5


@pytest.mark.parametrize("order", sorted(ORDERINGS))
@pytest.mark.parametrize("page_size", [1, 5, TOTAL])
def test_the_pages_add_up_to_the_total_with_nothing_repeated(
    client: TestClient, page_size: int, order: str
) -> None:
    served = walk(client, page_size, order=order)

    assert len(served) == TOTAL
    assert len(set(served)) == TOTAL


def test_a_decision_never_lands_on_two_pages(client: TestClient) -> None:
    first = set(keys(search(client, page=1, page_size=4)))
    second = set(keys(search(client, page=2, page_size=4)))
    third = set(keys(search(client, page=3, page_size=4)))

    assert not first & second
    assert not second & third
    assert not first & third


@pytest.mark.parametrize("order", sorted(ORDERINGS))
def test_tied_decisions_come_back_in_the_same_order_every_time(
    client: TestClient, order: str
) -> None:
    assert walk(client, 3, order=order) == walk(client, 3, order=order)


@pytest.mark.parametrize("order", sorted(ORDERINGS))
def test_the_sequence_does_not_change_with_the_page_size(
    client: TestClient, order: str
) -> None:
    """
    A tie the database is free to break as it likes shows up here as two walks
    holding the same twelve decisions in a different sequence.
    """
    assert walk(client, 1, order=order) == walk(client, 5, order=order)


def test_the_first_page_starts_at_one(client: TestClient) -> None:
    body = search(client, page=1, page_size=5)

    assert body["range_from"] == 1
    assert body["range_to"] == 5


def test_the_range_says_where_the_page_sits_in_the_total(client: TestClient) -> None:
    body = search(client, page=2, page_size=5)

    assert body["range_from"] == 6
    assert body["range_to"] == 10


def test_the_last_page_ends_on_the_total(client: TestClient) -> None:
    body = search(client, page=3, page_size=5)

    assert len(body["results"]) == 2
    assert body["range_from"] == 11
    assert body["range_to"] == body["total"] == TOTAL


def test_a_page_past_the_end_is_empty_and_not_an_error(client: TestClient) -> None:
    body = search(client, page=4, page_size=5)

    assert body["results"] == []
    assert body["total"] == TOTAL
    assert body["range_from"] is None
    assert body["range_to"] is None


def test_a_page_number_past_what_the_database_can_count_is_empty_too(
    client: TestClient,
) -> None:
    """
    An offset larger than a bigint came back as a 400 about stray control
    characters. It is a page past the end like any other.
    """
    body = search(client, page=10**30, page_size=5)

    assert body["results"] == []
    assert body["total"] == TOTAL
    assert body["range_from"] is None


def test_a_page_size_above_the_maximum_is_served_at_the_maximum(
    client: TestClient,
) -> None:
    body = search(client, page_size=settings.search_max_page_size + 500)

    assert body["page_size"] == settings.search_max_page_size
    assert len(body["results"]) == TOTAL
    assert body["range_to"] == TOTAL


def test_the_filter_and_the_order_travel_with_the_page(client: TestClient) -> None:
    served = walk(client, 3, order="date", tribunal="STJ")

    assert len(served) == TOTAL // 2
    assert len(set(served)) == len(served)
    assert {source for source, _ in served} == {"stj-empate"}


def test_the_total_counts_the_whole_cut_and_not_the_page(client: TestClient) -> None:
    for page_size in (1, 5, TOTAL):
        assert search(client, page_size=page_size)["total"] == TOTAL


def test_a_page_size_below_one_is_refused(client: TestClient) -> None:
    """
    The maximum is capped in silence because asking for too much is a request
    the API can still honour. Zero and below are not: there is no page of zero
    results to serve, and answering an empty one would read as the end.
    """
    for page_size in (0, -1, -20):
        response = search_response(client, page=1, page_size=page_size)

        assert response.status_code == 422, page_size


def test_the_ranges_walk_the_total_without_a_gap(client: TestClient) -> None:
    """
    Each page says where it sits, and the screen adds the number beside the
    results from it. Read one after another they have to meet end to end: a gap
    or an overlap is a count the reader can catch by paging twice.
    """
    seen: list[tuple[int, int]] = []
    for page in range(1, TOTAL + 2):
        body = search(client, page=page, page_size=4)
        if not body["results"]:
            assert body["range_from"] is None
            assert body["range_to"] is None
            break
        seen.append((body["range_from"], body["range_to"]))

    assert seen[0][0] == 1
    assert seen[-1][1] == TOTAL
    for (_, ends), (starts, _) in pairwise(seen):
        assert starts == ends + 1


def test_the_range_counts_what_the_page_actually_carries(client: TestClient) -> None:
    for page_size in (1, 4, TOTAL):
        for page in range(1, 3):
            body = search(client, page=page, page_size=page_size)
            if not body["results"]:
                continue

            carried = body["range_to"] - body["range_from"] + 1
            assert carried == len(body["results"]), (page, page_size)
