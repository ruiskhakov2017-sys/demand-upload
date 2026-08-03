from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select

from app.core.database import SessionLocal
from app.core.security import utcnow
from app.db.models import (
    AccountTestBundle,
    CampaignInstance,
    CampaignUpload,
    DeploymentPlan,
    DeploymentSchedule,
    DeploymentWave,
    GoogleConnection,
    Job,
    JobEvent,
    JobStatus,
    MediaAsset,
    PlanStatus,
    ScheduledAccountRun,
    ScheduleEvent,
    ScheduleRunStatus,
    ScheduleStatus,
    ScheduleWaveStatus,
    UploadStatus,
)
from app.domain.planner import validate_plan_snapshot
from app.domain.scheduling import (
    circuit_breaker_decision,
    is_transient_error,
    normalize_error_codes,
    retry_delay_seconds,
    should_pause_after_downtime,
    snapshot_fingerprint,
)
from app.domain_validation.persistence import validate_snapshot
from app.domain_validation.service import (
    blocked_execution_result,
    filter_blocked_campaigns,
    merge_domain_skips,
)
from app.google_ads.execution_guard import refresh_google_test_target
from app.google_ads.interface import PlanExecutionResult
from app.google_ads.mock_adapter import MockGoogleAdsAdapter
from app.google_ads.safety import require_execution_mode_for_connection
from app.google_ads.service import build_google_ads_adapter, is_google_connection_active
from app.jobs.celery_app import celery_app
from app.jobs.tasks import _save_deployment_instances, _update_batch_deployment_status

DISPATCHABLE_SCHEDULE_STATUSES = {
    ScheduleStatus.PLANNED.value,
    ScheduleStatus.RUNNING.value,
    ScheduleStatus.OBSERVATION.value,
    ScheduleStatus.WAITING_FOR_APPROVAL.value,
}
ACTIVE_RUN_STATUSES = {
    ScheduleRunStatus.QUEUED.value,
    ScheduleRunStatus.VALIDATING.value,
    ScheduleRunStatus.CREATING.value,
}
TERMINAL_RUN_STATUSES = {
    ScheduleRunStatus.SUCCEEDED.value,
    ScheduleRunStatus.FAILED.value,
    ScheduleRunStatus.CANCELLED.value,
    ScheduleRunStatus.SKIPPED.value,
}


