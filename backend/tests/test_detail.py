"""
Guards on the detail endpoint: what it must answer, and what it must refuse.

Written before touching the endpoint, so the behaviour that already holds cannot
quietly change while the rest of the card is built.
"""

import re
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api.decisions import MAX_SNIPPET_WORDS
from app.db import get_connection
from app.main import app
from tests.conftest import FIXTURES, needs_database
from tests.test_seal_filter import SEALED, transformation

pytestmark = needs_database

SOURCE = "tjdft-jurisdf"
PRESENT = "1000001"
# Longer than the snippet cut, so a truncated ementa is visible here.
LONG = "1000004"


@pytest.fixture
def client(db: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_the_detail_returns_the_ementa_byte_for_byte(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    """
    "Devolve a ementa completa" means all of it. Asserting only that a string
    came back would pass on a truncated one, which is how a detail page ends up
    showing the first few lines of a judgement.
    """
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT ementa FROM core.decisao WHERE identificador_fonte = %s",
            (LONG,),
        )
        row = cursor.fetchone()

    assert row is not None
    assert len(row["ementa"].split()) > MAX_SNIPPET_WORDS, (
        "the fixture ementa is shorter than the snippet cut, so truncation "
        "would pass unnoticed here"
    )

    body = client.get(f"/decisions/{SOURCE}/{LONG}").json()

    assert body["summary"] == row["ementa"]


def test_a_sealed_decision_is_not_reachable_by_its_own_identifier(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    """
    The card asks for this explicitly. Nothing hides these records at the
    endpoint: the transformation never lets them into `core.decisao`, so the
    lookup finds nothing. This walks the whole chain — sealed in raw, absent
    from the transformation, 404 at the door — so that removing any one link
    fails here.
    """
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))

    with db.cursor() as cursor:
        cursor.execute(
            'SELECT identificador FROM raw.acordao_tjdft WHERE "segredoJustica"'
        )
        sealed = {row["identificador"] for row in cursor.fetchall()}

        cursor.execute("DROP TABLE IF EXISTS core.decisao_do_teste")
        cursor.execute(f"CREATE TABLE core.decisao_do_teste AS {transformation()}")
        cursor.execute("SELECT identificador_fonte FROM core.decisao_do_teste")
        survived = {row["identificador_fonte"] for row in cursor.fetchall()}

    assert sealed == SEALED, "the fixture stopped carrying sealed records"
    assert sealed & survived == set(), "a sealed record reached the core"

    for identificador in sealed:
        response = client.get(f"/decisions/{SOURCE}/{identificador}")
        assert response.status_code == 404, identificador


def test_no_shape_of_bad_identifier_reaches_a_500(client: TestClient) -> None:
    """
    An identifier arrives from the URL, so it is whatever the caller typed. The
    endpoint has to answer, not fail: 404 for something it cannot find, never a
    stack trace.
    """
    shapes = [
        "000000",
        "nao-e-numero",
        "'; DROP TABLE core.decisao; --",
        "../../etc/passwd",
        # percent-encoded, which is how a NUL byte actually arrives
        "%00",
        "2071373%00",
        "1" * 500,
        "2071373 OR 1=1",
        "ção-com-acento",
    ]

    for identificador in shapes:
        response = client.get(f"/decisions/{SOURCE}/{identificador}")
        assert response.status_code == 404, (
            f"{identificador[:30]} answered {response.status_code}"
        )
        assert isinstance(response.json()["detail"], str)


def test_an_unknown_source_answers_404(client: TestClient) -> None:
    """
    A second court that does not exist yet must not return another court's
    decision because the identifier happens to match.
    """
    response = client.get(f"/decisions/tribunal-inexistente/{PRESENT}")

    assert response.status_code == 404


