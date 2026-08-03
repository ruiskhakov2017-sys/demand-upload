from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from time import sleep
from uuid import UUID

from sqlalchemy import desc, func, or_, select

from app.control_center.rule_engine import evaluate_rules
from app.control_center.rules import RuleExecutionBlocked, require_rules_enabled
from app.control_center.service import quota_summary
from app.core.database import SessionLocal
from app.core.security import utcnow
from app.db.models import (
    AccountMetricDaily,
    AccountMonitoringState,
    AuditLog,
    CampaignInstance,
    ControlCenterActionItem,
    ControlCenterActionRequest,
    ControlCenterAd,
    ControlCenterAdAssetLink,
    ControlCenterAdGroup,
    ControlCenterAsset,
    ControlCenterCampaign,
    ControlCenterEvent,
    ControlCenterGoogleChange,
    ControlCenterProblem,
    ControlCenterQuotaLedger,
    ControlCenterRule,
    ControlCenterRuleEvaluation,
    ControlCenterSyncItem,
    ControlCenterSyncRun,
    ConversionActionMapping,
    CustomerAccount,
    GoogleConnection,
    Job,
    JobEvent,
    JobStatus,
    Notification,
)
from app.google_ads.execution_guard import refresh_google_test_target
from app.google_ads.safety import GoogleAdsSafetyError
from app.google_ads.service import build_google_ads_adapter, is_google_connection_active
from app.jobs.celery_app import celery_app

SYNC_INTERVAL_MINUTES = {
    "WORKING": 15,
    "PREPARATION": 60,
    "UNCLASSIFIED": 120,
    "PAUSED": 240,
    "ARCHIVED": 1440,
}


@celery_app.task(name="app.jobs.run_control_center_sync")
def run_control_center_sync(sync_run_id: str) -> dict:
    with SessionLocal() as db:
        try:
            run_id = UUID(sync_run_id)
        except ValueError:
            return {"ok": False, "error": "invalid sync run id"}
        sync_run = db.scalar(
            select(ControlCenterSyncRun)
            .where(ControlCenterSyncRun.id == run_id)
            .with_for_update(skip_locked=True)
        )
        if not sync_run:
            return {"ok": False, "error": "sync run not found or locked"}
        if sync_run.status in {"SUCCEEDED", "COMPLETED_WITH_ERRORS", "FAILED"}:
            return {"ok": True, "reused": True, "status": sync_run.status}
        job = db.get(Job, sync_run.job_id) if sync_run.job_id else None
        sync_run.status = "RUNNING"
        sync_run.started_at = sync_run.started_at or utcnow()
        if job:
            job.status = JobStatus.RUNNING.value
        db.commit()

        items = list(
            db.scalars(
                select(ControlCenterSyncItem)
                .where(ControlCenterSyncItem.sync_run_id == sync_run.id)
                .order_by(ControlCenterSyncItem.created_at)
            ).all()
        )
        succeeded = 0
        failed = 0
        operations = 0
        for item in items:
            if item.status == "SUCCEEDED":
                succeeded += 1
                operations += item.operations
                continue
            ok, item_operations = _sync_account_item(db, sync_run, item)
            operations += item_operations
            if ok:
                succeeded += 1
            else:
                failed += 1
            if job:
                job.progress_current = succeeded + failed
            sync_run.successful_accounts = succeeded
            sync_run.failed_accounts = failed
            sync_run.actual_operations = operations
            db.commit()

        sync_run.completed_at = utcnow()
        sync_run.duration_ms = int(
            (sync_run.completed_at - sync_run.started_at).total_seconds() * 1000
        )
        sync_run.request_ids = list(
            dict.fromkeys(
                request_id
                for item in items
                for request_id in (item.request_ids or [])
            )
        )
        sync_run.statistics = {
            "accounts_total": len(items),
            "accounts_succeeded": succeeded,
            "accounts_failed": failed,
            "operations": operations,
            "request_ids": len(sync_run.request_ids),
        }
        next_runs = [
            account.next_sync_at
            for item in items
            if (account := db.get(CustomerAccount, item.account_id))
            and account.next_sync_at
        ]
        sync_run.next_run_at = min(next_runs) if next_runs else None
        if failed and succeeded:
            sync_run.status = "COMPLETED_WITH_ERRORS"
        elif failed:
            sync_run.status = "FAILED"
        else:
            sync_run.status = "SUCCEEDED"
        if job:
            job.status = (
                JobStatus.SUCCEEDED.value
                if sync_run.status in {"SUCCEEDED", "COMPLETED_WITH_ERRORS"}
                else JobStatus.FAILED.value
            )
            job.error_message = (
                f"Не удалось обновить {failed} аккаунтов" if failed else None
            )
            db.add(
                JobEvent(
                    job_id=job.id,
                    level="WARNING" if failed else "INFO",
                    message=(
                        f"Синхронизация завершена: {succeeded} успешно, {failed} с ошибкой"
                    ),
                    data={"sync_run_id": sync_run_id, "operations": operations},
                )
            )
        db.add(
            AuditLog(
                created_at=utcnow(),
                actor_user_id=sync_run.requested_by_id,
                action="control_center.sync.complete",
                entity_type="control_center_sync_run",
                entity_id=sync_run_id,
                summary={
                    "status": sync_run.status,
                    "successful": succeeded,
                    "failed": failed,
                    "operations": operations,
                },
            )
        )
        db.commit()
        return {
            "ok": not failed,
            "status": sync_run.status,
            "successful": succeeded,
            "failed": failed,
            "operations": operations,
        }


