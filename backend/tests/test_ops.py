"""FR-12.4: health signals and alerts on queue depth, the AI error rate and login failures.
Accept: each alert fires in a staged fault test. Logs carry no data values."""

import pytest
from fastapi.testclient import TestClient

from boardroom import events, ops
from boardroom.config import get_settings
from boardroom.modules.notify.mailer import memory_mailer
from tests.conftest import upload_file


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    ops.reset()
    yield
    ops.reset()


def _keys():
    return [a.key for a in ops.check()]


def test_a_healthy_system_raises_nothing(client, make_company, recorded_ai):
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    assert _keys() == []


def test_the_queue_alert_fires_when_events_wait(owner_conn):
    owner_conn.execute(
        "INSERT INTO intake.outbox (id, event_type, payload, created_at) VALUES "
        "(gen_random_uuid(), 'intake.upload_received', '{}', now() - interval '20 minutes')"
    )
    [alert] = ops.check()
    assert alert.key == "queue" and "1 events" in alert.message


def test_the_queue_alert_fires_when_a_file_is_stuck(client, make_company, recorded_ai, owner_conn):
    company = make_company()
    upload_file(client, company, "xero_pnl.csv")
    owner_conn.execute(
        "UPDATE intake.uploads "
        "SET status = 'calculating', updated_at = now() - interval '30 minutes'"
    )
    [alert] = ops.check()
    assert alert.key == "queue" and "1 files" in alert.message


def _ai_calls(owner_conn, tenant_id, failed, worked):
    for error in ["Model unavailable"] * failed + [None] * worked:
        owner_conn.execute(
            "INSERT INTO intake.interpretation_log "
            "(id, tenant_id, upload_id, source, error, dropped) "
            "VALUES (gen_random_uuid(), %s, gen_random_uuid(), %s, %s, '[]')",
            (tenant_id, "fallback" if error else "ai", error),
        )


@pytest.mark.parametrize(
    "failed, worked, fires",
    [(2, 2, True), (1, 3, True), (1, 4, False), (3, 0, False)],  # last: too few to judge
)
def test_the_ai_alert_fires_on_the_error_rate(make_company, owner_conn, failed, worked, fires):
    company = make_company()
    _ai_calls(owner_conn, company.tenant_id, failed, worked)
    assert ("ai_errors" in _keys()) is fires


def test_the_login_alert_fires_on_failed_sign_ins(client, make_company, monkeypatch):
    monkeypatch.setattr(get_settings(), "alert_login_failures", 3)
    company = make_company()
    for _ in range(2):
        client.post("/auth/login", json={"email": company.owner.email, "password": "wrong one!"})
    assert _keys() == []
    client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong one!"})
    assert _keys() == ["login_failures"]


def test_an_alert_is_emailed_once_an_hour(owner_conn, monkeypatch):
    monkeypatch.setattr(get_settings(), "ops_alert_email", "ops@boardroom.example.com")
    owner_conn.execute(
        "INSERT INTO metrics.outbox (id, event_type, payload, created_at) "
        "VALUES (gen_random_uuid(), 'metrics.run_finished', '{}', now() - interval '1 hour')"
    )
    memory_mailer().sent.clear()
    ops.check()
    ops.check()
    [mail] = memory_mailer().sent
    assert mail.to == "ops@boardroom.example.com" and mail.subject == "BoardRoom alert: queue"


def test_every_outbox_is_watched():
    import boardroom.worker  # noqa: F401  registers every module's outbox

    watched = set(ops.OUTBOXES)
    registered = {
        f"{m.__table__.schema}.{m.__tablename__}"  # type: ignore[attr-defined]
        for m in events._outboxes
    }
    assert watched == registered


def test_an_unexpected_error_is_logged_without_its_message(make_company, monkeypatch, capsys):
    from boardroom.gateway.app import create_app
    from boardroom.modules.identity import service as identity

    def broken(*_args, **_kwargs):
        raise ValueError("Revenue 48,213.07 for Harbour Robotics")

    monkeypatch.setattr(identity, "get_company", broken)
    company = make_company()
    with TestClient(create_app(), raise_server_exceptions=False) as app:
        r = app.get("/company", headers=company.owner.auth(company.tenant_id))
    assert r.status_code == 500
    assert r.json()["detail"] == "Something went wrong on our side. Try again in a moment."
    logged = capsys.readouterr().out
    assert '"unhandled_error"' in logged and '"ValueError"' in logged
    assert "Harbour" not in logged and "48,213" not in logged
