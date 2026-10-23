from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app.db import get_connection
from app.main import app
from tests.conftest import FIXTURES, needs_database
from tests.test_seal_filter import transformation


@pytest.fixture
def client(db_rolled_back: psycopg.Connection[DictRow]) -> Iterator[TestClient]:
    app.dependency_overrides[get_connection] = lambda: db_rolled_back
    yield TestClient(app)
    app.dependency_overrides.clear()


def filter_options(client: TestClient) -> dict[str, Any]:
    response = client.get("/filters")
    assert response.status_code == 200, response.text
    return response.json()


def add_decision(
    db: psycopg.Connection[DictRow],
    identifier: str,
    judging_body: str | None,
    reporting_judge: str | None,
) -> None:
    ementa = f"CIVIL. Dano moral. Decisão {identifier}."
    db.execute(
        """
        INSERT INTO core.decisao (
            fonte_codigo, identificador_fonte, tribunal_sigla,
            orgao_julgador, relator, data_referencia, ementa,
            turma_recursal, possui_inteiro_teor, url_fonte, ementa_busca
        ) VALUES (
            'filters-test', %s, 'STJ', %s, %s, '2026-03-10', %s,
            FALSE, FALSE, 'https://example.com/' || %s,
            TO_TSVECTOR('portugues_sem_acento', %s)
        )
        """,
        (identifier, judging_body, reporting_judge, ementa, identifier, ementa),
    )


@needs_database
def test_lists_distinct_values_from_the_whole_collection(client: TestClient) -> None:
    body = filter_options(client)

    assert set(body) == {"judging_bodies", "reporting_judges", "procedural_classes"}
    assert body["procedural_classes"] == [{"value": 198, "label": "Apelação Cível"}]
    assert body["judging_bodies"] == [
        {"value": "1ª TURMA CÍVEL", "label": "1ª TURMA CÍVEL"},
        {"value": "2ª TURMA RECURSAL", "label": "2ª TURMA RECURSAL"},
        {"value": "3ª TURMA CÍVEL", "label": "3ª TURMA CÍVEL"},
        {"value": "4ª TURMA CÍVEL", "label": "4ª TURMA CÍVEL"},
        {"value": "CÂMARA CRIMINAL", "label": "CÂMARA CRIMINAL"},
    ]
    assert body["reporting_judges"] == [
        {"value": "ALFEU MACHADO", "label": "ALFEU MACHADO"},
        {"value": "ANA CANTARINO", "label": "ANA CANTARINO"},
        {
            "value": "DEMETRIUS GOMES CAVALCANTI",
            "label": "DEMETRIUS GOMES CAVALCANTI",
        },
        {"value": "JOÃO EGMONT", "label": "JOÃO EGMONT"},
        {"value": "MARIA IVATÔNIA", "label": "MARIA IVATÔNIA"},
    ]
    assert filter_options(client) == body


