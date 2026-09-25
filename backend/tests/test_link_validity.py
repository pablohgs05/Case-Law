from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.api import decisions as decisions_module
from app.db import get_connection
from app.main import app
from tests.conftest import FIXTURES, needs_database
from tests.test_seal_filter import MODEL, transformation

pytestmark = [needs_database, pytest.mark.integration]

CARGA_MODEL = MODEL.parent / "core_carga.sql"

VERIFIED = "1000001"
BROKEN = "1000002"
UNVERIFIED = "1000003"


@pytest.fixture
def client(db: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def reachable(client: TestClient, identifier: str) -> object:
    body = client.get(f"/decisions/tjdft-jurisdf/{identifier}").json()
    return body["source_url_reachable"]


def test_the_three_states_reach_the_screen(client: TestClient) -> None:
    """
    Unverified is its own answer. Collapsing it into "broken" would disable a
    link that works; collapsing it into "fine" would hide one that does not.
    """
    assert reachable(client, VERIFIED) is True
    assert reachable(client, BROKEN) is False
    assert reachable(client, UNVERIFIED) is None


def test_the_search_carries_the_same_answer_as_the_detail(
    client: TestClient,
) -> None:
    body = client.get("/decisions", params={"q": "recurso OR apelação"}).json()
    by_identifier = {
        r["identifier"]: r["source_url_reachable"] for r in body["results"]
    }

    assert by_identifier, "the query matched nothing, so it would prove nothing"
    for identifier, answer in by_identifier.items():
        assert answer == reachable(client, identifier), identifier


def test_the_search_never_asks_the_court(client: TestClient) -> None:
    """
    The whole point of checking at load time. A request that reached the portal
    would make the search as slow and as available as the court's own site.
    """
    source = Path(decisions_module.__file__).read_text(encoding="utf-8")

    for forbidden in ("requests", "httpx", "urllib", "aiohttp", "socket"):
        assert forbidden not in source, f"the search endpoint imports {forbidden}"


def test_a_record_nobody_checked_comes_out_unverified(
    db: psycopg.Connection[DictRow],
) -> None:
    """
    The transformation runs against an empty verification table, which is what a
    fresh database looks like before the first check.
    """
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db.execute("TRUNCATE verificacao.link")
    db.execute("DROP TABLE IF EXISTS core.decisao_sem_verificacao")
    db.execute(f"CREATE TABLE core.decisao_sem_verificacao AS {transformation()}")

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) AS total FROM core.decisao_sem_verificacao "
            "WHERE link_valido IS NOT NULL"
        )
        row = cursor.fetchone()

    assert row is not None
    assert row["total"] == 0


def test_a_checked_record_carries_the_answer_through_the_transformation(
    db: psycopg.Connection[DictRow],
) -> None:
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db.execute("TRUNCATE verificacao.link")
    db.execute(
        "INSERT INTO verificacao.link (fonte_codigo, identificador, valido) "
        "VALUES ('tjdft-jurisdf', '9000001', TRUE), ('tjdft-jurisdf', '9000002', FALSE)"
    )
    db.execute("DROP TABLE IF EXISTS core.decisao_verificada")
    db.execute(f"CREATE TABLE core.decisao_verificada AS {transformation()}")

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT identificador_fonte, link_valido FROM core.decisao_verificada "
            "WHERE identificador_fonte IN ('9000001', '9000002', '9000003')"
        )
        found = {r["identificador_fonte"]: r["link_valido"] for r in cursor.fetchall()}

    assert found == {"9000001": True, "9000002": False, "9000003": None}


def carga_transformation() -> str:
    text = CARGA_MODEL.read_text(encoding="utf-8")
    body = text.split("\n);\n", 1)[1]
    return body.split("*/", 1)[1].strip().rstrip(";").strip()


