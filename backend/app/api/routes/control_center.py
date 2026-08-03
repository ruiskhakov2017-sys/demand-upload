from __future__ import annotations

import csv
import hashlib
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from openpyxl import Workbook
from sqlalchemy import and_, case, desc, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf, require_role
from app.control_center.query import (
    apply_account_filters,
    group_account_rows,
    sort_account_rows,
    sort_groups,
)
from app.control_center.rule_engine import evaluate_rules
from app.control_center.rules import (
    RULE_KILL_SWITCH_KEY,
    rule_kill_switch_active,
)
from app.control_center.schemas import (
    AccountPatchIn,
    ActionConfirmIn,
    ActionPreviewIn,
    BulkWorkStatusIn,
    ProblemPatchIn,
    RuleCreateIn,
    RuleLiveModeIn,
    RulePatchIn,
    SavedViewIn,
    SavedViewPatchIn,
    SyncEstimateIn,
    SyncStartIn,
    TagCreateIn,
)
from app.control_center.service import (
    PROBLEM_GOOGLE_STATUSES,
    TEST_ACCOUNT_CLOSED_STATUSES,
    account_payload,
    campaign_payload,
    currency_totals,
    estimate_signature,
    monitoring_state_map,
    period_bounds,
    quick_filter_counts,
    quota_summary,
    tag_map_for_accounts,
)
from app.core.database import get_db
from app.core.security import generate_token, hash_token, utcnow
from app.db.models import (
    AccountMetricDaily,
    AccountMonitoringState,
    AccountNoteHistory,
    AccountTag,
    AccountTagHistory,
    ApplicationSetting,
    ControlCenterActionItem,
    ControlCenterActionRequest,
    ControlCenterCampaign,
    ControlCenterEvent,
    ControlCenterProblem,
    ControlCenterRule,
    ControlCenterRuleEvaluation,
    ControlCenterSavedView,
    ControlCenterSyncItem,
    ControlCenterSyncRun,
    ControlCenterTag,
    CustomerAccount,
    GeoDefinition,
    GoogleAccountAccessPath,
    GoogleConnection,
    Job,
    JobStatus,
    MccAccount,
    ModerationRecord,
    User,
    UserRole,
)
from app.domain.audit import record_audit
from app.google_ads.execution_guard import refresh_google_test_target
from app.google_ads.safety import (
    GoogleAdsSafetyError,
    require_execution_mode_for_connection,
)
from app.google_ads.service import build_google_ads_adapter, is_google_connection_active

router = APIRouter(prefix="/control-center", tags=["control-center"])

ALLOWED_SORTS = {
    "name": func.coalesce(
        CustomerAccount.local_name,
        CustomerAccount.descriptive_name,
        CustomerAccount.customer_id,
    ),
    "customer_id": CustomerAccount.customer_id,
    "work_status": CustomerAccount.work_status,
    "google_status": CustomerAccount.status,
    "currency_code": CustomerAccount.currency_code,
    "last_sync_success_at": CustomerAccount.last_sync_success_at,
    "updated_at": CustomerAccount.updated_at,
}

CAMPAIGN_CPA_REGISTRATION = case(
    (
        ControlCenterCampaign.registrations > 0,
        ControlCenterCampaign.cost_micros
        / ControlCenterCampaign.registrations,
    ),
    else_=None,
)
CAMPAIGN_SORTS = {
    "name": ControlCenterCampaign.name,
    "status": ControlCenterCampaign.status,
    "budget": ControlCenterCampaign.budget_micros,
    "cost": ControlCenterCampaign.cost_micros,
    "impressions": ControlCenterCampaign.impressions,
    "clicks": ControlCenterCampaign.clicks,
    "registrations": ControlCenterCampaign.registrations,
    "deposits": ControlCenterCampaign.deposits,
    "cpa_registration": CAMPAIGN_CPA_REGISTRATION,
    "last_change": ControlCenterCampaign.last_change_at,
    "last_sync": ControlCenterCampaign.last_synced_at,
}

ACCOUNT_EXPORT_COLUMNS = {
    "group": ("Группа", "group_label"),
    "local_name": ("Локальное название", "local_name"),
    "google_name": ("Название Google", "descriptive_name"),
    "customer_id": ("Customer ID", "customer_id"),
    "geo": ("GEO", "geo.display_name"),
    "mcc": ("Текущий MCC", "mcc_name"),
    "connection": ("Подключение", "connection_name"),
    "work_status": ("Рабочий статус", "work_status_label"),
    "activity_status": ("Фактическая активность", "activity_status"),
    "google_status": ("Статус Google", "google_status_label"),
    "problem": ("Есть проблема", "has_problem"),
    "problem_count": ("Количество проблем", "active_problem_count"),
    "currency": ("Валюта", "currency_code"),
    "time_zone": ("Часовой пояс", "time_zone"),
    "cost": ("Расход", "metrics.cost_micros"),
    "budget": ("Бюджет", "metrics.budget_micros"),
    "impressions": ("Показы", "metrics.impressions"),
    "clicks": ("Клики", "metrics.clicks"),
    "ctr": ("CTR, %", "metrics.ctr"),
    "cpc": ("CPC", "metrics.cpc_micros"),
    "all_conversions": ("Все конверсии", "metrics.all_conversions"),
    "registrations": ("Регистрации", "metrics.registrations"),
    "deposits": ("Депозиты", "metrics.deposits"),
    "cpa_registration": ("CPA регистрации", "metrics.cpa_registration_micros"),
    "cpa_deposit": ("CPA депозита", "metrics.cpa_deposit_micros"),
    "registration_rate": ("Registration rate, %", "metrics.registration_rate"),
    "registration_to_deposit_rate": (
        "Registration-to-deposit rate, %",
        "metrics.registration_to_deposit_rate",
    ),
    "conversion_value": ("Ценность конверсий", "metrics.conversion_value"),
    "roas": ("ROAS", "metrics.roas"),
    "active_campaigns": ("Активные кампании", "metrics.active_campaigns"),
    "disapproved_ads": ("Отклонённые объявления", "metrics.disapproved_ads"),
    "policy": ("Проблемы модерации", "metrics.policy_issues"),
    "verification": ("Верификация", "verification_status"),
    "last_error": ("Последняя ошибка", "sync_error"),
    "last_sync": ("Последняя синхронизация", "last_sync_success_at"),
    "freshness": ("Свежесть данных", "metrics.freshness"),
    "note": ("Заметка", "current_note"),
    "tags": ("Теги", "tags"),
    "generated_at": ("Сформировано UTC", "generated_at"),
}
DEFAULT_ACCOUNT_EXPORT_COLUMNS = [
    "local_name",
    "google_name",
    "customer_id",
    "geo",
    "mcc",
    "work_status",
    "activity_status",
    "google_status",
    "problem",
    "problem_count",
    "currency",
    "cost",
    "budget",
    "impressions",
    "clicks",
    "ctr",
    "cpc",
    "all_conversions",
    "registrations",
    "deposits",
    "cpa_registration",
    "cpa_deposit",
    "registration_rate",
    "registration_to_deposit_rate",
    "conversion_value",
    "roas",
    "active_campaigns",
    "disapproved_ads",
    "last_sync",
    "note",
    "tags",
    "generated_at",
]


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    accounts = list(db.scalars(select(CustomerAccount)).all())
    states = list(db.scalars(select(AccountMonitoringState)).all())
    available_states = [state for state in states if state.cost_micros is not None]
    money_totals = currency_totals(accounts, states)
    counts = quick_filter_counts(db, accounts)
    active_problems = int(
        db.scalar(
            select(func.count()).select_from(ControlCenterProblem).where(ControlCenterProblem.state != "RESOLVED")
        )
        or 0
    )
    campaigns = int(db.scalar(select(func.count()).select_from(ControlCenterCampaign)) or 0)
    default_view = db.scalar(
        select(ControlCenterSavedView).where(
            ControlCenterSavedView.owner_user_id == user.id,
            ControlCenterSavedView.entity_level == "ACCOUNT",
            ControlCenterSavedView.is_default.is_(True),
        )
    )
    return {
        "accounts": counts,
        "campaigns": {
            "total": campaigns,
            "enabled": int(
                db.scalar(
                    select(func.count())
                    .select_from(ControlCenterCampaign)
                    .where(ControlCenterCampaign.status == "ENABLED")
                )
                or 0
            ),
        },
        "problems": {"active": active_problems},
        "metrics": {
            **money_totals,
            "clicks": (sum(state.clicks or 0 for state in available_states) if available_states else None),
            "conversions": (sum(state.conversions or 0 for state in available_states) if available_states else None),
        },
        "quota": quota_summary(db),
        "default_view": saved_view_payload(default_view) if default_view else None,
        "refreshed_at": utcnow(),
    }