def _sync_account_item(
    db, sync_run: ControlCenterSyncRun, item: ControlCenterSyncItem
) -> tuple[bool, int]:
    account = db.get(CustomerAccount, item.account_id)
    if not account:
        item.status = "FAILED"
        item.error_code = "ACCOUNT_NOT_FOUND"
        item.error_message = "Аккаунт удалён из локального каталога"
        item.completed_at = utcnow()
        return False, 0
    connection = db.get(GoogleConnection, account.connection_id)
    item.status = "RUNNING"
    item.started_at = utcnow()
    account.last_sync_attempt_at = utcnow()
    db.commit()
    if not is_google_connection_active(connection):
        return _fail_sync_item(
            db,
            sync_run,
            item,
            account,
            "CONNECTION_NOT_ACTIVE",
            "Сохранённое подключение Google Ads не активно",
            0,
        )
    if (
        connection.sync_circuit_open_until
        and connection.sync_circuit_open_until > utcnow()
    ):
        return _fail_sync_item(
            db,
            sync_run,
            item,
            account,
            "SYNC_CIRCUIT_OPEN",
            (
                "Синхронизация временно приостановлена после повторяющихся "
                f"ошибок до {connection.sync_circuit_open_until.isoformat()}."
            ),
            0,
        )

    adapter = build_google_ads_adapter(db, connection)
    today = datetime.now(UTC).date()
    history_start_date = today - timedelta(days=29)
    metric_start_date = _incremental_metric_start(
        history_start_date,
        account.last_sync_success_at,
    )
    heavy_sync = _needs_heavy_sync(account, sync_run)
    last_error: Exception | None = None
    max_attempts = max(1, min(int(connection.retry_count or 1), 3))
    for attempt in range(1, max_attempts + 1):
        item.attempts = attempt
        try:
            conversion_actions = _conversion_action_map(db, account)
            account_state = adapter.read_control_center_account(account.customer_id)
            metrics = adapter.fetch_control_center_metrics(
                account.customer_id,
                metric_start_date.isoformat(),
                today.isoformat(),
                conversion_actions,
            )
            campaigns = (
                adapter.list_control_center_campaigns(
                    account.customer_id,
                    history_start_date.isoformat(),
                    today.isoformat(),
                    conversion_actions,
                )
                if heavy_sync
                else None
            )
            verification = _fetch_verification(adapter, account.customer_id)
            conversion_catalog: list[dict] | None = None
            ad_groups: list[dict] | None = None
            ads: list[dict] | None = None
            asset_links: list[dict] | None = None
            changes: list[dict] | None = None
            optional_errors: list[dict] = []
            optional_request_ids: list[str] = []
            optional_operations = 0
            if heavy_sync:
                optional_reads = (
                    ("CONVERSION_ACTIONS", "list_conversion_actions", (account.customer_id,)),
                    ("AD_GROUPS", "list_control_center_ad_groups", (account.customer_id,)),
                    ("ADS", "list_control_center_ads", (account.customer_id,)),
                    ("ASSETS", "list_control_center_asset_links", (account.customer_id,)),
                    (
                        "CHANGE_EVENT",
                        "fetch_control_center_changes",
                        (
                            account.customer_id,
                            _change_event_start(account, item).isoformat(),
                            utcnow().isoformat(),
                        ),
                    ),
                )
                optional_results: dict[str, list[dict] | None] = {}
                for category, method_name, arguments in optional_reads:
                    data, read_request_ids, read_error = _safe_adapter_read(
                        adapter,
                        method_name,
                        arguments,
                    )
                    optional_operations += 1
                    optional_results[category] = None if read_error else data
                    optional_request_ids.extend(read_request_ids)
                    _record_quota(
                        db,
                        connection.id,
                        category,
                        read_error is None,
                        read_request_ids[-1] if read_request_ids else None,
                    )
                    if read_error:
                        optional_errors.append(
                            {"category": category, **read_error}
                        )
                    else:
                        _resolve_problem(db, account.id, f"SYNC_{category}")
                conversion_catalog = optional_results["CONVERSION_ACTIONS"]
                ad_groups = optional_results["AD_GROUPS"]
                ads = optional_results["ADS"]
                asset_links = optional_results["ASSETS"]
                changes = optional_results["CHANGE_EVENT"]
            request_ids = list(
                dict.fromkeys(
                    [
                        *(account_state.get("_request_ids") or []),
                        *(metrics.get("_request_ids") or []),
                        *(
                            campaigns[0].get("_request_ids") or []
                            if campaigns
                            else []
                        ),
                        *optional_request_ids,
                    ]
                )
            )
            operations = 3 + int(campaigns is not None) + optional_operations
            _record_quota(
                db,
                connection.id,
                "ACCOUNT_STATE",
                True,
                request_ids[0] if request_ids else None,
            )
            _record_quota(
                db,
                connection.id,
                "ACCOUNT_METRICS",
                True,
                request_ids[-1] if request_ids else None,
            )
            if campaigns is not None:
                _record_quota(
                    db,
                    connection.id,
                    "CAMPAIGN_CATALOG",
                    True,
                    request_ids[-1] if request_ids else None,
                )
            _record_quota(
                db,
                connection.id,
                "IDENTITY_VERIFICATION",
                not bool(verification.get("error_code")),
            )
            _persist_account_sync(
                db,
                account,
                account_state,
                metrics,
                campaigns,
                verification,
                metric_start_date,
                today,
                connection.connection_mode,
                conversion_catalog=conversion_catalog,
                ad_groups=ad_groups,
                ads=ads,
                asset_links=asset_links,
                changes=changes,
            )
            for optional_error in optional_errors:
                _upsert_problem(
                    db,
                    account,
                    f"SYNC_{optional_error['category']}",
                    "WARNING",
                    f"Часть данных не обновлена: {optional_error['category']}",
                    optional_error["message"],
                    optional_error.get("code"),
                    optional_error.get("request_id"),
                )
            if heavy_sync:
                item.cursor_after = {
                    **(item.cursor_before or {}),
                    "change_event_after": utcnow().isoformat(),
                    "heavy_sync_at": utcnow().isoformat(),
                }
            item.cursor_after = {
                **(item.cursor_after or item.cursor_before or {}),
                "metrics_through": today.isoformat(),
                "metrics_overlap_start": metric_start_date.isoformat(),
            }
            item.status = "SUCCEEDED"
            item.operations = operations
            item.request_ids = request_ids
            item.completed_at = utcnow()
            item.error_code = None
            item.error_message = None
            account.last_sync_success_at = utcnow()
            account.sync_error = None
            connection.sync_failure_count = 0
            connection.sync_circuit_open_until = None
            _resolve_problem(db, account.id, "SYNC_ERROR")
            db.add(
                ControlCenterEvent(
                    account_id=account.id,
                    campaign_id=None,
                    actor_user_id=sync_run.requested_by_id,
                    event_type="SYNC_SUCCEEDED",
                    source="GOOGLE_ADS_API",
                    summary="Данные аккаунта и рекламных объектов обновлены",
                    details={
                        "operations": operations,
                        "campaigns": len(campaigns or []),
                        "campaign_catalog_refreshed": campaigns is not None,
                        "metric_start_date": metric_start_date.isoformat(),
                        "ad_groups": len(ad_groups or []),
                        "ads": len(ads or []),
                        "assets": len(asset_links or []),
                        "changes": len(changes or []),
                        "partial_errors": optional_errors,
                    },
                    occurred_at=utcnow(),
                )
            )
            return True, operations
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                sleep(_retry_delay_seconds(attempt, account.id))
    message = str(last_error) if last_error else "Неизвестная ошибка синхронизации"
    _register_connection_sync_failure(connection)
    failed_categories = [
        "ACCOUNT_STATE",
        "ACCOUNT_METRICS",
        "IDENTITY_VERIFICATION",
    ]
    if heavy_sync:
        failed_categories.append("CAMPAIGN_CATALOG")
    for category in failed_categories:
        _record_quota(db, connection.id, category, False)
    return _fail_sync_item(
        db,
        sync_run,
        item,
        account,
        last_error.__class__.__name__ if last_error else "SYNC_ERROR",
        message,
        3 + int(heavy_sync),
    )


