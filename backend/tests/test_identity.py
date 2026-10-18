"""FRD chapter 2: users, tenants and roles."""

from datetime import UTC, datetime, timedelta

import jwt
from fastapi.testclient import TestClient

from tests.conftest import PASSWORD, last_invite_token


def test_signup_creates_one_company_with_the_user_as_owner(client, make_company, owner_conn):
    # FR-2.1
    company = make_company("Acme Ltd")
    me = client.get("/me", headers=company.owner.auth()).json()
    assert [(m["tenant_name"], m["role"]) for m in me["memberships"]] == [("Acme Ltd", "owner")]
    count = owner_conn.execute("SELECT count(*) FROM identity.tenants").fetchone()[0]
    assert count == 1


def test_invited_user_has_only_their_roles_permissions(client, make_company, invite):
    # FR-2.2
    company = make_company()
    lead = invite(company, "department_lead", ["sales", "people"])
    perms = client.get("/company/permissions", headers=lead.auth(company.tenant_id)).json()
    assert perms["role"] == "department_lead"
    assert "invite_users" not in perms["actions"]
    assert "upload_files" in perms["actions"]
    me = client.get("/me", headers=lead.auth()).json()
    assert me["memberships"][0]["departments"] == ["sales", "people"]
    r = client.post(
        "/company/invitations",
        headers=lead.auth(company.tenant_id),
        json={"email": "x@example.com", "role": "contributor", "departments": ["sales"]},
    )
    assert r.status_code == 403


def test_contributor_needs_exactly_one_department(client, make_company):
    company = make_company()
    for departments in ([], ["sales", "people"]):
        r = client.post(
            "/company/invitations",
            headers=company.owner.auth(company.tenant_id),
            json={"email": "c@example.com", "role": "contributor", "departments": departments},
        )
        assert r.status_code == 422


def test_owner_cannot_be_invited(client, make_company):
    company = make_company()
    r = client.post(
        "/company/invitations",
        headers=company.owner.auth(company.tenant_id),
        json={"email": "o@example.com", "role": "owner"},
    )
    assert r.status_code == 422


def test_investor_access_is_standing_from_one_invite(client, make_company, invite):
    # FR-2.3: the invite is the access. Nothing else is granted per update.
    # E5 adds updates; this proves the investor reaches the company with no further step.
    company = make_company()
    investor = invite(company, "investor")
    r = client.get("/company", headers=investor.auth(company.tenant_id))
    assert r.status_code == 200
    assert r.json()["name"] == company.name


def test_one_investor_login_holds_many_companies(client, make_company, invite):
    # FR-2.4
    a, b, c = make_company("Alpha"), make_company("Bravo"), make_company("Charlie")
    investor = invite(a, "investor")
    invite(b, "investor", existing=investor)
    invite(c, "investor", existing=investor)
    portfolio = client.get("/portfolio", headers=investor.auth()).json()
    assert [p["name"] for p in portfolio] == ["Alpha", "Bravo", "Charlie"]


def test_co_investors_see_each_other_and_no_one_else(client, make_company, invite):
    # FR-2.5
    x, y = make_company("X"), make_company("Y")
    investor_a = invite(x, "investor")
    investor_b = invite(x, "investor")
    investor_c = invite(y, "investor")
    names = client.get("/company/investors", headers=investor_a.auth(x.tenant_id)).json()
    ids = {p["user_id"] for p in names}
    assert ids == {investor_a.user_id, investor_b.user_id}
    assert investor_c.user_id not in ids
    # Investors see names, not email addresses.
    assert all(p["email"] is None for p in names)


def test_changing_approval_permission_changes_who_can_approve(client, make_company, invite):
    # FR-2.7
    company = make_company()
    ceo = invite(company, "ceo")
    lead = invite(company, "department_lead", ["sales"])

    def can(account):
        return client.get("/company/permissions", headers=account.auth(company.tenant_id)).json()[
            "can_approve"
        ]

    assert (can(company.owner), can(ceo), can(lead)) == (True, True, False)
    r = client.put(
        "/company/settings/approval",
        headers=company.owner.auth(company.tenant_id),
        json={"roles": [], "user_ids": [lead.user_id]},
    )
    assert r.status_code == 200, r.text
    assert (can(company.owner), can(ceo), can(lead)) == (True, False, True)


def test_approval_cannot_go_to_investors_or_contributors(client, make_company, invite):
    company = make_company()
    investor = invite(company, "investor")
    r = client.put(
        "/company/settings/approval",
        headers=company.owner.auth(company.tenant_id),
        json={"roles": ["investor"], "user_ids": []},
    )
    assert r.status_code == 422
    r = client.put(
        "/company/settings/approval",
        headers=company.owner.auth(company.tenant_id),
        json={"roles": ["ceo"], "user_ids": [investor.user_id]},
    )
    assert r.status_code == 422


def test_removing_an_investor_blocks_their_next_request(client, make_company, invite):
    # FR-2.8
    company = make_company()
    investor = invite(company, "investor")
    assert client.get("/company", headers=investor.auth(company.tenant_id)).status_code == 200
    r = client.delete(
        f"/company/investors/{investor.user_id}", headers=company.owner.auth(company.tenant_id)
    )
    assert r.status_code == 204
    assert client.get("/company", headers=investor.auth(company.tenant_id)).status_code == 403


def test_removed_investor_can_be_invited_back(client, make_company, invite):
    company = make_company()
    investor = invite(company, "investor")
    client.delete(
        f"/company/investors/{investor.user_id}", headers=company.owner.auth(company.tenant_id)
    )
    invite(company, "investor", existing=investor)
    assert client.get("/company", headers=investor.auth(company.tenant_id)).status_code == 200


