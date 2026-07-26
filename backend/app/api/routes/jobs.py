from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import JobOut
from app.core.database import get_db
from app.db.models import Job, User

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Job]:
    return list(db.scalars(select(Job).order_by(desc(Job.created_at)).limit(100)).all())
