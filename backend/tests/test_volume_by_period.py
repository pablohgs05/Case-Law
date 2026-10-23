"""
The search's decisions counted by period, run against PostgreSQL.

The promise is agreement: the counts have to add up to the same total the
search reports for the same parameters. The granularity adapts to the cut's
amplitude (month up to 3 years, quarter up to 10 years, year beyond) unless
explicitly requested. Periods without decisions inside the interval appear with
count zero so the timeline preserves visual continuity.
"""

from typing import Any, Self

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.main import app
from tests.conftest import needs_database
from tests.test_courts import decide, register

TERM = "dano moral"


def volume_by_period(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/indicators/volume-by-period", params={"q": TERM, **params})
    assert response.status_code == 200, response.text
    return response.json()


def searched(client: TestClient, **params: Any) -> int:
    response = client.get("/decisions", params={"q": TERM, "page_size": 1, **params})
    assert response.status_code == 200, response.text
    return int(response.json()["total"])


@pytest.fixture
def spread(db_rolled_back: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    """
    Decisions spread over several months with an intentional gap (month 3 has no
    decisions) to verify that empty periods inside the interval appear with count zero.
    """
    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    # TJDFT is already registered by schema.sql.

    # STJ has decisions in February (month 2) and April (month 4) - March is empty
    decide(db_rolled_back, "STJ", "STJ0001")
    db_rolled_back.execute(
        "UPDATE core.decisao SET data_referencia = '2026-02-15' WHERE identificador_fonte = 'STJ0001'"
    )
    decide(db_rolled_back, "STJ", "STJ0002")
    db_rolled_back.execute(
        "UPDATE core.decisao SET data_referencia = '2026-02-20' WHERE identificador_fonte = 'STJ0002'"
    )
    decide(db_rolled_back, "STJ", "STJ0003")
    db_rolled_back.execute(
        "UPDATE core.decisao SET data_referencia = '2026-04-10' WHERE identificador_fonte = 'STJ0003'"
    )

    # TJDFT has a decision in May (month 5)
    decide(db_rolled_back, "TJDFT", "TJDFT0001")
    db_rolled_back.execute(
        "UPDATE core.decisao SET data_referencia = '2026-05-02' WHERE identificador_fonte = 'TJDFT0001'"
    )

    return db_rolled_back


@pytest.fixture
def wide_spread(
    db_rolled_back: psycopg.Connection[DictRow],
) -> psycopg.Connection[DictRow]:
    """
    Decisions spanning multiple years to test automatic granularity resolution:
    - Decisions in 2018 and 2026 (~8 years) -> quarter
    - Decisions in 1995 and 2026 (~31 years) -> year
    """
    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")

    # 1995 (year 1)
    decide(db_rolled_back, "STJ", "STJ1995")
    db_rolled_back.execute(
        "UPDATE core.decisao SET data_referencia = '1995-06-10' WHERE identificador_fonte = 'STJ1995'"
    )

    # 2018 (year 24 from 1995, 8 years from 2026)
    decide(db_rolled_back, "STJ", "STJ2018")
    db_rolled_back.execute(
        "UPDATE core.decisao SET data_referencia = '2018-03-15' WHERE identificador_fonte = 'STJ2018'"
    )

    # 2026
    decide(db_rolled_back, "STJ", "STJ2026")
    db_rolled_back.execute(
        "UPDATE core.decisao SET data_referencia = '2026-05-20' WHERE identificador_fonte = 'STJ2026'"
    )

    return db_rolled_back


def test_the_endpoint_is_documented() -> None:
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/indicators/volume-by-period"]["get"]
    body = operation["responses"]["200"]["content"]["application/json"]["schema"]
    named = schema["components"]["schemas"][body["$ref"].rsplit("/", 1)[-1]]

    assert set(named["properties"]) == {"total", "granularity", "periods"}
    assert {p["name"] for p in operation["parameters"]} >= {
        "q",
        "tribunal",
        "granularity",
        "date_from",
        "date_to",
        "published_from",
        "published_to",
    }

    item_ref = named["properties"]["periods"]["items"]["$ref"].rsplit("/", 1)[-1]
    item_schema = schema["components"]["schemas"][item_ref]
    assert set(item_schema["properties"]) == {"period", "decisions"}


class _MockCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.query = ""
        self.params: Any = None

    def execute(self, query: str, params: Any = None) -> None:
        self.query = query
        self.params = params

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        pass


class _MockConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._cursor = _MockCursor(rows)

    def cursor(self) -> _MockCursor:
        return self._cursor


def test_endpoint_returns_empty_series_when_cut_matches_nothing() -> None:
    from app.db import get_connection

    mock_conn = _MockConnection([])
    app.dependency_overrides[get_connection] = lambda: mock_conn
    try:
        client = TestClient(app)
        response = client.get(
            "/indicators/volume-by-period", params={"q": "zzzznaoexiste"}
        )
        assert response.status_code == 200
        assert response.json() == {"total": 0, "granularity": "month", "periods": []}
    finally:
        app.dependency_overrides.clear()


def test_endpoint_returns_periods_with_zeros_and_correct_total() -> None:
    from datetime import date

    from app.db import get_connection

    mock_rows = [
        {"granularity": "month", "periodo": date(2026, 2, 1), "decisoes": 15},
        {"granularity": "month", "periodo": date(2026, 3, 1), "decisoes": 0},
        {"granularity": "month", "periodo": date(2026, 4, 1), "decisoes": 25},
    ]
    mock_conn = _MockConnection(mock_rows)
    app.dependency_overrides[get_connection] = lambda: mock_conn
    try:
        client = TestClient(app)
        response = client.get(
            "/indicators/volume-by-period", params={"q": "dano moral"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 40
        assert body["granularity"] == "month"
        assert body["periods"] == [
            {"period": "2026-02-01", "decisions": 15},
            {"period": "2026-03-01", "decisions": 0},
            {"period": "2026-04-01", "decisions": 25},
        ]
        assert "generate_series" in mock_conn._cursor.query
        assert "date_trunc" in mock_conn._cursor.query
    finally:
        app.dependency_overrides.clear()


def test_endpoint_validates_and_normalizes_granularity_parameter() -> None:
    from datetime import date

    from app.db import get_connection

    mock_rows = [
        {"granularity": "quarter", "periodo": date(2026, 1, 1), "decisoes": 10}
    ]
    mock_conn = _MockConnection(mock_rows)
    app.dependency_overrides[get_connection] = lambda: mock_conn
    try:
        client = TestClient(app)
        # Accepts 'trimestre' alias and converts to 'quarter'
        response = client.get(
            "/indicators/volume-by-period",
            params={"q": "dano moral", "granularity": "trimestre"},
        )
        assert response.status_code == 200
        assert response.json()["granularity"] == "quarter"
        assert mock_conn._cursor.params["granularity"] == "quarter"

        # Invalid granularity returns 400
        bad_response = client.get(
            "/indicators/volume-by-period",
            params={"q": "dano moral", "granularity": "dia"},
        )
        assert bad_response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_endpoint_refuses_inverted_date_range() -> None:
    from app.db import get_connection

    mock_conn = _MockConnection([])
    app.dependency_overrides[get_connection] = lambda: mock_conn
    try:
        client = TestClient(app)
        response = client.get(
            "/indicators/volume-by-period",
            params={
                "q": "dano moral",
                "date_from": "2026-05-01",
                "date_to": "2026-01-01",
            },
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_volume_over_time_alias_endpoint() -> None:
    from datetime import date

    from app.db import get_connection

    mock_rows = [{"granularity": "month", "periodo": date(2026, 1, 1), "decisoes": 5}]
    mock_conn = _MockConnection(mock_rows)
    app.dependency_overrides[get_connection] = lambda: mock_conn
    try:
        client = TestClient(app)
        res_main = client.get(
            "/indicators/volume-by-period", params={"q": "dano moral"}
        )
        res_alias = client.get(
            "/indicators/volume-over-time", params={"q": "dano moral"}
        )
        assert res_main.status_code == 200
        assert res_alias.status_code == 200
        assert res_main.json() == res_alias.json()
    finally:
        app.dependency_overrides.clear()


@needs_database
@pytest.mark.parametrize(
    "params",
    [
        {},
        {"tribunal": ["STJ"]},
        {"tribunal": ["TJDFT"]},
        {"tribunal": ["STJ", "TJDFT"]},
        {"tribunal": ["NAOEXISTE"]},
        {"date_from": "2026-02-01", "date_to": "2026-02-28"},
        {"date_from": "2026-04-01"},
        {"date_to": "2026-03-31"},
        {"date_from": "2030-01-01"},
    ],
    ids=[
        "all",
        "one court",
        "second court",
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
    body = volume_by_period(client, **params)

    assert sum(period["decisions"] for period in body["periods"]) == body["total"]
    assert body["total"] == searched(client, **params)


@needs_database
def test_periods_without_decisions_appear_with_zero(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    """
    March 2026 had no decisions, but sits between February and April/May.
    It must be present in the periods list with count 0.
    """
    body = volume_by_period(client)

    periods_by_date = {p["period"]: p["decisions"] for p in body["periods"]}
    assert "2026-03-01" in periods_by_date
    assert periods_by_date["2026-03-01"] == 0
    assert periods_by_date["2026-02-01"] == 2
    assert periods_by_date["2026-04-01"] == 1
    assert periods_by_date["2026-05-01"] == 1


@needs_database
def test_periods_come_in_chronological_order(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    body = volume_by_period(client)
    dates = [p["period"] for p in body["periods"]]

    assert dates == sorted(dates)
    assert dates == ["2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01"]


@needs_database
def test_automatic_granularity_adapts_to_cut_span(
    client: TestClient, wide_spread: psycopg.Connection[DictRow]
) -> None:
    """
    - 1 month / 3 months (span <= 3 years) -> month
    - 2018 to 2026 (~8 years, span 3-10 years) -> quarter
    - 1995 to 2026 (~31 years, span > 10 years) -> year
    """
    # 1. Span <= 3 years (e.g. only 2026):
    body_short = volume_by_period(client, date_from="2026-01-01", date_to="2026-12-31")
    assert body_short["granularity"] == "month"

    # 2. Span of ~8 years (2018 to 2026):
    body_medium = volume_by_period(client, date_from="2018-01-01")
    assert body_medium["granularity"] == "quarter"

    # 3. Whole collection (1995 to 2026):
    body_whole = volume_by_period(client)
    assert body_whole["granularity"] == "year"


@needs_database
def test_changing_granularity_does_not_change_the_total(
    client: TestClient, wide_spread: psycopg.Connection[DictRow]
) -> None:
    """Changing granularity preserves the exact sum and matches the search total."""
    search_total = searched(client)

    by_month = volume_by_period(client, granularity="month")
    by_quarter = volume_by_period(client, granularity="quarter")
    by_year = volume_by_period(client, granularity="year")

    assert by_month["total"] == search_total
    assert by_quarter["total"] == search_total
    assert by_year["total"] == search_total

    assert sum(p["decisions"] for p in by_month["periods"]) == search_total
    assert sum(p["decisions"] for p in by_quarter["periods"]) == search_total
    assert sum(p["decisions"] for p in by_year["periods"]) == search_total


@needs_database
def test_a_search_with_no_match_answers_an_empty_list(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    response = client.get(
        "/indicators/volume-by-period", params={"q": "zzzznaoexistezzz"}
    )

    assert response.status_code == 200
    assert response.json() == {"total": 0, "granularity": "month", "periods": []}


@needs_database
def test_a_period_that_ends_before_it_starts_is_refused(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    response = client.get(
        "/indicators/volume-by-period",
        params={"q": TERM, "date_from": "2026-03-31", "date_to": "2026-03-01"},
    )

    assert response.status_code == 400


@needs_database
def test_volume_over_time_alias_answers_identically(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    res_period = client.get("/indicators/volume-by-period", params={"q": TERM})
    res_alias = client.get("/indicators/volume-over-time", params={"q": TERM})

    assert res_alias.status_code == 200
    assert res_alias.json() == res_period.json()


@needs_database
@pytest.mark.parametrize("order", ["relevance", "date_desc", "date_asc"])
def test_search_order_does_not_reorder_the_series(
    client: TestClient, spread: psycopg.Connection[DictRow], order: str
) -> None:
    assert volume_by_period(client, order=order) == volume_by_period(client)


@needs_database
@pytest.mark.parametrize("granularity", ["month", "quarter", "year"])
def test_a_single_period_is_a_point_not_an_error(
    client: TestClient, spread: psycopg.Connection[DictRow], granularity: str
) -> None:
    params = {
        "date_from": "2026-02-01",
        "date_to": "2026-02-28",
        "granularity": granularity,
    }
    body = volume_by_period(client, **params)
    assert body["granularity"] == granularity
    assert len(body["periods"]) == 1
    assert (
        body["periods"][0]["decisions"]
        == body["total"]
        == searched(client, **params)
        == 2
    )


@needs_database
@pytest.mark.parametrize(
    "start,expected",
    [
        ("2026-05-01", "month"),
        ("2024-05-01", "month"),
        ("2018-05-01", "quarter"),
        ("1989-01-01", "year"),
    ],
)
def test_automatic_series_remains_legible_and_preserves_the_cut(
    client: TestClient, spread: psycopg.Connection[DictRow], start: str, expected: str
) -> None:
    # Add real boundary rows: the endpoint selects granularity from matched dates.
    for identifier, judged in [
        ("STJ1989", "1989-01-15"),
        ("STJ2018", "2018-05-01"),
        ("STJ2024", "2024-05-01"),
    ]:
        decide(spread, "STJ", identifier)
        spread.execute(
            "UPDATE core.decisao SET data_referencia = %s WHERE identificador_fonte = %s",
            (judged, identifier),
        )
    body = volume_by_period(client, date_from=start)
    assert body["granularity"] == expected
    assert 1 <= len(body["periods"]) <= 40
    assert (
        sum(p["decisions"] for p in body["periods"])
        == body["total"]
        == searched(client, date_from=start)
    )


@needs_database
def test_historical_cut_does_not_fabricate_tjdft_coverage(
    client: TestClient, spread: psycopg.Connection[DictRow]
) -> None:
    decide(spread, "STJ", "STJ1989")
    spread.execute(
        "UPDATE core.decisao SET data_referencia = '1989-06-01' WHERE identificador_fonte = 'STJ1989'"
    )
    params = {"date_from": "1989-01-01", "date_to": "1989-12-31"}
    stj = volume_by_period(client, tribunal=["STJ"], **params)
    tjdft = volume_by_period(client, tribunal=["TJDFT"], **params)
    assert stj["total"] == searched(client, tribunal=["STJ"], **params) == 1
    assert stj["periods"] == [{"period": "1989-06-01", "decisions": 1}]
    assert tjdft == {"total": 0, "granularity": "month", "periods": []}


@needs_database
@pytest.mark.parametrize(
    "granularity,selected,start,end,expected",
    [
        ("month", "2024-02-01", "2024-02-01", "2024-02-29", 2),
        ("quarter", "2024-01-01", "2024-01-01", "2024-03-31", 5),
        ("year", "2024-01-01", "2024-01-01", "2024-12-31", 7),
    ],
)
def test_selecting_a_period_includes_both_edges_and_preserves_the_original_cut(
    client: TestClient,
    spread: psycopg.Connection[DictRow],
    granularity: str,
    selected: str,
    start: str,
    end: str,
    expected: int,
) -> None:
    spread.execute("DELETE FROM core.decisao")
    dates = [
        "2023-12-31",
        "2024-01-01",
        "2024-02-01",
        "2024-02-29",
        "2024-03-01",
        "2024-03-31",
        "2024-04-01",
        "2024-12-31",
        "2025-01-01",
    ]
    for index, judged in enumerate(dates):
        identifier = f"STJ-edge-{index}"
        decide(spread, "STJ", identifier)
        spread.execute(
            "UPDATE core.decisao SET data_referencia = %s, resultado = 'negado', orgao_julgador = 'CORTE ESPECIAL', relator = 'RELATOR A', classe_cnj = 198 WHERE identificador_fonte = %s",
            (judged, identifier),
        )
    decide(spread, "TJDFT", "other-court")
    spread.execute(
        "UPDATE core.decisao SET data_referencia = '2024-02-29', resultado = 'negado' WHERE identificador_fonte = 'other-court'"
    )
    original: dict[str, Any] = {
        "tribunal": ["STJ"],
        "orgao_julgador": ["CORTE ESPECIAL"],
        "relator": ["RELATOR A"],
        "classe_cnj": [198],
        "resultado": ["negado"],
    }
    body = volume_by_period(client, granularity=granularity, **original)
    bucket = next(p for p in body["periods"] if p["period"] == selected)
    assert (
        searched(client, date_from=start, date_to=end, **original)
        == bucket["decisions"]
        == expected
    )
    # Intersect the selected period with existing dates rather than widen them.
    limited = {**original, "date_from": "2024-02-01", "date_to": "2024-03-31"}
    limited_body = volume_by_period(client, granularity=granularity, **limited)
    limited_bucket = next(p for p in limited_body["periods"] if p["period"] == selected)
    selected_cut = {
        **limited,
        "date_from": max(start, limited["date_from"]),
        "date_to": min(end, limited["date_to"]),
    }
    assert searched(client, **selected_cut) == limited_bucket["decisions"]
