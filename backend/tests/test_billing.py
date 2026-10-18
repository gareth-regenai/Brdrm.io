"""E8: entitlements as named keys, Stripe Checkout and the portal, warn or block.

Pricing is under commercial review, so the plans here are made up for the tests. Stripe is
never called: checkout and the portal use a recorded client, and webhook events are signed
here with the test secret and checked by the real signature code.
"""

import ast
from pathlib import Path

import pytest

from boardroom.config import get_settings
from boardroom.modules.billing import payments
from tests.conftest import subscription_event, upload_file

PACKAGE = Path(__file__).resolve().parents[1] / "boardroom"


@pytest.fixture
def block(monkeypatch):
    monkeypatch.setattr(get_settings(), "limit_behaviour", "block")


@pytest.fixture
def warn(monkeypatch):
    monkeypatch.setattr(get_settings(), "limit_behaviour", "warn")


def _invite(client, company, n):
    return client.post(
        "/company/invitations",
        headers=company.owner.auth(company.tenant_id),
        json={"email": f"investor{n}@fund.example.com", "role": "investor"},
    )


def _start_upload(client, company, size):
    return client.post(
        "/company/uploads",
        headers=company.owner.auth(company.tenant_id),
        json={"filename": "big.csv", "size_bytes": size, "content_type": "text/csv"},
    )


def _billing(client, company):
    r = client.get("/company/billing", headers=company.owner.auth(company.tenant_id))
    assert r.status_code == 200, r.text
    return r.json()


# FR-9.1: entitlements are named keys, changed with no deploy.


def test_with_no_plans_nothing_is_limited(client, make_company, stripe, block):
    company = make_company()
    for n in range(4):
        assert _invite(client, company, n).status_code == 201
    lines = {line["key"]: line for line in _billing(client, company)["lines"]}
    assert lines["viewers"] == {
        "key": "viewers",
        "label": "Investors, joined or invited",
        "limit": None,
        "used": 4,
    }


def test_changing_a_key_changes_behaviour_with_no_deploy(
    client, make_company, stripe, platform_admin, block
):
    company = make_company()
    admin = platform_admin.auth()
    r = client.put(
        "/admin/billing/plans/starter",
        headers=admin,
        json={"name": "Starter", "entitlements": {"viewers": 1}, "is_default": True},
    )
    assert r.status_code == 200, r.text
    assert _invite(client, company, 1).status_code == 201
    refused = _invite(client, company, 2)
    assert refused.status_code == 402
    assert refused.json()["detail"].startswith("Your plan includes 1 investor.")

    # The same running app, a new value.
    client.put(
        "/admin/billing/plans/starter",
        headers=admin,
        json={"name": "Starter", "entitlements": {"viewers": 2}, "is_default": True},
    )
    assert _invite(client, company, 2).status_code == 201
    [viewers] = [line for line in _billing(client, company)["lines"] if line["key"] == "viewers"]
    assert viewers["limit"] == 2 and viewers["used"] == 2


def test_only_platform_admins_set_plans_and_only_known_keys(client, make_company, platform_admin):
    company = make_company()
    body = {"name": "Starter", "entitlements": {"viewers": 1}}
    r = client.put("/admin/billing/plans/starter", headers=company.owner.auth(), json=body)
    assert r.status_code == 403
    assert client.get("/admin/billing/plans", headers=company.owner.auth()).status_code == 403
    bad = {"name": "Starter", "entitlements": {"seats": 1}}
    r = client.put("/admin/billing/plans/starter", headers=platform_admin.auth(), json=bad)
    assert r.status_code == 422 and "seats" in r.json()["detail"]
    negative = {"name": "Starter", "entitlements": {"viewers": -1}}
    r = client.put("/admin/billing/plans/starter", headers=platform_admin.auth(), json=negative)
    assert r.status_code == 422
    for key in ("Starter", "st%C3%A4rter", "a" * 41):
        r = client.put(f"/admin/billing/plans/{key}", headers=platform_admin.auth(), json=body)
        assert r.status_code == 422, key


