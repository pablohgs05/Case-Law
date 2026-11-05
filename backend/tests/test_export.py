"""Export collection agrees with the search without inheriting its page size."""

import re
from collections.abc import Iterator
from datetime import date
from io import BytesIO
from time import perf_counter
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import IsolationLevel
from psycopg.rows import DictRow
from pypdf import PdfReader

from app.export import ExportRefused, collect_export
from tests.conftest import TEST_DATABASE_URL, needs_database

pytestmark = needs_database


@pytest.mark.parametrize("order", ["relevance", "date"])
def test_downloaded_pdf_matches_actual_search_records_order_and_audited_links(
    client: TestClient, collection: psycopg.Connection[DictRow], order: str
) -> None:
    # URLs deliberately cannot be derived from the public decision identifier.
    collection.execute(
        """UPDATE core.decisao SET url_fonte =
        'https://oficial.test/acervo/' || md5(fonte_codigo || identificador_fonte)
        || '?versao=original&formato=inteiro'"""
    )
    collection.execute(
        "UPDATE core.decisao SET relator = NULL, resultado = NULL "
        "WHERE identificador_fonte = '2'"
    )
    params: dict[str, Any] = {
        "q": "dano moral",
        "tribunal": ["STJ"],
        "classe_cnj": [198],
        "date_from": "2024-01-01",
        "date_to": "2024-01-03",
        "order": order,
    }
    expected = []
    for page in range(1, 5):
        response = client.get("/decisions", params={**params, "page": page})
        assert response.status_code == 200
        expected.extend(response.json()["results"])
    assert len(expected) == response.json()["total"] == 19
    urls = {
        (row["fonte_codigo"], row["identificador_fonte"]): row["url_fonte"]
        for row in collection.execute(
            "SELECT fonte_codigo, identificador_fonte, url_fonte FROM core.decisao"
        ).fetchall()
    }
    downloaded = client.post("/exports/pdf", json=params)
    assert downloaded.status_code == 200, (
        downloaded.text[:300] if downloaded.status_code != 200 else ""
    )
    pdf = PdfReader(BytesIO(downloaded.content))
    text = "\n".join(page.extract_text() for page in pdf.pages)
    # Read references in the real PDF, rather than trusting its printed total.
    actual = re.findall(r"Fonte:\s*(\S+)\s+Identificação da decisão:\s*(\S+)", text)
    identities = [(row["source"], row["identifier"]) for row in expected]
    assert actual == identities
    assert re.search(r"Relator:\s*Não informado", text)
    assert re.search(r"Resultado:\s*Não informado", text)
    links = [
        annotation.get_object()["/A"]["/URI"]
        for page in pdf.pages
        for annotation in page.get("/Annots", [])
        if annotation.get_object().get("/A", {}).get("/URI")
    ]
    assert links == [urls[identity] for identity in identities]


