"""
The on-demand thesis route, against PostgreSQL.

The model is stubbed everywhere here. What is worth protecting is not that
Gemini answers — that is Google's problem — but what this API does with the
answer: what it refuses to show, what it refuses to keep, and what it never
asks twice.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app import agente, tese
from app.tese import Lida
from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = needs_database

DECISION = "900001"
SOURCE = "stj-teste"
ROUTE = f"/decisions/{SOURCE}/{DECISION}/thesis"

# `decide` writes "CIVIL. Dano moral configurado. Decisão 900001." — long
# enough to quote from, once the quote has to reach MIN_TRECHO.
QUOTE = "CIVIL. Dano moral configurado. Decisão 900001."


@pytest.fixture
def collection(db_rolled_back: psycopg.Connection[DictRow]) -> Any:
    from app.db import get_connection
    from app.main import app

    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    decide(db_rolled_back, "STJ", DECISION)

    # No `with`: entering the client runs the lifespan, and the connection pool
    # it opens refuses to be opened a second time. The route gets its
    # connection from the override above, so the pool is not wanted here.
    app.dependency_overrides[get_connection] = lambda: db_rolled_back
    yield TestClient(app)
    app.dependency_overrides.pop(get_connection, None)


@pytest.fixture(autouse=True)
def with_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "google_api_key", "chave-de-teste")
    monkeypatch.setattr(settings, "gemini_model", "modelo-de-teste")


def answering(monkeypatch: pytest.MonkeyPatch, lida: Lida | None) -> list[str]:
    """Stub the agent and record every ementa it was asked about."""
    asked: list[str] = []

    async def ler(ementa: str) -> Lida | None:
        asked.append(ementa)
        return lida

    monkeypatch.setattr(agente, "ler", ler)
    return asked


def test_a_verified_reading_is_returned_with_its_passage(
    collection: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    answering(monkeypatch, Lida(tese="O dano moral está configurado.", trecho=QUOTE))

    response = collection.post(ROUTE)

    assert response.status_code == 200
    body = response.json()
    assert body["thesis"] == "O dano moral está configurado."
    assert body["passage"] == QUOTE
    assert body["model"] == "modelo-de-teste"
    assert body["cached"] is False


def test_a_reading_the_ementa_does_not_support_is_not_shown(
    collection: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The model answered, fluently, about a decision it was not reading. The
    reader gets the same "no thesis identified" as for an empty answer.
    """
    answering(
        monkeypatch,
        Lida(
            tese="A prescrição é de cinco anos.",
            trecho="O prazo prescricional da pretensão indenizatória é quinquenal.",
        ),
    )

    response = collection.post(ROUTE)

    assert response.status_code == 200
    assert response.json()["thesis"] is None


