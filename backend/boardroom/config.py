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

    jwt_secret: str = Field(default="dev-only-change-me-at-least-32-chars", min_length=32)
    jwt_issuer: str = "boardroom.io"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    invitation_days: int = 14

    web_origin: str = "http://localhost:5173"

    # "console" prints emails, links included, so it is for development only.
    # "disabled" sends nothing until the email provider is chosen (OPEN.md).
    # "capture" keeps emails in storage for the end-to-end journeys (E9). Never production.
    mailer: Literal["console", "memory", "disabled", "smtp", "capture"] = "console"
    # Any SMTP server: an existing mailbox (Google Workspace or Gmail with an app
    # password), a provider, or Mailpit locally. The provider is open (OPEN.md).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = ""
    smtp_from_name: str = "BoardRoom.io"
    # "starttls" on 587, "ssl" on 465, "none" only for a local test inbox.
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    # In development and tests events are delivered straight after commit.
    # In staging and production the worker delivers them.
    dispatch_inline: bool = True

    # FR-2.8 is open: what a removed investor keeps of past updates.
    # "nothing" is the only behaviour until the decision is made. See OPEN.md.
    removed_investor_keeps: Literal["nothing"] = "nothing"
    # "Data true as of" on an update: the latest date in the data (falling back to the
    # upload date), or always the upload date. See OPEN.md, raised in E5.
    update_as_of: Literal["data", "upload"] = "data"
    # PDF tooling is an open decision. ReportLab is pure Python, so it runs on Render's
    # native runtime with no system libraries. See OPEN.md.
    pdf_renderer: Literal["reportlab"] = "reportlab"

    flags: FeatureFlags = Field(default_factory=FeatureFlags)

    # Where the API is reached from outside, for signed upload links in development.
    api_url: str = "http://localhost:8000"

    # File intake limits (FR-11.7). This size is the hard ceiling for every company; a
    # plan's max_file_mb entitlement can only set a lower one (E8).
    max_file_mb: int = 25
    max_rows: int = 200_000
    max_columns: int = 200
    max_cell_chars: int = 32_768
    max_uncompressed_mb: int = 200
    parse_memory_mb: int = 1024
    parse_seconds: int = 60

    # Storage provider is open (OPEN.md). Local is for development and tests only.
    storage_backend: Literal["local", "s3"] = "local"
    storage_root: str = ".storage"
    storage_bucket: str = ""
    storage_endpoint: str = ""
    storage_region: str = "eu-west-2"
    storage_access_key: str | None = None
    storage_secret_key: str | None = None

    # Malware scanner is open (OPEN.md). "basic" is not a real malware scan.
    scanner: Literal["basic", "clamav"] = "basic"
    clamav_host: str = "clamav"
    clamav_port: int = 3310

    # Skill 1, file understanding. Without a key, uploads go to manual mapping (FR-4.9).
    ai_enabled: bool = True
    anthropic_api_key: str | None = None
    skill1_model: str = "claude-sonnet-5-5"
    skill1_effort: Literal["low", "medium", "high"] = "medium"
    # Skill 2, row selection.
    skill2_model: str = "claude-sonnet-5-5"
    # The setup chat.
    setup_model: str = "claude-sonnet-5-5"
    commentary_model: str = "claude-sonnet-5-5"
    # Development only: replay recorded answers instead of calling the model.
    skill1_replay_dir: str | None = None

    # Billing (FRD ch. 9). Without a Stripe key plans and limits still apply; payment is off.
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    # FR-9.4 is open: at a limit, "warn" lets the action through and says so, "block"
    # refuses it. See OPEN.md.
    limit_behaviour: Literal["warn", "block"] = "warn"

    # Connected tools (connectors). The demo connector pulls sample books and deals, for
    # demos and the journey tests; production refuses it, so no real pack holds made-up data.
    connectors_demo: bool = False

    # Alerts (FR-12.4). Sent to this address as well as the log; empty means log only.
    ops_alert_email: str | None = None
    # A queued event or a file in progress waiting longer than this is the worker behind.
    alert_queue_minutes: int = 10
    # The AI failing on this share of files in an hour, once there are enough to judge.
    alert_ai_error_rate: float = 0.25
    alert_ai_min_calls: int = 4
    # Failed sign-ins in 15 minutes, across all accounts.
    alert_login_failures: int = 20

    # Staff support access (FR-11.6): how long a support session lasts.
    support_session_minutes: int = Field(default=60, ge=5, le=240)

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
    insecure = settings.jwt_secret == "dev-only-change-me-at-least-32-chars"  # noqa: S105
    if settings.environment in ("staging", "production"):
        if insecure:
            raise RuntimeError("JWT_SECRET must be set outside development")
        if settings.skill1_replay_dir:
            raise RuntimeError("SKILL1_REPLAY_DIR is for development only")
        if settings.storage_backend != "s3":
            raise RuntimeError("STORAGE_BACKEND=s3 is required outside development")
        # A preview (staging) may capture email for the journey tests; production never.
        allowed = (
            ("disabled", "smtp", "capture")
            if settings.environment == "staging"
            else (
                "disabled",
                "smtp",
            )
        )
        if settings.mailer not in allowed:
            raise RuntimeError("MAILER must be smtp or disabled in production")
        if settings.mailer == "smtp":
            if not settings.smtp_host or not settings.smtp_from:
                raise RuntimeError("MAILER=smtp needs SMTP_HOST and SMTP_FROM")
            if settings.smtp_security == "none":
                raise RuntimeError("SMTP_SECURITY=none is for a local test inbox only")
        if settings.connectors_demo and settings.environment == "production":
            raise RuntimeError("CONNECTORS_DEMO is for demos and tests, never production")
        if settings.stripe_secret_key and not settings.stripe_webhook_secret:
            raise RuntimeError("STRIPE_SECRET_KEY needs STRIPE_WEBHOOK_SECRET")
    return settings
