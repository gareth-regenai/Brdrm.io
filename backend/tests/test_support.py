"""FR-11.6: staff support access is time-limited, logged and shown to the customer.

A platform admin opens a session on one company with a reason. Support reads what the
company sees and changes nothing, every page it opens is in the company's audit log, the
company sees who and why and until when, and can end it. It also ends by itself.
"""

import psycopg
import pytest

from boardroom.permissions import MATRIX, Role
from tests.conftest import upload_file
from tests.routes import tenant_routes


def _h(account, company):
    return account.auth(company.tenant_id)


@pytest.fixture
def opened(client, make_company, platform_admin, recorded_ai):
    """A company with an update awaiting approval, and an open support session on it."""
    company = make_company("Kestrel Field")
    upload_file(client, company, "xero_pnl.csv")
    r = client.post(
        f"/admin/support/{company.tenant_id}",
        headers=platform_admin.auth(),
        json={"reason": "Their September file is stuck at Calculating"},
    )
    assert r.status_code == 200, r.text
    return company, platform_admin, r.json()


def test_support_reads_what_the_company_sees(client, opened):
    company, staff, session = opened
    assert session["reason"] == "Their September file is stuck at Calculating"
    me = client.get("/me", headers=staff.auth()).json()
    assert {"tenant_id": company.tenant_id, "role": "support"}.items() <= next(
        m for m in me["memberships"] if m["tenant_id"] == company.tenant_id
    ).items()
    h = _h(staff, company)
    assert client.get("/company", headers=h).status_code == 200
    # What the company sees, including the update awaiting approval.
    [update] = client.get("/company/updates", headers=h).json()
    assert update["status"] == "awaiting_approval"
    assert client.get("/company/metrics", headers=h).json()["tiles"]
    assert client.get("/company/uploads", headers=h).status_code == 403  # files are the team's


def test_support_changes_nothing(client, opened):
    company, staff, _ = opened
    h = _h(staff, company)
    [update] = client.get("/company/updates", headers=_h(company.owner, company)).json()
    for method, path, body in [
        ("POST", f"/company/updates/{update['id']}/approve", None),
        ("POST", f"/company/updates/{update['id']}/comments", {"body": "Hello"}),
        ("POST", "/company/invitations", {"email": "x@example.com", "role": "ceo"}),
        ("PUT", "/company/settings/profile", {"reporting_currency": "EUR"}),
        ("DELETE", "/company/support", None),
    ]:
        r = client.request(method, path, headers=h, json=body)
        assert r.status_code == 403, f"{method} {path}: {r.status_code}"


def test_no_action_support_may_take_changes_anything():
    for route in tenant_routes():
        if Role.SUPPORT in MATRIX[route.action]:
            assert route.method == "GET", f"{route.method} {route.path} is open to support"


@pytest.mark.parametrize("route", tenant_routes(), ids=lambda r: f"{r.method} {r.path}")
def test_support_gets_exactly_what_the_matrix_allows(route, client, opened):
    company, staff, _ = opened
    r = client.request(route.method, route.url(), headers=_h(staff, company), json={})
    if Role.SUPPORT in MATRIX[route.action]:
        assert r.status_code != 403, r.text
    else:
        assert r.status_code == 403, f"support allowed: {r.status_code}"


def test_the_company_sees_who_why_and_until_when(client, opened):
    company, staff, session = opened
    client.get("/company/updates", headers=_h(staff, company))
    [shown] = client.get("/company/support", headers=_h(company.owner, company)).json()
    assert shown["staff_name"] == staff_name(staff, client)
    assert shown["reason"] == session["reason"] and shown["expires_at"] == session["expires_at"]
    entries = client.get("/company/audit", headers=_h(company.owner, company)).json()
    started = next(e for e in entries if e["action"] == "support.session_started")
    assert started["details"]["reason"] == session["reason"]
    viewed = [e["details"]["path"] for e in entries if e["action"] == "support.viewed"]
    assert "/company/updates" in viewed


def staff_name(account, client):
    return client.get("/me", headers=account.auth()).json()["name"]


def test_the_company_can_end_it_at_once(client, opened):
    company, staff, _ = opened
    assert client.delete("/company/support", headers=_h(company.owner, company)).status_code == 204
    assert client.get("/company", headers=_h(staff, company)).status_code == 403
    assert client.get("/company/support", headers=_h(company.owner, company)).json() == []
    me = client.get("/me", headers=staff.auth()).json()
    assert all(m["tenant_id"] != company.tenant_id for m in me["memberships"])


def test_it_ends_by_itself_in_the_api_and_the_database(client, opened, owner_conn):
    company, staff, _ = opened
    owner_conn.execute(
        "UPDATE identity.support_sessions SET expires_at = now() - interval '1 minute'"
    )
    assert client.get("/company", headers=_h(staff, company)).status_code == 403
    with psycopg.connect(owner_conn.info.dsn, password=owner_conn.info.password) as conn:
        conn.execute("SET ROLE br_app")
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (company.tenant_id,))
        conn.execute("SELECT set_config('app.user_id', %s, false)", (staff.user_id,))
        assert conn.execute("SELECT count(*) FROM updates.updates").fetchone()[0] == 0
        seen = conn.execute(
            "SELECT count(*) FROM identity.tenants WHERE id = %s", (company.tenant_id,)
        ).fetchone()[0]
        assert seen == 0


def test_the_database_gives_an_open_session_read_access(client, opened, owner_conn):
    company, staff, _ = opened
    with psycopg.connect(owner_conn.info.dsn, password=owner_conn.info.password) as conn:
        conn.execute("SET ROLE br_app")
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (company.tenant_id,))
        conn.execute("SELECT set_config('app.user_id', %s, false)", (staff.user_id,))
        # Including the update not yet shared, which an investor could not read.
        assert conn.execute("SELECT count(*) FROM updates.updates").fetchone()[0] == 1


def test_support_is_never_one_of_the_people(client, opened, invite):
    company, staff, _ = opened
    h = _h(company.owner, company)
    investor = invite(company, "investor")
    for path, account in [
        ("/company/team", company.owner),
        ("/company/investors", company.owner),
        ("/company/people", company.owner),
        ("/company/people", investor),
    ]:
        r = client.get(path, headers=_h(account, company))
        assert staff.user_id not in r.text, path
    r = client.post(
        "/company/invitations", headers=h, json={"email": "s@example.com", "role": "support"}
    )
    assert r.status_code == 422


def test_only_platform_admins_open_sessions_and_only_on_companies(
    client, make_company, invite, platform_admin
):
    company = make_company()
    body = {"reason": "Checking a figure"}
    r = client.post(f"/admin/support/{company.tenant_id}", headers=company.owner.auth(), json=body)
    assert r.status_code == 403
    investor = invite(company, "investor")
    portfolio = client.get("/me", headers=investor.auth()).json()["memberships"]
    assert all(m["tenant_type"] == "company" for m in portfolio)
    r = client.post(
        "/admin/support/00000000-0000-0000-0000-000000000000",
        headers=platform_admin.auth(),
        json=body,
    )
    assert r.status_code == 404


def test_a_session_on_one_company_reads_no_other(client, opened, make_company):
    _, staff, _ = opened
    other = make_company("Bravo")
    assert client.get("/company", headers=_h(staff, other)).status_code == 403
