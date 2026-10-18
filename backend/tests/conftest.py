"""Tests run against a real Postgres, so row-level security is tested, not assumed.

TEST_ADMIN_DATABASE_URL points at a superuser connection. A fresh database is
created, migrated as the owner, and the app connects as br_login like production.
"""

import os
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

ADMIN_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
)
TEST_DB = "boardroom_test"
APP_PASSWORD = "br_login_test"
BACKEND = Path(__file__).resolve().parents[1]


def _db_url(user: str, password: str) -> str:
    base = psycopg.conninfo.conninfo_to_dict(ADMIN_URL)
    host = base.get("host", "localhost")
    port = base.get("port", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{TEST_DB}"


OWNER_URL = _db_url(
    psycopg.conninfo.conninfo_to_dict(ADMIN_URL).get("user", "postgres") or "postgres",
    psycopg.conninfo.conninfo_to_dict(ADMIN_URL).get("password", "") or "",
)

os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": _db_url("br_login", APP_PASSWORD),
        "MAILER": "memory",
        "DISPATCH_INLINE": "true",
        "JWT_SECRET": "test-secret-at-least-32-characters-long",
        "WEB_ORIGIN": "http://web.test",
        "API_URL": "http://testserver",
        "STORAGE_BACKEND": "local",
        "STORAGE_ROOT": tempfile.mkdtemp(prefix="boardroom-storage-"),
        "ANTHROPIC_API_KEY": "",
        "PARSE_MEMORY_MB": "1024",
        "PARSE_SECONDS": "20",
    }
)


def pytest_sessionstart(session: pytest.Session) -> None:
    with psycopg.connect(ADMIN_URL, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND,
        env={**os.environ, "MIGRATION_DATABASE_URL": OWNER_URL, "APP_DB_PASSWORD": APP_PASSWORD},
        check=True,
    )


@pytest.fixture
def owner_conn() -> Iterator[psycopg.Connection]:
    """A superuser connection for test setup and for checking what is stored."""
    with psycopg.connect(OWNER_URL, autocommit=True) as conn:
        yield conn


@pytest.fixture(autouse=True)
def clean_db() -> Iterator[None]:
    yield
    with psycopg.connect(OWNER_URL, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE identity.support_sessions, identity.tenants, identity.users, "
            "identity.outbox, events.processed_events, audit.audit_log, intake.uploads, "
            "intake.layouts, "
            "intake.interpretation_log, intake.manual_figures, intake.outbox, metrics.selections, "
            "metrics.runs, metrics.settings, metrics.outbox, setup.profiles, setup.targets, "
            "setup.conversations, setup.outbox, updates.updates, updates.outbox, "
            "billing.subscriptions, billing.stripe_events, billing.plans, connectors.connections "
            "CASCADE"
        )
    import shutil

    from boardroom.modules.notify.mailer import memory_mailer

    memory_mailer().sent.clear()
    shutil.rmtree(os.environ["STORAGE_ROOT"], ignore_errors=True)


@pytest.fixture
def client() -> Iterator[TestClient]:
    from boardroom.gateway.app import app

    with TestClient(app) as c:
        yield c


PASSWORD = "correct horse battery staple"


@dataclass
class Account:
    user_id: str
    email: str
    access_token: str
    refresh_token: str

    def auth(self, tenant_id: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.access_token}"}
        if tenant_id:
            headers["X-Tenant-ID"] = tenant_id
        return headers


@dataclass
class Company:
    tenant_id: str
    name: str
    owner: Account


