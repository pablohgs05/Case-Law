"""
The thesis the court wrote, split into what it numbered.

The split is the part that breaks quietly: a loose number inside a sentence
matches the item pattern, and one thesis becomes two fragments that read as
nonsense on screen.
"""

import re

from app.ementa import theses


def test_a_numbered_block_becomes_one_entry_per_item() -> None:
    found = theses(
        "1. A palavra da vítima possui especial relevância em crimes de "
        "violência doméstica. 2. A ausência de testemunhas presenciais não "
        "inviabiliza a condenação."
    )

    assert len(found) == 2
    assert found[0].startswith("A palavra da vítima")
    assert found[1].startswith("A ausência de testemunhas")


def test_a_single_thesis_is_a_list_of_one() -> None:
    """A quarter of the blocks carry one thesis and no numbering."""
    found = theses(
        "A ausência de impugnação concreta de todos os fundamentos impede o "
        "conhecimento do agravo em recurso especial."
    )

    assert len(found) == 1
    assert found[0].startswith("A ausência")


def test_letters_count_as_items_too() -> None:
    found = theses(
        "a) o habeas corpus não é cabível como substitutivo de recurso "
        "próprio; b) a suspensão do livramento condicional exige contraditório."
    )

    assert len(found) == 2


def test_a_precedent_number_does_not_open_an_item() -> None:
    """
    "Incide a Súmula n. 7 do STJ" carries a number followed by a stop, which is
    the item pattern. Splitting there turns four theses into eleven fragments —
    measured on two decisions of a hundred-decision sample.
    """
    found = theses(
        "1. Incide a Súmula n. 7 do STJ para obstar o reexame do conjunto "
        "fático-probatório. 2. Aplica-se, por analogia, a Súmula n. 284 do "
        "STF diante da deficiência de fundamentação."
    )

    assert len(found) == 2
    assert "Súmula n. 7 do STJ" in found[0]
    assert "Súmula n. 284 do STF" in found[1]


def test_a_law_number_does_not_open_an_item_either() -> None:
    found = theses(
        "1. Aplica-se a Súmula n. 83 do STJ quando o acórdão se harmoniza com "
        "a jurisprudência que resguarda, pelo art. 39 da Lei n. 4.886/1965, o "
        "foro do domicílio do representante comercial."
    )

    assert len(found) == 1


def test_a_lone_item_number_is_dropped_from_the_text() -> None:
    found = theses("1. Diante da ausência de elementos, não cabe a tutela.")

    assert found == ["Diante da ausência de elementos, não cabe a tutela."]


def test_nothing_in_nothing_out() -> None:
    assert theses(None) == []
    assert theses("") == []
    assert theses("   ") == []


# The label and the block boundary, mirrored from the `rotulada` and `tese`
# CTEs in core_decisao.sql, so a change there breaks a test here.
ROTULO = re.compile(
    r"teses?\s+(?:de\s+julgamento|firmadas?|fixadas?|adotada|do\s+julgado)\s*:",
    re.IGNORECASE,
)
BORDA_ESQUERDA = re.compile("^[\\s\u00a0\"\u201c\u201d'_.\u2013\u2014-]+")
BORDA_DIREITA = re.compile("[\\s\u00a0\"\u201c\u201d'_]+$")
SEGUINTE = re.compile(
    r"Dispositivos?\s+relevantes?|Jurisprud[eê]ncia\s+relevante", re.IGNORECASE
)


def extracted(ementa: str) -> str | None:
    """The rule in core_decisao.sql: where the thesis starts and where it stops."""
    rotulo = ROTULO.search(ementa)
    if rotulo is None:
        return None

    # REGEXP_INSTR with return_opt 1 gives the position after the match, so
    # the label itself is not part of the thesis.
    bloco = ementa[rotulo.end() :]
    corte = SEGUINTE.search(bloco)
    if corte is not None:
        bloco = bloco[: corte.start()]

    # The left trim takes the typesetting marks; the right one leaves the
    # full stop alone, because that one is the court's.
    return re.sub(BORDA_DIREITA, "", re.sub(BORDA_ESQUERDA, "", bloco)) or None


def test_the_block_stops_before_the_citations_that_follow_it() -> None:
    """
    The test the card calls the block-limit one. The CNJ's shape puts two
    lists of citations right after the thesis, and dragging them in does not
    fail: the column fills, the card is buried in references and the thesis
    is lost in the middle. It only shows up on the screen.
    """
    ementa = (
        "IV. DISPOSITIVO E TESE 5. Recurso conhecido e desprovido. "
        "Tese de julgamento: 1. O prazo corre da ciência da primeira "
        "diligência infrutífera. "
        "Dispositivos relevantes citados: CPC, art. 921. "
        "Jurisprudência relevante citada: STJ, REsp 1.340.553/RS."
    )

    assert extracted(ementa) == (
        "1. O prazo corre da ciência da primeira diligência infrutífera."
    )


def test_the_other_label_the_courts_use_is_read_too() -> None:
    assert (
        extracted("Tese firmada: A citação válida interrompe a prescrição.")
        == "A citação válida interrompe a prescrição."
    )


def test_an_ementa_with_no_label_answers_nothing_rather_than_empty() -> None:
    """
    `null` and `''` read the same on a screen and not in a query: a column
    that fills with empty strings stops `COUNT(tese)` from meaning anything.
    """
    assert extracted("CIVIL. Dano moral. Recurso desprovido.") is None
    assert extracted("Tese de julgamento:") is None


def test_the_colon_is_what_separates_the_label_from_prose() -> None:
    """
    Without it the pattern catches prose — "tese de julgamento extra petita"
    contaminated 3.925 decisions of the STJ.
    """
    assert extracted("Nulidade por tese de julgamento extra petita.") is None
