"""FR-10.7: events go through an outbox per module and are delivered at least once to
idempotent consumers."""

import uuid

from boardroom.db import system_session
from boardroom.events import Event, consumer, deliver, dispatch_pending
from boardroom.modules.notify.mailer import memory_mailer


def test_duplicate_events_cause_no_double_processing(client, make_company, owner_conn):
    company = make_company()
    r = client.post(
        "/company/invitations",
        headers=company.owner.auth(company.tenant_id),
        json={"email": "dup@example.com", "role": "ceo"},
    )
    assert r.status_code == 201
    assert len([e for e in memory_mailer().sent if e.to == "dup@example.com"]) == 1
    # Simulate redelivery: the dispatcher sees the same event again.
    owner_conn.execute("UPDATE identity.outbox SET dispatched_at = NULL")
    dispatch_pending()
    dispatch_pending()
    assert len([e for e in memory_mailer().sent if e.to == "dup@example.com"]) == 1


def test_a_failing_consumer_leaves_the_event_for_retry(owner_conn):
    calls: list[uuid.UUID] = []
    event_type = f"test.flaky.{uuid.uuid4().hex}"

    @consumer("test.flaky", event_type)
    def flaky(session, event):  # noqa: ANN001, ANN202
        calls.append(event.id)
        if len(calls) == 1:
            raise RuntimeError("temporary failure")

    event = Event(uuid.uuid4(), None, event_type, {})
    with system_session() as session:
        try:
            with session.begin_nested():
                deliver(session, event)
        except RuntimeError:
            pass
    with system_session() as session:
        assert deliver(session, event) == 1
    with system_session() as session:
        assert deliver(session, event) == 0
    assert len(calls) == 2


def test_events_are_written_in_the_same_transaction_as_the_change(client, make_company, owner_conn):
    company = make_company()
    r = client.post(
        "/company/invitations",
        headers=company.owner.auth(company.tenant_id),
        json={"email": "bad", "role": "ceo"},
    )
    assert r.status_code == 422
    assert owner_conn.execute("SELECT count(*) FROM identity.outbox").fetchone()[0] == 0