def _persist_account_sync(
    db,
    account: CustomerAccount,
    account_state: dict,
    metrics: dict,
    campaigns: list[dict] | None,
    verification: dict,
    start_date: date,
    end_date: date,
    data_source_mode: str,
    *,
    conversion_catalog: list[dict] | None = None,
    ad_groups: list[dict] | None = None,
    ads: list[dict] | None = None,
    asset_links: list[dict] | None = None,
    changes: list[dict] | None = None,
) -> None:
    now = utcnow()
    previous_status = account.status
    account.descriptive_name = account_state.get("descriptive_name")
    account.currency_code = account_state.get("currency_code")
    account.time_zone = account_state.get("time_zone")
    account.is_test_account = bool(account_state.get("test_account"))
    account.can_manage_clients = bool(account_state.get("manager"))
    account.status = account_state.get("status") or account.status
    account.last_google_request_ids = list(
        dict.fromkeys(
            [
                *(account.last_google_request_ids or []),
                *(account_state.get("_request_ids") or []),
                *(metrics.get("_request_ids") or []),
                *(
                    campaigns[0].get("_request_ids") or []
                    if campaigns
                    else []
                ),
            ]
        )
    )
    account.first_seen_at = account.first_seen_at or now
    account.last_seen_at = now
    account.detached_at = None
    account.verification_status = verification.get("status")
    account.verification_deadline = _parse_google_datetime(verification.get("deadline"))
    account.verification_action_url = verification.get("action_url")
    account.verification_checked_at = now
    if previous_status != account.status:
        db.add(
            ControlCenterEvent(
                account_id=account.id,
                campaign_id=None,
                actor_user_id=None,
                event_type="GOOGLE_STATUS_CHANGED",
                source="GOOGLE_ADS_API",
                summary=f"Статус Google изменён: {previous_status or 'UNKNOWN'} → {account.status}",
                details={"previous": previous_status, "current": account.status},
                occurred_at=now,
            )
        )
        db.add(
            Notification(
                user_id=None,
                severity=(
                    "ERROR"
                    if str(account.status or "").upper()
                    in {"SUSPENDED", "CLOSED", "CANCELED", "CANCELLED"}
                    else "INFO"
                ),
                title="Статус Google Ads изменён",
                message=(
                    f"{account.local_name or account.descriptive_name or account.customer_id}: "
                    f"{previous_status or 'UNKNOWN'} → {account.status}"
                ),
                entity_type="customer_account",
                entity_id=str(account.id),
            )
        )
    has_metrics = bool(metrics.get("has_data"))
    state = db.scalar(
        select(AccountMonitoringState).where(
            AccountMonitoringState.account_id == account.id
        )
    )
    if not state:
        state = AccountMonitoringState(account_id=account.id)
        db.add(state)
    state.period_start = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
    state.period_end = datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)
    state.timezone_mode = "ACCOUNT"
    state.boundary_precision = "EXACT"
    state.data_source_mode = data_source_mode
    state.impressions = metrics.get("impressions") if has_metrics else None
    state.clicks = metrics.get("clicks") if has_metrics else None
    state.cost_micros = metrics.get("cost_micros") if has_metrics else None
    state.conversions = metrics.get("conversions") if has_metrics else None
    state.all_conversions = metrics.get("all_conversions") if has_metrics else None
    state.conversion_value = metrics.get("conversion_value") if has_metrics else None
    state.registrations = metrics.get("registrations") if has_metrics else None
    state.deposits = metrics.get("deposits") if has_metrics else None
    state.registration_value = (
        metrics.get("registration_value") if has_metrics else None
    )
    state.deposit_value = metrics.get("deposit_value") if has_metrics else None
    state.registration_data_available = bool(
        metrics.get("registration_data_available")
    )
    state.deposit_data_available = bool(metrics.get("deposit_data_available"))
    if campaigns is None:
        stored_campaigns = list(
            db.scalars(
                select(ControlCenterCampaign).where(
                    ControlCenterCampaign.account_id == account.id
                )
            ).all()
        )
        budget_by_resource = {
            row.budget_resource_name: int(row.budget_micros)
            for row in stored_campaigns
            if row.status == "ENABLED"
            and row.budget_resource_name
            and row.budget_micros is not None
        }
        active_campaigns = sum(
            row.status == "ENABLED" for row in stored_campaigns
        )
        campaign_policy_issues = sum(
            bool(row.policy_issues) for row in stored_campaigns
        )
    else:
        budget_by_resource = {
            row["budget_resource_name"]: int(row["budget_micros"])
            for row in campaigns
            if row.get("status") == "ENABLED"
            and row.get("budget_resource_name")
            and row.get("budget_micros") is not None
        }
        active_campaigns = sum(
            row.get("status") == "ENABLED" for row in campaigns
        )
        campaign_policy_issues = sum(
            bool(row.get("policy_issues")) for row in campaigns
        )
    state.budget_micros = sum(budget_by_resource.values()) if budget_by_resource else None
    state.active_campaigns = active_campaigns
    if ads is not None:
        state.disapproved_ads = sum(
            row.get("policy_approval_status") == "DISAPPROVED" for row in ads
        )
    state.policy_issues = campaign_policy_issues + state.disapproved_ads
    state.freshness = "FRESH"
    state.data_observed_at = now
    state.aggregated_at = now
    state.last_error_code = None
    state.last_request_id = (
        account.last_google_request_ids[-1]
        if account.last_google_request_ids
        else None
    )
    for row in metrics.get("daily") or []:
        metric_date = date.fromisoformat(row["date"])
        snapshot = db.scalar(
            select(AccountMetricDaily).where(
                AccountMetricDaily.account_id == account.id,
                AccountMetricDaily.metric_date == metric_date,
                AccountMetricDaily.timezone_mode == "ACCOUNT",
            )
        )
        if not snapshot:
            snapshot = AccountMetricDaily(
                account_id=account.id,
                metric_date=metric_date,
                timezone_mode="ACCOUNT",
            )
            db.add(snapshot)
        snapshot.boundary_precision = "EXACT"
        snapshot.data_source_mode = data_source_mode
        snapshot.impressions = row.get("impressions")
        snapshot.clicks = row.get("clicks")
        snapshot.cost_micros = row.get("cost_micros")
        snapshot.conversions = row.get("conversions")
        snapshot.all_conversions = row.get("all_conversions")
        snapshot.conversion_value = row.get("conversion_value")
        snapshot.registrations = row.get("registrations")
        snapshot.deposits = row.get("deposits")
        snapshot.registration_value = row.get("registration_value")
        snapshot.deposit_value = row.get("deposit_value")
        snapshot.registration_data_available = bool(
            row.get("registration_data_available")
        )
        snapshot.deposit_data_available = bool(row.get("deposit_data_available"))
        snapshot.budget_micros = state.budget_micros
        snapshot.active_campaigns = state.active_campaigns
        snapshot.disapproved_ads = state.disapproved_ads
        snapshot.request_id = state.last_request_id
        snapshot.source = "GOOGLE_ADS"
        snapshot.observed_at = now
    uploader_names = _uploader_resource_names(db, account.customer_id)
    seen_resources: set[str] = set()
    for row in campaigns or []:
        resource_name = row["resource_name"]
        seen_resources.add(resource_name)
        campaign = db.scalar(
            select(ControlCenterCampaign).where(
                ControlCenterCampaign.account_id == account.id,
                ControlCenterCampaign.resource_name == resource_name,
            )
        )
        if not campaign:
            campaign = ControlCenterCampaign(
                account_id=account.id,
                connection_id=account.connection_id,
                resource_name=resource_name,
                campaign_id=row["campaign_id"],
                name=row["name"],
            )
            db.add(campaign)
        previous_campaign_status = campaign.status
        campaign.campaign_id = row["campaign_id"]
        campaign.name = row["name"]
        campaign.source = (
            "DEMAND_GEN_UPLOADER"
            if resource_name in uploader_names
            else "GOOGLE_ADS_MANUAL"
        )
        campaign.channel_type = row.get("channel_type")
        campaign.channel_subtype = row.get("channel_subtype")
        campaign.status = row.get("status")
        campaign.primary_status = row.get("primary_status")
        campaign.primary_status_reasons = row.get("primary_status_reasons") or []
        campaign.budget_resource_name = row.get("budget_resource_name")
        campaign.budget_micros = row.get("budget_micros")
        campaign.budget_shared = row.get("budget_shared")
        campaign.bidding_strategy_type = row.get("bidding_strategy_type")
        campaign.impressions = (
            None if account.is_test_account else row.get("impressions")
        )
        campaign.clicks = None if account.is_test_account else row.get("clicks")
        campaign.cost_micros = (
            None if account.is_test_account else row.get("cost_micros")
        )
        campaign.conversions = (
            None if account.is_test_account else row.get("conversions")
        )
        campaign.all_conversions = (
            None if account.is_test_account else row.get("all_conversions")
        )
        campaign.registrations = (
            None if account.is_test_account else row.get("registrations")
        )
        campaign.deposits = (
            None if account.is_test_account else row.get("deposits")
        )
        campaign.registration_data_available = bool(
            row.get("registration_data_available")
        ) and not account.is_test_account
        campaign.deposit_data_available = bool(
            row.get("deposit_data_available")
        ) and not account.is_test_account
        campaign.conversion_value = (
            None if account.is_test_account else row.get("conversion_value")
        )
        campaign.policy_status = row.get("policy_status")
        campaign.policy_issues = row.get("policy_issues") or []
        campaign.last_synced_at = now
        campaign.sync_error = None
        if previous_campaign_status and previous_campaign_status != campaign.status:
            db.add(
                ControlCenterEvent(
                    account_id=account.id,
                    campaign_id=campaign.id,
                    actor_user_id=None,
                    event_type="CAMPAIGN_STATUS_CHANGED",
                    source="GOOGLE_ADS_API",
                    summary=(
                        f"Кампания «{campaign.name}»: "
                        f"{previous_campaign_status} → {campaign.status}"
                    ),
                    details={
                        "previous": previous_campaign_status,
                        "current": campaign.status,
                    },
                    occurred_at=now,
                )
            )
    if campaigns is not None:
        for stale in db.scalars(
            select(ControlCenterCampaign).where(
                ControlCenterCampaign.account_id == account.id,
                ControlCenterCampaign.resource_name.not_in(seen_resources)
                if seen_resources
                else True,
            )
        ).all():
            stale.sync_error = "Кампания не найдена при последней синхронизации"
    if conversion_catalog is not None:
        _refresh_conversion_mappings(
            db,
            account,
            conversion_catalog,
            now,
        )
    if ad_groups is not None or ads is not None or asset_links is not None:
        _persist_drilldown(
            db,
            account,
            ad_groups=ad_groups or [],
            ads=ads or [],
            asset_links=asset_links or [],
            now=now,
        )
    if changes is not None:
        _persist_google_changes(
            db,
            account,
            changes,
            now=now,
        )
    account.activity_status = _activity_status_from_sync(account, state)
    interval = _adaptive_sync_interval(account, state)
    account.sync_interval_minutes = interval
    account.next_sync_at = now + timedelta(
        minutes=_jittered_sync_interval(account, interval)
    )


