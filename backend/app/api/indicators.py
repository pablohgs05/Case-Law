"""
What the collection is, rather than what is in it.

These answer questions a reader asks before trusting a search: how recent the
data is, and later how it is distributed. They read the load record the pipeline
writes, never the courts themselves.
"""

from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg import Connection
from psycopg.rows import DictRow
from pydantic import BaseModel, Field

from app.api.decisions import (
    MATCH,
    SEARCH_RESPONSES,
    _narrowing,
)
from app.db import get_connection
from app.errors import NOT_PUBLISHED, UNAVAILABLE

router = APIRouter(tags=["indicators"])

# A load that failed left nothing behind, so it cannot be what the data is
# from. Ordering matters: without it PostgreSQL returns whichever row it reaches
# first, which is right on a small table and wrong on a real one.
LAST_LOAD_SQL = """
SELECT concluida_em, registros_gravados
FROM core.carga
WHERE status = 'concluida'
ORDER BY concluida_em DESC
LIMIT 1
"""

# Asked only when there is no successful load, to tell a collection that has
# never been loaded from one whose every load failed. The first is a new
# environment; the second is a broken pipeline, and they are not the same news.
ANY_LOAD_SQL = "SELECT COUNT(*) AS total FROM core.carga"

State = Literal["loaded", "all_loads_failed", "never_loaded"]

# One example per state. A single example would teach a reader that the other
# two do not exist, and they are exactly the cases worth handling.
ANSWERS: dict[str, dict[str, Any]] = {
    "loaded": {
        "summary": "The usual answer: a load finished here and left a date.",
        "value": {
            "state": "loaded",
            "updated_at": "2026-09-18T14:42:03Z",
            "records": 7,
        },
    },
    "all_loads_failed": {
        "summary": "The pipeline ran here and never finished.",
        "value": {"state": "all_loads_failed", "updated_at": None, "records": 0},
    },
    "never_loaded": {
        "summary": "Nothing has been collected here yet.",
        "value": {"state": "never_loaded", "updated_at": None, "records": 0},
    },
}

RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"content": {"application/json": {"examples": ANSWERS}}},
    503: {
        "description": (
            "The load record has not been published to this environment yet, or "
            "the database is not answering. Neither means the request was wrong."
        ),
        "content": {
            "application/json": {
                "examples": {
                    "not published": {"value": {"detail": NOT_PUBLISHED}},
                    "database down": {"value": {"detail": UNAVAILABLE}},
                }
            }
        },
    },
}


class LastUpdate(BaseModel):
    state: State = Field(
        description=(
            "Which of three situations this is. `loaded` means `updated_at` "
            "holds a date. `all_loads_failed` means the pipeline ran here and "
            "never finished — the decisions on this server, if any, are from "
            "before that. `never_loaded` means nothing has been collected here "
            "at all. Read this rather than reading the absence of a date."
        ),
        examples=["loaded"],
    )
    updated_at: datetime | None = Field(
        description=(
            "When the most recent successful load finished, in UTC. `null` "
            "whenever `state` is not `loaded`."
        ),
        examples=["2026-09-18T14:42:03Z"],
    )
    records: int = Field(
        description="How many decisions that load wrote.",
        examples=[7],
    )


def _last_update(connection: Connection[DictRow]) -> LastUpdate:
    """
    Read the freshness once, so two answers cannot tell different stories.

    A failed load left nothing behind, so it cannot be what the data is from.
    Telling a collection never loaded from one whose every load failed costs a
    second question, and only when the first found nothing: one is a new
    environment, the other a broken pipeline.
    """
    with connection.cursor() as cursor:
        cursor.execute(LAST_LOAD_SQL)
        row = cursor.fetchone()

        if row is not None:
            return LastUpdate(
                state="loaded",
                updated_at=row["concluida_em"],
                records=row["registros_gravados"],
            )

        cursor.execute(ANY_LOAD_SQL)
        counted = cursor.fetchone()

    attempted = bool(counted and counted["total"])
    return LastUpdate(
        state="all_loads_failed" if attempted else "never_loaded",
        updated_at=None,
        records=0,
    )


