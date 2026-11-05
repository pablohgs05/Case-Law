"""
A database created from nothing comes up with what the project needs.

The scripts mounted in `/docker-entrypoint-initdb.d/` only run when the data
directory is empty, so a broken one never shows on a machine that already has
the volume: only to whoever clones the project, or runs `docker compose down -v`.
These tests read the mounts from `docker-compose.yml` itself and replay them,
in the order the entrypoint runs them, on a database created for the purpose.
"""

import uuid
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

import psycopg
import pytest
import yaml

from tests.conftest import TEST_DATABASE_URL, needs_database

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "docker-compose.yml"
INITDB = PurePosixPath("/docker-entrypoint-initdb.d")


def _init_scripts() -> list[tuple[str, Path]]:
    """
    Every file the compose mounts into the initdb directory, as (name, source).

    Sorted by the name inside the container, because that is the order the
    entrypoint runs them in — not the order they are written in the compose.
    """
    written = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    scripts = []
    for volume in written["services"]["postgres"]["volumes"]:
        source, _, rest = volume.partition(":")
        target = PurePosixPath(rest.split(":")[0])
        if target.parent == INITDB:
            scripts.append((target.name, (ROOT / source).resolve()))
    return sorted(scripts)


def test_the_compose_mounts_the_extensions_script() -> None:
    """Guards the tests below: a parse that finds nothing asserts nothing."""
    sources = [source for _, source in _init_scripts()]

    assert ROOT / "infra" / "postgres" / "init.sql" in sources


def test_every_mounted_init_script_exists() -> None:
    """
    A source path that does not exist is not an error to Docker: it creates an
    empty directory in its place, and the entrypoint skips it without a word.
    """
    for name, source in _init_scripts():
        assert source.is_file(), f"{name} is mounted from {source}, not a file"


@pytest.fixture
def fresh_database() -> Iterator[str]:
    """An empty database on the test server, dropped afterwards."""
    name = f"caselaw_initdb_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
        admin.execute(f'CREATE DATABASE "{name}" TEMPLATE template0')
    try:
        yield psycopg.conninfo.make_conninfo(TEST_DATABASE_URL, dbname=name)
    finally:
        with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as admin:
            admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@needs_database
def test_a_fresh_database_runs_every_init_script(fresh_database: str) -> None:
    with psycopg.connect(fresh_database, autocommit=True) as conn:
        for name, source in _init_scripts():
            try:
                conn.execute(source.read_text(encoding="utf-8"))
            except psycopg.Error as error:
                pytest.fail(f"{name} fails on a fresh database: {error}")


@needs_database
def test_a_fresh_database_has_what_the_application_reads(
    fresh_database: str,
) -> None:
    with psycopg.connect(fresh_database, autocommit=True) as conn:
        for _, source in _init_scripts():
            conn.execute(source.read_text(encoding="utf-8"))

        extensions = {
            row[0] for row in conn.execute("SELECT extname FROM pg_extension")
        }
        schemas = {row[0] for row in conn.execute("SELECT nspname FROM pg_namespace")}
        folded = conn.execute(
            "SELECT TO_TSVECTOR('portugues_sem_acento', 'ação')"
            " = TO_TSVECTOR('portugues_sem_acento', 'acao')"
        ).fetchone()

    assert {"pg_trgm", "unaccent", "vector"} <= extensions
    assert {"verificacao", "identidade"} <= schemas
    assert folded == (True,)