def _conversion_action_map(db, account: CustomerAccount) -> dict[str, list[str]]:
    rows = list(
        db.scalars(
            select(ConversionActionMapping).where(
                ConversionActionMapping.connection_id == account.connection_id,
                ConversionActionMapping.is_active.is_(True),
                or_(
                    ConversionActionMapping.account_id == account.id,
                    ConversionActionMapping.account_id.is_(None),
                ),
            )
        ).all()
    )
    result: dict[str, list[str]] = {"REGISTRATION": [], "DEPOSIT": []}
    for row in rows:
        if row.semantic_type in result:
            result[row.semantic_type].append(row.resource_name)
    return {
        semantic_type: list(dict.fromkeys(resource_names))
        for semantic_type, resource_names in result.items()
    }


def _needs_heavy_sync(
    account: CustomerAccount,
    sync_run: ControlCenterSyncRun,
) -> bool:
    if sync_run.scope == "SELECTED":
        return True
    if account.last_sync_success_at is None:
        return True
    return utcnow() - account.last_sync_success_at >= timedelta(hours=6)


def _incremental_metric_start(
    history_start: date,
    last_success_at: datetime | None,
) -> date:
    if last_success_at is None:
        return history_start
    overlap_start = last_success_at.astimezone(UTC).date() - timedelta(days=2)
    return max(history_start, overlap_start)


def _retry_delay_seconds(attempt: int, account_id: UUID) -> float:
    digest = hashlib.sha256(f"{account_id}:{attempt}".encode()).digest()
    jitter = int.from_bytes(digest[:2], "big") / 65_535 * 0.2
    return min(4.0, 0.5 * (2 ** max(0, attempt - 1)) + jitter)


def _register_connection_sync_failure(connection: GoogleConnection) -> None:
    connection.sync_failure_count = int(connection.sync_failure_count or 0) + 1
    if connection.sync_failure_count < 3:
        return
    exponent = min(3, connection.sync_failure_count - 3)
    connection.sync_circuit_open_until = utcnow() + timedelta(
        minutes=15 * (2**exponent)
    )


def _change_event_start(
    account: CustomerAccount,
    item: ControlCenterSyncItem,
) -> datetime:
    earliest = utcnow() - timedelta(days=29)
    cursor_value = (item.cursor_before or {}).get("change_event_after")
    candidates = [earliest, account.last_sync_success_at]
    if cursor_value:
        try:
            candidates.append(datetime.fromisoformat(str(cursor_value).replace("Z", "+00:00")))
        except ValueError:
            pass
    return max(value for value in candidates if value is not None)


def _safe_adapter_read(
    adapter,
    method_name: str,
    arguments: tuple,
) -> tuple[list[dict], list[str], dict | None]:
    method = getattr(adapter, method_name, None)
    if method is None:
        return (
            [],
            [],
            {
                "code": "ADAPTER_METHOD_UNAVAILABLE",
                "message": f"Адаптер не поддерживает чтение {method_name}",
                "request_id": None,
            },
        )
    try:
        data = method(*arguments)
        rows = data if isinstance(data, list) else []
        request_ids: list[str] = []
        for row in rows:
            request_ids.extend(row.get("_request_ids") or [])
        return rows, list(dict.fromkeys(request_ids)), None
    except Exception as exc:
        return [], [], _google_read_error(exc)


def _google_read_error(exc: Exception) -> dict:
    request_id = getattr(exc, "request_id", None)
    code = exc.__class__.__name__
    failure = getattr(exc, "failure", None)
    errors = list(getattr(failure, "errors", []) or [])
    messages: list[str] = []
    if errors:
        error_code = getattr(errors[0], "error_code", None)
        code = str(error_code or code).strip().replace("\n", " ")
        messages = [
            str(getattr(error, "message", "") or "").strip()
            for error in errors
            if str(getattr(error, "message", "") or "").strip()
        ]
    message = "; ".join(messages) or str(exc).strip()
    if "<_InactiveRpcError" in message or "debug_error_string" in message:
        message = "Google Ads API отклонил запрос; точная причина указана в коде ошибки."
    return {
        "code": code[:160],
        "message": message,
        "request_id": str(request_id) if request_id else None,
    }


def _refresh_conversion_mappings(
    db,
    account: CustomerAccount,
    catalog: list[dict],
    now: datetime,
) -> None:
    if not catalog:
        return
    catalog_by_resource = {
        row["resource_name"]: row
        for row in catalog
        if row.get("resource_name")
    }
    mappings = db.scalars(
        select(ConversionActionMapping).where(
            ConversionActionMapping.connection_id == account.connection_id,
            or_(
                ConversionActionMapping.account_id == account.id,
                ConversionActionMapping.account_id.is_(None),
            ),
        )
    ).all()
    for mapping in mappings:
        remote = catalog_by_resource.get(mapping.resource_name)
        if not remote:
            continue
        mapping.name = remote.get("name") or mapping.name
        mapping.owner_customer_id = (
            remote.get("owner_customer_id") or mapping.owner_customer_id
        )
        mapping.last_synced_at = now


