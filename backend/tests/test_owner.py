"""
The owner's commands, which run on the server and not here.

That is the whole difficulty: the repository is not checked out there, so a
file the command reads has to be one the image carries. These tests read the
Dockerfile and the deployment files to say so, because a path that resolves in
a checkout and nowhere else passes every test that only runs in a checkout.
"""

import re
from pathlib import Path

import psycopg
from psycopg.rows import DictRow

from app import owner

from .conftest import needs_database

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent

SHIPPERS = (
    Path("docker-compose.yml"),
    Path(".github/workflows/deploy-dev.yml"),
    Path(".github/workflows/deploy-producao.yml"),
)

# Built from the schema files themselves, so adding one puts it under the
# same scrutiny without this pattern being edited.
CITATION = re.compile(
    r"[A-Za-z0-9_./-]*(?:"
    + "|".join(re.escape(schema.name) for schema in owner.SCHEMAS)
    + r")"
)


def _copied_into_the_image() -> list[Path]:
    """The directories the Dockerfile puts in the image, as paths here."""
    copied: list[Path] = []

    for line in (BACKEND / "Dockerfile").read_text(encoding="utf-8").splitlines():
        words = line.split()

        if words[:1] == ["COPY"] and not line.startswith("COPY --from"):
            copied.extend(BACKEND / word for word in words[1:-1])

    return copied


def _files_cited_in(text: str) -> set[str]:
    """
    The repository files a deployment file names. Destinations on the server
    and inside containers match the pattern too, and are dropped by the only
    test that tells them apart: whether the path exists here.
    """
    found = {match.lstrip("./") for match in CITATION.findall(text)}
    return {path for path in found if (REPOSITORY / path).is_file()}


def test_the_schema_travels_with_the_code() -> None:
    """
    The file is inside something the Dockerfile copies.

    `migrar` exists to be run in the container, against a database that already
    has data — an environment created before accounts existed, where the init
    script never fires. A schema sitting outside the image makes that command
    fail on the one machine it was written for.
    """
    carried = _copied_into_the_image()

    assert owner.SCHEMAS, "no schema found beside the module"

    for schema in owner.SCHEMAS:
        assert any(schema.is_relative_to(directory) for directory in carried), (
            f"{schema} is not in the image, which carries {carried}"
        )


def test_everything_that_ships_the_schema_points_at_the_same_file() -> None:
    """
    One definition. The compose mounts it as the init script, the deployments
    upload it, and the command applies it — if they can disagree about where it
    is, a database gets one shape and the code assumes another.
    """
    expected = {schema.relative_to(REPOSITORY).as_posix() for schema in owner.SCHEMAS}

    for relative in SHIPPERS:
        cited = _files_cited_in((REPOSITORY / relative).read_text(encoding="utf-8"))

        assert cited == expected, f"{relative} ships {cited or 'nothing'}"


@needs_database
def test_migrate_applies_the_schema_and_may_be_run_again(
    db: psycopg.Connection[DictRow],
) -> None:
    """
    Idempotent, because the owner runs it on a database that may already hold
    accounts and must not be made to check first.
    """
    owner.migrate(db)
    owner.migrate(db)

    with db.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(DISTINCT table_schema) AS schemas "
            "FROM information_schema.tables "
            "WHERE table_schema IN ('identidade', 'leitura')"
        )
        found = cursor.fetchone()

    assert found is not None
    assert found["schemas"] == len(owner.SCHEMAS)
