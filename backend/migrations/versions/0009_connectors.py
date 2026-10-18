"""Connected tools: which tools a company has connected, by whom, and when each last sent
its data. What a tool sends becomes an upload and takes the upload's path from there.

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

TABLES = """
CREATE SCHEMA connectors;
GRANT USAGE ON SCHEMA connectors TO br_app, br_system;

CREATE TABLE connectors.connections (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  provider varchar(30) NOT NULL,
  status varchar(20) NOT NULL CHECK (status IN ('connected', 'failed')),
  connected_by uuid NOT NULL,
  connected_by_name varchar(200) NOT NULL,
  connected_at timestamptz NOT NULL DEFAULT now(),
  last_synced_at timestamptz,
  last_error varchar(300),
  UNIQUE (tenant_id, provider)
);
CREATE INDEX ix_connectors_connections_tenant_id ON connectors.connections (tenant_id);
"""


def upgrade() -> None:
    op.execute(TABLES)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON connectors.connections TO br_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON connectors.connections TO br_system")
    op.execute("ALTER TABLE connectors.connections ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY app_all ON connectors.connections FOR ALL TO br_app "
        "USING (tenant_id = app.member_tenant()) WITH CHECK (tenant_id = app.member_tenant())"
    )
    op.execute(
        "CREATE POLICY system_all ON connectors.connections FOR ALL TO br_system "
        "USING (true) WITH CHECK (true)"
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA connectors CASCADE")