def test_inviting_the_same_investor_again_takes_no_new_place(client, make_company, stripe, block):
    stripe.plan("starter", default=True, viewers=1)
    company = make_company()
    assert _invite(client, company, 1).status_code == 201
    assert _invite(client, company, 1).status_code == 201
    assert _invite(client, company, 2).status_code == 402


def test_the_file_size_key(client, make_company, stripe, block):
    stripe.plan("starter", default=True, max_file_mb=1)
    company = make_company()
    r = _start_upload(client, company, 2 * 1024 * 1024)
    assert r.status_code == 402 and "files up to 1 MB" in r.json()["detail"]
    assert _start_upload(client, company, 1024 * 1024).status_code == 201


def test_a_file_bigger_than_declared_is_checked_again(client, make_company, stripe, block):
    stripe.plan("starter", default=True, max_file_mb=1)
    company = make_company()
    h = company.owner.auth(company.tenant_id)
    start = _start_upload(client, company, 10).json()
    client.request(start["method"], start["url"], content=b"x" * (2 * 1024 * 1024 + 1))
    r = client.post(f"/company/uploads/{start['upload_id']}/complete", headers=h)
    assert r.json()["status"] == "failed" and "files up to 1 MB" in r.json()["message"]


def test_the_files_a_month_key(client, make_company, stripe, recorded_ai, block):
    stripe.plan("starter", default=True, uploads_per_month=1)
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    r = _start_upload(client, company, 100)
    assert r.status_code == 402 and "1 file a month" in r.json()["detail"]


def test_a_paid_plan_replaces_the_default_until_it_ends(client, make_company, stripe, block):
    stripe.plan("free", default=True, viewers=0)
    stripe.plan("growth", price="price_growth", viewers=5)
    company = make_company()
    assert _invite(client, company, 1).status_code == 402

    assert stripe.send(subscription_event(company.tenant_id, "price_growth")).status_code == 200
    assert _billing(client, company)["plan_name"] == "Growth"
    assert _invite(client, company, 1).status_code == 201

    ended = subscription_event(
        company.tenant_id, "price_growth", kind="deleted", created=1_790_000_100
    )
    stripe.send(ended)
    assert _billing(client, company)["plan_name"] == "Free"
    assert _invite(client, company, 2).status_code == 402


# FR-9.2: Stripe Checkout and the portal, with idempotent webhooks.


def test_checkout_goes_to_stripe_for_this_company(client, make_company, stripe):
    stripe.plan("growth", price="price_growth", viewers=5)
    company = make_company()
    r = client.post(
        "/company/billing/checkout",
        headers=company.owner.auth(company.tenant_id),
        json={"plan": "growth"},
    )
    assert r.status_code == 200 and r.json()["url"].startswith("https://checkout.stripe.test/")
    [sent] = stripe.payments.checkouts
    assert str(sent["tenant_id"]) == company.tenant_id and sent["price_id"] == "price_growth"
    assert sent["email"] == company.owner.email and sent["customer_id"] is None
    assert sent["success_url"] == f"http://web.test/c/{company.tenant_id}/settings?billing=done"


def test_a_plan_without_a_price_cannot_be_bought(client, make_company, stripe):
    stripe.plan("free", default=True)
    company = make_company()
    r = client.post(
        "/company/billing/checkout",
        headers=company.owner.auth(company.tenant_id),
        json={"plan": "free"},
    )
    assert r.status_code == 404
    assert [p["can_buy"] for p in _billing(client, company)["plans"]] == [False]


def test_without_stripe_set_up_payment_says_so(client, make_company, stripe):
    stripe.plan("growth", price="price_growth")
    payments.set_payments(None)
    company = make_company()
    r = client.post(
        "/company/billing/checkout",
        headers=company.owner.auth(company.tenant_id),
        json={"plan": "growth"},
    )
    assert r.status_code == 503 and r.json()["detail"] == "Payment is not set up yet."
    assert _billing(client, company)["payment_ready"] is False


