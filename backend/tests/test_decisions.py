from collections.abc import Callable, Iterator
from datetime import date
from typing import Any, Self

import pytest
from fastapi.testclient import TestClient

from app.api.decisions import (
    COUNT_SQL,
    DETAIL_SQL,
    HIGHLIGHT_SQL,
    MAX_SNIPPET_WORDS,
    PAGE_SQL,
    _fallback_ementa_start,
    _normalize_highlighted_text,
    _safe_snippet,
)
from app.db import get_connection
from app.main import app

MATCHING_ROW = {
    "fonte_codigo": "tjdft-jurisdf",
    "identificador_fonte": "2084700",
    "tribunal_sigla": "TJDFT",
    "processo": "0738852-37.2024.8.07.0003",
    "orgao_julgador": "1ª TURMA CÍVEL",
    "relator": "FABRÍCIO FONTOURA BEZERRA",
    "data_referencia": date(2026, 1, 28),
    "turma_recursal": False,
    "url_fonte": "https://jurisdf.tjdft.jus.br/detalhes/2084700",
    "link_valido": True,
    "ementa": "Ilícito contratual. Dano moral. Ação procedente. Recurso não provido.",
    "snippet": "Ilícito contratual. <mark>Dano</mark> <mark>moral</mark>.",
}

DETAIL_ROW = {
    **{key: value for key, value in MATCHING_ROW.items() if key != "snippet"},
    "classe_cnj": 198,
    "data_julgamento": date(2026, 1, 28),
    "data_publicacao": date(2026, 2, 26),
    "ementa": "Ementa: Direito do consumidor. Dano moral configurado.",
    "decisao_texto": "RECURSOS PARCIALMENTE PROVIDOS. UNÂNIME.",
    "possui_inteiro_teor": True,
}


class FakeCursor:
    def __init__(self, database: "FakeDatabase") -> None:
        self.database = database
        self.result: list[dict[str, Any]] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, statement: str, parameters: dict[str, Any]) -> None:
        self.database.statements.append(statement)
        self.database.parameters.append(parameters)
        self.result = self.database.answer(statement, parameters)

    def fetchone(self) -> dict[str, Any] | None:
        return self.result[0] if self.result else None

    def fetchall(self) -> list[dict[str, Any]]:
        return self.result


class FakeDatabase:
    def __init__(self, total: int = 1, found: bool = True) -> None:
        self.total = total
        self.found = found
        self.statements: list[str] = []
        self.parameters: list[dict[str, Any]] = []
        self.answer: Callable[[str, dict[str, Any]], list[dict[str, Any]]] = (
            self._default_answer
        )

    def _default_answer(
        self, statement: str, parameters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        if statement == COUNT_SQL:
            return [{"total": self.total}]
        if statement == PAGE_SQL:
            return [MATCHING_ROW] * min(self.total, parameters["limit"])
        if statement == DETAIL_SQL:
            return [DETAIL_ROW] if self.found else []
        if statement == HIGHLIGHT_SQL:
            return [{"highlighted": "Ementa: <mark>Dano</mark> moral configurado."}]
        raise AssertionError(f"unexpected statement: {statement}")

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)


@pytest.fixture
def database() -> Iterator[FakeDatabase]:
    fake = FakeDatabase()

    def override() -> Iterator[FakeDatabase]:
        yield fake

    app.dependency_overrides[get_connection] = override
    yield fake
    app.dependency_overrides.clear()


@pytest.fixture
def client(database: FakeDatabase) -> TestClient:
    return TestClient(app)


def test_exact_phrase_highlight_is_grouped_in_one_mark() -> None:
    value = (
        "Discussão sobre <mark>prescrição</mark> <mark>intercorrente</mark> no caso."
    )

    assert _normalize_highlighted_text(value, '"prescrição intercorrente"') == (
        "Discussão sobre <mark>prescrição intercorrente</mark> no caso."
    )


def test_simple_terms_stay_separate_when_they_do_not_form_the_same_phrase() -> None:
    value = (
        "Discussão sobre <mark>prescrição</mark> e <mark>intercorrente</mark> no caso."
    )

    assert _normalize_highlighted_text(value, "prescrição intercorrente") == value


