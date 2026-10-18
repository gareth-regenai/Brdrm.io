"""Tests run against a real Postgres, so row-level security is tested, not assumed.

TEST_ADMIN_DATABASE_URL points at a superuser connection. A fresh database is
created, migrated as the owner, and the app connects as br_login like production.
"""

import os
import subprocess
import sys
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
        "JWT_SECRET": "test-secret-at-least-16-chars",
        "WEB_ORIGIN": "http://web.test",
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
            "TRUNCATE identity.tenants, identity.users, identity.outbox, "
            "events.processed_events, audit.audit_log CASCADE"
        )
    from boardroom.modules.notify.mailer import memory_mailer

    memory_mailer().sent.clear()


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