@celery_app.task(name="app.jobs.dispatch_due_scheduled_accounts")
def dispatch_due_scheduled_accounts(now_iso: str | None = None) -> dict:
    now = _managed_now(now_iso)
    dispatched: list[str] = []
    paused: list[str] = []
    with SessionLocal() as db:
        schedule_ids = list(
            db.scalars(
                select(DeploymentSchedule.id).where(
                    DeploymentSchedule.is_current.is_(True),
                    DeploymentSchedule.status.in_(list(DISPATCHABLE_SCHEDULE_STATUSES)),
                )
            ).all()
        )
        for schedule_id in schedule_ids:
            schedule = db.scalar(
                select(DeploymentSchedule)
                .where(DeploymentSchedule.id == schedule_id)
                .with_for_update(skip_locked=True)
            )
            if not schedule:
                db.rollback()
                continue
            previous_dispatch_at = schedule.last_dispatch_at
            _recover_stale_runs(db, schedule, now)
            eligible_wave_ids = _advance_schedule_state(db, schedule, now)
            if schedule.status not in {
                ScheduleStatus.PLANNED.value,
                ScheduleStatus.RUNNING.value,
            }:
                schedule.last_dispatch_at = now
                _update_tracking_state(db, schedule, now)
                db.commit()
                continue

            due_count = _due_count(db, schedule, eligible_wave_ids, now)
            recovery_threshold = int((schedule.config or {}).get("recovery_pause_after_seconds") or 300)
            if should_pause_after_downtime(
                now=now,
                last_dispatch_at=previous_dispatch_at,
                overdue_count=due_count,
                max_parallel=schedule.max_parallel,
                threshold_seconds=recovery_threshold,
            ):
                schedule.status = ScheduleStatus.PAUSED.value
                schedule.paused_at = now
                schedule.pause_reason = (
                    f"После простоя накопилось просроченных аккаунтов: {due_count}. "
                    "Выберите способ продолжения."
                )
                schedule.recovery_required = True
                _event(
                    db,
                    schedule,
                    "RECOVERY_PAUSE",
                    schedule.pause_reason,
                    data={"overdue_accounts": due_count},
                    level="WARNING",
                )
                paused.append(str(schedule.id))
                schedule.last_dispatch_at = now
                db.commit()
                continue

            schedule.last_dispatch_at = now
            slots = _available_slots(db, schedule, now)
            if slots <= 0 or not eligible_wave_ids:
                _update_tracking_state(db, schedule, now)
                db.commit()
                continue
            runs = list(
                db.scalars(
                    select(ScheduledAccountRun)
                    .where(
                        ScheduledAccountRun.schedule_id == schedule.id,
                        ScheduledAccountRun.wave_id.in_(eligible_wave_ids),
                        or_(
                            (
                                (ScheduledAccountRun.status == ScheduleRunStatus.WAITING.value)
                                & (ScheduledAccountRun.scheduled_for <= now)
                            ),
                            (
                                (ScheduledAccountRun.status == ScheduleRunStatus.RETRY_WAIT.value)
                                & (ScheduledAccountRun.next_retry_at.is_not(None))
                                & (ScheduledAccountRun.next_retry_at <= now)
                            ),
                        ),
                    )
                    .order_by(ScheduledAccountRun.scheduled_for, ScheduledAccountRun.position)
                    .with_for_update(skip_locked=True)
                    .limit(slots)
                ).all()
            )
            for run in runs:
                run.status = ScheduleRunStatus.QUEUED.value
                run.last_heartbeat_at = now
                wave = db.get(DeploymentWave, run.wave_id)
                if wave and wave.status == ScheduleWaveStatus.PLANNED.value:
                    wave.status = ScheduleWaveStatus.RUNNING.value
                schedule.status = ScheduleStatus.RUNNING.value
                _event(
                    db,
                    schedule,
                    "ACCOUNT_QUEUED",
                    f"Аккаунт {run.account_name} передан worker",
                    run=run,
                )
                dispatched.append(str(run.id))
            _update_tracking_state(db, schedule, now)
            db.commit()

    enqueued: list[str] = []
    for run_id in dispatched:
        try:
            execute_scheduled_account_run.delay(run_id)
            enqueued.append(run_id)
        except Exception as exc:  # pragma: no cover - depends on broker availability
            _return_failed_enqueue(run_id, str(exc), now)
    return {
        "ok": True,
        "checked_at": now.isoformat(),
        "claimed": len(dispatched),
        "enqueued": len(enqueued),
        "paused_for_recovery": paused,
    }