def test_words_separated_by_text_do_not_merge_into_a_phrase() -> None:
    value = "Discussão sobre <mark>prescrição</mark> qualquer coisa <mark>intercorrente</mark> no caso."

    assert _normalize_highlighted_text(value, '"prescrição intercorrente"') == value


def test_stem_match_without_the_literal_term_is_kept_as_real_highlight_when_available() -> (
    None
):
    value = "<mark>Dano</mark> moral configurado. Danos materiais afastados."

    assert _normalize_highlighted_text(value, '"dano moral"') == value


def test_fallback_returns_the_ementa_start_when_no_mark_is_available() -> None:
    assert (
        _normalize_highlighted_text("Sem destaque aqui.", "dano moral")
        == "Sem destaque aqui."
    )
    assert _safe_snippet(
        "Sem destaque aqui.", "Direito do consumidor. Dano moral configurado."
    ) == ("Direito do consumidor. Dano moral configurado.")


def test_fallback_keeps_reading_past_the_opening_headnotes() -> None:
    """
    Ementas open with short headnote sentences in caps. Stopping at the second
    one leaves the card with a couple of words, which is what a sentence-based
    trim did: under 80 characters in 91% of the collection.
    """
    ementa = (
        "DIREITO DO CONSUMIDOR. APELAÇÃO CÍVEL. "
        "Contrato de transporte com atraso na entrega da mercadoria, "
        "reconhecida a falha na prestação do serviço e o dever de indenizar."
    )

    snippet = _safe_snippet(None, ementa)

    assert snippet.startswith("DIREITO DO CONSUMIDOR. APELAÇÃO CÍVEL.")
    assert "transporte" in snippet
    assert len(snippet) > 80


def test_fallback_trims_a_long_ementa_without_cutting_a_word() -> None:
    ementa = " ".join(f"palavra{n}" for n in range(200))

    snippet = _safe_snippet(None, ementa)

    assert len(snippet.split()) == MAX_SNIPPET_WORDS
    assert snippet.endswith(f"palavra{MAX_SNIPPET_WORDS - 1}")
    assert ementa.startswith(snippet)


def test_the_search_and_the_detail_trim_the_ementa_the_same_way() -> None:
    """
    Two rules for the same text drift apart. The detail endpoint builds its
    summary from the same helper the search falls back to.
    """
    ementa = " ".join(f"palavra{n}" for n in range(200))

    assert _safe_snippet(None, ementa) == _fallback_ementa_start(ementa)


def test_empty_and_none_ementas_return_empty_snippet() -> None:
    assert _safe_snippet(None, None) == ""
    assert _safe_snippet(None, "") == ""


def test_marked_output_escapes_raw_html_but_keeps_controlled_marks() -> None:
    value = '<script>alert("x")</script> <mark>prescrição</mark> & <b>falso</b>'

    assert _normalize_highlighted_text(value) == (
        '&lt;script&gt;alert("x")&lt;/script&gt; '
        "<mark>prescrição</mark> &amp; &lt;b&gt;falso&lt;/b&gt;"
    )


def test_search_returns_the_total_and_the_page(
    client: TestClient, database: FakeDatabase
) -> None:
    database.total = 1847

    body = client.get("/decisions", params={"q": "dano moral"}).json()

    assert body["total"] == 1847
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["results"]) == 20


def test_search_result_carries_the_highlighted_snippet(client: TestClient) -> None:
    body = client.get("/decisions", params={"q": "dano moral"}).json()

    assert body["results"][0]["snippet"] == MATCHING_ROW["snippet"]
    assert "summary" not in body["results"][0]