@router.get(
    "/indicators/last-update",
    summary="When the data was last refreshed",
    responses=RESPONSES,
)
def read_last_update(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> LastUpdate:
    """
    When this environment's decisions were last refreshed.

    A reader has to know how old the data is before drawing a conclusion from
    it, so this is read straight from the load record that travelled with the
    data rather than from the machine that answers.
    """
    return _last_update(connection)


# LEFT JOIN, not JOIN: a court the seed never registered would otherwise drop
# out and the sums would stop adding up to the search's total, which is the one
# thing this endpoint promises.
VOLUME_SQL = f"""
SELECT
    d.tribunal_sigla                     AS sigla,
    COALESCE(t.nome, d.tribunal_sigla)   AS nome,
    COUNT(*)                             AS decisoes
FROM core.decisao AS d
LEFT JOIN core.tribunal AS t ON t.sigla = d.tribunal_sigla
WHERE {MATCH}{{filters}}
GROUP BY d.tribunal_sigla, t.nome
ORDER BY COUNT(*) DESC, d.tribunal_sigla
"""


class CourtVolume(BaseModel):
    abbreviation: str = Field(description="The court's abbreviation.", examples=["STJ"])
    name: str = Field(
        description="The court's full name.",
        examples=["Superior Tribunal de Justiça"],
    )
    decisions: int = Field(
        description="How many of the search's decisions came from this court.",
        examples=[876996],
    )


class VolumeByCourt(BaseModel):
    total: int = Field(
        description=(
            "Every decision the same search matches. The courts' counts add up "
            "to it, so a chart drawn from this cannot disagree with the number "
            "beside the results."
        ),
        examples=[984824],
    )
    courts: list[CourtVolume] = Field(
        description="Busiest court first. Empty when the search matches nothing."
    )


@router.get(
    "/indicators/volume-by-court",
    summary="How the search's decisions divide between the courts",
    responses=SEARCH_RESPONSES,
)
def read_volume_by_court(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            description="The same expression the search takes.",
            examples=["dano moral"],
        ),
    ],
    tribunal: Annotated[
        list[str] | None,
        Query(description="The same court filter the search takes."),
    ] = None,
    orgao_julgador: Annotated[
        list[str] | None,
        Query(description="The same judging-body filter the search takes."),
    ] = None,
    relator: Annotated[
        list[str] | None,
        Query(description="The same reporting-judge filter the search takes."),
    ] = None,
    classe_cnj: Annotated[
        list[int] | None,
        Query(
            description="The same repeatable CNJ class filter the search takes.",
            examples=[[198], [198, 213]],
        ),
    ] = None,
    resultado: Annotated[
        list[str] | None,
        Query(
            description=(
                "Exact outcome values recorded by `/indicators/outcome-share`: "
                "`negado`, `provido`, or `parcialmente_provido`. Repeat for OR "
                "within this field; other filters combine using AND. Blank and "
                "repeated values are ignored. Decisions without an outcome do "
                "not match; unknown values return no matches."
            ),
            examples=[["negado"], ["provido", "parcialmente_provido"]],
        ),
    ] = None,
    date_from: Annotated[date | None, Query(description="Judged on or after.")] = None,
    date_to: Annotated[date | None, Query(description="Judged on or before.")] = None,
    published_from: Annotated[
        date | None, Query(description="Published on or after.")
    ] = None,
    published_to: Annotated[
        date | None, Query(description="Published on or before.")
    ] = None,
) -> VolumeByCourt:
    """
    The same decisions the search would return, counted by court.

    It takes the search's parameters and narrows the same way, from the same
    builder, so the chart and the results can never describe different sets. A
    search that matches nothing answers an empty list and a total of zero, not
    an error: no court is the honest answer to a question with no decisions.
    """
    filters, parameters = _narrowing(
        q,
        tribunal,
        date_from,
        date_to,
        published_from,
        published_to,
        orgao_julgador,
        relator,
        classe_cnj,
        resultado,
    )

    with connection.cursor() as cursor:
        cursor.execute(VOLUME_SQL.format(filters=filters), parameters)
        rows = cursor.fetchall()

    courts = [
        CourtVolume(
            abbreviation=row["sigla"], name=row["nome"], decisions=row["decisoes"]
        )
        for row in rows
    ]
    return VolumeByCourt(total=sum(c.decisions for c in courts), courts=courts)


