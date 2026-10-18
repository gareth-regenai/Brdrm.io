"""Connected tools: figures arrive from the company's tools instead of an export.

Only the demo connector is built. It pulls sample books and deals, which then take exactly
the path an uploaded file takes. Real tools show as "Coming soon" until each is built.
"""

from datetime import UTC, datetime, timedelta

import pytest

from boardroom.config import get_settings
from boardroom.events import dispatch_pending
from boardroom.modules.connectors import service


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.setattr(get_settings(), "connectors_demo", True)


def _h(account, company):
    return account.auth(company.tenant_id)


def _tools(client, company, account=None):
    r = client.get("/company/connections", headers=_h(account or company.owner, company))
    assert r.status_code == 200, r.text
    return {t["key"]: t for t in r.json()}


def _uploads(client, company):
    return client.get("/company/uploads", headers=_h(company.owner, company)).json()


def test_tools_say_what_they_send_and_whether_they_can_be_connected(client, make_company):
    company = make_company()
    tools = _tools(client, company)
    assert "demo" not in tools  # off unless switched on
    assert tools["xero"]["state"] == "coming_soon"
    assert tools["xero"]["sends"] == "Profit and loss and bank balance"
    assert tools["hubspot"]["state"] == "coming_soon"
    assert tools["jira"]["state"] == "phase_2" and tools["hibob"]["state"] == "phase_2"


@pytest.mark.parametrize(
    "key, words", [("xero", "Xero is coming soon"), ("jira", "Jira arrives in phase 2")]
)
def test_a_tool_not_built_yet_cannot_be_connected(client, make_company, key, words):
    company = make_company()
    r = client.post(f"/company/connections/{key}", headers=_h(company.owner, company))
    assert r.status_code == 409 and r.json()["detail"].startswith(words)
    r = client.post("/company/connections/nothing", headers=_h(company.owner, company))
    assert r.status_code == 404


def test_connecting_pulls_at_once_and_takes_the_upload_path(
    client, make_company, demo, recorded_ai
):
    company = make_company()
    r = client.post("/company/connections/demo", headers=_h(company.owner, company))
    assert r.status_code == 200, r.text
    tool = r.json()
    assert tool["state"] == "connected" and tool["last_synced_at"] is not None
    assert tool["connected_by_name"].startswith("Owner of")

    uploads = {u["filename"]: u for u in _uploads(client, company)}
    assert set(uploads) == {"Demo company: profit and loss.csv", "Demo company: deals.csv"}
    assert {u["kind"] for u in uploads.values()} == {"finance", "sales"}
    assert all(u["status"] in ("ready", "describing") for u in uploads.values())
    # The same figures and updates as the same files uploaded by hand.
    updates = client.get("/company/updates", headers=_h(company.owner, company)).json()
    assert len(updates) == 2 and all(u["figures"] for u in updates)
    tiles = client.get("/company/metrics", headers=_h(company.owner, company)).json()["tiles"]
    assert any(t["metric"] == "revenue" for t in tiles)


def test_pulling_again_with_nothing_new_adds_nothing(client, make_company, demo, recorded_ai):
    company = make_company()
    h = _h(company.owner, company)
    client.post("/company/connections/demo", headers=h)
    r = client.post("/company/connections/demo/sync", headers=h)
    assert r.status_code == 200 and r.json()["state"] == "connected"
    assert len(_uploads(client, company)) == 2
    assert len(client.get("/company/updates", headers=h).json()) == 2


def test_pulled_files_meet_the_plans_limits_like_any_file(
    client, make_company, demo, recorded_ai, stripe, monkeypatch
):
    monkeypatch.setattr(get_settings(), "limit_behaviour", "block")
    stripe.plan("starter", default=True, uploads_per_month=1)
    company = make_company()
    tool = client.post("/company/connections/demo", headers=_h(company.owner, company)).json()
    assert tool["state"] == "failed"
    assert tool["last_error"].startswith("Your plan includes 1 file a month.")
    # The first file went in; the one refused left nothing behind.
    assert [u["filename"] for u in _uploads(client, company)] == [
        "Demo company: profit and loss.csv"
    ]


def test_disconnecting_stops_pulls_and_keeps_what_arrived(client, make_company, demo, recorded_ai):
    company = make_company()
    h = _h(company.owner, company)
    client.post("/company/connections/demo", headers=h)
    assert client.delete("/company/connections/demo", headers=h).status_code == 204
    assert _tools(client, company)["demo"]["state"] == "available"
    assert len(_uploads(client, company)) == 2
    assert client.post("/company/connections/demo/sync", headers=h).status_code == 404


def test_the_daily_pull_runs_as_the_person_who_connected(
    client, make_company, invite, demo, recorded_ai, owner_conn
):
    company = make_company()
    ceo = invite(company, "ceo")
    client.post("/company/connections/demo", headers=_h(ceo, company))
    assert service.sync_due() == 0  # just pulled

    # A day on, with new books: pulled again, as the CEO.
    owner_conn.execute(
        "UPDATE connectors.connections SET last_synced_at = now() - interval '25 hours'"
    )
    owner_conn.execute("UPDATE intake.uploads SET sha256 = 'older'")
    assert service.sync_due() == 1
    dispatch_pending()
    uploads = _uploads(client, company)
    assert len(uploads) == 4
    added_by = owner_conn.execute("SELECT DISTINCT uploaded_by::text FROM intake.uploads")
    assert [r[0] for r in added_by.fetchall()] == [ceo.user_id]


def test_the_daily_pull_waits_when_that_person_no_longer_manages_tools(
    client, make_company, invite, demo, recorded_ai, owner_conn
):
    company = make_company()
    ceo = invite(company, "ceo")
    client.post("/company/connections/demo", headers=_h(ceo, company))
    owner_conn.execute(
        "UPDATE identity.memberships SET role = 'contributor', departments = '{sales}' "
        "WHERE user_id = %s",
        (ceo.user_id,),
    )
    later = datetime.now(UTC) + timedelta(days=2)
    assert service.sync_due(now=later) == 0
    tool = _tools(client, company)["demo"]
    assert tool["state"] == "failed"
    assert tool["last_error"] == (
        "ceo person no longer manages this company's tools. Connect it again to keep it up to date."
    )
    assert len(_uploads(client, company)) == 2


def test_one_company_never_sees_anothers_tools(client, make_company, demo, recorded_ai):
    a, b = make_company("Alpha"), make_company("Bravo")
    client.post("/company/connections/demo", headers=_h(a.owner, a))
    assert _tools(client, a)["demo"]["state"] == "connected"
    assert _tools(client, b)["demo"]["state"] == "available"
    r = client.delete("/company/connections/demo", headers=_h(b.owner, b))
    assert r.status_code == 404
    assert _tools(client, a)["demo"]["state"] == "connected"


def test_production_refuses_the_demo(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-secret-for-this-test-of-32-chars")
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("MAILER", "disabled")
    monkeypatch.setenv("CONNECTORS_DEMO", "true")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="CONNECTORS_DEMO"):
            get_settings()
    finally:
        get_settings.cache_clear()
