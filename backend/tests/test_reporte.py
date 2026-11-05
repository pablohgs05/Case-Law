"""
Reporting an incorrect classification (RF21).

Three promises, each tested because breaking it is silent. The report is
recorded against the decision and the information contested, with who sent it
and when. The reader is told it arrived. And the classification published does
not move: a report is a request for review, and a tool that let one reader's
report rewrite what every other reader sees would have no classification left
to trust.
"""

from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import DictRow

from app import accounts, sessions
from tests.conftest import needs_database

pytestmark = needs_database

SENHA = "Uma senha bem longa 1"
SOURCE, IDENTIFIER = "tjdft-jurisdf", "1000001"
ROUTE = f"/decisions/{SOURCE}/{IDENTIFIER}/reports"


@pytest.fixture
def db(db_rolled_back: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    db_rolled_back.execute("DELETE FROM qualidade.reporte")
    db_rolled_back.execute("DELETE FROM identidade.usuario")
    # A thesis and a cited precedent, so all four readings have something
    # published to contest. Inside the test's transaction, like everything else.
    db_rolled_back.execute(
        "UPDATE core.decisao SET tese = 'O dano moral decorre do próprio fato.' "
        "WHERE fonte_codigo = %s AND identificador_fonte = %s",
        (SOURCE, IDENTIFIER),
    )
    db_rolled_back.execute(
        "INSERT INTO core.decisao_precedente (fonte_codigo, identificador_fonte, "
        "corte, tipo, numero, trecho, resolvida, aderencia) "
        "VALUES (%s, %s, 'STJ', 'sumula', 385, 'súmula 385 do stj', TRUE, 'seguiu')",
        (SOURCE, IDENTIFIER),
    )
    return db_rolled_back


@pytest.fixture
def client(db: psycopg.Connection[DictRow]) -> Any:
    from app.db import get_connection
    from app.main import app
    from app.sessions import gate

    # Who reported is part of the record, so the door is real here: the prop
    # `conftest` puts under every other suite comes out.
    app.dependency_overrides.pop(gate, None)
    app.dependency_overrides[get_connection] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def manager(db: psycopg.Connection[DictRow]) -> dict[str, Any]:
    return accounts.create(
        db,
        nome="Ana Almeida Costa",
        email="ana@almeidacosta.com.br",
        senha=SENHA,
        papel="gerente",
    )


def analyst(db: psycopg.Connection[DictRow], boss: dict[str, Any]) -> dict[str, Any]:
    return accounts.create(
        db,
        nome="Bruno Dias",
        email="bruno@almeidacosta.com.br",
        senha=SENHA,
        papel="usuario",
        gerente=boss["id"],
    )


def header(person: dict[str, Any]) -> dict[str, str]:
    token, _ = sessions.issue(person)
    return {"Authorization": f"Bearer {token}"}


def published(db: psycopg.Connection[DictRow]) -> dict[str, Any]:
    """Everything the tool publishes about the decision, straight from `core`."""
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM core.decisao "
            "WHERE fonte_codigo = %s AND identificador_fonte = %s",
            (SOURCE, IDENTIFIER),
        )
        decision = cursor.fetchone()
        cursor.execute(
            "SELECT * FROM core.decisao_precedente "
            "WHERE fonte_codigo = %s AND identificador_fonte = %s "
            "ORDER BY tipo, numero",
            (SOURCE, IDENTIFIER),
        )
        precedents = cursor.fetchall()

    return {"decision": decision, "precedents": precedents}


def stored(db: psycopg.Connection[DictRow]) -> list[DictRow]:
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM qualidade.reporte ORDER BY criado_em")
        return cursor.fetchall()


