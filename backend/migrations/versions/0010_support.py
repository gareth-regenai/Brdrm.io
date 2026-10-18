"""E10: staff support access (FR-11.6). A BoardRoom staff member opens a support session on
one company, with a reason. It is read-only, lasts a fixed time, appears in the company's
audit log and on its pages, and the Owner or CEO can end it at once.

A session is not a membership, so support staff never appear in the team, the investor
list, tagging or emails. The two membership functions now also admit an open, unexpired
session, so row-level security grants access and withdraws it on expiry by itself.

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

TABLE = """
CREATE TABLE identity.support_sessions (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES identity.tenants(id),
  user_id uuid NOT NULL REFERENCES identity.users(id),
  staff_name varchar(200) NOT NULL,
  reason varchar(300) NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  ended_at timestamptz,
  ended_by uuid
);
CREATE INDEX ix_identity_support_sessions_tenant_id ON identity.support_sessions (tenant_id);
CREATE INDEX ix_identity_support_sessions_user_id ON identity.support_sessions (user_id);

GRANT SELECT, UPDATE ON identity.support_sessions TO br_app;
GRANT SELECT, INSERT, UPDATE ON identity.support_sessions TO br_system;
ALTER TABLE identity.support_sessions ENABLE ROW LEVEL SECURITY;
-- The company sees and can end sessions on itself; staff see their own.
CREATE POLICY app_read ON identity.support_sessions FOR SELECT TO br_app
  USING (tenant_id = app.member_tenant() OR user_id = app.current_user_id());
CREATE POLICY app_end ON identity.support_sessions FOR UPDATE TO br_app
  USING (tenant_id = app.member_tenant()) WITH CHECK (tenant_id = app.member_tenant());
CREATE POLICY system_all ON identity.support_sessions FOR ALL TO br_system
  USING (true) WITH CHECK (true);
"""

OPEN = "ended_at IS NULL AND expires_at > now()"

FUNCTIONS = f"""
CREATE OR REPLACE FUNCTION app.user_tenant_ids() RETURNS SETOF uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, identity AS
$$ SELECT tenant_id FROM identity.memberships
   WHERE user_id = app.current_user_id() AND status = 'active'
   UNION
   SELECT tenant_id FROM identity.support_sessions
   WHERE user_id = app.current_user_id() AND {OPEN} $$;

CREATE OR REPLACE FUNCTION app.member_role() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, identity AS
$$ SELECT COALESCE(
     (SELECT role FROM identity.memberships
      WHERE tenant_id = app.member_tenant() AND user_id = app.current_user_id()
        AND status = 'active'),
     (SELECT 'support'::text FROM identity.support_sessions
      WHERE tenant_id = app.member_tenant() AND user_id = app.current_user_id()
        AND {OPEN} LIMIT 1)) $$;
"""

ORIGINAL_FUNCTIONS = """
CREATE OR REPLACE FUNCTION app.user_tenant_ids() RETURNS SETOF uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, identity AS
$$ SELECT tenant_id FROM identity.memberships
   WHERE user_id = app.current_user_id() AND status = 'active' $$;

CREATE OR REPLACE FUNCTION app.member_role() RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, identity AS
$$ SELECT role FROM identity.memberships
   WHERE tenant_id = app.member_tenant() AND user_id = app.current_user_id()
     AND status = 'active' $$;
"""


def upgrade() -> None:
    op.execute(TABLE)
    op.execute(FUNCTIONS)


def downgrade() -> None:
    op.execute(ORIGINAL_FUNCTIONS)
    op.execute("DROP TABLE identity.support_sessions")
