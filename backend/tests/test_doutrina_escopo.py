"""
The two promises made to the client, made executable.

Nothing from a restricted collection reaches the base, and no work's text is
ever stored or served. Both are the kind of rule that nobody breaks on
purpose: they break when someone widens the collection without thinking, and
by then the data is already loaded. These fail loudly at that moment.

The scope rule itself is the STJ's, not ours — the library keeps Acesso Aberto
and Acesso Restrito in separate collections, and only the first is read.
"""

from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow
from psycopg.types.json import Json

from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = needs_database

TRANSFORMATIONS = Path(__file__).resolve().parents[2] / "pipeline" / "transformations"
MODEL = TRANSFORMATIONS / "models" / "core_doutrina.sql"
AUDITS = TRANSFORMATIONS / "audits" / "regras.sql"

ABERTO = "col_2011_8"
RESTRITO = "col_2011_9"

# Three paragraphs of an article, which is what must never be here. Short
# enough for a fixture, long enough that no abstract could be mistaken for it.
TEXTO_INTEGRAL = (
    "A responsabilidade civil por dano ambiental, no direito brasileiro, é "
    "objetiva e solidária, conforme o artigo 14, parágrafo 1º, da Lei n. "
    "6.938/1981. " * 40
)


def scope_sql() -> str:
    """The model's own filter, read off disk rather than restated here."""
    text = MODEL.read_text(encoding="utf-8")
    body = text.split("*/", 1)[1].split("JINJA_STATEMENT_BEGIN", 1)[0]
    return body.strip().rstrip(";").strip()


def audit_sql(name: str) -> str:
    """
    One audit's body, read off disk. An audit is a query that must return no
    row; restating it in the test would pass even if someone deleted it from
    the pipeline, which is exactly the day it has to fail.
    """
    blocks = AUDITS.read_text(encoding="utf-8").split("AUDIT (")
    for block in blocks:
        if block.lstrip().startswith(f"name {name},"):
            return block.split(");", 1)[1].strip().rstrip(";")
    raise AssertionError(f"a auditoria {name} sumiu de regras.sql")


def raw(
    db: psycopg.Connection[DictRow],
    identifier: str,
    sets: list[str],
    rights: str | None = None,
    summary: str | None = None,
) -> None:
    """A record as the extractor leaves it in the raw layer, before the model."""
    db.execute(
        "INSERT INTO raw.doutrina_bdjur ("
        "  repositorio, identificador_oai, titulo, titulos, autores, assuntos,"
        "  tipo, data, ano, idioma, publicacao, resumo, referencia, url_fonte,"
        "  direitos, conjuntos, arquivada_em, alterada_em"
        ") VALUES ("
        "  'bdjur', %(id)s, 'Dano ambiental e responsabilidade civil',"
        "  '[]'::JSONB, '[\"Silva, A.\"]'::JSONB, '[\"Dano ambiental\"]'::JSONB,"
        "  'Artigo', '2015', 2015, 'pt-BR', 'Revista', %(resumo)s,"
        "  'Revista, v. 1, 2015.',"
        "  'https://bdjur.stj.jus.br/handle/' || SPLIT_PART(%(id)s, ':', 3),"
        "  %(direitos)s, %(conjuntos)s::JSONB, NOW(), NOW()"
        ")",
        {
            "id": identifier,
            "conjuntos": Json(sets),
            "direitos": rights,
            "resumo": summary,
        },
    )


def collected(db: psycopg.Connection[DictRow]) -> list[DictRow]:
    with db.cursor() as cursor:
        cursor.execute(scope_sql())
        return cursor.fetchall()


@pytest.fixture
def layers(db_rolled_back: psycopg.Connection[DictRow]) -> Any:
    db_rolled_back.execute(
        "CREATE SCHEMA IF NOT EXISTS raw;"
        "CREATE TABLE IF NOT EXISTS raw.doutrina_bdjur ("
        "  repositorio TEXT, identificador_oai TEXT, titulo TEXT, titulos JSONB,"
        "  autores JSONB, assuntos JSONB, tipo TEXT, data TEXT, ano BIGINT,"
        "  idioma TEXT, publicacao TEXT, resumo TEXT, referencia TEXT,"
        "  url_fonte TEXT, direitos TEXT, conjuntos JSONB,"
        "  arquivada_em TIMESTAMPTZ, alterada_em TIMESTAMPTZ)"
    )
    db_rolled_back.execute("DELETE FROM raw.doutrina_bdjur")
    return db_rolled_back


def test_nenhum_registro_de_acesso_restrito_entra(
    layers: psycopg.Connection[DictRow],
) -> None:
    """
    O compromisso com o cliente, executável. Alimentando a camada bruta com
    registros do conjunto de Acesso Restrito, nada daquele conjunto é gravado
    — e isto falha de forma barulhenta no dia em que alguém ampliar a lista de
    conjuntos sem pensar.
    """
    raw(layers, "oai:bdjur.stj.jus.br:2011/1", [ABERTO])
    raw(layers, "oai:bdjur.stj.jus.br:2011/2", [RESTRITO])
    raw(layers, "oai:bdjur.stj.jus.br:2011/3", ["com_2011_2", RESTRITO])

    gravados = {linha["identificador_oai"] for linha in collected(layers)}

    assert gravados == {"oai:bdjur.stj.jus.br:2011/1"}


