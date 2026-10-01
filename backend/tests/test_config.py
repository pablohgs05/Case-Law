import pytest

from app.config import Settings

pytestmark = pytest.mark.unit


def test_cors_origins_defaults_to_the_local_frontend() -> None:
    assert Settings().cors_origins == ["http://localhost:5173"]


def test_cors_origins_reads_a_single_origin_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://caselaw.example.com")

    assert Settings().cors_origins == ["https://caselaw.example.com"]


def test_cors_origins_reads_a_comma_separated_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS", "http://localhost:5173, https://caselaw.example.com"
    )

    assert Settings().cors_origins == [
        "http://localhost:5173",
        "https://caselaw.example.com",
    ]


def test_environment_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert Settings().environment == "production"
