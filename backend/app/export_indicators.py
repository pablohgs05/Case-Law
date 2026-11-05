"""Read panel indicators and their context in the export's existing snapshot."""

from datetime import date
from typing import Any, NamedTuple

from psycopg import Connection
from psycopg.rows import DictRow

from app.api.decisions import MATCH
from app.api.indicators import (
    OutcomeShare,
    VolumeByCourt,
    VolumeByPeriod,
    read_outcome_share,
    read_volume_by_court,
    read_volume_by_period,
)


class ExportCourtCoverage(NamedTuple):
    court: str
    documents: int
    first: date | None
    last: date | None
    with_class: int


class ExportIndicators(NamedTuple):
    courts: VolumeByCourt
    timeline: VolumeByPeriod
    outcomes: OutcomeShare
    coverage: list[ExportCourtCoverage]
    with_class: int
    with_knowledge: int | None = None


def collect_export_indicators(
    connection: Connection[DictRow],
    query: str,
    parameters: dict[str, Any],
    decisions: list[DictRow],
    *,
    filters_sql: str,
) -> ExportIndicators:
    # These functions are the panel's actual calculations, called directly,
    # without HTTP or a new connection that could see another publication.
    applied = {
        "q": query,
        **{
            "tribunal" if key == "tribunais" else key: value
            for key, value in parameters.items()
            if key != "term"
        },
    }
    courts = read_volume_by_court(connection, **applied)
    timeline = read_volume_by_period(connection, **applied)
    outcomes = read_outcome_share(connection, **applied)
    # Include selected courts even when absent from the matches. Without a
    # court restriction, show the whole base's windows: a zero in an old cut
    # must not hide that another court's collection only starts years later.
    court_filter = (
        "WHERE tribunal_sigla = ANY(%(courts)s)" if parameters.get("tribunais") else ""
    )
    rows = connection.execute(
        f"""SELECT tribunal_sigla, COUNT(*) AS documents,
            MIN(data_referencia) AS first, MAX(data_referencia) AS last,
            COUNT(classe_cnj) AS with_class
        FROM core.decisao {court_filter}
        GROUP BY tribunal_sigla ORDER BY tribunal_sigla""",
        {"courts": parameters.get("tribunais")},
    ).fetchall()
    coverage = [
        ExportCourtCoverage(
            court=row["tribunal_sigla"],
            documents=row["documents"],
            first=row["first"],
            last=row["last"],
            with_class=row["with_class"],
        )
        for row in rows
    ]
    # Some publications predate this optional classification. Distinguish
    # unavailable metadata from a measured zero instead of quoting old ratios.
    knowledge_column = connection.execute(
        """SELECT EXISTS (
            SELECT 1 FROM pg_attribute
            WHERE attrelid = 'core.decisao'::regclass
                AND attname = 'conhecimento' AND NOT attisdropped
        ) AS available"""
    ).fetchone()
    with_knowledge = None
    if knowledge_column is not None and knowledge_column["available"]:
        knowledge = connection.execute(
            f"""SELECT COUNT(NULLIF(BTRIM(conhecimento), '')) AS classified
            FROM core.decisao WHERE {MATCH}{filters_sql}""",
            parameters,
        ).fetchone()
        assert knowledge is not None
        with_knowledge = int(knowledge["classified"])
    return ExportIndicators(
        courts=courts,
        timeline=timeline,
        outcomes=outcomes,
        coverage=coverage,
        with_class=sum(row["classe_cnj"] is not None for row in decisions),
        with_knowledge=with_knowledge,
    )
