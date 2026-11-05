"""
The precedents a decision cites and the adherence of a cut, against PostgreSQL.

The promise is the denominator, and here there are three of them: every
decision the search matches, the ones citing a precedent at all, and the
citations whose wording settled the question. "70% followed" is only ever true
of the third, so these count all three against the real statements over the
real tables.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = needs_database

TERM = "dano moral"
SOURCE = "stj-teste"


def adherence(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get("/indicators/adherence", params={"q": TERM, **params})
    assert response.status_code == 200, response.text
    return response.json()


def most_cited(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get(
        "/indicators/most-cited-precedents", params={"q": TERM, **params}
    )
    assert response.status_code == 200, response.text
    return list(response.json())


def detail(client: TestClient, identifier: str) -> dict[str, Any]:
    response = client.get(f"/decisions/{SOURCE}/{identifier}")
    assert response.status_code == 200, response.text
    return dict(response.json())


def catalogue(db: psycopg.Connection[DictRow], number: int) -> None:
    db.execute(
        "INSERT INTO core.precedente (corte, tipo, numero, enunciado, origem)"
        " VALUES ('STJ', 'sumula', %s, %s, 'reconstruido')",
        (number, f"Enunciado da Súmula {number}."),
    )


def cite(
    db: psycopg.Connection[DictRow],
    identifier: str,
    number: int,
    how: str,
    resolved: bool = True,
    source: str = SOURCE,
    court_stated: bool = True,
) -> None:
    db.execute(
        "INSERT INTO core.decisao_precedente"
        " (fonte_codigo, identificador_fonte, corte, tipo, numero, trecho,"
        "  resolvida, aderencia, corte_declarada)"
        " VALUES (%s, %s, 'STJ', 'sumula', %s, %s, %s, %s, %s)",
        (
            source,
            identifier,
            number,
            f"trecho citando a sumula {number}",
            resolved,
            how,
            court_stated,
        ),
    )


@pytest.fixture
def cited(db_rolled_back: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    """
    Six decisions, four of them citing. One cites two precedents in opposite
    ways, so the per-category decision counts cannot add up to `citing` — and
    one cites a precedent the catalogue never carried.
    """
    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    register(db_rolled_back, "TRF1")

    catalogue(db_rolled_back, 7)
    catalogue(db_rolled_back, 83)

    for name in ("a", "b", "c", "d", "silent"):
        decide(db_rolled_back, "STJ", name)
    decide(db_rolled_back, "TRF1", "other-court")

    cite(db_rolled_back, "a", 7, "seguiu")
    cite(db_rolled_back, "b", 7, "seguiu")
    cite(db_rolled_back, "c", 7, "afastou")
    cite(db_rolled_back, "c", 83, "seguiu")
    cite(db_rolled_back, "d", 7, "indeterminado")
    cite(db_rolled_back, "d", 999, "mencionou", resolved=False)
    cite(db_rolled_back, "other-court", 83, "seguiu", source="trf1-teste")
    return db_rolled_back


@pytest.fixture
def client(cited: psycopg.Connection[DictRow]) -> Any:
    from app.db import get_connection
    from app.main import app

    app.dependency_overrides[get_connection] = lambda: cited
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_the_categories_add_up_to_the_links(client: TestClient) -> None:
    body = adherence(client)

    counted = sum(row["links"] for row in body["adherences"])

    assert counted == body["determined"]
    assert body["determined"] + body["undetermined"] == body["links"]


def test_the_three_denominators_all_travel(client: TestClient) -> None:
    """
    The one the subtask exists for. A share over the citations presented as if
    it were over the cut is wrong in two layers: most decisions cite nothing,
    and some citations settled nothing.
    """
    body = adherence(client)

    assert body["decisions"] == 6
    assert body["citing"] == 5
    assert body["links"] == 7
    assert body["decisions"] > body["citing"] > 0


def test_a_decision_counts_in_every_category_it_used(client: TestClient) -> None:
    """
    Decision `c` followed one precedent and set another aside. Summing the
    per-category decision counts would count it twice, which is why `citing`
    is measured on its own rather than added up.
    """
    body = adherence(client)

    per_category = sum(row["decisions"] for row in body["adherences"])

    assert per_category > body["citing"]


def test_the_share_is_taken_over_the_settled_citations(client: TestClient) -> None:
    body = adherence(client)

    followed = next(r for r in body["adherences"] if r["adherence"] == "seguiu")

    assert followed["links"] == 4
    assert followed["share"] == round(4 / body["determined"] * 100, 1)


def test_the_court_filter_narrows_the_indicator(client: TestClient) -> None:
    """
    It reads through the same `_narrowing` the search uses, so every filter of
    SCRUM-107 restricts it without the endpoint knowing they exist.
    """
    whole = adherence(client)
    only_stj = adherence(client, tribunal=["STJ"])

    assert only_stj["decisions"] < whole["decisions"]
    assert only_stj["links"] == 6


def test_a_cut_with_no_citation_answers_zero_not_an_error(
    client: TestClient,
) -> None:
    body = adherence(client, tribunal=["TRF1"], date_from="2030-01-01")

    assert body["links"] == 0
    assert body["adherences"] == []


def test_the_four_categories_are_always_present(client: TestClient) -> None:
    """
    A category absent from the cut has to come back as zero. Dropping it would
    make a chart lose a bar between two searches, which reads as data rather
    than as absence.
    """
    named = {row["adherence"] for row in adherence(client)["adherences"]}

    assert named == {"seguiu", "afastou", "distinguiu", "mencionou"}


def test_a_decision_citing_nothing_answers_an_empty_list(client: TestClient) -> None:
    assert detail(client, "silent")["precedents"] == []


def test_an_unresolved_citation_is_shown_without_its_text(
    client: TestClient,
) -> None:
    """
    The catalogue misses 4% of what the courts cite. Hiding those would show
    fewer precedents than the decision names, so the citation travels with its
    snippet and a null text.
    """
    cited_here = detail(client, "d")["precedents"]

    unresolved = next(p for p in cited_here if p["number"] == 999)

    assert unresolved["resolved"] is False
    assert unresolved["text"] is None
    assert unresolved["snippet"]
    assert len(cited_here) == 2


def test_the_detail_carries_the_text_when_the_catalogue_has_it(
    client: TestClient,
) -> None:
    only = detail(client, "a")["precedents"][0]

    assert only["resolved"] is True
    assert only["text"] == "Enunciado da Súmula 7."
    assert only["adherence"] == "seguiu"


def test_the_most_cited_ranks_by_how_often_the_cut_invokes_each(
    client: TestClient,
) -> None:
    ranked = most_cited(client)

    assert [p["number"] for p in ranked] == [7, 83, 999]
    assert ranked[0]["citations"] == 4
    assert ranked[0]["decisions"] == 4


def test_a_precedent_outside_the_catalogue_still_ranks(client: TestClient) -> None:
    missing = next(p for p in most_cited(client) if p["number"] == 999)

    assert missing["text"] is None
    assert missing["citations"] == 1


def test_the_most_cited_obeys_the_limit(client: TestClient) -> None:
    assert len(most_cited(client, limit=1)) == 1


def test_a_thesis_is_never_answered_for_a_court_nobody_named(
    cited: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    The fixtures hid this one: the detail joined the catalogue on the court
    the extraction had guessed, so a bare "Tema 793" came back carrying the
    STJ's thesis even with `resolved` false. Both courts have a Tema 793, and
    answering with the wrong one's is worse than answering nothing.
    """
    # The catalogue has to hold it, or the join comes back empty for the right
    # reason and the test proves nothing.
    catalogue(cited, 500)
    cite(cited, "a", 500, "seguiu", resolved=False, court_stated=False)

    bare = next(
        p for p in detail(client, "a")["precedents"] if p["court_stated"] is False
    )

    assert bare["resolved"] is False
    assert bare["text"] is None


def test_a_citation_naming_no_court_is_left_out_of_the_ranking(
    cited: psycopg.Connection[DictRow], client: TestClient
) -> None:
    """
    It identifies no precedent, so it cannot be ranked under one: counting it
    among the STJ's would pad that row with citations of the STF's.
    """
    before = next(row for row in most_cited(client) if row["number"] == 83)["citations"]
    # Same decision, same precedent, cited again without naming the court: the
    # key allows it only because `b` had no link to 83 yet.
    cite(cited, "d", 83, "seguiu", resolved=False, court_stated=False)

    assert (
        next(row for row in most_cited(client) if row["number"] == 83)["citations"]
        == before
    )