# LEFT JOIN against generate_series so periods without decisions inside the
# interval are not omitted, which would draw false continuity on the chart.
# The bucket unit (month, quarter, or year) adapts to the cut's amplitude unless
# explicitly chosen.
PERIOD_VOLUME_SQL = f"""
WITH bounds AS (
    SELECT
        MIN(d.data_referencia) AS inicio_raw,
        MAX(d.data_referencia) AS fim_raw
    FROM core.decisao AS d
    WHERE {MATCH}{{filters}}
),
config AS (
    SELECT
        CASE
            WHEN %(granularity)s::text IS NOT NULL THEN %(granularity)s::text
            WHEN inicio_raw IS NULL THEN 'month'
            WHEN fim_raw - inicio_raw <= 1096 THEN 'month'
            WHEN fim_raw - inicio_raw <= 3653 THEN 'quarter'
            ELSE 'year'
        END AS step_unit,
        CASE
            WHEN COALESCE(%(granularity)s::text, CASE WHEN fim_raw - inicio_raw <= 1096 THEN 'month' WHEN fim_raw - inicio_raw <= 3653 THEN 'quarter' ELSE 'year' END) = 'year' THEN '1 year'::interval
            WHEN COALESCE(%(granularity)s::text, CASE WHEN fim_raw - inicio_raw <= 1096 THEN 'month' WHEN fim_raw - inicio_raw <= 3653 THEN 'quarter' ELSE 'year' END) = 'quarter' THEN '3 months'::interval
            ELSE '1 month'::interval
        END AS step_interval,
        inicio_raw,
        fim_raw
    FROM bounds
),
contagens AS (
    SELECT
        date_trunc(c.step_unit, d.data_referencia)::date AS periodo,
        COUNT(*) AS decisoes
    FROM core.decisao AS d
    CROSS JOIN config AS c
    WHERE {MATCH}{{filters}}
    GROUP BY c.step_unit, date_trunc(c.step_unit, d.data_referencia)
),
serie AS (
    SELECT
        c.step_unit,
        generate_series(
            date_trunc(c.step_unit, c.inicio_raw)::date,
            date_trunc(c.step_unit, c.fim_raw)::date,
            c.step_interval
        )::date AS periodo
    FROM config AS c
    WHERE c.inicio_raw IS NOT NULL
)
SELECT
    s.step_unit AS granularity,
    s.periodo,
    COALESCE(cnt.decisoes, 0) AS decisoes
FROM serie AS s
LEFT JOIN contagens AS cnt USING (periodo)
ORDER BY s.periodo ASC
"""

Granularity = Literal["month", "quarter", "year"]

INVALID_GRANULARITY = "Granularity must be 'month', 'quarter', or 'year'."

GRANULARITY_ALIASES: dict[str, Granularity] = {
    "month": "month",
    "quarter": "quarter",
    "year": "year",
    "mes": "month",
    "mês": "month",
    "trimestre": "quarter",
    "ano": "year",
}


class PeriodVolume(BaseModel):
    period: date = Field(
        description="The start of the period, as `YYYY-MM-DD`.",
        examples=["2026-03-01"],
    )
    decisions: int = Field(
        description="How many of the search's decisions fell in this period.",
        examples=[120],
    )


class VolumeByPeriod(BaseModel):
    total: int = Field(
        description=(
            "Every decision the same search matches. The periods' counts add up "
            "to it, so a chart drawn from this cannot disagree with the number "
            "beside the results."
        ),
        examples=[984824],
    )
    granularity: Granularity = Field(
        description=(
            "The period bucket used: `month`, `quarter`, or `year`. Chosen "
            "automatically from the span of the cut when omitted."
        ),
        examples=["month"],
    )
    periods: list[PeriodVolume] = Field(
        description=(
            "Chronological order, earliest first. Periods with zero decisions inside "
            "the interval appear with count 0 so continuity is preserved. Empty "
            "when the search matches nothing."
        )
    )


