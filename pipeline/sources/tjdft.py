import calendar
import os
import time
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import dlt
from dlt.destinations.exceptions import DatabaseUndefinedRelation
from dlt.sources.helpers import requests

SEARCH_URL = "https://jurisdf.tjdft.jus.br/api/v1/pesquisa"
COLLECTION = "acordaos"
PAGE_SIZE = 40
REQUEST_TIMEOUT = 90
REQUEST_INTERVAL = 0.5

DROPPED_FIELDS = ("marcadores",)
DROPPED_NESTED_FIELDS = {"jurisprudenciaEmFoco": ("conteudo",)}

dlt.config["schema.naming"] = "direct"


def _search_terms(start: date | None, end: date | None) -> list[dict[str, str]]:
    terms = [{"campo": "base", "valor": COLLECTION}]
    if start and end:
        terms.append({"campo": "dataJulgamento", "valor": f"entre {start} e {end}"})
    return terms


def _payload(
    terms: list[dict[str, str]],
    page: int,
    subject: str = "",
) -> dict[str, Any]:
    return {
        "query": subject,
        "termosAcessorios": terms,
        "pagina": page,
        "tamanho": PAGE_SIZE,
        "sinonimos": False,
        "espelho": False,
        "inteiroTeor": False,
        "retornaInteiroTeor": False,
        "retornaTotalizacao": False,
    }


def _clean(record: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: value for key, value in record.items() if key not in DROPPED_FIELDS}

    for field, inner_fields in DROPPED_NESTED_FIELDS.items():
        entries = cleaned.get(field)
        if not isinstance(entries, list):
            continue
        cleaned[field] = [
            {key: value for key, value in entry.items() if key not in inner_fields}
            for entry in entries
            if isinstance(entry, dict)
        ]

    return cleaned


class _Pacer:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self.last_call
        if self.last_call and elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.monotonic()


@dlt.resource(
    name="acordao_tjdft",
    write_disposition="merge",
    primary_key="identificador",
)
def acordaos(
    start: date | None = None,
    end: date | None = None,
    subject: str = "",
    max_pages: int | None = None,
    interval: float = REQUEST_INTERVAL,
) -> Iterator[list[dict[str, Any]]]:
    terms = _search_terms(start, end)
    pacer = _Pacer(interval)
    page = 0

    while max_pages is None or page < max_pages:
        pacer.wait()
        response = requests.post(
            SEARCH_URL,
            json=_payload(terms, page, subject),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        records = response.json().get("registros") or []

        if not records:
            return

        yield [_clean(record) for record in records]
        page += 1


def total_available(
    start: date | None = None,
    end: date | None = None,
    subject: str = "",
) -> int:
    response = requests.post(
        SEARCH_URL,
        json={**_payload(_search_terms(start, end), 0, subject), "tamanho": 1},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return int(response.json()["hits"]["value"])


def document_exists(identificador: str) -> bool:
    """
    Whether the source still holds this document.

    The portal page cannot answer this: `detalhes/{id}` is a single-page
    application that returns the same 200 and the same 62.758 bytes for a real
    identifier and for an invented one, because the document arrives later over
    this very API. So the check asks the API, by the identifier the link is
    built from.

    Raises whatever the request raised. The caller decides what an unreachable
    portal means; here it is not an answer of "invalid".
    """
    terms = [
        {"campo": "base", "valor": COLLECTION},
        {"campo": "identificador", "valor": identificador},
    ]
    response = requests.post(
        SEARCH_URL,
        json={**_payload(terms, 0, ""), "tamanho": 1},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    records = response.json().get("registros") or []
    return any(str(r.get("identificador")) == str(identificador) for r in records)


def _date_from_env(name: str) -> date | None:
    value = os.getenv(name, "").strip()
    return date.fromisoformat(value) if value else None


def _int_from_env(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    return int(value) if value else None


def _float_from_env(name: str, default: float) -> float:
    value = os.getenv(name, "").strip()
    return float(value) if value else default


def _windows(
    start: date,
    end: date,
    granularity: str,
) -> Iterator[tuple[date, date]]:
    cursor = start
    while cursor <= end:
        if granularity == "day":
            last = cursor
        else:
            days = calendar.monthrange(cursor.year, cursor.month)[1]
            last = cursor.replace(day=days)
        yield cursor, min(last, end)
        cursor = min(last, end) + timedelta(days=1)


def _already_loaded(pipeline: dlt.Pipeline, first: date, last: date) -> int:
    statement = (
        "SELECT COUNT(*) FROM raw.acordao_tjdft "
        'WHERE "dataJulgamento"::date BETWEEN %s AND %s'
    )
    try:
        with (
            pipeline.sql_client() as client,
            client.execute_query(statement, first, last) as rows,
        ):
            found = rows.fetchone()
            return int(found[0]) if found else 0
    except DatabaseUndefinedRelation:
        return 0


def run() -> None:
    start = _date_from_env("TJDFT_START_DATE")
    end = _date_from_env("TJDFT_END_DATE")
    subject = os.getenv("TJDFT_SUBJECT", "").strip()
    max_pages = _int_from_env("TJDFT_MAX_PAGES")
    interval = _float_from_env("TJDFT_REQUEST_INTERVAL", REQUEST_INTERVAL)
    granularity = os.getenv("TJDFT_WINDOW", "month").strip() or "month"

    pipeline = dlt.pipeline(
        pipeline_name="case_law",
        destination="postgres",
        dataset_name="raw",
    )

    if not (start and end):
        print(f"available at the source: {total_available(start, end, subject)}")
        print(
            pipeline.run(
                acordaos(
                    start=start,
                    end=end,
                    subject=subject,
                    max_pages=max_pages,
                    interval=interval,
                )
            )
        )
        return

    collected = 0
    skipped = 0
    failures: list[tuple[str, str]] = []

    for first, last in _windows(start, end, granularity):
        label = f"{first}..{last}"
        available = total_available(first, last, subject)
        loaded = _already_loaded(pipeline, first, last)

        if loaded >= available:
            skipped += 1
            continue

        print(f"{label}  {loaded}/{available} loaded, fetching", flush=True)
        try:
            pipeline.run(
                acordaos(
                    start=first,
                    end=last,
                    subject=subject,
                    max_pages=max_pages,
                    interval=interval,
                )
            )
        except Exception as error:  # noqa: BLE001
            print(f"{label}  FAILED: {error}", flush=True)
            failures.append((label, str(error)))
            continue

        now_loaded = _already_loaded(pipeline, first, last)
        collected += now_loaded - loaded
        print(f"{label}  now {now_loaded}/{available}", flush=True)

    print(f"\ncollected {collected} new records, {skipped} windows already complete")
    if failures:
        print(f"{len(failures)} windows failed and can be retried by running again:")
        for label, error in failures:
            print(f"  {label}: {error[:120]}")
        raise SystemExit(1)


if __name__ == "__main__":
    run()
