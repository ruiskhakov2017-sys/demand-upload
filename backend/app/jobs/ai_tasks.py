from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete, select, update

from app.ai.policy import effective_ai_settings
from app.core.database import SessionLocal
from app.core.security import utcnow
from app.db.models import AiConversation, AiDraft, AiSavedReport
from app.jobs.celery_app import celery_app


@celery_app.task(name="app.jobs.cleanup_ai_retention")
def cleanup_ai_retention() -> dict[str, int]:
    now = utcnow()
    with SessionLocal() as db:
        retention_cutoff = now - timedelta(days=int(effective_ai_settings(db)["retention_days"]))
        marked_expired = db.execute(
            update(AiDraft)
            .where(
                AiDraft.expires_at < now,
                AiDraft.status.in_(["EDITABLE", "READY_FOR_USER_PREVIEW"]),
            )
            .values(status="EXPIRED", updated_at=now)
        ).rowcount
        expired_drafts = db.execute(
            delete(AiDraft).where(
                AiDraft.status.in_(["DELETED", "EXPIRED"]),
                AiDraft.updated_at < retention_cutoff,
            )
        ).rowcount
        expired_reports = db.execute(
            delete(AiSavedReport).where(AiSavedReport.expires_at.is_not(None), AiSavedReport.expires_at < now)
        ).rowcount
        conversation_ids = list(
            db.scalars(
                select(AiConversation.id).where(
                    AiConversation.retention_until.is_not(None),
                    AiConversation.retention_until < now,
                )
            ).all()
        )
        deleted_conversations = (
            db.execute(delete(AiConversation).where(AiConversation.id.in_(conversation_ids))).rowcount
            if conversation_ids
            else 0
        )
        db.commit()
        return {
            "drafts_marked_expired": int(marked_expired or 0),
            "drafts": int(expired_drafts or 0),
            "reports": int(expired_reports or 0),
            "conversations": int(deleted_conversations or 0),
        }
