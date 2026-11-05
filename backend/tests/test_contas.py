"""
Accounts, roles, and what each one may do.

Three promises are tested here because breaking any of them is silent. The
tool refuses everyone without an account. A manager sees and administers
everyone, except their own account. And revoking someone takes the tool away
from them now — not when their token happens to expire.

One firm uses this system, with few people in it, so there is no tenancy to
keep apart: a manager who can see one account can see all of them.
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


@pytest.fixture
def db(db_rolled_back: psycopg.Connection[DictRow]) -> psycopg.Connection[DictRow]:
    db_rolled_back.execute("DELETE FROM identidade.usuario")
    return db_rolled_back


@pytest.fixture
def client(db: psycopg.Connection[DictRow]) -> Any:
    from app.db import get_connection
    from app.main import app
    from app.sessions import gate

    # This file is about the door, so the prop the rest of the suite leans on
    # comes out: `conftest` opens the gate for every test, and here it closes.
    app.dependency_overrides.pop(gate, None)
    app.dependency_overrides[get_connection] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def manager(
    db: psycopg.Connection[DictRow], email: str = "ana@almeidacosta.com.br"
) -> dict[str, Any]:
    return accounts.create(
        db, nome="Ana Almeida Costa", email=email, senha=SENHA, papel="gerente"
    )


def member(
    db: psycopg.Connection[DictRow],
    boss: dict[str, Any],
    email: str = "bruno@almeidacosta.com.br",
) -> dict[str, Any]:
    return accounts.create(
        db,
        nome="Bruno Dias",
        email=email,
        senha=SENHA,
        papel="usuario",
        gerente=boss["id"],
    )


def header(person: dict[str, Any]) -> dict[str, str]:
    token, _ = sessions.issue(person)
    return {"Authorization": f"Bearer {token}"}


def sign_in(client: TestClient, email: str, senha: str = SENHA) -> Any:
    return client.post("/session", json={"email": email, "password": senha})


class TestAPortaFechada:
    """Sem conta, a ferramenta não responde nada além de entrar."""

    def test_toda_rota_exige_conta(self, client: TestClient) -> None:
        for rota in ("/decisions?q=dano", "/courts", "/filters", "/doctrine?q=x"):
            assert client.get(rota).status_code == 401, rota

    def test_o_que_fica_de_fora_e_so_entrar_e_o_health(
        self, client: TestClient
    ) -> None:
        # Fechado por padrão: uma rota nova nasce protegida, e abrir exige
        # escrever o caminho em PUBLIC_PATHS, onde dá para ler a lista inteira.
        assert sessions.PUBLIC_PATHS == frozenset(
            {
                "/health",
                "/session",
                "/docs",
                "/redoc",
                "/openapi.json",
                "/docs/oauth2-redirect",
            }
        )
        assert client.get("/health").status_code == 200

    def test_token_inventado_nao_abre(self, client: TestClient) -> None:
        resposta = client.get(
            "/decisions?q=dano", headers={"Authorization": "Bearer inventado"}
        )

        assert resposta.status_code == 401

    def test_a_recusa_diz_ao_navegador_que_e_de_login(self, client: TestClient) -> None:
        # Sem este cabeçalho a tela não sabe distinguir "entre na sua conta" de
        # "o servidor caiu", e manda o leitor tentar de novo em vez de entrar.
        assert client.get("/courts").headers["WWW-Authenticate"] == "Bearer"


class TestEntrar:
    def test_entra_e_recebe_token(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        manager(db)

        resposta = sign_in(client, "ana@almeidacosta.com.br")

        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["user"]["role"] == "gerente"
        assert corpo["expires_in"] > 0
        assert "senha" not in resposta.text and "hash" not in resposta.text

    def test_o_email_nao_distingue_maiuscula(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        manager(db)

        assert sign_in(client, "ANA@AlmeidaCosta.com.BR").status_code == 200

    def test_a_recusa_e_a_mesma_para_senha_errada_e_conta_inexistente(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        """
        Respostas diferentes transformariam a tela de login numa consulta: quem
        quisesse saber se um escritório é cliente bastaria tentar um e-mail.
        """
        manager(db)

        errada = sign_in(client, "ana@almeidacosta.com.br", "não é essa")
        inexistente = sign_in(client, "ninguem@exemplo.com", "não é essa")

        assert errada.status_code == inexistente.status_code == 401
        assert errada.json() == inexistente.json()

    def test_quem_foi_revogado_nao_entra(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)
        pessoa = member(db, boss)
        accounts.revoke(db, identifier=pessoa["id"], manager=boss["id"])

        assert sign_in(client, "bruno@almeidacosta.com.br").status_code == 401

    def test_a_senha_nunca_fica_legivel_no_banco(
        self, db: psycopg.Connection[DictRow]
    ) -> None:
        manager(db)

        with db.cursor() as cursor:
            cursor.execute("SELECT senha_hash FROM identidade.usuario")
            row = cursor.fetchone()

        assert row is not None
        assert SENHA not in row["senha_hash"]
        assert row["senha_hash"].startswith("$argon2")


class TestOQueCadaPapelPode:
    def test_usuario_comum_pesquisa(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        pessoa = member(db, manager(db))

        assert client.get("/courts", headers=header(pessoa)).status_code == 200

    def test_usuario_comum_nao_administra(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        pessoa = member(db, manager(db))
        cabecalho = header(pessoa)

        assert client.get("/users", headers=cabecalho).status_code == 403
        assert (
            client.post(
                "/users",
                headers=cabecalho,
                json={"name": "X", "email": "x@y.com", "password": SENHA},
            ).status_code
            == 403
        )

    def test_a_api_nao_cria_gerente(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        """
        O papel não é parâmetro. Se fosse, bastaria um gerente comprometido
        para fabricar outros, e o dono deixaria de controlar quem administra.
        """
        boss = manager(db)

        criado = client.post(
            "/users",
            headers=header(boss),
            json={
                "name": "Tentativa",
                "email": "tentativa@almeidacosta.com.br",
                "password": SENHA,
                "role": "gerente",
                "papel": "gerente",
            },
        )

        assert criado.status_code == 201
        assert criado.json()["role"] == "usuario"


class TestOQueOGerenteAlcanca:
    def test_o_gerente_ve_todo_mundo(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        """
        Uma empresa só, poucas pessoas: o gerente enxerga o sistema inteiro,
        inclusive quem outro gerente cadastrou.
        """
        boss = manager(db)
        member(db, boss)
        outro = manager(db, "carla@almeidacosta.com.br")
        member(db, outro, "diego@almeidacosta.com.br")

        lista = client.get("/users", headers=header(boss)).json()["users"]

        assert {pessoa["email"] for pessoa in lista} == {
            "ana@almeidacosta.com.br",
            "bruno@almeidacosta.com.br",
            "carla@almeidacosta.com.br",
            "diego@almeidacosta.com.br",
        }

    def test_os_gerentes_aparecem_primeiro(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db, "zelia@almeidacosta.com.br")
        member(db, boss, "ana@almeidacosta.com.br")

        lista = client.get("/users", headers=header(boss)).json()["users"]

        assert [pessoa["role"] for pessoa in lista] == ["gerente", "usuario"]

    def test_revoga_quem_outro_gerente_cadastrou(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)
        alheio = member(db, manager(db, "carla@almeidacosta.com.br"), "diego@x.com")

        resposta = client.delete(f"/users/{alheio['id']}/access", headers=header(boss))

        assert resposta.status_code == 200
        assert resposta.json()["active"] is False

    def test_o_gerente_nao_revoga_a_si_mesmo(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        # Senão a empresa fica sem quem administre, e só o dono pode repor.
        boss = manager(db)

        resposta = client.delete(f"/users/{boss['id']}/access", headers=header(boss))

        assert resposta.status_code == 404
        assert accounts.by_id(db, boss["id"])["ativo"] is True  # type: ignore[index]

    def test_conta_inexistente_e_404(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)

        resposta = client.delete(
            "/users/0f9b9d1e-0000-4000-8000-000000000000/access",
            headers=header(boss),
        )

        assert resposta.status_code == 404

    def test_o_email_e_unico(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)
        member(db, boss, "repetido@exemplo.com")

        resposta = client.post(
            "/users",
            headers=header(boss),
            json={
                "name": "Repetido",
                "email": "REPETIDO@exemplo.com",
                "password": SENHA,
            },
        )

        assert resposta.status_code == 409


class TestRevogar:
    def test_revogar_tira_a_ferramenta_na_hora(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        """
        O teste que esta história existe para passar, e o defeito que ele pegou.

        A porta conferia só a assinatura do token. Como buscar e ler decisão
        não dependem de `signed_in`, quem fosse revogado continuava pesquisando
        até o token vencer — doze horas depois. A revogação não revogava nada.
        """
        boss = manager(db)
        pessoa = member(db, boss)
        cabecalho = header(pessoa)

        assert client.get("/decisions?q=dano", headers=cabecalho).status_code == 200

        client.delete(f"/users/{pessoa['id']}/access", headers=header(boss))

        for rota in ("/decisions?q=dano", "/courts", "/doctrine?q=x", "/session"):
            assert client.get(rota, headers=cabecalho).status_code == 401, rota

    def test_revogar_desativa_e_nao_apaga(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        """
        A conta pesquisou, e apagar a linha apagaria o registro de que pesquisou.
        Ela continua na lista, marcada.
        """
        boss = manager(db)
        pessoa = member(db, boss)

        client.delete(f"/users/{pessoa['id']}/access", headers=header(boss))
        lista = client.get("/users", headers=header(boss)).json()["users"]
        revogado = next(p for p in lista if p["id"] == str(pessoa["id"]))

        assert revogado["active"] is False
        assert accounts.by_id(db, pessoa["id"]) is not None

    def test_a_revogacao_registra_quando(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)
        pessoa = member(db, boss)

        client.delete(f"/users/{pessoa['id']}/access", headers=header(boss))

        with db.cursor() as cursor:
            cursor.execute(
                "SELECT revogado_em FROM identidade.usuario WHERE id = %s",
                (pessoa["id"],),
            )
            row = cursor.fetchone()

        assert row is not None and row["revogado_em"] is not None

    def test_da_para_desfazer_uma_revogacao_errada(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)
        pessoa = member(db, boss)
        client.delete(f"/users/{pessoa['id']}/access", headers=header(boss))

        devolvido = client.post(f"/users/{pessoa['id']}/access", headers=header(boss))

        assert devolvido.status_code == 200
        assert devolvido.json()["active"] is True
        assert sign_in(client, "bruno@almeidacosta.com.br").status_code == 200


class TestOBancoSegura:
    def test_usuario_comum_nao_existe_sem_gerente(
        self, db: psycopg.Connection[DictRow]
    ) -> None:
        """
        Sem gerente ninguém responde por ele e ninguém pode revogá-lo — uma
        conta órfã, viva para sempre. A trava está no banco e não só no código.
        """
        with pytest.raises(psycopg.errors.CheckViolation):
            accounts.create(
                db,
                nome="Orfao",
                email="orfao@exemplo.com",
                senha=SENHA,
                papel="usuario",
            )

    def test_gerente_nao_responde_a_outro_gerente(
        self, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)

        with pytest.raises(psycopg.errors.CheckViolation):
            accounts.create(
                db,
                nome="Chefe de chefe",
                email="outro@exemplo.com",
                senha=SENHA,
                papel="gerente",
                gerente=boss["id"],
            )

    def test_papel_fora_dos_dois_nao_entra(
        self, db: psycopg.Connection[DictRow]
    ) -> None:
        with pytest.raises(psycopg.errors.CheckViolation):
            accounts.create(
                db,
                nome="Deus",
                email="root@exemplo.com",
                senha=SENHA,
                papel="admin",  # type: ignore[arg-type]
            )


class TestAsRegrasDoCadastro:
    """
    A senha e o telefone, conferidos onde não dá para pular.

    A tela ajuda quem digita, e não é guarda: nada impede uma requisição de
    chegar sem passar por ela. Estes testes batem na API.
    """

    def test_a_senha_precisa_das_tres_coisas(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)

        for fraca in ("Curta1", "semmaiuscula1", "SEMNUMEROAQUI", "1234567"):
            resposta = client.post(
                "/users",
                headers=header(boss),
                json={
                    "name": "Alguem da Equipe",
                    "email": f"{fraca}@exemplo.com",
                    "password": fraca,
                },
            )

            assert resposta.status_code == 422, fraca
            assert "maiúscula" in resposta.json()["detail"]

    def test_a_recusa_diz_as_tres_de_uma_vez(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        """
        Uma de cada vez transformaria escolher senha em adivinhação: conserta o
        tamanho, descobre a maiúscula; conserta a maiúscula, descobre o número.
        """
        boss = manager(db)

        resposta = client.post(
            "/users",
            headers=header(boss),
            json={
                "name": "Alguem da Equipe",
                "email": "x@exemplo.com",
                "password": "curta",
            },
        )
        detalhe = resposta.json()["detail"]

        assert "8 caracteres" in detalhe
        assert "maiúscula" in detalhe
        assert "número" in detalhe

    def test_a_senha_boa_passa(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)

        resposta = client.post(
            "/users",
            headers=header(boss),
            json={"name": "Boa", "email": "boa@exemplo.com", "password": "Senha123"},
        )

        assert resposta.status_code == 201

    def test_o_telefone_recusa_letra_em_vez_de_apagar(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        """
        O defeito que apareceu ao testar: descartar a letra em silêncio fazia
        `1299999000a` virar um fixo de dez dígitos, com cara de certo e sem ser
        o número de ninguém.
        """
        boss = manager(db)

        resposta = client.post(
            "/users",
            headers=header(boss),
            json={
                "name": "Alguem da Equipe",
                "email": "x@exemplo.com",
                "password": "Senha123",
                "phone": "3131231231aaaa23213",
            },
        )

        assert resposta.status_code == 422
        assert "algarismos" in resposta.json()["detail"]

    def test_o_telefone_fica_num_formato_so(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)
        escritos = ("12999990000", "(12) 99999-0000", "+55 12 99999 0000")

        for n, escrito in enumerate(escritos):
            criado = client.post(
                "/users",
                headers=header(boss),
                json={
                    "name": "Alguem da Equipe",
                    "email": f"x{n}@exemplo.com",
                    "password": "Senha123",
                    "phone": escrito,
                },
            )

            assert criado.status_code == 201, escrito
            assert criado.json()["phone"] == "(12) 99999-0000", escrito

    def test_o_telefone_continua_opcional(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)

        criado = client.post(
            "/users",
            headers=header(boss),
            json={
                "name": "Sem telefone",
                "email": "s@exemplo.com",
                "password": "Senha123",
            },
        )

        assert criado.status_code == 201
        assert criado.json()["phone"] is None

    def test_numero_curto_demais_nao_entra(
        self, client: TestClient, db: psycopg.Connection[DictRow]
    ) -> None:
        boss = manager(db)

        resposta = client.post(
            "/users",
            headers=header(boss),
            json={
                "name": "Alguem da Equipe",
                "email": "x@exemplo.com",
                "password": "Senha123",
                "phone": "99999-0000",
            },
        )

        assert resposta.status_code == 422
