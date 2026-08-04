from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    AccountMetricDaily,
    AccountMonitoringState,
    AccountTag,
    ControlCenterCampaign,
    ControlCenterProblem,
    ControlCenterQuotaLedger,
    ControlCenterTag,
    CustomerAccount,
    GeoDefinition,
    GoogleConnection,
    MccAccount,
)

PROBLEM_GOOGLE_STATUSES = {
    "SUSPENDED",
    "CLOSED",
    "CANCELED",
    "CANCELLED",
    "NO_ACCESS",
    "SYNC_ERROR",
}
WORK_STATUS_LABELS = {
    "PREPARATION": "Подготовка",
    "READY": "Готов к работе",
    "WORKING": "В работе",
    "MANUAL_PAUSE": "Ручная пауза",
    "PROBLEM": "Проблема",
    "APPEAL": "Апелляция",
    "ARCHIVED": "Архив",
    "DO_NOT_USE": "Не использовать",
}
GOOGLE_STATUS_LABELS = {
    "ENABLED": "Активен",
    "ACTIVE": "Активен",
    "SUSPENDED": "Приостановлен",
    "CLOSED": "Закрыт",
    "CANCELED": "Отменён",
    "CANCELLED": "Отменён",
    "NO_ACCESS": "Нет доступа",
    "SYNC_ERROR": "Ошибка синхронизации",
    "UNKNOWN": "Неизвестен",
}
TEST_ACCOUNT_CLOSED_STATUSES = {"CLOSED", "CANCELED", "CANCELLED"}
PERIOD_DAYS = {"3d": 3, "7d": 7, "30d": 30}


