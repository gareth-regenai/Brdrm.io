import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from boardroom.db import Base
from boardroom.events import OutboxColumns, register_outbox

SCHEMA = "intake"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _tenant() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), index=True)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Upload(Base):
    __tablename__ = "uploads"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    # created, received, understanding, calculating, describing, ready, shared, failed
    status: Mapped[str] = mapped_column(String(20), default="created")
    status_message: Mapped[str | None] = mapped_column(String(500))
    needs_mapping: Mapped[bool] = mapped_column(Boolean, default=False)
    file_kind: Mapped[str | None] = mapped_column(String(20))
    header_fingerprint: Mapped[str | None] = mapped_column(String(64))
    # The checked interpretation waiting on a question. Kept off the API.
    proposal: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    row_count: Mapped[int | None] = mapped_column(Integer)
    data_as_of: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Question(Base):
    """The one plain question asked when a figure cannot be calculated without it (FR-3.2)."""

    __tablename__ = "questions"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    upload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.uploads.id"), index=True)
    subject: Mapped[str] = mapped_column(String(255))  # the column or row label asked about
    field: Mapped[str] = mapped_column(String(50))
    prompt: Mapped[str] = mapped_column(String(500))
    options: Mapped[list[dict[str, str]]] = mapped_column(JSONB)
    answer: Mapped[str | None] = mapped_column(String(300))
    answered_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class Layout(Base):
    """A confirmed interpretation, reused for the same headers next time (FR-4.7)."""

    __tablename__ = "layouts"
    __table_args__ = (UniqueConstraint("tenant_id", "fingerprint"), {"schema": SCHEMA})

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    fingerprint: Mapped[str] = mapped_column(String(64))
    interpretation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    confirmed: Mapped[list[str]] = mapped_column(JSONB, default=list)
    source: Mapped[str] = mapped_column(String(20))  # ai, answer, manual
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("tenant_id", "kind", "version"), {"schema": SCHEMA})

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    upload_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.uploads.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer)
    layout_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.layouts.id"))
    interpretation: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fields: Mapped[list[str]] = mapped_column(JSONB)
    row_count: Mapped[int] = mapped_column(Integer)
    invalid_cells: Mapped[int] = mapped_column(Integer)
    data_as_of: Mapped[date | None] = mapped_column(Date)
    fingerprint: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = _created()


class DatasetRow(Base):
    __tablename__ = "dataset_rows"
    __table_args__ = {"schema": SCHEMA}

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.datasets.id"), primary_key=True
    )
    row_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = _tenant()
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)


class InterpretationLog(Base):
    """What the AI understood and ignored, for platform admins only (FR-4.10)."""

    __tablename__ = "interpretation_log"
    __table_args__ = {"schema": SCHEMA}
    __mapper_args__ = {"eager_defaults": False}

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    upload_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    source: Mapped[str] = mapped_column(String(20))  # ai, layout, manual, fallback
    model: Mapped[str | None] = mapped_column(String(100))
    skill_version: Mapped[str | None] = mapped_column(String(100))
    interpretation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Positions and reasons of dropped pay-like columns. Never their names or values.
    dropped: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    error: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class ManualFigure(Base):
    """A figure or forecast typed in by a person (FR-4.8). No file source, no data check."""

    __tablename__ = "manual_figures"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    metric: Mapped[str] = mapped_column(String(50))
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    value: Mapped[str] = mapped_column(String(40))  # decimal string
    kind: Mapped[str] = mapped_column(String(20))  # actual, forecast, target
    note: Mapped[str | None] = mapped_column(String(300))
    entered_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    entered_by_name: Mapped[str] = mapped_column(String(200))
    entered_at: Mapped[datetime] = _created()


class IntakeOutbox(OutboxColumns, Base):
    __tablename__ = "outbox"
    __table_args__ = {"schema": SCHEMA}


register_outbox(IntakeOutbox)
