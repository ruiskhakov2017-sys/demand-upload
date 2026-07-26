from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.security import redact, utcnow
from app.db.models import AuditLog, User


def record_audit(
    db: Session,
    request: Request | None,
    user: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    summary: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            created_at=utcnow(),
            actor_user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=request.client.host if request and request.client else None,
            summary=redact(summary or {}),
        )
    )
