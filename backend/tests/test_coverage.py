"""
What the base covers as a whole, run against PostgreSQL.

The panel is read before anyone trusts a search, so the numbers have to come
from the rows rather than from a fixture that agrees with itself.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import FIXTURES, needs_database
from tests.test_courts import decide, register
from tests.test_seal_filter import transformation

pytestmark = [needs_database, pytest.mark.integration]


def coverage(client: TestClient) -> dict[str, Any]:
    response = client.get("/indicators/coverage")
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def two_courts(
    db_rolled_back: psycopg.Connection[DictRow],
) -> psycopg.Connection[DictRow]:
    """
    One court reaching back years and one holding a single recent month, which
    is the shape the base actually has and the reason each period is reported.
    """
    db_rolled_back.execute("DELETE FROM core.decisao")
    for abbreviation, dates in (
        ("STJ", ("1998-04-02", "2012-07-19", "2026-08-26")),
        ("TRF1", ("2026-09-01", "2026-09-17")),
    ):
        register(db_rolled_back, abbreviation)
        for n, day in enumerate(dates):
            identifier = f"{abbreviation}{n:04d}"
            decide(db_rolled_back, abbreviation, identifier)
            db_rolled_back.execute(
                "UPDATE core.decisao SET data_referencia = %s "
                "WHERE identificador_fonte = %s",
                (day, identifier),
            )
    return db_rolled_back


def test_it_counts_every_decision_in_the_base(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    body = coverage(client)

    assert body["documents"] == 5
    assert sum(court["documents"] for court in body["courts"]) == body["documents"]


def test_each_court_carries_its_own_period(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    """
    The reason the panel reports them separately. One court reaching back to
    1998 does not mean the base covers 1998 for the other, and a single span
    over both would say exactly that.
    """
    by_abbreviation = {c["abbreviation"]: c for c in coverage(client)["courts"]}

    assert by_abbreviation["STJ"]["first"] == "1998-04-02"
    assert by_abbreviation["STJ"]["last"] == "2026-08-26"
    assert by_abbreviation["TRF1"]["first"] == "2026-09-01"
    assert by_abbreviation["TRF1"]["last"] == "2026-09-17"


def test_the_span_reaches_from_the_oldest_to_the_newest(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    body = coverage(client)

    assert body["first"] == "1998-04-02"
    assert body["last"] == "2026-09-17"


def test_the_largest_court_comes_first(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    assert [c["abbreviation"] for c in coverage(client)["courts"]] == ["STJ", "TRF1"]


def test_an_empty_base_answers_rather_than_fails(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """A new environment is not a broken one, so it gets an answer."""
    db_rolled_back.execute("DELETE FROM core.decisao")

    body = coverage(client)

    assert body["documents"] == 0
    assert body["courts"] == []
    assert body["first"] is None
    assert body["last"] is None


def test_the_freshness_agrees_with_the_endpoint_that_reports_it(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    """Both read it from the same place, so they cannot tell different stories."""
    body = coverage(client)
    reported = client.get("/indicators/last-update").json()

    assert body["state"] == reported["state"]
    assert body["updated_at"] == reported["updated_at"]


def test_the_endpoint_is_documented(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/indicators/coverage"]["get"]
    body = operation["responses"]["200"]["content"]["application/json"]["schema"]
    named = schema["components"]["schemas"][body["$ref"].rsplit("/", 1)[-1]]

    assert set(named["properties"]) == {
        "documents",
        "first",
        "last",
        "courts",
        "state",
        "updated_at",
    }


def rebuild_core(db: psycopg.Connection[DictRow], unseal: bool = False) -> None:
    """
    Replace core.decisao with what the model builds from the raw rows.

    Counting the fixture's own table would count rows the fixture chose.
    Building it from the model counts the ones the transformation let through,
    which is the question the seal raises.
    """
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    if unseal:
        db.execute('UPDATE raw.acordao_tjdft SET "segredoJustica" = FALSE')
    db.execute("DROP TABLE IF EXISTS core.decisao CASCADE")
    db.execute(f"CREATE TABLE core.decisao AS {transformation()}")


def tjdft(body: dict[str, Any]) -> dict[str, Any]:
    """The court whose collection carries the seal flag."""
    found = [c for c in body["courts"] if c["abbreviation"] == "TJDFT"]
    assert found, "the TJDFT left the answer, so the seal proves nothing here"
    return found[0]


def collected(db: psycopg.Connection[DictRow]) -> tuple[int, int]:
    """How many the source gave, and how many of those are sealed."""
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS total, "
            'COUNT(*) FILTER (WHERE "segredoJustica") AS sob_sigilo '
            "FROM raw.acordao_tjdft"
        )
        row = cursor.fetchone() or {"total": 0, "sob_sigilo": 0}
    return row["total"], row["sob_sigilo"]


def test_a_sealed_record_is_never_counted(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    The check that goes unnoticed. A sealed decision cannot be searched, so
    counting it would promise a reach nobody can use: the number would be right
    about the rows and wrong about the product.
    """
    rebuild_core(db_rolled_back)
    total, sealed = collected(db_rolled_back)
    body = coverage(client)

    assert sealed > 0, "no sealed record in the fixture, so this proves nothing"
    assert tjdft(body)["documents"] == total - sealed
    assert body["documents"] == sum(c["documents"] for c in body["courts"])


def test_the_count_follows_the_seal_and_not_the_fixture(
    client: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    Guards the guard. Unsealing the same records has to raise the count by
    exactly as many as were sealed — otherwise the test above would agree with
    a transformation that had stopped filtering.
    """
    rebuild_core(db_rolled_back)
    _, sealed = collected(db_rolled_back)
    before = tjdft(coverage(client))["documents"]

    rebuild_core(db_rolled_back, unseal=True)

    assert tjdft(coverage(client))["documents"] == before + sealed


def test_the_four_values_answer_a_base_of_known_content(
    client: TestClient, two_courts: psycopg.Connection[DictRow]
) -> None:
    """
    The four the card asks for, read together: how many documents, how many
    courts, what period, and when it was last refreshed.
    """
    body = coverage(client)

    assert body["documents"] == 5
    assert len(body["courts"]) == 2
    assert (body["first"], body["last"]) == ("1998-04-02", "2026-09-17")
    assert body["state"] in {"loaded", "never_loaded", "all_loads_failed"}
    assert (body["updated_at"] is None) == (body["state"] != "loaded")