def period_bounds(
    period: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[date, date]:
    today = datetime.now(UTC).date()
    if period == "today":
        return today, today
    if period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if period == "custom":
        if start_date is None or end_date is None:
            raise ValueError("Для произвольного периода нужны обе даты")
        if start_date > end_date:
            raise ValueError("Начальная дата не может быть позже конечной")
        if (end_date - start_date).days > 366:
            raise ValueError("Период не может быть длиннее 367 дней")
        return start_date, end_date
    days = PERIOD_DAYS.get(period, 7)
    return today - timedelta(days=days - 1), today


def tag_map_for_accounts(db: Session, account_ids: list[UUID]) -> dict[UUID, list[dict]]:
    result: dict[UUID, list[dict]] = defaultdict(list)
    if not account_ids:
        return result
    rows = db.execute(
        select(AccountTag.account_id, ControlCenterTag)
        .join(ControlCenterTag, ControlCenterTag.id == AccountTag.tag_id)
        .where(AccountTag.account_id.in_(account_ids))
        .order_by(ControlCenterTag.name)
    ).all()
    for account_id, tag in rows:
        result[account_id].append({"id": str(tag.id), "name": tag.name, "color": tag.color})
    return result


def monitoring_state_map(
    db: Session,
    account_ids: list[UUID],
    start_date: date,
    end_date: date,
    timezone_mode: str,
) -> dict[UUID, dict]:
    if not account_ids:
        return {}
    states = {
        row.account_id: row
        for row in db.scalars(select(AccountMonitoringState).where(AccountMonitoringState.account_id.in_(account_ids)))
    }
    daily_rows = db.execute(
        select(
            AccountMetricDaily.account_id,
            func.sum(AccountMetricDaily.impressions),
            func.sum(AccountMetricDaily.clicks),
            func.sum(AccountMetricDaily.cost_micros),
            func.sum(AccountMetricDaily.conversions),
            func.sum(AccountMetricDaily.all_conversions),
            func.sum(AccountMetricDaily.conversion_value),
            func.sum(AccountMetricDaily.registrations),
            func.sum(AccountMetricDaily.deposits),
            func.sum(AccountMetricDaily.registration_value),
            func.sum(AccountMetricDaily.deposit_value),
            func.bool_or(AccountMetricDaily.registration_data_available),
            func.bool_or(AccountMetricDaily.deposit_data_available),
            func.max(AccountMetricDaily.budget_micros),
            func.max(AccountMetricDaily.active_campaigns),
            func.max(AccountMetricDaily.disapproved_ads),
            func.max(AccountMetricDaily.observed_at),
            func.bool_or(AccountMetricDaily.boundary_precision != "EXACT"),
            func.max(AccountMetricDaily.data_source_mode),
        )
        .where(
            AccountMetricDaily.account_id.in_(account_ids),
            AccountMetricDaily.metric_date.between(start_date, end_date),
            AccountMetricDaily.timezone_mode == timezone_mode,
        )
        .group_by(AccountMetricDaily.account_id)
    ).all()
    daily = {
        row[0]: {
            "impressions": row[1],
            "clicks": row[2],
            "cost_micros": row[3],
            "conversions": row[4],
            "all_conversions": row[5],
            "conversion_value": row[6],
            "registrations": row[7],
            "deposits": row[8],
            "registration_value": row[9],
            "deposit_value": row[10],
            "registration_data_available": bool(row[11]),
            "deposit_data_available": bool(row[12]),
            "budget_micros": row[13],
            "active_campaigns": row[14],
            "disapproved_ads": row[15],
            "data_observed_at": row[16],
            "boundary_precision": "APPROXIMATE_30M" if row[17] else "EXACT",
            "data_source_mode": row[18],
        }
        for row in daily_rows
    }
    result: dict[UUID, dict] = {}
    for account_id in account_ids:
        state = states.get(account_id)
        payload = {
            "impressions": state.impressions if state else None,
            "clicks": state.clicks if state else None,
            "cost_micros": state.cost_micros if state else None,
            "conversions": state.conversions if state else None,
            "all_conversions": state.all_conversions if state else None,
            "conversion_value": state.conversion_value if state else None,
            "registrations": state.registrations if state else None,
            "deposits": state.deposits if state else None,
            "registration_value": state.registration_value if state else None,
            "deposit_value": state.deposit_value if state else None,
            "registration_data_available": (state.registration_data_available if state else False),
            "deposit_data_available": (state.deposit_data_available if state else False),
            "budget_micros": state.budget_micros if state else None,
            "active_campaigns": state.active_campaigns if state else None,
            "disapproved_ads": state.disapproved_ads if state else None,
            "policy_issues": state.policy_issues if state else None,
            "freshness": state.freshness if state else "NO_DATA",
            "data_observed_at": state.data_observed_at if state else None,
            "boundary_precision": state.boundary_precision if state else "EXACT",
            "last_error_code": state.last_error_code if state else None,
            "last_request_id": state.last_request_id if state else None,
            "data_source_mode": state.data_source_mode if state else "UNKNOWN",
        }
        if account_id in daily:
            payload.update(daily[account_id])
        result[account_id] = with_derived_metrics(payload)
    return result


def with_derived_metrics(metrics: dict) -> dict:
    impressions = metrics.get("impressions")
    clicks = metrics.get("clicks")
    cost_micros = metrics.get("cost_micros")
    conversions = metrics.get("conversions")
    registrations = metrics.get("registrations") if metrics.get("registration_data_available") else None
    deposits = metrics.get("deposits") if metrics.get("deposit_data_available") else None
    metrics["registrations"] = registrations
    metrics["deposits"] = deposits
    metrics["ctr"] = (
        (float(clicks) / float(impressions)) * 100 if impressions not in (None, 0) and clicks is not None else None
    )
    metrics["cpc_micros"] = (
        int(Decimal(cost_micros) / Decimal(clicks)) if clicks not in (None, 0) and cost_micros is not None else None
    )
    metrics["cost_per_conversion_micros"] = (
        int(Decimal(cost_micros) / Decimal(str(conversions)))
        if conversions not in (None, 0) and cost_micros is not None
        else None
    )
    metrics["cpa_registration_micros"] = (
        int(Decimal(cost_micros) / Decimal(str(registrations)))
        if registrations not in (None, 0) and cost_micros is not None
        else None
    )
    metrics["cpa_deposit_micros"] = (
        int(Decimal(cost_micros) / Decimal(str(deposits)))
        if deposits not in (None, 0) and cost_micros is not None
        else None
    )
    metrics["registration_rate"] = (
        float(Decimal(str(registrations)) * Decimal(100) / Decimal(clicks))
        if registrations is not None and clicks not in (None, 0)
        else None
    )
    metrics["registration_to_deposit_rate"] = (
        float(Decimal(str(deposits)) * Decimal(100) / Decimal(str(registrations)))
        if deposits is not None and registrations not in (None, 0)
        else None
    )
    conversion_value = metrics.get("conversion_value")
    metrics["roas"] = (
        float(Decimal(str(conversion_value)) / (Decimal(cost_micros) / Decimal(1_000_000)))
        if conversion_value is not None and cost_micros not in (None, 0)
        else None
    )
    return metrics


def currency_totals(
    accounts: list[CustomerAccount],
    states: list[AccountMonitoringState],
) -> dict:
    account_currency = {account.id: (account.currency_code or "UNKNOWN").upper() for account in accounts}
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"cost_micros": 0, "accounts_with_data": 0})
    for state in states:
        if state.cost_micros is None:
            continue
        currency_code = account_currency.get(state.account_id, "UNKNOWN")
        grouped[currency_code]["cost_micros"] += int(state.cost_micros)
        grouped[currency_code]["accounts_with_data"] += 1
    by_currency = [
        {
            "currency_code": currency_code,
            "cost_micros": values["cost_micros"],
            "accounts_with_data": values["accounts_with_data"],
        }
        for currency_code, values in sorted(grouped.items())
    ]
    single_currency = len(by_currency) == 1
    return {
        "cost_micros": by_currency[0]["cost_micros"] if single_currency else None,
        "currency_code": by_currency[0]["currency_code"] if single_currency else None,
        "by_currency": by_currency,
        "mixed_currencies": len(by_currency) > 1,
        "accounts_with_data": sum(item["accounts_with_data"] for item in by_currency),
    }