@needs_database
def test_duplicates_are_removed_but_distinct_text_values_are_preserved(
    client: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    add_decision(db_rolled_back, "9000001", "ÓRGÃO NOVO", "RELATOR NOVO")
    add_decision(db_rolled_back, "9000002", "ÓRGÃO NOVO", "RELATOR NOVO")
    add_decision(db_rolled_back, "9000003", " ÓRGÃO NOVO ", " RELATOR NOVO ")
    add_decision(db_rolled_back, "9000004", "   ", "   ")
    add_decision(db_rolled_back, "9000005", "", "")
    add_decision(db_rolled_back, "9000006", None, None)

    body = filter_options(client)
    organs = [option["value"] for option in body["judging_bodies"]]
    judges = [option["value"] for option in body["reporting_judges"]]

    assert organs.count("ÓRGÃO NOVO") == 1
    assert organs.count(" ÓRGÃO NOVO ") == 1
    assert judges.count("RELATOR NOVO") == 1
    assert judges.count(" RELATOR NOVO ") == 1
    assert "   " not in organs
    assert "   " not in judges
    assert "" not in organs
    assert "" not in judges
    assert all(value.strip() for value in organs + judges)
    assert [option["label"] for option in body["judging_bodies"]] == organs
    assert [option["label"] for option in body["reporting_judges"]] == judges


@needs_database
def test_a_collection_without_decisions_returns_empty_lists(
    client: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    db_rolled_back.execute("DELETE FROM core.decisao")

    assert filter_options(client) == {
        "judging_bodies": [],
        "reporting_judges": [],
        "procedural_classes": [],
    }


@needs_database
def test_classes_require_decisions_and_keep_codes_with_the_same_name(
    client: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    db_rolled_back.execute("UPDATE core.decisao SET classe_cnj = NULL")
    # Both catalogue entries share a name; their CNJ codes are different options.
    for identifier, code in (
        ("9000010", 1669),
        ("9000011", 47),
        ("9000012", 47),
        ("9000013", 213),
        ("9000014", 1321),
    ):
        add_decision(db_rolled_back, identifier, "CORTE ESPECIAL", "RELATOR STJ")
        db_rolled_back.execute(
            "UPDATE core.decisao SET classe_cnj = %s WHERE identificador_fonte = %s",
            (code, identifier),
        )

    body = filter_options(client)
    assert body["procedural_classes"] == [
        {"value": 1321, "label": "Agravo Regimental"},
        {"value": 47, "label": "Ação Rescisória"},
        {"value": 1669, "label": "Ação Rescisória"},
        {"value": 213, "label": "Recurso Especial"},
    ]
    assert filter_options(client) == body

    for option in body["procedural_classes"]:
        assert db_rolled_back.execute(
            "SELECT 1 FROM core.decisao WHERE classe_cnj = %s LIMIT 1",
            (option["value"],),
        ).fetchone()


@needs_database
def test_classes_are_empty_when_no_decision_has_a_class(
    client: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    db_rolled_back.execute("UPDATE core.decisao SET classe_cnj = NULL")
    body = filter_options(client)
    assert body["procedural_classes"] == []
    assert body["judging_bodies"]
    assert body["reporting_judges"]


@needs_database
def test_sealed_decisions_do_not_add_filter_options(
    client: TestClient,
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    db_rolled_back.execute((FIXTURES / "raw.sql").read_text(encoding="utf-8"))
    db_rolled_back.execute(
        "UPDATE raw.acordao_tjdft "
        'SET "descricaoOrgaoJulgador" = %s, "nomeRelator" = %s '
        "WHERE identificador = %s",
        ("ORGÃO SIGILOSO", "RELATOR SIGILOSO", "9000004"),
    )
    db_rolled_back.execute("DELETE FROM core.decisao")
    columns = (
        "fonte_codigo, identificador_fonte, tribunal_sigla, orgao_julgador, "
        "relator, data_referencia, ementa, turma_recursal, possui_inteiro_teor, "
        "url_fonte, link_valido, ementa_busca"
    )
    db_rolled_back.execute(
        f"INSERT INTO core.decisao ({columns}) "
        f"SELECT {columns} FROM ({transformation()}) AS publicado"
    )

    body = filter_options(client)
    organs = [option["value"] for option in body["judging_bodies"]]
    judges = [option["value"] for option in body["reporting_judges"]]

    assert "ORGÃO SIGILOSO" not in organs
    assert "RELATOR SIGILOSO" not in judges


def test_endpoint_and_response_schema_are_in_openapi() -> None:
    client = TestClient(app)
    spec = client.get("/openapi.json").json()
    operation = spec["paths"]["/filters"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    schemas = spec["components"]["schemas"]

    assert response_schema["$ref"].endswith("/FilterOptions")
    assert set(schemas["FilterOptions"]["properties"]) == {
        "judging_bodies",
        "reporting_judges",
        "procedural_classes",
    }
    assert set(schemas["FilterOption"]["properties"]) == {"value", "label"}
    class_properties = schemas["ProceduralClassOption"]["properties"]
    assert class_properties["value"]["type"] == "integer"
    assert class_properties["label"]["type"] == "string"
    assert "503" in operation["responses"]

    for path in (
        "/decisions",
        "/indicators/volume-by-court",
        "/indicators/outcome-share",
    ):
        operation = spec["paths"][path]["get"]
        parameters = {
            parameter["name"]: parameter for parameter in operation["parameters"]
        }
        assert {"orgao_julgador", "relator"} <= set(parameters)
        alternatives = parameters["classe_cnj"]["schema"]["anyOf"]
        array = next(item for item in alternatives if item.get("type") == "array")
        assert array["items"]["type"] == "integer"

        for name in ("orgao_julgador", "relator"):
            alternatives = parameters[name]["schema"]["anyOf"]
            array = next(item for item in alternatives if item.get("type") == "array")
            assert array["items"]["type"] == "string"
