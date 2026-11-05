"""A selection counts the same decisions in the indicator and in the list."""

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = needs_database


@pytest.fixture
def indicator_cut(
    db_rolled_back: psycopg.Connection[DictRow],
) -> Iterator[dict[str, Any]]:
    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    register(db_rolled_back, "TRF1")
    # Both edges of the year and neighbouring years must be distinguishable.
    rows = [
        ("STJ", "2023-12-31", "provido"),
        ("STJ", "2024-01-01", "provido"),
        ("STJ", "2024-02-29", "negado"),
        ("STJ", "2024-12-31", "provido"),
        ("STJ", "2025-01-01", "negado"),
        ("TRF1", "2024-12-31", "parcialmente_provido"),
        ("TRF1", "2024-01-01", None),
    ]
    for n, (court, date, outcome) in enumerate(rows):
        decide(db_rolled_back, court, str(n))
        db_rolled_back.execute(
            "UPDATE core.decisao SET data_referencia = %s, resultado = %s, "
            "orgao_julgador = 'TURMA A', relator = 'RELATOR A', classe_cnj = 198 "
            "WHERE identificador_fonte = %s",
            (date, outcome, str(n)),
        )
    populated = db_rolled_back.execute(
        "SELECT COUNT(resultado) AS total FROM core.decisao"
    ).fetchone()
    assert populated is not None and populated["total"] == 6
    yield {
        "q": "dano moral",
        "tribunal": ["STJ", "TRF1"],
        "orgao_julgador": ["TURMA A"],
        "relator": ["RELATOR A"],
        "classe_cnj": [198],
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
    }


def read(client: TestClient, path: str, params: dict[str, Any]) -> dict[str, Any]:
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("kind", ["court", "period", "outcome"])
def test_every_selection_agrees_with_the_list_and_preserves_the_cut(
    client: TestClient, indicator_cut: dict[str, Any], kind: str
) -> None:
    selections: list[tuple[dict[str, Any], int]]
    if kind == "court":
        body = read(client, "/indicators/volume-by-court", indicator_cut)
        selections = [
            ({"tribunal": [row["abbreviation"]]}, row["decisions"])
            for row in body["courts"]
        ]
    elif kind == "outcome":
        body = read(client, "/indicators/outcome-share", indicator_cut)
        selections = [
            ({"resultado": [row["outcome"]]}, row["decisions"])
            for row in body["outcomes"]
        ]
    else:
        body = read(
            client,
            "/indicators/volume-by-period",
            {**indicator_cut, "granularity": "year"},
        )
        assert body["granularity"] == "year"
        selections = [({"date_from": "2024-01-01", "date_to": "2024-12-31"}, 5)]
        assert body["periods"] == [{"period": "2024-01-01", "decisions": 5}]
    for selection, expected in selections:
        result = read(client, "/decisions", {**indicator_cut, **selection})
        assert result["total"] == expected
        assert len(result["results"]) == expected
        assert all(
            "2024-01-01" <= row["decided_on"] <= "2024-12-31"
            for row in result["results"]
        )


def test_year_selection_includes_january_first_and_december_last(
    client: TestClient, indicator_cut: dict[str, Any]
) -> None:
    result = read(client, "/decisions", {**indicator_cut, "tribunal": ["STJ"]})
    assert result["total"] == 3
    assert {row["identifier"] for row in result["results"]} == {"1", "2", "3"}
