"""E4: setup chat. Company profile settings, targets, conversations and messages, with
row-level security on every table.

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TABLES = """
CREATE SCHEMA setup;
GRANT USAGE ON SCHEMA setup TO br_app, br_system;

CREATE TABLE setup.profiles (
  tenant_id uuid PRIMARY KEY,
  reporting_currency varchar(3) NOT NULL DEFAULT 'GBP',
  business_description varchar(300),
  website varchar(200),
  revenue_lines jsonb NOT NULL DEFAULT '[]',
  display_band integer CHECK (display_band BETWEEN 0 AND 4),
  voice varchar(20) NOT NULL DEFAULT 'we' CHECK (voice IN ('we', 'third_person')),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE setup.targets (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  metric varchar(30) NOT NULL CHECK (metric IN ('revenue', 'closed_won')),
  period varchar(7) NOT NULL,
  value varchar(40) NOT NULL,
  source varchar(20) NOT NULL CHECK (source IN ('chat', 'settings')),
  set_by uuid NOT NULL,
  set_by_name varchar(200) NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, metric, period)
);
CREATE INDEX ix_setup_targets_tenant_id ON setup.targets (tenant_id);

CREATE TABLE setup.conversations (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  status varchar(20) NOT NULL CHECK (status IN ('open', 'done', 'skipped')),
  pending_invites jsonb NOT NULL DEFAULT '[]',
  questions jsonb NOT NULL DEFAULT '[]',
  answered jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_setup_conversations_tenant_id ON setup.conversations (tenant_id);

CREATE TABLE setup.messages (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  conversation_id uuid NOT NULL REFERENCES setup.conversations(id),
  seq integer NOT NULL,
  role varchar(20) NOT NULL CHECK (role IN ('user', 'assistant')),
  content text NOT NULL,
  author_id uuid,
  applied jsonb NOT NULL DEFAULT '{}',
  source varchar(20) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (conversation_id, seq)
);
CREATE INDEX ix_setup_messages_tenant_id ON setup.messages (tenant_id);
CREATE INDEX ix_setup_messages_conversation_id ON setup.messages (conversation_id);

CREATE TABLE setup.outbox (
  id uuid PRIMARY KEY,
  tenant_id uuid,
  event_type varchar(100) NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  dispatched_at timestamptz
);
CREATE INDEX ix_setup_outbox_tenant_id ON setup.outbox (tenant_id);
CREATE INDEX ix_setup_outbox_pending ON setup.outbox (created_at) WHERE dispatched_at IS NULL;
"""

APP_TABLES = ("profiles", "targets", "conversations", "messages")


def upgrade() -> None:
    op.execute(TABLES)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON "
        + ", ".join(f"setup.{t}" for t in APP_TABLES)
        + " TO br_app"
    )
    op.execute("GRANT SELECT, INSERT ON setup.outbox TO br_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA setup TO br_system")
    for table in APP_TABLES:
        op.execute(f"ALTER TABLE setup.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY app_all ON setup.{table} FOR ALL TO br_app "
            "USING (tenant_id = app.member_tenant()) WITH CHECK (tenant_id = app.member_tenant())"
        )
    op.execute("ALTER TABLE setup.outbox ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY app_all ON setup.outbox FOR ALL TO br_app "
        "USING (tenant_id = app.member_tenant()) "
        "WITH CHECK (tenant_id IS NULL OR tenant_id = app.member_tenant())"
    )
    for table in (*APP_TABLES, "outbox"):
        op.execute(
            f"CREATE POLICY system_all ON setup.{table} FOR ALL TO br_system "
            "USING (true) WITH CHECK (true)"
        )


def downgrade() -> None:
    op.execute("DROP SCHEMA setup CASCADE")