@celery_app.task(name="app.jobs.execute_scheduled_account_run")
def execute_scheduled_account_run(run_id: str, now_iso: str | None = None) -> dict:
    now = _managed_now(now_iso)
    with SessionLocal() as db:
        run = db.scalar(
            select(ScheduledAccountRun)
            .where(ScheduledAccountRun.id == UUID(run_id))
            .with_for_update(skip_locked=True)
        )
        if not run:
            return {"ok": False, "error": "scheduled account run not found"}
        schedule = db.get(DeploymentSchedule, run.schedule_id)
        if not schedule:
            return {"ok": False, "error": "schedule not found"}
        if run.status == ScheduleRunStatus.SUCCEEDED.value:
            return {"ok": True, "reused": True, "resources": run.resource_names}
        if run.status != ScheduleRunStatus.QUEUED.value:
            return {"ok": False, "skipped": True, "status": run.status}
        if schedule.status == ScheduleStatus.PAUSED.value:
            run.status = ScheduleRunStatus.WAITING.value
            run.last_heartbeat_at = now
            db.commit()
            return {"ok": False, "skipped": True, "status": schedule.status}
        if schedule.status in {
            ScheduleStatus.CANCELLED.value,
            ScheduleStatus.COMPLETED.value,
            ScheduleStatus.COMPLETED_WITH_ERRORS.value,
        }:
            run.status = ScheduleRunStatus.CANCELLED.value
            run.actual_completed_at = now
            db.commit()
            return {"ok": False, "skipped": True, "status": schedule.status}

        run.status = ScheduleRunStatus.VALIDATING.value
        run.attempts += 1
        run.actual_started_at = run.actual_started_at or now
        run.last_heartbeat_at = now
        schedule.status = ScheduleStatus.RUNNING.value
        plan = db.get(DeploymentPlan, run.deployment_plan_id)
        bundle = db.get(AccountTestBundle, run.account_test_bundle_id)
        wave = db.get(DeploymentWave, run.wave_id)
        if wave:
            wave.status = ScheduleWaveStatus.RUNNING.value
        _event(
            db,
            schedule,
            "ACCOUNT_VALIDATING",
            f"Начата JIT-проверка аккаунта {run.account_name}",
            run=run,
            data={"attempt": run.attempts},
        )
        _mark_tracking_running(db, schedule, plan)
        db.commit()

        try:
            if not plan or not bundle:
                raise ScheduledExecutionError(
                    "SYSTEM_CONFIGURATION",
                    "Immutable plan или Launch Group не найдены",
                )
            if snapshot_fingerprint(plan.snapshot) != plan.fingerprint:
                raise ScheduledExecutionError(
                    "PLAN_FINGERPRINT_MISMATCH",
                    "Immutable plan был изменён после подтверждения",
                )
            snapshot, reused_resources = _account_snapshot(db, plan, bundle)
            domain_report = validate_snapshot(
                snapshot,
                cached_report=plan.snapshot.get("domain_validation") or {},
                force=plan.execution_mode == "GOOGLE_TEST",
            )
            snapshot, domain_skipped = filter_blocked_campaigns(snapshot, domain_report)
            if domain_skipped and not snapshot.get("campaigns"):
                blocked_result = blocked_execution_result(plan.execution_mode, domain_skipped, domain_report)
                _save_deployment_instances(db, plan, blocked_result)
                raise ScheduledExecutionError(
                    "DOMAIN_VALIDATION_BLOCKED",
                    "DOMAIN_VALIDATION_BLOCKED",
                    blocked_result.errors,
                )
            _check_assets(db, snapshot)
            local = validate_plan_snapshot(snapshot)
            if not local["valid"]:
                raise ScheduledExecutionError(
                    "LOCAL_VALIDATION_FAILED",
                    "Локальная проверка Launch Group не пройдена",
                    local["errors"],
                )
            adapter, guard_request_ids = _adapter_for_run(
                db, schedule, plan, bundle
            )
            run.request_ids = _unique(
                [*(run.request_ids or []), *guard_request_ids]
            )
            if snapshot.get("campaigns"):
                validation = adapter.validate_plan(snapshot)
                _save_jit_validation(db, plan, validation)
                run.request_ids = _unique([*(run.request_ids or []), *validation.request_ids])
                if not validation.ok:
                    raise ScheduledExecutionError(
                        "VALIDATE_ONLY_FAILED",
                        "JIT validate_only завершился ошибкой",
                        validation.errors,
                        validation.request_ids,
                    )
            else:
                validation = _empty_result(plan.execution_mode, validate_only=True)

            run.status = ScheduleRunStatus.CREATING.value
            run.last_heartbeat_at = utcnow()
            _event(
                db,
                schedule,
                "ACCOUNT_CREATING",
                f"Создаётся вся Launch Group аккаунта {run.account_name}",
                run=run,
                data={"campaigns": len(snapshot.get("campaigns") or [])},
            )
            db.commit()

            result = (
                adapter.deploy_plan(snapshot)
                if snapshot.get("campaigns")
                else _empty_result(plan.execution_mode, reused_resources, validate_only=False)
            )
            result = merge_domain_skips(result, domain_skipped, domain_report)
            _save_deployment_instances(db, plan, result)
            run.request_ids = _unique([*(run.request_ids or []), *result.request_ids])
            run.resource_names = _unique(
                [*(run.resource_names or []), *reused_resources, *result.resource_names]
            )
            if not result.ok:
                raise ScheduledExecutionError(
                    "DEPLOYMENT_FAILED",
                    "Создание Launch Group завершилось ошибкой",
                    result.errors,
                    result.request_ids,
                )
            _finish_success(db, schedule, run, plan, bundle, now)
            db.commit()
            return {
                "ok": True,
                "mode": plan.execution_mode,
                "run_id": run_id,
                "resources": run.resource_names,
                "request_ids": run.request_ids,
            }
        except ScheduledExecutionError as exc:
            return _finish_failure(db, schedule, run, plan, exc, now)
        except Exception as exc:
            wrapped = ScheduledExecutionError(
                exc.__class__.__name__,
                str(exc),
                [{"code": exc.__class__.__name__, "message": str(exc)}],
            )
            return _finish_failure(db, schedule, run, plan, wrapped, now)


