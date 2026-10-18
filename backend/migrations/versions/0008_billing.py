"""E8: plans, entitlements and payment.

Pricing is under commercial review (BR-9), so no plan, price or limit is written in code.
Plans are platform rows a platform admin changes with no deploy (FR-9.1). A company's
subscription is written only by Stripe's webhook, and each Stripe event is kept once so a
replay changes nothing (FR-9.2).

Revision ID: 0008
Revises: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TABLES = """
CREATE SCHEMA billing;
GRANT USAGE ON SCHEMA billing TO br_app, br_system;

-- Platform data, the same for every company: the plans and the value of each key in them.
CREATE TABLE billing.plans (
  key varchar(40) PRIMARY KEY CHECK (key ~ '^[a-z0-9_]+$'),
  name varchar(80) NOT NULL,
  stripe_price_id varchar(100) UNIQUE,
  entitlements jsonb NOT NULL DEFAULT '{}',
  is_default boolean NOT NULL DEFAULT false,
  available boolean NOT NULL DEFAULT true,
  position integer NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now()
);
-- At most one plan applies to companies with no subscription.
CREATE UNIQUE INDEX ux_billing_plans_default ON billing.plans (is_default) WHERE is_default;

CREATE TABLE billing.subscriptions (
  tenant_id uuid PRIMARY KEY,
  plan_key varchar(40) REFERENCES billing.plans(key),
  status varchar(30) NOT NULL,
  stripe_customer_id varchar(100) UNIQUE,
  stripe_subscription_id varchar(100) UNIQUE,
  current_period_end timestamptz,
  last_event_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Every Stripe event applied, by its id, so a replayed webhook is recognised.
CREATE TABLE billing.stripe_events (
  id varchar(100) PRIMARY KEY,
  event_type varchar(100) NOT NULL,
  tenant_id uuid,
  outcome varchar(20) NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_billing_stripe_events_tenant_id ON billing.stripe_events (tenant_id);
"""


def upgrade() -> None:
    op.execute(TABLES)
    op.execute("GRANT SELECT ON billing.plans, billing.subscriptions TO br_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA billing TO br_system")
    for table in ("plans", "subscriptions", "stripe_events"):
        op.execute(f"ALTER TABLE billing.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY system_all ON billing.{table} FOR ALL TO br_system "
            "USING (true) WITH CHECK (true)"
        )
    op.execute("CREATE POLICY app_read ON billing.plans FOR SELECT TO br_app USING (true)")
    op.execute(
        "CREATE POLICY app_read ON billing.subscriptions FOR SELECT TO br_app "
        "USING (tenant_id = app.member_tenant())"
    )
    # Stripe's events are for the webhook only. The app role has no grant and no rows.
    op.execute(
        "CREATE POLICY app_none ON billing.stripe_events FOR ALL TO br_app "
        "USING (false) WITH CHECK (false)"
    )


def downgrade() -> None:
    op.execute("DROP SCHEMA billing CASCADE")