def _persist_drilldown(
    db,
    account: CustomerAccount,
    *,
    ad_groups: list[dict],
    ads: list[dict],
    asset_links: list[dict],
    now: datetime,
) -> None:
    if not (ad_groups or ads or asset_links):
        return
    db.flush()
    campaign_rows = list(
        db.scalars(
            select(ControlCenterCampaign).where(
                ControlCenterCampaign.account_id == account.id
            )
        ).all()
    )
    campaign_by_resource = {
        row.resource_name: row for row in campaign_rows
    }
    ad_group_by_resource: dict[str, ControlCenterAdGroup] = {}
    for remote in ad_groups:
        campaign = campaign_by_resource.get(remote.get("campaign_resource_name"))
        if not campaign or not remote.get("resource_name"):
            continue
        row = db.scalar(
            select(ControlCenterAdGroup).where(
                ControlCenterAdGroup.account_id == account.id,
                ControlCenterAdGroup.resource_name == remote["resource_name"],
            )
        )
        if not row:
            row = ControlCenterAdGroup(
                account_id=account.id,
                campaign_id=campaign.id,
                resource_name=remote["resource_name"],
                ad_group_id=remote["ad_group_id"],
                name=remote["name"],
            )
            db.add(row)
        row.campaign_id = campaign.id
        row.ad_group_id = remote["ad_group_id"]
        row.name = remote["name"]
        row.status = remote.get("status")
        row.ad_group_type = remote.get("type")
        row.last_synced_at = now
        ad_group_by_resource[row.resource_name] = row
    db.flush()

    ad_by_resource: dict[str, ControlCenterAd] = {}
    for remote in ads:
        campaign = campaign_by_resource.get(remote.get("campaign_resource_name"))
        ad_group = ad_group_by_resource.get(remote.get("ad_group_resource_name"))
        if not campaign or not ad_group or not remote.get("resource_name"):
            continue
        row = db.scalar(
            select(ControlCenterAd).where(
                ControlCenterAd.account_id == account.id,
                ControlCenterAd.resource_name == remote["resource_name"],
            )
        )
        previous_approval = row.primary_status if row else None
        if not row:
            row = ControlCenterAd(
                account_id=account.id,
                campaign_id=campaign.id,
                ad_group_id=ad_group.id,
                resource_name=remote["resource_name"],
                ad_id=remote["ad_id"],
            )
            db.add(row)
        row.campaign_id = campaign.id
        row.ad_group_id = ad_group.id
        row.ad_id = remote["ad_id"]
        row.name = remote.get("name")
        row.ad_type = remote.get("type")
        row.status = remote.get("status")
        row.primary_status = remote.get("policy_approval_status")
        row.final_urls = remote.get("final_urls") or []
        row.policy_summary = {
            "approval_status": remote.get("policy_approval_status"),
            "review_status": remote.get("policy_review_status"),
            "topics": remote.get("policy_topics") or [],
        }
        row.disapproval_reasons = remote.get("policy_topics") or []
        row.last_synced_at = now
        ad_by_resource[row.resource_name] = row
        if previous_approval and previous_approval != row.primary_status:
            db.add(
                ControlCenterEvent(
                    account_id=account.id,
                    campaign_id=campaign.id,
                    actor_user_id=None,
                    event_type="AD_POLICY_STATUS_CHANGED",
                    source="GOOGLE_ADS_API",
                    summary=(
                        f"Статус объявления изменён: "
                        f"{previous_approval} → {row.primary_status}"
                    ),
                    details={
                        "ad_resource_name": row.resource_name,
                        "previous": previous_approval,
                        "current": row.primary_status,
                        "policy_topics": row.disapproval_reasons,
                    },
                    occurred_at=now,
                )
            )
            db.add(
                Notification(
                    user_id=None,
                    severity=(
                        "ERROR"
                        if row.primary_status == "DISAPPROVED"
                        else "INFO"
                    ),
                    title="Статус модерации объявления изменён",
                    message=(
                        f"{previous_approval} → {row.primary_status or 'UNKNOWN'}"
                    ),
                    entity_type="control_center_ad",
                    entity_id=str(row.id),
                )
            )
    db.flush()

    asset_by_resource: dict[str, ControlCenterAsset] = {}
    for remote in asset_links:
        resource_name = remote.get("asset_resource_name")
        if not resource_name:
            continue
        row = asset_by_resource.get(resource_name) or db.scalar(
            select(ControlCenterAsset).where(
                ControlCenterAsset.account_id == account.id,
                ControlCenterAsset.resource_name == resource_name,
            )
        )
        if not row:
            row = ControlCenterAsset(
                account_id=account.id,
                resource_name=resource_name,
                asset_id=remote["asset_id"],
            )
            db.add(row)
        row.asset_id = remote["asset_id"]
        row.name = remote.get("asset_name")
        row.asset_type = remote.get("asset_type")
        row.source = "GOOGLE_ADS"
        row.image_url = remote.get("image_url")
        row.image_width = remote.get("width")
        row.image_height = remote.get("height")
        row.youtube_video_id = remote.get("youtube_video_id")
        row.last_synced_at = now
        asset_by_resource[resource_name] = row
    db.flush()

    for remote in asset_links:
        campaign = campaign_by_resource.get(remote.get("campaign_resource_name"))
        ad_group = ad_group_by_resource.get(remote.get("ad_group_resource_name"))
        ad = ad_by_resource.get(remote.get("ad_resource_name"))
        asset = asset_by_resource.get(remote.get("asset_resource_name"))
        field_type = remote.get("field_type") or "UNKNOWN"
        if not campaign or not ad_group or not ad or not asset:
            continue
        row = db.scalar(
            select(ControlCenterAdAssetLink).where(
                ControlCenterAdAssetLink.ad_id == ad.id,
                ControlCenterAdAssetLink.asset_id == asset.id,
                ControlCenterAdAssetLink.field_type == field_type,
            )
        )
        if not row:
            row = ControlCenterAdAssetLink(
                account_id=account.id,
                campaign_id=campaign.id,
                ad_group_id=ad_group.id,
                ad_id=ad.id,
                asset_id=asset.id,
                field_type=field_type,
            )
            db.add(row)
        row.resource_name = remote.get("link_resource_name")
        row.performance_label = remote.get("performance_label")
        row.last_synced_at = now


def _persist_google_changes(
    db,
    account: CustomerAccount,
    changes: list[dict],
    *,
    now: datetime,
) -> None:
    if not changes:
        return
    campaigns = list(
        db.scalars(
            select(ControlCenterCampaign).where(
                ControlCenterCampaign.account_id == account.id
            )
        ).all()
    )
    campaign_by_resource = {item.resource_name: item for item in campaigns}
    for remote in changes:
        changed_resource_name = remote.get("changed_resource_name")
        changed_at = _parse_google_datetime(remote.get("changed_at")) or now
        if not changed_resource_name:
            continue
        fingerprint = hashlib.sha256(
            "|".join(
                [
                    account.customer_id,
                    str(remote.get("resource_name") or ""),
                    str(changed_resource_name),
                    changed_at.isoformat(),
                    str(remote.get("change_type") or ""),
                ]
            ).encode()
        ).hexdigest()
        if db.scalar(
            select(ControlCenterGoogleChange.id).where(
                ControlCenterGoogleChange.event_fingerprint == fingerprint
            )
        ):
            continue
        campaign = campaign_by_resource.get(changed_resource_name)
        request_ids = remote.get("_request_ids") or []
        db.add(
            ControlCenterGoogleChange(
                connection_id=account.connection_id,
                account_id=account.id,
                campaign_id=campaign.id if campaign else None,
                event_fingerprint=fingerprint,
                change_resource_name=remote.get("resource_name"),
                changed_resource_name=changed_resource_name,
                resource_type=remote.get("resource_type") or "UNKNOWN",
                change_type=remote.get("change_type") or "UNKNOWN",
                client_type=remote.get("client_type"),
                user_email=remote.get("user_email"),
                old_resource=remote.get("old_resource") or {},
                new_resource=remote.get("new_resource") or {},
                changed_fields=remote.get("changed_fields") or [],
                changed_at=changed_at,
                request_id=request_ids[-1] if request_ids else None,
            )
        )
        if campaign:
            campaign.last_change_at = max(
                filter(None, [campaign.last_change_at, changed_at])
            )


