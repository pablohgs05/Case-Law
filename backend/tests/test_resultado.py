"""
Provido, parcialmente provido or negado, read from the dispositive.

The hard part is that the words contain one another: "NEGAR PROVIMENTO AO
RECURSO" carries the word "PROVIMENTO". The order the patterns are tried in is
therefore part of the rule, and these exercise it as the SQL expresses it, so
the shapes come from the collection rather than from imagination.
"""

import re
import unicodedata

import pytest

PARCIAL = re.compile(
    r"parcial\w*\s+(?:provi|procedent)|provi\w*\s+(?:em\s+)?parte|"
    r"provimento\s+parcial|acolh\w+\s+(?:em\s+)?parte|em\s+parte\s+provi"
)
NEGADO = re.compile(
    r"\bneg\w+\s+(?:-lhe\s+)?provimento|neg\w+-lhe\s+provimento|\bdesprovi|"
    r"\bimprovi|\bnao\s+provi|\bnao\s+conhec|\brejeit|\bindeferi|"
    r"\bnao\s+acolh|\bdenega"
)
PROVIDO = re.compile(r"\bd[aeo]\w*\s+provimento|\bprovi[dm]|\bacolh|\bconced|\bdeferi")

TWO_APPEALS = re.compile(
    r"recurso d[eo] |recurso interposto|opostos? pel|interposto pel|apelacao d[eo] "
)
NEG_SIDE = re.compile(
    r"\bneg\w+\s+(?:-lhe\s+)?provimento|neg\w+-lhe\s+provimento|\bdesprovi|"
    r"\bimprovi|\bnao\s+provi"
)
POS_SIDE = re.compile(
    r"\bd[aeo]\w*\s+(?:-lhe\s+)?provimento|deu-lhe\s+provimento|\bprovi[dm]"
)


def outcome(text: str) -> str | None:
    """The rule in core_decisao.sql, so a change there breaks a test here."""
    lowered = "".join(
        ch
        for ch in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(ch) != "Mn"
    )

    if (
        len(TWO_APPEALS.findall(lowered)) >= 2
        and NEG_SIDE.search(lowered)
        and POS_SIDE.search(lowered)
    ):
        return None
    if PARCIAL.search(lowered):
        return "parcialmente_provido"
    if NEGADO.search(lowered):
        return "negado"
    if PROVIDO.search(lowered):
        return "provido"
    return None


TJDFT = [
    ("CONHECIDO. DESPROVIDO. UNÂNIME.", "negado"),
    ("NEGAR PROVIMENTO AO RECURSO. UNÂNIME", "negado"),
    ("CONHECIDO. NÃO PROVIDO. UNÂNIME.", "negado"),
    ("EMBARGOS DE DECLARAÇÃO CONHECIDOS E REJEITADOS. UNÂNIME.", "negado"),
    ("CONHECIDO. PROVIDO. UNÂNIME.", "provido"),
    ("DAR PROVIMENTO AO RECURSO. UNÂNIME", "provido"),
    ("CONHECIDO. PARCIALMENTE PROVIDO. UNÂNIME.", "parcialmente_provido"),
    ("CONHECIDOS. ACOLHIDOS EM PARTE. UNÂNIME.", "parcialmente_provido"),
]

STJ = [
    ("A Turma, por unanimidade, negou provimento ao agravo regimental", "negado"),
    ("A Turma, por unanimidade, rejeitou os embargos de declaração", "negado"),
    ("A Turma, por unanimidade, deu provimento ao recurso especial", "provido"),
    ("decide dar parcial provimento ao recurso especial", "parcialmente_provido"),
]


@pytest.mark.parametrize(("dispositive", "expected"), TJDFT)
def test_the_tjdft_writes_it_as_a_list(dispositive: str, expected: str) -> None:
    assert outcome(dispositive) == expected


@pytest.mark.parametrize(("dispositive", "expected"), STJ)
def test_the_stj_writes_it_in_prose(dispositive: str, expected: str) -> None:
    assert outcome(dispositive) == expected


@pytest.mark.parametrize(
    "dispositive",
    [
        "NEGAR PROVIMENTO AO RECURSO. UNÂNIME",
        "CONHECIDO. DESPROVIDO. UNÂNIME.",
        "RECURSO CONHECIDO E IMPROVIDO.",
        "A Turma negou provimento ao agravo em recurso especial",
        "CONHECER DO RECURSO E NEGAR-LHE PROVIMENTO. DECISÃO UNÂNIME.",
    ],
)
def test_a_denial_is_never_read_as_a_grant(dispositive: str) -> None:
    """
    The one the subtask exists for. Every text here carries the word
    "provimento" and means the opposite of granting it. A pattern for the
    grant tried before the one for the denial reads all five backwards, and
    nothing in a code review looks wrong.
    """
    assert outcome(dispositive) == "negado"


def test_a_partial_grant_is_neither_of_the_other_two() -> None:
    for dispositive in (
        "CONHECIDO. PARCIALMENTE PROVIDO. UNÂNIME.",
        "CONHECIDO. PROVIDO EM PARTE. UNÂNIME.",
        "deu-lhe parcial provimento, nos termos do voto",
    ):
        assert outcome(dispositive) == "parcialmente_provido", dispositive


def test_a_partial_admission_does_not_make_the_merits_partial() -> None:
    """
    "Parcialmente" here belongs to the admission, not to the merits: the court
    heard part of the appeal and decided that part in full. Reading the word
    wherever it appears would call all three partial.
    """
    assert (
        outcome(
            "A Turma, por unanimidade, conheceu parcialmente do agravo regimental "
            "e, nesta extensão, negou-lhe provimento"
        )
        == "negado"
    )
    assert (
        outcome("conhecer parcialmente do pedido e, nessa parte, conceder a ordem")
        == "provido"
    )
    assert (
        outcome("conhecer parcialmente do pedido e, nessa parte, denegar a ordem")
        == "negado"
    )


@pytest.mark.parametrize(
    "dispositive",
    [
        "recurso do autor desprovido. recurso do reu provido. unanime",
        "apelação do autor parcialmente provida. apelação do banco desprovida.",
        (
            "por unanimidade, negar provimento ao recurso do réu e dar provimento "
            "ao recurso do autor"
        ),
    ],
)
def test_two_appeals_decided_apart_have_no_single_outcome(dispositive: str) -> None:
    """
    The panel judged two appeals and they went opposite ways. Answering with
    either one would be inventing the other, so the column stays null.
    """
    assert outcome(dispositive) is None


@pytest.mark.parametrize(
    "dispositive",
    [
        "Suscitar o conflito de competência, nos termos do voto do Relator.",
        "Julgar extinto o processo sem resolução do mérito.",
        "Homologar o acordo celebrado entre as partes.",
    ],
)
def test_a_decision_that_is_not_an_appeal_on_its_merits_is_not_guessed(
    dispositive: str,
) -> None:
    """
    Null rather than the commonest category. A bias towards `negado` would be
    invisible on screen and would read as fact in a petition.
    """
    assert outcome(dispositive) is None
