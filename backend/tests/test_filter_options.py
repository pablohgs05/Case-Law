"""Every option must identify at least one searchable decision."""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database

pytestmark = needs_database


@pytest.mark.parametrize(
    ("field", "parameter"),
    [
        ("judging_bodies", "orgao_julgador"),
        ("reporting_judges", "relator"),
        ("procedural_classes", "classe_cnj"),
    ],
)
def test_every_offered_option_returns_decisions(
    client: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
    field: str,
    parameter: str,
) -> None:
    # All fixture decisions become matches so a term cannot mask a dead option.
    db_rolled_back.execute("""
        UPDATE core.decisao SET ementa = 'Dano moral.',
        ementa_busca = TO_TSVECTOR('portugues_sem_acento', 'Dano moral.')
    """)
    response = client.get("/filters")
    assert response.status_code == 200
    options: list[dict[str, Any]] = response.json()[field]
    assert options
    assert client.get("/filters").json()[field] == options
    for option in options:
        params = {"q": "dano moral", parameter: option["value"]}
        search = client.get("/decisions", params=params)
        volume = client.get("/indicators/volume-by-court", params=params)
        assert search.status_code == volume.status_code == 200
        assert search.json()["total"] > 0
        assert search.json()["total"] == volume.json()["total"]