def test_the_load_record_counts_broken_and_unchecked_links(
    db: psycopg.Connection[DictRow],
) -> None:
    """
    Criterion of the card: the count belongs in the load record. Unchecked is
    reported beside invalid, because zero invalid means little when nobody
    looked.
    """
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db.execute("TRUNCATE verificacao.link")
    db.execute(
        "INSERT INTO verificacao.link (fonte_codigo, identificador, valido) "
        "VALUES ('tjdft-jurisdf', '9000001', TRUE), ('tjdft-jurisdf', '9000002', FALSE), ('tjdft-jurisdf', '9000003', FALSE)"
    )
    db.execute("DROP TABLE IF EXISTS core.carga_apurada")
    db.execute(f"CREATE TABLE core.carga_apurada AS {carga_transformation()}")

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT SUM(links_invalidos) AS invalidos, "
            "SUM(links_nao_verificados) AS nao_verificados FROM core.carga_apurada"
        )
        row = cursor.fetchone()

    assert row is not None
    # Four records reach the core; three of them were checked above, so the
    # only one left unchecked is the record with no seal flag.
    assert row["invalidos"] == 2
    assert row["nao_verificados"] == 1


def test_a_sealed_record_is_never_counted_as_a_broken_link(
    db: psycopg.Connection[DictRow],
) -> None:
    """
    Sealed records never reach the core, so counting their links would report a
    problem on rows nobody can open.
    """
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db.execute("TRUNCATE verificacao.link")
    db.execute(
        "INSERT INTO verificacao.link (fonte_codigo, identificador, valido) "
        "VALUES ('tjdft-jurisdf', '9000004', FALSE), ('tjdft-jurisdf', '9000005', FALSE)"
    )
    db.execute("DROP TABLE IF EXISTS core.carga_sigilo")
    db.execute(f"CREATE TABLE core.carga_sigilo AS {carga_transformation()}")

    with db.cursor() as cursor:
        cursor.execute("SELECT SUM(links_invalidos) AS total FROM core.carga_sigilo")
        row = cursor.fetchone()

    assert row is not None
    assert row["total"] == 0


def test_a_verdict_belongs_to_the_source_that_produced_it(
    db: psycopg.Connection[DictRow],
) -> None:
    """
    Two collections number from 1, so the same identifier names a different
    decision in each. A verdict matched by the identifier alone lands on the
    wrong decision, and the screen shows a link as broken because another
    court's document went away.
    """
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db.execute("TRUNCATE verificacao.link")
    db.execute(
        "INSERT INTO verificacao.link (fonte_codigo, identificador, valido) "
        "VALUES ('stj-espelhos', '9000001', FALSE), "
        "       ('tjdft-jurisdf', '8000001', FALSE)"
    )
    db.execute("DROP TABLE IF EXISTS core.decisao_cruzada")
    db.execute(f"CREATE TABLE core.decisao_cruzada AS {transformation()}")

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT fonte_codigo, identificador_fonte, link_valido "
            "FROM core.decisao_cruzada "
            "WHERE identificador_fonte IN ('9000001', '8000001')"
        )
        found = {
            (r["fonte_codigo"], r["identificador_fonte"]): r["link_valido"]
            for r in cursor.fetchall()
        }

    assert found == {
        ("tjdft-jurisdf", "9000001"): None,
        ("stj-espelhos", "8000001"): None,
    }


def test_a_source_nobody_checked_yet_stays_unverified(
    db: psycopg.Connection[DictRow],
) -> None:
    """A verdict never appears for a source that has none of its own."""
    db.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db.execute("TRUNCATE verificacao.link")
    db.execute(
        "INSERT INTO verificacao.link (fonte_codigo, identificador, valido) "
        "VALUES ('tjdft-jurisdf', '9000001', TRUE)"
    )
    db.execute("DROP TABLE IF EXISTS core.decisao_sem_checagem")
    db.execute(f"CREATE TABLE core.decisao_sem_checagem AS {transformation()}")

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FILTER (WHERE link_valido IS NULL) AS sem_verdito, "
            "count(*) AS total FROM core.decisao_sem_checagem "
            "WHERE fonte_codigo = 'stj-espelhos'"
        )
        row = cursor.fetchone()

    assert row is not None
    assert row["total"] > 0, "the fixture has no STJ record, so this proves nothing"
    assert row["sem_verdito"] == row["total"]