def _activity_status_from_sync(
    account: CustomerAccount,
    state: AccountMonitoringState,
) -> str:
    status = (account.status or "UNKNOWN").upper()
    if account.detached_at is not None:
        return "NO_ACCESS"
    if status in {"SUSPENDED", "CLOSED", "CANCELED", "CANCELLED"}:
        return "SUSPENDED"
    if state.active_campaigns == 0:
        return "NO_ACTIVE_CAMPAIGNS"
    if state.active_campaigns and state.cost_micros == 0:
        return "ENABLED_NO_SPEND"
    if state.cost_micros is not None and state.cost_micros > 0:
        return "SPENDING"
    if state.cost_micros == 0:
        return "NOT_SPENDING"
    return "NO_DATA"


def _adaptive_sync_interval(
    account: CustomerAccount,
    state: AccountMonitoringState,
) -> int:
    if account.detached_at is not None:
        return 1440
    if account.work_status == "ARCHIVED":
        return 1440
    if account.sync_error or state.policy_issues:
        return 15
    return SYNC_INTERVAL_MINUTES.get(account.work_status, 360)


def _jittered_sync_interval(account: CustomerAccount, interval: int) -> int:
    jitter = ((int(account.id.hex[:4], 16) % 21) - 10) / 100
    return max(5, round(interval * (1 + jitter)))


def _fetch_verification(adapter, customer_id: str) -> dict:
    try:
        result = adapter.fetch_identity_verification(customer_id)
    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "deadline": None,
            "action_url": None,
            "error_code": exc.__class__.__name__,
        }
    if not isinstance(result, dict):
        return {"status": "UNKNOWN", "deadline": None, "action_url": None}
    return result


def _parse_google_datetime(value: str | None):
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _uploader_resource_names(db, customer_id: str) -> set[str]:
    names: set[str] = set()
    for resources in db.scalars(
        select(CampaignInstance.resource_names).where(
            CampaignInstance.customer_id == customer_id
        )
    ).all():
        names.update(str(item) for item in resources or [])
    return names


def _record_quota(
    db,
    connection_id: UUID | None,
    category: str,
    succeeded: bool,
    request_id: str | None = None,
) -> None:
    db.add(
        ControlCenterQuotaLedger(
            connection_id=connection_id,
            operation_date=datetime.now(UTC).date(),
            category=category,
            operation_count=1,
            succeeded=succeeded,
            request_id=request_id,
        )
    )


def _fail_sync_item(
    db,
    sync_run: ControlCenterSyncRun,
    item: ControlCenterSyncItem,
    account: CustomerAccount,
    code: str,
    message: str,
    operations: int,
) -> tuple[bool, int]:
    now = utcnow()
    item.status = "FAILED"
    item.operations = operations
    item.completed_at = now
    item.error_code = code
    item.error_message = message
    account.sync_error = message
    retry_interval = min(
        1440 if account.detached_at else 60,
        max(15, int(getattr(account, "sync_interval_minutes", 60) or 60)),
    )
    account.next_sync_at = now + timedelta(
        minutes=_jittered_sync_interval(account, retry_interval)
    )
    state = db.scalar(
        select(AccountMonitoringState).where(
            AccountMonitoringState.account_id == account.id
        )
    )
    if not state:
        state = AccountMonitoringState(account_id=account.id)
        db.add(state)
    state.freshness = "ERROR"
    state.last_error_code = code
    _upsert_problem(
        db,
        account,
        "SYNC_ERROR",
        "ERROR",
        "Ошибка синхронизации",
        message,
        code,
    )
    db.add(
        ControlCenterEvent(
            account_id=account.id,
            campaign_id=None,
            actor_user_id=sync_run.requested_by_id,
            event_type="SYNC_FAILED",
            source="GOOGLE_ADS_API",
            summary="Синхронизация аккаунта завершилась ошибкой",
            details={"code": code, "message": message},
            occurred_at=now,
        )
    )
    return False, operations


def _upsert_problem(
    db,
    account: CustomerAccount,
    problem_type: str,
    severity: str,
    title: str,
    description: str,
    google_code: str | None = None,
    request_id: str | None = None,
) -> None:
    fingerprint = hashlib.sha256(
        f"{account.id}:{problem_type}:{google_code or ''}".encode()
    ).hexdigest()
    problem = db.scalar(
        select(ControlCenterProblem).where(
            ControlCenterProblem.fingerprint == fingerprint
        )
    )
    now = utcnow()
    if not problem:
        problem = ControlCenterProblem(
            fingerprint=fingerprint,
            connection_id=account.connection_id,
            account_id=account.id,
            campaign_id=None,
            source="GOOGLE_ADS_API",
            problem_type=problem_type,
            severity=severity,
            title=title,
            description=description,
            google_code=google_code,
            request_id=request_id,
            state="NEW",
            first_seen_at=now,
            last_seen_at=now,
            diagnostics={},
        )
        db.add(problem)
    else:
        problem.severity = severity
        problem.title = title
        problem.description = description
        problem.google_code = google_code
        problem.request_id = request_id
        problem.state = "NEW" if problem.state == "RESOLVED" else problem.state
        problem.resolved_at = None
        problem.last_seen_at = now


def _resolve_problem(db, account_id: UUID, problem_type: str) -> None:
    now = utcnow()
    for problem in db.scalars(
        select(ControlCenterProblem).where(
            ControlCenterProblem.account_id == account_id,
            ControlCenterProblem.problem_type == problem_type,
            ControlCenterProblem.state != "RESOLVED",
        )
    ).all():
        problem.state = "RESOLVED"
        problem.resolved_at = now
        problem.last_seen_at = now


@celery_app.task(name="app.jobs.dispatch_due_control_center_sync")
def dispatch_due_control_center_sync() -> dict:
    with SessionLocal() as db:
        if quota_summary(db)["background_throttled"]:
            return {"queued": 0, "reason": "quota_reserve"}
        active = db.scalar(
            select(ControlCenterSyncRun).where(
                ControlCenterSyncRun.status.in_(["QUEUED", "RUNNING"])
            )
        )
        if active:
            return {"queued": 0, "reason": "active_run"}
        now = utcnow()
        accounts = list(
            db.scalars(
                select(CustomerAccount)
                .where(
                    or_(
                        CustomerAccount.next_sync_at.is_(None),
                        CustomerAccount.next_sync_at <= now,
                    )
                )
                .order_by(
                    desc(CustomerAccount.is_pinned),
                    CustomerAccount.next_sync_at,
                    CustomerAccount.last_sync_attempt_at,
                )
                .with_for_update(skip_locked=True)
                .limit(500)
            ).all()
        )
        due = accounts[:50]
        if not due:
            return {"queued": 0, "reason": "nothing_due"}
        fingerprint = hashlib.sha256(
            f"scheduled:{now.strftime('%Y-%m-%dT%H:%M')}:{','.join(str(item.id) for item in due)}".encode()
        ).hexdigest()
        existing = db.scalar(
            select(ControlCenterSyncRun).where(
                ControlCenterSyncRun.idempotency_key == fingerprint
            )
        )
        if existing:
            return {"queued": 0, "reason": "duplicate"}
        job = Job(
            type="CONTROL_CENTER_SYNC",
            status=JobStatus.QUEUED.value,
            connection_id=None,
            created_by_id=None,
            idempotency_key=f"cc-sync:{fingerprint}",
            progress_current=0,
            progress_total=len(due),
            payload={"scope": "ADAPTIVE", "account_ids": [str(item.id) for item in due]},
        )
        db.add(job)
        db.flush()
        sync_run = ControlCenterSyncRun(
            connection_id=None,
            job_id=job.id,
            requested_by_id=None,
            scope="ADAPTIVE",
            mode="READ_ONLY",
            status="QUEUED",
            estimated_operations=len(due) * 4,
            actual_operations=0,
            successful_accounts=0,
            failed_accounts=0,
            selection=[str(item.id) for item in due],
            idempotency_key=fingerprint,
        )
        db.add(sync_run)
        db.flush()
        for account in due:
            db.add(
                ControlCenterSyncItem(
                    sync_run_id=sync_run.id,
                    account_id=account.id,
                    status="QUEUED",
                    attempts=0,
                    operations=0,
                    request_ids=[],
                )
            )
        db.commit()
        run_control_center_sync.delay(str(sync_run.id))
        return {"queued": len(due), "sync_run_id": str(sync_run.id)}


