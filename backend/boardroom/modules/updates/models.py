import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from boardroom.db import Base
from boardroom.events import OutboxColumns, register_outbox

SCHEMA = "updates"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _tenant() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), index=True)


class Update(Base):
    """One addition of data, as a dated line (FR-6.1). No draft states, no versions: it
    awaits approval or is shared, and can be edited either way (FR-6.2)."""

    __tablename__ = "updates"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True)
    # The calculation this update shows. Runs are kept, so its figures stay traceable.
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    added_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    # Name and role as they were when the data was added.
    added_by_name: Mapped[str] = mapped_column(String(200))
    added_by_role: Mapped[str] = mapped_column(String(30))
    department: Mapped[str] = mapped_column(String(20))
    data_as_of: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))  # awaiting_approval, shared
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_by_name: Mapped[str | None] = mapped_column(String(200))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_edited_by_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UpdateFigure(Base):
    """A figure the update shows. The value comes from the metrics run, unless a person
    changed it in the update, in which case who, when and the value before are kept."""

    __tablename__ = "figures"
    __table_args__ = (UniqueConstraint("update_id", "figure_id"), {"schema": SCHEMA})

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    update_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.updates.id"), index=True)
    figure_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    metric: Mapped[str] = mapped_column(String(50))
    period: Mapped[str] = mapped_column(String(7))
    position: Mapped[int] = mapped_column(Integer)
    edited_value: Mapped[str | None] = mapped_column(String(60))
    edited_from: Mapped[str | None] = mapped_column(String(60))
    edited_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    edited_by_name: Mapped[str | None] = mapped_column(String(200))
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    update_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.updates.id"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    author_name: Mapped[str] = mapped_column(String(200))
    author_role: Mapped[str] = mapped_column(String(30))
    body: Mapped[str] = mapped_column(Text)
    # The people this comment tags with @, as user ids. Each is emailed.
    mentions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Section(Base):
    """A part of the commentary: the headline, a note per department, or likely board
    questions (company only). Drafted by Claude and passed by the number check, or left
    for a person, who can also edit or write any section (FR-5.5, FR-6.4)."""

    __tablename__ = "sections"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    update_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.updates.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # headline, note, questions
    department: Mapped[str | None] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer)
    # None while it waits for a person. "" when a person chose to leave it out.
    text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))  # drafted, needs_person, written, edited
    reason: Mapped[str | None] = mapped_column(String(200))
    check_result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    model: Mapped[str | None] = mapped_column(String(100))
    skill_version: Mapped[str | None] = mapped_column(String(50))
    edited_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    edited_by_name: Mapped[str | None] = mapped_column(String(200))
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UpdatesOutbox(OutboxColumns, Base):
    __tablename__ = "outbox"
    __table_args__ = {"schema": SCHEMA}


register_outbox(UpdatesOutbox)
