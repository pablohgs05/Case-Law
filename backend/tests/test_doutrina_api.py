"""
The two doctrine endpoints, against PostgreSQL.

What these protect is the promise the collection is allowed to make. The
matching finds nothing for four decisions in five, so "nothing" has to be a
normal answer rather than a failure — and the work itself has to stay at the
source, because open to read is not open to redistribute.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from tests.conftest import needs_database
from tests.test_courts import decide, register

pytestmark = needs_database

WORK = "oai:bdjur.stj.jus.br:2011/98958"
OTHER = "oai:bdjur.stj.jus.br:2011/32426"


def shelve(
    db: psycopg.Connection[DictRow],
    identifier: str = WORK,
    title: str = "A avaliação do regime jurídico da litigância de má-fé",
    subjects: list[str] | None = None,
    year: int | None = 2014,
    summary: str | None = "Resumo que não pode sair pela API.",
) -> None:
    db.execute(
        "INSERT INTO core.doutrina ("
        "  repositorio, identificador_oai, titulo, titulos_alternativos, autores,"
        "  assuntos, tipo, data, ano, idioma, publicacao, resumo, referencia,"
        "  url_fonte, busca"
        ") VALUES ("
        "  'bdjur', %(id)s, %(title)s, ARRAY[]::TEXT[], ARRAY['Gouveia, Mariana'],"
        "  %(subjects)s::TEXT[], 'Artigo', %(date)s, %(year)s, 'pt-br',"
        "  'Revista de Processo',"
        "  %(summary)s, 'Revista de Processo, v. 39, 2014.',"
        "  'https://bdjur.stj.jus.br/handle/' || SPLIT_PART(%(id)s, ':', 3),"
        "  SETWEIGHT(TO_TSVECTOR('portugues_sem_acento', %(title)s), 'A') ||"
        "  SETWEIGHT(TO_TSVECTOR('portugues_sem_acento',"
        "    ARRAY_TO_STRING(%(subjects)s::TEXT[], ' ')), 'A')"
        ")",
        {
            "id": identifier,
            "title": title,
            "subjects": subjects if subjects is not None else ["Litigância de má-fé"],
            "date": str(year) if year else None,
            "year": year,
            "summary": summary,
        },
    )


def suggest(
    db: psycopg.Connection[DictRow],
    identifier: str,
    work: str = WORK,
    score: float = 9.3,
    matched: list[str] | None = None,
) -> None:
    terms = matched if matched is not None else ["litiganc", "ma-f"]
    db.execute(
        "INSERT INTO core.decisao_doutrina ("
        "  fonte_codigo, identificador_fonte, repositorio, identificador_oai,"
        "  nota, termos, termo_mais_forte, casou_em, distancia"
        ") VALUES ('stj-teste', %s, 'bdjur', %s, %s, %s, 5.1, %s, 2)",
        (identifier, work, score, len(terms), terms),
    )


@pytest.fixture
def collection(db_rolled_back: psycopg.Connection[DictRow]) -> Any:
    from app.db import get_connection
    from app.main import app

    db_rolled_back.execute("DELETE FROM core.decisao")
    register(db_rolled_back, "STJ")
    decide(db_rolled_back, "STJ", "com-doutrina")
    decide(db_rolled_back, "STJ", "sem-doutrina")
    shelve(db_rolled_back)
    suggest(db_rolled_back, "com-doutrina")

    app.dependency_overrides[get_connection] = lambda: db_rolled_back
    yield TestClient(app)
    app.dependency_overrides.clear()


def related(client: TestClient, identifier: str, **params: Any) -> dict[str, Any]:
    response = client.get(f"/decisions/stj-teste/{identifier}/doctrine", params=params)
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_a_sugestao_traz_o_link_e_o_motivo(collection: TestClient) -> None:
    """
    O critério de aceite do card. Sem o link o leitor não alcança a obra, e sem
    o motivo não tem como julgar a sugestão sem abrir o artigo — que é
    exatamente o custo que a sugestão existe para poupar.
    """
    obra = related(collection, "com-doutrina")["results"][0]

    assert obra["url"] == "https://bdjur.stj.jus.br/handle/2011/98958"
    assert obra["matched_on"] == ["litiganc", "ma-f"]
    assert obra["title"].startswith("A avaliação do regime jurídico")


def test_decisao_sem_doutrina_devolve_lista_vazia(collection: TestClient) -> None:
    """
    Quatro decisões em cada cinco respondem assim. Se isso fosse erro, a tela
    mostraria falha no caso normal.
    """
    assert related(collection, "sem-doutrina") == {"results": []}


def test_decisao_inexistente_e_404(collection: TestClient) -> None:
    resposta = collection.get("/decisions/stj-teste/nao-existe/doctrine")

    assert resposta.status_code == 404


def test_identificador_com_byte_nulo_nao_quebra(collection: TestClient) -> None:
    """Um %00 na URL chega como texto que o PostgreSQL recusa."""
    resposta = collection.get("/decisions/stj-teste/a%00b/doctrine")

    assert resposta.status_code == 404


def test_nenhuma_resposta_carrega_o_texto_da_obra(collection: TestClient) -> None:
    """
    A regra de escopo, no lugar onde custaria caro esquecê-la: metadado e link,
    nunca a obra. O resumo está gravado na linha e não pode sair por nenhum dos
    dois caminhos.
    """
    sugestao = related(collection, "com-doutrina")["results"][0]
    busca = collection.get("/doctrine", params={"q": "litigância"}).json()

    for obra in (sugestao, *busca["results"]):
        assert "summary" not in obra
        assert "resumo" not in obra
        assert "não pode sair" not in str(obra)


def test_as_sugestoes_vem_da_mais_forte_para_a_mais_fraca(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    shelve(db_rolled_back, OTHER, title="Drogas: fora da lei e dentro do usuário")
    suggest(db_rolled_back, "com-doutrina", work=OTHER, score=20.0)

    notas = [o["score"] for o in related(collection, "com-doutrina")["results"]]

    assert notas == sorted(notas, reverse=True)
    assert notas[0] == 20.0


def test_o_limite_de_sugestoes_e_respeitado(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    shelve(db_rolled_back, OTHER, title="Drogas: fora da lei e dentro do usuário")
    suggest(db_rolled_back, "com-doutrina", work=OTHER, score=20.0)

    assert len(related(collection, "com-doutrina", limit=1)["results"]) == 1


def test_a_busca_acha_pelo_titulo_e_pelo_assunto(collection: TestClient) -> None:
    for termo in ("litigância", "má-fé"):
        resposta = collection.get("/doctrine", params={"q": termo})

        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["total"] == 1, termo


def test_a_busca_ignora_acento(collection: TestClient) -> None:
    """A mesma configuração `portugues_sem_acento` que a busca de decisões usa."""
    assert collection.get("/doctrine", params={"q": "litigancia"}).json()["total"] == 1


def test_a_busca_sem_resultado_nao_e_erro(collection: TestClient) -> None:
    resposta = collection.get("/doctrine", params={"q": "astrofisica"})

    assert resposta.status_code == 200
    assert resposta.json() == {
        "total": 0,
        "page": 1,
        "page_size": 20,
        "results": [],
    }


def test_a_pagina_alem_da_ultima_devolve_o_mesmo_total(
    collection: TestClient,
) -> None:
    resposta = collection.get(
        "/doctrine", params={"q": "litigância", "page": 99}
    ).json()

    assert resposta["total"] == 1
    assert resposta["results"] == []


def test_as_duas_consultas_fecham_no_desempate_pela_chave() -> None:
    """
    O critério de aceite sobre estabilidade, e a única forma honesta de
    afirmá-lo aqui: sem o desempate o PostgreSQL devolve empates na ordem que
    quiser, e uma obra aparece em duas páginas ou em nenhuma. Em seis linhas o
    planejador escolhe sempre o mesmo caminho, então o teste pela resposta
    passa com e sem a correção — foi verificado. O que falha de verdade quando
    alguém tira o desempate é esta afirmação sobre a consulta, como
    `test_ordering` já faz para as decisões.
    """
    from app.api.doctrine import RELATED_SQL, SEARCH_SQL, TIEBREAK

    assert TIEBREAK == "d.repositorio, d.identificador_oai"
    for consulta in (RELATED_SQL, SEARCH_SQL):
        ordenacao = consulta.split("ORDER BY")[1].split("LIMIT")[0]
        assert ordenacao.strip().endswith(TIEBREAK), consulta


def test_a_paginacao_nao_repete_nem_perde_obra(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    Que as páginas somadas dão a coleção inteira, sem repetir nem perder. Não
    prova o desempate — ver o teste acima —, prova a aritmética do offset.
    """
    for n in range(5):
        shelve(
            db_rolled_back,
            f"oai:bdjur.stj.jus.br:2011/{700 + n}",
            title="Litigância de má-fé no processo civil",
            subjects=["Litigância de má-fé"],
        )

    vistas: list[str] = []
    for pagina in (1, 2, 3):
        corpo = collection.get(
            "/doctrine", params={"q": "litigância", "page": pagina, "page_size": 2}
        ).json()
        assert corpo["total"] == 6
        vistas.extend(o["identifier"] for o in corpo["results"])

    assert len(vistas) == len(set(vistas)) == 6


