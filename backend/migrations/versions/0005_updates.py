"""E5: updates, approvals and comments, and the logo and colour for exports.

Investors see an update only once it is shared (FR-3.3). That is enforced here as well as
in the API: an investor's session cannot read an update awaiting approval, its figures or
its comments, and cannot change an update at all.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

FUNCTIONS = """
-- The current user's role in the current tenant, if they are an active member of it.
CREATE FUNCTION app.member_role() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, identity AS
$$ SELECT role FROM identity.memberships
   WHERE tenant_id = app.member_tenant() AND user_id = app.current_user_id()
     AND status = 'active' $$;
REVOKE ALL ON FUNCTION app.member_role() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.member_role() TO br_app, br_system;
"""

TABLES = """
CREATE SCHEMA updates;
GRANT USAGE ON SCHEMA updates TO br_app, br_system;

CREATE TABLE updates.updates (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  upload_id uuid NOT NULL UNIQUE,
  run_id uuid NOT NULL,
  added_by uuid NOT NULL,
  added_by_name varchar(200) NOT NULL,
  added_by_role varchar(30) NOT NULL,
  department varchar(20) NOT NULL,
  data_as_of date NOT NULL,
  status varchar(20) NOT NULL CHECK (status IN ('awaiting_approval', 'shared')),
  approved_by uuid,
  approved_by_name varchar(200),
  approved_at timestamptz,
  last_edited_at timestamptz,
  last_edited_by_name varchar(200),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_updates_updates_tenant_id ON updates.updates (tenant_id);

CREATE TABLE updates.figures (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  update_id uuid NOT NULL REFERENCES updates.updates(id),
  figure_id uuid NOT NULL,
  metric varchar(50) NOT NULL,
  period varchar(7) NOT NULL,
  position integer NOT NULL,
  edited_value varchar(60),
  edited_from varchar(60),
  edited_by uuid,
  edited_by_name varchar(200),
  edited_at timestamptz,
  UNIQUE (update_id, figure_id)
);
CREATE INDEX ix_updates_figures_tenant_id ON updates.figures (tenant_id);
CREATE INDEX ix_updates_figures_update_id ON updates.figures (update_id);

CREATE TABLE updates.comments (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  update_id uuid NOT NULL REFERENCES updates.updates(id),
  author_id uuid NOT NULL,
  author_name varchar(200) NOT NULL,
  author_role varchar(30) NOT NULL,
  body text NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_updates_comments_tenant_id ON updates.comments (tenant_id);
CREATE INDEX ix_updates_comments_update_id ON updates.comments (update_id);

CREATE TABLE updates.outbox (
  id uuid PRIMARY KEY,
  tenant_id uuid,
  event_type varchar(100) NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  dispatched_at timestamptz
);
CREATE INDEX ix_updates_outbox_tenant_id ON updates.outbox (tenant_id);
CREATE INDEX ix_updates_outbox_pending ON updates.outbox (created_at) WHERE dispatched_at IS NULL;

ALTER TABLE setup.profiles
  ADD COLUMN brand_colour varchar(7) CHECK (brand_colour ~ '^#[0-9A-F]{6}$'),
  ADD COLUMN logo_key varchar(200);
"""

GRANTS = """
GRANT SELECT, UPDATE ON updates.updates, updates.figures TO br_app;
GRANT SELECT, INSERT ON updates.comments, updates.outbox TO br_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA updates TO br_system;
"""

# Updates are created by the event consumer (br_system) when an upload is ready. In the
# app, company users read and change them; investors read shared ones and comment.
POLICIES = """
ALTER TABLE updates.updates ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_read ON updates.updates FOR SELECT TO br_app
  USING (tenant_id = app.member_tenant()
         AND (status = 'shared' OR app.member_role() <> 'investor'));
CREATE POLICY app_update ON updates.updates FOR UPDATE TO br_app
  USING (tenant_id = app.member_tenant() AND app.member_role() <> 'investor')
  WITH CHECK (tenant_id = app.member_tenant() AND app.member_role() <> 'investor');

ALTER TABLE updates.figures ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_read ON updates.figures FOR SELECT TO br_app
  USING (tenant_id = app.member_tenant() AND update_id IN (SELECT id FROM updates.updates));
CREATE POLICY app_update ON updates.figures FOR UPDATE TO br_app
  USING (tenant_id = app.member_tenant() AND app.member_role() <> 'investor')
  WITH CHECK (tenant_id = app.member_tenant() AND app.member_role() <> 'investor');

ALTER TABLE updates.comments ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_read ON updates.comments FOR SELECT TO br_app
  USING (tenant_id = app.member_tenant() AND update_id IN (SELECT id FROM updates.updates));
CREATE POLICY app_insert ON updates.comments FOR INSERT TO br_app
  WITH CHECK (tenant_id = app.member_tenant() AND author_id = app.current_user_id()
              AND update_id IN (SELECT id FROM updates.updates));

ALTER TABLE updates.outbox ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_all ON updates.outbox FOR ALL TO br_app
  USING (tenant_id = app.member_tenant())
  WITH CHECK (tenant_id IS NULL OR tenant_id = app.member_tenant());
"""


def upgrade() -> None:
    op.execute(FUNCTIONS)
    op.execute(TABLES)
    op.execute(GRANTS)
    op.execute(POLICIES)
    for table in ("updates", "figures", "comments", "outbox"):
        op.execute(
            f"CREATE POLICY system_all ON updates.{table} FOR ALL TO br_system "
            "USING (true) WITH CHECK (true)"
        )


def downgrade() -> None:
    op.execute("DROP SCHEMA updates CASCADE")
    op.execute("ALTER TABLE setup.profiles DROP COLUMN brand_colour, DROP COLUMN logo_key")
    op.execute("DROP FUNCTION app.member_role()")