def test_direitos_restritos_vencem_a_colecao(
    layers: psycopg.Connection[DictRow],
) -> None:
    """
    Onde os dois discordam, o campo manda. Uma obra arquivada em Acesso Aberto
    declara "Restricted access" no próprio `dc:rights` — 1 em 798 na amostra —
    e não entra. A regra é lista de permissão: direitos desconhecido exclui.
    """
    raw(layers, "oai:bdjur.stj.jus.br:2011/4", [ABERTO], rights="Acesso aberto")
    raw(layers, "oai:bdjur.stj.jus.br:2011/5", [ABERTO], rights="Restricted access")
    raw(layers, "oai:bdjur.stj.jus.br:2011/6", [ABERTO], rights="Sob embargo até 2030")

    gravados = {linha["identificador_oai"] for linha in collected(layers)}

    assert gravados == {"oai:bdjur.stj.jus.br:2011/4"}


def test_registro_sem_resumo_entra_com_resumo_nulo(
    layers: psycopg.Connection[DictRow],
) -> None:
    """
    68% dos registros não têm `dc:description`. Descartá-los por isso jogaria
    fora dois terços do acervo.
    """
    raw(layers, "oai:bdjur.stj.jus.br:2011/7", [ABERTO], summary=None)

    linhas = collected(layers)

    assert len(linhas) == 1
    assert linhas[0]["resumo"] is None


def test_nenhum_texto_integral_e_armazenado(
    layers: psycopg.Connection[DictRow],
) -> None:
    """
    A segunda promessa. O teto de 5.000 caracteres não julga resumo comprido:
    o maior `dc:description` da amostra tem 1.255. Ele reprova o dia em que
    alguém apontar o extrator para o corpo da obra, e é a mesma auditoria que
    roda na carga.
    """
    raw(layers, "oai:bdjur.stj.jus.br:2011/8", [ABERTO], summary=TEXTO_INTEGRAL)

    linha = collected(layers)[0]

    assert len(TEXTO_INTEGRAL) > 5000, "o cenário precisa de um texto de obra"
    assert len(linha["resumo"] or "") > 5000, (
        "a camada bruta guarda o que a fonte mandou, sem interpretar"
    )
    # E a auditoria que roda na carga reprova exatamente esta linha. A consulta
    # vem do arquivo de auditorias, não daqui: apagá-la de lá quebra isto.
    regra = audit_sql("doutrina_sem_texto_integral").replace(
        "@this_model", "(" + scope_sql() + ") AS modelo"
    )
    with layers.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS reprovadas FROM ({regra}) AS auditoria")
        row = cursor.fetchone()

    assert row is not None and row["reprovadas"] == 1


def test_a_api_nunca_serve_texto_de_obra(
    db_rolled_back: psycopg.Connection[DictRow],
) -> None:
    """
    A mesma promessa na outra ponta. O resumo está gravado na linha e não pode
    sair por nenhum dos dois caminhos da API.
    """
    from app.db import get_connection
    from app.main import app

    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    decide(db_rolled_back, "STJ", "uma")
    db_rolled_back.execute(
        "INSERT INTO core.doutrina ("
        "  repositorio, identificador_oai, titulo, resumo, url_fonte, busca"
        ") VALUES ('bdjur', 'oai:x:1', 'Dano ambiental', %s,"
        "  'https://bdjur.stj.jus.br/handle/2011/1',"
        "  TO_TSVECTOR('portugues_sem_acento', 'Dano ambiental'))",
        (TEXTO_INTEGRAL,),
    )
    db_rolled_back.execute(
        "INSERT INTO core.decisao_doutrina ("
        "  fonte_codigo, identificador_fonte, repositorio, identificador_oai,"
        "  nota, termos, termo_mais_forte, casou_em, distancia"
        ") VALUES ('stj-teste', 'uma', 'bdjur', 'oai:x:1', 12.0, 2, 5.0,"
        "  ARRAY['dano', 'ambiental'], 1)"
    )

    app.dependency_overrides[get_connection] = lambda: db_rolled_back
    client = TestClient(app)
    try:
        respostas = [
            client.get("/decisions/stj-teste/uma/doctrine"),
            client.get("/doctrine", params={"q": "ambiental"}),
        ]
    finally:
        app.dependency_overrides.clear()

    for resposta in respostas:
        assert resposta.status_code == 200, resposta.text
        assert "responsabilidade civil por dano ambiental" not in resposta.text.lower()
        assert len(resposta.text) < 2000, "resposta grande demais para só metadado"
