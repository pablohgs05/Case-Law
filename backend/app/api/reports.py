"""
A reader telling the tool one of its readings is wrong.

The tool infers four things about a decision — the appeal's outcome, how the
panel voted, how each cited precedent was used, and the thesis — and says so
where it shows them. This is where a reader who disagrees says so back.

A report is a request for review and nothing else. It is written to its own
schema, outside `core`, and nothing here writes to `core`: the classification
the search shows stays exactly as it was published until someone reviews it.
What was published is copied into the report, because the next publication
may change it, and a report that no longer says what it disagreed with cannot
be reviewed.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field, field_validator

from app import sessions
from app.api.users import FORBIDDEN_RESPONSE
from app.db import get_connection
from app.errors import DATABASE_RESPONSES, NOT_FOUND_RESPONSE

router = APIRouter(tags=["quality"])

Information = Literal["resultado", "deliberacao", "aderencia", "tese"]

MAX_DESCRIPTION = 2000

RECEIVED = (
    "Recebemos o seu reporte. A classificação publicada continua a mesma até "
    "que alguém o revise."
)

KIND_LABELS = {"sumula": "Súmula", "tema": "Tema"}

# What the tool publishes for each information, read the way the search reads
# it. The precedents are one row per citation, so they are read apart.
PUBLISHED_SQL = """
SELECT resultado, deliberacao, tese
FROM core.decisao
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
"""

ADHERENCE_SQL = """
SELECT corte, tipo, numero, aderencia
FROM core.decisao_precedente
WHERE fonte_codigo = %(source)s AND identificador_fonte = %(identifier)s
ORDER BY tipo, numero, corte
"""

INSERT_SQL = """
INSERT INTO qualidade.reporte (
    fonte_codigo, identificador_fonte, informacao, valor_publicado, relato,
    usuario_id
)
VALUES (
    %(source)s, %(identifier)s, %(information)s, %(published)s,
    %(description)s, %(person)s
)
RETURNING id, criado_em, situacao
"""

# Newest first, closing on the key so two reports in the same instant never
# swap places between two readings. An inner join loses nothing: an account is
# revoked, never deleted, so every report still has the person who sent it.
LIST_SQL = """
SELECT
    r.id, r.fonte_codigo, r.identificador_fonte, r.informacao,
    r.valor_publicado, r.relato, r.situacao, r.criado_em,
    u.id AS usuario_id, u.nome, u.email
