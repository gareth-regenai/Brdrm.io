"""E1: identity, tenancy, audit log and outbox, with row-level security on every table.

Revision ID: 0001
Revises:
"""

import os

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


ROLES = """
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'br_app') THEN
    CREATE ROLE br_app NOLOGIN NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'br_system') THEN
    CREATE ROLE br_system NOLOGIN NOBYPASSRLS;
  END IF;
END $$;
"""

SCHEMAS = """
CREATE SCHEMA identity;
CREATE SCHEMA audit;
CREATE SCHEMA events;
CREATE SCHEMA app;
GRANT USAGE ON SCHEMA identity, audit, events, app TO br_app, br_system;
"""

# Context helpers. Missing settings read as null, so a session with no tenant sees no tenant rows.
HELPERS = """
CREATE FUNCTION app.current_tenant() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$;

CREATE FUNCTION app.current_user_id() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;
"""

TABLES = """
CREATE TABLE identity.tenants (
  id uuid PRIMARY KEY,
  tenant_type varchar(20) NOT NULL CHECK (tenant_type IN ('company', 'investor', 'deal_team')),
  name varchar(200) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);

CREATE TABLE identity.users (
  id uuid PRIMARY KEY,
  email varchar(320) NOT NULL UNIQUE,
  name varchar(200) NOT NULL,
  password_hash varchar(200) NOT NULL,
  is_platform_admin boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE identity.memberships (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES identity.tenants(id),
  user_id uuid NOT NULL REFERENCES identity.users(id),
  role varchar(30) NOT NULL
    CHECK (role IN ('owner', 'ceo', 'department_lead', 'contributor', 'investor')),
  departments varchar(30)[] NOT NULL DEFAULT '{}',
  status varchar(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'removed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  removed_at timestamptz,
  UNIQUE (tenant_id, user_id)
);
CREATE INDEX ix_identity_memberships_tenant_id ON identity.memberships (tenant_id);
CREATE INDEX ix_identity_memberships_user_id ON identity.memberships (user_id);

CREATE TABLE identity.invitations (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES identity.tenants(id),
  email varchar(320) NOT NULL,
  role varchar(30) NOT NULL CHECK (role IN ('ceo', 'department_lead', 'contributor', 'investor')),
  departments varchar(30)[] NOT NULL DEFAULT '{}',
  invited_by uuid NOT NULL REFERENCES identity.users(id),
  token_hash varchar(64) UNIQUE,
  expires_at timestamptz NOT NULL,
  accepted_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_identity_invitations_tenant_id ON identity.invitations (tenant_id);

CREATE TABLE identity.company_settings (
  tenant_id uuid PRIMARY KEY REFERENCES identity.tenants(id),
  approver_roles varchar(30)[] NOT NULL,
  approver_user_ids varchar(36)[] NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE identity.refresh_tokens (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES identity.users(id),
  token_hash varchar(64) NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_identity_refresh_tokens_user_id ON identity.refresh_tokens (user_id);

CREATE TABLE identity.outbox (
  id uuid PRIMARY KEY,
  tenant_id uuid,
  event_type varchar(100) NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  dispatched_at timestamptz
);
CREATE INDEX ix_identity_outbox_tenant_id ON identity.outbox (tenant_id);
CREATE INDEX ix_identity_outbox_pending ON identity.outbox (created_at) WHERE dispatched_at IS NULL;

CREATE TABLE events.processed_events (
  consumer varchar(100) NOT NULL,
  event_id uuid NOT NULL,
  tenant_id uuid,
  processed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (consumer, event_id)
);

CREATE TABLE audit.audit_log (
  id uuid PRIMARY KEY,
  tenant_id uuid,
  actor_user_id uuid,
  action varchar(100) NOT NULL,
  target_type varchar(50),
  target_id varchar(64),
  details jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_audit_log_tenant_id ON audit.audit_log (tenant_id);
CREATE INDEX ix_audit_audit_log_created_at ON audit.audit_log (created_at);

CREATE FUNCTION audit.refuse_change() RETURNS trigger LANGUAGE plpgsql AS
$$ BEGIN RAISE EXCEPTION 'audit_log is append-only'; END $$;
CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE ON audit.audit_log
  FOR EACH ROW EXECUTE FUNCTION audit.refuse_change();
"""

# These run as the table owner, so they read memberships without recursing into its policy.
MEMBERSHIP_HELPERS = """
CREATE FUNCTION app.user_tenant_ids() RETURNS SETOF uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, identity AS
$$ SELECT tenant_id FROM identity.memberships
   WHERE user_id = app.current_user_id() AND status = 'active' $$;

CREATE FUNCTION app.tenant_member_ids() RETURNS SETOF uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, identity AS
$$ SELECT m.user_id FROM identity.memberships m
   WHERE m.tenant_id = app.current_tenant()
     AND m.tenant_id IN (SELECT app.user_tenant_ids()) $$;

-- The current tenant, but only if the current user is an active member of it.
-- Tenant-scoped policies use this, so setting a tenant alone reveals nothing.
CREATE FUNCTION app.member_tenant() RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, identity AS
$$ SELECT t FROM (SELECT app.current_tenant() AS t) c
   WHERE t IN (SELECT app.user_tenant_ids()) $$;

CREATE FUNCTION app.tenant_has_members(t uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, identity AS
$$ SELECT EXISTS (SELECT 1 FROM identity.memberships WHERE tenant_id = t) $$;

REVOKE ALL ON FUNCTION app.user_tenant_ids(), app.tenant_member_ids(), app.member_tenant(),
  app.tenant_has_members(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.current_tenant(), app.current_user_id(),
  app.user_tenant_ids(), app.tenant_member_ids(), app.member_tenant(),
  app.tenant_has_members(uuid) TO br_app, br_system;
"""