@router.get(
    "/indicators/volume-by-period",
    summary="How the search's decisions divide across time",
    responses=SEARCH_RESPONSES,
)
@router.get(
    "/indicators/volume-over-time",
    include_in_schema=False,
)
def read_volume_by_period(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            description="The same expression the search takes.",
            examples=["dano moral"],
        ),
    ],
    tribunal: Annotated[
        list[str] | None,
        Query(description="The same court filter the search takes."),
    ] = None,
    orgao_julgador: Annotated[
        list[str] | None,
        Query(
            description="The same repeatable judging-body filter the search takes.",
            examples=[["CORTE ESPECIAL"]],
        ),
    ] = None,
    relator: Annotated[
        list[str] | None,
        Query(
            description="The same repeatable reporting-judge filter the search takes.",
            examples=[["ANA CANTARINO"]],
        ),
    ] = None,
    classe_cnj: Annotated[
        list[int] | None,
        Query(
            description="The same repeatable CNJ class filter the search takes.",
            examples=[[198], [198, 213]],
        ),
    ] = None,
    granularity: Annotated[
        str | None,
        Query(
            description=(
                "Bucket size: `month`, `quarter`, or `year`. When omitted, "
                "chosen automatically from the span of the cut: month up to "
                "3 years, quarter up to 10 years, and year beyond."
            ),
            examples=["month", "quarter", "year"],
        ),
    ] = None,
    resultado: Annotated[
        list[str] | None,
        Query(
            description=(
                "Exact outcome values recorded by `/indicators/outcome-share`: "
                "`negado`, `provido`, or `parcialmente_provido`. Repeat for OR "
                "within this field; other filters combine using AND. Blank and "
                "repeated values are ignored. Decisions without an outcome do "
                "not match; unknown values return no matches."
            ),
            examples=[["negado"], ["provido", "parcialmente_provido"]],
        ),
    ] = None,
    date_from: Annotated[date | None, Query(description="Judged on or after.")] = None,
    date_to: Annotated[date | None, Query(description="Judged on or before.")] = None,
    published_from: Annotated[
        date | None, Query(description="Published on or after.")
    ] = None,
    published_to: Annotated[
        date | None, Query(description="Published on or before.")
    ] = None,
) -> VolumeByPeriod:
    """
    The same decisions the search would return, counted by period.

    It takes the search's parameters and narrows the same way, from the same
    builder, so the chart and the results can never describe different sets. A
    search that matches nothing answers an empty list and a total of zero, not
    an error. The bucket size adapts to the cut's amplitude (month for up to 3
    years, quarter for up to 10, year beyond) unless a specific granularity is
    requested. Periods with zero decisions inside the interval are kept with
    count 0 so the timeline preserves visual continuity.
    """
    normalized_granularity: Granularity | None = None
    if granularity is not None:
        cleaned = granularity.strip().lower()
        if cleaned not in GRANULARITY_ALIASES:
            raise HTTPException(status_code=400, detail=INVALID_GRANULARITY)
        normalized_granularity = GRANULARITY_ALIASES[cleaned]

    filters, parameters = _narrowing(
        q,
        tribunal,
        date_from,
        date_to,
        published_from,
        published_to,
        orgao_julgador,
        relator,
        classe_cnj,
        resultado,
    )
    parameters["granularity"] = normalized_granularity

    with connection.cursor() as cursor:
        cursor.execute(PERIOD_VOLUME_SQL.format(filters=filters), parameters)
        rows = cursor.fetchall()

    if not rows:
        return VolumeByPeriod(
            total=0,
            granularity=normalized_granularity or "month",
            periods=[],
        )

    resolved_granularity: Granularity = rows[0]["granularity"]
    periods = [
        PeriodVolume(period=row["periodo"], decisions=row["decisoes"]) for row in rows
    ]
    return VolumeByPeriod(
        total=sum(p.decisions for p in periods),
        granularity=resolved_granularity,
        periods=periods,
    )


OUTCOME_SQL = f"""
SELECT
    d.resultado  AS resultado,
    COUNT(*)     AS decisoes
FROM core.decisao AS d
WHERE {MATCH}{{filters}}
GROUP BY d.resultado
"""

