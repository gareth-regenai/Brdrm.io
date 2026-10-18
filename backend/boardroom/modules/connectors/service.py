"""Connecting a company's tools, and pulling from them on demand and once a day.

What a tool sends becomes an upload (intake.add_pulled_file), so the pay columns are
dropped, the AI reads it, code calculates the figures and an update is drafted, exactly as
for a file. Nothing here touches a figure.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from boardroom.config import get_settings
from boardroom.db import app_session, system_session
from boardroom.logs import get_logger
from boardroom.modules.audit import service as audit
from boardroom.modules.connectors.models import Connection
from boardroom.modules.connectors.providers import PROVIDERS, Provider, PullFailed
from boardroom.modules.identity import service as identity
from boardroom.modules.intake import service as intake
from boardroom.permissions import Action, allowed

log = get_logger(__name__)

# Connected tools are pulled again once a day, by the worker.
SYNC_EVERY = timedelta(hours=24)


class ConnectorError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Tool:
    key: str
    name: str
    department: str
    sends: str
    # connected, failed, available, coming_soon, phase_2
    state: str
    connected_by_name: str | None = None
    connected_at: datetime | None = None
    last_synced_at: datetime | None = None
    last_error: str | None = None


def _state(provider: Provider) -> str:
    settings = get_settings()
    if provider.flag and not getattr(settings.flags, provider.flag):
        return "phase_2"
    return "available" if provider.ready(settings) else "coming_soon"


def tools(session: Session, tenant_id: uuid.UUID) -> list[Tool]:
    connections = {
        c.provider: c
        for c in session.scalars(select(Connection).where(Connection.tenant_id == tenant_id))
    }
    out = []
    for p in PROVIDERS.values():
        state = _state(p)
        c = connections.get(p.key)
        if state != "available" and c is None:
            # The demo is offered only where it is switched on.
            if p.key != "demo":
                out.append(Tool(p.key, p.name, p.department, p.sends, state))
            continue
        out.append(
            Tool(
                p.key,
                p.name,
                p.department,
                p.sends,
                c.status if c else "available",
                c.connected_by_name if c else None,
                c.connected_at if c else None,
                c.last_synced_at if c else None,
                c.last_error if c else None,
            )
        )
    return out


def _tool(session: Session, tenant_id: uuid.UUID, key: str) -> Tool:
    return next(t for t in tools(session, tenant_id) if t.key == key)


def _provider(key: str) -> Provider:
    provider = PROVIDERS.get(key)
    if provider is None:
        raise ConnectorError(404, "That tool was not found.")
    return provider


def _connection(session: Session, tenant_id: uuid.UUID, key: str) -> Connection:
    c = session.scalar(
        select(Connection).where(Connection.tenant_id == tenant_id, Connection.provider == key)
    )
    if c is None:
        raise ConnectorError(404, "That tool is not connected.")
    return c


def connect(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, key: str) -> Tool:
    """Connects a tool and pulls from it straight away, so figures arrive at once."""
    provider = _provider(key)
    state = _state(provider)
    if state == "phase_2":
        raise ConnectorError(409, f"{provider.name} arrives in phase 2.")
    if state != "available":
        raise ConnectorError(409, f"{provider.name} is coming soon. Add an export from it for now.")
    existing = session.scalar(
        select(Connection).where(Connection.tenant_id == tenant_id, Connection.provider == key)
    )
    if existing is None:
        person = identity.contact(session, user_id, tenant_id)
        session.add(
            Connection(
                tenant_id=tenant_id,
                provider=key,
                status="connected",
                connected_by=user_id,
                connected_by_name=person.name if person else "",
            )
        )
        session.flush()
        audit.record(
            session,
            "connection.connected",
            tenant_id=tenant_id,
            actor_user_id=user_id,
            target_type="connection",
            target_id=key,
        )
    return sync(session, tenant_id, user_id, key)


def disconnect(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, key: str) -> None:
    """Stops future pulls. What the tool already sent stays, like any file."""
    session.delete(_connection(session, tenant_id, key))
    audit.record(
        session,
        "connection.disconnected",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="connection",
        target_id=key,
    )


def sync(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, key: str) -> Tool:
    """Pulls from a connected tool now, as ``user_id``. Each file it sends becomes an upload."""
    c = _connection(session, tenant_id, key)
    provider = _provider(key)
    try:
        if _state(provider) != "available":
            raise PullFailed(f"{provider.name} is not available here any more.")
        added = 0
        for filename, data in provider.pull():
            # A file refused (a plan limit, say) leaves the files before it in place.
            with session.begin_nested():
                if intake.add_pulled_file(session, tenant_id, user_id, filename, data):
                    added += 1
    except (PullFailed, intake.IntakeError) as exc:
        c.status = "failed"
        c.last_error = (getattr(exc, "message", None) or str(exc))[:300]
    else:
        c.status = "connected"
        c.last_error = None
        c.last_synced_at = datetime.now(UTC)
    audit.record(
        session,
        "connection.synced",
        tenant_id=tenant_id,
        actor_user_id=user_id,
        target_type="connection",
        target_id=key,
        details={"status": c.status, "new_files": added if c.status == "connected" else 0},
    )
    session.flush()
    return _tool(session, tenant_id, key)


def sync_due(now: datetime | None = None) -> int:
    """The worker's daily pull of every connected tool. Each runs as the person who connected
    it, under their company's row-level security; if they no longer manage the company's
    tools, the connection waits for someone to reconnect it."""
    cutoff = (now or datetime.now(UTC)) - SYNC_EVERY
    with system_session() as session:
        due = [
            (c.id, c.tenant_id, c.provider, c.connected_by)
            for c in session.scalars(
                select(Connection).where(
                    (Connection.last_synced_at.is_(None)) | (Connection.last_synced_at < cutoff)
                )
            )
        ]
    done = 0
    for connection_id, tenant_id, key, user_id in due:
        with app_session(user_id=user_id, tenant_id=tenant_id) as session:
            membership = identity.active_membership(session, user_id, tenant_id)
            if membership is not None and allowed(membership.role, Action.MANAGE_CONNECTIONS):
                sync(session, tenant_id, user_id, key)
                done += 1
                continue
        with system_session() as session:
            c = session.get(Connection, connection_id)
            if c is not None:
                c.status = "failed"
                c.last_error = (
                    f"{c.connected_by_name or 'The person who connected it'} no longer manages "
                    "this company's tools. Connect it again to keep it up to date."
                )
        log.info("connection_waiting", provider=key)
    return done
