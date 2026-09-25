"""
The courts a search can be narrowed to.

Read from the data on every request, so a court appears the moment its first
decision is published and no code has to learn its name.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app.db import get_connection
from app.errors import (
    NOT_PUBLISHED,
    OUT_OF_DATE,
    UNAVAILABLE,
    ErrorResponse,
    two_examples,
)

router = APIRouter(tags=["search"])

# A court is listed when at least one decision carries its abbreviation. Every
# decision in `core.decisao` is one the search can return — sealed ones never
# enter it — so this is exactly the set of courts a search can answer with.
#
# Starting from the court table keeps one row per court and the name the seed
# gives it. One statement answers for every court, and the decisions are only
# probed through the index on (tribunal_sigla, data_referencia), never read into
# the API. The abbreviation is unique, which makes the order stable.
COURTS_SQL = """
SELECT t.sigla, t.nome
FROM core.tribunal AS t
WHERE EXISTS (
    SELECT 1 FROM core.decisao AS d WHERE d.tribunal_sigla = t.sigla
)
ORDER BY t.sigla
"""


class Court(BaseModel):
    abbreviation: str = Field(
        description=(
            "The court's abbreviation. It is the value the search's `tribunal` "
            "parameter takes and the one its results carry in `court`, so it "
            "can be sent back as it arrives."
        ),
        examples=["TJDFT"],
    )
    name: str = Field(
        description="The court's full name, for a person to read.",
        examples=["Tribunal de Justiça do Distrito Federal e dos Territórios"],
    )


class Courts(BaseModel):
    courts: list[Court] = Field(
        description=(
            "Every court with at least one decision here, ordered by "
            "abbreviation. Empty when no court has a decision yet — a "
            "collection that is not published answers 503 instead."
        )
    )


TJDFT: dict[str, Any] = {
    "abbreviation": "TJDFT",
    "name": "Tribunal de Justiça do Distrito Federal e dos Territórios",
}

RESPONSES: dict[int | str, dict[str, Any]] = {
    200: two_examples(
        ("with decisions", "The usual answer.", {"courts": [TJDFT]}),
        (
            "no decisions",
            (
                "The courts are published but none has a decision yet. An empty "
                "list, not an error: nothing is wrong with the request."
            ),
            {"courts": []},
        ),
    ),
    503: {
        "model": ErrorResponse,
        "description": (
            "The data is not published here, is older than this API, or the "
            "database is not answering. Never an empty list: a failure is "
            "never presented as a collection with no courts."
        ),
        "content": {
            "application/json": {
                "examples": {
                    "not published": {"value": {"detail": NOT_PUBLISHED}},
                    "out of date": {"value": {"detail": OUT_OF_DATE}},
                    "database down": {"value": {"detail": UNAVAILABLE}},
                }
            }
        },
    },
}


@router.get(
    "/courts",
    summary="Courts with decisions to search",
    responses=RESPONSES,
)
def list_courts(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Courts:
    """
    The courts that have at least one decision in the collection, for a screen
    to offer as the search's court filter.

    A court only registered, with no decision yet, is left out: choosing it
    could only ever return nothing. The list is read from the data on every
    call, so a court whose decisions are published shows up on the next request.

    It covers the whole collection, not a search: no term, no period.
    """
    with connection.cursor() as cursor:
        cursor.execute(COURTS_SQL)
        rows = cursor.fetchall()

    return Courts(
        courts=[Court(abbreviation=row["sigla"], name=row["nome"]) for row in rows]
    )
