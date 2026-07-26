from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf
from app.api.workflow_schemas import ScheduleActionIn, ScheduleConfigIn
from app.core.database import get_db
from app.core.security import utcnow
from app.db.models import (
    AccountTestBundle,
    CampaignInstance,
    CampaignUpload,
    DeploymentSchedule,
    DeploymentWave,
    GoogleConnection,
    LaunchBatch,
    MediaAsset,
    ScheduledAccountRun,
    ScheduleEvent,
    ScheduleRunStatus,
    ScheduleStatus,
    ScheduleWaveStatus,
    User,
)
from app.domain.audit import record_audit
from app.domain.scheduling import (
    ScheduleValidationError,
    build_schedule_preview,
    local_to_utc,
    schedule_fingerprint,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])

ACTIVE_RUN_STATUSES = {
    ScheduleRunStatus.QUEUED.value,
    ScheduleRunStatus.VALIDATING.value,
    ScheduleRunStatus.CREATING.value,
}
FUTURE_RUN_STATUSES = {
    ScheduleRunStatus.WAITING.value,
    ScheduleRunStatus.RETRY_WAIT.value,
    ScheduleRunStatus.QUEUED.value,
}
TERMINAL_RUN_STATUSES = {
    ScheduleRunStatus.SUCCEEDED.value,
    ScheduleRunStatus.FAILED.value,
    ScheduleRunStatus.CANCELLED.value,
    ScheduleRunStatus.SKIPPED.value,
}