def account_payload(
    account: CustomerAccount,
    connection_name: str | None,
    tags: list[dict],
    metrics: dict,
    active_problem_count: int = 0,
    *,
    mcc: MccAccount | None = None,
    geo: GeoDefinition | None = None,
    access_path_count: int = 0,
) -> dict:
    google_status = (account.status or "UNKNOWN").upper()
    benign_test_closure = bool(account.is_test_account and google_status in TEST_ACCOUNT_CLOSED_STATUSES)
    has_problem = bool(
        (google_status in PROBLEM_GOOGLE_STATUSES and not benign_test_closure)
        or account.sync_error
        or active_problem_count
        or account.detached_at
    )
    return {
        "id": str(account.id),
        "connection_id": str(account.connection_id),
        "connection_name": connection_name,
        "customer_id": account.customer_id,
        "manager_customer_id": account.manager_customer_id,
        "parent_customer_id": account.parent_customer_id,
        "primary_mcc_id": (
            str(getattr(account, "primary_mcc_id", None)) if getattr(account, "primary_mcc_id", None) else None
        ),
        "mcc_customer_id": mcc.customer_id if mcc else account.manager_customer_id,
        "mcc_name": mcc.descriptive_name if mcc else None,
        "hierarchy_level": account.hierarchy_level,
        "descriptive_name": account.descriptive_name,
        "local_name": account.local_name,
        "display_name": account.local_name or account.descriptive_name or account.customer_id,
        "currency_code": account.currency_code,
        "time_zone": account.time_zone,
        "geo": (
            {
                "id": str(geo.id),
                "iso_code": geo.iso_code,
                "display_name": geo.display_name,
                "color": geo.color,
                "short_label": geo.short_label,
            }
            if geo
            else None
        ),
        "geo_id": str(geo.id) if geo else None,
        "geo_source": ("ACCOUNT_OVERRIDE" if getattr(account, "geo_override_id", None) else "MCC"),
        "geo_override_id": (
            str(getattr(account, "geo_override_id", None)) if getattr(account, "geo_override_id", None) else None
        ),
        "access_path_count": access_path_count,
        "google_status": google_status,
        "google_status_label": (
            "Тестовый аккаунт — показ рекламы отключён Google"
            if benign_test_closure
            else GOOGLE_STATUS_LABELS.get(google_status, "Неизвестен")
        ),
        "work_status": account.work_status,
        "work_status_label": WORK_STATUS_LABELS.get(account.work_status, account.work_status),
        "current_note": account.current_note,
        "note_updated_at": account.note_updated_at,
        "note_updated_by_id": str(account.note_updated_by_id) if account.note_updated_by_id else None,
        "pinned_note": getattr(account, "pinned_note", None),
        "pinned_note_updated_at": getattr(account, "pinned_note_updated_at", None),
        "pinned_note_updated_by_id": (
            str(account.pinned_note_updated_by_id) if getattr(account, "pinned_note_updated_by_id", None) else None
        ),
        "tags": tags,
        "is_pinned": account.is_pinned,
        "is_test_account": account.is_test_account,
        "is_hidden": account.is_hidden,
        "is_detached": account.detached_at is not None,
        "detached_at": account.detached_at,
        "last_sync_attempt_at": account.last_sync_attempt_at,
        "last_sync_success_at": account.last_sync_success_at,
        "sync_error": account.sync_error,
        "verification_status": account.verification_status,
        "verification_deadline": account.verification_deadline,
        "verification_action_url": account.verification_action_url,
        "verification_checked_at": account.verification_checked_at,
        "has_problem": has_problem,
        "active_problem_count": active_problem_count,
        "activity_status": activity_status_for_account(account, metrics),
        "activity_period_days": getattr(account, "activity_period_days", 7),
        "metrics": {
            **metrics,
            "no_data_reason": (
                "Нет данных: тестовые аккаунты не показывают рекламу"
                if account.is_test_account
                and metrics.get("data_source_mode") == "GOOGLE_TEST"
                and metrics.get("cost_micros") is None
                else None
            ),
        },
        "updated_at": account.updated_at,
    }


