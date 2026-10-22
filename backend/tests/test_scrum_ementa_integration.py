"""Trabalho posterior: API + PostgreSQL real, fora da apresentação unitária."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import needs_database


@needs_database
@pytest.mark.integration
def test_api_preserva_todas_as_secoes_da_ementa(client: TestClient) -> None:
    # Dado: fixture 1000004 com ementa estruturada no PostgreSQL de teste.
    # Quando: abrir o detalhe pela API real.
    response = client.get("/decisions/tjdft-jurisdf/1000004")
    # Então: todas as seções presentes, sem truncar a ementa.
    assert response.status_code == 200
    body = response.json()
    sections = body["sections"]
    assert set(sections) == {"headnote", "case", "question", "reasoning", "ruling"}
    assert all(isinstance(value, str) and value.strip() for value in sections.values())
    assert body["summary"].startswith(sections["headnote"])
    for name in ("case", "question", "reasoning", "ruling"):
        assert sections[name] in body["summary"]