class ScheduledExecutionError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        errors: list[dict] | None = None,
        request_ids: list[str] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.errors = errors or [{"code": code, "message": message}]
        self.request_ids = request_ids or []


def _account_snapshot(
    db,
    plan: DeploymentPlan,
    bundle: AccountTestBundle,
) -> tuple[dict, list[str]]:
    snapshot = deepcopy(plan.snapshot)
    campaigns = [
        item
        for item in snapshot.get("campaigns") or []
        if str(item.get("account_test_bundle_id")) == str(bundle.id)
    ]
    pending = []
    reused_resources: list[str] = []
    for campaign in campaigns:
        instance_id = campaign.get("campaign_instance_id")
        instance = db.get(CampaignInstance, UUID(str(instance_id))) if instance_id else None
        if not instance:
            raise ScheduledExecutionError(
                "SYSTEM_CONFIGURATION",
                f"Campaign Instance не найдена: {instance_id}",
            )
        if instance.resource_names and instance.status in {"PAUSED", "ENABLED"}:
            reused_resources.extend(instance.resource_names)
            continue
        pending.append(campaign)
    if not campaigns:
        raise ScheduledExecutionError(
            "SYSTEM_CONFIGURATION",
            "В Launch Group нет кампаний immutable plan",
        )
    snapshot["campaigns"] = pending
    snapshot["scheduled_account_run"] = {
        "account_test_bundle_id": str(bundle.id),
        "customer_id": bundle.customer_id,
    }
    return snapshot, _unique(reused_resources)


def _check_assets(db, snapshot: dict) -> None:
    selected_ids = {
        str(media_id)
        for campaign in snapshot.get("campaigns") or []
        for media_id in campaign.get("media_ids") or []
    }
    snapshot_media = {str(item.get("id")): item for item in snapshot.get("media") or []}
    errors = []
    for media_id in selected_ids:
        try:
            asset = db.get(MediaAsset, UUID(media_id))
        except ValueError:
            asset = None
        immutable = snapshot_media.get(media_id)
        if not asset or not immutable:
            errors.append({"code": "ASSET_MISSING", "message": f"Медиа {media_id} не найдено"})
        elif asset.status != "READY" or immutable.get("status") != "READY":
            errors.append(
                {
                    "code": "MEDIA_NOT_READY",
                    "message": f"Медиа {asset.name} не готово",
                }
            )
        elif asset.sha256 != immutable.get("sha256"):
            errors.append(
                {
                    "code": "ASSET_CHANGED",
                    "message": f"Медиа {asset.name} изменилось после фиксации плана",
                }
            )
    if errors:
        raise ScheduledExecutionError("MEDIA_NOT_READY", "Обязательные медиа не готовы", errors)


def _adapter_for_run(
    db,
    schedule: DeploymentSchedule,
    plan: DeploymentPlan,
    bundle: AccountTestBundle,
):
    if plan.execution_mode == "SIMULATION":
        return MockGoogleAdsAdapter(), []
    connection = db.get(GoogleConnection, schedule.connection_id)
    if not is_google_connection_active(connection):
        raise ScheduledExecutionError(
            "CONNECTION_UNAVAILABLE",
            "Активное подключение Google недоступно",
        )
    try:
        require_execution_mode_for_connection(connection, plan.execution_mode)
        adapter = build_google_ads_adapter(db, connection)
        _, _, request_ids = refresh_google_test_target(
            db,
            connection,
            adapter,
            bundle.customer_id,
            confirmed_at=plan.confirmed_at,
            require_confirmation=True,
        )
    except Exception as exc:
        raise ScheduledExecutionError(
            "MCC_ACCESS_CHECK_FAILED",
            f"Не удалось проверить доступ MCC: {exc}",
            [{"code": exc.__class__.__name__, "message": str(exc)}],
        ) from exc
    return adapter, request_ids


