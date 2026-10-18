"""E2: AI file intake. Uploads, questions, saved layouts, datasets, the internal
interpretation log and hand-entered figures, with row-level security on every table.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = """
CREATE SCHEMA intake;
GRANT USAGE ON SCHEMA intake TO br_app, br_system;

CREATE TABLE intake.uploads (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  uploaded_by uuid NOT NULL,
  filename varchar(255) NOT NULL,
  content_type varchar(100) NOT NULL,
  size_bytes integer NOT NULL,
  sha256 varchar(64),
  status varchar(20) NOT NULL DEFAULT 'created' CHECK (status IN
    ('created', 'received', 'understanding', 'calculating', 'describing', 'ready', 'shared', 'failed')),
  status_message varchar(500),
  needs_mapping boolean NOT NULL DEFAULT false,
  file_kind varchar(20),
  header_fingerprint varchar(64),
  proposal jsonb,
  dataset_id uuid,
  row_count integer,
  data_as_of date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_intake_uploads_tenant_id ON intake.uploads (tenant_id);

CREATE TABLE intake.questions (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  upload_id uuid NOT NULL REFERENCES intake.uploads(id),
  subject varchar(255) NOT NULL,
  field varchar(50) NOT NULL,
  prompt varchar(500) NOT NULL,
  options jsonb NOT NULL,
  answer varchar(300),
  answered_by uuid,
  answered_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_intake_questions_tenant_id ON intake.questions (tenant_id);
CREATE INDEX ix_intake_questions_upload_id ON intake.questions (upload_id);

CREATE TABLE intake.layouts (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  fingerprint varchar(64) NOT NULL,
  interpretation jsonb NOT NULL,
  confirmed jsonb NOT NULL,
  source varchar(20) NOT NULL,
  updated_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, fingerprint)
);
CREATE INDEX ix_intake_layouts_tenant_id ON intake.layouts (tenant_id);

CREATE TABLE intake.datasets (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  upload_id uuid NOT NULL REFERENCES intake.uploads(id),
  kind varchar(20) NOT NULL,
  version integer NOT NULL,
  layout_id uuid NOT NULL REFERENCES intake.layouts(id),
  interpretation jsonb NOT NULL,
  fields jsonb NOT NULL,
  row_count integer NOT NULL,
  invalid_cells integer NOT NULL,
  data_as_of date,
  fingerprint varchar(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, kind, version)
);
CREATE INDEX ix_intake_datasets_tenant_id ON intake.datasets (tenant_id);
CREATE INDEX ix_intake_datasets_upload_id ON intake.datasets (upload_id);

CREATE TABLE intake.dataset_rows (
  dataset_id uuid NOT NULL REFERENCES intake.datasets(id),
  row_number integer NOT NULL,
  tenant_id uuid NOT NULL,
  data jsonb NOT NULL,
  PRIMARY KEY (dataset_id, row_number)
);
CREATE INDEX ix_intake_dataset_rows_tenant_id ON intake.dataset_rows (tenant_id);

CREATE TABLE intake.interpretation_log (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  upload_id uuid NOT NULL,
  source varchar(20) NOT NULL,
  model varchar(100),
  skill_version varchar(100),
  interpretation jsonb,
  dropped jsonb NOT NULL,
  error varchar(300),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_intake_interpretation_log_tenant_id ON intake.interpretation_log (tenant_id);
CREATE INDEX ix_intake_interpretation_log_upload_id ON intake.interpretation_log (upload_id);

CREATE TABLE intake.manual_figures (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  metric varchar(50) NOT NULL,
  period varchar(7) NOT NULL,
  value varchar(40) NOT NULL,
  kind varchar(20) NOT NULL CHECK (kind IN ('actual', 'forecast', 'target')),
  note varchar(300),
  entered_by uuid NOT NULL,
  entered_by_name varchar(200) NOT NULL,
  entered_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_intake_manual_figures_tenant_id ON intake.manual_figures (tenant_id);

CREATE TABLE intake.outbox (
  id uuid PRIMARY KEY,
  tenant_id uuid,
  event_type varchar(100) NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  dispatched_at timestamptz
);
CREATE INDEX ix_intake_outbox_tenant_id ON intake.outbox (tenant_id);
CREATE INDEX ix_intake_outbox_pending ON intake.outbox (created_at) WHERE dispatched_at IS NULL;
"""

APP_TABLES = ("uploads", "questions", "layouts", "datasets", "dataset_rows", "manual_figures")
ALL_TABLES = (*APP_TABLES, "interpretation_log", "outbox")


def upgrade() -> None:
    op.execute(TABLES)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON "
        + ", ".join(f"intake.{t}" for t in APP_TABLES)
        + " TO br_app"
    )
    op.execute("GRANT SELECT, INSERT ON intake.outbox TO br_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA intake TO br_system")
    for table in APP_TABLES:
        op.execute(f"ALTER TABLE intake.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY app_all ON intake.{table} FOR ALL TO br_app "
            "USING (tenant_id = app.member_tenant()) WITH CHECK (tenant_id = app.member_tenant())"
        )
    op.execute("ALTER TABLE intake.outbox ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY app_all ON intake.outbox FOR ALL TO br_app "
        "USING (tenant_id = app.member_tenant()) "
        "WITH CHECK (tenant_id IS NULL OR tenant_id = app.member_tenant())"
    )
    # Platform admins only (FR-4.10). The app role has no grant and this policy shows nothing.
    op.execute("ALTER TABLE intake.interpretation_log ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY app_none ON intake.interpretation_log FOR ALL TO br_app "
        "USING (false) WITH CHECK (false)"
    )
    for table in ALL_TABLES:
        op.execute(
            f"CREATE POLICY system_all ON intake.{table} FOR ALL TO br_system "
            "USING (true) WITH CHECK (true)"
        )


def downgrade() -> None:
    op.execute("DROP SCHEMA intake CASCADE")
