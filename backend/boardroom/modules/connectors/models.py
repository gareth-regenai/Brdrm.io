import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from boardroom.db import Base

SCHEMA = "connectors"


class Connection(Base):
    """One tool a company has connected. Disconnecting removes the row."""

    __tablename__ = "connections"
    __table_args__ = (UniqueConstraint("tenant_id", "provider"), {"schema": SCHEMA})

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))  # connected, failed
    # Scheduled pulls run as this person, so they stop if the person leaves the company.
    connected_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    connected_by_name: Mapped[str] = mapped_column(String(200))
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))
