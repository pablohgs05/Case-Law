"""SCRUM-20: proposta de cenários para ratificação na planning."""

import pytest
from fastapi.testclient import TestClient

from app.ementa import Section, StructuredEmenta
from tests.conftest import needs_database


@pytest.mark.unit
@pytest.mark.parametrize("text", ["", "Ação.\n", "  texto com espaços  "])
def test_rebuild_preserva_texto_e_ordem_das_secoes(text: str) -> None:
    # Given: classe utilitária isolada, sem banco, rede ou API.
    ementa = StructuredEmenta(
        headnote=text,
        case=Section("I.", text),
        question=Section("II.", text),
        reasoning=Section("III.", text),
        ruling=Section("IV.", text),
    )

    # When: o método da classe reconstrói a ementa.
    rebuilt = ementa.rebuild()

    # Then: nenhuma seção, espaço ou caractere é perdido ou reordenado.
    assert rebuilt == text + "I." + text + "II." + text + "III." + text + "IV." + text


@needs_database
@pytest.mark.integration
def test_api_preserva_todas_as_secoes_da_ementa(client: TestClient) -> None:
    # Given: API e PostgreSQL real preparados pelos fixtures do projeto.
    # O registro 1000004 contém as quatro seções e texto maior que um snippet.
    # When: o leitor abre a decisão completa, sem termo de destaque.
    response = client.get("/decisions/tjdft-jurisdf/1000004")

    # Then: contrato HTTP e todas as seções têm conteúdo, sem truncamento.
    assert response.status_code == 200
    body = response.json()
    sections = body["sections"]
    assert set(sections) == {"headnote", "case", "question", "reasoning", "ruling"}
    assert all(isinstance(value, str) and value.strip() for value in sections.values())
    assert body["summary"].startswith(sections["headnote"])
    for name in ("case", "question", "reasoning", "ruling"):
        assert sections[name] in body["summary"]
