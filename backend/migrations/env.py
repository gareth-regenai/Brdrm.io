"""Migrations run as the database owner, never as the app's login role.

MIGRATION_DATABASE_URL is the owner connection. On Render it is the database's
own connection string, used only by the pre-deploy command.
"""

import os

from alembic import context
from sqlalchemy import create_engine

import boardroom.events  # noqa: F401
import boardroom.modules.audit.models  # noqa: F401
import boardroom.modules.billing.models  # noqa: F401
import boardroom.modules.identity.models  # noqa: F401
import boardroom.modules.intake.models  # noqa: F401
import boardroom.modules.metrics.models  # noqa: F401
import boardroom.modules.setup.models  # noqa: F401
import boardroom.modules.updates.models  # noqa: F401
from boardroom.db import Base

target_metadata = Base.metadata
SCHEMAS = (
    "identity",
    "audit",
    "events",
    "intake",
    "metrics",
    "setup",
    "updates",
    "billing",
)


def _url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Set MIGRATION_DATABASE_URL to the database owner connection")
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    if type_ == "schema":
        return name in SCHEMAS
    return True


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            version_table_schema="public",
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