class TestReportar:
    def test_grava_vinculado_a_decisao_a_informacao_e_a_quem_reportou(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        pessoa = analyst(db, manager(db))

        resposta = client.post(
            ROUTE,
            headers=header(pessoa),
            json={
                "information": "aderencia",
                "description": "  A súmula 385 foi afastada, não seguida.  ",
            },
        )

        assert resposta.status_code == 201
        [linha] = stored(db)
        assert linha["fonte_codigo"] == SOURCE
        assert linha["identificador_fonte"] == IDENTIFIER
        assert linha["informacao"] == "aderencia"
        assert linha["relato"] == "A súmula 385 foi afastada, não seguida."
        assert linha["usuario_id"] == pessoa["id"]
        assert linha["criado_em"] is not None
        assert linha["situacao"] == "pendente"

    def test_confirma_o_recebimento(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        pessoa = analyst(db, manager(db))

        corpo = client.post(
            ROUTE,
            headers=header(pessoa),
            json={"information": "deliberacao", "description": "Houve voto vencido."},
        ).json()

        assert corpo["message"].startswith("Recebemos o seu reporte")
        assert corpo["status"] == "pendente"
        assert corpo["id"] == str(stored(db)[0]["id"])
        assert corpo["source"] == SOURCE and corpo["identifier"] == IDENTIFIER

    @pytest.mark.parametrize(
        ("information", "expected"),
        [
            ("resultado", "negado"),
            ("deliberacao", "unanime"),
            ("tese", "O dano moral decorre do próprio fato."),
            ("aderencia", "STJ Súmula 385: seguiu"),
        ],
    )
    def test_guarda_o_que_estava_publicado_para_aquela_informacao(
        self,
        client: TestClient,
        db: psycopg.Connection[DictRow],
        information: str,
        expected: str,
    ) -> None:
        """
        A próxima publicação pode mudar a classificação, e um reporte que já
        não diz do que discordava não pode ser revisto.
        """
        pessoa = analyst(db, manager(db))

        corpo = client.post(
            ROUTE,
            headers=header(pessoa),
            json={"information": information, "description": "Está errado."},
        ).json()

        assert corpo["published_value"] == expected
        assert stored(db)[0]["valor_publicado"] == expected


class TestAClassificacaoPublicadaFicaIntacta:
    """O critério que esta história existe para cumprir."""

    @pytest.mark.parametrize(
        "information", ["resultado", "deliberacao", "aderencia", "tese"]
    )
    def test_o_core_continua_identico_depois_do_reporte(
        self,
        client: TestClient,
        db: psycopg.Connection[DictRow],
        information: str,
    ) -> None:
        pessoa = analyst(db, manager(db))
        antes = published(db)

        resposta = client.post(
            ROUTE,
            headers=header(pessoa),
            json={"information": information, "description": "Está errado."},
        )

        assert resposta.status_code == 201
        assert published(db) == antes

    def test_a_decisao_lida_pela_api_continua_a_mesma(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        pessoa = analyst(db, manager(db))
        cabecalho = header(pessoa)
        leitura = f"/decisions/{SOURCE}/{IDENTIFIER}"
        antes = client.get(leitura, headers=cabecalho).json()

        for information in ("resultado", "deliberacao", "aderencia", "tese"):
            client.post(
                ROUTE,
                headers=cabecalho,
                json={"information": information, "description": "Está errado."},
            )

        assert len(stored(db)) == 4
        assert client.get(leitura, headers=cabecalho).json() == antes

    def test_a_busca_filtrada_pelo_resultado_continua_a_mesma(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        pessoa = analyst(db, manager(db))
        cabecalho = header(pessoa)
        busca = "/decisions?q=dano&resultado=negado"
        antes = client.get(busca, headers=cabecalho).json()

        client.post(
            ROUTE,
            headers=cabecalho,
            json={"information": "resultado", "description": "Foi provido."},
        )

        assert client.get(busca, headers=cabecalho).json() == antes


class TestOQueORelatoRecusa:
    def test_sem_conta_nao_reporta(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        resposta = client.post(
            ROUTE, json={"information": "resultado", "description": "Errado."}
        )

        assert resposta.status_code == 401
        assert stored(db) == []

    def test_decisao_inexistente_e_404(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        pessoa = analyst(db, manager(db))

        resposta = client.post(
            f"/decisions/{SOURCE}/nao-existe/reports",
            headers=header(pessoa),
            json={"information": "resultado", "description": "Errado."},
        )

        assert resposta.status_code == 404
        assert stored(db) == []

    @pytest.mark.parametrize(
        "body",
        [
            {"information": "tribunal", "description": "Errado."},
            {"information": "resultado", "description": "   "},
            {"information": "resultado", "description": "x" * 2001},
            {"information": "resultado", "description": "com \x00 nulo"},
            {"information": "resultado"},
        ],
        ids=["informacao-desconhecida", "vazio", "longo-demais", "nul", "sem-relato"],
    )
    def test_relato_malformado_e_422(
        self,
        client: TestClient,
        db: psycopg.Connection[DictRow],
        body: dict[str, str],
    ) -> None:
        pessoa = analyst(db, manager(db))

        resposta = client.post(ROUTE, headers=header(pessoa), json=body)

        assert resposta.status_code == 422
        assert stored(db) == []

    def test_quem_reporta_nao_escolhe_o_autor(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)
        pessoa = analyst(db, boss)

        client.post(
            ROUTE,
            headers=header(pessoa),
            json={
                "information": "resultado",
                "description": "Errado.",
                "usuario_id": str(boss["id"]),
                "status": "aceito",
            },
        )

        [linha] = stored(db)
        assert linha["usuario_id"] == pessoa["id"]
        assert linha["situacao"] == "pendente"


class TestAListaDoGerente:
    def test_o_gerente_ve_os_reportes_com_quem_reportou(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)
        pessoa = analyst(db, boss)
        client.post(
            ROUTE,
            headers=header(pessoa),
            json={"information": "resultado", "description": "Primeiro."},
        )
        client.post(
            ROUTE,
            headers=header(pessoa),
            json={"information": "tese", "description": "Segundo."},
        )

        resposta = client.get("/reports", headers=header(boss))

        assert resposta.status_code == 200
        lista = resposta.json()["reports"]
        assert [item["description"] for item in lista] == ["Segundo.", "Primeiro."]
        assert lista[0]["reported_by"] == {
            "id": str(pessoa["id"]),
            "name": "Bruno Dias",
            "email": "bruno@almeidacosta.com.br",
        }
        assert lista[0]["source"] == SOURCE
        assert lista[0]["identifier"] == IDENTIFIER
        assert lista[0]["information"] == "tese"

    def test_o_analista_nao_ve_a_lista(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        pessoa = analyst(db, manager(db))

        assert client.get("/reports", headers=header(pessoa)).status_code == 403

    def test_a_lista_vazia_e_uma_lista(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        resposta = client.get("/reports", headers=header(manager(db)))

        assert resposta.status_code == 200
        assert resposta.json() == {"reports": []}


class TestOSchemaFicaForaDoCore:
    def test_a_tabela_mora_em_qualidade(self, db: psycopg.Connection[DictRow]) -> None:
        """
        `publish` derruba o `core` inteiro a cada publicação; um reporte
        guardado ali sumiria justamente quando alguém fosse procurá-lo.
        """
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT table_schema FROM information_schema.tables "
                "WHERE table_name = 'reporte'"
            )
            schemas = {row["table_schema"] for row in cursor.fetchall()}

        assert schemas == {"qualidade"}

    def test_o_reporte_sobrevive_a_derrubada_do_core(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        pessoa = analyst(db, manager(db))
        client.post(
            ROUTE,
            headers=header(pessoa),
            json={"information": "resultado", "description": "Errado."},
        )

        # What `pipeline/publish.py` does, inside the test's transaction so the
        # rollback puts the fixture back.
        db.execute("DROP SCHEMA core CASCADE")

        assert len(stored(db)) == 1
