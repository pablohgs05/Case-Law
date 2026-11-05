from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_MODEL = "gemini-3.5-flash-lite"


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
    # Reads a thesis out of a decision the court wrote none for. Empty turns
    # the feature off everywhere rather than failing per request: without a
    # key there is nothing to ask, and the screen says so instead of offering
    # a button that cannot work.
    google_api_key: str = ""
    # Flash Lite, and the choice is about quota rather than quality. The
    # free tier allows 20 requests a day on the Flash models and 500 on
    # this one: a single afternoon of use exhausts the first. Pulling one
    # sentence out of a short ementa is work it does well, and a reading
    # it gets wrong is caught by `tese.confere` and never shown.
    #
    # A name, never an alias like `gemini-flash-latest`: an alias moves
    # under the readings already stored against it.
    gemini_model: str = DEFAULT_MODEL
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    @field_validator("gemini_model", mode="before")
    @classmethod
    def fall_back_when_blank(cls, value: object) -> object:
        """
        An empty value means the default, not an empty model name.

        A compose file written as `${GEMINI_MODEL:-}` passes an empty
        string rather than nothing at all, which would otherwise override
        the default with a name the API cannot use — and the failure would
        arrive as a model error on the first reading, nowhere near here.
        """
        if isinstance(value, str) and not value.strip():
            return DEFAULT_MODEL
        return value

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
