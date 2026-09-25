"""
The court and date filters, run against PostgreSQL.

A fake database answers whatever the test tells it to, so it proves the filters
reach the query and nothing about what the query does with them. These send the
real statement to the real table.
"""

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.db import get_connection
from app.main import app
from tests.conftest import needs_database

pytestmark = needs_database

# The fixture holds only TJDFT. These add two more courts and put decisions on
# the edges of March 2026, so a bound that is exclusive by mistake loses one.
#
# Every test below searches "dano moral". What matches it, fixture included:
#
#                  decided_on  published
#   TJDFT 1000001  2026-03-10  2026-03-15
#   TJDFT 1000003  2026-05-05  2026-05-09
#   STJ   2000001  2026-03-01  —           first day of March
#   STJ   2000002  2026-03-31  2026-04-02  last day of March
#   TRF1  3000001  2026-03-10  —           a third court, left out of every union
#
# STJ 2000003 is in March and does not match, so it only turns up when the
# expression is ignored. The decisions with no publication date are the ones a
# publication period must leave out.
EXTRA = """
INSERT INTO core.decisao (
    fonte_codigo, identificador_fonte, tribunal_sigla, data_referencia,
    data_publicacao, ementa, turma_recursal, possui_inteiro_teor, url_fonte,
    ementa_busca
)
SELECT fonte, identificador, tribunal, dia::date, publicada::date, ementa,
       FALSE, FALSE, 'https://example.com/' || identificador,
       TO_TSVECTOR('portugues_sem_acento', ementa)
FROM (VALUES
    ('stj-teste',  '2000001', 'STJ',  '2026-03-01', NULL,
     'CIVIL. Dano moral configurado.'),
    ('stj-teste',  '2000002', 'STJ',  '2026-03-31', '2026-04-02',
     'CONSUMIDOR. Dano moral in re ipsa.'),
    ('stj-teste',  '2000003', 'STJ',  '2026-03-15', NULL,
     'PENAL. Usucapião extraordinário.'),
    ('trf1-teste', '3000001', 'TRF1', '2026-03-10', NULL,
     'ADMINISTRATIVO. Dano moral afastado.')
) AS extra (fonte, identificador, tribunal, dia, publicada, ementa)
"""

TJDFT = {"1000001", "1000003"}
STJ = {"2000001", "2000002"}
TRF1 = {"3000001"}


