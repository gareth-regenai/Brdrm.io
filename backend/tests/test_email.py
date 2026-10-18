"""Email over SMTP, checked against a real SMTP server running in the test."""

import socket
from collections.abc import Iterator
from email import message_from_bytes
from email.utils import parseaddr

import pytest
from aiosmtpd.controller import Controller

from boardroom.config import get_settings


class Inbox:
    def __init__(self) -> None:
        self.messages: list[tuple[str, list[str], bytes]] = []

    async def handle_DATA(self, server, session, envelope):  # noqa: ANN001, ANN201, N802
        self.messages.append((envelope.mail_from, envelope.rcpt_tos, envelope.content))
        return "250 OK"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def inbox(monkeypatch) -> Iterator[Inbox]:
    box = Inbox()
    port = _free_port()
    controller = Controller(box, hostname="127.0.0.1", port=port)
    controller.start()
    for key, value in {
        "MAILER": "smtp",
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": str(port),
        "SMTP_SECURITY": "none",
        "SMTP_FROM": "hello@boardroom.example.com",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield box
    controller.stop()
    get_settings.cache_clear()


def test_an_invitation_arrives_by_email(client, make_company, inbox):
    company = make_company("Northwind Analytics")
    r = client.post(
        "/company/invitations",
        headers=company.owner.auth(company.tenant_id),
        json={"email": "sam@seedfund.example.com", "role": "investor"},
    )
    assert r.status_code == 201
    assert len(inbox.messages) == 1
    sender, recipients, raw = inbox.messages[0]
    message = message_from_bytes(raw)
    assert sender == "hello@boardroom.example.com"
    assert recipients == ["sam@seedfund.example.com"]
    assert parseaddr(message["From"]) == ("BoardRoom.io", "hello@boardroom.example.com")
    assert message["Subject"] == "Join Northwind Analytics on BoardRoom.io"
    body = message.get_payload(decode=True).decode()
    assert "/invite?token=" in body


def test_the_emailed_link_lets_the_investor_join(client, make_company, inbox):
    company = make_company()
    client.post(
        "/company/invitations",
        headers=company.owner.auth(company.tenant_id),
        json={"email": "ivy@fund.example.com", "role": "investor"},
    )
    body = message_from_bytes(inbox.messages[0][2]).get_payload(decode=True).decode()
    token = body.split("token=")[1].split()[0]
    r = client.post(
        "/auth/signup",
        json={
            "email": "ivy@fund.example.com",
            "password": "correct horse battery staple",
            "name": "Ivy",
            "invite_token": token,
        },
    )
    assert r.status_code == 201 and r.json()["tenant_id"] == company.tenant_id


def test_a_failed_send_is_retried(client, make_company, monkeypatch, owner_conn):
    """With the mail server down the invitation is still created, and the email goes
    out on the next delivery round once the server is back."""
    from boardroom.events import dispatch_pending

    port = _free_port()
    for key, value in {
        "MAILER": "smtp",
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": str(port),
        "SMTP_SECURITY": "none",
        "SMTP_FROM": "hello@boardroom.example.com",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    company = make_company()
    r = client.post(
        "/company/invitations",
        headers=company.owner.auth(company.tenant_id),
        json={"email": "late@fund.example.com", "role": "investor"},
    )
    assert r.status_code == 201
    pending = owner_conn.execute(
        "SELECT count(*) FROM identity.outbox WHERE dispatched_at IS NULL"
    ).fetchone()[0]
    assert pending == 1

    box = Inbox()
    controller = Controller(box, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        dispatch_pending()
    finally:
        controller.stop()
        get_settings.cache_clear()
    assert [m[1] for m in box.messages] == [["late@fund.example.com"]]


@pytest.mark.parametrize(
    "env, ok",
    [
        ({"MAILER": "smtp", "SMTP_HOST": "smtp.gmail.com", "SMTP_FROM": "a@b.co"}, True),
        ({"MAILER": "smtp", "SMTP_HOST": "", "SMTP_FROM": "a@b.co"}, False),
        (
            {"MAILER": "smtp", "SMTP_HOST": "x", "SMTP_FROM": "a@b.co", "SMTP_SECURITY": "none"},
            False,
        ),
        ({"MAILER": "console"}, False),
        ({"MAILER": "disabled"}, True),
        # The journey tests' capture mailer runs on a preview, never in production.
        ({"MAILER": "capture"}, False),
        ({"MAILER": "capture", "ENVIRONMENT": "staging"}, True),
    ],
)
def test_production_email_settings(monkeypatch, env, ok):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-secret-for-this-test-of-32-chars")
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    try:
        if ok:
            get_settings()
        else:
            with pytest.raises(RuntimeError):
                get_settings()
    finally:
        get_settings.cache_clear()


def test_the_capture_mailbox_exists_only_in_capture_mode(client, make_company, monkeypatch):
    from fastapi.testclient import TestClient

    from boardroom.gateway.app import create_app

    # Off: no such route, and it is not public.
    assert client.get("/e2e/mail", params={"to": "a@b.co"}).status_code == 401
    monkeypatch.setattr(get_settings(), "mailer", "capture")
    with TestClient(create_app()) as capture:
        company = make_company()
        r = capture.post(
            "/company/invitations",
            headers=company.owner.auth(company.tenant_id),
            json={"email": "Priya@Fund.example.com", "role": "investor"},
        )
        assert r.status_code == 201, r.text
        [mail] = capture.get("/e2e/mail", params={"to": "priya@fund.example.com"}).json()
        assert "invite?token=" in mail["body"]
        assert capture.get("/e2e/mail", params={"to": "nobody@fund.example.com"}).json() == []
