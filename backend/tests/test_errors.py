from typing import Self

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.errors import UndefinedTable
from psycopg_pool import PoolTimeout

from app.db import get_connection
from app.errors import MALFORMED, NOT_PUBLISHED, OUT_OF_DATE, UNAVAILABLE
from app.main import app


class FailingConnection:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def cursor(self) -> Self:
        return self

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, *_: object, **__: object) -> None:
        raise self.error


@pytest.fixture
def client_failing_with() -> object:
    def build(error: Exception) -> TestClient:
        app.dependency_overrides[get_connection] = lambda: FailingConnection(error)
        return TestClient(app, raise_server_exceptions=False)

    yield build
    app.dependency_overrides.clear()


def test_a_missing_dataset_answers_503_and_says_so(client_failing_with) -> None:
    client = client_failing_with(
        UndefinedTable('relation "core.decisao" does not exist')
    )

    response = client.get("/decisions", params={"q": "dano moral"})

    assert response.status_code == 503
    assert response.json()["detail"] == NOT_PUBLISHED


def test_a_database_that_is_down_answers_503(client_failing_with) -> None:
    client = client_failing_with(psycopg.OperationalError("connection refused"))

    response = client.get("/decisions", params={"q": "dano moral"})

    assert response.status_code == 503
    assert response.json()["detail"] == UNAVAILABLE


def test_a_pool_timeout_answers_503(client_failing_with) -> None:
    client = client_failing_with(PoolTimeout("no connection available"))

    response = client.get("/decisions", params={"q": "dano moral"})

    assert response.status_code == 503
    assert response.json()["detail"] == UNAVAILABLE


def test_the_detail_endpoint_is_covered_too(client_failing_with) -> None:
    client = client_failing_with(
        UndefinedTable('relation "core.decisao" does not exist')
    )

    response = client.get("/decisions/tjdft-jurisdf/2164119")

    assert response.status_code == 503


def test_a_value_postgres_cannot_read_answers_400_not_500(client_failing_with) -> None:
    """
    Every parameter comes from the caller, so a value the database refuses is a
    bad request. Handled centrally: an endpoint added later inherits it instead
    of having to remember.
    """
    client = client_failing_with(
        psycopg.DataError("PostgreSQL text fields cannot contain NUL (0x00) bytes")
    )

    response = client.get("/decisions", params={"q": "dano moral"})

    assert response.status_code == 400
    assert response.json()["detail"] == MALFORMED


def test_a_publication_older_than_the_code_answers_503(client_failing_with) -> None:
    """
    The incident this guards: a deploy added a column to the model, the servers
    kept serving the publication from before it, and every search answered a
    bare 500. UndefinedColumn is a sibling of UndefinedTable rather than a
    subclass, so it escaped the handler that was meant to cover exactly this.
    """
    client = client_failing_with(
        psycopg.errors.UndefinedColumn('column "link_valido" does not exist')
    )

    response = client.get("/decisions", params={"q": "dano moral"})

    assert response.status_code == 503
    assert response.json()["detail"] == OUT_OF_DATE


@pytest.mark.parametrize(
    ("error", "detail"),
    [
        (UndefinedTable('relation "core.tribunal" does not exist'), NOT_PUBLISHED),
        (psycopg.errors.UndefinedColumn('column "nome" does not exist'), OUT_OF_DATE),
        (psycopg.OperationalError("connection refused"), UNAVAILABLE),
    ],
)
def test_the_court_list_never_answers_a_failure_as_an_empty_list(
    client_failing_with, error: Exception, detail: str
) -> None:
    """
    An empty list means no court has a decision yet. A screen would read a
    failure presented that way as a collection with nothing in it.
    """
    client = client_failing_with(error)

    response = client.get("/courts")

    assert response.status_code == 503
    assert response.json() == {"detail": detail}


def test_the_detail_answers_the_same_way(client_failing_with) -> None:
    client = client_failing_with(
        psycopg.errors.UndefinedColumn('column "link_valido" does not exist')
    )

    response = client.get("/decisions/tjdft-jurisdf/2071373")

    assert response.status_code == 503
