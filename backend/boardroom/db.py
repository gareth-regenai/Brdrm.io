"""Database access with the tenant set per transaction (FR-2.6, FR-11.1).

The app's login role has no table rights. Each transaction switches role:

- ``br_app``: row-level security applies, scoped by ``app.tenant_id`` and
  ``app.user_id``. Every request runs here.
- ``br_system``: sees every row. Used only for the few steps that happen
  before a tenant or user is known (login, refresh, invitation lookup) and by
  the outbox dispatcher. Callers are listed in tests/test_architecture.py.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from boardroom.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def _set_context(session: Session, user_id: uuid.UUID | None, tenant_id: uuid.UUID | None) -> None:
    session.execute(
        text(
            "SELECT set_config('app.user_id', :user_id, true),"
            " set_config('app.tenant_id', :tenant_id, true)"
        ),
        {
            "user_id": str(user_id) if user_id else "",
            "tenant_id": str(tenant_id) if tenant_id else "",
        },
    )


def set_tenant(session: Session, user_id: uuid.UUID | None, tenant_id: uuid.UUID | None) -> None:
    """Move an open app session to another tenant, for example a company just created."""
    _set_context(session, user_id, tenant_id)


@contextmanager
def app_session(
    user_id: uuid.UUID | None = None, tenant_id: uuid.UUID | None = None
) -> Iterator[Session]:
    with _session_factory()() as session, session.begin():
        session.execute(text("SET LOCAL ROLE br_app"))
        _set_context(session, user_id, tenant_id)
        yield session


@contextmanager
def as_system(session: Session) -> Iterator[None]:
    """Run part of an app transaction as br_system, for a step the app role may not take
    itself, such as joining a company once its invitation is checked."""
    session.flush()
    session.execute(text("SET LOCAL ROLE br_system"))
    yield
    # On an error the transaction rolls back, and SET LOCAL goes with it.
    session.flush()
    session.execute(text("SET LOCAL ROLE br_app"))


@contextmanager
def system_session() -> Iterator[Session]:
    with _session_factory()() as session, session.begin():
        session.execute(text("SET LOCAL ROLE br_system"))
        yield session