def activity_status_for_account(account: CustomerAccount, metrics: dict) -> str:
    google_status = (account.status or "UNKNOWN").upper()
    if account.detached_at is not None or getattr(account, "link_status", None) == "DETACHED":
        return "NO_ACCESS"
    if google_status in {"SUSPENDED", "CLOSED", "CANCELED", "CANCELLED"}:
        if not (account.is_test_account and google_status in TEST_ACCOUNT_CLOSED_STATUSES):
            return "SUSPENDED"
    if metrics.get("freshness") in {"STALE", "ERROR"}:
        return "STALE"
    active_campaigns = metrics.get("active_campaigns")
    cost_micros = metrics.get("cost_micros")
    if active_campaigns == 0:
        return "NO_ACTIVE_CAMPAIGNS"
    if active_campaigns and cost_micros == 0:
        return "ENABLED_NO_SPEND"
    if cost_micros is not None and cost_micros > 0:
        return "SPENDING"
    if cost_micros == 0:
        return "NOT_SPENDING"
    return "NO_DATA"


def campaign_payload(campaign: ControlCenterCampaign, account: CustomerAccount | None) -> dict:
    test_account_no_delivery = bool(account and account.is_test_account)
    metrics = with_derived_metrics(
        {
            "impressions": None if test_account_no_delivery else campaign.impressions,
            "clicks": None if test_account_no_delivery else campaign.clicks,
            "cost_micros": None if test_account_no_delivery else campaign.cost_micros,
            "conversions": None if test_account_no_delivery else campaign.conversions,
            "all_conversions": (None if test_account_no_delivery else getattr(campaign, "all_conversions", None)),
            "registrations": (None if test_account_no_delivery else getattr(campaign, "registrations", None)),
            "deposits": (None if test_account_no_delivery else getattr(campaign, "deposits", None)),
            "registration_data_available": (
                False if test_account_no_delivery else getattr(campaign, "registration_data_available", False)
            ),
            "deposit_data_available": (
                False if test_account_no_delivery else getattr(campaign, "deposit_data_available", False)
            ),
            "conversion_value": None if test_account_no_delivery else campaign.conversion_value,
        }
    )
    metrics["data_source_mode"] = "GOOGLE_TEST" if test_account_no_delivery else "UNKNOWN"
    metrics["no_data_reason"] = (
        "Нет данных: тестовые аккаунты не показывают рекламу" if test_account_no_delivery else None
    )
    return {
        "id": str(campaign.id),
        "account_id": str(campaign.account_id),
        "customer_id": account.customer_id if account else None,
        "account_name": (account.local_name or account.descriptive_name or account.customer_id if account else None),
        "resource_name": campaign.resource_name,
        "campaign_id": campaign.campaign_id,
        "name": campaign.name,
        "source": campaign.source,
        "channel_type": campaign.channel_type,
        "channel_subtype": campaign.channel_subtype,
        "status": campaign.status,
        "primary_status": campaign.primary_status,
        "primary_status_reasons": campaign.primary_status_reasons,
        "budget_resource_name": campaign.budget_resource_name,
        "budget_micros": campaign.budget_micros,
        "budget_shared": campaign.budget_shared,
        "bidding_strategy_type": getattr(campaign, "bidding_strategy_type", None),
        "currency_code": account.currency_code if account else None,
        "metrics": metrics,
        "policy_issues": campaign.policy_issues,
        "policy_status": getattr(campaign, "policy_status", None),
        "last_change_at": getattr(campaign, "last_change_at", None),
        "manually_paused": campaign.manually_paused,
        "last_synced_at": campaign.last_synced_at,
        "sync_error": campaign.sync_error,
    }


