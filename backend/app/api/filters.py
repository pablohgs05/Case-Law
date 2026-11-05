"""The available judging bodies, reporting judges and procedural classes."""

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

JUDGING_BODIES_SQL = """
SELECT DISTINCT orgao_julgador COLLATE "C" AS value
FROM core.decisao
WHERE NULLIF(BTRIM(orgao_julgador), '') IS NOT NULL
ORDER BY value
"""

REPORTING_JUDGES_SQL = """
SELECT DISTINCT relator COLLATE "C" AS value
FROM core.decisao
WHERE NULLIF(BTRIM(relator), '') IS NOT NULL
ORDER BY value
"""

PROCEDURAL_CLASSES_SQL = """
SELECT c.codigo_cnj AS value, c.nome AS label
FROM core.classe_processual AS c
WHERE EXISTS (
    SELECT 1 FROM core.decisao AS d WHERE d.classe_cnj = c.codigo_cnj
)
ORDER BY c.nome COLLATE "C", c.codigo_cnj
"""


class ProceduralClassOption(BaseModel):
    value: int = Field(
        description="The CNJ code of a class present on at least one decision.",
        examples=[198],
    )
    label: str = Field(
        description="The procedural class name from the CNJ catalogue.",
        examples=["Apelação Cível"],
    )


class FilterOption(BaseModel):
    value: str = Field(
        description=(
            "The exact nonblank value stored on at least one searchable decision. "
            "Send this value unchanged when filtering."
        ),
        examples=["1ª TURMA CÍVEL"],
    )
    label: str = Field(
        description="The value to display. It preserves the source spelling.",
        examples=["1ª TURMA CÍVEL"],
    )


JUDGING_BODY = {"value": "1ª TURMA CÍVEL", "label": "1ª TURMA CÍVEL"}
REPORTING_JUDGE = {
    "value": "FABRÍCIO FONTOURA BEZERRA",
    "label": "FABRÍCIO FONTOURA BEZERRA",
}
PROCEDURAL_CLASS = {"value": 198, "label": "Apelação Cível"}


class FilterOptions(BaseModel):
    judging_bodies: list[FilterOption] = Field(
        description=(
            "Distinct nonblank judging-body values from decisions in the whole "
            "published collection, in deterministic order."
        ),
        examples=[[JUDGING_BODY]],
    )
    reporting_judges: list[FilterOption] = Field(
        description=(
            "Distinct nonblank reporting-judge values from decisions in the whole "
            "published collection, in deterministic order."
        ),
        examples=[[REPORTING_JUDGE]],
    )
    procedural_classes: list[ProceduralClassOption] = Field(
        description=(
            "Classes with at least one decision in the whole published collection, "
            "ordered by name and then CNJ code. Empty when no class has decisions."
        ),
        examples=[[PROCEDURAL_CLASS]],
    )


EXAMPLE_OPTIONS = {
    "judging_bodies": [JUDGING_BODY],
    "reporting_judges": [REPORTING_JUDGE],
    "procedural_classes": [PROCEDURAL_CLASS],
}

RESPONSES: dict[int | str, dict[str, Any]] = {
    200: two_examples(
        ("with options", "The available values.", EXAMPLE_OPTIONS),
        (
            "no decisions",
            "The collection is published but has no nonblank values yet.",
            {"judging_bodies": [], "reporting_judges": [], "procedural_classes": []},
        ),
    ),
    503: {
        "model": ErrorResponse,
        "description": (
            "The data is not published here, is older than this API, or the "
            "database is not answering. A failure is never returned as empty lists."
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
    "/filters",
    summary="Decision filter options",
    responses=RESPONSES,
)
def list_filter_options(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> FilterOptions:
    """List all nonblank option values present in the searchable collection."""
    with connection.cursor() as cursor:
        cursor.execute(JUDGING_BODIES_SQL)
        judging_bodies = cursor.fetchall()

        cursor.execute(REPORTING_JUDGES_SQL)
        reporting_judges = cursor.fetchall()

        cursor.execute(PROCEDURAL_CLASSES_SQL)
        procedural_classes = cursor.fetchall()

    return FilterOptions(
        judging_bodies=[
            FilterOption(value=row["value"], label=row["value"])
            for row in judging_bodies
        ],
        reporting_judges=[
            FilterOption(value=row["value"], label=row["value"])
            for row in reporting_judges
        ],
        procedural_classes=[ProceduralClassOption(**row) for row in procedural_classes],
    )
