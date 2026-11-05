"""
The owner's commands, run on the server and nowhere else.

Creating a manager is the one action with no route behind it. A manager can add
people and revoke them, so being able to create one is being able to create
anything — and an endpoint for it, however well guarded, is a door on the
public internet. This runs with a shell on the machine that holds the database,
which is a door that was already there.

    python -m app.owner migrar
    python -m app.owner gerente "Ana Almeida Costa" ana@almeidacosta.com.br
    python -m app.owner listar-gerentes
"""

import getpass
import sys
from pathlib import Path

from psycopg import Connection
from psycopg.rows import DictRow

from app import accounts, passwords
from app.db import connection, pool

# Beside the module, so it travels into the image with the code: this
# command runs on the server, where the repository is not checked out.
SCHEMA = Path(__file__).resolve().parent / "identidade.sql"

MANAGERS_SQL = """
SELECT nome, email, ativo, criado_em,
       (SELECT COUNT(*) FROM identidade.usuario AS u
         WHERE u.gerente_id = g.id) AS equipe
FROM identidade.usuario AS g
WHERE papel = 'gerente'
ORDER BY LOWER(nome)
"""


def migrate(db: Connection[DictRow]) -> None:
    """
    Apply the identity schema. Idempotent, so it is safe on a database that
    already has it — which is how an environment created before accounts
    existed gets them without being rebuilt.
    """
    db.execute(SCHEMA.read_text(encoding="utf-8"))
    print(f"schema identidade aplicado a partir de {SCHEMA}")


def ask_password() -> str:
    """
    Read it twice, without echoing. Typed once, a slip becomes a manager who
    cannot sign in and an owner who has to be called back.
    """
    while True:
        chosen = getpass.getpass("Senha do gerente: ")

        recusa = passwords.refuses(chosen)

        if recusa:
            print(f"  {recusa}")
            continue

        if chosen != getpass.getpass("Repita a senha: "):
            print("  as duas não conferem.")
            continue

        return chosen


def create_manager(db: Connection[DictRow], name: str, email: str) -> None:
    migrate(db)

    try:
        created = accounts.create(
            db, nome=name, email=email, senha=ask_password(), papel="gerente"
        )
    except accounts.EmailTaken:
        raise SystemExit(f"já existe uma conta com o e-mail {email}") from None

    print(f"gerente criado: {created['nome']} <{created['email']}>")
    print(f"  id {created['id']}")
    print("  ele já pode entrar e cadastrar a equipe dele.")


def list_managers(db: Connection[DictRow]) -> None:
    with db.cursor() as cursor:
        cursor.execute(MANAGERS_SQL)
        rows = cursor.fetchall()

    if not rows:
        print("nenhum gerente cadastrado ainda.")
        return

    for row in rows:
        estado = "ativo" if row["ativo"] else "revogado"
        print(
            f"{row['nome']} <{row['email']}> · {estado}"
            f" · {row['equipe']} na equipe"
            f" · desde {row['criado_em']:%d/%m/%Y}"
        )


def main() -> None:
    arguments = sys.argv[1:]

    if not arguments:
        raise SystemExit(__doc__)

    command, rest = arguments[0], arguments[1:]

    # The API opens the pool from its lifespan; a command has no lifespan, so
    # it opens its own and gives the connection back when it is done.
    pool.open()
    try:
        run(command, rest)
    finally:
        pool.close()


def run(command: str, rest: list[str]) -> None:
    with connection() as db:
        if command == "migrar":
            migrate(db)
        elif command == "gerente":
            if len(rest) != 2:
                raise SystemExit('uso: gerente "Nome Completo" email@empresa.com')
            create_manager(db, rest[0], rest[1])
        elif command == "listar-gerentes":
            list_managers(db)
        else:
            raise SystemExit(f"comando desconhecido: {command}\n{__doc__}")


if __name__ == "__main__":
    main()
