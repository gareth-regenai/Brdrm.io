import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from boardroom.db import Base
from boardroom.events import OutboxColumns, register_outbox

SCHEMA = "metrics"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _tenant() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), index=True)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class RowSelection(Base):
    """Which rows of one dataset feed one row set (FR-5.2), chosen once per dataset version."""

    __tablename__ = "selections"
    __table_args__ = (UniqueConstraint("dataset_id", "row_set"), {"schema": SCHEMA})

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    row_set: Mapped[str] = mapped_column(String(50))
    filters: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(20))  # ai, standard
    reason: Mapped[str] = mapped_column(String(300))
    model: Mapped[str | None] = mapped_column(String(100))
    skill_version: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = _created()


class Run(Base):
    """One calculation of every figure for a company."""

    __tablename__ = "runs"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    upload_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    annual_revenue: Mapped[str | None] = mapped_column(String(40))
    band: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = _created()


class FigureRecord(Base):
    __tablename__ = "figures"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{SCHEMA}.runs.id"), index=True)
    metric: Mapped[str] = mapped_column(String(50))
    period: Mapped[str] = mapped_column(String(7))
    # The exact value as a decimal string. Never rounded, never written from an AI response.
    value: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20))
    formula_version: Mapped[str] = mapped_column(String(20))
    method: Mapped[str] = mapped_column(String(50))
    custom: Mapped[bool] = mapped_column(Boolean)
    inputs: Mapped[dict[str, str]] = mapped_column(JSONB)
    lineage: Mapped[dict[str, Any]] = mapped_column(JSONB)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB)
    risk_measure: Mapped[str | None] = mapped_column(String(60))
    risk_common: Mapped[str | None] = mapped_column(String(10))
    risk_company: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = _created()


class MetricSetting(Base):
    """A company's own view (FR-5.6, FR-5.7): which tiles, display band, warning lines.
    The investor overview ignores the warning lines here and uses the common ones."""

    __tablename__ = "settings"
    __table_args__ = {"schema": SCHEMA}

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    metric: Mapped[str] = mapped_column(String(50), primary_key=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    band_offset: Mapped[int] = mapped_column(Integer, default=0)
    high: Mapped[str | None] = mapped_column(String(40))
    medium: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MetricsOutbox(OutboxColumns, Base):
    __tablename__ = "outbox"
    __table_args__ = {"schema": SCHEMA}


register_outbox(MetricsOutbox)