def quick_filter_counts(db: Session, accounts: list[CustomerAccount]) -> dict[str, int]:
    if not accounts:
        return {key: 0 for key in ("all", "working", "issues", "verification", "paused", "archive")}
    ids = [account.id for account in accounts]
    problem_ids = set(
        db.scalars(
            select(ControlCenterProblem.account_id).where(
                ControlCenterProblem.account_id.in_(ids),
                ControlCenterProblem.state != "RESOLVED",
            )
        )
    )
    return {
        "all": len(accounts),
        "working": sum(account.work_status == "WORKING" for account in accounts),
        "issues": sum(
            (
                (account.status or "UNKNOWN").upper() in PROBLEM_GOOGLE_STATUSES
                and not (
                    account.is_test_account and (account.status or "UNKNOWN").upper() in TEST_ACCOUNT_CLOSED_STATUSES
                )
            )
            or bool(account.sync_error)
            or account.id in problem_ids
            or account.detached_at is not None
            for account in accounts
        ),
        "verification": sum(
            (account.verification_status or "").upper() in {"REQUIRED", "PENDING", "ACTION_REQUIRED"}
            for account in accounts
        ),
        "paused": sum(account.work_status == "MANUAL_PAUSE" for account in accounts),
        "archive": sum(account.work_status == "ARCHIVED" for account in accounts),
    }


def quota_summary(db: Session) -> dict:
    today = datetime.now(UTC).date()
    rows = db.execute(
        select(
            ControlCenterQuotaLedger.connection_id,
            func.sum(ControlCenterQuotaLedger.operation_count),
            func.sum(
                case(
                    (
                        ControlCenterQuotaLedger.succeeded.is_(False),
                        ControlCenterQuotaLedger.operation_count,
                    ),
                    else_=0,
                )
            ),
        )
        .where(ControlCenterQuotaLedger.operation_date == today)
        .group_by(ControlCenterQuotaLedger.connection_id)
    ).all()
    connections = {connection.id: connection.name for connection in db.scalars(select(GoogleConnection)).all()}
    used = sum(int(row[1] or 0) for row in rows)
    failed = sum(int(row[2] or 0) for row in rows)
    elapsed_minutes = max(1, datetime.now(UTC).hour * 60 + datetime.now(UTC).minute)
    forecast = min(
        settings.control_center_daily_operation_limit,
        round(used * 1440 / elapsed_minutes),
    )
    reserve = round(settings.control_center_daily_operation_limit * 0.2)
    internal_remaining = max(0, settings.control_center_daily_operation_limit - reserve - used)
    return {
        "used_today": used,
        "forecast_end_of_day": forecast,
        "internal_remaining": internal_remaining,
        "manual_reserve": reserve,
        "failed_operations": failed,
        "daily_planning_limit": settings.control_center_daily_operation_limit,
        "background_throttled": used >= settings.control_center_daily_operation_limit - reserve,
        "disclaimer": "Внутренняя оценка программы, а не официальный остаток Google.",
        "by_connection": [
            {
                "connection_id": str(row[0]) if row[0] else None,
                "connection_name": connections.get(row[0], "Неизвестное подключение"),
                "operations": int(row[1] or 0),
            }
            for row in rows
        ],
    }


def estimate_signature(scope: str, account_ids: list[UUID], estimated_operations: int) -> str:
    payload = {
        "scope": scope,
        "account_ids": sorted(str(item) for item in account_ids),
        "estimated_operations": estimated_operations,
        "bucket": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def matches_rule_condition(payload: dict[str, Any], condition: dict[str, Any]) -> bool:
    field = str(condition.get("field") or "")
    operator = str(condition.get("operator") or "eq").lower()
    expected = condition.get("value")
    actual: Any = payload
    for part in field.split("."):
        if not isinstance(actual, dict):
            actual = None
            break
        actual = actual.get(part)
    if operator == "is_null":
        return actual is None
    if operator == "not_null":
        return actual is not None
    if actual is None:
        return False
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "gt":
        return float(actual) > float(expected)
    if operator == "gte":
        return float(actual) >= float(expected)
    if operator == "lt":
        return float(actual) < float(expected)
    if operator == "lte":
        return float(actual) <= float(expected)
    if operator == "contains":
        return str(expected).casefold() in str(actual).casefold()
    if operator == "in":
        return actual in (expected or [])
    return False