def test_a_stripe_error_is_explained_and_charges_nothing(client, make_company, stripe):
    import stripe as stripe_sdk

    class Down:
        def checkout_url(self, **kwargs):
            raise stripe_sdk.APIConnectionError("no route")

    stripe.plan("growth", price="price_growth")
    payments.set_payments(Down())
    company = make_company()
    r = client.post(
        "/company/billing/checkout",
        headers=company.owner.auth(company.tenant_id),
        json={"plan": "growth"},
    )
    assert r.status_code == 502 and "Nothing was charged" in r.json()["detail"]


def test_the_portal_opens_once_checkout_is_complete(client, make_company, stripe):
    company = make_company()
    h = company.owner.auth(company.tenant_id)
    assert client.post("/company/billing/portal", headers=h).status_code == 404
    done = {
        "id": "evt_checkout",
        "type": "checkout.session.completed",
        "created": 1_790_000_000,
        "data": {
            "object": {
                "mode": "subscription",
                "client_reference_id": company.tenant_id,
                "customer": "cus_42",
                "subscription": "sub_42",
            }
        },
    }
    assert stripe.send(done).json() == {"outcome": "applied"}
    r = client.post("/company/billing/portal", headers=h)
    assert r.status_code == 200
    assert stripe.payments.portals[0]["customer_id"] == "cus_42"


def test_an_unsigned_or_wrongly_signed_event_changes_nothing(
    client, make_company, stripe, owner_conn
):
    stripe.plan("growth", price="price_growth")
    company = make_company()
    event = subscription_event(company.tenant_id, "price_growth")
    assert stripe.send(event, secret="whsec_wrong").status_code == 400
    r = client.post("/billing/stripe/webhook", json=event)
    assert r.status_code == 400
    assert owner_conn.execute("SELECT count(*) FROM billing.stripe_events").fetchone()[0] == 0
    assert _billing(client, company)["plan_name"] is None


def test_replayed_webhooks_change_nothing(client, make_company, stripe, owner_conn):
    stripe.plan("growth", price="price_growth")
    company = make_company()
    first = subscription_event(company.tenant_id, "price_growth", created=1_790_000_000)
    ended = subscription_event(
        company.tenant_id, "price_growth", kind="deleted", created=1_790_000_100
    )
    assert stripe.send(first).json() == {"outcome": "applied"}
    assert stripe.send(ended).json() == {"outcome": "applied"}

    def state():
        return owner_conn.execute(
            "SELECT plan_key, status, last_event_at FROM billing.subscriptions"
        ).fetchall()

    before = state()
    audited = owner_conn.execute("SELECT count(*) FROM audit.audit_log").fetchone()[0]
    # The same events again, in any order: each is recognised and nothing moves.
    assert stripe.send(first).json() == {"outcome": "duplicate"}
    assert stripe.send(ended).json() == {"outcome": "duplicate"}
    assert state() == before and before[0][1] == "canceled"
    assert owner_conn.execute("SELECT count(*) FROM audit.audit_log").fetchone()[0] == audited


def test_an_older_event_arriving_late_cannot_undo_a_newer_one(client, make_company, stripe):
    stripe.plan("growth", price="price_growth")
    company = make_company()
    stripe.send(
        subscription_event(company.tenant_id, "price_growth", kind="deleted", created=1_790_000_100)
    )
    late = subscription_event(company.tenant_id, "price_growth", created=1_790_000_000)
    assert stripe.send(late).json() == {"outcome": "stale"}
    assert _billing(client, company)["status"] == "canceled"


def test_events_for_no_company_are_kept_and_ignored(client, stripe):
    event = subscription_event(None, "price_growth", sub_id="sub_unknown")
    assert stripe.send(event).json() == {"outcome": "ignored"}
    assert stripe.send(event).json() == {"outcome": "duplicate"}


