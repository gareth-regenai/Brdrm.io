"""FR-11.2: a role-by-endpoint matrix generated from the API, which must pass at 100%."""

import pytest

from boardroom.permissions import MATRIX, Role
from tests.routes import all_routes, openapi_operations, tenant_routes, unguarded_routes

ROLES = [Role.OWNER, Role.CEO, Role.DEPARTMENT_LEAD, Role.CONTRIBUTOR, Role.INVESTOR]
DEPARTMENTS = {Role.DEPARTMENT_LEAD: ["sales"], Role.CONTRIBUTOR: ["finance"]}


def test_route_discovery_finds_every_documented_endpoint():
    assert {(r.method, r.path) for r in all_routes()} == openapi_operations()


def test_every_endpoint_is_public_user_level_or_declares_an_action():
    assert unguarded_routes() == []


def test_matrix_covers_every_tenant_endpoint():
    routes = tenant_routes()
    assert routes, "no tenant endpoints found"
    for route in routes:
        assert route.action in MATRIX


@pytest.mark.parametrize("route", tenant_routes(), ids=lambda r: f"{r.method} {r.path}")
def test_each_role_gets_exactly_what_the_matrix_allows(route, client, make_company, invite):
    company = make_company()
    accounts = {Role.OWNER: company.owner}
    for role in ROLES[1:]:
        accounts[role] = invite(company, role.value, DEPARTMENTS.get(role))
    # The Owner last, since some actions (deleting the workspace) end the company.
    for role in ROLES[1:] + [Role.OWNER]:
        r = client.request(
            route.method, route.url(), headers=accounts[role].auth(company.tenant_id), json={}
        )
        expected_allowed = role in MATRIX[route.action]
        if expected_allowed:
            assert r.status_code != 403, f"{role} refused: {r.text}"
        else:
            assert r.status_code == 403, f"{role} allowed: {r.status_code} {r.text}"