# Zeroed rather than dropped: a category missing from the cut would take its
# slice off the chart, and a reader cannot tell an absent slice from one nobody
# drew.
OUTCOMES = ("negado", "provido", "parcialmente_provido")


class OutcomeCount(BaseModel):
    outcome: str = Field(
        description="The reading, as the model records it.",
        examples=["negado"],
    )
    decisions: int = Field(
        description="How many of the search's decisions were read this way.",
        examples=[752293],
    )
    share: float = Field(
        description=(
            "Percentage over `classified`, not over `total`. Rounded to one "
            "decimal, so the counts are what add up, not these."
        ),
        examples=[75.9],
    )


class OutcomeShare(BaseModel):
    total: int = Field(
        description=(
            "Every decision the same search matches, read or not. The counts "
            "below never add up to it on their own."
        ),
        examples=[1788],
    )
    classified: int = Field(
        description=(
            "How many of them the dispositive stated an outcome for. This is "
            "the denominator of every `share`, and the reason it travels: "
            "a percentage of a part of the cut reads as a percentage of the "
            "cut unless the reader is told otherwise."
        ),
        examples=[1715],
    )
    unclassified: int = Field(
        description=(
            "The rest, which the court decided but not as an appeal on its "
            "merits — a conflict of competence, a prejudiced appeal, an "
            "extinction. `classified` and this add up to `total`."
        ),
        examples=[73],
    )
    outcomes: list[OutcomeCount] = Field(
        description=(
            "Commonest first, and always the three the model can record, zero "
            "included. Empty only when the search matches nothing."
        )
    )


@router.get(
    "/indicators/outcome-share",
    summary="How the search's decisions divide between the appeal outcomes",
    responses=SEARCH_RESPONSES,
)
def read_outcome_share(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
    q: Annotated[
        str,
        Query(
            min_length=2,
            description="The same expression the search takes.",
            examples=["prescrição intercorrente"],
        ),
    ],
    tribunal: Annotated[
        list[str] | None,
        Query(description="The same court filter the search takes."),
    ] = None,
    orgao_julgador: Annotated[
        list[str] | None,
        Query(
            description="The same repeatable judging-body filter the search takes.",
            examples=[["CORTE ESPECIAL"]],
        ),
    ] = None,
    relator: Annotated[
        list[str] | None,
        Query(
            description="The same repeatable reporting-judge filter the search takes.",
            examples=[["ANA CANTARINO"]],
        ),
    ] = None,
    classe_cnj: Annotated[
        list[int] | None,
        Query(
            description="The same repeatable CNJ class filter the search takes.",
            examples=[[198], [198, 213]],
        ),
    ] = None,
    resultado: Annotated[
        list[str] | None,
        Query(
            description=(
                "Exact outcome values recorded by `/indicators/outcome-share`: "
                "`negado`, `provido`, or `parcialmente_provido`. Repeat for OR "
                "within this field; other filters combine using AND. Blank and "
                "repeated values are ignored. Decisions without an outcome do "
                "not match; unknown values return no matches."
            ),
            examples=[["negado"], ["provido", "parcialmente_provido"]],
        ),
    ] = None,
    date_from: Annotated[date | None, Query(description="Judged on or after.")] = None,
    date_to: Annotated[date | None, Query(description="Judged on or before.")] = None,
    published_from: Annotated[
        date | None, Query(description="Published on or after.")
    ] = None,
    published_to: Annotated[
        date | None, Query(description="Published on or before.")
    ] = None,
) -> OutcomeShare:
    """
    The same decisions the search would return, counted by what the court
    decided.

    It narrows from the builder the search itself uses, so the two can never
    describe different sets. A search that matches nothing answers an empty
    list and a total of zero, not an error.
    """
    filters, parameters = _narrowing(
        q,
        tribunal,
        date_from,
        date_to,
        published_from,
        published_to,
        orgao_julgador,
        relator,
        classe_cnj,
        resultado,
    )

    with connection.cursor() as cursor:
        cursor.execute(OUTCOME_SQL.format(filters=filters), parameters)
        rows = cursor.fetchall()

    counted = {row["resultado"]: row["decisoes"] for row in rows}
    total = sum(counted.values())

    if total == 0:
        return OutcomeShare(total=0, classified=0, unclassified=0, outcomes=[])

    unclassified = counted.get(None, 0)
    classified = total - unclassified

    outcomes = [
        OutcomeCount(
            outcome=name,
            decisions=counted.get(name, 0),
            share=round(counted.get(name, 0) / classified * 100, 1)
            if classified
            else 0.0,
        )
        for name in OUTCOMES
    ]
    outcomes.sort(key=lambda item: (-item.decisions, item.outcome))
    return OutcomeShare(
        total=total,
        classified=classified,
        unclassified=unclassified,
        outcomes=outcomes,
    )