def test_search_returns_the_start_of_the_ementa_when_no_highlight_is_found(
    client: TestClient, database: FakeDatabase
) -> None:
    database.total = 1
    database.answer = lambda statement, parameters: (
        [{"total": 1}]
        if statement == COUNT_SQL
        else [
            {
                **MATCHING_ROW,
                "ementa": MATCHING_ROW["ementa"],
                "snippet": "Ilícito contratual. Dano moral. Ação procedente.",
            }
        ]
        if statement == PAGE_SQL
        else []
    )

    body = client.get("/decisions", params={"q": "dano moral"}).json()

    assert "<mark>" not in body["results"][0]["snippet"]
    assert body["results"][0]["snippet"].startswith("Ilícito contratual. Dano moral.")


def test_search_handles_short_and_empty_ementas(client: TestClient) -> None:
    body = client.get("/decisions", params={"q": "dano moral"}).json()

    assert "" != body["results"][0]["snippet"]
    assert "<mark>" in body["results"][0]["snippet"]


def test_search_maps_every_column_the_screen_needs(client: TestClient) -> None:
    result = client.get("/decisions", params={"q": "dano moral"}).json()["results"][0]

    assert result["identifier"] == "2084700"
    assert result["court"] == "TJDFT"
    assert result["case_number"] == "0738852-37.2024.8.07.0003"
    assert result["reporting_judge"] == "FABRÍCIO FONTOURA BEZERRA"
    assert result["decided_on"] == "2026-01-28"
    assert result["source_url"].endswith("/2084700")


def test_search_skips_the_page_query_when_nothing_matches(
    client: TestClient, database: FakeDatabase
) -> None:
    database.total = 0

    body = client.get("/decisions", params={"q": "termo inexistente"}).json()

    assert body["total"] == 0
    assert body["results"] == []
    assert PAGE_SQL not in database.statements


def test_paging_translates_into_an_offset(
    client: TestClient, database: FakeDatabase
) -> None:
    database.total = 100

    client.get("/decisions", params={"q": "dano", "page": 3, "page_size": 20})

    assert database.parameters[-1]["offset"] == 40
    assert database.parameters[-1]["limit"] == 20


def test_page_size_is_capped(client: TestClient, database: FakeDatabase) -> None:
    database.total = 5000

    body = client.get("/decisions", params={"q": "dano", "page_size": 9999}).json()

    assert body["page_size"] == 100


def test_search_rejects_a_term_that_is_too_short(client: TestClient) -> None:
    assert client.get("/decisions", params={"q": "a"}).status_code == 422


def test_search_rejects_a_page_below_one(client: TestClient) -> None:
    assert client.get("/decisions", params={"q": "dano", "page": 0}).status_code == 422


def test_search_requires_a_term(client: TestClient) -> None:
    assert client.get("/decisions").status_code == 422


def test_detail_returns_the_whole_ementa(client: TestClient) -> None:
    body = client.get("/decisions/tjdft-jurisdf/2084700").json()

    assert body["summary"] == DETAIL_ROW["ementa"]
    assert body["class_code"] == 198
    assert body["judged_on"] == "2026-01-28"
    assert body["published_on"] == "2026-02-26"
    assert body["full_text_available"] is True


def test_detail_highlights_when_the_search_term_comes_along(
    client: TestClient, database: FakeDatabase
) -> None:
    body = client.get(
        "/decisions/tjdft-jurisdf/2084700", params={"q": "dano moral"}
    ).json()

    assert "<mark>Dano</mark>" in body["summary"]
    assert HIGHLIGHT_SQL in database.statements


def test_detail_leaves_the_ementa_alone_without_a_term(
    client: TestClient, database: FakeDatabase
) -> None:
    client.get("/decisions/tjdft-jurisdf/2084700")

    assert HIGHLIGHT_SQL not in database.statements


def test_detail_answers_404_when_the_decision_does_not_exist(
    client: TestClient, database: FakeDatabase
) -> None:
    database.found = False

    response = client.get("/decisions/tjdft-jurisdf/000000")

    assert response.status_code == 404
    assert response.json()["detail"] == "Decision not found."


def test_detail_looks_the_decision_up_by_its_natural_key(
    client: TestClient, database: FakeDatabase
) -> None:
    client.get("/decisions/tjdft-jurisdf/2084700")

    assert database.parameters[0] == {
        "source": "tjdft-jurisdf",
        "identifier": "2084700",
    }
