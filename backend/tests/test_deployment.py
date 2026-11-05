"""
What the deployed environments hand the API.

`session_secret_or_fail` falls back to a known default while developing, and
the development server is a `development` environment — so on that machine the
refusal never fires and the fallback is what signs the tokens. The default is
in a public repository. These tests read the deployment files and insist that
no environment reaches the API without a secret of its own.
"""

import os
import re
import subprocess
from pathlib import Path

import yaml

from app.config import DEVELOPMENT_SECRET

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"

COMPOSES = sorted(DEPLOY.glob("docker-compose.*.yml"))


def _backend_environment(compose: Path) -> dict[str, str]:
    written = yaml.safe_load(compose.read_text(encoding="utf-8"))
    return written["services"]["backend"]["environment"]


def test_there_is_a_compose_for_each_environment() -> None:
    """Guards the tests below: a glob that matches nothing asserts nothing."""
    assert {compose.name for compose in COMPOSES} == {
        "docker-compose.dev.yml",
        "docker-compose.prod.yml",
    }


def test_every_deployed_environment_is_handed_a_session_secret() -> None:
    for compose in COMPOSES:
        assert "SESSION_SECRET" in _backend_environment(compose), compose.name


def test_a_missing_secret_stops_the_release_instead_of_defaulting() -> None:
    """
    `${SESSION_SECRET:?...}` refuses to start the container. A default would
    hand every environment the same key, which is the thing being prevented —
    and `:-` is one character away from `:?`.
    """
    for compose in COMPOSES:
        written = _backend_environment(compose)["SESSION_SECRET"]

        assert re.fullmatch(r"\$\{SESSION_SECRET:\?.+\}", written), (
            f"{compose.name} accepts a missing secret: {written}"
        )


def _env_after_release(tmp_path: Path, existing: str | None) -> str:
    """
    Run the part of `release.sh` that prepares the environment file, with the
    machine's own commands stubbed. Reading the script would only say that the
    words are in it; running it says what the server ends up holding.
    """
    script = (DEPLOY / "release.sh").read_text(encoding="utf-8")
    prepares = script[: script.index("set -a")]

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "tailscale").write_text("#!/bin/sh\necho 100.0.0.1\n", encoding="utf-8")
    (bin_dir / "tailscale").chmod(0o755)

    work = tmp_path / "deploy"
    work.mkdir()
    (work / "release.sh").write_text(prepares, encoding="utf-8")

    if existing is not None:
        (work / ".env").write_text(existing, encoding="utf-8")

    subprocess.run(
        ["bash", str(work / "release.sh")],
        check=True,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )

    return (work / ".env").read_text(encoding="utf-8")


def _secret_in(env_file: str) -> str:
    written = dict(line.split("=", 1) for line in env_file.splitlines() if "=" in line)
    return written.get("SESSION_SECRET", "")


def test_a_new_server_is_given_a_secret(tmp_path: Path) -> None:
    secret = _secret_in(_env_after_release(tmp_path, existing=None))

    assert len(secret) >= 32
    assert secret != DEVELOPMENT_SECRET


def test_a_server_deployed_before_accounts_is_given_one_too(tmp_path: Path) -> None:
    """
    The environments already running were created before accounts existed, so
    their file has no secret in it. Without this the upgrade would stop at the
    compose check instead of starting.
    """
    before = "POSTGRES_PASSWORD=kept\nBACKEND_BIND=100.0.0.1\nFRONTEND_BIND=100.0.0.1\n"

    after = _env_after_release(tmp_path, existing=before)

    assert len(_secret_in(after)) >= 32
    assert "POSTGRES_PASSWORD=kept" in after


def test_the_secret_is_not_minted_twice(tmp_path: Path) -> None:
    """
    A second release must not replace it: a new key invalidates every token in
    flight, signing everyone out on a deployment that changed nothing for them.
    """
    before = "POSTGRES_PASSWORD=kept\nSESSION_SECRET=ja-existe\nBACKEND_BIND=100.0.0.1\nFRONTEND_BIND=100.0.0.1\n"

    assert _secret_in(_env_after_release(tmp_path, existing=before)) == "ja-existe"


def test_no_deployment_file_carries_the_development_secret() -> None:
    for path in sorted(DEPLOY.iterdir()):
        if path.is_file():
            assert DEVELOPMENT_SECRET not in path.read_text(encoding="utf-8"), path.name