def test_deal_team_is_reserved_in_the_schema(owner_conn):
    # FR-2.9: the value exists; test_architecture checks that no route uses it.
    check = owner_conn.execute(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'identity.tenants'::regclass AND contype = 'c'"
    ).fetchone()[0]
    assert "deal_team" in check


def test_deleted_workspace_blocks_everyone(client, make_company, invite):
    company = make_company()
    investor = invite(company, "investor")
    assert (
        client.delete("/company", headers=company.owner.auth(company.tenant_id)).status_code == 204
    )
    for account in (company.owner, investor):
        assert client.get("/company", headers=account.auth(company.tenant_id)).status_code == 403


# Invitation abuse


def _send_invite(client, company, email, role="ceo"):
    r = client.post(
        "/company/invitations",
        headers=company.owner.auth(company.tenant_id),
        json={"email": email, "role": role},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"], last_invite_token(email)


def test_invitation_only_works_for_the_invited_email(client, make_company):
    company = make_company()
    _, token = _send_invite(client, company, "right@example.com")
    r = client.post(
        "/auth/signup",
        json={
            "email": "wrong@example.com",
            "password": PASSWORD,
            "name": "W",
            "invite_token": token,
        },
    )
    assert r.status_code == 403


def test_invitation_works_once(client, make_company):
    company = make_company()
    _, token = _send_invite(client, company, "once@example.com")
    body = {"email": "once@example.com", "password": PASSWORD, "name": "O", "invite_token": token}
    assert client.post("/auth/signup", json=body).status_code == 201
    body["email"] = "once@example.com"
    assert client.post("/auth/signup", json=body).status_code in (404, 409)


def test_revoked_invitation_does_not_work(client, make_company):
    company = make_company()
    invitation_id, token = _send_invite(client, company, "rev@example.com")
    r = client.delete(
        f"/company/invitations/{invitation_id}", headers=company.owner.auth(company.tenant_id)
    )
    assert r.status_code == 204
    r = client.post(
        "/auth/signup",
        json={"email": "rev@example.com", "password": PASSWORD, "name": "R", "invite_token": token},
    )
    assert r.status_code == 404


def test_expired_invitation_does_not_work(client, make_company, owner_conn):
    company = make_company()
    _, token = _send_invite(client, company, "old@example.com")
    owner_conn.execute("UPDATE identity.invitations SET expires_at = now() - interval '1 day'")
    r = client.post(
        "/auth/signup",
        json={"email": "old@example.com", "password": PASSWORD, "name": "O", "invite_token": token},
    )
    assert r.status_code == 410


def test_invitation_tokens_are_stored_only_as_hashes(client, make_company, owner_conn):
    company = make_company()
    _, token = _send_invite(client, company, "hash@example.com")
    stored = owner_conn.execute("SELECT token_hash FROM identity.invitations").fetchone()[0]
    assert token not in stored and len(stored) == 64


def test_cannot_invite_someone_already_in_the_company(client, make_company, invite):
    company = make_company()
    ceo = invite(company, "ceo")
    r = client.post(
        "/company/invitations",
        headers=company.owner.auth(company.tenant_id),
        json={"email": ceo.email, "role": "investor"},
    )
    assert r.status_code == 409


# Tokens


def test_tampered_and_expired_tokens_are_refused(client: TestClient, make_company):
    company = make_company()
    good = company.owner.access_token
    tampered = good[:-2] + ("AA" if good[-2:] != "AA" else "BB")
    forged = jwt.encode(
        {
            "sub": company.owner.user_id,
            "iss": "boardroom.io",
            "typ": "access",
            "iat": 0,
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        },
        "some-other-secret-value",
        algorithm="HS256",
    )
    expired = jwt.encode(
        {
            "sub": company.owner.user_id,
            "iss": "boardroom.io",
            "typ": "access",
            "iat": 0,
            "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
        },
        "test-secret-at-least-16-chars",
        algorithm="HS256",
    )
    for token in (tampered, forged, expired, "", "not-a-jwt"):
        r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, token


def test_refresh_tokens_rotate_and_work_once(client, make_company):
    company = make_company()
    first = company.owner.refresh_token
    r = client.post("/auth/refresh", json={"refresh_token": first})
    assert r.status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": first}).status_code == 401
    second = r.json()["refresh_token"]
    assert (
        client.get(
            "/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}
        ).status_code
        == 200
    )
    client.post("/auth/logout", json={"refresh_token": second})
    assert client.post("/auth/refresh", json={"refresh_token": second}).status_code == 401


def test_login_with_wrong_password_is_refused_and_audited(client, make_company, owner_conn):
    company = make_company()
    r = client.post(
        "/auth/login", json={"email": company.owner.email, "password": "wrong password"}
    )
    assert r.status_code == 401
    r = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "wrong password"}
    )
    assert r.status_code == 401
    failed = owner_conn.execute(
        "SELECT count(*) FROM audit.audit_log WHERE action = 'auth.login_failed'"
    ).fetchone()[0]
    assert failed == 2
    r = client.post("/auth/login", json={"email": company.owner.email, "password": PASSWORD})
    assert r.status_code == 200


def test_company_roles_cannot_reach_the_portfolio(client, make_company):
    # FR-7.7, in place from E1.
    company = make_company()
    assert client.get("/portfolio", headers=company.owner.auth()).status_code == 403
