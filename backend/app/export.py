"""Collect the complete cut before a document renderer is invoked."""

from datetime import date
from typing import Any, NamedTuple

from psycopg import Connection
from psycopg.pq import TransactionStatus
from psycopg.rows import DictRow

from app.api.decisions import (
    DEFAULT_ORDER,
    MATCH,
    ORDERINGS,
    SNIPPET,
    SNIPPET_OPTIONS,
    Order,
    _count_sql,
    _narrowing,
)
from app.export_indicators import ExportIndicators, collect_export_indicators


class ExportRefused(ValueError):
    code = "empty"
    total = 0

    def __init__(self) -> None:
        super().__init__("There are no decisions to export.")


class ExportDataset(NamedTuple):
    total: int
    order: Order
    decisions: list[DictRow]
    query: str
    filters: dict[str, Any]
    indicators: ExportIndicators


def collect_export(
    connection: Connection[DictRow],
    q: str,
    *,
    tribunal: list[str] | None = None,
    orgao_julgador: list[str] | None = None,
    relator: list[str] | None = None,
    classe_cnj: list[int] | None = None,
    resultado: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    published_from: date | None = None,
    published_to: date | None = None,
    order: Order = DEFAULT_ORDER,
) -> ExportDataset:
    """Count, refuse if necessary, then fetch every reference in screen order.

    Own a read-only repeatable snapshot when passed an idle pooled connection.
    A caller-owned transaction must already use repeatable read or serializable:
    a savepoint alone cannot prevent count/list disagreement under read committed.
    No renderer or HTTP endpoint is introduced by this collection step.
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
    ordering = ORDERINGS[order]
    idle = connection.info.transaction_status == TransactionStatus.IDLE
    with connection.transaction():
        if idle:
            connection.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            )
        else:
            isolation = connection.execute("SHOW transaction_isolation").fetchone()
            if isolation is None or isolation["transaction_isolation"] not in {
                "repeatable read",
                "serializable",
            }:
                raise ValueError(
                    "Export collection needs an idle connection or a repeatable snapshot."
                )

        counted = connection.execute(_count_sql(filters), parameters).fetchone()
        assert counted is not None
        total = int(counted["total"])
        if total == 0:
            raise ExportRefused()

        # Expensive rank and excerpt generation run only after accepting the
        # count. The excerpt is the same ts_headline used by the search cards.
        rows = connection.execute(
            f"""SELECT fonte_codigo, identificador_fonte, tribunal_sigla, processo,
                orgao_julgador, relator, classe_cnj, data_referencia,
                data_julgamento, data_publicacao, resultado, deliberacao,
                url_fonte, link_valido, {SNIPPET} AS snippet
            FROM core.decisao WHERE {MATCH}{filters}
            {ordering}""",
            {**parameters, "snippet_options": SNIPPET_OPTIONS, "highlight": q},
        ).fetchall()
        indicators = collect_export_indicators(
            connection, q, parameters, rows, filters_sql=filters
        )
    return ExportDataset(
        total=total,
        order=order,
        decisions=rows,
        query=q,
        filters={key: value for key, value in parameters.items() if key != "term"},
        indicators=indicators,
    )