@pytest.fixture
def client(db: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    """
    The extra decisions exist only inside this test's transaction. The rollback
    sits in the teardown so a failing test cannot leave them behind for the ones
    that count the fixture.
    """
    with db.cursor() as cursor:
        cursor.execute(EXTRA)
    app.dependency_overrides[get_connection] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        db.rollback()


def search(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/decisions", params={"q": "dano moral", **params})
    assert response.status_code == 200, response.text
    return response.json()


def identifiers(body: dict[str, Any]) -> set[str]:
    return {result["identifier"] for result in body["results"]}


def test_one_court_returns_only_its_decisions(client: TestClient) -> None:
    body = search(client, tribunal="STJ")

    assert identifiers(body) == STJ
    assert body["total"] == len(STJ)
    assert {result["court"] for result in body["results"]} == {"STJ"}


def test_several_courts_return_their_union(client: TestClient) -> None:
    body = search(client, tribunal=["TJDFT", "STJ"])

    assert identifiers(body) == TJDFT | STJ
    assert body["total"] == len(TJDFT | STJ)


def test_a_court_with_no_decisions_returns_nothing(client: TestClient) -> None:
    body = search(client, tribunal="TRIBUNAL_INEXISTENTE")

    assert body["total"] == 0
    assert body["results"] == []


def test_the_court_is_compared_as_written(client: TestClient) -> None:
    assert search(client, tribunal="stj")["total"] == 0


def test_the_range_includes_both_ends(client: TestClient) -> None:
    body = search(client, date_from="2026-03-01", date_to="2026-03-31")

    assert identifiers(body) == {"1000001"} | STJ | TRF1
    assert {"2026-03-01", "2026-03-31"} <= {r["decided_on"] for r in body["results"]}


def test_the_same_day_on_both_ends_is_that_day(client: TestClient) -> None:
    body = search(client, date_from="2026-03-10", date_to="2026-03-10")

    assert identifiers(body) == {"1000001"} | TRF1


def test_date_from_alone_leaves_the_end_open(client: TestClient) -> None:
    body = search(client, date_from="2026-03-31")

    assert identifiers(body) == {"2000002", "1000003"}


def test_date_to_alone_leaves_the_start_open(client: TestClient) -> None:
    body = search(client, date_to="2026-03-01")

    assert identifiers(body) == {"2000001"}


def test_courts_dates_and_expression_narrow_together(client: TestClient) -> None:
    body = search(
        client,
        q='"dano moral"',
        tribunal=["STJ", "TRF1"],
        date_from="2026-03-05",
        date_to="2026-03-31",
    )

    # 2000001 is STJ and matches, but is before the range; 1000001 is in the
    # range and matches, but is TJDFT; 2000003 is STJ and in the range, but
    # does not match the expression.
    assert identifiers(body) == {"2000002", "3000001"}
    assert body["total"] == 2


def test_the_expression_still_applies_under_the_filters(client: TestClient) -> None:
    body = search(
        client,
        q="usucapiao",
        tribunal="STJ",
        date_from="2026-03-01",
        date_to="2026-03-31",
    )

    assert identifiers(body) == {"2000003"}


def test_without_filters_every_court_and_date_is_searched(
    client: TestClient,
) -> None:
    body = search(client)

    assert identifiers(body) == TJDFT | STJ | TRF1
    assert body["total"] == len(TJDFT | STJ | TRF1)


def test_blank_filters_are_the_same_as_none(client: TestClient) -> None:
    assert search(client, tribunal="") == search(client)


def test_the_total_counts_the_whole_cut_on_every_page(client: TestClient) -> None:
    union = TJDFT | STJ
    seen: set[str] = set()

    for page in range(1, len(union) + 1):
        body = search(client, tribunal=["TJDFT", "STJ"], page=page, page_size=1)
        assert body["total"] == len(union)
        assert len(body["results"]) == 1
        seen |= identifiers(body)

    assert seen == union

    past_the_end = search(
        client, tribunal=["TJDFT", "STJ"], page=len(union) + 1, page_size=1
    )
    assert past_the_end["total"] == len(union)
    assert past_the_end["results"] == []


def test_the_total_follows_the_dates_too(client: TestClient) -> None:
    body = search(
        client,
        tribunal="STJ",
        date_from="2026-03-01",
        date_to="2026-03-31",
        page_size=1,
    )

    assert body["total"] == len(STJ)
    assert len(body["results"]) == 1


def test_the_publication_period_reads_the_publication_date_not_the_judgement(
    client: TestClient,
) -> None:
    """
    1000001 was judged on the 10th and published on the 15th. Each period finds
    it on its own date and misses it on the other's.
    """
    assert identifiers(
        search(client, published_from="2026-03-15", published_to="2026-03-15")
    ) == {"1000001"}
    assert (
        identifiers(search(client, date_from="2026-03-15", date_to="2026-03-15"))
        == set()
    )
    assert "1000001" not in identifiers(
        search(client, published_from="2026-03-10", published_to="2026-03-10")
    )


def test_the_publication_period_includes_both_ends(client: TestClient) -> None:
    body = search(client, published_from="2026-03-15", published_to="2026-04-02")

    assert identifiers(body) == {"1000001", "2000002"}
    assert body["total"] == 2


def test_published_from_alone_leaves_the_end_open(client: TestClient) -> None:
    assert identifiers(search(client, published_from="2026-04-02")) == {
        "2000002",
        "1000003",
    }


def test_published_to_alone_leaves_the_start_open(client: TestClient) -> None:
    assert identifiers(search(client, published_to="2026-03-15")) == {"1000001"}


def test_a_decision_without_a_publication_date_is_left_out_of_that_period(
    client: TestClient,
) -> None:
    body = search(client, published_from="2000-01-01")

    # 2000001 and 3000001 match the expression and have no publication date.
    assert identifiers(body) == {"1000001", "1000003", "2000002"}


def test_both_periods_courts_and_expression_narrow_together(client: TestClient) -> None:
    body = search(
        client,
        tribunal=["TJDFT", "STJ"],
        date_from="2026-03-01",
        date_to="2026-03-31",
        published_from="2026-04-01",
        published_to="2026-04-30",
    )

    # Judged in March: 1000001, 2000001, 2000002 (and 3000001, from TRF1).
    # Published in April: only 2000002.
    assert identifiers(body) == {"2000002"}
    assert body["total"] == 1


def test_an_inverted_publication_period_is_refused(client: TestClient) -> None:
    response = client.get(
        "/decisions",
        params={
            "q": "dano moral",
            "published_from": "2026-03-31",
            "published_to": "2026-03-01",
        },
    )

    assert response.status_code == 400
    assert "published_from" in response.json()["detail"]


def test_a_publication_date_that_is_not_a_day_is_refused(client: TestClient) -> None:
    response = client.get(
        "/decisions", params={"q": "dano moral", "published_to": "31/03/2026"}
    )

    assert response.status_code == 422


def test_an_inverted_range_is_refused(client: TestClient) -> None:
    response = client.get(
        "/decisions",
        params={"q": "dano moral", "date_from": "2026-03-31", "date_to": "2026-03-01"},
    )

    assert response.status_code == 400


@pytest.mark.parametrize("value", ["2026-02-30", "31/03/2026", "ontem"])
def test_a_date_that_is_not_a_day_is_refused(client: TestClient, value: str) -> None:
    response = client.get("/decisions", params={"q": "dano moral", "date_from": value})

    assert response.status_code == 422
