"""
Ordering under filters, run against PostgreSQL.

Each works alone and is tested alone. What this file asks is whether the
sequence survives being narrowed: filters rewrite the WHERE of the same
statement the ordering rewrites the ORDER BY of, and a sequence that only holds
without filters would look right in every test that never combines them.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database

pytestmark = [needs_database, pytest.mark.integration]

TERM = "dano moral"

# A second court interleaved with the first, so filtering by court changes which
# dates are on screen. The identifiers deliberately run against the dates: they
# are what breaks a tie, so aligning them would let a sequence that ignored the
# order come out looking right.
EXTRA = """
INSERT INTO core.decisao (
    fonte_codigo, identificador_fonte, tribunal_sigla, data_referencia,
    ementa, turma_recursal, possui_inteiro_teor, url_fonte, ementa_busca
)
SELECT fonte, identificador, 'STJ', dia::date, ementa, FALSE, FALSE,
       'https://example.com/' || identificador,
       TO_TSVECTOR('portugues_sem_acento', ementa)
FROM (VALUES
    ('stj-teste', '7000003', '2026-02-01', 'CIVIL. Dano moral em fevereiro.'),
    ('stj-teste', '7000001', '2026-04-01', 'CIVIL. Dano moral em abril.'),
    ('stj-teste', '7000002', '2026-07-01', 'CIVIL. Dano moral em julho.')
) AS extra (fonte, identificador, dia, ementa)
"""


@pytest.fixture
def mixed(db_rolled_back: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    db_rolled_back.execute(EXTRA)
    return db_rolled_back


def page(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get("/decisions", params={"q": TERM, "page_size": 50, **params})
    assert response.status_code == 200, response.text
    return response.json()["results"]


def dates(results: list[dict[str, Any]]) -> list[str]:
    return [r["decided_on"] for r in results]


def test_the_date_sequence_holds_inside_a_court(
    client: TestClient, mixed: psycopg.Connection[DictRow]
) -> None:
    served = page(client, order="date", tribunal="STJ")

    assert dates(served) == ["2026-07-01", "2026-04-01", "2026-02-01"]
    assert {r["court"] for r in served} == {"STJ"}


def test_the_date_sequence_holds_inside_a_period(
    client: TestClient, mixed: psycopg.Connection[DictRow]
) -> None:
    served = page(client, order="date", date_from="2026-02-01", date_to="2026-04-30")

    assert dates(served) == sorted(dates(served), reverse=True)
    assert served, "the period matched nothing, so it would prove nothing"
    assert all("2026-02-01" <= d <= "2026-04-30" for d in dates(served))


def test_the_order_still_decides_when_a_filter_narrows(
    client: TestClient, mixed: psycopg.Connection[DictRow]
) -> None:
    """
    A filter that swallowed the ordering would answer the same sequence for
    both, and every assertion about one of them would still pass.
    """
    by_relevance = page(client, tribunal=["TJDFT", "STJ"])
    by_date = page(client, tribunal=["TJDFT", "STJ"], order="date")

    assert {r["identifier"] for r in by_relevance} == {r["identifier"] for r in by_date}
    assert [r["identifier"] for r in by_relevance] != [r["identifier"] for r in by_date]
    assert dates(by_date) == sorted(dates(by_date), reverse=True)


def test_narrowing_does_not_reshuffle_what_it_keeps(
    client: TestClient, mixed: psycopg.Connection[DictRow]
) -> None:
    """
    The decisions a filter keeps have to come back in the order they were in
    before it was applied. Anything else means the filter is deciding the
    sequence.
    """
    everything = [r["identifier"] for r in page(client, order="date")]
    only_stj = [r["identifier"] for r in page(client, order="date", tribunal="STJ")]

    assert only_stj == [i for i in everything if i in set(only_stj)]
    assert len(only_stj) == 3


def test_the_sequence_survives_being_paged_under_a_filter(
    client: TestClient, mixed: psycopg.Connection[DictRow]
) -> None:
    """
    Three at a time, because the boundary between pages is where an ordering
    that forgets the filter shows up as a repeat or a gap.
    """
    whole = [r["identifier"] for r in page(client, order="date")]
    walked: list[str] = []
    for number in (1, 2, 3, 4):
        walked += [
            r["identifier"]
            for r in page(client, order="date", page=number, page_size=3)
        ]

    assert walked == whole
    assert len(walked) == len(set(walked))
