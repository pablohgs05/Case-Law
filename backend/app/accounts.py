"""
Who exists, what they may do, and who answers for them.

Two roles. A *gerente* runs the firm's access: they add people, see everyone,
and revoke whoever leaves. A *usuario* searches and nothing else. The owner
adds managers out of band — there is no screen for it, by design.

One firm uses this system, with few people in it, so a manager sees all of
them. `gerente_id` stays as the record of who added whom — useful when two
managers are asked later who let somebody in — and is not a permission.

Revoking deactivates, never deletes. An account that ran searches has to stay
readable afterwards, and a deleted row would take the trail with it.
"""

from typing import Any, Literal
from uuid import UUID

from psycopg import Connection, errors
from psycopg.rows import DictRow

from app import passwords

Role = Literal["usuario", "gerente"]

FIELDS = """
  id, nome, telefone, email, papel, gerente_id, ativo, criado_em, revogado_em
"""

BY_EMAIL_SQL = f"""
SELECT {FIELDS}, senha_hash
FROM identidade.usuario
WHERE LOWER(email) = LOWER(%(email)s)
"""

BY_ID_SQL = f"""
SELECT {FIELDS}
FROM identidade.usuario
WHERE id = %(id)s
"""

# Everyone, managers first. Ordering closes on the key so two people added in
# the same second never swap places between two readings of the list.
EVERYONE_SQL = f"""
SELECT {FIELDS}
FROM identidade.usuario
ORDER BY papel = 'gerente' DESC, ativo DESC, LOWER(nome), id
"""

CREATE_SQL = f"""
INSERT INTO identidade.usuario (nome, telefone, email, senha_hash, papel, gerente_id)
VALUES (%(nome)s, %(telefone)s, %(email)s, %(senha)s, %(papel)s, %(gerente)s)
RETURNING {FIELDS}
"""

# A manager revokes anyone but themselves. Revoking yourself would lock the
# firm out of its own administration, and only the owner could put it back.
REVOKE_SQL = f"""
UPDATE identidade.usuario
SET ativo = FALSE, revogado_em = NOW()
WHERE id = %(id)s AND id <> %(manager)s AND ativo
RETURNING {FIELDS}
"""

RESTORE_SQL = f"""
UPDATE identidade.usuario
SET ativo = TRUE, revogado_em = NULL
WHERE id = %(id)s AND id <> %(manager)s AND NOT ativo
RETURNING {FIELDS}
"""

REHASH_SQL = """
UPDATE identidade.usuario SET senha_hash = %(senha)s WHERE id = %(id)s
"""


class EmailTaken(Exception):
    """The address already has an account, anywhere in the system."""


def _person(row: DictRow | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: value for key, value in row.items() if key != "senha_hash"}


def by_email(db: Connection[DictRow], email: str) -> DictRow | None:
    with db.cursor() as cursor:
        cursor.execute(BY_EMAIL_SQL, {"email": email})
        return cursor.fetchone()


def by_id(db: Connection[DictRow], identifier: UUID | str) -> dict[str, Any] | None:
    with db.cursor() as cursor:
        cursor.execute(BY_ID_SQL, {"id": str(identifier)})
        return _person(cursor.fetchone())


def everyone(db: Connection[DictRow]) -> list[dict[str, Any]]:
    with db.cursor() as cursor:
        cursor.execute(EVERYONE_SQL)
        return [person for row in cursor.fetchall() if (person := _person(row))]


def create(
    db: Connection[DictRow],
    *,
    nome: str,
    email: str,
    senha: str,
    telefone: str | None = None,
    papel: Role = "usuario",
    gerente: UUID | str | None = None,
) -> dict[str, Any]:
    parameters = {
        "nome": nome.strip(),
        "telefone": (telefone or "").strip() or None,
        "email": email.strip(),
        "senha": passwords.hash_password(senha),
        "papel": papel,
        "gerente": str(gerente) if gerente else None,
    }

    try:
        with db.cursor() as cursor:
            cursor.execute(CREATE_SQL, parameters)
            created = _person(cursor.fetchone())
    except errors.UniqueViolation as duplicate:
        raise EmailTaken(email) from duplicate

    assert created is not None
    return created


def revoke(
    db: Connection[DictRow], *, identifier: UUID | str, manager: UUID | str
) -> dict[str, Any] | None:
    with db.cursor() as cursor:
        cursor.execute(REVOKE_SQL, {"id": str(identifier), "manager": str(manager)})
        return _person(cursor.fetchone())


def restore(
    db: Connection[DictRow], *, identifier: UUID | str, manager: UUID | str
) -> dict[str, Any] | None:
    with db.cursor() as cursor:
        cursor.execute(RESTORE_SQL, {"id": str(identifier), "manager": str(manager)})
        return _person(cursor.fetchone())


def authenticate(
    db: Connection[DictRow], *, email: str, senha: str
) -> dict[str, Any] | None:
    """
    The account behind these credentials, or None.

    One answer for every kind of failure — unknown address, wrong password,
    revoked account. Telling them apart would let anyone ask the login screen
    which addresses have accounts here.
    """
    row = by_email(db, email)

    if row is None:
        # Spend the time anyway. Answering an unknown address faster than a
        # known one tells the asker which is which, without ever logging in.
        passwords.matches(passwords.hash_password("sem conta"), senha)
        return None

    if not passwords.matches(str(row["senha_hash"]), senha):
        return None

    if not row["ativo"]:
        return None

    if passwords.stale(str(row["senha_hash"])):
        with db.cursor() as cursor:
            cursor.execute(
                REHASH_SQL,
                {"senha": passwords.hash_password(senha), "id": row["id"]},
            )

    return _person(row)