def test_a_reading_that_was_not_shown_is_not_kept(
    collection: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Caching a refusal would make it permanent. The model may do better on the
    next ask, and nothing was shown, so nothing is owed.
    """
    answering(
        monkeypatch,
        Lida(tese="Inventada.", trecho="Passagem que não está na ementa nenhuma."),
    )

    collection.post(ROUTE)

    with db_rolled_back.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS guardadas FROM leitura.tese")
        found = cursor.fetchone()

    assert found is not None
    assert found["guardadas"] == 0


def test_the_second_reader_does_not_pay_for_the_first_reading(
    collection: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = answering(
        monkeypatch, Lida(tese="O dano moral está configurado.", trecho=QUOTE)
    )

    first = collection.post(ROUTE)
    second = collection.post(ROUTE)

    assert len(asked) == 1, "the model was asked again for a reading already made"
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert second.json()["thesis"] == first.json()["thesis"]


def test_a_reading_of_an_ementa_that_changed_is_made_again(
    collection: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The collection is rebuilt from the sources on every publication. A reading
    of the old text would describe a passage no longer on the screen.
    """
    asked = answering(
        monkeypatch, Lida(tese="O dano moral está configurado.", trecho=QUOTE)
    )
    collection.post(ROUTE)

    db_rolled_back.execute(
        "UPDATE core.decisao SET ementa = ementa || ' EMBARGOS REJEITADOS.'"
        " WHERE identificador_fonte = %s",
        (DECISION,),
    )
    collection.post(ROUTE)

    assert len(asked) == 2


def test_a_decision_with_the_courts_own_thesis_is_refused(
    collection: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The court wrote one. Putting a machine reading beside it would offer the
    reader a choice between the court's words and ours, over the court's name.
    """
    asked = answering(monkeypatch, Lida(tese="Qualquer.", trecho=QUOTE))
    db_rolled_back.execute(
        "UPDATE core.decisao SET tese = ARRAY['A tese do tribunal.']"
        " WHERE identificador_fonte = %s",
        (DECISION,),
    )

    response = collection.post(ROUTE)

    assert response.status_code == 409
    assert asked == []


def test_an_unknown_decision_answers_404(
    collection: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked = answering(monkeypatch, Lida(tese="Qualquer.", trecho=QUOTE))

    assert collection.post("/decisions/stj-teste/000000/thesis").status_code == 404
    assert asked == []


def test_a_nul_byte_in_the_path_answers_404_rather_than_a_stack_trace(
    collection: TestClient,
) -> None:
    assert collection.post("/decisions/stj-teste/9%0000/thesis").status_code == 404


def test_without_a_key_the_route_says_so_instead_of_failing(
    collection: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "google_api_key", "")
    asked = answering(monkeypatch, Lida(tese="Qualquer.", trecho=QUOTE))

    response = collection.post(ROUTE)

    assert response.status_code == 501
    assert asked == []


def test_a_model_that_cannot_be_reached_answers_503(
    collection: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def ler(ementa: str) -> Lida | None:
        raise TimeoutError("the model did not answer")

    monkeypatch.setattr(agente, "ler", ler)

    response = collection.post(ROUTE)

    assert response.status_code == 503
    assert "Tente de novo" in response.json()["detail"]


def test_the_route_is_behind_the_gate(
    collection: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    It spends money. An anonymous caller must not be able to spend it, and the
    gate is closed by default precisely so a route added later is covered
    without anyone remembering to cover it.
    """
    from app.main import app
    from app.sessions import gate

    answering(monkeypatch, Lida(tese="Qualquer.", trecho=QUOTE))
    guard = app.dependency_overrides.pop(gate, None)

    try:
        assert collection.post(ROUTE).status_code == 401
    finally:
        if guard is not None:
            app.dependency_overrides[gate] = guard


def test_a_decision_with_no_ementa_asks_nothing(
    collection: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = answering(monkeypatch, Lida(tese="Qualquer.", trecho=QUOTE))
    db_rolled_back.execute(
        "UPDATE core.decisao SET ementa = '' WHERE identificador_fonte = %s",
        (DECISION,),
    )

    response = collection.post(ROUTE)

    assert response.status_code == 200
    assert response.json()["thesis"] is None
    assert asked == []


def test_what_is_kept_is_what_was_verified(
    collection: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The stored row carries the passage and the model, which is what makes a
    reading attributable months later — and what lets a reading made by an
    older model be found and redone.
    """
    answering(monkeypatch, Lida(tese="O dano moral está configurado.", trecho=QUOTE))

    collection.post(ROUTE)

    with db_rolled_back.cursor() as cursor:
        cursor.execute("SELECT * FROM leitura.tese")
        kept = cursor.fetchone()

    assert kept is not None
    assert kept["trecho"] == QUOTE
    assert kept["modelo"] == "modelo-de-teste"
    assert kept["fonte_codigo"] == SOURCE
    assert kept["ementa_digest"] == tese.digest(
        f"CIVIL. Dano moral configurado. Decisão {DECISION}."
    )


def test_a_decision_that_settles_no_thesis_says_so(
    collection: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The instruction asks for two empty fields when the ementa settles nothing,
    and three decisions in sixteen answer that way. Reporting it as a failure
    to read would blame the tool for a fact about the decision.
    """
    answering(monkeypatch, Lida(tese="", trecho=""))

    body = collection.post(ROUTE).json()

    assert body["outcome"] == "none"
    assert body["thesis"] is None


def test_a_reading_the_ementa_does_not_support_is_marked_unverified(
    collection: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    answering(
        monkeypatch,
        Lida(tese="Inventada.", trecho="Passagem que não está em ementa nenhuma."),
    )

    body = collection.post(ROUTE).json()

    assert body["outcome"] == "unverified"
    assert body["thesis"] is None


def test_a_verified_reading_is_marked_read(
    collection: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    answering(monkeypatch, Lida(tese="O dano moral está configurado.", trecho=QUOTE))

    assert collection.post(ROUTE).json()["outcome"] == "read"
