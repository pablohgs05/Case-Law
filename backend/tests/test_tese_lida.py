"""
The check that stands between a model and a court's name.

Everything here is about `tese.confere`. A reading that passes it is shown to a
lawyer beside the court's own ementa, so these tests are less about the happy
path than about the ways a plausible answer can still be one the decision does
not support.
"""

import pytest

from app import tese
from app.tese import Lida

EMENTA = (
    "RECURSO ESPECIAL. CONSUMIDOR. AÇÃO DE INDENIZAÇÃO POR DANOS MORAIS. "
    "A legitimidade ativa para pleitear dano moral por ricochete é reconhecida "
    "a quem, não sendo vítima direta do evento danoso, mantém vínculo de "
    "proximidade afetiva com o ofendido direto. RECURSO PROVIDO."
)

TRECHO = (
    "A legitimidade ativa para pleitear dano moral por ricochete é reconhecida "
    "a quem, não sendo vítima direta do evento danoso, mantém vínculo de "
    "proximidade afetiva com o ofendido direto."
)


def test_a_reading_quoting_the_ementa_is_accepted() -> None:
    lida = Lida(tese="A vítima por ricochete tem legitimidade ativa.", trecho=TRECHO)

    assert tese.confere(EMENTA, lida)


def test_a_thesis_the_ementa_does_not_contain_is_refused() -> None:
    """
    The whole point. The thesis reads well, cites a real-sounding passage, and
    says something the decision never said.
    """
    inventada = Lida(
        tese="O prazo prescricional para a pretensão é de cinco anos.",
        trecho=(
            "O prazo prescricional para a pretensão indenizatória é de cinco "
            "anos, contados do conhecimento do dano pela vítima."
        ),
    )

    assert not tese.confere(EMENTA, inventada)


def test_a_passage_from_a_different_decision_is_refused() -> None:
    outra = Lida(
        tese="O fornecedor responde objetivamente pelo defeito do serviço.",
        trecho=(
            "A responsabilidade objetiva do fornecedor pelo defeito na prestação "
            "do serviço dispensa a demonstração de culpa."
        ),
    )

    assert not tese.confere(EMENTA, outra)


@pytest.mark.parametrize(
    "variacao",
    [
        TRECHO.replace("é", "e").replace("ô", "o").replace("í", "i"),
        TRECHO.replace(" ", "  ").replace(",", " ,"),
        TRECHO.upper(),
        TRECHO.replace("—", "-").replace("vínculo", "vinculo"),
    ],
    ids=["sem acentos", "espaçamento", "caixa alta", "pontuação trocada"],
)
def test_a_quote_copied_imperfectly_is_still_the_same_passage(variacao: str) -> None:
    """
    A model transcribing a passage drops an accent, doubles a space, changes
    the case. Refusing those would throw away readings that are correct, and
    the words and their order — what actually identifies the passage — are
    untouched by any of it.
    """
    assert tese.confere(EMENTA, Lida(tese="Uma tese.", trecho=variacao))


def test_a_quote_too_short_to_identify_a_passage_is_refused() -> None:
    """
    `dano moral` occurs in the ementa and in a hundred thousand others. A quote
    that short does not show where a thesis came from, so it does not count as
    showing it.
    """
    curto = Lida(tese="Alguma tese sobre dano moral.", trecho="dano moral")

    assert not tese.confere(EMENTA, curto)
    assert len("dano moral") < tese.MIN_TRECHO


def test_a_quote_without_a_thesis_is_refused() -> None:
    assert not tese.confere(EMENTA, Lida(tese="   ", trecho=TRECHO))


def test_an_empty_answer_is_refused() -> None:
    """
    The instruction asks for two empty fields when the decision settles no
    thesis. That answer is correct and must still not reach the screen.
    """
    assert not tese.confere(EMENTA, Lida(tese="", trecho=""))


def test_the_digest_changes_when_the_ementa_changes() -> None:
    """
    What a kept reading is kept against. The collection is rebuilt from the
    sources on every publication, and a reading of text nobody can see any
    more has to be made again rather than shown.
    """
    assert tese.digest(EMENTA) == tese.digest(EMENTA)
    assert tese.digest(EMENTA) != tese.digest(EMENTA + " EMBARGOS REJEITADOS.")
