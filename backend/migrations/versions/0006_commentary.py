"""E6: commentary sections on updates.

Each update holds a headline, a note per department and likely board questions. Investors
read the headline and notes of shared updates only; the board questions help the company
prepare and are never shown to investors. Enforced here as well as in the API.

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TABLES = """
CREATE TABLE updates.sections (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  update_id uuid NOT NULL REFERENCES updates.updates(id),
  kind varchar(20) NOT NULL CHECK (kind IN ('headline', 'note', 'questions')),
  department varchar(20),
  position integer NOT NULL,
  text text CHECK (char_length(text) <= 4000),
  status varchar(20) NOT NULL CHECK (status IN ('drafted', 'needs_person', 'written', 'edited')),
  reason varchar(200),
  check_result jsonb NOT NULL DEFAULT '{}',
  model varchar(100),
  skill_version varchar(50),
  edited_by uuid,
  edited_by_name varchar(200),
  edited_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_updates_sections_tenant_id ON updates.sections (tenant_id);
CREATE INDEX ix_updates_sections_update_id ON updates.sections (update_id);
"""

POLICIES = """
GRANT SELECT, INSERT, UPDATE, DELETE ON updates.sections TO br_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON updates.sections TO br_system;
ALTER TABLE updates.sections ENABLE ROW LEVEL SECURITY;
CREATE POLICY app_read ON updates.sections FOR SELECT TO br_app
  USING (tenant_id = app.member_tenant()
         AND update_id IN (SELECT id FROM updates.updates)
         AND (kind <> 'questions' OR app.member_role() <> 'investor'));
CREATE POLICY app_insert ON updates.sections FOR INSERT TO br_app
  WITH CHECK (tenant_id = app.member_tenant() AND app.member_role() <> 'investor');
CREATE POLICY app_update ON updates.sections FOR UPDATE TO br_app
  USING (tenant_id = app.member_tenant() AND app.member_role() <> 'investor')
  WITH CHECK (tenant_id = app.member_tenant() AND app.member_role() <> 'investor');
CREATE POLICY app_delete ON updates.sections FOR DELETE TO br_app
  USING (tenant_id = app.member_tenant() AND app.member_role() <> 'investor');
CREATE POLICY system_all ON updates.sections FOR ALL TO br_system USING (true) WITH CHECK (true);
"""


def upgrade() -> None:
    op.execute(TABLES)
    op.execute(POLICIES)


def downgrade() -> None:
    op.execute("DROP TABLE updates.sections")
