import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from boardroom.modules.audit.models import AuditEntry


def record(
    session: Session,
    action: str,
    *,
    tenant_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    target_type: str | None = None,
    target_id: uuid.UUID | str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEntry(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            details=details or {},
        )
    )
    # Written now, under the tenant that is current at the time of the action.
    session.flush()


def list_for_tenant(session: Session, limit: int = 200) -> list[AuditEntry]:
    """Row-level security limits this to the session's tenant."""
    return list(
        session.scalars(
            select(AuditEntry).order_by(AuditEntry.created_at.desc()).limit(limit)
        ).all()
    )