def _account(client: TestClient, body: dict[str, object]) -> tuple[Account, str | None]:
    r = client.post("/auth/signup", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    me = client.get("/me", headers={"Authorization": f"Bearer {data['access_token']}"}).json()
    return Account(me["id"], me["email"], data["access_token"], data["refresh_token"]), data[
        "tenant_id"
    ]


@pytest.fixture
def make_company(client: TestClient):
    def make(name: str | None = None) -> Company:
        name = name or f"Company {uuid.uuid4().hex[:6]}"
        email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
        account, tenant_id = _account(
            client,
            {
                "email": email,
                "password": PASSWORD,
                "name": f"Owner of {name}",
                "company_name": name,
            },
        )
        assert tenant_id
        return Company(tenant_id, name, account)

    return make


def last_invite_token(email: str) -> str:
    from boardroom.modules.notify.mailer import memory_mailer

    for sent in reversed(memory_mailer().sent):
        if sent.to == email:
            return sent.body.split("token=")[1].split()[0]
    raise AssertionError(f"no invitation email to {email}")


@pytest.fixture
def invite(client: TestClient):
    """Invite someone into a company and have them sign up or accept. Returns their account."""

    def do(
        company: Company,
        role: str,
        departments: list[str] | None = None,
        email: str | None = None,
        existing: Account | None = None,
        by: Account | None = None,
    ) -> Account:
        email = (
            existing.email if existing else (email or f"{role}-{uuid.uuid4().hex[:8]}@example.com")
        )
        inviter = by or company.owner
        r = client.post(
            "/company/invitations",
            headers=inviter.auth(company.tenant_id),
            json={"email": email, "role": role, "departments": departments or []},
        )
        assert r.status_code == 201, r.text
        token = last_invite_token(email)
        if existing:
            r = client.post("/invitations/accept", headers=existing.auth(), json={"token": token})
            assert r.status_code == 200, r.text
            return existing
        account, tenant_id = _account(
            client,
            {"email": email, "password": PASSWORD, "name": f"{role} person", "invite_token": token},
        )
        assert tenant_id == company.tenant_id
        return account

    return do


# Intake helpers

FIXTURES = Path(__file__).parent / "fixtures"


class RecordedClient:
    """Replays recorded skill 1 responses (FR-13.2) and keeps every payload, so tests
    can check what the model would have been sent."""

    def __new__(cls) -> "RecordedClient":
        from boardroom.modules.intake.replay import ReplayClient

        return ReplayClient(FIXTURES / "recorded")  # type: ignore[return-value]

    payloads: list[dict[str, str]]
    override: object | None


@pytest.fixture
def recorded_ai() -> Iterator[RecordedClient]:
    from boardroom.modules.intake import skill1

    client = RecordedClient()
    skill1.set_client(client)
    yield client
    skill1.set_client(None)


@pytest.fixture(autouse=True)
def _no_live_ai() -> Iterator[None]:
    """CI never calls the live API: without a recorded client, the AI is off."""
    from boardroom.modules.insights import skill3
    from boardroom.modules.intake import skill1

    skill1.set_client(None)
    skill3.set_client(None)
    yield
    skill1.set_client(None)
    skill3.set_client(None)


def upload_file(
    client: TestClient,
    company: Company,
    name: str,
    data: bytes | None = None,
    account: Account | None = None,
) -> dict:
    data = data if data is not None else (FIXTURES / "files" / name).read_bytes()
    who = account or company.owner
    r = client.post(
        "/company/uploads",
        headers=who.auth(company.tenant_id),
        json={"filename": name, "size_bytes": len(data), "content_type": "text/csv"},
    )
    assert r.status_code == 201, r.text
    link = r.json()
    put = client.put(
        link["url"].replace("http://testserver", ""), content=data, headers=link["headers"]
    )
    assert put.status_code == 204, put.text
    r = client.post(
        f"/company/uploads/{link['upload_id']}/complete", headers=who.auth(company.tenant_id)
    )
    assert r.status_code == 200, r.text
    r = client.get(f"/company/uploads/{link['upload_id']}", headers=who.auth(company.tenant_id))
    return r.json()


def stored_keys() -> list[str]:
    from boardroom.modules.intake.storage import get_storage

    return get_storage().all_keys()  # type: ignore[attr-defined]


def png_data_url(size: tuple[int, int] = (120, 40), colour: str = "#1F5F8F") -> str:
    """A small logo, as the browser sends it."""
    import base64
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", size, colour).save(out, format="PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


# Billing: a recorded payment client and signed Stripe events, so CI never calls Stripe.

WEBHOOK_SECRET = "whsec_test_secret"


class RecordedPayments:
    def __init__(self) -> None:
        self.checkouts: list[dict] = []
        self.portals: list[dict] = []

    def checkout_url(self, **kwargs) -> str:
        self.checkouts.append(kwargs)
        return f"https://checkout.stripe.test/c/{len(self.checkouts)}"

    def portal_url(self, **kwargs) -> str:
        self.portals.append(kwargs)
        return "https://billing.stripe.test/p/1"


@dataclass
class Stripe:
    client: TestClient
    owner_conn: psycopg.Connection
    payments: RecordedPayments

    def plan(self, key: str, *, price: str | None = None, default: bool = False, **limits):
        """Set a plan straight in the database, as a platform admin's change would."""
        import json

        self.owner_conn.execute(
            "INSERT INTO billing.plans (key, name, stripe_price_id, entitlements, is_default) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (key) DO UPDATE SET "
            "stripe_price_id = EXCLUDED.stripe_price_id, entitlements = EXCLUDED.entitlements, "
            "is_default = EXCLUDED.is_default",
            (key, key.title(), price, json.dumps(limits), default),
        )

    def send(self, event: dict, secret: str = WEBHOOK_SECRET):
        import hashlib
        import hmac
        import json
        import time

        payload = json.dumps(event)
        stamp = int(time.time())
        mac = hmac.new(secret.encode(), f"{stamp}.{payload}".encode(), hashlib.sha256)
        return self.client.post(
            "/billing/stripe/webhook",
            content=payload,
            headers={
                "Stripe-Signature": f"t={stamp},v1={mac.hexdigest()}",
                "Content-Type": "application/json",
            },
        )


_event_seq = iter(range(1, 1_000_000))


def subscription_event(
    tenant_id: str | None,
    price: str,
    status: str = "active",
    kind: str = "updated",
    created: int = 1_790_000_000,
    sub_id: str = "sub_1",
    event_id: str | None = None,
) -> dict:
    return {
        "id": event_id or f"evt_{next(_event_seq)}",
        "type": f"customer.subscription.{kind}",
        "created": created,
        "data": {
            "object": {
                "id": sub_id,
                "object": "subscription",
                "customer": f"cus_for_{sub_id}",
                "status": status,
                "metadata": {"tenant_id": tenant_id} if tenant_id else {},
                "items": {
                    "data": [{"price": {"id": price}, "current_period_end": created + 2_592_000}]
                },
            }
        },
    }


@pytest.fixture
def stripe(client, owner_conn, monkeypatch) -> Iterator[Stripe]:
    from boardroom.config import get_settings
    from boardroom.modules.billing import payments

    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", WEBHOOK_SECRET)
    recorded = RecordedPayments()
    payments.set_payments(recorded)
    yield Stripe(client, owner_conn, recorded)
    payments.set_payments(None)


@pytest.fixture
def platform_admin(make_company, owner_conn) -> Account:
    """A BoardRoom staff account. Platform admins are set in the database, never by the API."""
    company = make_company("BoardRoom staff")
    owner_conn.execute(
        "UPDATE identity.users SET is_platform_admin = true WHERE id = %s",
        (company.owner.user_id,),
    )
    return company.owner
