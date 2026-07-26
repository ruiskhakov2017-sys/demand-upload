from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import utcnow
from app.db.models import (
    CampaignUpload,
    CustomerAccount,
    DeploymentPlan,
    GoogleConnection,
    Job,
    MediaAsset,
    Notification,
    User,
)
from app.google_ads.service import ACTIVE_GOOGLE_CONNECTION_STATUSES

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    def count(model: type, *conditions: object) -> int:
        query = select(func.count()).select_from(model)
        if conditions:
            query = query.where(*conditions)
        return int(db.scalar(query) or 0)

    return {
        "connections": {
            "total": count(GoogleConnection),
            "connected": count(
                GoogleConnection,
                GoogleConnection.status.in_(ACTIVE_GOOGLE_CONNECTION_STATUSES),
            ),
            "test": count(GoogleConnection, GoogleConnection.environment == "TEST"),
        },
        "accounts": {"total": count(CustomerAccount)},
        "uploads": {
            "total": count(CampaignUpload),
            "draft": count(CampaignUpload, CampaignUpload.status == "DRAFT"),
            "succeeded": count(CampaignUpload, CampaignUpload.status == "SUCCEEDED"),
        },
        "plans": {
            "total": count(DeploymentPlan),
            "validated": count(DeploymentPlan, DeploymentPlan.status == "VALIDATED"),
        },
        "jobs": {
            "total": count(Job),
            "active": count(Job, Job.status.in_(["QUEUED", "RUNNING"])),
            "failed": count(Job, Job.status == "FAILED"),
        },
        "media": {"total": count(MediaAsset), "ready": count(MediaAsset, MediaAsset.status == "READY")},
        "alerts": {
            "unread": count(
                Notification,
                Notification.read_at.is_(None),
                (Notification.user_id == user.id) | Notification.user_id.is_(None),
            )
        },
        "refreshed_at": utcnow(),
    }