def _save_jit_validation(
    db,
    plan: DeploymentPlan,
    result: PlanExecutionResult,
) -> None:
    for row in (result.details or {}).get("instances") or []:
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
            "mode": result.mode,
            "jit": True,
            "errors": row.get("errors") or [],
            "warnings": row.get("warnings") or [],
            "request_ids": row.get("request_ids") or [],
            "google_contacted": bool((result.details or {}).get("google_contacted")),
        }
        instance.request_ids = _unique(
            [*(instance.request_ids or []), *(row.get("request_ids") or [])]
        )
        instance.status = "VALIDATED" if row.get("ok") else "VALIDATION_FAILED"


def _finish_success(
    db,
    schedule: DeploymentSchedule,
    run: ScheduledAccountRun,
    plan: DeploymentPlan,
    bundle: AccountTestBundle,
    now: datetime,
) -> None:
    run.status = ScheduleRunStatus.SUCCEEDED.value
    run.actual_completed_at = now
    run.next_retry_at = None
    run.structured_error = {}
    run.last_heartbeat_at = now
    schedule.consecutive_serious_errors = 0
    bundle.status = "READY"
    bundle.completed_at = now
    _event(
        db,
        schedule,
        "ACCOUNT_SUCCEEDED",
        f"Launch Group аккаунта {run.account_name} создана в PAUSED",
        run=run,
        data={
            "campaigns": run.campaigns_count,
            "request_ids": run.request_ids,
            "resource_names": run.resource_names,
        },
    )
    _advance_schedule_state(db, schedule, now)
    _update_tracking_state(db, schedule, now, plan=plan)


def _finish_failure(
    db,
    schedule: DeploymentSchedule,
    run: ScheduledAccountRun,
    plan: DeploymentPlan | None,
    exc: ScheduledExecutionError,
    now: datetime,
) -> dict:
    codes = sorted(normalize_error_codes([{"code": exc.code}, *exc.errors]))
    transient = is_transient_error(exc.errors)
    max_attempts = int((schedule.config or {}).get("retry_max_attempts") or 3)
    request_ids = _unique([*(run.request_ids or []), *exc.request_ids])
    run.request_ids = request_ids
    error = {
        "code": exc.code,
        "codes": codes,
        "message": exc.message,
        "errors": exc.errors,
        "request_ids": request_ids,
        "transient": transient,
        "attempt": run.attempts,
    }
    run.structured_error = error
    run.last_heartbeat_at = now
    if transient and run.attempts < max_attempts:
        delay = retry_delay_seconds(
            run.deployment_key,
            run.attempts,
            base_seconds=int((schedule.config or {}).get("retry_base_seconds") or 60),
        )
        run.status = ScheduleRunStatus.RETRY_WAIT.value
        run.next_retry_at = now + timedelta(seconds=delay)
        _event(
            db,
            schedule,
            "ACCOUNT_RETRY_WAIT",
            f"Временная ошибка у {run.account_name}; повтор через {delay} сек.",
            run=run,
            data=error,
            level="WARNING",
        )
    else:
        run.status = ScheduleRunStatus.FAILED.value
        run.actual_completed_at = now
        run.next_retry_at = None
        next_count, pause = circuit_breaker_decision(
            consecutive_serious_errors=schedule.consecutive_serious_errors,
            threshold=schedule.circuit_breaker_threshold,
            errors=[{"code": exc.code}, *exc.errors],
        )
        schedule.consecutive_serious_errors = next_count
        summary = dict(schedule.summary or {})
        code_counts = dict(summary.get("serious_error_codes") or {})
        for code in codes:
            code_counts[code] = int(code_counts.get(code) or 0) + 1
        summary["serious_error_codes"] = code_counts
        schedule.summary = summary
        if any(value >= schedule.circuit_breaker_threshold for value in code_counts.values()):
            pause = True
        _event(
            db,
            schedule,
            "ACCOUNT_FAILED",
            f"Аккаунт {run.account_name} завершился ошибкой: {exc.message}",
            run=run,
            data=error,
            level="ERROR",
        )
        if pause:
            remaining = int(
                db.scalar(
                    select(func.count(ScheduledAccountRun.id)).where(
                        ScheduledAccountRun.schedule_id == schedule.id,
                        ScheduledAccountRun.status.in_(
                            [
                                ScheduleRunStatus.WAITING.value,
                                ScheduleRunStatus.RETRY_WAIT.value,
                                ScheduleRunStatus.QUEUED.value,
                            ]
                        ),
                    )
                )
                or 0
            )
            schedule.status = ScheduleStatus.PAUSED.value
            schedule.paused_at = now
            schedule.pause_reason = (
                f"Сработала аварийная остановка после {next_count} серьёзных ошибок подряд"
            )
            schedule.recovery_required = False
            _event(
                db,
                schedule,
                "CIRCUIT_BREAKER_OPENED",
                schedule.pause_reason,
                run=run,
                data={
                    "codes": codes,
                    "request_ids": request_ids,
                    "remaining_accounts": remaining,
                },
                level="ERROR",
            )
        else:
            _advance_schedule_state(db, schedule, now)
    _update_tracking_state(db, schedule, now, plan=plan)
    db.commit()
    return {
        "ok": False,
        "run_id": str(run.id),
        "status": run.status,
        "error": error,
        "schedule_status": schedule.status,
        "next_retry_at": run.next_retry_at.isoformat() if run.next_retry_at else None,
    }


