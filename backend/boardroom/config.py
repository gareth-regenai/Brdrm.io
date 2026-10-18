from functools import lru_cache
from typing import Literal
from urllib.parse import quote, urlsplit, urlunsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureFlags(BaseSettings):
    """Phase 2 features stay off in phase 1 (FR-1.3)."""

    model_config = SettingsConfigDict(env_prefix="FLAG_")

    product_delivery: bool = False
    people: bool = False
    currency_conversion: bool = False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"

    # The app connects as a login role with no table rights of its own. Every
    # transaction switches to br_app (row-level security applies) or br_system.
    database_url: str = "postgresql+psycopg://br_login:br_login@localhost:5432/boardroom"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = Field(default="dev-only-change-me", min_length=16)
    jwt_issuer: str = "boardroom.io"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    invitation_days: int = 14

    web_origin: str = "http://localhost:5173"

    # "console" prints emails, links included, so it is for development only.
    # "disabled" sends nothing until the email provider is chosen (OPEN.md).
    mailer: Literal["console", "memory", "disabled"] = "console"
    # In development and tests events are delivered straight after commit.
    # In staging and production the worker delivers them.
    dispatch_inline: bool = True

    # FR-2.8 is open: what a removed investor keeps of past updates.
    # "nothing" is the only behaviour until the decision is made. See OPEN.md.
    removed_investor_keeps: Literal["nothing"] = "nothing"

    flags: FeatureFlags = Field(default_factory=FeatureFlags)

    # On Render the app has the owner URL (for migrations) and the br_login password.
    # The app's own URL is the owner URL with br_login in place of the owner.
    migration_database_url: str | None = None
    app_db_password: str | None = None

    @model_validator(mode="after")
    def _app_database_url(self) -> "Settings":
        if (
            "database_url" not in self.model_fields_set
            and self.migration_database_url
            and self.app_db_password
        ):
            parts = urlsplit(self.migration_database_url)
            host = parts.hostname or "localhost"
            netloc = f"br_login:{quote(self.app_db_password, safe='')}@{host}"
            if parts.port:
                netloc += f":{parts.port}"
            self.database_url = urlunsplit(parts._replace(netloc=netloc))
        self.database_url = _psycopg_driver(self.database_url)
        return self


def _psycopg_driver(url: str) -> str:
    # Render gives postgres:// or postgresql:// URLs. SQLAlchemy needs the driver named.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    insecure = settings.jwt_secret == "dev-only-change-me"  # noqa: S105
    if settings.environment in ("staging", "production"):
        if insecure:
            raise RuntimeError("JWT_SECRET must be set outside development")
        if settings.mailer != "disabled":
            raise RuntimeError("Only MAILER=disabled is allowed until an email provider is chosen")
    return settings
