from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.db.models import AuditLog, User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 100,
) -> list[dict]:
    rows = db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(min(limit, 500))).all()
    return [
        {
            "id": str(row.id),
            "created_at": row.created_at,
            "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "summary": row.summary,
        }
        for row in rows
    ]
