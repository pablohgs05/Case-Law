"""
A manager running the firm's access.

Three things, and nothing more: add someone, see who is there, take the access
away from someone who left. There is no screen for creating a manager — the
owner does that on the server, so no request reaching this API from the
internet can ever mint one.

One firm uses this system, with few people in it, so a manager sees all of
them. The only account a manager cannot touch is their own: revoking yourself
would leave the firm with nobody able to administer it.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, EmailStr, Field

from app import accounts, passwords, phones, sessions
from app.api.session import PERSON_EXAMPLE, Person, person_of
from app.db import get_connection
from app.errors import DATABASE_RESPONSES, ErrorResponse

router = APIRouter(tags=["accounts"])

NO_SUCH_PERSON = "Não existe esse usuário, ou é a sua própria conta."
EMAIL_TAKEN = "Já existe uma conta com esse e-mail."
FORBIDDEN_RESPONSE: dict[int | str, dict[str, Any]] = {
    403: {
        "model": ErrorResponse,
        "description": "A signed-in account that is not a manager.",
        "content": {
            "application/json": {"example": {"detail": sessions.NOT_A_MANAGER}}
        },
    }
}


class NewUser(BaseModel):
    name: str = Field(min_length=2, max_length=120, examples=["Ana Almeida Costa"])
    email: EmailStr = Field(examples=["ana@almeidacosta.com.br"])
    phone: str | None = Field(
        default=None,
        max_length=40,
        description=(
            "Optional. The area code and the number, digits only: ten for a "
            "landline, eleven for a mobile. Stored as `(12) 99999-0000`."
        ),
        examples=["(12) 99999-0000"],
    )
    password: str = Field(
        min_length=1,
        description=(
            f"At least {passwords.MIN_LENGTH} characters, with one capital "
            "letter and one digit. Stored hashed and never readable again, "
            "by anyone."
        ),
    )


class Team(BaseModel):
    users: list[Person] = Field(
        description=(
            "Everyone with an account, managers first. Revoked accounts stay "
            "on the list, marked inactive: they ran searches, and hiding them "
            "would hide that."
        ),
    )

    model_config = {"json_schema_extra": {"example": {"users": [PERSON_EXAMPLE]}}}


@router.get(
    "/users",
    summary="Everyone with an account",
    responses={**DATABASE_RESPONSES, **FORBIDDEN_RESPONSE},
)
def list_users(
    _: Annotated[dict[str, Any], Depends(sessions.manager)],
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Team:
    """
    Everyone with an account, active or revoked.

    Managers appear first, then active people, then revoked ones, each group in
    alphabetical order.
    """
    return Team(users=[person_of(row) for row in accounts.everyone(connection)])


@router.post(
    "/users",
    summary="Add someone to the firm",
    status_code=201,
    responses={
        **DATABASE_RESPONSES,
        **FORBIDDEN_RESPONSE,
        409: {
            "model": ErrorResponse,
            "description": "The address already has an account.",
            "content": {"application/json": {"example": {"detail": EMAIL_TAKEN}}},
        },
    },
)
def add_user(
    new: NewUser,
    manager: Annotated[dict[str, Any], Depends(sessions.manager)],
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Person:
    """
    Create a common account.

    The role is not a parameter. A manager adds people who search; only the
    owner adds managers, on the server, so nothing reaching this API can raise
    its own privileges. The manager who created the account is recorded, which
    is the answer to "who let this person in" when two managers share the job.
    """
    # Checked here as well as on the screen: the screen is a convenience for
    # the person typing, and nothing stops a request from skipping it.
    recusa = passwords.refuses(new.password)

    if recusa:
        raise HTTPException(status_code=422, detail=recusa)

    try:
        telefone = phones.formatted(new.phone)
    except ValueError as malformado:
        raise HTTPException(status_code=422, detail=str(malformado)) from None

    try:
        created = accounts.create(
            connection,
            nome=new.name,
            email=new.email,
            senha=new.password,
            telefone=telefone,
            papel="usuario",
            gerente=manager["id"],
        )
    except accounts.EmailTaken:
        raise HTTPException(status_code=409, detail=EMAIL_TAKEN) from None

    return person_of(created)


@router.delete(
    "/users/{identifier}/access",
    summary="Revoke someone's access",
    responses={
        **DATABASE_RESPONSES,
        **FORBIDDEN_RESPONSE,
        404: {
            "model": ErrorResponse,
            "description": (
                "No account with this identifier, or it is the manager's own: "
                "revoking yourself would leave nobody able to administer."
            ),
            "content": {"application/json": {"example": {"detail": NO_SUCH_PERSON}}},
        },
    },
)
def revoke_access(
    identifier: Annotated[str, Path(description="Identifier of the account.")],
    manager: Annotated[dict[str, Any], Depends(sessions.manager)],
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Person:
    """
    Take the access away from someone who left the firm.

    It takes effect on the next request they make, not when their token
    expires. The account is deactivated rather than deleted: it ran searches,
    and removing the row would remove the record that it did.
    """
    revoked = accounts.revoke(connection, identifier=identifier, manager=manager["id"])

    if revoked is None:
        raise HTTPException(status_code=404, detail=NO_SUCH_PERSON)

    return person_of(revoked)


@router.post(
    "/users/{identifier}/access",
    summary="Give the access back",
    responses={**DATABASE_RESPONSES, **FORBIDDEN_RESPONSE},
)
def restore_access(
    identifier: Annotated[str, Path(description="Identifier of the account.")],
    manager: Annotated[dict[str, Any], Depends(sessions.manager)],
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Person:
    """
    Undo a revocation.

    Here because revoking the wrong person is an ordinary mistake, and without
    this the only repair would be a second account — which would leave the
    first one's searches orphaned from the person who ran them.
    """
    restored = accounts.restore(
        connection, identifier=identifier, manager=manager["id"]
    )

    if restored is None:
        raise HTTPException(status_code=404, detail=NO_SUCH_PERSON)

    return person_of(restored)
