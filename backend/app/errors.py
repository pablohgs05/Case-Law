from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg import DataError, OperationalError
from psycopg.errors import UndefinedColumn, UndefinedObject, UndefinedTable
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, Field

NOT_PUBLISHED = (
    "The decisions have not been published to this environment yet. "
    "Nothing is wrong with your request."
)

# A column the code reads and the published data does not have. It means the
# same thing as a missing table — this environment is serving an older
# publication than the code expects — and it is answered the same way, because
# the caller can do nothing about either.
OUT_OF_DATE = (
    "This environment is serving a publication older than the API that reads "
    "it. Nothing is wrong with your request: the data has to be published "
    "again."
)

UNAVAILABLE = "The database is not answering right now. Try again in a moment."

MALFORMED = (
    "Part of the request is not text the database can read. Check for stray "
    "control characters, such as %00, in the query or the identifier."
)


class ErrorResponse(BaseModel):
    """What every failure on this API looks like, whatever went wrong."""

    detail: str = Field(
        description="One sentence a person can act on.",
        examples=[UNAVAILABLE],
    )


def _example(detail: str) -> dict[str, Any]:
    return {"application/json": {"example": {"detail": detail}}}


# Both endpoints read the same database, so they fail the same ways. Declared
# once and shared, so a new endpoint documents itself by reusing this.
DATABASE_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {
        "model": ErrorResponse,
        "description": "A parameter carries something the database cannot read.",
        "content": _example(MALFORMED),
    },
    503: {
        "model": ErrorResponse,
        "description": (
            "The decisions are not published here yet, or the database is not "
            "answering. Neither means the request was wrong."
        ),
        "content": _example(NOT_PUBLISHED),
    },
}

NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: {
        "model": ErrorResponse,
        "description": (
            "No decision with this identifier in this collection. A decision "
            "under seal answers the same way: it never enters the collection, "
            "so there is nothing to tell apart from one that never existed."
        ),
        "content": _example("Decision not found."),
    }
}


def two_examples(
    first: tuple[str, str, Any], second: tuple[str, str, Any]
) -> dict[str, Any]:
    """
    A 200 that answers two different shapes needs to show both. One example
    teaches the reader that the other case does not exist.
    """
    return {
        "content": {
            "application/json": {
                "examples": {
                    name: {"summary": summary, "value": value}
                    for name, summary, value in (first, second)
                }
            }
        }
    }


def _unavailable(detail: str) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": detail})


def register(app: FastAPI) -> None:
    @app.exception_handler(UndefinedTable)
    @app.exception_handler(UndefinedObject)
    async def _missing_dataset(_: Request, __: Exception) -> JSONResponse:
        return _unavailable(NOT_PUBLISHED)

    # UndefinedColumn is a sibling of the two above, not a subclass, so it
    # escaped them and reached the client as a bare 500.
    @app.exception_handler(UndefinedColumn)
    async def _stale_publication(_: Request, __: Exception) -> JSONResponse:
        return _unavailable(OUT_OF_DATE)

    @app.exception_handler(OperationalError)
    @app.exception_handler(PoolTimeout)
    async def _database_down(_: Request, __: Exception) -> JSONResponse:
        return _unavailable(UNAVAILABLE)

    # A caller controls every parameter, so a value PostgreSQL refuses to read
    # is a bad request, not a broken server. Registered centrally because the
    # next endpoint would otherwise have to remember this on its own.
    @app.exception_handler(DataError)
    async def _malformed_input(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": MALFORMED})