def test_one_company_never_sees_anothers_plan(client, make_company, stripe):
    stripe.plan("growth", price="price_growth", viewers=5)
    a, b = make_company("Alpha"), make_company("Bravo")
    stripe.send(subscription_event(a.tenant_id, "price_growth"))
    assert _billing(client, a)["plan_name"] == "Growth"
    assert _billing(client, b)["plan_name"] is None and _billing(client, b)["status"] is None


def test_the_database_hides_one_companys_subscription_from_another(
    make_company, stripe, owner_conn
):
    import psycopg

    stripe.plan("growth", price="price_growth")
    a, b = make_company("Alpha"), make_company("Bravo")
    stripe.send(subscription_event(a.tenant_id, "price_growth", sub_id="sub_a"))
    stripe.send(subscription_event(b.tenant_id, "price_growth", sub_id="sub_b"))
    with psycopg.connect(owner_conn.info.dsn, password=owner_conn.info.password) as conn:
        conn.execute("SET ROLE br_app")
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (a.tenant_id,))
        conn.execute("SELECT set_config('app.user_id', %s, false)", (a.owner.user_id,))
        rows = conn.execute("SELECT stripe_subscription_id FROM billing.subscriptions").fetchall()
        assert rows == [("sub_a",)]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM billing.stripe_events")


# FR-9.3: no approval behaviour depends on the tier.


@pytest.mark.parametrize("tier", ["none", "tight", "paid"])
def test_approval_works_the_same_on_every_tier(
    client, make_company, invite, stripe, recorded_ai, block, tier
):
    company = make_company()
    ceo = invite(company, "ceo")
    upload_file(client, company, "xero_pnl.csv")
    if tier == "tight":
        stripe.plan("tight", default=True, viewers=0, uploads_per_month=0, max_file_mb=0)
    if tier == "paid":
        stripe.plan("growth", price="price_growth", viewers=0)
        stripe.send(subscription_event(company.tenant_id, "price_growth"))
    [update] = client.get("/company/updates", headers=ceo.auth(company.tenant_id)).json()
    r = client.post(f"/company/updates/{update['id']}/approve", headers=ceo.auth(company.tenant_id))
    assert r.status_code == 200 and r.json()["status"] == "shared"


def test_approval_code_never_reads_the_plan():
    paths = [PACKAGE / "permissions.py", *(PACKAGE / "modules" / "updates").rglob("*.py")]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "billing" not in node.module, path
                assert all(a.name != "billing" for a in node.names), path


# FR-9.4: what happens at a limit is a setting, and both settings work.


def test_block_refuses_and_keeps_nothing(client, make_company, stripe, block, owner_conn):
    stripe.plan("free", default=True, viewers=0)
    company = make_company()
    r = _invite(client, company, 1)
    assert r.status_code == 402
    assert r.json()["detail"] == (
        "Your plan includes 0 investors. The Owner or CEO can change the plan in Settings."
    )
    assert owner_conn.execute("SELECT count(*) FROM identity.invitations").fetchone()[0] == 0


def test_warn_lets_it_through_and_says_so(client, make_company, stripe, warn, owner_conn):
    stripe.plan("free", default=True, viewers=0)
    company = make_company()
    r = _invite(client, company, 1)
    assert r.status_code == 201
    assert r.headers["X-Limit-Warning"] == (
        "Your plan includes 0 investors. This went through. The Owner or CEO can change the plan."
    )
    passed = owner_conn.execute(
        "SELECT details FROM audit.audit_log WHERE action = 'billing.limit_passed'"
    ).fetchall()
    assert [d for (d,) in passed] == [{"key": "viewers", "limit": 0, "wanted": 1}]
    # Within the limit, no warning.
    stripe.plan("free", default=True, viewers=5)
    assert "X-Limit-Warning" not in _invite(client, company, 2).headers


def test_the_billing_page_says_which_setting_applies(client, make_company, stripe, block):
    company = make_company()
    assert _billing(client, company)["behaviour"] == "block"
