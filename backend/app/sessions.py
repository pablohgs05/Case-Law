"""
Proving who is asking, on every request.

A signed token carries the account id and the role, and the API reads it from
the `Authorization` header. Nothing on the server remembers a session, so a
token is valid until it expires — which is why the role is re-read from the
database on every request rather than trusted from the token: revoking someone
has to take effect now, not when their token runs out.

Closed by default. The gate below refuses anything that is not on the list of
public paths, so a router added later is protected without anyone remembering
to protect it.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request
from psycopg import Connection
from psycopg.rows import DictRow

from app import accounts
from app.config import session_secret_or_fail, settings
from app.db import get_connection

ALGORITHM = "HS256"

# What a caller may reach with no account at all. Everything else is refused.
# `/session` is here because logging in is how a caller stops being anonymous,
# and the health check because the orchestrator has no credentials.
PUBLIC_PATHS = frozenset(
    {
        "/health",
        "/session",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/docs/oauth2-redirect",
    }
)

NOT_SIGNED_IN = "Entre na sua conta para usar a ferramenta."
SESSION_OVER = "Sua sessão expirou. Entre novamente."
NOT_A_MANAGER = "Só um gerente pode administrar usuários."


def issue(person: dict[str, Any]) -> tuple[str, int]:
    """The token for this account, and how many seconds it lasts."""
    seconds = settings.session_hours * 3600
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(person["id"]),
            "papel": person["papel"],
            "iat": now,
            "exp": now + timedelta(seconds=seconds),
        },
        session_secret_or_fail(),
        algorithm=ALGORITHM,
    )
    return token, seconds


def read(token: str) -> dict[str, Any] | None:
    try:
        return dict(jwt.decode(token, session_secret_or_fail(), algorithms=[ALGORITHM]))
    except jwt.PyJWTError:
        return None


def _bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    kind, _, token = header.partition(" ")
    return token.strip() if kind.lower() == "bearer" and token.strip() else None


def _unauthorized(detail: str) -> HTTPException:
    # The header is what tells a browser this is a sign-in problem rather than
    # a server fault, and it is what the frontend keys its redirect on.
    return HTTPException(
        status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def _resolve(request: Request, connection: Connection[DictRow]) -> dict[str, Any]:
    """
    The account behind this request, refusing it when there is none.

    The row is read fresh every time, and that is the whole of revocation. A
    token is signed rather than stored, so nothing on the server can take one
    back: the only way a manager's revocation reaches someone who already
    holds a token is for every request to ask the table whether that account is
    still allowed in.
    """
    token = _bearer(request)

    if token is None:
        raise _unauthorized(NOT_SIGNED_IN)

    claims = read(token)

    if claims is None or not claims.get("sub"):
        raise _unauthorized(SESSION_OVER)

    person = accounts.by_id(connection, str(claims["sub"]))

    if person is None or not person["ativo"]:
        raise _unauthorized(SESSION_OVER)

    return person


def signed_in(
    request: Request,
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> dict[str, Any]:
    return _resolve(request, connection)


def manager(
    person: Annotated[dict[str, Any], Depends(signed_in)],
) -> dict[str, Any]:
    if person["papel"] != "gerente":
        raise HTTPException(status_code=403, detail=NOT_A_MANAGER)
    return person


def gate(
    request: Request,
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> None:
    """
    The door, applied to every route at once.

    Declared on the application rather than per router, so adding a router is
    not a chance to forget. A path reachable without an account has to be named
    in `PUBLIC_PATHS` — a decision someone makes on purpose, in one place.

    It resolves the account rather than only checking the signature. Checking
    the signature alone was the first version, and it left revocation not
    revoking anything: the routes that matter — searching, reading a decision —
    do not depend on `signed_in`, so a revoked account kept working until its
    token expired, up to twelve hours later.
    """
    path = request.url.path.rstrip("/") or "/"

    if path in PUBLIC_PATHS or request.method == "OPTIONS":
        return

    _resolve(request, connection)