@router.get("/accounts")
def list_control_center_accounts(
    quick_filter: str = Query(default="working"),
    search: str | None = Query(default=None, max_length=500),
    work_status: str | None = None,
    activity_status: str | None = None,
    google_status: str | None = None,
    connection_id: UUID | None = None,
    geo_id: UUID | None = None,
    mcc_id: UUID | None = None,
    currency: str | None = None,
    tag_id: UUID | None = None,
    has_problems: bool | None = None,
    problem_type: str | None = None,
    note: str | None = Query(default=None, max_length=500),
    last_sync_before: datetime | None = None,
    last_sync_after: datetime | None = None,
    period: str = "7d",
    timezone_mode: str = "ACCOUNT",
    start_date: str | None = None,
    end_date: str | None = None,
    sort: str = "name",
    direction: str = "asc",
    grouping: str = Query(default="none", pattern="^(none|geo|mcc|geo_mcc)$"),
    cost_min: int | None = Query(default=None, ge=0),
    cost_max: int | None = Query(default=None, ge=0),
    registrations_min: float | None = Query(default=None, ge=0),
    registrations_max: float | None = Query(default=None, ge=0),
    deposits_min: float | None = Query(default=None, ge=0),
    deposits_max: float | None = Query(default=None, ge=0),
    deposits_eq: float | None = Query(default=None, ge=0),
    cpa_min: int | None = Query(default=None, ge=0),
    cpa_max: int | None = Query(default=None, ge=0),
    active_campaigns_min: int | None = Query(default=None, ge=0),
    disapproved_ads_min: int | None = Query(default=None, ge=0),
    registrations_without_deposits: bool = False,
    limit: int = Query(default=100, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    date_start, date_end = _parse_period(period, start_date, end_date)
    base = select(CustomerAccount)
    conditions = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        tagged_accounts = (
            select(AccountTag.account_id)
            .join(ControlCenterTag, ControlCenterTag.id == AccountTag.tag_id)
            .where(ControlCenterTag.name.ilike(term))
        )
        conditions.append(
            or_(
                CustomerAccount.local_name.ilike(term),
                CustomerAccount.descriptive_name.ilike(term),
                CustomerAccount.customer_id.ilike(term),
                CustomerAccount.current_note.ilike(term),
                CustomerAccount.id.in_(tagged_accounts),
            )
        )
    if work_status:
        normalized_work_status = work_status.upper()
        if normalized_work_status == "NOT_WORKING":
            conditions.append(CustomerAccount.work_status != "WORKING")
        else:
            conditions.append(CustomerAccount.work_status == normalized_work_status)
    if google_status:
        conditions.append(func.upper(CustomerAccount.status) == google_status.upper())
    if connection_id:
        conditions.append(CustomerAccount.connection_id == connection_id)
    if geo_id:
        conditions.append(
            or_(
                CustomerAccount.geo_override_id == geo_id,
                and_(
                    CustomerAccount.geo_override_id.is_(None),
                    CustomerAccount.geo_id == geo_id,
                ),
            )
        )
    if mcc_id:
        conditions.append(CustomerAccount.primary_mcc_id == mcc_id)
    if currency:
        conditions.append(func.upper(CustomerAccount.currency_code) == currency.upper())
    if tag_id:
        conditions.append(CustomerAccount.id.in_(select(AccountTag.account_id).where(AccountTag.tag_id == tag_id)))
    if note and note.strip():
        conditions.append(CustomerAccount.current_note.ilike(f"%{note.strip()}%"))
    if last_sync_before:
        conditions.append(CustomerAccount.last_sync_success_at < last_sync_before)
    if last_sync_after:
        conditions.append(CustomerAccount.last_sync_success_at >= last_sync_after)
    if conditions:
        base = base.where(and_(*conditions))
    base_accounts = list(db.scalars(base).all())
    counts = quick_filter_counts(db, base_accounts)
    filtered = _apply_quick_filter(base, quick_filter)
    accounts = list(db.scalars(filtered).all())
    account_ids = [account.id for account in accounts]
    tags = tag_map_for_accounts(db, account_ids)
    metrics = monitoring_state_map(db, account_ids, date_start, date_end, timezone_mode.upper())
    connections = {
        connection.id: connection.name
        for connection in db.scalars(
            select(GoogleConnection).where(GoogleConnection.id.in_([account.connection_id for account in accounts]))
        ).all()
    }
    mcc_by_id, geo_by_id, path_counts = _account_context_maps(db, accounts)
    problem_rows = list(
        db.scalars(
            select(ControlCenterProblem).where(
                ControlCenterProblem.account_id.in_(account_ids),
                ControlCenterProblem.state != "RESOLVED",
            )
        ).all()
    )
    problem_counts: dict[UUID, int] = {}
    problem_types: dict[UUID, set[str]] = {}
    for problem in problem_rows:
        if problem.account_id is None:
            continue
        problem_counts[problem.account_id] = problem_counts.get(problem.account_id, 0) + 1
        problem_types.setdefault(problem.account_id, set()).add(problem.problem_type)
    rows = []
    for account in accounts:
        row = account_payload(
            account,
            connections.get(account.connection_id),
            tags.get(account.id, []),
            metrics.get(account.id, {}),
            problem_counts.get(account.id, 0),
            mcc=mcc_by_id.get(account.primary_mcc_id),
            geo=geo_by_id.get(account.geo_override_id or account.geo_id),
            access_path_count=path_counts.get(account.id, 0),
        )
        row["problem_types"] = sorted(problem_types.get(account.id, set()))
        rows.append(row)
    numeric_filters = {
        "cost_min": cost_min,
        "cost_max": cost_max,
        "registrations_min": registrations_min,
        "registrations_max": registrations_max,
        "deposits_min": deposits_min,
        "deposits_max": deposits_max,
        "deposits_eq": deposits_eq,
        "cpa_min": cpa_min,
        "cpa_max": cpa_max,
        "active_campaigns_min": active_campaigns_min,
        "disapproved_ads_min": disapproved_ads_min,
        "activity_status": activity_status,
        "has_problems": has_problems,
        "problem_type": problem_type,
        "registrations_without_deposits": registrations_without_deposits,
    }
    rows = apply_account_filters(rows, numeric_filters)
    sort_fields = [item.strip() for item in sort.split(",") if item.strip()]
    directions = [item.strip() for item in direction.split(",") if item.strip()]
    rows = sort_account_rows(rows, sort_fields, directions)
    total = len(rows)
    groups = group_account_rows(rows, grouping)
    if groups:
        groups = sort_groups(groups, sort_fields, directions)
    page_rows = rows[offset : offset + limit]
    return {
        "items": page_rows,
        "groups": groups,
        "grouping": grouping,
        "total": total,
        "counts": counts,
        "period": {
            "start_date": date_start,
            "end_date": date_end,
            "timezone_mode": timezone_mode.upper(),
        },
        "sort": [
            {
                "field": field,
                "direction": (
                    directions[index] if index < len(directions) else directions[-1] if directions else "asc"
                ),
            }
            for index, field in enumerate(sort_fields or ["name"])
        ],
        "filters": {
            "quick_filter": quick_filter,
            "search": search,
            "work_status": work_status,
            "activity_status": activity_status,
            "google_status": google_status,
            "connection_id": str(connection_id) if connection_id else None,
            "geo_id": str(geo_id) if geo_id else None,
            "mcc_id": str(mcc_id) if mcc_id else None,
            "currency": currency,
            "tag_id": str(tag_id) if tag_id else None,
            "has_problems": has_problems,
            "problem_type": problem_type,
            "note": note,
            **numeric_filters,
        },
        "limit": limit,
        "offset": offset,
    }


@router.get("/accounts/export")
def export_control_center_accounts(
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    quick_filter: str = "working",
    search: str | None = Query(default=None, max_length=500),
    work_status: str | None = None,
    activity_status: str | None = None,
    google_status: str | None = None,
    connection_id: UUID | None = None,
    geo_id: UUID | None = None,
    mcc_id: UUID | None = None,
    currency: str | None = None,
    tag_id: UUID | None = None,
    has_problems: bool | None = None,
    problem_type: str | None = None,
    note: str | None = Query(default=None, max_length=500),
    last_sync_before: datetime | None = None,
    last_sync_after: datetime | None = None,
    period: str = "7d",
    timezone_mode: str = "ACCOUNT",
    start_date: str | None = None,
    end_date: str | None = None,
    sort: str = "name",
    direction: str = "asc",
    grouping: str = Query(default="none", pattern="^(none|geo|mcc|geo_mcc)$"),
    cost_min: int | None = Query(default=None, ge=0),
    cost_max: int | None = Query(default=None, ge=0),
    registrations_min: float | None = Query(default=None, ge=0),
    registrations_max: float | None = Query(default=None, ge=0),
    deposits_min: float | None = Query(default=None, ge=0),
    deposits_max: float | None = Query(default=None, ge=0),
    deposits_eq: float | None = Query(default=None, ge=0),
    cpa_min: int | None = Query(default=None, ge=0),
    cpa_max: int | None = Query(default=None, ge=0),
    active_campaigns_min: int | None = Query(default=None, ge=0),
    disapproved_ads_min: int | None = Query(default=None, ge=0),
    registrations_without_deposits: bool = False,
    columns: str | None = Query(default=None, max_length=2_000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    result = list_control_center_accounts(
        quick_filter=quick_filter,
        search=search,
        work_status=work_status,
        activity_status=activity_status,
        google_status=google_status,
        connection_id=connection_id,
        geo_id=geo_id,
        mcc_id=mcc_id,
        currency=currency,
        tag_id=tag_id,
        has_problems=has_problems,
        problem_type=problem_type,
        note=note,
        last_sync_before=last_sync_before,
        last_sync_after=last_sync_after,
        period=period,
        timezone_mode=timezone_mode,
        start_date=start_date,
        end_date=end_date,
        sort=sort,
        direction=direction,
        grouping=grouping,
        cost_min=cost_min,
        cost_max=cost_max,
        registrations_min=registrations_min,
        registrations_max=registrations_max,
        deposits_min=deposits_min,
        deposits_max=deposits_max,
        deposits_eq=deposits_eq,
        cpa_min=cpa_min,
        cpa_max=cpa_max,
        active_campaigns_min=active_campaigns_min,
        disapproved_ads_min=disapproved_ads_min,
        registrations_without_deposits=registrations_without_deposits,
        limit=5000,
        offset=0,
        db=db,
        user=user,
    )
    selected_columns = (
        [item.strip() for item in columns.split(",") if item.strip()]
        if columns
        else list(DEFAULT_ACCOUNT_EXPORT_COLUMNS)
    )
    invalid_columns = sorted(set(selected_columns) - set(ACCOUNT_EXPORT_COLUMNS))
    if invalid_columns:
        raise HTTPException(
            status_code=422,
            detail="Неизвестные колонки экспорта: " + ", ".join(invalid_columns),
        )
    if grouping != "none" and "group" not in selected_columns:
        selected_columns.insert(0, "group")
    generated_at = utcnow()
    export_items: list[dict] = []
    if grouping == "none":
        export_items = list(result["items"])
    else:
        for group in result["groups"]:
            for item in group["items"]:
                export_items.append({**item, "group_label": group["label"]})
    headers = [ACCOUNT_EXPORT_COLUMNS[column][0] for column in selected_columns]
    rows = [
        [
            _account_export_value(
                {
                    **item,
                    "generated_at": generated_at,
                },
                ACCOUNT_EXPORT_COLUMNS[column][1],
                column,
            )
            for column in selected_columns
        ]
        for item in export_items
    ]
    if format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Аккаунты"
        sheet.append(headers)
        for row in rows:
            sheet.append(row)
        metadata = workbook.create_sheet("Параметры")
        metadata.append(["Сформировано UTC", generated_at.isoformat()])
        metadata.append(["Период", f"{result['period']['start_date']} — {result['period']['end_date']}"])
        metadata.append(["Часовой пояс данных", result["period"]["timezone_mode"]])
        metadata.append(["Группировка", grouping])
        metadata.append(["Сортировка", f"{sort} / {direction}"])
        metadata.append(["Количество строк", len(rows)])
        metadata.append(["Фильтры", str(result["filters"])])
        stream = io.BytesIO()
        workbook.save(stream)
        return Response(
            stream.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="control-center-accounts.xlsx"'},
        )
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        "\ufeff" + stream.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="control-center-accounts.csv"'},
    )


@router.get("/accounts/{account_id}")
def get_control_center_account(
    account_id: UUID,
    period: str = "7d",
    timezone_mode: str = "ACCOUNT",
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    account = _get_account(db, account_id)
    date_start, date_end = _parse_period(period, start_date, end_date)
    metrics = monitoring_state_map(db, [account.id], date_start, date_end, timezone_mode.upper()).get(account.id, {})
    connection = db.get(GoogleConnection, account.connection_id)
    mcc_by_id, geo_by_id, path_counts = _account_context_maps(db, [account])
    tags = tag_map_for_accounts(db, [account.id]).get(account.id, [])
    note_history = list(
        db.scalars(
            select(AccountNoteHistory)
            .where(AccountNoteHistory.account_id == account.id)
            .order_by(desc(AccountNoteHistory.changed_at))
            .limit(200)
        ).all()
    )
    tag_history = list(
        db.scalars(
            select(AccountTagHistory)
            .where(AccountTagHistory.account_id == account.id)
            .order_by(desc(AccountTagHistory.changed_at))
            .limit(200)
        ).all()
    )
    campaigns = list(
        db.scalars(
            select(ControlCenterCampaign)
            .where(ControlCenterCampaign.account_id == account.id)
            .order_by(ControlCenterCampaign.name)
        ).all()
    )
    problems = list(
        db.scalars(
            select(ControlCenterProblem)
            .where(ControlCenterProblem.account_id == account.id)
            .order_by(desc(ControlCenterProblem.last_seen_at))
        ).all()
    )
    events = list(
        db.scalars(
            select(ControlCenterEvent)
            .where(ControlCenterEvent.account_id == account.id)
            .order_by(desc(ControlCenterEvent.occurred_at))
            .limit(300)
        ).all()
    )
    daily = list(
        db.scalars(
            select(AccountMetricDaily)
            .where(
                AccountMetricDaily.account_id == account.id,
                AccountMetricDaily.metric_date.between(date_start, date_end),
                AccountMetricDaily.timezone_mode == timezone_mode.upper(),
            )
            .order_by(AccountMetricDaily.metric_date)
        ).all()
    )
    ads_assets = list(
        db.scalars(
            select(ModerationRecord)
            .where(ModerationRecord.customer_id == account.customer_id)
            .order_by(desc(ModerationRecord.checked_at))
            .limit(200)
        ).all()
    )
    return {
        "account": account_payload(
            account,
            connection.name if connection else None,
            tags,
            metrics,
            len(problems),
            mcc=mcc_by_id.get(account.primary_mcc_id),
            geo=geo_by_id.get(account.geo_override_id or account.geo_id),
            access_path_count=path_counts.get(account.id, 0),
        ),
        "campaigns": [campaign_payload(item, account) for item in campaigns],
        "problems": [problem_payload(item, account) for item in problems],
        "metric_history": [
            {
                "date": item.metric_date,
                "cost_micros": item.cost_micros,
                "conversions": item.conversions,
                "impressions": item.impressions,
                "clicks": item.clicks,
                "boundary_precision": item.boundary_precision,
            }
            for item in daily
        ],
        "ads_assets": [
            {
                "resource_name": item.resource_name,
                "approval_status": item.approval_status,
                "policy_topics": item.policy_topics,
                "checked_at": item.checked_at,
            }
            for item in ads_assets
        ],
        "note_history": [
            {
                "id": str(item.id),
                "previous_note": item.previous_note,
                "note": item.note,
                "changed_by_id": str(item.changed_by_id) if item.changed_by_id else None,
                "changed_at": item.changed_at,
            }
            for item in note_history
        ],
        "tag_history": [
            {
                "id": str(item.id),
                "tag_name": item.tag_name,
                "action": item.action,
                "changed_by_id": str(item.changed_by_id) if item.changed_by_id else None,
                "changed_at": item.changed_at,
            }
            for item in tag_history
        ],
        "events": [event_payload(item) for item in events],
        "unsupported": [
            "Google Ads API не предоставляет полный поток уведомлений интерфейса.",
            "Google Ads API не предоставляет универсальную точную причину блокировки аккаунта.",
        ],
    }


@router.patch("/accounts/{account_id}")
def patch_control_center_account(
    account_id: UUID,
    payload: AccountPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> dict:
    account = _get_account(db, account_id)
    changes = payload.model_dump(exclude_unset=True)
    if "geo_override_id" in changes:
        geo_override_id = changes.pop("geo_override_id")
        geo = db.get(GeoDefinition, geo_override_id) if geo_override_id else None
        if geo_override_id and not geo:
            raise HTTPException(status_code=404, detail="GEO не найдено")
        account.geo_override_id = geo.id if geo else None
        account.geo_override_by_id = user.id if geo else None
        account.geo_override_at = utcnow() if geo else None
        if geo:
            account.geo_id = geo.id
        else:
            mcc = db.get(MccAccount, account.primary_mcc_id) if account.primary_mcc_id else None
            account.geo_id = mcc.geo_id if mcc else None
        changes["geo_override_id"] = account.geo_override_id
        _event(
            db,
            account.id,
            "GEO_CHANGED",
            "GEO аккаунта изменено вручную" if geo else "Ручное GEO аккаунта сброшено",
            user.id,
            {
                "geo_id": str(account.geo_id) if account.geo_id else None,
                "source": "ACCOUNT_OVERRIDE" if geo else "MCC",
            },
        )
    if "current_note" in changes and changes["current_note"] != account.current_note:
        db.add(
            AccountNoteHistory(
                account_id=account.id,
                previous_note=account.current_note,
                note=changes["current_note"],
                changed_by_id=user.id,
                changed_at=utcnow(),
            )
        )
        account.note_updated_at = utcnow()
        account.note_updated_by_id = user.id
        _event(
            db,
            account.id,
            "NOTE_CHANGED",
            "Заметка аккаунта изменена",
            user.id,
            {"has_note": bool(changes["current_note"])},
        )
    for field, value in changes.items():
        setattr(account, field, value.value if hasattr(value, "value") else value)
    if "work_status" in changes:
        _event(
            db,
            account.id,
            "WORK_STATUS_CHANGED",
            f"Рабочий статус изменён на {account.work_status}",
            user.id,
            {"work_status": account.work_status},
        )
    if "local_name" in changes:
        _event(
            db,
            account.id,
            "LOCAL_NAME_CHANGED",
            "Локальное название изменено",
            user.id,
            {"local_name": account.local_name},
        )
    record_audit(
        db,
        request,
        user,
        "control_center.account.update",
        "customer_account",
        str(account.id),
        {"fields": sorted(changes)},
    )
    db.commit()
    db.refresh(account)
    connection = db.get(GoogleConnection, account.connection_id)
    mcc_by_id, geo_by_id, path_counts = _account_context_maps(db, [account])
    metrics = monitoring_state_map(
        db, [account.id], datetime.now(UTC).date() - timedelta(days=6), datetime.now(UTC).date(), "ACCOUNT"
    ).get(account.id, {})
    return account_payload(
        account,
        connection.name if connection else None,
        tag_map_for_accounts(db, [account.id]).get(account.id, []),
        metrics,
        mcc=mcc_by_id.get(account.primary_mcc_id),
        geo=geo_by_id.get(account.geo_override_id or account.geo_id),
        access_path_count=path_counts.get(account.id, 0),
    )


@router.post("/accounts/bulk-work-status")
def bulk_work_status(
    payload: BulkWorkStatusIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> dict:
    accounts = list(db.scalars(select(CustomerAccount).where(CustomerAccount.id.in_(payload.account_ids))).all())
    if len(accounts) != len(set(payload.account_ids)):
        raise HTTPException(status_code=404, detail="Один или несколько аккаунтов не найдены")
    now = utcnow()
    for account in accounts:
        previous = account.work_status
        account.work_status = payload.work_status.value
        if previous != account.work_status:
            db.add(
                ControlCenterEvent(
                    account_id=account.id,
                    campaign_id=None,
                    actor_user_id=user.id,
                    event_type="WORK_STATUS_CHANGED",
                    source="LOCAL",
                    summary=f"Массовая смена статуса: {previous} → {account.work_status}",
                    details={"previous": previous, "current": account.work_status},
                    occurred_at=now,
                )
            )
    record_audit(
        db,
        request,
        user,
        "control_center.account.bulk_work_status",
        "customer_account",
        None,
        {"count": len(accounts), "work_status": payload.work_status.value},
    )
    db.commit()
    return {"updated": len(accounts), "work_status": payload.work_status.value}


@router.get("/tags")
def list_tags(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    del user
    tags = list(db.scalars(select(ControlCenterTag).order_by(ControlCenterTag.name)).all())
    counts = {
        tag_id: int(count)
        for tag_id, count in db.execute(select(AccountTag.tag_id, func.count()).group_by(AccountTag.tag_id)).all()
    }
    return [
        {
            "id": str(tag.id),
            "name": tag.name,
            "color": tag.color,
            "accounts_count": counts.get(tag.id, 0),
        }
        for tag in tags
    ]


@router.post("/tags", status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    existing = db.scalar(select(ControlCenterTag).where(func.lower(ControlCenterTag.name) == payload.name.lower()))
    if existing:
        return {"id": str(existing.id), "name": existing.name, "color": existing.color}
    tag = ControlCenterTag(name=payload.name, color=payload.color, created_by_id=user.id)
    db.add(tag)
    record_audit(db, request, user, "control_center.tag.create", "tag", None, {"name": payload.name})
    db.commit()
    db.refresh(tag)
    return {"id": str(tag.id), "name": tag.name, "color": tag.color}


@router.post("/accounts/{account_id}/tags/{tag_id}", status_code=status.HTTP_201_CREATED)
def assign_tag(
    account_id: UUID,
    tag_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    account = _get_account(db, account_id)
    tag = db.get(ControlCenterTag, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Тег не найден")
    assignment = db.scalar(select(AccountTag).where(AccountTag.account_id == account.id, AccountTag.tag_id == tag.id))
    if not assignment:
        assignment = AccountTag(
            account_id=account.id,
            tag_id=tag.id,
            assigned_by_id=user.id,
            assigned_at=utcnow(),
        )
        db.add(assignment)
        db.add(
            AccountTagHistory(
                account_id=account.id,
                tag_name=tag.name,
                action="ADDED",
                changed_by_id=user.id,
                changed_at=utcnow(),
            )
        )
        _event(db, account.id, "TAG_ADDED", f"Добавлен тег «{tag.name}»", user.id)
        record_audit(
            db, request, user, "control_center.tag.assign", "customer_account", str(account.id), {"tag": tag.name}
        )
        db.commit()
    return {"id": str(tag.id), "name": tag.name, "color": tag.color}


@router.delete("/accounts/{account_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tag(
    account_id: UUID,
    tag_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> Response:
    account = _get_account(db, account_id)
    tag = db.get(ControlCenterTag, tag_id)
    assignment = db.scalar(select(AccountTag).where(AccountTag.account_id == account.id, AccountTag.tag_id == tag_id))
    if assignment:
        db.delete(assignment)
        db.add(
            AccountTagHistory(
                account_id=account.id,
                tag_name=tag.name if tag else str(tag_id),
                action="REMOVED",
                changed_by_id=user.id,
                changed_at=utcnow(),
            )
        )
        _event(
            db,
            account.id,
            "TAG_REMOVED",
            f"Удалён тег «{tag.name if tag else tag_id}»",
            user.id,
        )
        record_audit(
            db,
            request,
            user,
            "control_center.tag.remove",
            "customer_account",
            str(account.id),
            {"tag_id": str(tag_id)},
        )
        db.commit()
    return Response(status_code=204)


@router.get("/saved-views")
def list_saved_views(
    entity_level: str = "ACCOUNT",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    rows = list(
        db.scalars(
            select(ControlCenterSavedView)
            .where(
                or_(
                    ControlCenterSavedView.owner_user_id == user.id,
                    ControlCenterSavedView.is_shared.is_(True),
                ),
                ControlCenterSavedView.entity_level == entity_level.upper(),
            )
            .order_by(
                desc(ControlCenterSavedView.owner_user_id == user.id),
                desc(ControlCenterSavedView.is_default),
                ControlCenterSavedView.name,
            )
        ).all()
    )
    return [saved_view_payload(row, current_user_id=user.id) for row in rows]


@router.post("/saved-views", status_code=status.HTTP_201_CREATED)
def create_saved_view(
    payload: SavedViewIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> dict:
    if payload.is_shared and user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Общие представления может создавать только администратор")
    if payload.is_default:
        _clear_default_views(db, user.id, payload.entity_level)
    view = ControlCenterSavedView(
        owner_user_id=user.id,
        entity_level=payload.entity_level,
        name=payload.name.strip(),
        config=payload.config,
        is_default=payload.is_default,
        is_shared=payload.is_shared,
        description=payload.description,
    )
    db.add(view)
    record_audit(db, request, user, "control_center.saved_view.create", "saved_view", None, {"name": view.name})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Представление с таким именем уже существует") from exc
    db.refresh(view)
    return saved_view_payload(view, current_user_id=user.id)


@router.patch("/saved-views/{view_id}")
def patch_saved_view(
    view_id: UUID,
    payload: SavedViewPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> dict:
    view = db.get(ControlCenterSavedView, view_id)
    if not view or view.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Представление не найдено")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("is_shared") and user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Общие представления может создавать только администратор")
    if changes.get("is_default"):
        _clear_default_views(db, user.id, view.entity_level)
    for field, value in changes.items():
        setattr(view, field, value)
    record_audit(
        db, request, user, "control_center.saved_view.update", "saved_view", str(view.id), {"fields": sorted(changes)}
    )
    db.commit()
    db.refresh(view)
    return saved_view_payload(view, current_user_id=user.id)


@router.post("/saved-views/{view_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_saved_view(
    view_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> dict:
    source = db.get(ControlCenterSavedView, view_id)
    if not source or (source.owner_user_id != user.id and not source.is_shared):
        raise HTTPException(status_code=404, detail="Представление не найдено")
    base_name = f"Копия: {source.name}"[:120]
    existing_names = set(
        db.scalars(
            select(ControlCenterSavedView.name).where(
                ControlCenterSavedView.owner_user_id == user.id,
                ControlCenterSavedView.entity_level == source.entity_level,
            )
        ).all()
    )
    name = base_name
    suffix = 2
    while name in existing_names:
        suffix_text = f" ({suffix})"
        name = f"{base_name[: 120 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    view = ControlCenterSavedView(
        owner_user_id=user.id,
        entity_level=source.entity_level,
        name=name,
        config=dict(source.config or {}),
        is_default=False,
        is_shared=False,
        description=source.description,
        source_view_id=source.id,
    )
    db.add(view)
    record_audit(
        db,
        request,
        user,
        "control_center.saved_view.duplicate",
        "saved_view",
        str(source.id),
        {"new_name": name},
    )
    db.commit()
    db.refresh(view)
    return saved_view_payload(view, current_user_id=user.id)


@router.delete("/saved-views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_view(
    view_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: User = Depends(require_csrf),
) -> Response:
    view = db.get(ControlCenterSavedView, view_id)
    if not view or view.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Представление не найдено")
    db.delete(view)
    record_audit(db, request, user, "control_center.saved_view.delete", "saved_view", str(view.id))
    db.commit()
    return Response(status_code=204)


@router.get("/campaigns")
def list_control_center_campaigns(
    search: str | None = Query(default=None, max_length=500),
    status_filter: str | None = None,
    source: str | None = None,
    account_id: UUID | None = None,
    cost_min_micros: int | None = Query(default=None, ge=0),
    cost_max_micros: int | None = Query(default=None, ge=0),
    registrations_min: Decimal | None = Query(default=None, ge=0),
    deposits_eq: Decimal | None = Query(default=None, ge=0),
    cpa_registration_min_micros: int | None = Query(default=None, ge=0),
    registrations_without_deposits: bool = False,
    sort_fields: str = Query(default="name", max_length=500),
    sort_directions: str = Query(default="asc", max_length=100),
    limit: int = Query(default=200, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    query = select(ControlCenterCampaign)
    if search and search.strip():
        query = query.where(ControlCenterCampaign.name.ilike(f"%{search.strip()}%"))
    if status_filter:
        query = query.where(ControlCenterCampaign.status == status_filter.upper())
    if source:
        query = query.where(ControlCenterCampaign.source == source.upper())
    if account_id:
        query = query.where(ControlCenterCampaign.account_id == account_id)
    if cost_min_micros is not None:
        query = query.where(ControlCenterCampaign.cost_micros >= cost_min_micros)
    if cost_max_micros is not None:
        query = query.where(ControlCenterCampaign.cost_micros <= cost_max_micros)
    if registrations_min is not None:
        query = query.where(
            ControlCenterCampaign.registrations >= registrations_min
        )
    if deposits_eq is not None:
        query = query.where(ControlCenterCampaign.deposits == deposits_eq)
    if cpa_registration_min_micros is not None:
        query = query.where(
            CAMPAIGN_CPA_REGISTRATION >= cpa_registration_min_micros
        )
    if registrations_without_deposits:
        query = query.where(
            ControlCenterCampaign.registration_data_available.is_(True),
            ControlCenterCampaign.deposit_data_available.is_(True),
            ControlCenterCampaign.registrations > 0,
            ControlCenterCampaign.deposits == 0,
        )
    total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    requested_sorts = [
        field.strip()
        for field in sort_fields.split(",")
        if field.strip() in CAMPAIGN_SORTS
    ][:4] or ["name"]
    requested_directions = [
        direction.strip().lower()
        for direction in sort_directions.split(",")
    ]
    ordering = []
    for index, field in enumerate(requested_sorts):
        direction = (
            requested_directions[index]
            if index < len(requested_directions)
            and requested_directions[index] in {"asc", "desc"}
            else "asc"
        )
        expression = CAMPAIGN_SORTS[field]
        ordering.append(
            expression.desc().nullslast()
            if direction == "desc"
            else expression.asc().nullslast()
        )
    ordering.append(ControlCenterCampaign.id.asc())
    campaigns = list(
        db.scalars(
            query.order_by(*ordering).offset(offset).limit(limit)
        ).all()
    )
    account_map = {
        account.id: account
        for account in db.scalars(
            select(CustomerAccount).where(CustomerAccount.id.in_([campaign.account_id for campaign in campaigns]))
        ).all()
    }
    return {
        "items": [campaign_payload(campaign, account_map.get(campaign.account_id)) for campaign in campaigns],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/problems")
def list_problems(
    severity: str | None = None,
    problem_type: str | None = None,
    state_filter: str | None = None,
    limit: int = Query(default=200, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    del user
    query = select(ControlCenterProblem)
    if severity:
        query = query.where(ControlCenterProblem.severity == severity.upper())
    if problem_type:
        query = query.where(ControlCenterProblem.problem_type == problem_type.upper())
    if state_filter:
        query = query.where(ControlCenterProblem.state == state_filter.upper())
    problems = list(db.scalars(query.order_by(desc(ControlCenterProblem.last_seen_at)).limit(limit)).all())
    account_map = {
        account.id: account
        for account in db.scalars(
            select(CustomerAccount).where(
                CustomerAccount.id.in_([problem.account_id for problem in problems if problem.account_id])
            )
        ).all()
    }
    return [problem_payload(item, account_map.get(item.account_id)) for item in problems]


@router.patch("/problems/{problem_id}")
def patch_problem(
    problem_id: UUID,
    payload: ProblemPatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    problem = db.get(ControlCenterProblem, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Проблема не найдена")
    problem.state = payload.state
    problem.resolved_at = utcnow() if payload.state == "RESOLVED" else None
    record_audit(
        db,
        request,
        user,
        "control_center.problem.state",
        "control_center_problem",
        str(problem.id),
        {"state": payload.state},
    )
    db.commit()
    db.refresh(problem)
    return problem_payload(problem, db.get(CustomerAccount, problem.account_id) if problem.account_id else None)


@router.get("/history")
def list_history(
    account_id: UUID | None = None,
    event_type: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    del user
    query = select(ControlCenterEvent)
    if account_id:
        query = query.where(ControlCenterEvent.account_id == account_id)
    if event_type:
        query = query.where(ControlCenterEvent.event_type == event_type.upper())
    events = list(db.scalars(query.order_by(desc(ControlCenterEvent.occurred_at)).limit(limit)).all())
    return [event_payload(item) for item in events]


@router.post("/sync/estimate")
def estimate_sync(
    payload: SyncEstimateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    accounts = _sync_accounts_for_scope(db, payload.scope, payload.account_ids)
    estimated_operations = len(accounts) * 3
    quota = quota_summary(db)
    return {
        "scope": payload.scope,
        "accounts": len(accounts),
        "estimated_operations": estimated_operations,
        "estimate_token": estimate_signature(payload.scope, [account.id for account in accounts], estimated_operations),
        "quota": quota,
        "warning": (
            "Фоновая синхронизация замедлена: сохранён резерв для ручных действий."
            if quota["background_throttled"]
            else None
        ),
    }


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
def start_sync(
    payload: SyncStartIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    accounts = _sync_accounts_for_scope(db, payload.scope, payload.account_ids)
    estimated_operations = len(accounts) * 3
    expected_token = estimate_signature(payload.scope, [account.id for account in accounts], estimated_operations)
    if payload.estimate_token != expected_token:
        raise HTTPException(
            status_code=409,
            detail="Оценка нагрузки устарела. Повторите предварительную оценку.",
        )
    existing = db.scalar(
        select(ControlCenterSyncRun).where(ControlCenterSyncRun.idempotency_key == payload.estimate_token)
    )
    if existing:
        return {
            "sync_run_id": str(existing.id),
            "job_id": str(existing.job_id) if existing.job_id else None,
            "status": existing.status,
            "reused": True,
        }
    job = Job(
        type="CONTROL_CENTER_SYNC",
        status=JobStatus.QUEUED.value,
        connection_id=None,
        created_by_id=user.id,
        idempotency_key=f"cc-sync:{payload.estimate_token}",
        progress_current=0,
        progress_total=len(accounts),
        payload={"scope": payload.scope, "account_ids": [str(account.id) for account in accounts]},
    )
    db.add(job)
    db.flush()
    sync_run = ControlCenterSyncRun(
        connection_id=None,
        job_id=job.id,
        requested_by_id=user.id,
        scope=payload.scope,
        mode="READ_ONLY",
        status="QUEUED",
        estimated_operations=estimated_operations,
        actual_operations=0,
        successful_accounts=0,
        failed_accounts=0,
        selection=[str(account.id) for account in accounts],
        idempotency_key=payload.estimate_token,
    )
    db.add(sync_run)
    db.flush()
    for account in accounts:
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
    record_audit(
        db,
        request,
        user,
        "control_center.sync.start",
        "control_center_sync_run",
        str(sync_run.id),
        {"scope": payload.scope, "accounts": len(accounts), "estimated_operations": estimated_operations},
    )
    db.commit()
    from app.jobs.control_center_tasks import run_control_center_sync

    run_control_center_sync.delay(str(sync_run.id))
    return {
        "sync_run_id": str(sync_run.id),
        "job_id": str(job.id),
        "status": "QUEUED",
        "reused": False,
    }


@router.get("/sync/{sync_run_id}")
def get_sync_run(
    sync_run_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    sync_run = db.get(ControlCenterSyncRun, sync_run_id)
    if not sync_run:
        raise HTTPException(status_code=404, detail="Задание синхронизации не найдено")
    items = list(
        db.scalars(
            select(ControlCenterSyncItem)
            .where(ControlCenterSyncItem.sync_run_id == sync_run.id)
            .order_by(ControlCenterSyncItem.created_at)
        ).all()
    )
    return {
        "id": str(sync_run.id),
        "job_id": str(sync_run.job_id) if sync_run.job_id else None,
        "scope": sync_run.scope,
        "status": sync_run.status,
        "estimated_operations": sync_run.estimated_operations,
        "actual_operations": sync_run.actual_operations,
        "successful_accounts": sync_run.successful_accounts,
        "failed_accounts": sync_run.failed_accounts,
        "started_at": sync_run.started_at,
        "completed_at": sync_run.completed_at,
        "error_message": sync_run.error_message,
        "items": [
            {
                "id": str(item.id),
                "account_id": str(item.account_id),
                "status": item.status,
                "attempts": item.attempts,
                "operations": item.operations,
                "request_ids": item.request_ids,
                "error_code": item.error_code,
                "error_message": item.error_message,
            }
            for item in items
        ],
    }


@router.post("/actions/preview", status_code=status.HTTP_201_CREATED)
def preview_action(
    payload: ActionPreviewIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> dict:
    if payload.execution_mode == "PRODUCTION":
        raise HTTPException(
            status_code=409,
            detail="PRODUCTION_MUTATE_BLOCKED: Production mutate полностью заблокирован.",
        )
    campaigns = list(
        db.scalars(select(ControlCenterCampaign).where(ControlCenterCampaign.id.in_(payload.campaign_ids))).all()
    )
    if len(campaigns) != len(set(payload.campaign_ids)):
        raise HTTPException(status_code=404, detail="Одна или несколько кампаний не найдены")
    accounts = {
        account.id: account
        for account in db.scalars(
            select(CustomerAccount).where(CustomerAccount.id.in_([campaign.account_id for campaign in campaigns]))
        ).all()
    }
    confirmation_token = generate_token("cc_confirm")
    now = utcnow()
    pre_states = []
    changes = []
    warnings = []
    request_ids: list[str] = []
    validation = {
        "ok": True,
        "validate_only": False,
        "validate_only_pending_confirmation": payload.execution_mode == "GOOGLE_TEST",
        "execution_mode": payload.execution_mode,
        "google_contacted": False,
        "errors": [],
    }
    fresh_states: dict[UUID, dict] = {}
    if payload.execution_mode == "GOOGLE_TEST":
        try:
            adapters = {}
            for account in accounts.values():
                connection = db.get(GoogleConnection, account.connection_id)
                if not is_google_connection_active(connection):
                    raise ValueError(f"Подключение аккаунта {account.customer_id} недоступно")
                require_execution_mode_for_connection(connection, payload.execution_mode)
                adapter = build_google_ads_adapter(db, connection)
                adapters[account.id] = adapter
                _, _, account_request_ids = refresh_google_test_target(
                    db,
                    connection,
                    adapter,
                    account.customer_id,
                    require_confirmation=False,
                )
                request_ids.extend(account_request_ids)
            for campaign in campaigns:
                account = accounts[campaign.account_id]
                adapter = adapters[account.id]
                current = adapter.read_control_center_campaign(account.customer_id, campaign.resource_name)
                fresh_states[campaign.id] = current
                request_ids.extend(current.get("_request_ids") or [])
            validation["google_contacted"] = True
        except GoogleAdsSafetyError as exc:
            raise HTTPException(status_code=409, detail=f"{exc.code}: {exc}") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    for campaign in campaigns:
        current = fresh_states.get(campaign.id) or {
            "resource_name": campaign.resource_name,
            "name": campaign.name,
            "status": campaign.status,
            "budget_resource_name": campaign.budget_resource_name,
            "budget_micros": campaign.budget_micros,
            "budget_shared": campaign.budget_shared,
            "budget_reference_count": None,
            "source": "LOCAL_SNAPSHOT",
        }
        pre_states.append(_action_pre_state(campaign.id, current))
        if payload.action_type == "SET_BUDGET":
            changes.append(
                {
                    "campaign_id": str(campaign.id),
                    "field": "budget_micros",
                    "before": current.get("budget_micros"),
                    "after": payload.amount_micros,
                }
            )
            if current.get("budget_shared"):
                warnings.append(
                    {
                        "campaign_id": str(campaign.id),
                        "code": "SHARED_BUDGET",
                        "message": (
                            "Бюджет общий и может затронуть "
                            f"{current.get('budget_reference_count') or 'несколько'} кампаний."
                        ),
                    }
                )
        else:
            changes.append(
                {
                    "campaign_id": str(campaign.id),
                    "field": "status",
                    "before": current.get("status"),
                    "after": "PAUSED" if payload.action_type == "PAUSE" else "ENABLED",
                }
            )
    action = ControlCenterActionRequest(
        account_id=campaigns[0].account_id if len({item.account_id for item in campaigns}) == 1 else None,
        campaign_id=campaigns[0].id if len(campaigns) == 1 else None,
        requested_by_id=user.id,
        action_type=payload.action_type,
        execution_mode=payload.execution_mode,
        status="PREVIEWED" if validation["ok"] else "VALIDATION_FAILED",
        requested_payload=payload.model_dump(mode="json"),
        pre_state={"campaigns": pre_states},
        preview={"changes": changes, "warnings": warnings},
        validation=validation,
        readback={},
        confirmation_token_hash=hash_token(confirmation_token),
        confirmation_expires_at=now + timedelta(minutes=15),
        idempotency_key=hashlib.sha256(f"{user.id}:{payload.model_dump_json()}:{now.isoformat()}".encode()).hexdigest(),
        request_ids=list(dict.fromkeys(request_ids)),
    )
    db.add(action)
    db.flush()
    for campaign in campaigns:
        db.add(
            ControlCenterActionItem(
                action_request_id=action.id,
                account_id=campaign.account_id,
                campaign_id=campaign.id,
                status="VALIDATED" if validation["ok"] else "VALIDATION_FAILED",
                previous_state=next(item for item in pre_states if item["campaign_id"] == str(campaign.id)),
                result={},
            )
        )
    record_audit(
        db,
        request,
        user,
        "control_center.action.preview",
        "control_center_action_request",
        str(action.id),
        {
            "action_type": action.action_type,
            "execution_mode": action.execution_mode,
            "campaigns": len(campaigns),
            "validate_only": validation["validate_only"],
            "google_contacted": validation["google_contacted"],
        },
    )
    db.commit()
    return {
        "id": str(action.id),
        "status": action.status,
        "execution_mode": action.execution_mode,
        "preview": action.preview,
        "validation": action.validation,
        "confirmation_token": confirmation_token,
        "confirmation_expires_at": action.confirmation_expires_at,
        "request_ids": action.request_ids,
    }


@router.post("/actions/{action_id}/confirm", status_code=status.HTTP_202_ACCEPTED)
def confirm_action(
    action_id: UUID,
    payload: ActionConfirmIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> dict:
    action = db.get(ControlCenterActionRequest, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Предварительный просмотр не найден")
    if action.requested_by_id != user.id:
        raise HTTPException(status_code=403, detail="Подтвердить действие может только его автор")
    if action.status not in {"PREVIEWED"}:
        raise HTTPException(status_code=409, detail=f"Действие уже имеет статус {action.status}")
    if action.confirmation_expires_at < utcnow():
        action.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=409, detail="Срок подтверждения истёк. Создайте новый preview.")
    if hash_token(payload.confirmation_token) != action.confirmation_token_hash:
        raise HTTPException(status_code=403, detail="Код подтверждения не совпадает")
    action.confirmed_at = utcnow()
    if action.execution_mode == "SIMULATION":
        action.status = "SUCCEEDED_SIMULATION"
        action.completed_at = utcnow()
        items = list(
            db.scalars(
                select(ControlCenterActionItem).where(ControlCenterActionItem.action_request_id == action.id)
            ).all()
        )
        simulated_readback = []
        for item in items:
            item.status = "SUCCEEDED_SIMULATION"
            if action.action_type in {"PAUSE", "ENABLE"}:
                result = {
                    "status": "PAUSED" if action.action_type == "PAUSE" else "ENABLED",
                    "simulated": True,
                    "google_contacted": False,
                }
            else:
                result = {
                    "budget_micros": action.requested_payload.get("amount_micros"),
                    "simulated": True,
                    "google_contacted": False,
                }
            item.result = result
            simulated_readback.append({"campaign_id": str(item.campaign_id), **result})
            _event(
                db,
                item.account_id,
                "MANUAL_ACTION_SIMULATED",
                f"{action.action_type}: проверен полный путь без Google mutate",
                user.id,
                {"action_request_id": str(action.id), **result},
                item.campaign_id,
            )
        action.readback = {"items": simulated_readback}
        audit_action = "control_center.action.simulation.complete"
    else:
        if action.execution_mode != "GOOGLE_TEST":
            raise HTTPException(
                status_code=409,
                detail="PRODUCTION_MUTATE_BLOCKED: Production mutate полностью заблокирован.",
            )
        action.status = "QUEUED"
        audit_action = "control_center.action.google_test.confirm"
    record_audit(
        db,
        request,
        user,
        audit_action,
        "control_center_action_request",
        str(action.id),
        {"action_type": action.action_type, "execution_mode": action.execution_mode},
    )
    db.commit()
    if action.execution_mode == "GOOGLE_TEST":
        from app.jobs.control_center_tasks import execute_control_center_action

        execute_control_center_action.delay(str(action.id))
    return {
        "id": str(action.id),
        "status": action.status,
        "execution_mode": action.execution_mode,
        "readback": action.readback,
        "request_ids": action.request_ids,
    }


@router.get("/actions/{action_id}")
def get_action(
    action_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    del user
    action = db.get(ControlCenterActionRequest, action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Действие не найдено")
    items = list(
        db.scalars(select(ControlCenterActionItem).where(ControlCenterActionItem.action_request_id == action.id)).all()
    )
    return {
        "id": str(action.id),
        "action_type": action.action_type,
        "execution_mode": action.execution_mode,
        "status": action.status,
        "preview": action.preview,
        "validation": action.validation,
        "readback": action.readback,
        "request_ids": action.request_ids,
        "error_message": action.error_message,
        "items": [
            {
                "campaign_id": str(item.campaign_id),
                "account_id": str(item.account_id),
                "status": item.status,
                "result": item.result,
                "request_id": item.request_id,
                "error_message": item.error_message,
            }
            for item in items
        ],
    }


@router.get("/rules/kill-switch")
def get_kill_switch(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    del user
    return {"active": rule_kill_switch_active(db)}


@router.patch("/rules/kill-switch")
def patch_kill_switch(
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    active = bool(payload.get("active", True))
    setting = db.scalar(select(ApplicationSetting).where(ApplicationSetting.key == RULE_KILL_SWITCH_KEY))
    if not setting:
        setting = ApplicationSetting(
            key=RULE_KILL_SWITCH_KEY,
            value={"active": active},
            updated_by_id=user.id,
        )
        db.add(setting)
    else:
        setting.value = {"active": active}
        setting.updated_by_id = user.id
    stopped_actions = 0
    if active:
        queued_actions = list(
            db.scalars(
                select(ControlCenterActionRequest)
                .join(
                    ControlCenterRuleEvaluation,
                    ControlCenterRuleEvaluation.action_request_id
                    == ControlCenterActionRequest.id,
                )
                .where(ControlCenterActionRequest.status == "QUEUED")
                .with_for_update(skip_locked=True)
            ).all()
        )
        for action in queued_actions:
            action.status = "SKIPPED_KILL_SWITCH"
            action.completed_at = utcnow()
            action.error_message = "GLOBAL_KILL_SWITCH_ACTIVE"
            for item in db.scalars(
                select(ControlCenterActionItem).where(
                    ControlCenterActionItem.action_request_id == action.id
                )
            ).all():
                item.status = "SKIPPED_KILL_SWITCH"
                item.error_message = "GLOBAL_KILL_SWITCH_ACTIVE"
            evaluation = db.scalar(
                select(ControlCenterRuleEvaluation).where(
                    ControlCenterRuleEvaluation.action_request_id == action.id
                )
            )
            if evaluation:
                evaluation.status = "SKIPPED_KILL_SWITCH"
                evaluation.skip_reason = "GLOBAL_KILL_SWITCH_ACTIVE"
            stopped_actions += 1
    record_audit(
        db,
        request,
        user,
        "control_center.rules.kill_switch",
        "application_setting",
        str(setting.id) if setting.id else None,
        {"active": active, "stopped_rule_actions": stopped_actions},
    )
    db.commit()
    return {"active": active, "stopped_rule_actions": stopped_actions}


@router.get("/rules")
def list_rules(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[dict]:
    del user
    rules = list(db.scalars(select(ControlCenterRule).order_by(ControlCenterRule.name)).all())
    return [rule_payload(rule) for rule in rules]


@router.post("/rules", status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: RuleCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    rule = ControlCenterRule(created_by_id=user.id, **payload.model_dump())
    db.add(rule)
    record_audit(
        db,
        request,
        user,
        "control_center.rule.create",
        "control_center_rule",
        None,
        {"name": rule.name, "mode": rule.mode},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Правило с таким именем уже существует") from exc
    db.refresh(rule)
    return rule_payload(rule)


@router.patch("/rules/{rule_id}")
def patch_rule(
    rule_id: UUID,
    payload: RulePatchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    rule = db.get(ControlCenterRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(rule, field, value)
    if changes.get("mode") == "DRY_RUN":
        rule.live_confirmed_at = None
        rule.live_confirmed_by_id = None
    record_audit(
        db,
        request,
        user,
        "control_center.rule.update",
        "control_center_rule",
        str(rule.id),
        {"fields": sorted(changes)},
    )
    db.commit()
    db.refresh(rule)
    return rule_payload(rule)


@router.post("/rules/{rule_id}/live-mode")
def change_rule_live_mode(
    rule_id: UUID,
    payload: RuleLiveModeIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    rule = db.get(ControlCenterRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    if payload.confirmation == "ENABLE LIVE RULES":
        if not rule.actions:
            raise HTTPException(
                status_code=409,
                detail="Нельзя включить LIVE для правила без действий",
            )
        rule.mode = "LIVE"
        rule.enabled = False
        rule.live_confirmed_at = utcnow()
        rule.live_confirmed_by_id = user.id
        audit_action = "control_center.rule.live.confirm"
    else:
        rule.mode = "DRY_RUN"
        rule.enabled = False
        rule.live_confirmed_at = None
        rule.live_confirmed_by_id = None
        audit_action = "control_center.rule.live.disable"
    record_audit(
        db,
        request,
        user,
        audit_action,
        "control_center_rule",
        str(rule.id),
        {
            "mode": rule.mode,
            "enabled": rule.enabled,
            "requires_explicit_enable": True,
        },
    )
    db.commit()
    db.refresh(rule)
    return rule_payload(rule)


@router.post("/rules/{rule_id}/evaluate")
def evaluate_rule(
    rule_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> dict:
    rule = db.get(ControlCenterRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    engine_result = evaluate_rules(db, [rule], force=True)
    payload = {
        "rule_id": str(rule.id),
        "mode": rule.mode,
        **engine_result.payload(),
    }
    record_audit(
        db,
        request,
        user,
        "control_center.rule.evaluate",
        "control_center_rule",
        str(rule.id),
        payload,
    )
    db.commit()
    if engine_result.action_request_ids:
        from app.jobs.control_center_tasks import execute_control_center_action

        for action_request_id in engine_result.action_request_ids:
            execute_control_center_action.delay(str(action_request_id))
    return payload


def _account_context_maps(
    db: Session,
    accounts: list[CustomerAccount],
) -> tuple[dict[UUID, MccAccount], dict[UUID, GeoDefinition], dict[UUID, int]]:
    if not accounts:
        return {}, {}, {}
    mcc_ids = {account.primary_mcc_id for account in accounts if account.primary_mcc_id}
    geo_ids = {
        account.geo_override_id or account.geo_id for account in accounts if account.geo_override_id or account.geo_id
    }
    mcc_by_id = {item.id: item for item in db.scalars(select(MccAccount).where(MccAccount.id.in_(mcc_ids))).all()}
    geo_by_id = {item.id: item for item in db.scalars(select(GeoDefinition).where(GeoDefinition.id.in_(geo_ids))).all()}
    account_ids = [account.id for account in accounts]
    path_counts = {
        account_id: int(count)
        for account_id, count in db.execute(
            select(GoogleAccountAccessPath.account_id, func.count())
            .where(
                GoogleAccountAccessPath.account_id.in_(account_ids),
                GoogleAccountAccessPath.is_active.is_(True),
            )
            .group_by(GoogleAccountAccessPath.account_id)
        ).all()
        if account_id is not None
    }
    return mcc_by_id, geo_by_id, path_counts


def _account_export_value(payload: dict, path: str, column: str):
    value = payload
    for part in path.split("."):
        if not isinstance(value, dict):
            value = None
            break
        value = value.get(part)
    if column == "tags":
        return ", ".join(str(item.get("name") or "") for item in (value or []))
    if column in {
        "cost",
        "budget",
        "cpc",
        "cpa_registration",
        "cpa_deposit",
    }:
        return "Нет данных" if value is None else Decimal(int(value)) / Decimal(1_000_000)
    if value is None:
        return (
            "Нет данных"
            if column
            in {
                "all_conversions",
                "registrations",
                "deposits",
                "conversion_value",
                "roas",
                "active_campaigns",
                "disapproved_ads",
            }
            else ""
        )
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    return value


def _parse_period(period: str, start_date: str | None, end_date: str | None):
    try:
        parsed_start = datetime.fromisoformat(start_date).date() if start_date else None
        parsed_end = datetime.fromisoformat(end_date).date() if end_date else None
        return period_bounds(period, parsed_start, parsed_end)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _apply_quick_filter(query, quick_filter: str):
    value = quick_filter.lower()
    if value == "working":
        return query.where(CustomerAccount.work_status == "WORKING")
    if value == "paused":
        return query.where(CustomerAccount.work_status == "PAUSED")
    if value == "archive":
        return query.where(CustomerAccount.work_status == "ARCHIVED")
    if value == "verification":
        return query.where(
            func.upper(CustomerAccount.verification_status).in_(["REQUIRED", "PENDING", "ACTION_REQUIRED"])
        )
    if value == "issues":
        problem_accounts = select(ControlCenterProblem.account_id).where(ControlCenterProblem.state != "RESOLVED")
        return query.where(
            or_(
                and_(
                    func.upper(CustomerAccount.status).in_(PROBLEM_GOOGLE_STATUSES),
                    or_(
                        CustomerAccount.is_test_account.is_(False),
                        func.upper(CustomerAccount.status).not_in(TEST_ACCOUNT_CLOSED_STATUSES),
                    ),
                ),
                CustomerAccount.sync_error.is_not(None),
                CustomerAccount.detached_at.is_not(None),
                CustomerAccount.id.in_(problem_accounts),
            )
        )
    return query


def _get_account(db: Session, account_id: UUID) -> CustomerAccount:
    account = db.get(CustomerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    return account


def _event(
    db: Session,
    account_id: UUID | None,
    event_type: str,
    summary: str,
    actor_user_id: UUID | None = None,
    details: dict | None = None,
    campaign_id: UUID | None = None,
) -> None:
    db.add(
        ControlCenterEvent(
            account_id=account_id,
            campaign_id=campaign_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            source="LOCAL",
            summary=summary,
            details=details or {},
            occurred_at=utcnow(),
        )
    )


def saved_view_payload(view: ControlCenterSavedView, current_user_id: UUID | None = None) -> dict:
    return {
        "id": str(view.id),
        "owner_user_id": str(view.owner_user_id),
        "is_owner": current_user_id is None or view.owner_user_id == current_user_id,
        "name": view.name,
        "entity_level": view.entity_level,
        "config": view.config,
        "is_default": view.is_default,
        "is_shared": view.is_shared,
        "description": view.description,
        "source_view_id": str(view.source_view_id) if view.source_view_id else None,
        "created_at": view.created_at,
        "updated_at": view.updated_at,
    }


def problem_payload(problem: ControlCenterProblem, account: CustomerAccount | None) -> dict:
    return {
        "id": str(problem.id),
        "account_id": str(problem.account_id) if problem.account_id else None,
        "account_name": (account.local_name or account.descriptive_name or account.customer_id if account else None),
        "customer_id": account.customer_id if account else None,
        "campaign_id": str(problem.campaign_id) if problem.campaign_id else None,
        "source": problem.source,
        "problem_type": problem.problem_type,
        "severity": problem.severity,
        "title": problem.title,
        "description": _problem_display_description(problem),
        "google_code": problem.google_code,
        "request_id": problem.request_id,
        "state": problem.state,
        "first_seen_at": problem.first_seen_at,
        "last_seen_at": problem.last_seen_at,
        "resolved_at": problem.resolved_at,
        "diagnostics": problem.diagnostics,
    }


def _problem_display_description(problem: ControlCenterProblem) -> str:
    description = str(problem.google_message or problem.description or "").strip()
    technical_markers = ("<_InactiveRpcError", "debug_error_string", "Traceback")
    if not any(marker in description for marker in technical_markers):
        return description

    code = str(problem.google_code or "").upper()
    if "UNRECOGNIZED_FIELD" in code:
        message = "Google Ads отклонил неизвестное поле в запросе истории изменений."
    elif "INVALID_DATE_FORMAT" in code:
        message = "Google Ads отклонил формат даты в запросе истории изменений."
    else:
        message = "Google Ads API отклонил запрос; точная причина указана в коде ошибки."
    if problem.state == "RESOLVED":
        message += " Повторная синхронизация прошла успешно, проблема закрыта."
    return message


def event_payload(event: ControlCenterEvent) -> dict:
    return {
        "id": str(event.id),
        "account_id": str(event.account_id) if event.account_id else None,
        "campaign_id": str(event.campaign_id) if event.campaign_id else None,
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "event_type": event.event_type,
        "source": event.source,
        "summary": event.summary,
        "details": event.details,
        "occurred_at": event.occurred_at,
    }


def rule_payload(rule: ControlCenterRule) -> dict:
    return {
        "id": str(rule.id),
        "name": rule.name,
        "enabled": rule.enabled,
        "mode": rule.mode,
        "scope": rule.scope,
        "condition_logic": rule.condition_logic,
        "conditions": rule.conditions,
        "actions": rule.actions,
        "safeguards": rule.safeguards,
        "cooldown_minutes": rule.cooldown_minutes,
        "max_actions_per_run": rule.max_actions_per_run,
        "max_actions_per_day": rule.max_actions_per_day,
        "priority": rule.priority,
        "schedule": rule.schedule,
        "max_budget_change_percent": (
            float(rule.max_budget_change_percent)
            if rule.max_budget_change_percent is not None
            else None
        ),
        "live_confirmed_at": rule.live_confirmed_at,
        "live_confirmed_by_id": (
            str(rule.live_confirmed_by_id)
            if rule.live_confirmed_by_id
            else None
        ),
        "last_evaluated_at": rule.last_evaluated_at,
        "last_action_at": rule.last_action_at,
        "circuit_open_until": rule.circuit_open_until,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def _clear_default_views(db: Session, user_id: UUID, entity_level: str) -> None:
    for view in db.scalars(
        select(ControlCenterSavedView).where(
            ControlCenterSavedView.owner_user_id == user_id,
            ControlCenterSavedView.entity_level == entity_level,
            ControlCenterSavedView.is_default.is_(True),
        )
    ).all():
        view.is_default = False


def _sync_accounts_for_scope(db: Session, scope: str, account_ids: list[UUID]) -> list[CustomerAccount]:
    query = select(CustomerAccount)
    if scope == "SELECTED":
        if not account_ids:
            raise HTTPException(status_code=422, detail="Выберите хотя бы один аккаунт")
        query = query.where(CustomerAccount.id.in_(account_ids))
    elif scope == "WORKING":
        query = query.where(CustomerAccount.work_status == "WORKING")
    accounts = list(db.scalars(query.order_by(CustomerAccount.id)).all())
    if scope == "SELECTED" and len(accounts) != len(set(account_ids)):
        raise HTTPException(status_code=404, detail="Один или несколько аккаунтов не найдены")
    return accounts


def _action_pre_state(campaign_id: UUID, current: dict) -> dict:
    state = dict(current)
    google_campaign_id = state.get("campaign_id")
    if google_campaign_id is not None:
        state["google_campaign_id"] = google_campaign_id
    state["campaign_id"] = str(campaign_id)
    return state
