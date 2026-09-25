"""
Checks that the link each decision carries still reaches a document.

Runs at load time, never inside a search request. The search reads what this
wrote, so a court portal that is down slows nothing down and takes nothing off
the screen — the record simply stays unverified until the next run.
"""

import os
import sys
from typing import Any

import psycopg2

from datetime import date

from sources.tjdft import (
    REQUEST_INTERVAL,
    _Pacer,
    _windows,
    document_exists,
    identifiers_between,
)

SCHEMA = "verificacao"
TABLE = f"{SCHEMA}.link"

CREATE = f"""
CREATE SCHEMA IF NOT EXISTS {SCHEMA};
CREATE TABLE IF NOT EXISTS {TABLE} (
    identificador TEXT        PRIMARY KEY,
    valido        BOOLEAN     NOT NULL,
    verificado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# A record with no row here is unverified, which is not the same as invalid.
PENDING = f"""
SELECT d.identificador_fonte
FROM core.decisao AS d
LEFT JOIN {TABLE} AS v ON v.identificador = d.identificador_fonte
WHERE v.identificador IS NULL
ORDER BY d.data_referencia DESC
LIMIT %(limit)s
"""

RECORD = f"""
INSERT INTO {TABLE} (identificador, valido, verificado_em)
VALUES (%(identificador)s, %(valido)s, NOW())
ON CONFLICT (identificador) DO UPDATE
SET valido = EXCLUDED.valido, verificado_em = EXCLUDED.verificado_em
"""

# Stops a run that is only producing failures: a portal that is down would
# otherwise be asked once per remaining record.
MAX_CONSECUTIVE_FAILURES = 10

SPAN = """
SELECT MIN(data_julgamento) AS first, MAX(data_julgamento) AS last
FROM core.decisao
WHERE data_julgamento IS NOT NULL
"""

IN_WINDOW = """
SELECT identificador_fonte
FROM core.decisao
WHERE data_julgamento BETWEEN %(first)s AND %(last)s
"""


def _connection() -> Any:
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "caselaw"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def _limit() -> int:
    value = os.getenv("VERIFY_MAX", "").strip()
    return int(value) if value else 1000


def _interval() -> float:
    value = os.getenv("VERIFY_INTERVAL", "").strip()
    return float(value) if value else REQUEST_INTERVAL


def verify() -> int:
    pacer = _Pacer(_interval())
    checked = invalid = failed = 0
    consecutive = 0

    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE)
            cursor.execute(PENDING, {"limit": _limit()})
            pending = [row[0] for row in cursor.fetchall()]

        print(f"{len(pending)} to verify", flush=True)

        for identificador in pending:
            pacer.wait()
            try:
                exists = document_exists(identificador)
            except Exception as error:  # noqa: BLE001 — any failure is "unknown"
                failed += 1
                consecutive += 1
                if consecutive >= MAX_CONSECUTIVE_FAILURES:
                    print(f"  stopping: {consecutive} failures in a row", flush=True)
                    print(f"  last one: {error}", flush=True)
                    break
                continue

            consecutive = 0
            checked += 1
            invalid += not exists

            with connection.cursor() as cursor:
                cursor.execute(
                    RECORD, {"identificador": identificador, "valido": exists}
                )
            connection.commit()

    print(f"verified {checked}, invalid {invalid}, unreachable {failed}", flush=True)
    return invalid


def sweep() -> int:
    """
    The same answer as `verify`, in a fraction of the requests.

    Reading a window costs one request per forty documents, so the collection
    is listed for about 2.700 requests instead of 107.828. What the listing
    does not carry is a candidate, not a verdict: a corrected judgement date
    moves a record out of the window it was collected in, so each absence is
    confirmed one by one before being written down as broken.
    """
    pacer = _Pacer(_interval())
    checked = invalid = 0

    with _connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE)
            cursor.execute(SPAN)
            span = cursor.fetchone()

        if span is None or span[0] is None:
            print("nothing loaded", flush=True)
            return 0

        first, last = span
        janelas = list(_windows(first, last, "month"))
        print(f"{first} to {last}, {len(janelas)} windows", flush=True)

        for inicio, fim in janelas:
            listed = identifiers_between(inicio, fim, _interval())

            with connection.cursor() as cursor:
                cursor.execute(IN_WINDOW, {"first": inicio, "last": fim})
                ours = [row[0] for row in cursor.fetchall()]

            missing = [i for i in ours if i not in listed]
            print(
                f"  {inicio:%Y-%m}  listed {len(listed):>5}  ours {len(ours):>5}"
                f"  to confirm {len(missing)}",
                flush=True,
            )

            for identificador in ours:
                if identificador in listed:
                    valido = True
                else:
                    pacer.wait()
                    try:
                        valido = document_exists(identificador)
                    except Exception:  # noqa: BLE001
                        continue

                checked += 1
                invalid += not valido
                with connection.cursor() as cursor:
                    cursor.execute(
                        RECORD, {"identificador": identificador, "valido": valido}
                    )
            connection.commit()

    print(f"verified {checked}, invalid {invalid}", flush=True)
    return invalid


def main() -> None:
    modo = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    try:
        sweep() if modo == "sweep" else verify()
    except KeyboardInterrupt:
        print("\ninterrupted — what was verified is already recorded", flush=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
