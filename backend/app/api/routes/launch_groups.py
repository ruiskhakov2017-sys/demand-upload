from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.api.routes.batches import _guardrails, _instance_out
from app.api.workflow_schemas import CampaignStatusIn
from app.core.database import get_db
from app.core.security import utcnow, verify_password
from app.db.models import (
    AccountTestBundle,
    CampaignInstance,
    CampaignStatusAction,
    CustomerAccount,
    GoogleConnection,
    Job,
    JobStatus,
    LaunchBatch,
    User,
)
from app.domain.audit import record_audit
from app.google_ads.safety import (
    GoogleAdsSafetyError,
    require_execution_mode_for_connection,
    require_google_test_connection_target,
)

router = APIRouter(prefix="/launch-groups", tags=["launch-groups"])


@router.get("")
def list_launch_groups(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    groups = list(
        db.scalars(select(AccountTestBundle).order_by(desc(AccountTestBundle.created_at)).limit(500)).all()
    )
    batch_ids = {item.launch_batch_id for item in groups}
    batches = {
        item.id: item
        for item in db.scalars(select(LaunchBatch).where(LaunchBatch.id.in_(batch_ids))).all()
    }
    return [_group_summary(db, item, batches.get(item.launch_batch_id)) for item in groups]


@router.get("/{group_id}")
def get_launch_group(
    group_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return _group_detail(db, _get_group(db, group_id))


@router.post("/{group_id}/status-actions", status_code=status.HTTP_202_ACCEPTED)
def create_status_action(
    group_id: UUID,
    payload: CampaignStatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    group = _get_group(db, group_id)
    selected = _select_instances(_group_instances(db, group.id), payload.campaign_instance_ids)
    if not selected:
        raise HTTPException(status_code=422, detail="Не выбраны кампании")
    if not payload.confirmation:
        raise HTTPException(status_code=409, detail="Подтвердите изменение статуса кампаний")
    batch = db.get(LaunchBatch, group.launch_batch_id)
    if batch and batch.execution_mode != "SIMULATION":
        connection = (
            db.get(GoogleConnection, batch.connection_id)
            if batch.connection_id
            else None
        )
        account = db.scalar(
            select(CustomerAccount).where(
                CustomerAccount.connection_id == batch.connection_id,
                CustomerAccount.customer_id == group.customer_id,
            )
        )
        try:
            require_execution_mode_for_connection(connection, batch.execution_mode)
            require_google_test_connection_target(
                connection, account, group.customer_id
            )
        except GoogleAdsSafetyError as exc:
            raise HTTPException(status_code=409, detail=f"{exc.code}: {exc}") from exc

    requested_status = "ENABLED" if payload.action == "ENABLE" else "PAUSED"
    if requested_status == "ENABLED":
        limit = int(_guardrails(db)["max_parallel_enabled"])
        if len(selected) > limit and not _password_ok(user, payload.password_confirmation):
            raise HTTPException(
                status_code=409,
                detail="Превышен лимит параллельного включения. Подтвердите действие паролем.",
            )

    action, job = _queue_action(db, group, selected, payload.action, requested_status, user)
    record_audit(
        db,
        request,
        user,
        "campaign.status.queue",
        "campaign_status_action",
        str(action.id),
        {
            "launch_group_id": str(group.id),
            "action": payload.action,
            "requested_status": requested_status,
            "instances": [str(item.id) for item in selected],
            "selection": "ALL" if not payload.campaign_instance_ids else "SELECTED",
        },
    )
    db.commit()
    from app.jobs.tasks import apply_campaign_status_action

    apply_campaign_status_action.delay(str(action.id), str(job.id))
    return {
        "action_id": str(action.id),
        "job_id": str(job.id),
        "status": action.status,
        "selected_count": len(selected),
    }


@router.post("/{group_id}/sync-metrics", status_code=status.HTTP_202_ACCEPTED)
def queue_metrics_sync(
    group_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    group = _get_group(db, group_id)
    batch = db.get(LaunchBatch, group.launch_batch_id)
    job = Job(
        type="SYNC_LAUNCH_GROUP_METRICS",
        status=JobStatus.QUEUED.value,
        connection_id=batch.connection_id if batch else None,
        created_by_id=user.id,
        idempotency_key=f"launch-group-metrics:{group.id}:{utcnow().strftime('%Y%m%d%H')}",
        progress_current=0,
        progress_total=len(_group_instances(db, group.id)),
        payload={"launch_group_id": str(group.id)},
    )
    existing = db.scalar(select(Job).where(Job.idempotency_key == job.idempotency_key))
    if existing and existing.status in {JobStatus.QUEUED.value, JobStatus.RUNNING.value}:
        return {"job_id": str(existing.id), "reused": True}
    db.add(job)
    db.flush()
    record_audit(db, request, user, "launch_group.metrics.queue", "job", str(job.id))
    db.commit()
    from app.jobs.tasks import sync_launch_group_metrics

    sync_launch_group_metrics.delay(str(group.id), str(job.id))
    return {"job_id": str(job.id), "reused": False}


@router.get("/{group_id}/history")
def get_launch_group_history(
    group_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    group = _get_group(db, group_id)
    actions = list(
        db.scalars(
            select(CampaignStatusAction)
            .where(CampaignStatusAction.account_test_bundle_id == group.id)
            .order_by(desc(CampaignStatusAction.created_at))
        ).all()
    )
    return {
        "actions": [
            {
                "id": str(item.id),
                "action": item.action,
                "requested_status": item.requested_status,
                "status": item.status,
                "selected_instance_ids": item.selected_instance_ids,
                "request_ids": item.request_ids,
                "error_message": item.error_message,
                "created_at": item.created_at,
                "completed_at": item.completed_at,
            }
            for item in actions
        ]
    }


def _queue_action(
    db: Session,
    group: AccountTestBundle,
    selected: list[CampaignInstance],
    action_name: str,
    requested_status: str,
    user: User,
) -> tuple[CampaignStatusAction, Job]:
    batch = db.get(LaunchBatch, group.launch_batch_id)
    action = CampaignStatusAction(
        account_test_bundle_id=group.id,
        campaign_instance_id=None,
        action=action_name,
        previous_status=None,
        requested_status=requested_status,
        execution_mode=batch.execution_mode if batch else "SIMULATION",
        status="QUEUED",
        selected_instance_ids=[str(item.id) for item in selected],
        request_ids=[],
        resource_names=[],
        requested_by_id=user.id,
    )
    db.add(action)
    db.flush()
    job = Job(
        type="CAMPAIGN_STATUS_ACTION",
        status=JobStatus.QUEUED.value,
        connection_id=batch.connection_id if batch else None,
        created_by_id=user.id,
        idempotency_key=f"campaign-status:{action.id}",
        progress_current=0,
        progress_total=len(selected),
        payload={"action_id": str(action.id)},
    )
    db.add(job)
    return action, job


def _group_summary(db: Session, group: AccountTestBundle, batch: LaunchBatch | None) -> dict:
    instances = _group_instances(db, group.id)
    return {
        "id": str(group.id),
        "launch_batch_id": str(group.launch_batch_id),
        "launch_batch_name": batch.name if batch else None,
        "execution_mode": batch.execution_mode if batch else None,
        "customer_id": group.customer_id,
        "account_name": group.account_name,
        "currency_code": group.currency_code,
        "time_zone": group.time_zone,
        "status": group.status,
        "campaigns_count": len(instances),
        "total_cost_micros": sum(int((item.metrics or {}).get("cost_micros") or 0) for item in instances),
        "total_conversions": sum(float((item.metrics or {}).get("conversions") or 0) for item in instances),
        "updated_at": group.updated_at,
    }


def _group_detail(db: Session, group: AccountTestBundle) -> dict:
    batch = db.get(LaunchBatch, group.launch_batch_id)
    return {
        **_group_summary(db, group, batch),
        "instances": [_instance_out(item, group) for item in _group_instances(db, group.id)],
    }


def _get_group(db: Session, group_id: UUID) -> AccountTestBundle:
    item = db.get(AccountTestBundle, group_id)
    if not item:
        raise HTTPException(status_code=404, detail="Группа запуска не найдена")
    return item


def _group_instances(db: Session, group_id: UUID) -> list[CampaignInstance]:
    return list(
        db.scalars(
            select(CampaignInstance)
            .where(CampaignInstance.account_test_bundle_id == group_id)
            .order_by(CampaignInstance.campaign_sequence)
        ).all()
    )


def _select_instances(instances: list[CampaignInstance], selected_ids: list[UUID]) -> list[CampaignInstance]:
    if not selected_ids:
        return instances
    allowed = set(selected_ids)
    return [item for item in instances if item.id in allowed]


def _password_ok(user: User, value: str | None) -> bool:
    return bool(value and verify_password(value, user.password_hash))
