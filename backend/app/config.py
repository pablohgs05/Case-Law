from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/caselaw"
    environment: str = "development"
    root_path: str = ""
    database_pool_size: int = 10
    search_max_page_size: int = 100
    # Signs the session tokens. Empty is allowed only while developing: an
    # environment that serves real accounts with a default secret is one where
    # anyone can mint a manager's token, so `session_secret_or_fail` refuses to
    # start instead.
    session_secret: str = ""
    session_hours: int = 12
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def developing(self) -> bool:
        return self.environment.strip().lower() in ("development", "test")


settings = Settings()


DEVELOPMENT_SECRET = "desenvolvimento-apenas-nao-usar-em-producao"


def session_secret_or_fail() -> str:
    """
    The key the session tokens are signed with.

    Unset outside development is a refusal, not a warning. A deployment that
    falls back to a known default issues tokens anyone can forge, and the first
    sign of it would be a stranger holding a manager's session.
    """
    if settings.session_secret.strip():
        return settings.session_secret.strip()

    if settings.developing:
        return DEVELOPMENT_SECRET

    raise RuntimeError(
        "SESSION_SECRET is not set. Accounts cannot be served without it: "
        "generate one with `python -c 'import secrets; print(secrets.token_urlsafe(48))'`"
    )