def test_a_busca_nao_le_o_resumo(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    O resumo existe em 31,8% dos registros e costuma ser sumário ou nota de
    evento. Indexá-lo traria obra cujo texto nunca discute o termo.
    """
    shelve(
        db_rolled_back,
        OTHER,
        title="Drogas: fora da lei e dentro do usuário",
        subjects=["Tráfico de drogas"],
        summary="Palestra proferida na 6ª Reunião sobre usucapião.",
    )

    assert collection.get("/doctrine", params={"q": "usucapião"}).json()["total"] == 0


def test_a_obra_sem_assunto_nao_quebra_a_resposta(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    45% da coleção não tem assunto nenhum. Lista vazia, nunca nulo, porque a
    tela não deve precisar distinguir os dois.
    """
    shelve(db_rolled_back, OTHER, title="Obra sem assunto algum", subjects=[])

    obra = next(
        o
        for o in collection.get("/doctrine", params={"q": "assunto"}).json()["results"]
        if o["identifier"] == OTHER
    )

    assert obra["subjects"] == []
    assert obra["alternative_titles"] == []


def test_a_data_parcial_chega_como_a_biblioteca_escreveu(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    `1997/1998` é data de publicação real. Virar DATE inventa dia e mês que
    ninguém registrou, então a API devolve texto e o ano ao lado.
    """
    db_rolled_back.execute(
        "UPDATE core.doutrina SET data = '1997/1998', ano = 1997"
        " WHERE identificador_oai = %s",
        (WORK,),
    )

    obra = related(collection, "com-doutrina")["results"][0]

    assert obra["date"] == "1997/1998"
    assert obra["year"] == 1997


def test_o_detalhe_abre_sem_a_doutrina(
    collection: TestClient, db_rolled_back: psycopg.Connection[DictRow]
) -> None:
    """
    A regra de degradação, provada em vez de afirmada. A doutrina é
    enriquecimento e nunca pode estar no caminho crítico: com as tabelas fora
    do ar, o detalhe tem de abrir igual. Aqui elas somem de verdade, dentro da
    transação que o teste desfaz no fim.
    """
    db_rolled_back.execute("DROP TABLE core.decisao_doutrina, core.doutrina")

    detalhe = collection.get("/decisions/stj-teste/com-doutrina")
    doutrina = collection.get("/decisions/stj-teste/com-doutrina/doctrine")

    assert detalhe.status_code == 200, detalhe.text
    assert detalhe.json()["identifier"] == "com-doutrina"
    # E a doutrina diz que não está publicada, sem derrubar nada.
    assert doutrina.status_code == 503
