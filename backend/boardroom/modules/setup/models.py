import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from boardroom.db import Base
from boardroom.events import OutboxColumns, register_outbox

SCHEMA = "setup"


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class CompanyProfile(Base):
    """Company settings the chat and the settings page write to (FR-8.5). Never figures."""

    __tablename__ = "profiles"
    __table_args__ = {"schema": SCHEMA}

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    reporting_currency: Mapped[str] = mapped_column(String(3), default="GBP")
    business_description: Mapped[str | None] = mapped_column(String(300))
    website: Mapped[str | None] = mapped_column(String(200))
    revenue_lines: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # None follows annual revenue (FR-5.6). 0 to 4 fixes the band.
    display_band: Mapped[int | None] = mapped_column(Integer)
    voice: Mapped[str] = mapped_column(String(20), default="we")  # used by commentary (E6)
    # The company's colour and logo, used on exports (FR-6.6).
    brand_colour: Mapped[str | None] = mapped_column(String(7))
    logo_key: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Target(Base):
    """A target set in the chat or in settings (FR-4.11). A setting, not a figure."""

    __tablename__ = "targets"
    __table_args__ = (UniqueConstraint("tenant_id", "metric", "period"), {"schema": SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    metric: Mapped[str] = mapped_column(String(30))  # revenue, closed_won
    period: Mapped[str] = mapped_column(String(7))
    value: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(20))  # chat, settings
    set_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    set_by_name: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open, done, skipped
    pending_invites: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # The interview: the questions planned when it opened, and those answered or skipped.
    questions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    answered: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("conversation_id", "seq"), {"schema": SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.conversations.id"), index=True
    )
    # Order within the conversation. Timestamps tie inside one transaction.
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))  # user, assistant
    content: Mapped[str] = mapped_column(Text)
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    # What this assistant message changed, for the audit trail and the "Changed" chips.
    applied: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source: Mapped[str] = mapped_column(String(20), default="ai")  # ai, template
    created_at: Mapped[datetime] = _created()


class SetupOutbox(OutboxColumns, Base):
    __tablename__ = "outbox"
    __table_args__ = {"schema": SCHEMA}


register_outbox(SetupOutbox)
