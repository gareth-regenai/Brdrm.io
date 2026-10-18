"""FR-11.5: an append-only audit log, and every state change emits an audit event."""

import psycopg
import pytest

from tests.conftest import upload_file
from tests.routes import all_routes

MUTATING = [r for r in all_routes() if r.method in ("POST", "PUT", "PATCH", "DELETE")]


def _count(owner_conn):
    return owner_conn.execute("SELECT count(*) FROM audit.audit_log").fetchone()[0]


def _audit_actions(owner_conn):
    return {a for (a,) in owner_conn.execute("SELECT action FROM audit.audit_log").fetchall()}


@pytest.fixture
def scenario(client, make_company, invite, owner_conn, recorded_ai):
    """Exercises every state-changing endpoint once and returns the audit actions it produced."""
    company = make_company()
    owner = company.owner
    h = owner.auth(company.tenant_id)
    lead = invite(company, "department_lead", ["sales"])
    investor = invite(company, "investor")
    r = client.post(
        "/company/invitations", headers=h, json={"email": "z@example.com", "role": "ceo"}
    )
    client.delete(f"/company/invitations/{r.json()['id']}", headers=h)
    client.put(
        "/company/settings/approval", headers=h, json={"roles": ["ceo"], "user_ids": [lead.user_id]}
    )
    client.delete(f"/company/investors/{investor.user_id}", headers=h)
    client.post("/companies", headers=owner.auth(), json={"name": "Second Co"})
    other = make_company()
    invite(other, "investor", existing=lead)
    client.post(
        "/auth/login", json={"email": owner.email, "password": "correct horse battery staple"}
    )
    client.post("/auth/refresh", json={"refresh_token": owner.refresh_token})
    client.post("/auth/logout", json={"refresh_token": lead.refresh_token})
    # Intake: one file with a question, one mapped by hand, one typed-in figure.
    asked = upload_file(client, company, "finance_ambiguous.csv")
    client.post(
        f"/company/uploads/{asked['id']}/answer",
        headers=h,
        json={"question_id": asked["question"]["id"], "answer": "yes"},
    )
    recorded_ai.override = {"not": "valid"}
    manual = upload_file(client, company, "quickbooks_monthly.csv")
    client.put(
        f"/company/uploads/{manual['id']}/mapping",
        headers=h,
        json={"kind": "finance", "columns": [{"column": "Income", "field": "revenue"}]},
    )
    client.post(
        "/company/figures",
        headers=h,
        json={"metric": "revenue", "period": "2026-12", "value": "1", "kind": "target"},
    )
    client.delete("/company", headers=h)
    return _audit_actions(owner_conn)


# Each state-changing endpoint and the audit event it must write.
EXPECTED = {
    ("POST", "/auth/signup"): "user.signed_up",
    ("POST", "/auth/login"): "auth.login",
    ("POST", "/auth/logout"): "auth.logout",
    ("POST", "/companies"): "company.created",
    ("DELETE", "/company"): "company.deleted",
    ("POST", "/company/invitations"): "invitation.created",
    ("DELETE", "/company/invitations/{invitation_id}"): "invitation.revoked",
    ("POST", "/invitations/accept"): "invitation.accepted",
    ("DELETE", "/company/investors/{user_id}"): "investor.removed",
    ("PUT", "/company/settings/approval"): "settings.approval_changed",
    ("POST", "/company/uploads"): "upload.started",
    ("POST", "/company/uploads/{upload_id}/complete"): "upload.added",
    ("POST", "/company/uploads/{upload_id}/answer"): "upload.question_answered",
    ("PUT", "/company/uploads/{upload_id}/mapping"): "upload.mapped_by_hand",
    ("POST", "/company/figures"): "figure.entered",
}
# A refresh swaps tokens only; the sign-in it continues is already audited.
NOT_STATE_CHANGES = {("POST", "/auth/refresh"), ("PUT", "/storage/upload/{token}")}
# The signed-link upload only places the file. Adding it is audited at /complete.


def test_every_state_changing_endpoint_has_an_expected_audit_event():
    routes = {(r.method, r.path) for r in MUTATING}
    assert routes - NOT_STATE_CHANGES == set(EXPECTED), "add the new endpoint to EXPECTED"


def test_every_state_change_emits_its_audit_event(scenario):
    missing = {route: action for route, action in EXPECTED.items() if action not in scenario}
    assert missing == {}
    assert "invitation.sent" in scenario


def test_investor_views_are_audited(client, make_company, invite, owner_conn):
    company = make_company()
    investor = invite(company, "investor")
    before = _count(owner_conn)
    # Opening the company is logged; the other requests the page makes are not.
    client.get("/company", headers=investor.auth(company.tenant_id))
    client.get("/company/investors", headers=investor.auth(company.tenant_id))
    client.get("/company", headers=investor.auth(company.tenant_id))
    viewed = owner_conn.execute(
        "SELECT count(*) FROM audit.audit_log "
        "WHERE action = 'investor.viewed' AND actor_user_id = %s",
        (investor.user_id,),
    ).fetchone()[0]
    assert viewed == 2 and _count(owner_conn) == before + 2


def test_audit_log_is_append_only(make_company, owner_conn):
    make_company()
    with pytest.raises(psycopg.errors.RaiseException):
        owner_conn.execute("UPDATE audit.audit_log SET action = 'changed'")
    with pytest.raises(psycopg.errors.RaiseException):
        owner_conn.execute("DELETE FROM audit.audit_log")


def test_app_role_cannot_change_audit_entries(make_company, owner_conn):
    company = make_company()
    with psycopg.connect(owner_conn.info.dsn, password=owner_conn.info.password) as conn:
        conn.execute("SET ROLE br_app")
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (company.tenant_id,))
        conn.execute("SELECT set_config('app.user_id', %s, false)", (company.owner.user_id,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM audit.audit_log")


def test_company_audit_view_shows_this_company_only(client, make_company):
    a, b = make_company(), make_company()
    entries = client.get("/company/audit", headers=a.owner.auth(a.tenant_id)).json()
    assert entries and all(b.tenant_id not in str(e) for e in entries)


def test_audit_details_hold_no_secrets(scenario, owner_conn):
    rows = owner_conn.execute("SELECT details::text FROM audit.audit_log").fetchall()
    for (details,) in rows:
        assert "password" not in details and "token" not in details
