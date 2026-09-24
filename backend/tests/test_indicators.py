"""
The indicators, starting with how recent the data is.

A reader has to know the age of the collection before drawing a conclusion from
it, so this is as much a part of the answer as the decisions are.
"""

from collections.abc import Iterator
from typing import get_args

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api.indicators import ANSWERS, LastUpdate, State
from app.db import get_connection
from app.main import app
from tests.conftest import needs_database

pytestmark = needs_database


@pytest.fixture
def undone(db: psycopg.Connection[DictRow]) -> Iterator[psycopg.Connection[DictRow]]:
    """
    For the tests that have to change the load record to make their point.

    Teardown runs even when the assertion fails, which a rollback at the end of
    the test body does not: the fixture's connection commits on the way out, so
    a failing test would leave its change behind for every test after it.
    """
    try:
        yield db
    finally:
        db.rollback()


@pytest.fixture
def client(db: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_it_answers_with_the_last_successful_load(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT concluida_em, registros_gravados FROM core.carga "
            "WHERE status = 'concluida' ORDER BY concluida_em DESC LIMIT 1"
        )
        row = cursor.fetchone()

    assert row is not None
    body = client.get("/indicators/last-update").json()

    assert body["updated_at"].startswith(row["concluida_em"].date().isoformat())
    assert body["records"] == row["registros_gravados"]


def test_the_date_is_the_most_recent_one_not_just_any(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    """
    Ordering by the wrong column, or not ordering at all, gives whichever row
    PostgreSQL happens to return first — right on a small table, wrong later.
    """
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT max(concluida_em) AS latest FROM core.carga "
            "WHERE status = 'concluida'"
        )
        row = cursor.fetchone()

    assert row is not None
    body = client.get("/indicators/last-update").json()

    assert body["updated_at"].startswith(row["latest"].date().isoformat())


def test_it_reads_the_data_that_travelled_with_the_decisions(
    client: TestClient,
) -> None:
    """
    The date comes from the load record published alongside the decisions, not
    from the clock of the machine answering. A server that has not been
    refreshed must keep reporting its own older date.
    """
    from app.api.indicators import LAST_LOAD_SQL

    assert "core.carga" in LAST_LOAD_SQL
    assert "NOW()" not in LAST_LOAD_SQL.upper()


def test_a_load_that_failed_is_not_the_answer(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    """
    The fixture's failed load is dated after both successful ones. Filtering
    after sorting, or not filtering at all, would report it — and report a date
    on which nothing was written.
    """
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT concluida_em FROM core.carga WHERE status <> 'concluida' "
            "ORDER BY concluida_em DESC LIMIT 1"
        )
        failed = cursor.fetchone()

    assert failed is not None, "the fixture stopped carrying a failed load"
    body = client.get("/indicators/last-update").json()

    assert body["state"] == "loaded"
    assert not body["updated_at"].startswith(failed["concluida_em"].date().isoformat())


def test_a_collection_whose_every_load_failed_says_so(
    client: TestClient, undone: psycopg.Connection[DictRow]
) -> None:
    """
    A pipeline that ran and never finished is different news from one that never
    ran, and a screen has to be able to say which.
    """
    undone.execute("UPDATE core.carga SET status = 'falhou'")

    body = client.get("/indicators/last-update").json()

    assert body["state"] == "all_loads_failed"
    assert body["updated_at"] is None
    assert body["records"] == 0


def test_a_collection_with_no_load_at_all_says_so(
    client: TestClient, undone: psycopg.Connection[DictRow]
) -> None:
    """
    The card asks for an explicit answer rather than a silent null. `null` alone
    would leave a screen unable to tell "not loaded yet" from "the field is
    missing".
    """
    undone.execute("DELETE FROM core.carga")

    body = client.get("/indicators/last-update").json()

    assert body["state"] == "never_loaded"
    assert body["updated_at"] is None
    assert body["records"] == 0


def documented(client: TestClient) -> dict[str, object]:
    spec = client.get("/openapi.json").json()
    return spec["paths"]["/indicators/last-update"]["get"]["responses"]


def test_every_state_the_endpoint_can_answer_is_documented() -> None:
    """
    An example per state, checked against the type rather than against a list
    someone has to remember to update. Adding a fourth state fails here.
    """
    assert set(ANSWERS) == set(get_args(State))


def test_each_documented_answer_would_pass_the_response_model() -> None:
    """
    The examples are hand written, so nothing stops one carrying a shape the
    endpoint never sends. This reads them back through the model that serves it.
    """
    for name, example in ANSWERS.items():
        assert LastUpdate.model_validate(example["value"]), name


def test_only_the_loaded_state_carries_a_date() -> None:
    for name, example in ANSWERS.items():
        has_date = example["value"]["updated_at"] is not None
        assert has_date == (name == "loaded"), name


def test_the_endpoint_documents_the_answer_it_actually_sends(
    client: TestClient,
) -> None:
    served = client.get("/indicators/last-update").json()
    promised = ANSWERS[served["state"]]["value"]

    assert set(served) == set(promised)


def test_it_documents_the_environment_that_has_no_data_yet(
    client: TestClient,
) -> None:
    """
    A caller writing error handling from the spec would otherwise read a 503
    here as a bug in their own code rather than as a server awaiting its first
    publication.
    """
    assert "503" in documented(client)
