"""The models and the migrated database agree, so no change slips in without a migration."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

import boardroom.events  # noqa: F401
import boardroom.modules.audit.models  # noqa: F401
import boardroom.modules.identity.models  # noqa: F401
import boardroom.modules.intake.models  # noqa: F401
import boardroom.modules.metrics.models  # noqa: F401
import boardroom.modules.setup.models  # noqa: F401
from boardroom.db import Base
from tests.conftest import OWNER_URL


def test_models_match_the_migrated_schema():
    engine = create_engine(OWNER_URL.replace("postgresql://", "postgresql+psycopg://"))
    with engine.connect() as conn:
        context = MigrationContext.configure(
            conn,
            opts={
                "include_schemas": True,
                "include_name": lambda name, type_, _p: (
                    type_ != "schema"
                    or name in ("identity", "audit", "events", "intake", "metrics", "setup")
                ),
                "compare_server_default": False,
            },
        )
        diff = compare_metadata(context, Base.metadata)
    # Partial indexes and check constraints live only in the migration.
    partial = {
        "ix_identity_outbox_pending",
        "ix_intake_outbox_pending",
        "ix_metrics_outbox_pending",
        "ix_setup_outbox_pending",
    }
    diff = [d for d in diff if not (d[0] == "remove_index" and d[1].name in partial)]
    assert diff == []
