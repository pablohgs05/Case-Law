import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

STAGING_SCHEMA = "core_publicacao"
PUBLISHED_SCHEMA = "core"

ROOT = Path(__file__).resolve().parent.parent

# Written by hand, and that is the trap: `stage` copies these names and
# nothing else, so a table a model creates stays invisible in dev and
# production until it is added here. core.precedente and core.doutrina were
# both ready in the code and absent from the environments for exactly that
# reason.
TABLES = (
    "tribunal",
    "fonte",
    "classe_processual",
    "carga",
    "decisao",
    "precedente",
    "decisao_precedente",
    "doutrina",
    "doutrina_termo",
    "decisao_doutrina",
)

INDEXES = (
    (
        f"CREATE UNIQUE INDEX ON {STAGING_SCHEMA}.decisao "
        "(fonte_codigo, identificador_fonte)"
    ),
    f"CREATE INDEX ON {STAGING_SCHEMA}.decisao USING gin (ementa_busca)",
    (
        f"CREATE INDEX ON {STAGING_SCHEMA}.decisao "
        "(data_referencia DESC, fonte_codigo, identificador_fonte)"
    ),
    f"CREATE INDEX ON {STAGING_SCHEMA}.decisao (tribunal_sigla, data_referencia DESC)",
    f"CREATE INDEX ON {STAGING_SCHEMA}.decisao (tribunal_sigla, orgao_julgador)",
    f"CREATE INDEX ON {STAGING_SCHEMA}.decisao (tribunal_sigla, relator)",
    f"CREATE INDEX ON {STAGING_SCHEMA}.decisao (processo)",
    f"CREATE INDEX ON {STAGING_SCHEMA}.decisao (classe_cnj)",
    # The copy is a plain SELECT, so no index comes with it. These mirror what
    # the models declare: without them the detail screen reads 28 thousand
    # suggestions sequentially on every decision opened.
    f"CREATE UNIQUE INDEX ON {STAGING_SCHEMA}.precedente (corte, tipo, numero)",
    f"CREATE INDEX ON {STAGING_SCHEMA}.precedente (tipo, numero)",
    (
        f"CREATE UNIQUE INDEX ON {STAGING_SCHEMA}.decisao_precedente "
        "(fonte_codigo, identificador_fonte, corte, tipo, numero)"
    ),
    f"CREATE INDEX ON {STAGING_SCHEMA}.decisao_precedente (corte, tipo, numero)",
    f"CREATE INDEX ON {STAGING_SCHEMA}.decisao_precedente (resolvida)",
    (
        f"CREATE UNIQUE INDEX ON {STAGING_SCHEMA}.doutrina "
        "(repositorio, identificador_oai)"
    ),
    f"CREATE INDEX ON {STAGING_SCHEMA}.doutrina USING gin (busca)",
    f"CREATE INDEX ON {STAGING_SCHEMA}.doutrina (ano)",
    (
        f"CREATE UNIQUE INDEX ON {STAGING_SCHEMA}.doutrina_termo "
        "(repositorio, identificador_oai, termo)"
    ),
    f"CREATE INDEX ON {STAGING_SCHEMA}.doutrina_termo (termo)",
    (
        f"CREATE UNIQUE INDEX ON {STAGING_SCHEMA}.decisao_doutrina "
        "(fonte_codigo, identificador_fonte, repositorio, identificador_oai)"
    ),
    (
        f"CREATE INDEX ON {STAGING_SCHEMA}.decisao_doutrina "
        "(fonte_codigo, identificador_fonte, nota DESC)"
    ),
    f"CREATE INDEX ON {STAGING_SCHEMA}.decisao_doutrina (repositorio, identificador_oai)",
)

SEARCH_CONFIGURATION = """
CREATE EXTENSION IF NOT EXISTS unaccent;
DO $do$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'portugues_sem_acento')
    THEN
        CREATE TEXT SEARCH CONFIGURATION portugues_sem_acento ( COPY = portuguese );
        ALTER TEXT SEARCH CONFIGURATION portugues_sem_acento
          ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;
    END IF;
END $do$;
"""

SWAP = f"""
BEGIN;
DROP SCHEMA IF EXISTS {PUBLISHED_SCHEMA} CASCADE;
ALTER SCHEMA {STAGING_SCHEMA} RENAME TO {PUBLISHED_SCHEMA};
COMMIT;
"""