def _advance_schedule_state(db, schedule: DeploymentSchedule, now: datetime) -> list[UUID]:
    if schedule.status in {
        ScheduleStatus.PAUSED.value,
        ScheduleStatus.CANCELLED.value,
        ScheduleStatus.COMPLETED.value,
        ScheduleStatus.COMPLETED_WITH_ERRORS.value,
    }:
        return []
    waves = list(
        db.scalars(
            select(DeploymentWave)
            .where(DeploymentWave.schedule_id == schedule.id)
            .order_by(DeploymentWave.wave_number)
        ).all()
    )
    for index, wave in enumerate(waves):
        statuses = list(
            db.scalars(
                select(ScheduledAccountRun.status).where(
                    ScheduledAccountRun.schedule_id == schedule.id,
                    ScheduledAccountRun.wave_id == wave.id,
                )
            ).all()
        )
        if statuses and all(item in TERMINAL_RUN_STATUSES for item in statuses):
            if wave.observation_until and now < wave.observation_until and index < len(waves) - 1:
                wave.status = ScheduleWaveStatus.OBSERVATION.value
                schedule.status = ScheduleStatus.OBSERVATION.value
                return []
            wave.status = ScheduleWaveStatus.COMPLETED.value
            continue
        if wave.approval_required and not wave.approved_at:
            wave.status = ScheduleWaveStatus.WAITING_FOR_APPROVAL.value
            schedule.status = ScheduleStatus.WAITING_FOR_APPROVAL.value
            return []
        if schedule.status in {
            ScheduleStatus.OBSERVATION.value,
            ScheduleStatus.WAITING_FOR_APPROVAL.value,
        }:
            schedule.status = ScheduleStatus.RUNNING.value
        return [wave.id]

    if waves:
        failed = int(
            db.scalar(
                select(func.count(ScheduledAccountRun.id)).where(
                    ScheduledAccountRun.schedule_id == schedule.id,
                    ScheduledAccountRun.status == ScheduleRunStatus.FAILED.value,
                )
            )
            or 0
        )
        schedule.status = (
            ScheduleStatus.COMPLETED_WITH_ERRORS.value
            if failed
            else ScheduleStatus.COMPLETED.value
        )
        schedule.completed_at = now
        _event(
            db,
            schedule,
            "SCHEDULE_COMPLETED",
            "Расписание завершено" if not failed else f"Расписание завершено с ошибками: {failed}",
            data={"failed_accounts": failed},
            level="WARNING" if failed else "INFO",
        )
    return []


def _available_slots(db, schedule: DeploymentSchedule, now: datetime) -> int:
    active = int(
        db.scalar(
            select(func.count(ScheduledAccountRun.id)).where(
                ScheduledAccountRun.schedule_id == schedule.id,
                ScheduledAccountRun.status.in_(list(ACTIVE_RUN_STATUSES)),
            )
        )
        or 0
    )
    started_hour = int(
        db.scalar(
            select(func.count(ScheduledAccountRun.id)).where(
                ScheduledAccountRun.schedule_id == schedule.id,
                ScheduledAccountRun.actual_started_at > now - timedelta(hours=1),
            )
        )
        or 0
    )
    started_day = int(
        db.scalar(
            select(func.count(ScheduledAccountRun.id)).where(
                ScheduledAccountRun.schedule_id == schedule.id,
                ScheduledAccountRun.actual_started_at > now - timedelta(days=1),
            )
        )
        or 0
    )
    return max(
        0,
        min(
            schedule.max_parallel - active,
            schedule.max_accounts_per_hour - started_hour,
            schedule.max_accounts_per_day - started_day,
        ),
    )


