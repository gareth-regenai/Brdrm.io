"""E3: figures engine. Row selections, calculation runs, figures with lineage, and each
company's display and warning-line settings. Row-level security on every table.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLES = """
CREATE SCHEMA metrics;
GRANT USAGE ON SCHEMA metrics TO br_app, br_system;

CREATE TABLE metrics.selections (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  dataset_id uuid NOT NULL,
  row_set varchar(50) NOT NULL,
  filters jsonb NOT NULL,
  source varchar(20) NOT NULL CHECK (source IN ('ai', 'standard')),
  reason varchar(300) NOT NULL,
  model varchar(100),
  skill_version varchar(100),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (dataset_id, row_set)
);
CREATE INDEX ix_metrics_selections_tenant_id ON metrics.selections (tenant_id);

CREATE TABLE metrics.runs (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  upload_id uuid,
  annual_revenue varchar(40),
  band integer NOT NULL,
  currency varchar(3) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_metrics_runs_tenant_id ON metrics.runs (tenant_id);

CREATE TABLE metrics.figures (
  id uuid PRIMARY KEY,
  tenant_id uuid NOT NULL,
  run_id uuid NOT NULL REFERENCES metrics.runs(id),
  metric varchar(50) NOT NULL,
  period varchar(7) NOT NULL,
  value varchar(60),
  status varchar(20) NOT NULL,
  formula_version varchar(20) NOT NULL,
  method varchar(50) NOT NULL,
  custom boolean NOT NULL,
  inputs jsonb NOT NULL,
  lineage jsonb NOT NULL,
  extra jsonb NOT NULL,
  risk_measure varchar(60),
  risk_common varchar(10),
  risk_company varchar(10),
  created_at timestamptz NOT NULL DEFAULT now(),
  -- A custom method is always flagged (FR-5.3), and every figure has lineage (FR-1.2).
  CHECK (custom = (method <> 'standard')),
  CHECK (status <> 'ok' OR lineage <> '{"datasets": [], "manual": []}'::jsonb)
);
CREATE INDEX ix_metrics_figures_tenant_id ON metrics.figures (tenant_id);
CREATE INDEX ix_metrics_figures_run_id ON metrics.figures (run_id);

CREATE TABLE metrics.settings (
  tenant_id uuid NOT NULL,
  metric varchar(50) NOT NULL,
  hidden boolean NOT NULL DEFAULT false,
  band_offset integer NOT NULL DEFAULT 0 CHECK (band_offset BETWEEN -1 AND 1),
  high varchar(40),
  medium varchar(40),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, metric)
);

CREATE TABLE metrics.outbox (
  id uuid PRIMARY KEY,
  tenant_id uuid,
  event_type varchar(100) NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  dispatched_at timestamptz
);
CREATE INDEX ix_metrics_outbox_tenant_id ON metrics.outbox (tenant_id);
CREATE INDEX ix_metrics_outbox_pending ON metrics.outbox (created_at) WHERE dispatched_at IS NULL;
"""

APP_TABLES = ("selections", "runs", "figures", "settings")


def upgrade() -> None:
    op.execute(TABLES)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON "
        + ", ".join(f"metrics.{t}" for t in APP_TABLES)
        + " TO br_app"
    )
    op.execute("GRANT SELECT, INSERT ON metrics.outbox TO br_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA metrics TO br_system")
    for table in APP_TABLES:
        op.execute(f"ALTER TABLE metrics.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY app_all ON metrics.{table} FOR ALL TO br_app "
            "USING (tenant_id = app.member_tenant()) WITH CHECK (tenant_id = app.member_tenant())"
        )
    op.execute("ALTER TABLE metrics.outbox ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY app_all ON metrics.outbox FOR ALL TO br_app "
        "USING (tenant_id = app.member_tenant()) "
        "WITH CHECK (tenant_id IS NULL OR tenant_id = app.member_tenant())"
    )
    for table in (*APP_TABLES, "outbox"):
        op.execute(
            f"CREATE POLICY system_all ON metrics.{table} FOR ALL TO br_system "
            "USING (true) WITH CHECK (true)"
        )


def downgrade() -> None:
    op.execute("DROP SCHEMA metrics CASCADE")