RECORD = """
CREATE SCHEMA IF NOT EXISTS meta;
CREATE TABLE IF NOT EXISTS meta.publicacao (
    publicada_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decisoes     BIGINT      NOT NULL,
    origem       TEXT        NOT NULL
);
INSERT INTO meta.publicacao (decisoes, origem)
SELECT COUNT(*), :'origem' FROM core.decisao;
"""


@dataclass(frozen=True)
class Target:
    name: str
    host: str
    user: str
    container: str
    database: str

    @property
    def address(self) -> str:
        return f"{self.user}@{self.host}"


def _target(name: str) -> Target:
    prefix = f"PUBLISH_{name.upper()}"
    values = {
        key: os.getenv(f"{prefix}_{key}", "").strip()
        for key in ("HOST", "USER", "CONTAINER")
    }
    missing = [f"{prefix}_{key}" for key, value in values.items() if not value]
    if missing:
        raise SystemExit(f"missing environment: {', '.join(missing)}")

    return Target(
        name=name,
        host=values["HOST"],
        user=values["USER"],
        container=values["CONTAINER"],
        database=os.getenv(f"{prefix}_DB", "caselaw").strip() or "caselaw",
    )


def _local_psql(arguments: list[str]) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "postgres",
            "-d",
            "caselaw",
            "-v",
            "ON_ERROR_STOP=1",
            *arguments,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _remote_psql(target: Target, statement: str, arguments: list[str]) -> None:
    subprocess.run(
        [
            "ssh",
            target.address,
            "docker",
            "exec",
            "-i",
            target.container,
            "psql",
            "-U",
            "caselaw",
            "-d",
            target.database,
            "-v",
            "ON_ERROR_STOP=1",
            *arguments,
            "-f",
            "-",
        ],
        input=statement.encode("utf-8"),
        check=True,
    )


def stage() -> int:
    _local_psql(["-c", f"DROP SCHEMA IF EXISTS {STAGING_SCHEMA} CASCADE"])
    _local_psql(["-c", f"CREATE SCHEMA {STAGING_SCHEMA}"])

    for table in TABLES:
        _local_psql(
            [
                "-c",
                (
                    f"CREATE TABLE {STAGING_SCHEMA}.{table} AS "
                    f"SELECT * FROM {PUBLISHED_SCHEMA}.{table}"
                ),
            ]
        )

    for statement in INDEXES:
        _local_psql(["-c", statement])

    _local_psql(["-c", f"ANALYZE {STAGING_SCHEMA}.decisao"])

    return int(
        _local_psql(["-tA", "-c", f"SELECT COUNT(*) FROM {STAGING_SCHEMA}.decisao"])
    )


def transfer(target: Target) -> None:
    dump = subprocess.Popen(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            "postgres",
            "-d",
            "caselaw",
            "--schema",
            STAGING_SCHEMA,
            "--no-owner",
            "--no-privileges",
            "--format",
            "custom",
            "--compress",
            "6",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
    )

    restore = subprocess.Popen(
        [
            "ssh",
            target.address,
            "docker",
            "exec",
            "-i",
            target.container,
            "pg_restore",
            "-U",
            "caselaw",
            "-d",
            target.database,
            "--no-owner",
            "--no-privileges",
            "--clean",
            "--if-exists",
        ],
        stdin=dump.stdout,
    )

    if dump.stdout:
        dump.stdout.close()
    restore.communicate()

    if dump.wait() != 0:
        raise SystemExit("the dump failed")
    if restore.returncode != 0:
        raise SystemExit("the restore failed")


def publish(name: str) -> None:
    target = _target(name)

    print(f"staging {PUBLISHED_SCHEMA} as real tables", flush=True)
    decisions = stage()
    print(f"  {decisions} decisions ready", flush=True)

    print(f"preparing {target.name}", flush=True)
    _remote_psql(target, SEARCH_CONFIGURATION, [])

    print(f"transferring to {target.name}", flush=True)
    transfer(target)

    print("swapping the schema", flush=True)
    _remote_psql(target, SWAP, [])
    _remote_psql(target, RECORD, ["-v", f"origem={os.uname().nodename}"])

    _local_psql(["-c", f"DROP SCHEMA IF EXISTS {STAGING_SCHEMA} CASCADE"])
    print(f"published {decisions} decisions to {target.name}\n", flush=True)


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m publish <dev|producao> [...]")
    for name in sys.argv[1:]:
        publish(name)


if __name__ == "__main__":
    main()