def test_actual_empty_export_never_renders_a_document(
    client: TestClient,
    collection: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import exports

    def forbidden(*args: Any, **kwargs: Any) -> bytes:
        pytest.fail("An empty cut must never reach the PDF renderer")

    monkeypatch.setattr(exports, "render_export_pdf", forbidden)
    response = client.post("/exports/pdf", json={"q": "inexistente"})
    assert response.status_code == 409
    assert response.json()["code"] == "empty"
    assert "content-disposition" not in response.headers


@pytest.fixture
def collection(
    db_rolled_back: psycopg.Connection[DictRow],
) -> Iterator[psycopg.Connection[DictRow]]:
    db_rolled_back.isolation_level = IsolationLevel.REPEATABLE_READ
    db_rolled_back.execute("DELETE FROM core.decisao")
    db_rolled_back.execute(
        """INSERT INTO core.decisao (
            fonte_codigo, identificador_fonte, tribunal_sigla, processo,
            data_referencia, data_julgamento, data_publicacao, ementa,
            orgao_julgador, relator, classe_cnj, resultado,
            turma_recursal, possui_inteiro_teor, url_fonte, link_valido, ementa_busca
        ) SELECT 'export-test', n::text, 'STJ', 'processo-' || n,
            '2024-01-01'::date + n % 3, '2024-01-01'::date + n % 3,
            '2024-02-01'::date, text, 'TURMA A', 'RELATOR A', 198, 'provido',
            FALSE, FALSE, 'https://example.test/' || n, TRUE,
            to_tsvector('portugues_sem_acento', text)
        FROM generate_series(1, 18) n
        CROSS JOIN LATERAL (
            SELECT CASE WHEN n % 2 = 0 THEN 'Dano moral. Dano moral.'
                        ELSE 'Dano moral. Outros fundamentos e explicações.' END AS text
        ) e"""
    )
    # The same identifier in another source is a different decision.
    db_rolled_back.execute(
        """INSERT INTO core.decisao (
            fonte_codigo, identificador_fonte, tribunal_sigla, processo,
            orgao_julgador, relator, classe_cnj, data_julgamento, data_publicacao,
            data_referencia, ementa, tipo_texto, decisao_texto, resultado,
            deliberacao, turma_recursal, possui_inteiro_teor, url_fonte,
            link_valido, ementa_busca
        )
        SELECT 'export-other', identificador_fonte, tribunal_sigla, processo,
            orgao_julgador, relator, classe_cnj, data_julgamento, data_publicacao,
            data_referencia, ementa, tipo_texto, decisao_texto, resultado,
            deliberacao, turma_recursal, possui_inteiro_teor, url_fonte,
            link_valido, ementa_busca
        FROM core.decisao WHERE identificador_fonte = '1'"""
    )
    yield db_rolled_back


@pytest.mark.parametrize("order", ["relevance", "date"])
def test_collects_every_page_in_the_same_stable_order_as_the_search(
    client: TestClient, collection: psycopg.Connection[DictRow], order: Any
) -> None:
    expected = []
    for page in range(1, 5):
        response = client.get(
            "/decisions", params={"q": "dano moral", "order": order, "page": page}
        )
        assert response.status_code == 200
        expected.extend(response.json()["results"])
    exported = collect_export(collection, "dano moral", order=order)
    assert exported.total == len(exported.decisions) == len(expected) == 19
    assert exported.order == order
    assert exported.query == "dano moral"
    assert all("Dano" in row["snippet"] for row in exported.decisions)
    assert [
        (r["fonte_codigo"], r["identificador_fonte"]) for r in exported.decisions
    ] == [(r["source"], r["identifier"]) for r in expected]
    assert (
        len({(r["fonte_codigo"], r["identificador_fonte"]) for r in exported.decisions})
        == 19
    )


def test_collection_supports_search_snippets_with_a_highlight_parameter(
    collection: psycopg.Connection[DictRow], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import export

    monkeypatch.setattr(
        export,
        "SNIPPET",
        f"CASE WHEN %(highlight)s = %(term)s THEN {export.SNIPPET} ELSE ementa END",
    )
    result = collect_export(collection, "dano moral")
    assert len(result.decisions) == result.total == 19
    assert all("<mark>" in row["snippet"] for row in result.decisions)


@pytest.mark.parametrize(
    ("column", "wrong"),
    [
        ("tribunal_sigla", "TJDFT"),
        ("orgao_julgador", "OUTRA TURMA"),
        ("relator", "OUTRO RELATOR"),
        ("classe_cnj", 213),
        ("resultado", "negado"),
        ("data_referencia", date(2024, 1, 4)),
        ("data_publicacao", date(2024, 2, 2)),
    ],
)
def test_composes_all_search_filters_before_collecting(
    client: TestClient,
    collection: psycopg.Connection[DictRow],
    column: str,
    wrong: Any,
) -> None:
    from psycopg import sql

    collection.execute(
        sql.SQL(
            "UPDATE core.decisao SET {} = %s WHERE identificador_fonte = '1'"
        ).format(sql.Identifier(column)),
        (wrong,),
    )
    params: dict[str, Any] = {
        "q": "dano moral",
        "tribunal": ["STJ", "STJ"],
        "orgao_julgador": ["TURMA A"],
        "relator": ["RELATOR A"],
        "classe_cnj": [198],
        "resultado": ["provido", "provido"],
        "date_from": date(2024, 1, 1),
        "date_to": date(2024, 1, 3),
        "published_from": date(2024, 2, 1),
        "published_to": date(2024, 2, 1),
        "order": "date",
    }
    response = client.get("/decisions", params={**params, "page_size": 100})
    assert response.status_code == 200
    result = collect_export(collection, **params)
    assert result.total == len(result.decisions) == response.json()["total"] == 17
    assert all(row["identificador_fonte"] != "1" for row in result.decisions)
    assert result.query == params["q"]
    assert result.filters == {
        "tribunais": ["STJ"],
        "orgao_julgador": ["TURMA A"],
        "relator": ["RELATOR A"],
        "classe_cnj": [198],
        "resultado": ["provido"],
        "date_from": date(2024, 1, 1),
        "date_to": date(2024, 1, 3),
        "published_from": date(2024, 2, 1),
        "published_to": date(2024, 2, 1),
    }
    for path, indicator in (
        ("volume-by-court", result.indicators.courts),
        ("volume-by-period", result.indicators.timeline),
        ("outcome-share", result.indicators.outcomes),
    ):
        response = client.get(f"/indicators/{path}", params=params)
        assert response.status_code == 200
        assert indicator.model_dump(mode="json") == response.json()
    # Coverage is labelled as context from the whole represented court, not
    # passed off as the denominator of the filtered indicator.
    assert result.indicators.coverage[0].documents == (
        17 if column == "tribunal_sigla" else 19
    )


def test_export_preserves_empty_periods_and_actual_classification_coverage(
    collection: psycopg.Connection[DictRow],
) -> None:
    collection.execute(
        "UPDATE core.decisao SET data_referencia = '2024-03-01', classe_cnj = NULL "
        "WHERE identificador_fonte = '2'"
    )
    collection.execute(
        "UPDATE core.decisao SET resultado = NULL WHERE identificador_fonte = '1'"
    )
    result = collect_export(collection, "dano moral")
    indicators = result.indicators
    assert (
        indicators.courts.total
        == indicators.timeline.total
        == indicators.outcomes.total
        == 19
    )
    assert [(p.period, p.decisions) for p in indicators.timeline.periods] == [
        (date(2024, 1, 1), 18),
        (date(2024, 2, 1), 0),
        (date(2024, 3, 1), 1),
    ]
    assert indicators.outcomes.classified == 17
    assert indicators.outcomes.unclassified == 2
    assert indicators.with_class == indicators.coverage[0].with_class == 18
    assert indicators.with_knowledge is None


def test_knowledge_coverage_is_measured_when_the_publication_has_the_column(
    collection: psycopg.Connection[DictRow],
) -> None:
    collection.execute("ALTER TABLE core.decisao ADD COLUMN conhecimento TEXT")
    collection.execute(
        "UPDATE core.decisao SET conhecimento = 'conhecido' WHERE identificador_fonte = '1'"
    )
    collection.execute(
        "UPDATE core.decisao SET conhecimento = '   ' WHERE identificador_fonte = '2'"
    )
    result = collect_export(collection, "dano moral")
    assert result.indicators.with_knowledge == 2
    filtered = collect_export(collection, "dano moral", date_from=date(2024, 1, 3))
    assert filtered.total == 6
    assert filtered.indicators.with_knowledge == 0


def test_methodology_stemming_example_matches_the_actual_search_configuration(
    db: psycopg.Connection[DictRow],
) -> None:
    result = db.execute(
        """SELECT to_tsquery('portugues_sem_acento', 'moral')::text AS singular,
            to_tsquery('portugues_sem_acento', 'morais')::text AS plural"""
    ).fetchone()
    assert result is not None
    assert result["singular"] != result["plural"]


def test_methodology_does_not_hide_a_court_with_no_results_in_the_cut(
    collection: psycopg.Connection[DictRow],
) -> None:
    collection.execute(
        """INSERT INTO core.decisao (
            fonte_codigo, identificador_fonte, tribunal_sigla, data_referencia,
            ementa, turma_recursal, possui_inteiro_teor, url_fonte, ementa_busca
        ) VALUES ('coverage-only', 'outside-cut', 'TJDFT', '2025-09-17',
            'Assunto criminal', FALSE, FALSE, 'https://example.test/outside-cut',
            to_tsvector('portugues_sem_acento', 'Assunto criminal'))"""
    )
    data = collect_export(collection, "dano moral")
    assert data.total == 19
    assert [c.abbreviation for c in data.indicators.courts.courts] == ["STJ"]
    assert [c.court for c in data.indicators.coverage] == ["STJ", "TJDFT"]
    assert data.indicators.coverage[1].first == date(2025, 9, 17)
    restricted = collect_export(collection, "dano moral", tribunal=["STJ"])
    assert [c.court for c in restricted.indicators.coverage] == ["STJ"]


def recorded_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    queries: list[str] = []
    original = psycopg.Connection.execute

    def execute(self: Any, query: Any, params: Any = None, **kwargs: Any) -> Any:
        queries.append(str(query))
        return original(self, query, params, **kwargs)

    monkeypatch.setattr(psycopg.Connection, "execute", execute)
    return queries


def test_empty_cut_refuses_before_reading_or_sorting_references(
    collection: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queries = recorded_queries(monkeypatch)
    with pytest.raises(ExportRefused) as failure:
        collect_export(collection, "inexistente")
    assert failure.value.code == "empty"
    assert failure.value.total == 0
    assert any("COUNT(*)" in query for query in queries)
    assert not any("ORDER BY" in query or "ts_rank" in query for query in queries)


def test_retains_reference_metadata(
    collection: psycopg.Connection[DictRow],
) -> None:
    collection.execute(
        "UPDATE core.decisao SET relator = NULL, link_valido = FALSE "
        "WHERE identificador_fonte = '1'"
    )
    result = collect_export(collection, "dano moral")
    assert result.total == len(result.decisions) == 19
    missing = [row for row in result.decisions if row["identificador_fonte"] == "1"]
    assert len(missing) == 2
    assert all(
        row["relator"] is None and row["link_valido"] is False for row in missing
    )


@pytest.mark.parametrize("size", [1000, 1001])
def test_large_exports_include_every_reference_without_a_record_limit(
    collection: psycopg.Connection[DictRow],
    size: int,
) -> None:
    collection.execute(
        """INSERT INTO core.decisao (
            fonte_codigo, identificador_fonte, tribunal_sigla, data_referencia,
            ementa, turma_recursal, possui_inteiro_teor, url_fonte, ementa_busca
        ) SELECT 'export-large', n::text, 'STJ', '2024-01-01', 'Amostra exportável',
            FALSE, FALSE, 'https://example.test/' || n,
            to_tsvector('portugues_sem_acento', 'Amostra exportável')
        FROM generate_series(1, %s) n""",
        (size,),
    )
    result = collect_export(collection, "amostra exportável")
    assert result.total == len(result.decisions) == size
    assert {row["identificador_fonte"] for row in result.decisions} == {
        str(n) for n in range(1, size + 1)
    }
    from app.export_document import render_export_pdf

    started = perf_counter()
    document = render_export_pdf(result)
    elapsed = perf_counter() - started
    pdf = PdfReader(BytesIO(document))
    text = "\n".join(page.extract_text() for page in pdf.pages)
    entries = re.findall(r"Fonte:\s*(\S+)\s+Identificação da decisão:\s*(\S+)", text)
    assert entries == [
        (row["fonte_codigo"], row["identificador_fonte"]) for row in result.decisions
    ]
    # Measure the complete current template; do not impose the spike's timing
    # on CI machines with different resources or silently count only collection.
    print(f"{size} decisions: PDF generation {elapsed:.3f}s, {len(pdf.pages)} pages")


def test_idle_connection_owns_a_read_only_snapshot(
    db: psycopg.Connection[DictRow],
) -> None:
    result = collect_export(db, "dano moral")
    assert result.total == len(result.decisions) > 0
    assert db.info.transaction_status == psycopg.pq.TransactionStatus.IDLE


def test_active_read_committed_transaction_cannot_mix_two_snapshots(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    db_rolled_back.execute("SELECT 1")
    with pytest.raises(ValueError, match="repeatable snapshot"):
        collect_export(db_rolled_back, "dano moral")


def test_concurrent_publication_cannot_change_the_counted_set(
    db: psycopg.Connection[DictRow],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = psycopg.Connection.execute
    inserted = False
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as writer:

        def execute(self: Any, query: Any, params: Any = None, **kwargs: Any) -> Any:
            nonlocal inserted
            cursor = original(self, query, params, **kwargs)
            if self is db and "SELECT COUNT(*)" in str(query):
                writer.execute(
                    """INSERT INTO core.decisao (
                        fonte_codigo, identificador_fonte, tribunal_sigla,
                        data_referencia, ementa, turma_recursal,
                        possui_inteiro_teor, url_fonte, ementa_busca
                    ) VALUES ('export-concurrent', 'after-count', 'TJDFT',
                        '2024-01-01', 'Dano moral', FALSE, FALSE,
                        'https://example.test/after-count',
                        to_tsvector('portugues_sem_acento', 'Dano moral'))"""
                )
                inserted = True
            return cursor

        monkeypatch.setattr(psycopg.Connection, "execute", execute)
        try:
            result = collect_export(db, "dano moral")
            assert inserted, "the publication must commit between count and read"
            assert result.total == len(result.decisions)
            assert all(
                row["fonte_codigo"] != "export-concurrent" for row in result.decisions
            )
        finally:
            writer.execute(
                "DELETE FROM core.decisao WHERE fonte_codigo = 'export-concurrent'"
            )