# One pass, grouped, so the courts and the base cannot disagree about a period
# the reader is deciding from. NULL dates sort out of MIN and MAX on their own.
COVERAGE_SQL = """
SELECT
    d.tribunal_sigla                     AS sigla,
    COALESCE(t.nome, d.tribunal_sigla)   AS nome,
    COUNT(*)                             AS documentos,
    MIN(d.data_referencia)               AS primeira,
    MAX(d.data_referencia)               AS ultima
FROM core.decisao AS d
LEFT JOIN core.tribunal AS t ON t.sigla = d.tribunal_sigla
GROUP BY d.tribunal_sigla, t.nome
ORDER BY COUNT(*) DESC, d.tribunal_sigla
"""


class CourtCoverage(BaseModel):
    abbreviation: str = Field(description="The court's abbreviation.", examples=["STJ"])
    name: str = Field(
        description="The court's full name.",
        examples=["Superior Tribunal de Justiça"],
    )
    documents: int = Field(
        description="How many decisions the base holds from this court.",
        examples=[876996],
    )
    first: date | None = Field(
        description="The oldest decision from this court. `null` if none is dated.",
        examples=["1989-02-19"],
    )
    last: date | None = Field(
        description="The most recent decision from this court.",
        examples=["2026-08-26"],
    )


class Coverage(BaseModel):
    documents: int = Field(
        description="Every decision the base holds. Zero before the first load.",
        examples=[984824],
    )
    first: date | None = Field(
        description=(
            "The oldest decision in the base. `null` when it holds none. Read it "
            "beside each court's own period: one court reaching back decades "
            "does not mean the base covers those decades for the others."
        ),
        examples=["1989-02-19"],
    )
    last: date | None = Field(
        description="The most recent decision in the base.",
        examples=["2026-09-17"],
    )
    courts: list[CourtCoverage] = Field(
        description="Every court present, largest first, each with its own period."
    )
    state: State = Field(
        description="Whether a load ever finished here. See `/indicators/last-update`.",
        examples=["loaded"],
    )
    updated_at: datetime | None = Field(
        description=(
            "When the data was last refreshed, so the scope above can be read "
            "with its age. `null` when no load ever finished."
        ),
        examples=["2026-09-25T17:12:44Z"],
    )


@router.get(
    "/indicators/coverage",
    summary="What the base covers as a whole",
    responses=RESPONSES,
)
def read_coverage(
    connection: Annotated[Connection[DictRow], Depends(get_connection)],
) -> Coverage:
    """
    How far the base reaches, so a reader knows the scope before trusting it.

    This answers for the collection, not for a search: the volume endpoint
    answers for the set a query matched. An empty base answers zero documents
    and no courts, which is an answer rather than an error — a new environment
    is not a broken one.

    The freshness comes along because scope without age is half an answer, and
    it is read by the same function `/indicators/last-update` uses, so the two
    cannot disagree.
    """
    with connection.cursor() as cursor:
        cursor.execute(COVERAGE_SQL)
        rows = cursor.fetchall()

    courts = [
        CourtCoverage(
            abbreviation=row["sigla"],
            name=row["nome"],
            documents=row["documentos"],
            first=row["primeira"],
            last=row["ultima"],
        )
        for row in rows
    ]
    starts = [c.first for c in courts if c.first is not None]
    ends = [c.last for c in courts if c.last is not None]

    fresh = _last_update(connection)

    return Coverage(
        documents=sum(c.documents for c in courts),
        first=min(starts, default=None),
        last=max(ends, default=None),
        courts=courts,
        state=fresh.state,
        updated_at=fresh.updated_at,
    )
