from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decrypt_json, utcnow
from app.db.models import (
    AccountTestBundle,
    AuditLog,
    CampaignInstance,
    CampaignStatusAction,
    CampaignUpload,
    CustomerAccount,
    DeploymentPlan,
    FinanceProfile,
    FinanceSnapshot,
    GoogleConnection,
    GoogleCredential,
    Job,
    JobEvent,
    JobStatus,
    LaunchBatch,
    MediaAsset,
    MediaStatus,
    MetricSnapshot,
    ModerationRecord,
    Notification,
    PerformanceSnapshot,
    PlanStatus,
    UploadStatus,
)
from app.domain_validation.persistence import validate_snapshot, validate_upload
from app.domain_validation.service import (
    blocked_execution_result,
    filter_blocked_campaigns,
    merge_domain_skips,
)
from app.google_ads.execution_guard import (
    refresh_google_test_snapshot_targets,
    refresh_google_test_target,
)
from app.google_ads.interface import PlanExecutionResult
from app.google_ads.mock_adapter import MockGoogleAdsAdapter
from app.google_ads.safety import require_execution_mode_for_connection
from app.google_ads.service import build_google_ads_adapter, is_google_connection_active
from app.integrations.brocard import BrocardClient
from app.jobs.celery_app import celery_app


@celery_app.task(name="app.jobs.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="app.jobs.validate_upload_domains")
def validate_upload_domains(
    upload_id: str,
    job_id: str | None = None,
    force: bool = False,
) -> dict:
    with SessionLocal() as db:
        try:
            upload = db.get(CampaignUpload, UUID(upload_id))
        except ValueError:
            upload = None
        job = None
        if job_id:
            try:
                job = db.get(Job, UUID(job_id))
            except ValueError:
                job = None
        if not upload:
            if job:
                job.status = JobStatus.FAILED.value
                job.error_message = "Загрузка не найдена"
                db.add(
                    JobEvent(
                        job_id=job.id,
                        level="ERROR",
                        message="Проверка доменов не выполнена: загрузка не найдена",
                        data={"code": "UPLOAD_NOT_FOUND"},
                    )
                )
                db.commit()
            return {"ok": False, "code": "UPLOAD_NOT_FOUND"}
        if job and job.status == JobStatus.SUCCEEDED.value:
            summary = (upload.draft or {}).get("domain_validation", {}).get(
                "summary", {}
            )
            return {"ok": True, "reused": True, "summary": summary}
        if job:
            job.status = JobStatus.RUNNING.value
            job.progress_current = 0
            job.progress_total = 1
            db.add(
                JobEvent(
                    job_id=job.id,
                    level="INFO",
                    message="Проверка доменов начата",
                    data={"upload_id": upload_id, "force": force},
                )
            )
            db.commit()
        try:
            report = validate_upload(db, upload, force=force)
            if job:
                job.status = JobStatus.SUCCEEDED.value
                job.progress_current = 1
                job.error_message = None
                db.add(
                    JobEvent(
                        job_id=job.id,
                        level="INFO",
                        message="Проверка доменов завершена",
                        data={"summary": report["summary"]},
                    )
                )
            db.commit()
            return {"ok": True, "summary": report["summary"]}
        except Exception as exc:
            db.rollback()
            if job:
                job = db.get(Job, job.id)
                if job:
                    job.status = JobStatus.FAILED.value
                    job.error_message = "Проверка доменов временно недоступна"
                    db.add(
                        JobEvent(
                            job_id=job.id,
                            level="ERROR",
                            message="Проверка доменов завершилась ошибкой",
                            data={"code": exc.__class__.__name__},
                        )
                    )
                    db.commit()
            return {"ok": False, "code": exc.__class__.__name__}


@celery_app.task(name="app.jobs.deploy_plan")
def deploy_plan(plan_id: str, job_id: str) -> dict:
    with SessionLocal() as db:
        plan = db.get(DeploymentPlan, UUID(plan_id))
        job = db.get(Job, UUID(job_id))
        if not plan or not job:
            return {"ok": False, "error": "plan or job not found"}
        if plan.status == PlanStatus.SUCCEEDED.value and job.status == JobStatus.SUCCEEDED.value:
            return {"ok": True, "reused": True}
        plan.status = PlanStatus.RUNNING.value
        job.status = JobStatus.RUNNING.value
        upload = db.get(CampaignUpload, plan.upload_id)
        if upload:
            upload.status = UploadStatus.RUNNING.value
        db.add(JobEvent(job_id=job.id, level="INFO", message="Создание кампаний начато", data={}))
        db.commit()

        try:
            snapshot, reused_resources = _pending_deployment_snapshot(db, plan, job)
            domain_report = validate_snapshot(
                snapshot,
                cached_report=plan.snapshot.get("domain_validation") or {},
                force=plan.execution_mode == "GOOGLE_TEST",
            )
            snapshot, domain_skipped = filter_blocked_campaigns(snapshot, domain_report)
            if not snapshot.get("campaigns"):
                if domain_skipped:
                    result = blocked_execution_result(plan.execution_mode, domain_skipped, domain_report)
                else:
                    result = PlanExecutionResult(
                        ok=True,
                        mode=plan.execution_mode,
                        errors=[],
                        warnings=[{"code": "IDEMPOTENT_REUSE", "message": "Все Campaign Instance уже созданы"}],
                        request_ids=[],
                        resource_names=reused_resources,
                        details={
                            "validate_only": False,
                            "google_contacted": False,
                            "campaign_status": "PAUSED",
                            "instances": [],
                        },
                    )
            if plan.execution_mode == "SIMULATION":
                if snapshot.get("campaigns"):
                    result = MockGoogleAdsAdapter().deploy_plan(snapshot)
            elif snapshot.get("campaigns"):
                connection = db.get(GoogleConnection, plan.connection_id) if plan.connection_id else None
                if not is_google_connection_active(connection):
                    raise ValueError("Активное подключение Google недоступно")
                require_execution_mode_for_connection(connection, plan.execution_mode)
                adapter = build_google_ads_adapter(db, connection)
                guard_request_ids = refresh_google_test_snapshot_targets(
                    db,
                    connection,
                    adapter,
                    snapshot,
                    confirmed_at=plan.confirmed_at,
                    require_confirmation=True,
                )
                result = adapter.deploy_plan(snapshot)
                result.request_ids = list(
                    dict.fromkeys([*guard_request_ids, *result.request_ids])
                )
            if snapshot.get("campaigns"):
                result = merge_domain_skips(result, domain_skipped, domain_report)
        except Exception as exc:
            _fail_job(db, job, str(exc), "deployment_plan", plan_id)
            plan.status = PlanStatus.FAILED.value
            plan.result = {"ok": False, "errors": [{"code": exc.__class__.__name__, "message": str(exc)}]}
            if upload:
                upload.status = UploadStatus.FAILED.value
                upload.last_error = str(exc)
            db.commit()
            return {"ok": False, "error": str(exc)}

        plan.result = result.__dict__
        plan.request_ids = result.request_ids
        plan.resource_names = list(dict.fromkeys([*(plan.resource_names or []), *result.resource_names]))
        plan.completed_at = utcnow()
        _save_deployment_instances(db, plan, result)
        if result.ok:
            plan.status = PlanStatus.SUCCEEDED.value
            job.status = JobStatus.SUCCEEDED.value
            job.progress_current = job.progress_total
            if upload:
                upload.status = UploadStatus.SUCCEEDED.value
                upload.last_error = None
            _update_batch_deployment_status(db, plan, succeeded=True)
            db.add(
                JobEvent(
                    job_id=job.id,
                    level="INFO",
                    message="План выполнен",
                    data={"mode": result.mode, "resources": result.resource_names},
                )
            )
        else:
            plan.status = PlanStatus.FAILED.value
            job.status = JobStatus.FAILED.value
            job.error_message = "; ".join(item.get("message", "Ошибка Google Ads") for item in result.errors)
            if upload:
                upload.status = UploadStatus.FAILED.value
                upload.last_error = job.error_message
            _update_batch_deployment_status(db, plan, succeeded=False)
            _add_failure_alert(db, job, "Создание кампаний не выполнено", job.error_message)
        db.add(
            AuditLog(
                created_at=utcnow(),
                actor_user_id=job.created_by_id,
                action="plan.deploy.complete",
                entity_type="deployment_plan",
                entity_id=plan_id,
                summary={"ok": result.ok, "mode": result.mode, "request_ids": result.request_ids},
            )
        )
        db.commit()
        return {"ok": result.ok, "mode": result.mode, "resources": result.resource_names}


def _pending_deployment_snapshot(
    db,
    plan: DeploymentPlan,
    job: Job,
) -> tuple[dict, list[str]]:
    snapshot = deepcopy(plan.snapshot)
    selected_ids = {str(item) for item in (job.payload or {}).get("campaign_instance_ids") or []}
    pending: list[dict] = []
    reused_resources: list[str] = []
    reused_instances = 0
    for campaign in snapshot.get("campaigns") or []:
        instance_id = campaign.get("campaign_instance_id")
        if selected_ids and str(instance_id) not in selected_ids:
            continue
        instance = None
        if instance_id:
            try:
                instance = db.get(CampaignInstance, UUID(str(instance_id)))
            except ValueError:
                instance = None
        if instance and instance.resource_names and instance.status in {"PAUSED", "ENABLED"}:
            reused_resources.extend(instance.resource_names)
            reused_instances += 1
            continue
        if instance:
            instance.status = "DEPLOYING"
            instance.error_message = None
        pending.append(campaign)
    snapshot["campaigns"] = pending
    job.progress_total = len(pending) + reused_instances
    db.commit()
    return snapshot, reused_resources


def _save_deployment_instances(db, plan: DeploymentPlan, result: PlanExecutionResult) -> None:
    now = utcnow()
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
        instance.request_ids = list(dict.fromkeys([*(instance.request_ids or []), *(row.get("request_ids") or [])]))
        if row.get("ok"):
            instance.status = "PAUSED"
            instance.resource_names = list(
                dict.fromkeys([*(instance.resource_names or []), *(row.get("resource_names") or [])])
            )
            instance.error_message = None
            if result.mode == "SIMULATION" and not instance.metrics:
                instance.metrics = _simulation_metrics(instance.campaign_sequence)
                instance.last_synced_at = now
                db.add(
                    PerformanceSnapshot(
                        campaign_instance_id=instance.id,
                        period_start=now,
                        period_end=now,
                        account_time_zone=_bundle_time_zone(db, instance.account_test_bundle_id),
                        impressions=instance.metrics["impressions"],
                        clicks=instance.metrics["clicks"],
                        cost_micros=instance.metrics["cost_micros"],
                        conversions=instance.metrics["conversions"],
                        conversion_value=instance.metrics["conversion_value"],
                        metrics={"source": "SIMULATION", "google_contacted": False},
                    )
                )
        else:
            instance.status = "DOMAIN_BLOCKED" if row.get("skipped") else "DEPLOYMENT_FAILED"
            instance.error_message = "; ".join(
                str(item.get("code") or item.get("message") or "GOOGLE_ADS_ERROR")
                for item in row.get("errors") or []
            )


def _simulation_metrics(sequence: int) -> dict:
    presets = {
        1: {"impressions": 1200, "clicks": 36, "cost_micros": 150_000_000, "conversions": 0.0},
        2: {"impressions": 2400, "clicks": 72, "cost_micros": 216_000_000, "conversions": 3.0},
        3: {"impressions": 3100, "clicks": 124, "cost_micros": 180_000_000, "conversions": 10.0},
    }
    base = presets.get(sequence) or {
        "impressions": 900 + sequence * 140,
        "clicks": 20 + sequence * 5,
        "cost_micros": (90 + sequence * 12) * 1_000_000,
        "conversions": float(max(0, sequence - 1)),
    }
    return {**base, "conversion_value": float(base["conversions"] * 32), "source": "SIMULATION"}


def _bundle_time_zone(db, bundle_id: UUID) -> str:
    bundle = db.get(AccountTestBundle, bundle_id)
    return bundle.time_zone if bundle else "UTC"


def _update_batch_deployment_status(db, plan: DeploymentPlan, succeeded: bool) -> None:
    if not plan.launch_batch_id:
        return
    batch = db.get(LaunchBatch, plan.launch_batch_id)
    instances = list(
        db.scalars(
            select(CampaignInstance).where(
                CampaignInstance.launch_batch_id == plan.launch_batch_id,
                CampaignInstance.included.is_(True),
            )
        ).all()
    )
    for bundle in db.scalars(
        select(AccountTestBundle).where(AccountTestBundle.launch_batch_id == plan.launch_batch_id)
    ).all():
        bundle_instances = [item for item in instances if item.account_test_bundle_id == bundle.id]
        if bundle_instances and all(item.status in {"PAUSED", "ENABLED"} for item in bundle_instances):
            bundle.status = "READY"
        elif any(item.status in {"DEPLOYMENT_FAILED", "DOMAIN_BLOCKED"} for item in bundle_instances):
            bundle.status = "PARTIAL_FAILURE"
    if batch:
        if instances and all(item.status in {"PAUSED", "ENABLED"} for item in instances):
            batch.status = "CREATED_PAUSED"
        elif any(item.status in {"PAUSED", "ENABLED"} for item in instances):
            batch.status = "PARTIAL_FAILURE"
        else:
            batch.status = "FAILED" if not succeeded else "CREATED_PAUSED"


@celery_app.task(name="app.jobs.apply_campaign_status_action")
def apply_campaign_status_action(action_id: str, job_id: str) -> dict:
    with SessionLocal() as db:
        action = db.get(CampaignStatusAction, UUID(action_id))
        job = db.get(Job, UUID(job_id))
        if not action or not job:
            return {"ok": False, "error": "status action or job not found"}
        if action.status == "SUCCEEDED" and job.status == JobStatus.SUCCEEDED.value:
            return {"ok": True, "reused": True}
        bundle = db.get(AccountTestBundle, action.account_test_bundle_id)
        batch = db.get(LaunchBatch, bundle.launch_batch_id) if bundle else None
        selected_ids = {UUID(str(item)) for item in action.selected_instance_ids}
        instances = list(
            db.scalars(
                select(CampaignInstance).where(
                    CampaignInstance.account_test_bundle_id == action.account_test_bundle_id,
                    CampaignInstance.id.in_(selected_ids),
                )
            ).all()
        )
        action.status = "RUNNING"
        job.status = JobStatus.RUNNING.value
        db.commit()
        try:
            adapter = _status_adapter(db, batch, action.execution_mode)
            if action.execution_mode == "GOOGLE_TEST":
                connection = db.get(GoogleConnection, batch.connection_id)
                _, _, guard_request_ids = refresh_google_test_target(
                    db,
                    connection,
                    adapter,
                    bundle.customer_id,
                    confirmed_at=action.created_at,
                    require_confirmation=True,
                )
                validation = adapter.validate_campaign_status(
                    bundle.customer_id,
                    _campaign_refs(instances),
                    "ENABLED" if action.requested_status == "ENABLED" else "PAUSED",
                )
                if not validation.ok:
                    raise RuntimeError(
                        "; ".join(
                            item.get("message", "validate_only failed")
                            for item in validation.errors
                        )
                    )
            else:
                guard_request_ids = []
                validation = None
            google_status = "ENABLED" if action.requested_status == "ENABLED" else "PAUSED"
            results = [adapter.change_campaign_status(bundle.customer_id, _campaign_refs(instances), google_status)]
        except Exception as exc:
            action.status = "FAILED"
            action.error_message = str(exc)
            action.completed_at = utcnow()
            _fail_job(db, job, str(exc), "campaign_status_action", action_id)
            db.commit()
            return {"ok": False, "error": str(exc)}

        errors = [item for result in results for item in result.errors]
        action.request_ids = list(
            dict.fromkeys(
                [
                    *guard_request_ids,
                    *(
                        validation.request_ids
                        if validation is not None
                        else []
                    ),
                    *(
                        item
                        for result in results
                        for item in result.request_ids
                    ),
                ]
            )
        )
        action.resource_names = list(dict.fromkeys(item for result in results for item in result.resource_names))
        action.completed_at = utcnow()
        if errors:
            action.status = "FAILED"
            action.error_message = "; ".join(item.get("message", "Ошибка Google Ads") for item in errors)
            _fail_job(db, job, action.error_message, "campaign_status_action", action_id)
        else:
            _apply_local_status(action, bundle, instances)
            action.status = "SUCCEEDED"
            action.error_message = None
            job.status = JobStatus.SUCCEEDED.value
            job.progress_current = job.progress_total
            db.add(
                JobEvent(
                    job_id=job.id,
                    level="INFO",
                    message="Статусы кампаний обновлены",
                    data={"mode": action.execution_mode, "action": action.action},
                )
            )
        db.add(
            AuditLog(
                created_at=utcnow(),
                actor_user_id=action.requested_by_id,
                action="campaign.status.complete",
                entity_type="campaign_status_action",
                entity_id=action_id,
                summary={
                    "ok": not errors,
                    "mode": action.execution_mode,
                    "request_ids": action.request_ids,
                    "selected_instance_ids": action.selected_instance_ids,
                },
            )
        )
        db.commit()
        return {"ok": not errors, "mode": action.execution_mode, "request_ids": action.request_ids}


@celery_app.task(name="app.jobs.sync_launch_group_metrics")
def sync_launch_group_metrics(bundle_id: str, job_id: str) -> dict:
    with SessionLocal() as db:
        bundle = db.get(AccountTestBundle, UUID(bundle_id))
        job = db.get(Job, UUID(job_id))
        if not bundle or not job:
            return {"ok": False, "error": "bundle or job not found"}
        batch = db.get(LaunchBatch, bundle.launch_batch_id)
        instances = list(
            db.scalars(
                select(CampaignInstance).where(CampaignInstance.account_test_bundle_id == bundle.id)
            ).all()
        )
        refs = {name: item for item in instances for name in _campaign_resource_names(item)}
        if not refs:
            _fail_job(db, job, "В группе запуска ещё нет созданных кампаний", "account_test_bundle", bundle_id)
            db.commit()
            return {"ok": False, "error": job.error_message}
        job.status = JobStatus.RUNNING.value
        db.commit()
        try:
            adapter = _status_adapter(db, batch, batch.execution_mode if batch else "SIMULATION")
            rows = adapter.fetch_campaign_performance(bundle.customer_id, list(refs))
        except Exception as exc:
            _fail_job(db, job, str(exc), "account_test_bundle", bundle_id)
            db.commit()
            return {"ok": False, "error": str(exc)}
        now = utcnow()
        for row in rows:
            instance = refs.get(row["resource_name"])
            if not instance:
                continue
            metrics = {**row["metrics"], "source": batch.execution_mode if batch else "SIMULATION"}
            instance.metrics = metrics
            instance.last_synced_at = now
            if row.get("status") in {"ENABLED", "PAUSED"}:
                instance.status = row["status"]
            db.add(
                PerformanceSnapshot(
                    campaign_instance_id=instance.id,
                    period_start=now,
                    period_end=now,
                    account_time_zone=bundle.time_zone,
                    impressions=int(metrics.get("impressions") or 0),
                    clicks=int(metrics.get("clicks") or 0),
                    cost_micros=int(metrics.get("cost_micros") or 0),
                    conversions=float(metrics.get("conversions") or 0),
                    conversion_value=float(metrics.get("conversion_value") or 0),
                    metrics={"source": metrics["source"]},
                )
            )
        job.status = JobStatus.SUCCEEDED.value
        job.progress_current = len(rows)
        db.add(
            JobEvent(
                job_id=job.id,
                level="INFO",
                message=f"Метрики группы запуска обновлены: {len(rows)}",
                data={"mode": batch.execution_mode if batch else "SIMULATION"},
            )
        )
        db.add(
            AuditLog(
                created_at=now,
                actor_user_id=job.created_by_id,
                action="launch_group.metrics.complete",
                entity_type="account_test_bundle",
                entity_id=bundle_id,
                summary={"rows": len(rows), "mode": batch.execution_mode if batch else "SIMULATION"},
            )
        )
        db.commit()
        return {"ok": True, "rows": len(rows)}


def _status_adapter(db, batch: LaunchBatch | None, execution_mode: str):
    if execution_mode == "SIMULATION":
        return MockGoogleAdsAdapter()
    connection = db.get(GoogleConnection, batch.connection_id) if batch and batch.connection_id else None
    if not is_google_connection_active(connection):
        raise ValueError("Активное подключение Google недоступно")
    return build_google_ads_adapter(db, connection)


def _campaign_refs(instances: list[CampaignInstance]) -> list[dict]:
    result = []
    for item in instances:
        resource_names = _campaign_resource_names(item)
        if not resource_names:
            raise ValueError(f"У Campaign Instance {item.campaign_name} нет campaign resource name")
        result.append({"campaign_instance_id": str(item.id), "resource_name": resource_names[0]})
    return result


def _campaign_resource_names(instance: CampaignInstance) -> list[str]:
    return [str(item) for item in instance.resource_names or [] if "/campaigns/" in str(item)]


def _apply_local_status(
    action: CampaignStatusAction,
    bundle: AccountTestBundle,
    instances: list[CampaignInstance],
) -> None:
    now = utcnow()
    if action.requested_status == "ENABLED":
        for item in instances:
            item.status = "ENABLED"
            item.enabled_at = item.enabled_at or now
        bundle.status = "ACTIVE"
    else:
        for item in instances:
            item.status = "PAUSED"
        bundle.status = "PAUSED"


@celery_app.task(name="app.jobs.upload_youtube_video")
def upload_youtube_video(job_id: str) -> dict:
    with SessionLocal() as db:
        job = db.get(Job, UUID(job_id))
        if not job:
            return {"ok": False, "error": "job not found"}
        asset = db.get(MediaAsset, UUID(job.payload["media_id"]))
        if not asset or not asset.storage_key:
            _fail_job(db, job, "Исходное видео не найдено", "media_asset", job.payload.get("media_id"))
            db.commit()
            return {"ok": False, "error": job.error_message}
        job.status = JobStatus.RUNNING.value
        asset.status = MediaStatus.UPLOADING.value
        db.commit()
        try:
            if job.payload["execution_mode"] == "SIMULATION":
                adapter = MockGoogleAdsAdapter()
            else:
                connection = db.get(GoogleConnection, job.connection_id) if job.connection_id else None
                if not is_google_connection_active(connection):
                    raise ValueError("Активное подключение Google недоступно")
                adapter = build_google_ads_adapter(db, connection)
                confirmed_at = datetime.fromisoformat(job.payload["confirmed_at"])
                refresh_google_test_target(
                    db,
                    connection,
                    adapter,
                    job.payload["customer_id"],
                    confirmed_at=confirmed_at,
                    require_confirmation=True,
                )
            result = adapter.start_youtube_video_upload(
                job.payload["customer_id"],
                str(settings.storage_root / asset.storage_key),
                job.payload["title"],
                job.payload.get("description", ""),
            )
        except Exception as exc:
            _fail_job(db, job, str(exc), "media_asset", str(asset.id))
            asset.status = MediaStatus.FAILED.value
            asset.validation = {**asset.validation, "upload_error": str(exc)}
            db.commit()
            return {"ok": False, "error": str(exc)}

        asset.youtube_upload_resource = result.resource_name
        asset.youtube_video_id = result.video_id
        asset.details = {**asset.details, "youtube_state": result.state, "youtube_message": result.message}
        job.progress_current = 1
        if result.state == "PROCESSED" and result.video_id:
            asset.status = MediaStatus.READY.value
            job.status = JobStatus.SUCCEEDED.value
            job.progress_current = 2
            db.commit()
            return {"ok": True, "video_id": result.video_id, "state": result.state}
        asset.status = MediaStatus.PROCESSING.value
        db.commit()
        poll_youtube_video.apply_async(args=[job_id], countdown=15)
        return {"ok": True, "state": result.state, "polling": True}


@celery_app.task(bind=True, name="app.jobs.poll_youtube_video", max_retries=60)
def poll_youtube_video(self, job_id: str) -> dict:
    should_retry = False
    with SessionLocal() as db:
        job = db.get(Job, UUID(job_id))
        if not job:
            return {"ok": False, "error": "job not found"}
        asset = db.get(MediaAsset, UUID(job.payload["media_id"]))
        if not asset or not asset.youtube_upload_resource:
            _fail_job(db, job, "Ресурс YouTube upload отсутствует", "media_asset", job.payload.get("media_id"))
            db.commit()
            return {"ok": False, "error": job.error_message}
        try:
            if job.payload["execution_mode"] == "SIMULATION":
                adapter = MockGoogleAdsAdapter()
            else:
                connection = db.get(GoogleConnection, job.connection_id) if job.connection_id else None
                if not connection:
                    raise ValueError("Подключение Google не найдено")
                adapter = build_google_ads_adapter(db, connection)
            result = adapter.get_youtube_video_upload(job.payload["customer_id"], asset.youtube_upload_resource)
        except Exception as exc:
            if self.request.retries < self.max_retries:
                should_retry = True
                result = None
            else:
                _fail_job(db, job, str(exc), "media_asset", str(asset.id))
                asset.status = MediaStatus.FAILED.value
                db.commit()
                return {"ok": False, "error": str(exc)}

        if result:
            asset.details = {**asset.details, "youtube_state": result.state, "youtube_message": result.message}
            if result.state == "PROCESSED" and result.video_id:
                asset.youtube_video_id = result.video_id
                asset.status = MediaStatus.READY.value
                job.status = JobStatus.SUCCEEDED.value
                job.progress_current = 2
                db.commit()
                return {"ok": True, "state": result.state, "video_id": result.video_id}
            if result.state in {"FAILED", "REJECTED", "UNAVAILABLE"}:
                message = f"YouTube upload завершён со статусом {result.state}"
                _fail_job(db, job, message, "media_asset", str(asset.id))
                asset.status = MediaStatus.FAILED.value
                db.commit()
                return {"ok": False, "state": result.state}
            should_retry = True
            db.commit()
    if should_retry:
        raise self.retry(countdown=30)
    return {"ok": False}


@celery_app.task(name="app.jobs.sync_google_data")
def sync_google_data(job_id: str, kind: str) -> dict:
    with SessionLocal() as db:
        job = db.get(Job, UUID(job_id))
        if not job:
            return {"ok": False, "error": "job not found"}
        connection = db.get(GoogleConnection, job.connection_id) if job.connection_id else None
        if not connection:
            _fail_job(db, job, "Подключение Google не найдено", "job", job_id)
            db.commit()
            return {"ok": False, "error": job.error_message}
        accounts = db.scalars(
            select(CustomerAccount).where(
                CustomerAccount.connection_id == connection.id,
                CustomerAccount.can_manage_clients.is_(False),
                CustomerAccount.is_hidden.is_(False),
            )
        ).all()
        customer_ids = [item.customer_id for item in accounts]
        if not customer_ids:
            _fail_job(db, job, "Сначала синхронизируйте клиентские аккаунты MCC", "job", job_id)
            db.commit()
            return {"ok": False, "error": job.error_message}
        job.status = JobStatus.RUNNING.value
        db.commit()
        try:
            adapter = build_google_ads_adapter(db, connection)
            rows = (
                adapter.fetch_moderation(customer_ids)
                if kind == "moderation"
                else adapter.fetch_statistics(customer_ids)
            )
            if kind == "moderation":
                for row in rows:
                    item = db.scalar(
                        select(ModerationRecord).where(
                            ModerationRecord.customer_id == row["customer_id"],
                            ModerationRecord.resource_name == row["resource_name"],
                        )
                    )
                    if not item:
                        item = ModerationRecord(
                            connection_id=connection.id,
                            customer_id=row["customer_id"],
                            resource_name=row["resource_name"],
                        )
                        db.add(item)
                    item.approval_status = row["approval_status"]
                    item.policy_topics = row["policy_topics"]
                    item.checked_at = utcnow()
            else:
                for row in rows:
                    item = db.scalar(
                        select(MetricSnapshot).where(
                            MetricSnapshot.connection_id == connection.id,
                            MetricSnapshot.customer_id == row["customer_id"],
                            MetricSnapshot.snapshot_date == row["snapshot_date"],
                        )
                    )
                    if not item:
                        item = MetricSnapshot(
                            connection_id=connection.id,
                            customer_id=row["customer_id"],
                            snapshot_date=row["snapshot_date"],
                        )
                        db.add(item)
                    item.metrics = row["metrics"]
        except Exception as exc:
            _fail_job(db, job, str(exc), "job", job_id)
            db.commit()
            return {"ok": False, "error": str(exc)}
        job.status = JobStatus.SUCCEEDED.value
        job.progress_current = 1
        db.add(JobEvent(job_id=job.id, level="INFO", message=f"Синхронизировано записей: {len(rows)}", data={}))
        db.commit()
        return {"ok": True, "rows": len(rows)}


@celery_app.task(name="app.jobs.sync_finance")
def sync_finance(job_id: str) -> dict:
    with SessionLocal() as db:
        job = db.get(Job, UUID(job_id))
        if not job:
            return {"ok": False, "error": "job not found"}
        profile_id = UUID(job.payload["profile_id"])
        profile = db.get(FinanceProfile, profile_id)
        credential = db.get(GoogleCredential, profile.credential_id) if profile and profile.credential_id else None
        if not profile or not credential:
            _fail_job(db, job, "Профиль Brocard или токен не найден", "finance_profile", str(profile_id))
            db.commit()
            return {"ok": False, "error": job.error_message}

        job.status = JobStatus.RUNNING.value
        profile.status = "SYNCING"
        db.commit()
        try:
            token = decrypt_json(credential.encrypted_payload)["api_token"]
            with BrocardClient(profile.details["api_base_url"], token) as client:
                result = client.fetch_snapshot()
        except Exception as exc:
            message = str(exc)
            profile.status = "ERROR"
            profile.details = {**profile.details, "last_error": message, "last_sync_at": utcnow().isoformat()}
            _fail_job(db, job, message, "finance_profile", str(profile.id))
            db.commit()
            return {"ok": False, "error": message}

        db.add(
            FinanceSnapshot(
                profile_id=profile.id,
                balance=result.balance,
                currency=result.currency,
                cards_total=result.cards_total,
                cards_active=result.cards_active,
                provider_payload=result.provider_payload,
            )
        )
        profile.status = "CONNECTED"
        profile.details = {
            **profile.details,
            "last_error": None,
            "last_sync_at": utcnow().isoformat(),
            "request_ids": result.provider_payload["request_ids"],
        }
        job.status = JobStatus.SUCCEEDED.value
        job.progress_current = 1
        db.add(
            JobEvent(
                job_id=job.id,
                level="INFO",
                message="Данные Brocard синхронизированы",
                data={"cards_total": result.cards_total, "request_ids": result.provider_payload["request_ids"]},
            )
        )
        db.add(
            AuditLog(
                created_at=utcnow(),
                actor_user_id=job.created_by_id,
                action="finance.sync.complete",
                entity_type="finance_profile",
                entity_id=str(profile.id),
                summary={"balance": result.balance, "currency": result.currency, "cards_total": result.cards_total},
            )
        )
        db.commit()
        return {"ok": True, "cards_total": result.cards_total, "balance": result.balance}


def _fail_job(db, job: Job, message: str, entity_type: str, entity_id: str | None) -> None:
    job.status = JobStatus.FAILED.value
    job.error_message = message
    db.add(JobEvent(job_id=job.id, level="ERROR", message=message, data={}))
    _add_failure_alert(db, job, "Фоновое задание завершилось ошибкой", message, entity_type, entity_id)


def _add_failure_alert(
    db,
    job: Job,
    title: str,
    message: str,
    entity_type: str = "job",
    entity_id: str | None = None,
) -> None:
    db.add(
        Notification(
            user_id=job.created_by_id,
            severity="ERROR",
            title=title,
            message=message[:4000],
            entity_type=entity_type,
            entity_id=entity_id or str(job.id),
        )
    )