def _due_count(
    db,
    schedule: DeploymentSchedule,
    wave_ids: list[UUID],
    now: datetime,
) -> int:
    if not wave_ids:
        return 0
    return int(
        db.scalar(
            select(func.count(ScheduledAccountRun.id)).where(
                ScheduledAccountRun.schedule_id == schedule.id,
                ScheduledAccountRun.wave_id.in_(wave_ids),
                or_(
                    (
                        (ScheduledAccountRun.status == ScheduleRunStatus.WAITING.value)
                        & (ScheduledAccountRun.scheduled_for <= now)
                    ),
                    (
                        (ScheduledAccountRun.status == ScheduleRunStatus.RETRY_WAIT.value)
                        & (ScheduledAccountRun.next_retry_at.is_not(None))
                        & (ScheduledAccountRun.next_retry_at <= now)
                    ),
                ),
            )
        )
        or 0
    )


def _recover_stale_runs(db, schedule: DeploymentSchedule, now: datetime) -> None:
    queued_before = now - timedelta(minutes=5)
    working_before = now - timedelta(hours=1)
    rows = list(
        db.scalars(
            select(ScheduledAccountRun).where(
                ScheduledAccountRun.schedule_id == schedule.id,
                ScheduledAccountRun.status.in_(list(ACTIVE_RUN_STATUSES)),
            )
        ).all()
    )
    for run in rows:
        heartbeat = run.last_heartbeat_at or run.updated_at
        if run.status == ScheduleRunStatus.QUEUED.value and heartbeat < queued_before:
            run.status = ScheduleRunStatus.WAITING.value
            run.scheduled_for = now
            _event(
                db,
                schedule,
                "STALE_QUEUE_RECOVERED",
                f"Зависшая очередь восстановлена: {run.account_name}",
                run=run,
                level="WARNING",
            )
        elif run.status in {
            ScheduleRunStatus.VALIDATING.value,
            ScheduleRunStatus.CREATING.value,
        } and heartbeat < working_before:
            run.status = ScheduleRunStatus.RETRY_WAIT.value
            run.next_retry_at = now
            _event(
                db,
                schedule,
                "STALE_WORKER_RECOVERED",
                f"Задание после остановки worker будет проверено повторно: {run.account_name}",
                run=run,
                level="WARNING",
            )


def _update_tracking_state(
    db,
    schedule: DeploymentSchedule,
    now: datetime,
    *,
    plan: DeploymentPlan | None = None,
) -> None:
    runs = list(
        db.scalars(
            select(ScheduledAccountRun).where(ScheduledAccountRun.schedule_id == schedule.id)
        ).all()
    )
    completed = sum(item.status in TERMINAL_RUN_STATUSES for item in runs)
    failed = sum(item.status == ScheduleRunStatus.FAILED.value for item in runs)
    resources = _unique([name for item in runs for name in item.resource_names or []])
    request_ids = _unique([request_id for item in runs for request_id in item.request_ids or []])
    job = db.get(Job, schedule.job_id) if schedule.job_id else None
    if job:
        job.progress_current = completed
        if schedule.status in {
            ScheduleStatus.COMPLETED.value,
            ScheduleStatus.COMPLETED_WITH_ERRORS.value,
            ScheduleStatus.CANCELLED.value,
        }:
            job.status = (
                JobStatus.SUCCEEDED.value
                if schedule.status == ScheduleStatus.COMPLETED.value
                else JobStatus.FAILED.value
            )
            job.error_message = (
                None if schedule.status == ScheduleStatus.COMPLETED.value else schedule.pause_reason
            )
        elif schedule.status == ScheduleStatus.PAUSED.value:
            job.status = JobStatus.RUNNING.value
        elif completed or any(item.status in ACTIVE_RUN_STATUSES for item in runs):
            job.status = JobStatus.RUNNING.value
    if not plan and schedule.deployment_plan_id:
        plan = db.get(DeploymentPlan, schedule.deployment_plan_id)
    if plan:
        plan.resource_names = resources
        plan.request_ids = request_ids
        plan.result = {
            "ok": schedule.status == ScheduleStatus.COMPLETED.value,
            "mode": plan.execution_mode,
            "schedule_id": str(schedule.id),
            "schedule_status": schedule.status,
            "accounts_completed": completed,
            "accounts_total": len(runs),
            "accounts_failed": failed,
            "campaign_status": "PAUSED",
            "request_ids": request_ids,
            "resource_names": resources,
        }
        upload = db.get(CampaignUpload, plan.upload_id)
        if schedule.status == ScheduleStatus.COMPLETED.value:
            plan.status = PlanStatus.SUCCEEDED.value
            plan.completed_at = now
            if upload:
                upload.status = UploadStatus.SUCCEEDED.value
                upload.last_error = None
            _update_batch_deployment_status(db, plan, succeeded=True)
        elif schedule.status == ScheduleStatus.COMPLETED_WITH_ERRORS.value:
            plan.status = PlanStatus.FAILED.value
            plan.completed_at = now
            if upload:
                upload.status = UploadStatus.FAILED.value
                upload.last_error = f"Расписание завершено с ошибками: {failed}"
            _update_batch_deployment_status(db, plan, succeeded=False)
        elif schedule.status == ScheduleStatus.CANCELLED.value:
            plan.status = PlanStatus.FAILED.value
            plan.completed_at = now
            if upload:
                upload.status = UploadStatus.FAILED.value
                upload.last_error = "Будущие запуски отменены"
        elif schedule.status in {
            ScheduleStatus.RUNNING.value,
            ScheduleStatus.OBSERVATION.value,
            ScheduleStatus.WAITING_FOR_APPROVAL.value,
            ScheduleStatus.PAUSED.value,
        }:
            plan.status = PlanStatus.RUNNING.value
            if upload:
                upload.status = UploadStatus.RUNNING.value


