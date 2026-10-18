"""Outbox per module, delivered at least once to idempotent consumers (FR-10.7).

A module writes events to its own outbox table in the same transaction as the
change. The dispatcher reads each outbox and hands every event to the
consumers registered for its type. A consumer runs at most once per event:
``events.processed_events`` holds (consumer, event_id) and the handler runs in
the same transaction as that insert.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from boardroom.db import Base, system_session
from boardroom.logs import get_logger

log = get_logger(__name__)


class OutboxColumns:
    """Columns shared by every module's outbox table."""

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProcessedEvent(Base):
    __tablename__ = "processed_events"
    __table_args__ = {"schema": "events"}

    consumer: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


@dataclass(frozen=True)
class Event:
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    event_type: str
    payload: dict[str, Any]


Handler = Callable[[Session, Event], None]

_outboxes: list[type[OutboxColumns]] = []
_consumers: dict[str, list[tuple[str, Handler]]] = {}


def register_outbox(model: type[OutboxColumns]) -> None:
    if model not in _outboxes:
        _outboxes.append(model)


def consumer(name: str, *event_types: str) -> Callable[[Handler], Handler]:
    def decorate(handler: Handler) -> Handler:
        for event_type in event_types:
            handlers = _consumers.setdefault(event_type, [])
            if all(existing != name for existing, _ in handlers):
                handlers.append((name, handler))
        return handler

    return decorate


def emit(
    session: Session,
    outbox: type[OutboxColumns],
    event_type: str,
    tenant_id: uuid.UUID | None,
    payload: dict[str, Any],
) -> uuid.UUID:
    event_id = uuid.uuid4()
    session.add(
        outbox(id=event_id, tenant_id=tenant_id, event_type=event_type, payload=payload)  # type: ignore[call-arg]
    )
    return event_id


def deliver(session: Session, event: Event) -> int:
    """Run every consumer of one event that has not yet processed it. Returns how many ran."""
    ran = 0
    for name, handler in _consumers.get(event.event_type, []):
        inserted = session.execute(
            insert(ProcessedEvent)
            .values(consumer=name, event_id=event.id, tenant_id=event.tenant_id)
            .on_conflict_do_nothing()
            .returning(ProcessedEvent.event_id)
        ).first()
        if inserted is None:
            continue
        handler(session, event)
        ran += 1
    return ran


def dispatch_pending(limit: int = 100) -> int:
    """Deliver undispatched events from every outbox. Safe to run concurrently."""
    delivered = 0
    for outbox in list(_outboxes):
        with system_session() as session:
            rows = session.scalars(
                select(outbox)
                .where(outbox.dispatched_at.is_(None))
                .order_by(outbox.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
            for row in rows:
                event = Event(row.id, row.tenant_id, row.event_type, row.payload)
                try:
                    with session.begin_nested():
                        delivered += deliver(session, event)
                except Exception:
                    # Left undispatched, so the next run retries it.
                    log.exception("event_failed", event_type=row.event_type, event_id=str(row.id))
                    continue
                row.dispatched_at = datetime.now(UTC)
                log.info("event_dispatched", event_type=row.event_type, event_id=str(row.id))
    return delivered
