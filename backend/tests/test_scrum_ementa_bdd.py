"""SCRUM-20: proposta de cenários para ratificação na planning."""

import pytest

from app.ementa import Section, StructuredEmenta


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


@pytest.mark.unit
def test_rebuild_preserva_secoes_distintas() -> None:
    # Dado: textos diferentes permitem detectar perda, duplicação e troca de ordem.
    ementa = StructuredEmenta(
        headnote="DIREITO CIVIL.\n",
        case=Section("I. CASO EM EXAME\n", "Pedido de reparação.\n"),
        question=Section("II. QUESTÃO EM DISCUSSÃO\n", "Existe dano?\n"),
        reasoning=Section("III. RAZÕES DE DECIDIR\n", "Prova insuficiente.\n"),
        ruling=Section("IV. DISPOSITIVO\n", "Recurso negado.\n"),
    )
    # Quando: a classe utilitária reconstrói a ementa sem banco ou API.
    rebuilt = ementa.rebuild()
    # Então: comparar com texto literal independente da implementação.
    assert rebuilt == (
        "DIREITO CIVIL.\n"
        "I. CASO EM EXAME\nPedido de reparação.\n"
        "II. QUESTÃO EM DISCUSSÃO\nExiste dano?\n"
        "III. RAZÕES DE DECIDIR\nProva insuficiente.\n"
        "IV. DISPOSITIVO\nRecurso negado.\n"
    )
