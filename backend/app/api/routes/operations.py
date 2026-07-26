from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.api.workflow_schemas import AlertReadIn, FinanceProfileIn
from app.core.config import settings
from app.core.database import get_db
from app.core.security import encrypt_json, utcnow
from app.db.models import (
    FinanceProfile,
    FinanceSnapshot,
    GoogleConnection,
    GoogleCredential,
    Job,
    JobStatus,
    MetricSnapshot,
    ModerationRecord,
    Notification,
    User,
)
from app.domain.audit import record_audit
from app.google_ads.capability_registry import get_demand_gen_capabilities
from app.google_ads.service import ACTIVE_GOOGLE_CONNECTION_STATUSES, is_google_connection_active

router = APIRouter(prefix="/operations", tags=["operations"])


class GoogleSyncIn(BaseModel):
    connection_id: UUID


@router.get("/moderation")
def list_moderation(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    rows = db.scalars(select(ModerationRecord).order_by(desc(ModerationRecord.updated_at)).limit(500)).all()
    return [
        {
            "id": str(row.id),
            "customer_id": row.customer_id,
            "resource_name": row.resource_name,
            "approval_status": row.approval_status,
            "policy_topics": row.policy_topics,
            "checked_at": row.checked_at,
        }
        for row in rows
    ]


@router.get("/statistics")
def list_statistics(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    rows = db.scalars(select(MetricSnapshot).order_by(desc(MetricSnapshot.snapshot_date)).limit(1000)).all()
    return [
        {
            "id": str(row.id),
            "customer_id": row.customer_id,
            "snapshot_date": row.snapshot_date,
            "metrics": row.metrics,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


@router.post("/{kind}/sync", status_code=status.HTTP_202_ACCEPTED)
def queue_google_sync(
    kind: str,
    payload: GoogleSyncIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    if kind not in {"moderation", "statistics"}:
        raise HTTPException(status_code=404, detail="Неизвестный тип синхронизации")
    connection = db.get(GoogleConnection, payload.connection_id)
    if not is_google_connection_active(connection):
        raise HTTPException(status_code=409, detail="Нужно активное подключение Google")
    job = Job(
        type=f"SYNC_{kind.upper()}",
        status=JobStatus.QUEUED.value,
        connection_id=connection.id,
        created_by_id=user.id,
        idempotency_key=None,
        progress_current=0,
        progress_total=1,
        payload={"connection_id": str(connection.id), "kind": kind},
    )
    db.add(job)
    db.flush()
    record_audit(
        db,
        request,
        user,
        f"{kind}.sync.queue",
        "job",
        str(job.id),
        {"connection_id": str(connection.id)},
    )
    db.commit()
    from app.jobs.tasks import sync_google_data

    sync_google_data.delay(str(job.id), kind)
    return {"job_id": str(job.id), "status": job.status}


@router.get("/finance")
def list_finance(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    profiles = db.scalars(select(FinanceProfile).order_by(desc(FinanceProfile.updated_at))).all()
    result = []
    for profile in profiles:
        snapshot = db.scalar(
            select(FinanceSnapshot)
            .where(FinanceSnapshot.profile_id == profile.id)
            .order_by(desc(FinanceSnapshot.created_at))
            .limit(1)
        )
        result.append(
            {
                "id": str(profile.id),
                "name": profile.name,
                "provider": profile.provider,
                "status": profile.status,
                "details": profile.details,
                "updated_at": profile.updated_at,
                "latest_snapshot": (
                    {
                        "balance": snapshot.balance,
                        "currency": snapshot.currency,
                        "cards_total": snapshot.cards_total,
                        "cards_active": snapshot.cards_active,
                        "created_at": snapshot.created_at,
                    }
                    if snapshot
                    else None
                ),
            }
        )
    return result


@router.post("/finance", status_code=status.HTTP_201_CREATED)
def configure_finance(
    payload: FinanceProfileIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    profile = db.scalar(select(FinanceProfile).where(FinanceProfile.name == payload.name))
    credential = db.get(GoogleCredential, profile.credential_id) if profile and profile.credential_id else None
    if credential:
        credential.encrypted_payload = encrypt_json({"api_token": payload.api_token})
        credential.last_rotated_at = utcnow()
    else:
        credential = GoogleCredential(
            kind="BROCARD_API_TOKEN",
            encrypted_payload=encrypt_json({"api_token": payload.api_token}),
            created_by_id=user.id,
        )
        db.add(credential)
        db.flush()
    details = {
        "api_base_url": payload.api_base_url,
        "sync_supported": True,
        "note": "API token сохранён в зашифрованном виде",
    }
    if profile:
        profile.credential_id = credential.id
        profile.status = "CONFIGURED"
        profile.details = details
    else:
        profile = FinanceProfile(
            name=payload.name,
            provider="BROCARD",
            status="CONFIGURED",
            credential_id=credential.id,
            details=details,
            created_by_id=user.id,
        )
        db.add(profile)
    db.flush()
    record_audit(db, request, user, "finance.configure", "finance_profile", str(profile.id), details)
    db.commit()
    return {"id": str(profile.id), "name": profile.name, "status": profile.status, "details": profile.details}


@router.post("/finance/{profile_id}/sync", status_code=status.HTTP_202_ACCEPTED)
def queue_finance_sync(
    profile_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    profile = db.get(FinanceProfile, profile_id)
    if not profile or not profile.credential_id:
        raise HTTPException(status_code=404, detail="Профиль Brocard не найден")
    job = Job(
        type="SYNC_FINANCE",
        status=JobStatus.QUEUED.value,
        created_by_id=user.id,
        progress_current=0,
        progress_total=1,
        payload={"profile_id": str(profile.id)},
    )
    profile.status = "SYNCING"
    profile.details = {**profile.details, "last_error": None}
    db.add(job)
    db.flush()
    record_audit(db, request, user, "finance.sync.queue", "job", str(job.id), {"profile_id": str(profile.id)})
    db.commit()
    from app.jobs.tasks import sync_finance

    sync_finance.delay(str(job.id))
    return {"job_id": str(job.id), "status": job.status}


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    rows = db.scalars(
        select(Notification)
        .where((Notification.user_id == user.id) | Notification.user_id.is_(None))
        .order_by(desc(Notification.created_at))
        .limit(300)
    ).all()
    return [
        {
            "id": str(row.id),
            "severity": row.severity,
            "title": row.title,
            "message": row.message,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "read_at": row.read_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.patch("/alerts/{alert_id}")
def set_alert_read(
    alert_id: UUID,
    payload: AlertReadIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    alert = db.get(Notification, alert_id)
    if not alert or (alert.user_id and alert.user_id != user.id):
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    alert.read_at = utcnow() if payload.read else None
    db.commit()
    return {"id": str(alert.id), "read_at": alert.read_at}


@router.get("/settings")
def product_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    capabilities = get_demand_gen_capabilities(settings.google_ads_api_version)
    connected = db.scalars(
        select(GoogleConnection).where(GoogleConnection.status.in_(ACTIVE_GOOGLE_CONNECTION_STATUSES))
    ).all()
    return {
        "app_environment": settings.app_env,
        "public_base_url": settings.app_public_base_url,
        "google_ads_api_version": settings.google_ads_api_version,
        "live_connections": len(connected),
        "deployment_policy": {
            "campaign_status": "PAUSED",
            "validate_only_required": True,
            "explicit_confirmation": "CREATE_PAUSED",
            "simulation_contacts_google": False,
        },
        "capabilities": capabilities.__dict__,
        "finance": {
            "provider": "BROCARD",
            "integration_contract": "API base URL must be supplied by the operator",
        },
        "today": date.today().isoformat(),
    }