@celery_app.task(name="app.jobs.execute_control_center_action")
def execute_control_center_action(action_id: str) -> dict:
    with SessionLocal() as db:
        try:
            parsed_id = UUID(action_id)
        except ValueError:
            return {"ok": False, "error": "invalid action id"}
        action = db.scalar(
            select(ControlCenterActionRequest)
            .where(ControlCenterActionRequest.id == parsed_id)
            .with_for_update(skip_locked=True)
        )
        if not action:
            return {"ok": False, "error": "action not found or locked"}
        if action.execution_mode != "GOOGLE_TEST" or action.status != "QUEUED":
            return {
                "ok": False,
                "error": "action is not a queued GOOGLE_TEST action",
            }
        rule_evaluation = db.scalar(
            select(ControlCenterRuleEvaluation).where(
                ControlCenterRuleEvaluation.action_request_id == action.id
            )
        )
        if rule_evaluation:
            try:
                require_rules_enabled(db, "BEFORE_MUTATE")
            except RuleExecutionBlocked:
                _stop_rule_action_for_kill_switch(
                    db,
                    action,
                    rule_evaluation,
                    "BEFORE_MUTATE",
                )
                db.commit()
                return {
                    "ok": False,
                    "status": action.status,
                    "error": "GLOBAL_KILL_SWITCH_ACTIVE",
                }
        action.status = "RUNNING"
        db.commit()
        items = list(
            db.scalars(
                select(ControlCenterActionItem).where(
                    ControlCenterActionItem.action_request_id == action.id
                )
            ).all()
        )
        grouped: dict[UUID, list[ControlCenterActionItem]] = defaultdict(list)
        for item in items:
            grouped[item.account_id].append(item)
        any_failed = False
        all_request_ids = list(action.request_ids or [])
        validation_request_ids: list[str] = []
        mutate_request_ids: list[str] = []
        readback: list[dict] = []
        kill_switch_blocked = False
        for account_id, account_items in grouped.items():
            account = db.get(CustomerAccount, account_id)
            connection = db.get(GoogleConnection, account.connection_id) if account else None
            if not account or not is_google_connection_active(connection):
                for item in account_items:
                    item.status = "FAILED"
                    item.error_message = "Аккаунт или подключение недоступны"
                any_failed = True
                continue
            adapter = build_google_ads_adapter(db, connection)
            campaigns = {
                campaign.id: campaign
                for campaign in db.scalars(
                    select(ControlCenterCampaign).where(
                        ControlCenterCampaign.id.in_(
                            [item.campaign_id for item in account_items]
                        )
                    )
                ).all()
            }
            try:
                _, _, account_request_ids = refresh_google_test_target(
                    db,
                    connection,
                    adapter,
                    account.customer_id,
                    confirmed_at=action.confirmed_at,
                    require_confirmation=True,
                )
                all_request_ids.extend(account_request_ids)
                fresh = {}
                for campaign in campaigns.values():
                    state = adapter.read_control_center_campaign(
                        account.customer_id, campaign.resource_name
                    )
                    fresh[campaign.id] = state
                    all_request_ids.extend(state.get("_request_ids") or [])
                for item in account_items:
                    current = fresh[item.campaign_id]
                    previous = item.previous_state or {}
                    field = (
                        "budget_micros"
                        if action.action_type == "SET_BUDGET"
                        else "status"
                    )
                    if previous.get(field) != current.get(field):
                        raise GoogleAdsSafetyError(
                            "STALE_STATE",
                            (
                                f"Состояние кампании изменилось после preview: "
                                f"{field} было {previous.get(field)!r}, "
                                f"стало {current.get(field)!r}."
                            ),
                        )
                if action.action_type in {"PAUSE", "ENABLE"}:
                    target = "PAUSED" if action.action_type == "PAUSE" else "ENABLED"
                    refs = [
                        {
                            "resource_name": campaigns[
                                item.campaign_id
                            ].resource_name,
                            "campaign_instance_id": str(item.campaign_id),
                        }
                        for item in account_items
                    ]
                    if rule_evaluation:
                        require_rules_enabled(db, "BEFORE_VALIDATE_ONLY")
                    validation = adapter.validate_campaign_status(
                        account.customer_id,
                        refs,
                        target,
                    )
                    validation_request_ids.extend(validation.request_ids)
                    all_request_ids.extend(validation.request_ids)
                    if not validation.ok:
                        raise RuntimeError(_result_error_message(validation))
                    if rule_evaluation:
                        require_rules_enabled(db, "BEFORE_MUTATE")
                    result = adapter.change_campaign_status(
                        account.customer_id,
                        refs,
                        target,
                    )
                    _record_quota(
                        db,
                        connection.id,
                        "CAMPAIGN_STATUS_MUTATE",
                        result.ok,
                        result.request_ids[0] if result.request_ids else None,
                    )
                    all_request_ids.extend(result.request_ids)
                    mutate_request_ids.extend(result.request_ids)
                    if not result.ok:
                        raise RuntimeError(_result_error_message(result))
                else:
                    for item in account_items:
                        current = fresh[item.campaign_id]
                        if rule_evaluation:
                            require_rules_enabled(db, "BEFORE_VALIDATE_ONLY")
                        validation = adapter.change_campaign_budget(
                            account.customer_id,
                            current["budget_resource_name"],
                            int(action.requested_payload["amount_micros"]),
                            validate_only=True,
                        )
                        validation_request_ids.extend(validation.request_ids)
                        all_request_ids.extend(validation.request_ids)
                        if not validation.ok:
                            raise RuntimeError(_result_error_message(validation))
                        if rule_evaluation:
                            require_rules_enabled(db, "BEFORE_MUTATE")
                        result = adapter.change_campaign_budget(
                            account.customer_id,
                            current["budget_resource_name"],
                            int(action.requested_payload["amount_micros"]),
                            validate_only=False,
                        )
                        _record_quota(
                            db,
                            connection.id,
                            "CAMPAIGN_BUDGET_MUTATE",
                            result.ok,
                            result.request_ids[0] if result.request_ids else None,
                        )
                        all_request_ids.extend(result.request_ids)
                        mutate_request_ids.extend(result.request_ids)
                        if not result.ok:
                            raise RuntimeError(_result_error_message(result))
                for item in account_items:
                    campaign = campaigns[item.campaign_id]
                    current = adapter.read_control_center_campaign(
                        account.customer_id, campaign.resource_name
                    )
                    read_request_ids = list(current.get("_request_ids") or [])
                    all_request_ids.extend(read_request_ids)
                    if action.action_type in {"PAUSE", "ENABLE"}:
                        requested_value = (
                            "PAUSED"
                            if action.action_type == "PAUSE"
                            else "ENABLED"
                        )
                        actual_value = current.get("status")
                        field = "status"
                    else:
                        requested_value = int(
                            action.requested_payload["amount_micros"]
                        )
                        actual_value = current.get("budget_micros")
                        field = "budget_micros"
                    if actual_value != requested_value:
                        raise GoogleAdsSafetyError(
                            "READBACK_MISMATCH",
                            (
                                f"Повторное чтение не подтвердило {field}: "
                                f"ожидалось {requested_value!r}, "
                                f"получено {actual_value!r}."
                            ),
                        )
                    item.status = "SUCCEEDED"
                    item.result = {
                        "customer_id": account.customer_id,
                        "object": campaign.resource_name,
                        "field": field,
                        "before": item.previous_state.get(field),
                        "requested": requested_value,
                        "actual": actual_value,
                        "readback_verified": True,
                        "readback_at": utcnow().isoformat(),
                        "google_test": True,
                        "state": current,
                    }
                    item.request_id = (
                        mutate_request_ids[-1]
                        if mutate_request_ids
                        else None
                    )
                    campaign.status = current.get("status")
                    campaign.budget_micros = current.get("budget_micros")
                    campaign.last_synced_at = utcnow()
                    campaign.manually_paused = action.action_type == "PAUSE"
                    readback.append(
                        {
                            "campaign_id": str(campaign.id),
                            **item.result,
                            "request_ids": list(
                                dict.fromkeys(
                                    [
                                        *validation_request_ids,
                                        *mutate_request_ids,
                                        *read_request_ids,
                                    ]
                                )
                            ),
                        }
                    )
            except RuleExecutionBlocked as exc:
                any_failed = True
                kill_switch_blocked = True
                for item in account_items:
                    if item.status != "SUCCEEDED":
                        item.status = "SKIPPED_KILL_SWITCH"
                        item.error_message = "GLOBAL_KILL_SWITCH_ACTIVE"
                if rule_evaluation:
                    rule_evaluation.status = "SKIPPED_KILL_SWITCH"
                    rule_evaluation.skip_reason = "GLOBAL_KILL_SWITCH_ACTIVE"
                    rule_evaluation.evaluation = {
                        **(rule_evaluation.evaluation or {}),
                        "phase": exc.phase,
                        "reason": "GLOBAL_KILL_SWITCH_ACTIVE",
                    }
            except Exception as exc:
                any_failed = True
                for item in account_items:
                    if item.status != "SUCCEEDED":
                        item.status = "FAILED"
                        item.error_message = (
                            f"{exc.code}: {exc}"
                            if isinstance(exc, GoogleAdsSafetyError)
                            else str(exc)
                        )
        action.request_ids = list(dict.fromkeys(all_request_ids))
        action.validation = {
            "ok": not any_failed,
            "validate_only": True,
            "execution_mode": "GOOGLE_TEST",
            "google_contacted": True,
            "request_ids": list(dict.fromkeys(validation_request_ids)),
        }
        action.readback = {"items": readback}
        action.status = (
            "SKIPPED_KILL_SWITCH"
            if kill_switch_blocked and not readback
            else "COMPLETED_WITH_ERRORS"
            if any_failed
            else "SUCCEEDED"
        )
        action.error_message = (
            "GLOBAL_KILL_SWITCH_ACTIVE"
            if action.status == "SKIPPED_KILL_SWITCH"
            else "Часть операций не выполнена"
            if any_failed
            else None
        )
        action.completed_at = utcnow()
        if rule_evaluation:
            rule = db.get(ControlCenterRule, rule_evaluation.rule_id)
            rule_evaluation.mutation_performed = bool(readback)
            if action.status == "SUCCEEDED":
                rule_evaluation.status = "MUTATED"
                rule_evaluation.skip_reason = None
                if rule:
                    rule.last_action_at = action.completed_at
                    rule.circuit_open_until = None
            elif action.status != "SKIPPED_KILL_SWITCH":
                rule_evaluation.status = "ACTION_FAILED"
                rule_evaluation.skip_reason = "GOOGLE_ACTION_FAILED"
                if rule:
                    _update_rule_circuit_breaker(db, rule, action.completed_at)
                    db.add(
                        Notification(
                            user_id=rule.created_by_id,
                            severity="ERROR",
                            title=f"Ошибка автоправила: {rule.name}",
                            message=action.error_message or "Действие Google Ads не выполнено",
                            entity_type="control_center_rule",
                            entity_id=str(rule.id),
                        )
                    )
        db.add(
            AuditLog(
                created_at=utcnow(),
                actor_user_id=action.requested_by_id,
                action="control_center.action.google_test.complete",
                entity_type="control_center_action_request",
                entity_id=action_id,
                summary={
                    "status": action.status,
                    "action_type": action.action_type,
                    "request_ids": action.request_ids,
                    "validation_request_ids": list(
                        dict.fromkeys(validation_request_ids)
                    ),
                    "mutate_request_ids": list(
                        dict.fromkeys(mutate_request_ids)
                    ),
                    "readback_verified": not any_failed,
                },
            )
        )
        db.commit()
        return {"ok": not any_failed, "status": action.status}