FROM qualidade.reporte AS r
JOIN identidade.usuario AS u ON u.id = r.usuario_id
ORDER BY r.criado_em DESC, r.id
"""


class NewReport(BaseModel):
    information: Information = Field(
        description=(
            "Which of the tool's readings is contested: `resultado`, the "
            "appeal's outcome; `deliberacao`, how the panel voted; "
            "`aderencia`, how the cited precedents were used; `tese`, the "
            "thesis."
        ),
        examples=["resultado"],
    )
    description: str = Field(
        min_length=1,
        max_length=MAX_DESCRIPTION,
        description="What is wrong, in the reader's own words.",
        examples=["O dispositivo diz que o recurso foi provido em parte."],
    )

    @field_validator("description")
    @classmethod
    def has_content(cls, value: str) -> str:
        stripped = value.strip()

        if not stripped:
            raise ValueError("Descreva o que está incorreto.")

        # A NUL byte cannot be sent to PostgreSQL as text.
        if "\x00" in stripped:
            raise ValueError("O relato contém um caractere inválido.")

        return stripped


class Reporter(BaseModel):
    id: str
    name: str
    email: str


class Report(BaseModel):
    id: str = Field(description="Identifier of the report.")
    source: str = Field(examples=["tjdft-jurisdf"])
    identifier: str = Field(examples=["2084700"])
    information: Information
    published_value: str | None = Field(
        description=(
            "What the tool was publishing for that information when the report "
            "arrived. `null` when it published nothing for it."
        ),
        examples=["negado"],
    )
    description: str
    status: Literal["pendente", "aceito", "recusado"] = Field(
        description=(
            "`pendente` until someone reviews it. A report never changes the "
            "classification on its own."
        ),
        examples=["pendente"],
    )
    received_at: datetime


class Receipt(Report):
    message: str = Field(
        description="The confirmation to show the reader.", examples=[RECEIVED]
    )


class ListedReport(Report):
    reported_by: Reporter


class Reports(BaseModel):
    reports: list[ListedReport] = Field(description="Newest first.")


def _adherence(rows: list[DictRow]) -> str | None:
    if not rows:
        return None

    return "; ".join(
        f"{row['corte']} {KIND_LABELS.get(row['tipo'], row['tipo'])} "
        f"{row['numero']}: {row['aderencia']}"
        for row in rows
    )


def _published(
    connection: Connection[DictRow],
    source: str,
    identifier: str,
    information: Information,
) -> str | None:
    """
    What the tool publishes for this information on this decision. Raises 404
    when the decision is not in the published base: a report about nothing
    cannot be reviewed.
    """
    parameters = {"source": source, "identifier": identifier}

    with connection.cursor() as cursor:
        cursor.execute(PUBLISHED_SQL, parameters)
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Decision not found.")

        if information == "aderencia":
            cursor.execute(ADHERENCE_SQL, parameters)
            return _adherence(cursor.fetchall())

    value = row[information]
    return value if value is None else str(value)


@router.post(
    "/decisions/{source}/{identifier}/reports",
    summary="Report an incorrect classification",
    status_code=201,
    responses={**DATABASE_RESPONSES, **NOT_FOUND_RESPONSE},
)
def report_classification(
    report: NewReport,
    person: Annotated[dict[str, Any], Depends(sessions.signed_in)],
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    source: Annotated[str, Path(description="Collection code.")],
    identifier: Annotated[str, Path(description="Identifier within the collection.")],
) -> Receipt:
    """
    Tell the tool one of its readings of this decision is wrong.

    The report is recorded with the decision, the information contested, what
    was published for it at that moment, who sent it and when. It does **not**
    change the classification: the search keeps showing what was published
    until the report is reviewed.
    """
    if "\x00" in source or "\x00" in identifier:
        raise HTTPException(status_code=404, detail="Decision not found.")

    published = _published(connection, source, identifier, report.information)

    with connection.cursor() as cursor:
        cursor.execute(
            INSERT_SQL,
            {
                "source": source,
                "identifier": identifier,
                "information": report.information,
                "published": published,
                "description": report.description,
                "person": person["id"],
            },
        )
        created = cursor.fetchone()

    assert created is not None

    return Receipt(
        id=str(created["id"]),
        source=source,
        identifier=identifier,
        information=report.information,
        published_value=published,
        description=report.description,
        status=created["situacao"],
        received_at=created["criado_em"],
        message=RECEIVED,
    )


@router.get(
    "/reports",
    summary="Every report, for a manager",
    responses={**DATABASE_RESPONSES, **FORBIDDEN_RESPONSE},
)
def list_reports(
    _: Annotated[dict[str, Any], Depends(sessions.manager)],
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Reports:
    """
    Every report received, newest first, with who sent it.

    A manager's list: it names the people who sent each report, which is not
    something one analyst needs to know about another.
    """
    with connection.cursor() as cursor:
        cursor.execute(LIST_SQL)
        rows = cursor.fetchall()

    return Reports(
        reports=[
            ListedReport(
                id=str(row["id"]),
                source=row["fonte_codigo"],
                identifier=row["identificador_fonte"],
                information=row["informacao"],
                published_value=row["valor_publicado"],
                description=row["relato"],
                status=row["situacao"],
                received_at=row["criado_em"],
                reported_by=Reporter(
                    id=str(row["usuario_id"]), name=row["nome"], email=row["email"]
                ),
            )
            for row in rows
        ]
    )
