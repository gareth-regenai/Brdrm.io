import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from boardroom.db import Base

SCHEMA = "billing"


class Plan(Base):
    """A plan and the value of each entitlement key in it. Platform data, not a company's."""

    __tablename__ = "plans"
    __table_args__ = {"schema": SCHEMA}

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    stripe_price_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    # Key to value. A key that is missing or null has no limit.
    entitlements: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # The plan for companies with no subscription.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    # Offered to companies choosing a plan.
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Subscription(Base):
    """A company's plan as Stripe last reported it. Only the webhook writes it."""

    __tablename__ = "subscriptions"
    __table_args__ = {"schema": SCHEMA}

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    plan_key: Mapped[str | None] = mapped_column(ForeignKey("billing.plans.key"))
    status: Mapped[str] = mapped_column(String(30))
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the newest subscription event applied was created at Stripe, so an older
    # event arriving late cannot undo a newer one.
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StripeEvent(Base):
    __tablename__ = "stripe_events"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100))
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    outcome: Mapped[str] = mapped_column(String(20))  # applied, ignored, stale
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
