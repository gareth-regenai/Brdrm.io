"""FR-2.6: the active tenant is part of every request and nothing crosses between companies."""

import psycopg
import pytest

from tests.routes import tenant_routes

GET_ROUTES = [r for r in tenant_routes() if r.method == "GET"]


@pytest.fixture
def two_companies(make_company, invite):
    a, b = make_company("Alpha Holdings"), make_company("Bravo Widgets")
    people = {}
    for company in (a, b):
        people[company.tenant_id] = {
            "owner": company.owner,
            "ceo": invite(company, "ceo"),
            "lead": invite(company, "department_lead", ["sales"]),
            "investor": invite(company, "investor"),
        }
    return a, b, people


@pytest.mark.parametrize("route", tenant_routes(), ids=lambda r: f"{r.method} {r.path}")
def test_no_one_in_one_company_can_act_on_the_other(route, client, two_companies):
    a, b, people = two_companies
    for account in people[a.tenant_id].values():
        r = client.request(route.method, route.url(), headers=account.auth(b.tenant_id), json={})
        assert r.status_code == 403, f"{route.method} {route.path}: {r.status_code}"


def test_responses_carry_no_data_from_the_other_company(client, two_companies, owner_conn):
    a, b, people = two_companies
    b_markers = {b.tenant_id, b.name}
    for account in people[b.tenant_id].values():
        b_markers |= {account.user_id, account.email}
    for account in people[a.tenant_id].values():
        for route in GET_ROUTES:
            r = client.get(route.url(), headers=account.auth(a.tenant_id))
            for marker in b_markers:
                assert marker not in r.text, f"{route.path} leaked {marker}"
        for path in ("/me", "/portfolio"):
            r = client.get(path, headers=account.auth())
            for marker in b_markers:
                assert marker not in r.text, f"{path} leaked {marker}"


def test_an_investor_in_both_sees_each_company_only_under_its_own_tenant(
    client, make_company, invite
):
    a, b = make_company("Alpha"), make_company("Bravo")
    investor = invite(a, "investor")
    invite(b, "investor", existing=investor)
    other_a = invite(a, "investor")
    r = client.get("/company/investors", headers=investor.auth(b.tenant_id))
    assert other_a.user_id not in r.text


def test_database_rows_are_invisible_across_tenants(two_companies, owner_conn):
    """Below the API: with tenant A set, the app role sees no row of tenant B in any table."""
    a, b, people = two_companies
    tables = owner_conn.execute(
        "SELECT schemaname || '.' || tablename FROM pg_tables "
        "WHERE schemaname IN ('identity', 'audit', 'events', 'intake', 'metrics') "
        "AND has_table_privilege('br_app', schemaname || '.' || tablename, 'SELECT')"
    ).fetchall()
    owner = people[a.tenant_id]["owner"]
    with psycopg.connect(owner_conn.info.dsn, password=owner_conn.info.password) as conn:
        conn.execute("SET ROLE br_app")
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (a.tenant_id,))
        conn.execute("SELECT set_config('app.user_id', %s, false)", (owner.user_id,))
        b_ids = {b.tenant_id} | {p.user_id for p in people[b.tenant_id].values()}
        for (table,) in tables:
            rows = conn.execute(f"SELECT row_to_json(t)::text FROM {table} t").fetchall()  # noqa: S608
            for (row,) in rows:
                for marker in b_ids:
                    assert marker not in row, f"{table} shows tenant B data"


def test_setting_another_tenant_without_membership_shows_nothing(two_companies, owner_conn):
    """Even if code set the wrong tenant, a non-member sees none of that company's rows."""
    a, b, people = two_companies
    outsider = people[a.tenant_id]["owner"]
    with psycopg.connect(owner_conn.info.dsn, password=owner_conn.info.password) as conn:
        conn.execute("SET ROLE br_app")
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (b.tenant_id,))
        conn.execute("SELECT set_config('app.user_id', %s, false)", (outsider.user_id,))
        users = conn.execute("SELECT id::text FROM identity.users").fetchall()
        assert {u for (u,) in users} == {outsider.user_id}
        for table in (
            "identity.invitations",
            "identity.company_settings",
            "audit.audit_log",
            "identity.outbox",
        ):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0, table  # noqa: S608
        tenants = conn.execute("SELECT id::text FROM identity.tenants").fetchall()
        assert b.tenant_id not in {t for (t,) in tenants}
        members = conn.execute("SELECT tenant_id::text FROM identity.memberships").fetchall()
        assert b.tenant_id not in {t for (t,) in members}