def _stop_rule_action_for_kill_switch(
    db,
    action: ControlCenterActionRequest,
    evaluation: ControlCenterRuleEvaluation,
    phase: str,
) -> None:
    action.status = "SKIPPED_KILL_SWITCH"
    action.completed_at = utcnow()
    action.error_message = "GLOBAL_KILL_SWITCH_ACTIVE"
    evaluation.status = "SKIPPED_KILL_SWITCH"
    evaluation.skip_reason = "GLOBAL_KILL_SWITCH_ACTIVE"
    evaluation.evaluation = {
        **(evaluation.evaluation or {}),
        "phase": phase,
        "reason": "GLOBAL_KILL_SWITCH_ACTIVE",
    }
    for item in db.scalars(
        select(ControlCenterActionItem).where(
            ControlCenterActionItem.action_request_id == action.id
        )
    ).all():
        item.status = "SKIPPED_KILL_SWITCH"
        item.error_message = "GLOBAL_KILL_SWITCH_ACTIVE"
    db.add(
        ControlCenterEvent(
            account_id=action.account_id,
            campaign_id=action.campaign_id,
            actor_user_id=action.requested_by_id,
            event_type="RULE_ACTION_SKIPPED",
            source="RULE_ENGINE",
            summary="Действие автоправила остановлено общим выключателем",
            details={
                "rule_id": str(evaluation.rule_id),
                "action_request_id": str(action.id),
                "phase": phase,
            },
            occurred_at=utcnow(),
        )
    )


def _update_rule_circuit_breaker(
    db,
    rule: ControlCenterRule,
    failed_at: datetime,
) -> None:
    safeguards = rule.safeguards or {}
    threshold = max(1, int(safeguards.get("circuit_failure_threshold", 3)))
    window_minutes = max(5, int(safeguards.get("circuit_window_minutes", 60)))
    open_minutes = max(5, int(safeguards.get("circuit_open_minutes", 30)))
    recent_failures = int(
        db.scalar(
            select(func.count(ControlCenterRuleEvaluation.id)).where(
                ControlCenterRuleEvaluation.rule_id == rule.id,
                ControlCenterRuleEvaluation.status == "ACTION_FAILED",
                ControlCenterRuleEvaluation.created_at
                >= failed_at - timedelta(minutes=window_minutes),
            )
        )
        or 0
    )
    if recent_failures + 1 >= threshold:
        rule.circuit_open_until = failed_at + timedelta(minutes=open_minutes)


def _result_error_message(result) -> str:
    return "; ".join(
        (
            f"{error.get('code')}: {error.get('message')}"
            if error.get("code")
            else str(error.get("message") or "Google Ads error")
        )
        for error in result.errors
    )


@celery_app.task(name="app.jobs.evaluate_control_center_rules")
def evaluate_control_center_rules() -> dict:
    with SessionLocal() as db:
        rules = list(
            db.scalars(
                select(ControlCenterRule).where(
                    ControlCenterRule.enabled.is_(True),
                    ControlCenterRule.mode.in_(["DRY_RUN", "LIVE"]),
                ).order_by(ControlCenterRule.priority, ControlCenterRule.name)
            ).all()
        )
        result = evaluate_rules(db, rules)
        db.commit()
        for action_request_id in result.action_request_ids:
            execute_control_center_action.delay(str(action_request_id))
        return result.payload()
