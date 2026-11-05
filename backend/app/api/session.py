"""
Entering, and knowing who entered.

Signing in is the only thing this API answers without an account, so it is also
the only place an outsider can push on. It gives one answer to every kind of
failure, and spends the same time on all of them.

There is no sign-out endpoint, on purpose. The token is signed rather than
stored, so the server has nothing to forget: the browser discards it and the
session is over. What does end a session from this side is revocation, and that
is a manager's action — `app.sessions.signed_in` re-reads the account on every
request precisely so it takes effect at once.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, EmailStr, Field

from app import accounts, sessions
from app.db import get_connection
from app.errors import DATABASE_RESPONSES, ErrorResponse

router = APIRouter(tags=["accounts"])

REFUSED = "E-mail ou senha incorretos, ou o acesso desta conta foi revogado."

PERSON_EXAMPLE: dict[str, Any] = {
    "id": "7c3f1f0e-2a5b-4c9d-8e1f-6b2d9a4c7e35",
    "name": "Ana Almeida Costa",
    "email": "advogada@almeidacosta.com.br",
    "phone": "+55 12 99999-0000",
    "role": "gerente",
    "active": True,
}


class Person(BaseModel):
    """An account, as everyone who may see it sees it. Never the password."""

    id: str = Field(description="Identifier of the account.")
    name: str = Field(description="As the person was registered.")
    email: str
    phone: str | None = Field(
        default=None, description="Optional: not every account registers one."
    )
    role: str = Field(
        description="`gerente` administers the company's access; `usuario` searches.",
        examples=["gerente"],
    )
    active: bool = Field(
        description="False once a manager revoked the access. The account stays "
        "readable; it simply cannot sign in."
    )

    model_config = {"json_schema_extra": {"example": PERSON_EXAMPLE}}


class Credentials(BaseModel):
    email: EmailStr = Field(examples=["advogada@almeidacosta.com.br"])
    password: str = Field(min_length=1, examples=["uma senha longa de verdade"])


class Session(BaseModel):
    token: str = Field(
        description="Send it back as `Authorization: Bearer <token>`.",
    )
    expires_in: int = Field(
        description="Seconds until the token stops being accepted.",
        examples=[43200],
    )
    user: Person


def person_of(row: dict[str, Any]) -> Person:
    return Person(
        id=str(row["id"]),
        name=row["nome"],
        email=row["email"],
        phone=row["telefone"],
        role=row["papel"],
        active=bool(row["ativo"]),
    )


@router.post(
    "/session",
    summary="Sign in",
    responses={
        **DATABASE_RESPONSES,
        401: {
            "model": ErrorResponse,
            "description": (
                "The credentials were refused. One answer covers an unknown "
                "address, a wrong password and a revoked account: telling them "
                "apart would let anyone ask this screen which addresses have "
                "an account here."
            ),
            "content": {"application/json": {"example": {"detail": REFUSED}}},
        },
    },
)
def sign_in(
    credentials: Credentials,
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Session:
    """
    Exchange an e-mail and a password for a session token.

    The token carries the account and expires on its own. Keep it for the
    `Authorization` header; every other route on this API requires it.
    """
    person = accounts.authenticate(
        connection, email=credentials.email, senha=credentials.password
    )

    if person is None:
        raise HTTPException(status_code=401, detail=REFUSED)

    token, seconds = sessions.issue(person)

    return Session(token=token, expires_in=seconds, user=person_of(person))


@router.get(
    "/session",
    summary="Who is signed in",
    responses={**DATABASE_RESPONSES},
)
def whoami(
    person: Annotated[dict[str, Any], Depends(sessions.signed_in)],
) -> Person:
    """
    The account behind the token being used.

    Read from the database rather than from the token, so a revoked account is
    refused here even while its token is still within its lifetime.
    """
    return person_of(person)
