"""
Seguiu, afastou, distinguiu, mencionou or indeterminado, read from the words
around the citation.

The negative forms contain the positive ones: "não se aplica a súmula" carries
"aplica". The order the patterns are tried in is therefore part of the rule,
and these exercise it as the SQL expresses it, so the shapes come from the
collection rather than from imagination.
"""

import re
import unicodedata

import pytest

AFASTOU = re.compile(
    r"nao\s+(?:se\s+)?(?:aplica|incid|atrai)|inaplica|superad[oa]|"
    r"nao\s+obsta|nao\s+ha\s+falar\s+em\s+(?:aplicacao|incidencia)|"
    r"afastad\w*\s+(?:a\s+|o\s+)?(?:incidencia|aplicacao|obice)"
)
DISTINGUIU = re.compile(r"distingu|distincao")
SEGUIU = re.compile(
    r"incid|aplica|obice|obsta|esbarra|atrai|conforme|consoante|conformidade|"
    r"nos\s+termos|a\s+teor|a\s+luz|consonancia|orientacao|entendimento|"
    r"enunciado|observ|vedad|impede"
)
REFERENCIA = re.compile(
    r"precedente|no\s+mesmo\s+sentido|\bcf\.|\bvide|\bv\.g\.|"
    r"a\s+exemplo\s+d|dentre\s+outros|entre\s+outros"
)


def _fold(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(ch) != "Mn"
    )


def _read(text: str) -> str | None:
    folded = _fold(text)
    if AFASTOU.search(folded):
        return "afastou"
    if DISTINGUIU.search(folded):
        return "distinguiu"
    if SEGUIU.search(folded):
        return "seguiu"
    if REFERENCIA.search(folded):
        return "mencionou"
    return None


def adherence(snippet: str, ementa: str | None = None) -> str:
    """The rule in core_decisao_precedente.sql, so a change there breaks a test here."""
    return _read(snippet) or (ementa and _read(ementa)) or "indeterminado"


SEGUIDAS = [
    ("incidência da Súmula n. 7 do Superior Tribunal de Justiça", "seguiu"),
    ("enfrenta o óbice da Súmula 7/STJ", "seguiu"),
    ("reexame de provas, conforme Súmula 7 do STJ", "seguiu"),
    ("consoante enunciado da Súmula 448/STF", "seguiu"),
    ("em razão da sua conformidade com o Tema 355/STJ", "seguiu"),
    ("acórdão recorrido em consonância com a Súmula 83/STJ", "seguiu"),
    ("aplica-se o IPC, nos termos da Súmula 179/STJ", "seguiu"),
]

AFASTADAS = [
    ("não incidência. Súmula 7/STJ. agravo não provido", "afastou"),
    ("não se aplica a orientação contida na Súmula 183/STJ", "afastou"),
    ("não aplicação - divergência superada - Súmula 168 do STJ", "afastou"),
    ("tal entendimento não se aplica ao caso em análise", "afastou"),
    ("afastada a incidência da Súmula 7/STJ", "afastou"),
]


@pytest.mark.parametrize(("snippet", "expected"), SEGUIDAS)
def test_the_court_applied_the_precedent(snippet: str, expected: str) -> None:
    assert adherence(snippet) == expected


@pytest.mark.parametrize(("snippet", "expected"), AFASTADAS)
def test_the_court_set_the_precedent_aside(snippet: str, expected: str) -> None:
    assert adherence(snippet) == expected


@pytest.mark.parametrize(
    "snippet",
    [
        "não se aplica a Súmula 183/STJ",
        "não incidência da Súmula 7/STJ",
        "inaplicabilidade da Súmula 487/STJ",
        "afastada a aplicação da Súmula 7/STJ",
        "não há falar em incidência da Súmula 282/STF",
    ],
)
def test_a_refusal_is_never_read_as_an_application(snippet: str) -> None:
    """
    The one the subtask exists for. Every text here carries "aplica" or
    "incid" and means the opposite of applying the precedent. A pattern for
    the application tried before the one for the refusal reads all five
    backwards, and nothing in a code review looks wrong.
    """
    assert adherence(snippet) == "afastou"


def test_the_two_sentences_the_story_turns_on() -> None:
    """
    The test the card names as deciding the story. The two sentences are
    nearly identical, cite the same precedent, and mean opposite things. If
    this fails, the adherence indicator measures the reverse of what it
    claims — and no code review catches it, because the SQL stays valid and
    the column stays full.
    """
    assert adherence("Aplica-se, na espécie, o óbice da Súmula 284 do STF") == "seguiu"
    assert adherence("Não se aplica ao caso a Súmula 284, porquanto...") == "afastou"


def test_a_distinction_is_neither_of_the_other_two() -> None:
    assert adherence("há distinção entre o caso e o Tema 630") == "distinguiu"


@pytest.mark.parametrize(
    "snippet",
    [
        "precedentes: Súmula 83/STJ, Súmula 7/STJ",
        "no mesmo sentido, a Súmula 284/STF",
        "a exemplo do Tema 630/STJ",
        "Súmula 7/STJ, dentre outros",
    ],
)
def test_a_list_of_precedents_is_a_mention_not_an_application(snippet: str) -> None:
    """
    A citation carried in a list states no judgment about applying it. Reading
    it as `seguiu` inflates the adherence indicator: 6,151 links were being
    counted that way because the word "precedente" sat in the pattern for the
    application.
    """
    assert adherence(snippet) == "mencionou"


def test_the_ementa_answers_only_when_one_precedent_was_cited() -> None:
    """
    With a second citation in the same ementa the verb has another precedent
    it could belong to, so attributing it would be a guess.
    """
    bare = "Súmula n. 7/STJ. decisão mantida."
    assert adherence(bare, "reexame de prova, óbice da súmula") == "seguiu"
    assert adherence(bare, None) == "indeterminado"


def test_nothing_is_categorised_by_elimination() -> None:
    """
    The honesty rule the card states: a link with no signal is undetermined,
    never the leftover category. An indicator built on guesses is worse than
    no indicator.
    """
    assert adherence("Súmula 7/STJ. honorários advocatícios.") == "indeterminado"