@router.get("")
def list_schedules(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    schedules = list(
        db.scalars(
            select(DeploymentSchedule)
            .where(DeploymentSchedule.is_current.is_(True))
            .order_by(desc(DeploymentSchedule.created_at))
            .limit(200)
        ).all()
    )
    return [_schedule_out(db, item, include_events=False) for item in schedules]


@router.get("/{schedule_id}")
def get_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return _schedule_out(db, _get_schedule(db, schedule_id), include_events=True)


@router.post("/preview/{launch_batch_id}")
def preview_schedule(
    launch_batch_id: UUID,
    payload: ScheduleConfigIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    batch = _get_batch(db, launch_batch_id)
    preview = _preview(db, batch, payload)
    return preview


@router.post("/from-launch-batch/{launch_batch_id}", status_code=status.HTTP_201_CREATED)
def create_schedule(
    launch_batch_id: UUID,
    payload: ScheduleConfigIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    batch = _get_batch(db, launch_batch_id)
    preview = _preview(db, batch, payload)
    if not preview["valid"]:
        raise HTTPException(status_code=422, detail="Назначьте время каждому аккаунту")

    existing = db.scalar(
        select(DeploymentSchedule).where(
            DeploymentSchedule.launch_batch_id == batch.id,
            DeploymentSchedule.fingerprint == preview["fingerprint"],
        )
    )
    if existing:
        if not existing.is_current:
            raise HTTPException(
                status_code=409,
                detail="Такое расписание уже сохранено в истории; измените время или параметры",
            )
        return _schedule_out(db, existing, include_events=True)

    current = db.scalar(
        select(DeploymentSchedule)
        .where(
            DeploymentSchedule.launch_batch_id == batch.id,
            DeploymentSchedule.is_current.is_(True),
        )
        .order_by(desc(DeploymentSchedule.version_number))
    )
    if current and current.status not in {
        ScheduleStatus.DRAFT.value,
        ScheduleStatus.CANCELLED.value,
    }:
        raise HTTPException(
            status_code=409,
            detail="Подтверждённое расписание меняется только через раздел «Расписание»",
        )
    version = int(
        db.scalar(
            select(func.coalesce(func.max(DeploymentSchedule.version_number), 0)).where(
                DeploymentSchedule.launch_batch_id == batch.id
            )
        )
        or 0
    ) + 1
    if current:
        current.is_current = False

    connection = db.get(GoogleConnection, batch.connection_id) if batch.connection_id else None
    summary = {**preview["summary"], "warnings": preview["warnings"]}
    schedule = DeploymentSchedule(
        deployment_plan_id=None,
        upload_id=batch.upload_id,
        connection_id=batch.connection_id,
        launch_batch_id=batch.id,
        parent_schedule_id=current.id if current else None,
        mcc_customer_id=connection.login_customer_id if connection else None,
        mode=preview["mode"],
        status=ScheduleStatus.DRAFT.value,
        time_zone=preview["time_zone"],
        start_at=_dt(preview["summary"]["start_at"]),
        end_at=_dt(preview["summary"]["end_at"]),
        max_accounts_per_hour=preview["summary"]["max_accounts_per_hour"],
        max_accounts_per_day=preview["summary"]["max_accounts_per_day"],
        max_parallel=preview["summary"]["max_parallel"],
        circuit_breaker_threshold=preview["summary"]["circuit_breaker_threshold"],
        consecutive_serious_errors=0,
        version_number=version,
        fingerprint=preview["fingerprint"],
        is_current=True,
        manual_approval=bool(preview["config"].get("manual_approval", True)),
        config=preview["config"],
        summary=summary,
        created_by_id=user.id,
    )
    db.add(schedule)
    db.flush()
    waves = _create_waves(db, schedule, preview["waves"])
    for row in preview["runs"]:
        db.add(
            ScheduledAccountRun(
                schedule_id=schedule.id,
                wave_id=waves[int(row["wave_number"])].id,
                deployment_plan_id=None,
                account_test_bundle_id=UUID(row["account_test_bundle_id"]),
                customer_id=row["customer_id"],
                account_name=row["account_name"],
                position=row["position"],
                scheduled_for=_dt(row["scheduled_for"]),
                campaigns_count=row["campaigns_count"],
                status=ScheduleRunStatus.WAITING.value,
                attempts=0,
                deployment_key=row["deployment_key"],
                resource_names=[],
                request_ids=[],
                structured_error={},
                created_by_id=user.id,
            )
        )
    db.add(
        ScheduleEvent(
            schedule_id=schedule.id,
            actor_user_id=user.id,
            event_type="SCHEDULE_CREATED",
            message=f"Создано расписание версии {version}",
            data={"fingerprint": schedule.fingerprint, "mode": schedule.mode},
        )
    )
    upload = db.get(CampaignUpload, batch.upload_id)
    if upload:
        upload.draft = {**(upload.draft or {}), "schedule_id": str(schedule.id)}
    record_audit(
        db,
        request,
        user,
        "schedule.create",
        "deployment_schedule",
        str(schedule.id),
        {
            "launch_batch_id": str(batch.id),
            "mode": schedule.mode,
            "version": version,
            "fingerprint": schedule.fingerprint,
        },
    )
    db.commit()
    return _schedule_out(db, schedule, include_events=True)


@router.post("/{schedule_id}/actions")
def schedule_action(
    schedule_id: UUID,
    payload: ScheduleActionIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    if not payload.confirmation:
        raise HTTPException(status_code=422, detail="Подтвердите действие")
    schedule = _get_schedule(db, schedule_id)
    now = utcnow()
    action = payload.action
    result_schedule = schedule

    if action == "PAUSE":
        if schedule.status in {
            ScheduleStatus.COMPLETED.value,
            ScheduleStatus.COMPLETED_WITH_ERRORS.value,
            ScheduleStatus.CANCELLED.value,
        }:
            raise HTTPException(status_code=409, detail="Это расписание уже завершено")
        schedule.status = ScheduleStatus.PAUSED.value
        schedule.paused_at = now
        schedule.pause_reason = "Приостановлено пользователем"
        _event(db, schedule, user, action, "Расписание приостановлено")
    elif action == "RESUME":
        _resume_schedule(db, schedule, payload, now, user)
    elif action == "APPROVE_NEXT_WAVE":
        wave = db.scalar(
            select(DeploymentWave)
            .where(
                DeploymentWave.schedule_id == schedule.id,
                DeploymentWave.approval_required.is_(True),
                DeploymentWave.approved_at.is_(None),
                DeploymentWave.status.in_(
                    [
                        ScheduleWaveStatus.PLANNED.value,
                        ScheduleWaveStatus.WAITING_FOR_APPROVAL.value,
                    ]
                ),
            )
            .order_by(DeploymentWave.wave_number)
        )
        if not wave:
            raise HTTPException(status_code=409, detail="Нет волны, ожидающей подтверждения")
        wave.approved_at = now
        wave.approved_by_id = user.id
        wave.status = ScheduleWaveStatus.PLANNED.value
        schedule.status = ScheduleStatus.RUNNING.value
        schedule.pause_reason = None
        _event(db, schedule, user, action, f"Подтверждена волна {wave.wave_number}", wave=wave)
    elif action == "RUN_NEXT_NOW":
        run = db.scalar(
            select(ScheduledAccountRun)
            .where(
                ScheduledAccountRun.schedule_id == schedule.id,
                ScheduledAccountRun.status.in_(
                    [ScheduleRunStatus.WAITING.value, ScheduleRunStatus.RETRY_WAIT.value]
                ),
            )
            .order_by(ScheduledAccountRun.scheduled_for, ScheduledAccountRun.position)
        )
        if not run:
            raise HTTPException(status_code=409, detail="Нет ожидающих аккаунтов")
        run.scheduled_for = now
        run.next_retry_at = None
        run.status = ScheduleRunStatus.WAITING.value
        schedule.status = ScheduleStatus.RUNNING.value
        schedule.recovery_required = False
        schedule.last_dispatch_at = now
        _event(db, schedule, user, action, f"Аккаунт {run.account_name} поставлен следующим", run=run)
    elif action in {"RESCHEDULE_REMAINING", "MOVE_ACCOUNT"}:
        result_schedule = _create_changed_version(db, schedule, payload, now, user)
    elif action == "RETRY":
        runs = _selected_runs(db, schedule, payload.run_ids)
        if not runs:
            raise HTTPException(status_code=422, detail="Выберите ошибочные аккаунты")
        failed_runs = [run for run in runs if run.status == ScheduleRunStatus.FAILED.value]
        if not failed_runs:
            raise HTTPException(status_code=409, detail="Среди выбранных нет ошибочных аккаунтов")
        for run in failed_runs:
            run.status = ScheduleRunStatus.WAITING.value
            run.scheduled_for = now
            run.next_retry_at = None
            run.actual_completed_at = None
            run.structured_error = {}
            _event(db, schedule, user, action, f"Повтор разрешён: {run.account_name}", run=run)
        schedule.status = ScheduleStatus.RUNNING.value
        schedule.consecutive_serious_errors = 0
        schedule.pause_reason = None
    elif action == "CANCEL_SELECTED":
        runs = _selected_runs(db, schedule, payload.run_ids)
        if not runs:
            raise HTTPException(status_code=422, detail="Выберите аккаунты")
        future_runs = [run for run in runs if run.status in FUTURE_RUN_STATUSES]
        if not future_runs:
            raise HTTPException(status_code=409, detail="Среди выбранных нет будущих запусков")
        for run in future_runs:
            run.status = ScheduleRunStatus.CANCELLED.value
            run.actual_completed_at = now
            _event(db, schedule, user, action, f"Запуск отменён: {run.account_name}", run=run)
    elif action == "CANCEL_FUTURE":
        runs = list(
            db.scalars(
                select(ScheduledAccountRun).where(
                    ScheduledAccountRun.schedule_id == schedule.id,
                    ScheduledAccountRun.status.in_(list(FUTURE_RUN_STATUSES)),
                )
            ).all()
        )
        if not runs:
            raise HTTPException(status_code=409, detail="Будущих запусков нет")
        for run in runs:
            run.status = ScheduleRunStatus.CANCELLED.value
            run.actual_completed_at = now
        schedule.status = ScheduleStatus.CANCELLED.value
        schedule.completed_at = now
        schedule.pause_reason = "Будущие запуски отменены пользователем"
        _event(db, schedule, user, action, f"Отменено будущих запусков: {len(runs)}")
    else:  # pragma: no cover
        raise HTTPException(status_code=422, detail="Неизвестное действие")

    record_audit(
        db,
        request,
        user,
        f"schedule.{action.lower()}",
        "deployment_schedule",
        str(result_schedule.id),
        {
            "source_schedule_id": str(schedule.id),
            "run_ids": [str(item) for item in payload.run_ids],
            "target_wave_number": payload.target_wave_number,
            "shift_minutes": payload.shift_minutes,
        },
    )
    db.commit()
    return _schedule_out(db, result_schedule, include_events=True)


@router.get("/{schedule_id}/report.csv")
def download_schedule_report(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    schedule = _get_schedule(db, schedule_id)
    runs = list(
        db.scalars(
            select(ScheduledAccountRun)
            .where(ScheduledAccountRun.schedule_id == schedule.id)
            .order_by(ScheduledAccountRun.position)
        ).all()
    )
    waves = {
        item.id: item.wave_number
        for item in db.scalars(
            select(DeploymentWave).where(DeploymentWave.schedule_id == schedule.id)
        ).all()
    }
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "wave",
            "planned_time_utc",
            "actual_start_utc",
            "actual_end_utc",
            "account",
            "customer_id",
            "campaigns",
            "status",
            "attempts",
            "request_ids",
            "resource_names",
            "error",
        ]
    )
    for run in runs:
        writer.writerow(
            [
                waves.get(run.wave_id),
                run.scheduled_for.isoformat(),
                run.actual_started_at.isoformat() if run.actual_started_at else "",
                run.actual_completed_at.isoformat() if run.actual_completed_at else "",
                run.account_name,
                run.customer_id,
                run.campaigns_count,
                run.status,
                run.attempts,
                " | ".join(run.request_ids or []),
                " | ".join(run.resource_names or []),
                (run.structured_error or {}).get("message", ""),
            ]
        )
    filename = f"schedule-{schedule.id}-v{schedule.version_number}.csv"
    return Response(
        buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def schedule_plan_snapshot(db: Session, schedule: DeploymentSchedule) -> dict:
    waves = list(
        db.scalars(
            select(DeploymentWave)
            .where(DeploymentWave.schedule_id == schedule.id)
            .order_by(DeploymentWave.wave_number)
        ).all()
    )
    wave_numbers = {item.id: item.wave_number for item in waves}
    runs = list(
        db.scalars(
            select(ScheduledAccountRun)
            .where(ScheduledAccountRun.schedule_id == schedule.id)
            .order_by(ScheduledAccountRun.position)
        ).all()
    )
    return {
        "schedule_id": str(schedule.id),
        "schedule_version": schedule.version_number,
        "fingerprint": schedule.fingerprint,
        "mode": schedule.mode,
        "time_zone": schedule.time_zone,
        "max_accounts_per_hour": schedule.max_accounts_per_hour,
        "max_accounts_per_day": schedule.max_accounts_per_day,
        "max_parallel": schedule.max_parallel,
        "circuit_breaker_threshold": schedule.circuit_breaker_threshold,
        "manual_approval": schedule.manual_approval,
        "waves": [
            {
                "wave_number": item.wave_number,
                "starts_at": item.starts_at.isoformat(),
                "ends_at": item.ends_at.isoformat(),
                "observation_until": item.observation_until.isoformat() if item.observation_until else None,
                "approval_required": item.approval_required,
            }
            for item in waves
        ],
        "runs": [
            {
                "account_test_bundle_id": str(item.account_test_bundle_id),
                "customer_id": item.customer_id,
                "campaigns_count": item.campaigns_count,
                "wave_number": wave_numbers[item.wave_id],
                "position": item.position,
                "scheduled_for": item.scheduled_for.isoformat(),
                "deployment_key": item.deployment_key,
            }
            for item in runs
        ],
    }


def _preview(db: Session, batch: LaunchBatch, payload: ScheduleConfigIn) -> dict:
    bundles = list(
        db.scalars(
            select(AccountTestBundle)
            .where(AccountTestBundle.launch_batch_id == batch.id)
            .order_by(AccountTestBundle.account_name, AccountTestBundle.customer_id)
        ).all()
    )
    instances = list(
        db.scalars(
            select(CampaignInstance).where(
                CampaignInstance.launch_batch_id == batch.id,
                CampaignInstance.included.is_(True),
            )
        ).all()
    )
    by_bundle: dict[UUID, list[CampaignInstance]] = {}
    for instance in instances:
        by_bundle.setdefault(instance.account_test_bundle_id, []).append(instance)
    accounts = [
        {
            "id": item.id,
            "customer_id": item.customer_id,
            "account_name": item.account_name,
            "campaigns_count": len(by_bundle.get(item.id, [])),
            "budget_micros": sum(row.budget_micros for row in by_bundle.get(item.id, [])),
        }
        for item in bundles
    ]
    try:
        preview = build_schedule_preview(
            accounts,
            payload.model_dump(mode="json", exclude_none=True),
            now=utcnow(),
        )
    except ScheduleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    asset_warnings = _asset_warnings(db, instances)
    preview["warnings"].extend(asset_warnings)
    preview["summary"]["warnings"] = len(preview["warnings"])
    preview["summary"]["not_ready_assets"] = len(asset_warnings)
    return preview


def _asset_warnings(db: Session, instances: list[CampaignInstance]) -> list[dict]:
    media_ids = {
        str(media_id)
        for instance in instances
        for media_id in (
            (instance.creative_assignment or {}).get("media_ids")
            or (instance.creative_assignment or {}).get("items")
            or []
        )
    }
    if not media_ids:
        return []
    assets = []
    for media_id in media_ids:
        try:
            asset = db.get(MediaAsset, UUID(media_id))
        except ValueError:
            asset = None
        if not asset or asset.status != "READY":
            assets.append(asset.name if asset else media_id)
    if not assets:
        return []
    return [
        {
            "code": "MEDIA_NOT_READY",
            "message": "Неготовые или отсутствующие медиа: " + ", ".join(sorted(assets)[:20]),
        }
    ]


def _create_waves(
    db: Session,
    schedule: DeploymentSchedule,
    rows: list[dict],
) -> dict[int, DeploymentWave]:
    result = {}
    for row in rows:
        wave = DeploymentWave(
            schedule_id=schedule.id,
            wave_number=int(row["wave_number"]),
            status=ScheduleWaveStatus.PLANNED.value,
            starts_at=_dt(row["starts_at"]),
            ends_at=_dt(row["ends_at"]),
            observation_until=_dt(row["observation_until"]) if row.get("observation_until") else None,
            approval_required=bool(row.get("approval_required")),
            config=row.get("config") or {},
        )
        db.add(wave)
        db.flush()
        result[wave.wave_number] = wave
    return result


def _resume_schedule(
    db: Session,
    schedule: DeploymentSchedule,
    payload: ScheduleActionIn,
    now: datetime,
    user: User,
) -> None:
    if schedule.status not in {
        ScheduleStatus.PAUSED.value,
        ScheduleStatus.WAITING_FOR_APPROVAL.value,
        ScheduleStatus.OBSERVATION.value,
        ScheduleStatus.PLANNED.value,
    }:
        raise HTTPException(status_code=409, detail="Расписание нельзя продолжить из текущего состояния")
    if payload.recovery_strategy == "SEQUENTIAL":
        runs = list(
            db.scalars(
                select(ScheduledAccountRun)
                .where(
                    ScheduledAccountRun.schedule_id == schedule.id,
                    ScheduledAccountRun.status.in_(
                        [ScheduleRunStatus.WAITING.value, ScheduleRunStatus.RETRY_WAIT.value]
                    ),
                    ScheduledAccountRun.scheduled_for < now,
                )
                .order_by(ScheduledAccountRun.position)
            ).all()
        )
        interval_seconds = max(1, 3600 // schedule.max_accounts_per_hour)
        for index, run in enumerate(runs):
            run.scheduled_for = now + timedelta(seconds=interval_seconds * index)
            if run.status == ScheduleRunStatus.RETRY_WAIT.value:
                run.next_retry_at = run.scheduled_for
    schedule.status = ScheduleStatus.RUNNING.value
    schedule.paused_at = None
    schedule.pause_reason = None
    schedule.recovery_required = False
    schedule.last_dispatch_at = now
    _event(db, schedule, user, "RESUME", "Расписание продолжено")


def _create_changed_version(
    db: Session,
    schedule: DeploymentSchedule,
    payload: ScheduleActionIn,
    now: datetime,
    user: User,
) -> DeploymentSchedule:
    if not schedule.is_current:
        raise HTTPException(status_code=409, detail="Изменять можно только текущую версию")
    active_count = int(
        db.scalar(
            select(func.count(ScheduledAccountRun.id)).where(
                ScheduledAccountRun.schedule_id == schedule.id,
                ScheduledAccountRun.status.in_(list(ACTIVE_RUN_STATUSES)),
            )
        )
        or 0
    )
    if active_count:
        raise HTTPException(status_code=409, detail="Дождитесь завершения текущего аккаунта")
    old_waves = list(
        db.scalars(
            select(DeploymentWave)
            .where(DeploymentWave.schedule_id == schedule.id)
            .order_by(DeploymentWave.wave_number)
        ).all()
    )
    old_runs = list(
        db.scalars(
            select(ScheduledAccountRun)
            .where(ScheduledAccountRun.schedule_id == schedule.id)
            .order_by(ScheduledAccountRun.position)
        ).all()
    )
    target_run_id = payload.run_ids[0] if payload.run_ids else None
    remaining = [item for item in old_runs if item.status not in TERMINAL_RUN_STATUSES]
    if not remaining:
        raise HTTPException(status_code=409, detail="Будущих запусков для изменения нет")
    if payload.action == "MOVE_ACCOUNT":
        if not target_run_id or not payload.target_wave_number:
            raise HTTPException(status_code=422, detail="Выберите аккаунт и целевую волну")
        if payload.target_wave_number not in {item.wave_number for item in old_waves}:
            raise HTTPException(status_code=422, detail="Целевая волна не найдена")
        if target_run_id not in {item.id for item in remaining}:
            raise HTTPException(status_code=409, detail="Переносить можно только будущий запуск")

    changed_times: dict[UUID, datetime] = {}
    if payload.action == "RESCHEDULE_REMAINING":
        if payload.start_local and payload.end_local:
            try:
                start_at = local_to_utc(payload.start_local, schedule.time_zone, field="start")
                end_at = local_to_utc(payload.end_local, schedule.time_zone, field="end")
            except ScheduleValidationError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if not start_at or not end_at or end_at <= start_at:
                raise HTTPException(status_code=422, detail="Проверьте новый диапазон времени")
            interval = (end_at - start_at) / max(1, len(remaining))
            changed_times = {item.id: start_at + interval * index for index, item in enumerate(remaining)}
        else:
            shift = payload.shift_minutes or 0
            if shift == 0:
                raise HTTPException(status_code=422, detail="Укажите сдвиг или новый диапазон")
            changed_times = {item.id: item.scheduled_for + timedelta(minutes=shift) for item in remaining}

    old_wave_numbers = {item.id: item.wave_number for item in old_waves}
    run_wave_numbers = {
        item.id: (
            payload.target_wave_number
            if payload.action == "MOVE_ACCOUNT" and item.id == target_run_id
            else old_wave_numbers[item.wave_id]
        )
        for item in old_runs
    }
    wave_rows = []
    for old_wave in old_waves:
        rows = [item for item in old_runs if run_wave_numbers[item.id] == old_wave.wave_number]
        times = [changed_times.get(item.id, item.scheduled_for) for item in rows]
        starts_at = min(times, default=old_wave.starts_at)
        ends_at = max(times, default=old_wave.ends_at)
        observation_until = old_wave.observation_until
        if observation_until and rows:
            shift = starts_at - min(item.scheduled_for for item in rows)
            observation_until += shift
        wave_rows.append(
            {
                "wave_number": old_wave.wave_number,
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "observation_until": observation_until.isoformat() if observation_until else None,
                "approval_required": old_wave.approval_required,
            }
        )
    snapshot = {
        "schema_version": 1,
        "mode": schedule.mode,
        "time_zone": schedule.time_zone,
        "config": {
            **(schedule.config or {}),
            "parent_fingerprint": schedule.fingerprint,
            "change": payload.action,
            "version": schedule.version_number + 1,
        },
        "waves": wave_rows,
        "runs": [
            {
                "account_test_bundle_id": str(item.account_test_bundle_id),
                "customer_id": item.customer_id,
                "campaigns_count": item.campaigns_count,
                "wave_number": run_wave_numbers[item.id],
                "position": item.position,
                "scheduled_for": changed_times.get(item.id, item.scheduled_for).isoformat(),
                "deployment_key": item.deployment_key,
            }
            for item in old_runs
        ],
    }
    fingerprint = schedule_fingerprint(snapshot)
    new_schedule = DeploymentSchedule(
        deployment_plan_id=schedule.deployment_plan_id,
        upload_id=schedule.upload_id,
        connection_id=schedule.connection_id,
        launch_batch_id=schedule.launch_batch_id,
        job_id=schedule.job_id,
        parent_schedule_id=schedule.id,
        mcc_customer_id=schedule.mcc_customer_id,
        mode=schedule.mode,
        status=(
            ScheduleStatus.PAUSED.value
            if schedule.status == ScheduleStatus.PAUSED.value
            else ScheduleStatus.RUNNING.value
        ),
        time_zone=schedule.time_zone,
        start_at=min(
            (changed_times.get(item.id, item.scheduled_for) for item in old_runs),
            default=schedule.start_at,
        ),
        end_at=max(
            (changed_times.get(item.id, item.scheduled_for) for item in old_runs),
            default=schedule.end_at,
        ),
        max_accounts_per_hour=schedule.max_accounts_per_hour,
        max_accounts_per_day=schedule.max_accounts_per_day,
        max_parallel=schedule.max_parallel,
        circuit_breaker_threshold=schedule.circuit_breaker_threshold,
        consecutive_serious_errors=schedule.consecutive_serious_errors,
        version_number=schedule.version_number + 1,
        fingerprint=fingerprint,
        is_current=True,
        manual_approval=schedule.manual_approval,
        config=snapshot["config"],
        summary={**(schedule.summary or {}), "version_change": payload.action},
        recovery_required=False,
        confirmed_at=schedule.confirmed_at,
        last_dispatch_at=now,
        created_by_id=user.id,
    )
    schedule.is_current = False
    schedule.status = ScheduleStatus.CANCELLED.value
    schedule.completed_at = now
    schedule.pause_reason = f"Заменено версией {new_schedule.version_number}"
    for run in remaining:
        run.status = ScheduleRunStatus.CANCELLED.value
        run.actual_completed_at = now
    db.add(new_schedule)
    db.flush()

    wave_map: dict[int, DeploymentWave] = {}
    wave_rows_by_number = {int(item["wave_number"]): item for item in wave_rows}
    for old_wave in old_waves:
        wave_row = wave_rows_by_number[old_wave.wave_number]
        wave = DeploymentWave(
            schedule_id=new_schedule.id,
            wave_number=old_wave.wave_number,
            status=old_wave.status,
            starts_at=_dt(wave_row["starts_at"]),
            ends_at=_dt(wave_row["ends_at"]),
            observation_until=(
                _dt(wave_row["observation_until"])
                if wave_row.get("observation_until")
                else None
            ),
            approval_required=old_wave.approval_required,
            approved_at=old_wave.approved_at,
            approved_by_id=old_wave.approved_by_id,
            config=old_wave.config or {},
        )
        db.add(wave)
        db.flush()
        wave_map[wave.wave_number] = wave
    for old_run in old_runs:
        wave_number = run_wave_numbers[old_run.id]
        terminal = old_run.status in TERMINAL_RUN_STATUSES and old_run.id not in {item.id for item in remaining}
        db.add(
            ScheduledAccountRun(
                schedule_id=new_schedule.id,
                wave_id=wave_map[int(wave_number)].id,
                deployment_plan_id=old_run.deployment_plan_id,
                account_test_bundle_id=old_run.account_test_bundle_id,
                customer_id=old_run.customer_id,
                account_name=old_run.account_name,
                position=old_run.position,
                scheduled_for=changed_times.get(old_run.id, old_run.scheduled_for),
                actual_started_at=old_run.actual_started_at if terminal else None,
                actual_completed_at=old_run.actual_completed_at if terminal else None,
                campaigns_count=old_run.campaigns_count,
                status=old_run.status if terminal else ScheduleRunStatus.WAITING.value,
                attempts=old_run.attempts if terminal else 0,
                deployment_key=old_run.deployment_key,
                resource_names=old_run.resource_names or [],
                request_ids=old_run.request_ids or [],
                structured_error=old_run.structured_error if terminal else {},
                created_by_id=user.id,
            )
        )
    _event(
        db,
        new_schedule,
        user,
        "VERSION_CREATED",
        f"Создана версия {new_schedule.version_number} из версии {schedule.version_number}",
        data={"action": payload.action, "parent_schedule_id": str(schedule.id)},
    )
    upload = db.get(CampaignUpload, schedule.upload_id)
    if upload:
        upload.draft = {**(upload.draft or {}), "schedule_id": str(new_schedule.id)}
    return new_schedule


def _schedule_out(db: Session, schedule: DeploymentSchedule, *, include_events: bool) -> dict:
    waves = list(
        db.scalars(
            select(DeploymentWave)
            .where(DeploymentWave.schedule_id == schedule.id)
            .order_by(DeploymentWave.wave_number)
        ).all()
    )
    runs = list(
        db.scalars(
            select(ScheduledAccountRun)
            .where(ScheduledAccountRun.schedule_id == schedule.id)
            .order_by(ScheduledAccountRun.position)
        ).all()
    )
    wave_numbers = {item.id: item.wave_number for item in waves}
    status_counts = Counter(item.status for item in runs)
    active_wave = next(
        (
            item
            for item in waves
            if item.status
            not in {ScheduleWaveStatus.COMPLETED.value, ScheduleWaveStatus.CANCELLED.value}
        ),
        waves[-1] if waves else None,
    )
    next_run = next(
        (
            item
            for item in sorted(runs, key=lambda row: (row.scheduled_for, row.position))
            if item.status in {
                ScheduleRunStatus.WAITING.value,
                ScheduleRunStatus.RETRY_WAIT.value,
                ScheduleRunStatus.QUEUED.value,
            }
        ),
        None,
    )
    events = []
    if include_events:
        events = list(
            db.scalars(
                select(ScheduleEvent)
                .where(ScheduleEvent.schedule_id == schedule.id)
                .order_by(desc(ScheduleEvent.created_at))
                .limit(200)
            ).all()
        )
    return {
        "id": schedule.id,
        "deployment_plan_id": schedule.deployment_plan_id,
        "upload_id": schedule.upload_id,
        "connection_id": schedule.connection_id,
        "launch_batch_id": schedule.launch_batch_id,
        "parent_schedule_id": schedule.parent_schedule_id,
        "mcc_customer_id": schedule.mcc_customer_id,
        "mode": schedule.mode,
        "status": schedule.status,
        "time_zone": schedule.time_zone,
        "start_at": schedule.start_at,
        "end_at": schedule.end_at,
        "max_accounts_per_hour": schedule.max_accounts_per_hour,
        "max_accounts_per_day": schedule.max_accounts_per_day,
        "max_parallel": schedule.max_parallel,
        "circuit_breaker_threshold": schedule.circuit_breaker_threshold,
        "consecutive_serious_errors": schedule.consecutive_serious_errors,
        "version_number": schedule.version_number,
        "fingerprint": schedule.fingerprint,
        "is_current": schedule.is_current,
        "manual_approval": schedule.manual_approval,
        "config": schedule.config,
        "summary": schedule.summary,
        "pause_reason": schedule.pause_reason,
        "recovery_required": schedule.recovery_required,
        "confirmed_at": schedule.confirmed_at,
        "paused_at": schedule.paused_at,
        "completed_at": schedule.completed_at,
        "last_dispatch_at": schedule.last_dispatch_at,
        "created_at": schedule.created_at,
        "updated_at": schedule.updated_at,
        "progress": {
            "total_accounts": len(runs),
            "completed_accounts": sum(
                status_counts[item]
                for item in (
                    ScheduleRunStatus.SUCCEEDED.value,
                    ScheduleRunStatus.FAILED.value,
                    ScheduleRunStatus.CANCELLED.value,
                    ScheduleRunStatus.SKIPPED.value,
                )
            ),
            "successful_accounts": status_counts[ScheduleRunStatus.SUCCEEDED.value],
            "failed_accounts": status_counts[ScheduleRunStatus.FAILED.value],
            "waiting_accounts": sum(
                status_counts[item]
                for item in (
                    ScheduleRunStatus.WAITING.value,
                    ScheduleRunStatus.RETRY_WAIT.value,
                    ScheduleRunStatus.QUEUED.value,
                    ScheduleRunStatus.VALIDATING.value,
                    ScheduleRunStatus.CREATING.value,
                )
            ),
            "created_campaigns": sum(
                item.campaigns_count for item in runs if item.status == ScheduleRunStatus.SUCCEEDED.value
            ),
            "current_wave": active_wave.wave_number if active_wave else None,
            "next_account": next_run.account_name if next_run else None,
            "next_run_at": next_run.next_retry_at or next_run.scheduled_for if next_run else None,
        },
        "waves": [
            {
                "id": item.id,
                "wave_number": item.wave_number,
                "status": item.status,
                "starts_at": item.starts_at,
                "ends_at": item.ends_at,
                "observation_until": item.observation_until,
                "approval_required": item.approval_required,
                "approved_at": item.approved_at,
                "config": item.config,
            }
            for item in waves
        ],
        "runs": [
            {
                "id": item.id,
                "wave_id": item.wave_id,
                "wave_number": wave_numbers.get(item.wave_id),
                "account_test_bundle_id": item.account_test_bundle_id,
                "customer_id": item.customer_id,
                "account_name": item.account_name,
                "position": item.position,
                "scheduled_for": item.scheduled_for,
                "actual_started_at": item.actual_started_at,
                "actual_completed_at": item.actual_completed_at,
                "campaigns_count": item.campaigns_count,
                "status": item.status,
                "attempts": item.attempts,
                "next_retry_at": item.next_retry_at,
                "deployment_key": item.deployment_key,
                "resource_names": item.resource_names,
                "request_ids": item.request_ids,
                "structured_error": item.structured_error,
            }
            for item in runs
        ],
        "events": [
            {
                "id": item.id,
                "event_type": item.event_type,
                "level": item.level,
                "message": item.message,
                "data": item.data,
                "created_at": item.created_at,
            }
            for item in events
        ],
    }


def _selected_runs(
    db: Session,
    schedule: DeploymentSchedule,
    run_ids: list[UUID],
) -> list[ScheduledAccountRun]:
    if not run_ids:
        return []
    return list(
        db.scalars(
            select(ScheduledAccountRun).where(
                ScheduledAccountRun.schedule_id == schedule.id,
                ScheduledAccountRun.id.in_(run_ids),
            )
        ).all()
    )


def _event(
    db: Session,
    schedule: DeploymentSchedule,
    user: User | None,
    event_type: str,
    message: str,
    *,
    wave: DeploymentWave | None = None,
    run: ScheduledAccountRun | None = None,
    data: dict | None = None,
    level: str = "INFO",
) -> None:
    db.add(
        ScheduleEvent(
            schedule_id=schedule.id,
            wave_id=wave.id if wave else (run.wave_id if run else None),
            account_run_id=run.id if run else None,
            actor_user_id=user.id if user else None,
            event_type=event_type,
            level=level,
            message=message,
            data=data or {},
        )
    )


def _get_schedule(db: Session, schedule_id: UUID) -> DeploymentSchedule:
    schedule = db.get(DeploymentSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Расписание не найдено")
    return schedule


def _get_batch(db: Session, launch_batch_id: UUID) -> LaunchBatch:
    batch = db.get(LaunchBatch, launch_batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Launch Batch не найден")
    return batch


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