GRANTS = """
GRANT SELECT, INSERT, UPDATE ON identity.tenants, identity.users, identity.memberships,
  identity.invitations, identity.company_settings, identity.refresh_tokens TO br_app;
GRANT SELECT, INSERT ON identity.outbox, events.processed_events TO br_app;
GRANT SELECT, INSERT ON audit.audit_log TO br_app;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA identity, events TO br_system;
GRANT SELECT, INSERT ON audit.audit_log TO br_system;
"""

# br_app: scoped to the session's tenant and user. br_system: every row.
POLICIES = """
ALTER TABLE identity.tenants ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_read ON identity.tenants FOR SELECT TO br_app
  USING (id IN (SELECT app.user_tenant_ids()));
CREATE POLICY app_insert ON identity.tenants FOR INSERT TO br_app
  WITH CHECK (id = app.current_tenant());
CREATE POLICY app_update ON identity.tenants FOR UPDATE TO br_app
  USING (id = app.member_tenant()) WITH CHECK (id = app.member_tenant());

ALTER TABLE identity.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_read ON identity.users FOR SELECT TO br_app
  USING (id = app.current_user_id() OR id IN (SELECT app.tenant_member_ids()));
CREATE POLICY app_insert ON identity.users FOR INSERT TO br_app
  WITH CHECK (id = app.current_user_id());
CREATE POLICY app_update ON identity.users FOR UPDATE TO br_app
  USING (id = app.current_user_id()) WITH CHECK (id = app.current_user_id());

-- The only membership the app role can create is the Owner of a new, empty company.
-- Joining by invitation runs as br_system once the invitation is checked.
ALTER TABLE identity.memberships ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_read ON identity.memberships FOR SELECT TO br_app
  USING (tenant_id = app.member_tenant() OR user_id = app.current_user_id());
CREATE POLICY app_insert ON identity.memberships FOR INSERT TO br_app
  WITH CHECK (tenant_id = app.current_tenant() AND user_id = app.current_user_id()
              AND role = 'owner' AND NOT app.tenant_has_members(tenant_id));
CREATE POLICY app_update ON identity.memberships FOR UPDATE TO br_app
  USING (tenant_id = app.member_tenant()) WITH CHECK (tenant_id = app.member_tenant());

ALTER TABLE identity.invitations ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_all ON identity.invitations FOR ALL TO br_app
  USING (tenant_id = app.member_tenant()) WITH CHECK (tenant_id = app.member_tenant());

ALTER TABLE identity.company_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_all ON identity.company_settings FOR ALL TO br_app
  USING (tenant_id = app.member_tenant()) WITH CHECK (tenant_id = app.member_tenant());

ALTER TABLE identity.refresh_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_all ON identity.refresh_tokens FOR ALL TO br_app
  USING (user_id = app.current_user_id()) WITH CHECK (user_id = app.current_user_id());

ALTER TABLE identity.outbox ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_all ON identity.outbox FOR ALL TO br_app
  USING (tenant_id = app.member_tenant())
  WITH CHECK (tenant_id IS NULL OR tenant_id = app.member_tenant());

ALTER TABLE events.processed_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_all ON events.processed_events FOR ALL TO br_app
  USING (tenant_id = app.member_tenant()) WITH CHECK (tenant_id = app.member_tenant());

ALTER TABLE audit.audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_read ON audit.audit_log FOR SELECT TO br_app
  USING (tenant_id = app.member_tenant());
CREATE POLICY app_insert ON audit.audit_log FOR INSERT TO br_app
  WITH CHECK (tenant_id IS NULL OR tenant_id = app.member_tenant());
"""

SYSTEM_TABLES = (
    "identity.tenants",
    "identity.users",
    "identity.memberships",
    "identity.invitations",
    "identity.company_settings",
    "identity.refresh_tokens",
    "identity.outbox",
    "events.processed_events",
    "audit.audit_log",
)


def _login_role() -> str:
    """The app's login role: no rights of its own, may switch to br_app or br_system."""
    password = os.environ.get("APP_DB_PASSWORD")
    if not password:
        return ""
    # DDL cannot take bind parameters. The password is generated by Render, and quotes are escaped.
    quoted = password.replace("'", "''")
    return f"""
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'br_login') THEN
    CREATE ROLE br_login LOGIN NOINHERIT PASSWORD '{quoted}';
  ELSE
    ALTER ROLE br_login LOGIN NOINHERIT PASSWORD '{quoted}';
  END IF;
END $$;
GRANT br_app, br_system TO br_login;
"""


def upgrade() -> None:
    op.execute(ROLES)
    op.execute(SCHEMAS)
    op.execute(HELPERS)
    op.execute(TABLES)
    op.execute(MEMBERSHIP_HELPERS)
    op.execute(GRANTS)
    op.execute(POLICIES)
    for table in SYSTEM_TABLES:
        op.execute(
            f"CREATE POLICY system_all ON {table} FOR ALL TO br_system USING (true) WITH CHECK (true)"
        )
    login = _login_role()
    if login:
        op.execute(login)


def downgrade() -> None:
    op.execute("DROP SCHEMA audit CASCADE")
    op.execute("DROP SCHEMA events CASCADE")
    op.execute("DROP SCHEMA identity CASCADE")
    op.execute("DROP SCHEMA app CASCADE")