def test_the_decision_still_survives_a_lookup_that_should_work(
    client: TestClient,
) -> None:
    """
    Guards the guard: if this fails, the tests above pass because nothing is
    reachable at all.
    """
    response = client.get(f"/decisions/{SOURCE}/{PRESENT}")

    assert response.status_code == 200
    assert response.json()["identifier"] == PRESENT


def test_the_whole_ementa_survives_a_term_that_does_not_appear_in_it(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    """
    A search matches by stem, so the reader can arrive from a term that is
    nowhere in the text. The detail is a reading screen: it answers with the
    judgement, highlighted or not, never with its first few lines.
    """
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT ementa FROM core.decisao WHERE identificador_fonte = %s",
            (LONG,),
        )
        row = cursor.fetchone()

    assert row is not None
    body = client.get(f"/decisions/{SOURCE}/{LONG}", params={"q": "xyzabc"}).json()

    assert "<mark>" not in body["summary"]
    assert len(body["summary"].split()) == len(row["ementa"].split())


def test_a_term_that_does_appear_still_marks_without_losing_the_rest(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT ementa FROM core.decisao WHERE identificador_fonte = %s",
            (LONG,),
        )
        row = cursor.fetchone()

    assert row is not None
    body = client.get(f"/decisions/{SOURCE}/{LONG}", params={"q": "prescrição"}).json()
    summary = body["summary"]

    assert "<mark>" in summary
    stripped = re.sub(r"</?mark>", "", summary)
    assert len(stripped.split()) == len(row["ementa"].split())


def test_a_structured_ementa_comes_back_in_sections(client: TestClient) -> None:
    body = client.get(f"/decisions/{SOURCE}/{LONG}").json()
    sections = body["sections"]

    assert sections is not None
    assert "Apelação interposta" in sections["case"]
    assert "termo inicial da suspensão" in sections["question"]
    assert "artigo 40" in sections["reasoning"]
    assert "desprovida" in sections["ruling"]
    assert sections["headnote"].startswith("PROCESSUAL CIVIL")


def test_free_prose_says_so_instead_of_guessing(client: TestClient) -> None:
    """
    Sixteen per cent of the collection is not written in the shape. `null` is
    how the two cases are told apart.
    """
    body = client.get(f"/decisions/{SOURCE}/{PRESENT}").json()

    assert body["sections"] is None
    assert body["summary"] != ""


def test_the_sections_keep_every_word_of_the_ementa(
    client: TestClient, db: psycopg.Connection[DictRow]
) -> None:
    """
    The card asks that nothing be lost. Read through the endpoint rather than
    the splitter, so a field dropped on the way out is caught here too.
    """
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT ementa FROM core.decisao WHERE identificador_fonte = %s",
            (LONG,),
        )
        row = cursor.fetchone()

    assert row is not None
    sections = client.get(f"/decisions/{SOURCE}/{LONG}").json()["sections"]
    joined = " ".join(
        sections[name]
        for name in ("headnote", "case", "question", "reasoning", "ruling")
    )

    original = set(row["ementa"].split())
    served = set(joined.split())
    assert original - served <= {
        "I.",
        "II.",
        "III.",
        "IV.",
        "CASO",
        "EM",
        "EXAME",
        "QUESTÃO",
        "DISCUSSÃO",
        "RAZÕES",
        "DE",
        "DECIDIR",
        "DISPOSITIVO",
    }, "words other than the section labels went missing"


def test_the_search_term_never_changes_whether_it_is_structured(
    client: TestClient,
) -> None:
    """
    Sections are read from the court's own text. Splitting the highlighted copy
    would make a search for "caso" mark the label itself and turn a structured
    decision into an unstructured one.
    """
    plain = client.get(f"/decisions/{SOURCE}/{LONG}").json()["sections"]

    for term in ("caso", "dispositivo", "prescrição", "xyzabc"):
        with_term = client.get(
            f"/decisions/{SOURCE}/{LONG}", params={"q": term}
        ).json()["sections"]
        assert with_term == plain, term