def _mark_tracking_running(
    db,
    schedule: DeploymentSchedule,
    plan: DeploymentPlan | None,
) -> None:
    if plan:
        plan.status = PlanStatus.RUNNING.value
        upload = db.get(CampaignUpload, plan.upload_id)
        if upload:
            upload.status = UploadStatus.RUNNING.value
    if schedule.job_id:
        job = db.get(Job, schedule.job_id)
        if job:
            job.status = JobStatus.RUNNING.value
            db.add(
                JobEvent(
                    job_id=job.id,
                    level="INFO",
                    message="Начата обработка дочернего аккаунта",
                    data={"schedule_id": str(schedule.id)},
                )
            )


def _return_failed_enqueue(run_id: str, message: str, now: datetime) -> None:
    with SessionLocal() as db:
        run = db.get(ScheduledAccountRun, UUID(run_id))
        if not run or run.status != ScheduleRunStatus.QUEUED.value:
            return
        schedule = db.get(DeploymentSchedule, run.schedule_id)
        run.status = ScheduleRunStatus.WAITING.value
        run.scheduled_for = now
        run.last_heartbeat_at = now
        if schedule:
            _event(
                db,
                schedule,
                "BROKER_ENQUEUE_FAILED",
                f"Не удалось передать {run.account_name} worker: {message}",
                run=run,
                level="WARNING",
            )
        db.commit()


def _empty_result(
    mode: str,
    resources: list[str] | None = None,
    *,
    validate_only: bool,
) -> PlanExecutionResult:
    return PlanExecutionResult(
        ok=True,
        mode=mode,
        errors=[],
        warnings=[{"code": "IDEMPOTENT_REUSE", "message": "Ресурсы уже созданы"}],
        request_ids=[],
        resource_names=resources or [],
        details={
            "validate_only": validate_only,
            "google_contacted": False,
            "campaign_status": "PAUSED",
            "instances": [],
        },
    )


def _event(
    db,
    schedule: DeploymentSchedule,
    event_type: str,
    message: str,
    *,
    run: ScheduledAccountRun | None = None,
    data: dict | None = None,
    level: str = "INFO",
) -> None:
    db.add(
        ScheduleEvent(
            schedule_id=schedule.id,
            wave_id=run.wave_id if run else None,
            account_run_id=run.id if run else None,
            event_type=event_type,
            level=level,
            message=message,
            data=data or {},
        )
    )


def _managed_now(value: str | None) -> datetime:
    if not value:
        return utcnow()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("managed clock must include a time zone")
    return parsed.astimezone(UTC)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if item))


def _digits(value: object) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())
