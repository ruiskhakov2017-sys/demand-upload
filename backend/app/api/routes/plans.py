from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.api.workflow_schemas import (
    PlanBuildIn,
    PlanConfirmIn,
    PlanConfirmOut,
    PlanOut,
    PlanValidationOut,
)
from app.core.database import get_db
from app.core.security import utcnow
from app.db.models import (
    AccountTestBundle,
    CampaignInstance,
    CampaignUpload,
    DeploymentPlan,
    DeploymentSchedule,
    GoogleConnection,
    Job,
    JobStatus,
    LaunchBatch,
    MediaAsset,
    PlanStatus,
    ScheduledAccountRun,
    ScheduleEvent,
    ScheduleStatus,
    UploadStatus,
    User,
)
from app.domain.audit import record_audit
from app.domain.planner import build_batch_plan_snapshot, build_plan_snapshot, validate_plan_snapshot
from app.domain.scheduling import snapshot_fingerprint
from app.google_ads.mock_adapter import MockGoogleAdsAdapter
from app.google_ads.service import build_google_ads_adapter, is_google_connection_active

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[DeploymentPlan]:
    return list(db.scalars(select(DeploymentPlan).order_by(desc(DeploymentPlan.created_at)).limit(200)).all())


@router.get("/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> DeploymentPlan:
    return _get_plan(db, plan_id)


@router.post("/from-upload/{upload_id}", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def build_plan(
    upload_id: UUID,
    payload: PlanBuildIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> DeploymentPlan:
    upload = db.get(CampaignUpload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Загрузка не найдена")
    if payload.execution_mode == "LIVE":
        connection = db.get(GoogleConnection, upload.connection_id) if upload.connection_id else None
        if not is_google_connection_active(connection):
            raise HTTPException(status_code=409, detail="Для live-плана нужно активное подключение Google")

    media = list(db.scalars(select(MediaAsset)).all())
    batch, bundles, instances = _load_batch_context(db, upload)
    schedule = None
    if payload.schedule_id:
        schedule = db.get(DeploymentSchedule, payload.schedule_id)
        if (
            not schedule
            or not batch
            or schedule.launch_batch_id != batch.id
            or schedule.upload_id != upload.id
        ):
            raise HTTPException(status_code=404, detail="Расписание этой загрузки не найдено")
        if not schedule.is_current or schedule.status != ScheduleStatus.DRAFT.value:
            raise HTTPException(status_code=409, detail="Для плана нужна текущая черновая версия расписания")
    if batch:
        snapshot, fingerprint = build_batch_plan_snapshot(
            upload,
            batch,
            bundles,
            instances,
            media,
            payload.execution_mode,
        )
    else:
        snapshot, fingerprint = build_plan_snapshot(upload, media, payload.execution_mode)
    if schedule:
        from app.api.routes.schedules import schedule_plan_snapshot

        snapshot["schedule"] = schedule_plan_snapshot(db, schedule)
        fingerprint = snapshot_fingerprint(snapshot)
    existing = db.scalar(select(DeploymentPlan).where(DeploymentPlan.fingerprint == fingerprint))
    if existing:
        if schedule and not schedule.deployment_plan_id:
            schedule.deployment_plan_id = existing.id
            for run in db.scalars(
                select(ScheduledAccountRun).where(ScheduledAccountRun.schedule_id == schedule.id)
            ).all():
                run.deployment_plan_id = existing.id
            db.commit()
        return existing
    validation = validate_plan_snapshot(snapshot)
    plan = DeploymentPlan(
        upload_id=upload.id,
        connection_id=upload.connection_id,
        launch_batch_id=batch.id if batch else None,
        status=PlanStatus.READY.value,
        execution_mode=payload.execution_mode,
        fingerprint=fingerprint,
        snapshot=snapshot,
        local_validation=validation,
        google_validation={},
        result={},
        request_ids=[],
        resource_names=[],
        created_by_id=user.id,
    )
    db.add(plan)
    db.flush()
    if schedule:
        schedule.deployment_plan_id = plan.id
        for run in db.scalars(
            select(ScheduledAccountRun).where(ScheduledAccountRun.schedule_id == schedule.id)
        ).all():
            run.deployment_plan_id = plan.id
    if batch:
        instance_validation = _validation_by_instance(snapshot, validation)
        for instance in instances:
            if instance.included:
                instance.deployment_plan_id = plan.id
                instance.local_validation = instance_validation.get(
                    str(instance.id),
                    {"valid": False, "errors": [{"code": "MISSING", "message": "Кампания не вошла в план"}]},
                )
                instance.status = "LOCAL_VALID" if instance.local_validation["valid"] else "LOCAL_INVALID"
        batch.status = "PLAN_READY" if validation["valid"] else "LOCAL_INVALID"
    upload.status = UploadStatus.PLAN_READY.value if validation["valid"] else UploadStatus.DRAFT.value
    upload.last_error = None if validation["valid"] else f"Локальная проверка: ошибок {len(validation['errors'])}"
    db.flush()
    record_audit(
        db,
        request,
        user,
        "plan.build",
        "deployment_plan",
        str(plan.id),
        {
            "upload_id": str(upload.id),
            "execution_mode": payload.execution_mode,
            "fingerprint": fingerprint,
            "valid": validation["valid"],
        },
    )
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/{plan_id}/validate", response_model=PlanValidationOut)
def validate_plan(
    plan_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> PlanValidationOut:
    plan = _get_plan(db, plan_id)
    local = validate_plan_snapshot(plan.snapshot)
    plan.local_validation = local
    if not local["valid"]:
        result = {
            "ok": False,
            "mode": plan.execution_mode,
            "errors": local["errors"],
            "warnings": local["warnings"],
            "request_ids": [],
            "resource_names": [],
            "details": {"validate_only": False, "google_contacted": False},
        }
    elif plan.execution_mode == "SIMULATION":
        execution = MockGoogleAdsAdapter().validate_plan(plan.snapshot)
        result = execution.__dict__
    else:
        connection = db.get(GoogleConnection, plan.connection_id) if plan.connection_id else None
        if not is_google_connection_active(connection):
            raise HTTPException(status_code=409, detail="Подключение Google недоступно")
        execution = build_google_ads_adapter(db, connection).validate_plan(plan.snapshot)
        result = execution.__dict__

    plan.google_validation = result
    plan.request_ids = result["request_ids"]
    plan.status = PlanStatus.VALIDATED.value if result["ok"] else PlanStatus.FAILED.value
    plan.validated_at = utcnow()
    _save_instance_validation_results(db, plan, result)
    batch = db.get(LaunchBatch, plan.launch_batch_id) if plan.launch_batch_id else None
    if batch:
        batch.status = "VALIDATED" if result["ok"] else "VALIDATION_FAILED"
    upload = db.get(CampaignUpload, plan.upload_id)
    if upload:
        upload.status = UploadStatus.VALIDATED.value if result["ok"] else UploadStatus.FAILED.value
        upload.last_error = None if result["ok"] else "validate_only не пройден"
    record_audit(
        db,
        request,
        user,
        "plan.validate_only",
        "deployment_plan",
        str(plan.id),
        {"ok": result["ok"], "mode": result["mode"], "request_ids": result["request_ids"]},
    )
    db.commit()
    db.refresh(plan)
    return PlanValidationOut(
        plan=PlanOut.model_validate(plan),
        ok=result["ok"],
        mode=result["mode"],
        errors=result["errors"],
        warnings=[*local["warnings"], *result["warnings"]],
        request_ids=result["request_ids"],
    )


@router.post("/{plan_id}/confirm", response_model=PlanConfirmOut)
def confirm_plan(
    plan_id: UUID,
    payload: PlanConfirmIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> PlanConfirmOut:
    plan = _get_plan(db, plan_id)
    if plan.status not in {PlanStatus.VALIDATED.value, PlanStatus.FAILED.value}:
        raise HTTPException(status_code=409, detail="Сначала выполните validate_only")
    valid_instance_ids = _valid_instance_ids(plan.google_validation)
    if not plan.google_validation.get("ok") and not (payload.allow_partial and valid_instance_ids):
        raise HTTPException(status_code=409, detail="Последняя проверка validate_only завершилась ошибкой")
    schedule = db.scalar(
        select(DeploymentSchedule).where(
            DeploymentSchedule.deployment_plan_id == plan.id,
            DeploymentSchedule.is_current.is_(True),
        )
    )
    if schedule:
        if payload.allow_partial:
            raise HTTPException(
                status_code=409,
                detail="Расписание выполняет Launch Group целиком и не поддерживает частичный запуск",
            )
        return _confirm_schedule(db, plan, schedule, payload, request, user)
    selected_instance_ids = valid_instance_ids if payload.allow_partial else []
    selection_material = ",".join(sorted(selected_instance_ids)) if selected_instance_ids else "all"
    selection_key = hashlib.sha256(selection_material.encode()).hexdigest()[:16]
    key = f"deploy-plan:{plan.fingerprint}:{selection_key}"
    job = db.scalar(select(Job).where(Job.idempotency_key == key))
    if job and job.status in {JobStatus.QUEUED.value, JobStatus.RUNNING.value, JobStatus.SUCCEEDED.value}:
        return PlanConfirmOut(plan=PlanOut.model_validate(plan), job_id=job.id, reused=True)
    if not job:
        job = Job(
            type="DEPLOY_PLAN",
            status=JobStatus.QUEUED.value,
            connection_id=plan.connection_id,
            created_by_id=user.id,
            idempotency_key=key,
            progress_current=0,
            progress_total=len(selected_instance_ids) or len(plan.snapshot.get("campaigns") or []),
            payload={
                "plan_id": str(plan.id),
                "execution_mode": plan.execution_mode,
                "campaign_instance_ids": selected_instance_ids,
            },
        )
        db.add(job)
    else:
        job.status = JobStatus.QUEUED.value
        job.error_message = None
        job.progress_current = 0
    plan.status = PlanStatus.QUEUED.value
    plan.confirmed_at = utcnow()
    upload = db.get(CampaignUpload, plan.upload_id)
    if upload:
        upload.status = UploadStatus.QUEUED.value
    batch = db.get(LaunchBatch, plan.launch_batch_id) if plan.launch_batch_id else None
    if batch:
        batch.status = "QUEUED"
    db.flush()
    record_audit(
        db,
        request,
        user,
        "plan.confirm_paused",
        "deployment_plan",
        str(plan.id),
        {
            "job_id": str(job.id),
            "confirmation": payload.confirmation,
            "mode": plan.execution_mode,
            "allow_partial": payload.allow_partial,
            "campaign_instance_ids": selected_instance_ids,
        },
    )
    db.commit()
    db.refresh(plan)
    from app.jobs.tasks import deploy_plan

    deploy_plan.delay(str(plan.id), str(job.id))
    return PlanConfirmOut(plan=PlanOut.model_validate(plan), job_id=job.id, reused=False)


def _confirm_schedule(
    db: Session,
    plan: DeploymentPlan,
    schedule: DeploymentSchedule,
    payload: PlanConfirmIn,
    request: Request,
    user: User,
) -> PlanConfirmOut:
    if schedule.status not in {ScheduleStatus.DRAFT.value, ScheduleStatus.PLANNED.value}:
        if schedule.job_id:
            job = db.get(Job, schedule.job_id)
            if job:
                return PlanConfirmOut(plan=PlanOut.model_validate(plan), job_id=job.id, reused=True)
        raise HTTPException(status_code=409, detail="Расписание уже подтверждено")
    key = f"deploy-schedule:{schedule.fingerprint}"
    job = db.scalar(select(Job).where(Job.idempotency_key == key))
    if job and job.status in {
        JobStatus.QUEUED.value,
        JobStatus.RUNNING.value,
        JobStatus.SUCCEEDED.value,
    }:
        schedule.job_id = job.id
        db.commit()
        return PlanConfirmOut(plan=PlanOut.model_validate(plan), job_id=job.id, reused=True)
    run_count = int(
        db.scalar(
            select(func.count(ScheduledAccountRun.id)).where(
                ScheduledAccountRun.schedule_id == schedule.id
            )
        )
        or 0
    )
    if not job:
        job = Job(
            type="DEPLOY_SCHEDULE",
            status=JobStatus.QUEUED.value,
            connection_id=plan.connection_id,
            created_by_id=user.id,
            idempotency_key=key,
            progress_current=0,
            progress_total=run_count,
            payload={
                "plan_id": str(plan.id),
                "schedule_id": str(schedule.id),
                "execution_mode": plan.execution_mode,
            },
        )
        db.add(job)
        db.flush()
    else:
        job.status = JobStatus.QUEUED.value
        job.error_message = None
        job.progress_current = 0
        job.progress_total = run_count
    now = utcnow()
    schedule.job_id = job.id
    schedule.status = ScheduleStatus.PLANNED.value
    schedule.confirmed_at = now
    schedule.last_dispatch_at = now
    schedule.pause_reason = None
    schedule.recovery_required = False
    plan.status = PlanStatus.QUEUED.value
    plan.confirmed_at = now
    upload = db.get(CampaignUpload, plan.upload_id)
    if upload:
        upload.status = UploadStatus.QUEUED.value
    batch = db.get(LaunchBatch, plan.launch_batch_id) if plan.launch_batch_id else None
    if batch:
        batch.status = "SCHEDULED"
    db.add(
        ScheduleEvent(
            schedule_id=schedule.id,
            actor_user_id=user.id,
            event_type="SCHEDULE_CONFIRMED",
            message="Расписание подтверждено и ожидает планового времени",
            data={
                "plan_id": str(plan.id),
                "job_id": str(job.id),
                "confirmation": payload.confirmation,
            },
        )
    )
    record_audit(
        db,
        request,
        user,
        "schedule.confirm_paused",
        "deployment_schedule",
        str(schedule.id),
        {
            "plan_id": str(plan.id),
            "job_id": str(job.id),
            "mode": plan.execution_mode,
            "accounts": run_count,
        },
    )
    db.commit()
    db.refresh(plan)
    return PlanConfirmOut(plan=PlanOut.model_validate(plan), job_id=job.id, reused=False)


def _get_plan(db: Session, plan_id: UUID) -> DeploymentPlan:
    plan = db.get(DeploymentPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="План не найден")
    return plan


def _load_batch_context(
    db: Session,
    upload: CampaignUpload,
) -> tuple[LaunchBatch | None, list[AccountTestBundle], list[CampaignInstance]]:
    batch_id = (upload.draft or {}).get("launch_batch_id")
    if not batch_id:
        return None, [], []
    try:
        parsed_id = UUID(str(batch_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="В черновике сохранён некорректный Launch Batch ID") from exc
    batch = db.get(LaunchBatch, parsed_id)
    if not batch or batch.upload_id != upload.id:
        raise HTTPException(status_code=404, detail="Launch Batch этой загрузки не найден")
    bundles = list(
        db.scalars(select(AccountTestBundle).where(AccountTestBundle.launch_batch_id == batch.id)).all()
    )
    instances = list(
        db.scalars(select(CampaignInstance).where(CampaignInstance.launch_batch_id == batch.id)).all()
    )
    return batch, bundles, instances


def _validation_by_instance(snapshot: dict, validation: dict) -> dict[str, dict]:
    campaigns = snapshot.get("campaigns") or []
    result = {
        str(item.get("campaign_instance_id")): {"valid": True, "errors": [], "warnings": []}
        for item in campaigns
        if item.get("campaign_instance_id")
    }
    for kind in ("errors", "warnings"):
        for issue in validation.get(kind) or []:
            path = str(issue.get("path") or "")
            parts = path.split(".")
            if len(parts) < 2 or parts[0] != "campaigns" or not parts[1].isdigit():
                continue
            index = int(parts[1])
            if index >= len(campaigns):
                continue
            instance_id = str(campaigns[index].get("campaign_instance_id") or "")
            if instance_id not in result:
                continue
            result[instance_id][kind].append(issue)
            if kind == "errors":
                result[instance_id]["valid"] = False
    return result


def _save_instance_validation_results(db: Session, plan: DeploymentPlan, result: dict) -> None:
    rows = (result.get("details") or {}).get("instances") or []
    for row in rows:
        instance_id = row.get("campaign_instance_id")
        if not instance_id:
            continue
        try:
            instance = db.get(CampaignInstance, UUID(str(instance_id)))
        except ValueError:
            continue
        if not instance or instance.deployment_plan_id != plan.id:
            continue
        instance.google_validation = {
            "ok": bool(row.get("ok")),
            "mode": result.get("mode"),
            "errors": row.get("errors") or [],
            "warnings": row.get("warnings") or [],
            "request_ids": row.get("request_ids") or [],
            "google_contacted": bool((result.get("details") or {}).get("google_contacted")),
        }
        instance.request_ids = list(dict.fromkeys([*(instance.request_ids or []), *(row.get("request_ids") or [])]))
        instance.status = "VALIDATED" if row.get("ok") else "VALIDATION_FAILED"


def _valid_instance_ids(result: dict) -> list[str]:
    return [
        str(item["campaign_instance_id"])
        for item in (result.get("details") or {}).get("instances") or []
        if item.get("ok") and item.get("campaign_instance_id")
    ]
