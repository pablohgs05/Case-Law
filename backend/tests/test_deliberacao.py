"""
Unânime or by majority, read from the dispositive.

The hard part is not the 99,8% that declare one of the two. It is the 3.162
that declare BOTH, because the panel decided more than one thing and each got
its own vote. Three steps find the one that belongs to the merits, and a
fourth case has no answer at all.

These exercise the rule as SQL expresses it, so the shapes come from the
collection, not from imagination.
"""

import re

import pytest

# The dispositive, normalised the way the model does before reading it.
MERITS = re.compile(r"no merito")
TWO_APPEALS = re.compile(
    r"recurso d[eo] |recurso interposto|opostos? pel|interposto pel|apelacao d[eo] "
)
ACCESSORY = re.compile(r"multa|honorario|custas|prejudicad")


def deliberation(text: str) -> str | None:
    """The rule in core_decisao.sql, so a change there breaks a test here."""
    lowered = (
        text.lower()
        .replace("â", "a")
        .replace("á", "a")
        .replace("é", "e")
        .replace("ê", "e")
    )
    scope = lowered[lowered.index("no merito") :] if MERITS.search(lowered) else lowered

    unanimous = [m.start() for m in re.finditer(r"unanime|unanimidade", scope)]
    majority = [m.start() for m in re.finditer(r"maioria", scope)]

    if not unanimous and not majority:
        return None
    if not majority:
        return "unanime"
    if not unanimous:
        return "maioria"
    if len(TWO_APPEALS.findall(scope)) >= 2:
        return None
    if ACCESSORY.search(lowered):
        return "unanime" if unanimous[0] < majority[0] else "maioria"
    return "unanime" if unanimous[-1] > majority[-1] else "maioria"


def test_a_plain_dispositive_says_which_it_was() -> None:
    assert deliberation("RECURSO CONHECIDO E DESPROVIDO. UNÂNIME.") == "unanime"
    assert deliberation("CONHECER. NEGAR PROVIMENTO. MAIORIA.") == "maioria"


def test_the_stj_writes_it_in_prose() -> None:
    assert (
        deliberation(
            "acordam os Ministros da QUINTA TURMA do Superior Tribunal de "
            "Justiça, por unanimidade, negar provimento ao recurso"
        )
        == "unanime"
    )


def test_the_merits_marker_wins_over_the_preliminary() -> None:
    """
    The case the subtask exists for. The preliminary was unanimous and the
    merits went by majority, so the decision was by majority. Reading the
    first marker would call it unanimous, and 586 decisions carry this shape.
    """
    assert (
        deliberation(
            "CONHECIDO. PREJUDICIAL DE MÉRITO AFASTADA. PRELIMINAR REJEITADA. "
            "UNÂNIME. NO MÉRITO, PROVIDO. MAIORIA, VENCIDA A RELATORA."
        )
        == "maioria"
    )


def test_the_merits_are_read_from_where_the_merits_begin() -> None:
    """
    Two real dispositives from the STJ, mirror images of each other, where the
    preliminary and the merits were voted differently. Reading the whole
    sentence answers the preliminary in both; reading from "no merito" answers
    the decision. 41 dispositives change their answer with this step alone, and
    the second one says who dissented, so it can be checked against the court.
    """
    assert (
        deliberation(
            "PRELIMINARMENTE, POR MAIORIA, REJEITAR A ARGUIÇÃO DE INCOMPETENCIA "
            "DA CORTE, E NO MERITO, POR UNANIMIDADE, JULGAR PREJUDICADO O PEDIDO."
        )
        == "unanime"
    )
    assert (
        deliberation(
            "POR UNANIMIDADE, CONHECER DO RECURSO; NO MERITO, POR MAIORIA, "
            "NEGAR-LHE PROVIMENTO E JULGAR PREJUDICADO O HC 6.035/DF. "
            "VOTOU VENCIDO O MIN. EDSON VIDIGAL."
        )
        == "maioria"
    )


def test_a_penalty_decided_by_majority_does_not_decide_the_appeal() -> None:
    """
    The appeal was unanimous; only the fine went by majority. Reading the last
    marker would call the decision one by majority, and 267 carry this shape.
    """
    assert (
        deliberation(
            "Embargos de declaração conhecidos e desprovidos. Unânime. "
            "Multa aplicada. Maioria"
        )
        == "unanime"
    )


def test_admissibility_first_merits_last() -> None:
    assert (
        deliberation("CONHECER, MAIORIA, E DAR PARCIAL PROVIMENTO, UNÂNIME")
        == "unanime"
    )


def test_a_prejudiced_appeal_alongside_does_not_decide_it() -> None:
    assert (
        deliberation(
            "RECURSO DE APELAÇÃO CONHECIDO E PROVIDO, NOS TERMOS DO VOTO DO 1º "
            "VOGAL. MAIORIA. PREJUDICADO O AGRAVO INTERNO À UNANIMIDADE."
        )
        == "maioria"
    )


def test_two_appeals_with_different_votes_have_no_single_answer() -> None:
    """
    The panel judged two appeals, from two parties, and they were decided
    differently. There is no deliberation of the decision — there are two.
    Picking one would be inventing, so the column stays null and the screen
    says it does not know. 263 decisions carry this shape.
    """
    assert (
        deliberation(
            "CONHECER DOS EMBARGOS OPOSTOS PELA CCEE E DAR-LHES PARCIAL "
            "PROVIMENTO. DECISÃO UNÂNIME. CONHECER DOS EMBARGOS OPOSTOS PELA "
            "CEMIG E DAR-LHES PARCIAL PROVIMENTO. DECISÃO POR MAIORIA."
        )
        is None
    )


def test_a_dispositive_with_no_marker_is_not_guessed() -> None:
    assert deliberation("RECURSO CONHECIDO E DESPROVIDO.") is None


@pytest.mark.parametrize(
    "dispositive",
    [
        "APELAÇÃO CONHECIDA E DESPROVIDA. UNÂNIME.",
        "APELAÇÃO CONHECIDA E PROVIDA. UNÂNIME.",
        "RECURSO NÃO CONHECIDO. MAIORIA.",
    ],
)
def test_the_outcome_never_decides_the_vote(dispositive: str) -> None:
    """
    An appeal denied is not unanimous for being denied. The two read from the
    same sentence and are independent, so the rule must not infer one from
    the other.
    """
    expected = "maioria" if "MAIORIA" in dispositive else "unanime"
    assert deliberation(dispositive) == expected
