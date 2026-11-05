from typing import Any

import pytest

from app.config import Settings


def configured(**environment: Any) -> Settings:
    """
    Settings as this code defines them, with no `.env` underneath.

    `Settings()` reads one when it is there, so a developer who keeps a
    local `.env` — which is how the project is meant to be run — would see
    these tests fail over their own configuration. CI has no such file, so
    the failure only ever appears on the machines doing the work.
    """
    return Settings(_env_file=None, **environment)  # type: ignore[call-arg]


def test_cors_origins_defaults_to_the_local_frontend() -> None:
    assert configured().cors_origins == ["http://localhost:5173"]


def test_cors_origins_reads_a_single_origin_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://caselaw.example.com")

    assert configured().cors_origins == ["https://caselaw.example.com"]


def test_cors_origins_reads_a_comma_separated_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS", "http://localhost:5173, https://caselaw.example.com"
    )

    assert configured().cors_origins == [
        "http://localhost:5173",
        "https://caselaw.example.com",
    ]


def test_environment_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert configured().environment == "production"


def test_legacy_export_limit_does_not_restrict_exports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXPORT_MAX_DECISIONS", "1000")
    assert "export_max_decisions" not in Settings.model_fields


def test_a_blank_model_name_falls_back_to_the_default() -> None:
    """
    `${GEMINI_MODEL:-}` in a compose file passes an empty string, not nothing.
    Without this it would override the default with a name no API accepts, and
    the failure would surface as a model error on the first reading.
    """
    from app.config import DEFAULT_MODEL

    assert configured(GEMINI_MODEL="").gemini_model == DEFAULT_MODEL
    assert configured(GEMINI_MODEL="   ").gemini_model == DEFAULT_MODEL


def test_a_model_name_that_was_given_is_kept() -> None:
    assert (
        configured(GEMINI_MODEL="gemini-2.5-flash").gemini_model == "gemini-2.5-flash"
    )
