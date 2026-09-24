"""
The section splitter, against the shapes the courts actually write.

Every variant below was counted in the collection before it was written down
here, so these are not invented edge cases.
"""

import json
from pathlib import Path

import pytest

from app.ementa import split

pytestmark = pytest.mark.unit

STRUCTURED = """DIREITO CIVIL. APELAÇÃO. RECURSO PROVIDO.
I. CASO EM EXAME
1. Apelação interposta contra sentença de improcedência.
II. QUESTÃO EM DISCUSSÃO
2. Definir se houve falha na prestação do serviço.
III. RAZÕES DE DECIDIR
3. A falha ficou demonstrada pela prova documental.
IV. DISPOSITIVO
4. Recurso provido."""


def test_a_structured_ementa_comes_back_in_four_sections() -> None:
    parts = split(STRUCTURED)

    assert parts is not None
    assert parts.headnote.strip() == "DIREITO CIVIL. APELAÇÃO. RECURSO PROVIDO."
    assert "Apelação interposta" in parts.case.text
    assert "Definir se houve falha" in parts.question.text
    assert "prova documental" in parts.reasoning.text
    assert "Recurso provido" in parts.ruling.text


def test_nothing_of_the_original_is_lost() -> None:
    """
    The card asks for this in so many words. Rebuilding from the parts has to
    give back the same characters, labels included.
    """
    parts = split(STRUCTURED)

    assert parts is not None
    assert parts.rebuild() == STRUCTURED


def test_prose_without_the_shape_is_not_split() -> None:
    prose = (
        "DIREITO DO CONSUMIDOR. Inscrição indevida em cadastro de inadimplentes. "
        "Dano moral in re ipsa. Recurso não provido."
    )

    assert split(prose) is None


def test_three_sections_out_of_four_count_as_no_shape() -> None:
    """
    A partial split would leave the reader guessing which section is missing.
    The whole text says more than three quarters of a shape.
    """
    partial = STRUCTURED.replace("IV. DISPOSITIVO\n4. Recurso provido.", "")

    assert split(partial) is None


def test_the_plural_form_of_the_second_section_is_recognised() -> None:
    """1.561 ementas write QUESTÕES EM DISCUSSÃO."""
    plural = STRUCTURED.replace("QUESTÃO EM DISCUSSÃO", "QUESTÕES EM DISCUSSÃO")

    parts = split(plural)

    assert parts is not None
    assert parts.rebuild() == plural


def test_the_fourth_section_may_carry_the_thesis_in_its_name() -> None:
    """10.232 ementas write DISPOSITIVO E TESE."""
    with_thesis = STRUCTURED.replace("IV. DISPOSITIVO", "IV. DISPOSITIVO E TESE")

    parts = split(with_thesis)

    assert parts is not None
    assert parts.ruling.label == "IV. DISPOSITIVO E TESE"
    assert parts.rebuild() == with_thesis


def test_lower_case_labels_are_recognised() -> None:
    lowered = STRUCTURED.replace("CASO EM EXAME", "Caso em exame")

    parts = split(lowered)

    assert parts is not None
    assert parts.rebuild() == lowered


def test_labels_glued_to_the_previous_sentence_are_recognised() -> None:
    """
    Some ementas arrive with no line breaks at all:
    `RECURSO PROVIDO.I. CASO EM EXAME1. Agravo de instrumento...`
    """
    glued = STRUCTURED.replace("\n", "")

    parts = split(glued)

    assert parts is not None
    assert parts.rebuild() == glued


def test_a_citation_inside_the_last_section_does_not_open_a_fifth() -> None:
    """
    The fourth section commonly ends with "Dispositivos relevantes citados:".
    Matching the word alone would cut the section in half.
    """
    with_citations = STRUCTURED + (
        "\nDispositivos relevantes citados: CPC, art. 487, I.\n"
        "Jurisprudência relevante citada: TJDFT, Acórdão 2025943."
    )

    parts = split(with_citations)

    assert parts is not None
    assert "Dispositivos relevantes citados" in parts.ruling.text
    assert parts.rebuild() == with_citations


def test_an_absent_ementa_is_not_a_failure() -> None:
    assert split(None) is None
    assert split("") is None


SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "ementas.json").read_text(encoding="utf-8")
)

# Every shape counted in the collection, six real ementas each where six exist.
STRUCTURED_SHAPES = {
    "estruturada-comum",
    "questao-plural",
    "dispositivo-e-tese",
    "rotulo-minusculo",
    "rotulo-colado",
    "com-citacoes",
}
PROSE_SHAPES = {"prosa-livre", "prosa-curta"}


def test_the_sample_still_covers_every_shape() -> None:
    """
    Guards the guard. A sample that quietly lost a shape would let the tests
    below pass while the splitter stopped handling it.
    """
    present = {item["shape"] for item in SAMPLE}

    assert present == STRUCTURED_SHAPES | PROSE_SHAPES


@pytest.mark.parametrize(
    "item", SAMPLE, ids=lambda i: f"{i['shape']}-{i['identifier']}"
)
def test_no_real_ementa_loses_text_when_split(item: dict[str, str]) -> None:
    """
    The card's fourth criterion, against decisions the court actually published
    rather than against text written to pass.
    """
    parts = split(item["ementa"])

    if parts is None:
        return
    assert parts.rebuild() == item["ementa"]


@pytest.mark.parametrize(
    "item", SAMPLE, ids=lambda i: f"{i['shape']}-{i['identifier']}"
)
def test_each_shape_is_read_the_way_it_was_collected(item: dict[str, str]) -> None:
    parts = split(item["ementa"])

    if item["shape"] in PROSE_SHAPES:
        assert parts is None, "free prose was split as though it had the shape"
    else:
        assert parts is not None, "a shape counted in the collection was not read"
        assert parts.case.text.strip()
        assert parts.ruling.text.strip()
