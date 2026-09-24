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

from sources.tjdft import REQUEST_INTERVAL, _Pacer, document_exists

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


def main() -> None:
    try:
        verify()
    except KeyboardInterrupt:
        print("\ninterrupted — what was verified is already recorded", flush=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
