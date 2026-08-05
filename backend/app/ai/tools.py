from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import monotonic
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.ai.policy import ToolContext, authorize_tool, effective_ai_settings, require_allowed_ids
from app.ai.schemas import (
    AccountFilterArgs,
    AccountNoteDraftArgs,
    ActionSelectionDraftArgs,
    CampaignListArgs,
    ChangeHistoryArgs,
    ComparePeriodsArgs,
    DemandGenPlanDraftArgs,
    EmptyArgs,
    EntityIdArgs,
    PlansSchedulesArgs,
    RefreshArgs,
    ReportDraftArgs,
    RuleDraftArgs,
    SavedViewDraftArgs,
    ScheduleDraftArgs,
    TagsDraftArgs,
    ToolRisk,
    WorkStatusDraftArgs,
)
from app.ai.security import redact, untrusted_data
from app.control_center.query import sort_account_rows
from app.control_center.service import (
    account_payload,
    campaign_payload,
    monitoring_state_map,
    period_bounds,
    tag_map_for_accounts,
)
from app.core.security import utcnow
from app.db.models import (
    AccountMetricDaily,
    AccountNoteHistory,
    AccountTagHistory,
    AccountWorkStatusHistory,
    AiDraft,
    AiRun,
    ControlCenterAd,
    ControlCenterAdGroup,
    ControlCenterAsset,
    ControlCenterCampaign,
    ControlCenterEvent,
    ControlCenterGoogleChange,
    ControlCenterProblem,
    ControlCenterSavedView,
    ControlCenterSyncItem,
    ControlCenterSyncRun,
    CustomerAccount,
    DeploymentPlan,
    DeploymentSchedule,
    FinanceProfile,
    FinanceSnapshot,
    GeoAnalyticsOverride,
    GeoAnalyticsProfile,
    GeoDefinition,
    GoogleConnection,
    Job,
    JobEvent,
    JobStatus,
    MccAccount,
    MetricSourceMapping,
    UserRole,
)

ToolHandler = Callable[[Session, ToolContext, BaseModel], dict[str, Any]]
ALL_ROLES = frozenset({UserRole.ADMIN.value, UserRole.OPERATOR.value, UserRole.VIEWER.value})
EDIT_ROLES = frozenset({UserRole.ADMIN.value, UserRole.OPERATOR.value})


class ToolExecutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    risk: ToolRisk
    required_roles: frozenset[str]
    handler: ToolHandler
    version: str = "1.0"
    feature_flag: str | None = None

    def openai_schema(self) -> dict[str, Any]:
        schema = _strict_schema(self.args_model.model_json_schema())
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": schema,
            "strict": True,
        }


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec] | None = None) -> None:
        catalog = specs or build_tool_catalog()
        self._specs = {spec.name: spec for spec in catalog}
        forbidden = {
            name for name in self._specs if any(word in name for word in ("confirm", "execute", "mutate", "deploy_now"))
        }
        if forbidden:
            raise ValueError(f"Forbidden model tools: {', '.join(sorted(forbidden))}")

    @property
    def specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def schemas_for(self, context: ToolContext, db: Session) -> list[dict[str, Any]]:
        gates = effective_ai_settings(db)
        result = []
        for spec in self.specs:
            try:
                authorize_tool(
                    context,
                    risk=spec.risk,
                    required_roles=spec.required_roles,
                    feature_flag=spec.feature_flag,
                    gates=gates,
                )
            except PermissionError:
                continue
            result.append(spec.openai_schema())
        return result

    def execute(
        self,
        db: Session,
        context: ToolContext,
        name: str,
        raw_arguments: str | dict[str, Any],
        *,
        call_id: str,
    ) -> tuple[ToolSpec, dict[str, Any], dict[str, Any], int]:
        spec = self._specs.get(name)
        if not spec:
            raise ToolExecutionError("AI_UNKNOWN_TOOL", f"Неизвестный инструмент: {name}")
        authorize_tool(
            context,
            risk=spec.risk,
            required_roles=spec.required_roles,
            feature_flag=spec.feature_flag,
            gates=effective_ai_settings(db),
        )
        try:
            payload = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            arguments = spec.args_model.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ToolExecutionError("AI_INVALID_TOOL_ARGUMENTS", str(exc)) from exc
        started = monotonic()
        result = spec.handler(db, context, arguments)
        duration_ms = int((monotonic() - started) * 1000)
        return spec, redact(arguments.model_dump(mode="json")), redact(result), duration_ms

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)


def build_tool_catalog() -> list[ToolSpec]:
    read = ToolRisk.READ
    return [
        ToolSpec(
            "get_mcc_hierarchy",
            "Получить доступную структуру подключений, MCC и аккаунтов.",
            EmptyArgs,
            read,
            ALL_ROLES,
            _get_mcc_hierarchy,
        ),
        ToolSpec(
            "find_accounts",
            "Найти и отсортировать аккаунты по типизированным фильтрам и готовым backend-метрикам.",
            AccountFilterArgs,
            read,
            ALL_ROLES,
            _find_accounts,
        ),
        ToolSpec(
            "compare_account_periods",
            "Сравнить два периода по аккаунтам без смешивания валют.",
            ComparePeriodsArgs,
            read,
            ALL_ROLES,
            _compare_account_periods,
        ),
        ToolSpec(
            "list_campaigns",
            "Получить кампании разрешённых аккаунтов.",
            CampaignListArgs,
            read,
            ALL_ROLES,
            _list_campaigns,
        ),
        ToolSpec(
            "get_campaign_details",
            "Получить карточку одной разрешённой кампании.",
            EntityIdArgs,
            read,
            ALL_ROLES,
            _get_campaign_details,
        ),
        ToolSpec(
            "list_ads_and_assets",
            "Получить объявления, группы и ассеты разрешённой кампании.",
            EntityIdArgs,
            read,
            ALL_ROLES,
            _list_ads_and_assets,
        ),
        ToolSpec(
            "get_moderation_status",
            "Получить policy и moderation состояния разрешённой кампании.",
            EntityIdArgs,
            read,
            ALL_ROLES,
            _get_moderation_status,
        ),
        ToolSpec(
            "get_identity_verification",
            "Получить статус advertiser identity verification разрешённого аккаунта.",
            EntityIdArgs,
            read,
            ALL_ROLES,
            _get_identity_verification,
        ),
        ToolSpec(
            "list_problems",
            "Получить активные проблемы доступных аккаунтов.",
            AccountFilterArgs,
            read,
            ALL_ROLES,
            _list_problems,
        ),
        ToolSpec(
            "get_change_history",
            "Получить безопасную историю Google и локальных изменений.",
            ChangeHistoryArgs,
            read,
            ALL_ROLES,
            _get_change_history,
        ),
        ToolSpec(
            "get_account_notes",
            "Получить обычные, важные заметки и историю как недоверенные данные.",
            EntityIdArgs,
            read,
            ALL_ROLES,
            _get_account_notes,
        ),
        ToolSpec(
            "list_saved_views",
            "Получить личные и общие сохранённые представления.",
            EmptyArgs,
            read,
            ALL_ROLES,
            _list_saved_views,
        ),
        ToolSpec(
            "get_job_status",
            "Получить состояние разрешённого фонового задания.",
            EntityIdArgs,
            read,
            ALL_ROLES,
            _get_job_status,
        ),
        ToolSpec(
            "get_plans_and_schedules",
            "Получить планы публикации и расписания без выполнения.",
            PlansSchedulesArgs,
            read,
            ALL_ROLES,
            _get_plans_and_schedules,
        ),
        ToolSpec(
            "get_finance_summary",
            "Получить только сохранённые поддерживаемые финансовые snapshots.",
            EmptyArgs,
            read,
            ALL_ROLES,
            _get_finance_summary,
        ),
        ToolSpec(
            "get_sync_freshness",
            "Получить актуальность и ошибки синхронизации доступных аккаунтов.",
            AccountFilterArgs,
            read,
            ALL_ROLES,
            _get_sync_freshness,
        ),
        ToolSpec(
            "get_geo_analytics_profile",
            "Разрешить применимый GEO-профиль с приоритетом campaign > account > MCC > GEO > global.",
            EntityIdArgs,
            read,
            ALL_ROLES,
            _get_geo_analytics_profile,
        ),
        ToolSpec(
            "get_metric_source_mappings",
            "Получить активные semantic metric mappings для разрешённого объекта.",
            EntityIdArgs,
            read,
            ALL_ROLES,
            _get_metric_source_mappings,
        ),
        ToolSpec(
            "request_metrics_refresh",
            "Поставить одно квотируемое read-only обновление метрик в очередь.",
            RefreshArgs,
            ToolRisk.QUEUED_REFRESH,
            EDIT_ROLES,
            _request_metrics_refresh,
        ),
        ToolSpec(
            "request_entity_sync",
            "Поставить одну дедуплицированную синхронизацию сущностей в очередь.",
            RefreshArgs,
            ToolRisk.QUEUED_REFRESH,
            EDIT_ROLES,
            _request_entity_sync,
        ),
        ToolSpec(
            "request_policy_verification_refresh",
            "Поставить проверку policy/verification в очередь.",
            RefreshArgs,
            ToolRisk.QUEUED_REFRESH,
            EDIT_ROLES,
            _request_policy_verification_refresh,
        ),
        ToolSpec(
            "create_account_note_draft",
            "Создать редактируемый черновик заметки; аккаунт не изменяется.",
            AccountNoteDraftArgs,
            ToolRisk.DRAFT,
            EDIT_ROLES,
            _create_draft,
        ),
        ToolSpec(
            "create_work_status_draft",
            "Создать редактируемый черновик локального статуса.",
            WorkStatusDraftArgs,
            ToolRisk.DRAFT,
            EDIT_ROLES,
            _create_draft,
        ),
        ToolSpec(
            "create_tags_draft",
            "Создать редактируемый черновик изменения тегов.",
            TagsDraftArgs,
            ToolRisk.DRAFT,
            EDIT_ROLES,
            _create_draft,
        ),
        ToolSpec(
            "create_saved_view_draft",
            "Создать черновик сохранённого представления.",
            SavedViewDraftArgs,
            ToolRisk.DRAFT,
            EDIT_ROLES,
            _create_draft,
        ),
        ToolSpec(
            "create_rule_draft",
            "Создать только DRY_RUN черновик deterministic правила.",
            RuleDraftArgs,
            ToolRisk.DRAFT,
            EDIT_ROLES,
            _create_draft,
        ),
        ToolSpec(
            "create_demand_gen_plan_draft",
            "Создать черновик Demand Gen plan без публикации.",
            DemandGenPlanDraftArgs,
            ToolRisk.DRAFT,
            EDIT_ROLES,
            _create_draft,
        ),
        ToolSpec(
            "create_schedule_draft",
            "Создать черновик расписания без запуска.",
            ScheduleDraftArgs,
            ToolRisk.DRAFT,
            EDIT_ROLES,
            _create_draft,
        ),
        ToolSpec(
            "create_action_selection_draft",
            "Создать редактируемый набор целей действия без preview и выполнения.",
            ActionSelectionDraftArgs,
            ToolRisk.DRAFT,
            EDIT_ROLES,
            _create_draft,
        ),
        ToolSpec(
            "create_report_draft",
            "Создать сохраняемый черновик отчёта.",
            ReportDraftArgs,
            ToolRisk.DRAFT,
            EDIT_ROLES,
            _create_draft,
        ),
        ToolSpec(
            "preview_campaign_action",
            "Подготовить локально проверенный preview для отдельной кнопки подтверждения пользователя.",
            ActionSelectionDraftArgs,
            ToolRisk.PREVIEW,
            EDIT_ROLES,
            _create_preview_draft,
        ),
        ToolSpec(
            "preview_local_account_change",
            "Подготовить preview локального статуса; применение возможно только отдельной кнопкой.",
            WorkStatusDraftArgs,
            ToolRisk.PREVIEW,
            EDIT_ROLES,
            _create_preview_draft,
        ),
        ToolSpec(
            "preview_demand_gen_plan",
            "Проверить и подготовить preview Demand Gen plan без публикации.",
            DemandGenPlanDraftArgs,
            ToolRisk.PREVIEW,
            EDIT_ROLES,
            _create_preview_draft,
            feature_flag="demand_gen_actions_enabled",
        ),
        ToolSpec(
            "preview_schedule",
            "Подготовить preview расписания без запуска.",
            ScheduleDraftArgs,
            ToolRisk.PREVIEW,
            EDIT_ROLES,
            _create_preview_draft,
        ),
        ToolSpec(
            "preview_rule_activation",
            "Подготовить preview правила; модель не может включить LIVE.",
            RuleDraftArgs,
            ToolRisk.PREVIEW,
            EDIT_ROLES,
            _create_preview_draft,
        ),
    ]


def _get_mcc_hierarchy(db: Session, context: ToolContext, args: BaseModel) -> dict[str, Any]:
    del args
    connections = {
        item.id: item
        for item in db.scalars(
            select(GoogleConnection).where(GoogleConnection.id.in_(context.allowed_connection_ids))
        ).all()
    }
    mcc_rows = list(
        db.scalars(
            select(MccAccount)
            .where(MccAccount.id.in_(context.allowed_mcc_ids))
            .order_by(MccAccount.hierarchy_level, MccAccount.customer_id)
        ).all()
    )
    accounts = list(
        db.scalars(
            select(CustomerAccount)
            .where(CustomerAccount.id.in_(context.allowed_account_ids))
            .order_by(CustomerAccount.customer_id)
        ).all()
    )
    payload = []
    for connection_id, connection in connections.items():
        payload.append(
            {
                "connection_id": str(connection_id),
                "connection_name": connection.name,
                "environment": connection.connection_mode,
                "status": connection.status,
                "mcc": [
                    {
                        "id": str(item.id),
                        "customer_id": item.customer_id,
                        "name": item.descriptive_name,
                        "parent_customer_id": item.parent_customer_id,
                        "level": item.hierarchy_level,
                        "geo_id": str(item.geo_id) if item.geo_id else None,
                        "accounts": [
                            {
                                "id": str(account.id),
                                "customer_id": account.customer_id,
                                "name": account.local_name or account.descriptive_name,
                                "work_status": account.work_status,
                            }
                            for account in accounts
                            if account.primary_mcc_id == item.id
                        ][: context.row_limit],
                    }
                    for item in mcc_rows
                    if item.connection_id == connection_id
                ],
            }
        )
    return _envelope(context, payload, "MCC_HIERARCHY", "GOOGLE_ADS_AND_LOCAL", completeness="COMPLETE")


def _find_accounts(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, AccountFilterArgs)
    selected = set(require_allowed_ids(args.account_ids, context.allowed_account_ids, "account"))
    rows = _account_rows(db, context, selected, args)
    total = len(rows)
    rows = sort_account_rows(rows, [args.sort_by], [args.direction])
    rows = rows[args.offset : args.offset + min(args.limit, context.row_limit)]
    currency_groups: dict[str, int] = defaultdict(int)
    for row in rows:
        cost = (row.get("metrics") or {}).get("cost_micros")
        if cost is not None:
            currency_groups[row.get("currency_code") or "UNKNOWN"] += int(cost)
    data: dict[str, Any] = {
        "items": rows,
        "total": total,
        "limit": min(args.limit, context.row_limit),
        "offset": args.offset,
        "grouping": args.grouping,
        "currency_groups": [
            {"currency_code": code, "cost_micros": amount} for code, amount in sorted(currency_groups.items())
        ],
        "mixed_currencies": len(currency_groups) > 1,
    }
    if args.grouping != "none":
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            key = _group_key(row, args.grouping)
            grouped[key].append(row)
        data["groups"] = [{"key": key, "items": items, "accounts": len(items)} for key, items in grouped.items()]
    return _envelope(context, data, "ACCOUNT_PERFORMANCE", "GOOGLE_ADS_SNAPSHOT")


def _compare_account_periods(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, ComparePeriodsArgs)
    if max((args.first_end - args.first_start).days, (args.second_end - args.second_start).days) > context.date_limit:
        raise ToolExecutionError("AI_DATE_RANGE_LIMIT", "Период превышает разрешённый предел")
    account_ids = require_allowed_ids(args.account_ids, context.allowed_account_ids, "account")
    accounts = {
        item.id: item for item in db.scalars(select(CustomerAccount).where(CustomerAccount.id.in_(account_ids))).all()
    }
    daily = list(
        db.scalars(
            select(AccountMetricDaily).where(
                AccountMetricDaily.account_id.in_(account_ids),
                or_(
                    AccountMetricDaily.metric_date.between(args.first_start, args.first_end),
                    AccountMetricDaily.metric_date.between(args.second_start, args.second_end),
                ),
            )
        ).all()
    )
    output = []
    for account_id, account in accounts.items():
        first = _sum_daily(
            [
                item
                for item in daily
                if item.account_id == account_id and args.first_start <= item.metric_date <= args.first_end
            ]
        )
        second = _sum_daily(
            [
                item
                for item in daily
                if item.account_id == account_id and args.second_start <= item.metric_date <= args.second_end
            ]
        )
        output.append(
            {
                "account_id": str(account_id),
                "name": account.local_name or account.descriptive_name or account.customer_id,
                "currency_code": account.currency_code,
                "first": first,
                "second": second,
                "delta": {key: _delta(first.get(key), second.get(key)) for key in first},
            }
        )
    return _envelope(
        context,
        {"items": output[: context.row_limit], "periods": args.model_dump(mode="json")},
        "ACCOUNT_PERIOD_COMPARISON",
        "GOOGLE_ADS_SNAPSHOT",
    )


def _list_campaigns(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, CampaignListArgs)
    account_ids = set(require_allowed_ids(args.account_ids, context.allowed_account_ids, "account"))
    campaign_ids = set(require_allowed_ids(args.campaign_ids, context.allowed_campaign_ids, "campaign"))
    query = select(ControlCenterCampaign).where(
        ControlCenterCampaign.account_id.in_(account_ids), ControlCenterCampaign.id.in_(campaign_ids)
    )
    if args.statuses:
        query = query.where(ControlCenterCampaign.status.in_([item.upper() for item in args.statuses]))
    if args.search:
        query = query.where(ControlCenterCampaign.name.ilike(f"%{args.search}%"))
    campaigns = list(db.scalars(query.order_by(ControlCenterCampaign.name)).all())
    accounts = {
        item.id: item for item in db.scalars(select(CustomerAccount).where(CustomerAccount.id.in_(account_ids))).all()
    }
    items = [campaign_payload(item, accounts.get(item.account_id)) for item in campaigns]
    return _envelope(
        context,
        {"items": items[args.offset : args.offset + min(args.limit, context.row_limit)], "total": len(items)},
        "CAMPAIGN_CATALOG",
        "GOOGLE_ADS_SNAPSHOT",
    )


def _get_campaign_details(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, EntityIdArgs)
    _require_id(args.entity_id, context.allowed_campaign_ids, "campaign")
    campaign = db.get(ControlCenterCampaign, args.entity_id)
    if not campaign:
        raise ToolExecutionError("AI_NOT_FOUND", "Кампания не найдена")
    account = db.get(CustomerAccount, campaign.account_id)
    return _envelope(context, campaign_payload(campaign, account), "CAMPAIGN_DETAILS", "GOOGLE_ADS_SNAPSHOT")


def _list_ads_and_assets(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, EntityIdArgs)
    _require_id(args.entity_id, context.allowed_campaign_ids, "campaign")
    ad_groups = list(
        db.scalars(select(ControlCenterAdGroup).where(ControlCenterAdGroup.campaign_id == args.entity_id)).all()
    )
    ads = list(db.scalars(select(ControlCenterAd).where(ControlCenterAd.campaign_id == args.entity_id)).all())
    account_id = next((item.account_id for item in ads), None) or next((item.account_id for item in ad_groups), None)
    assets = (
        list(db.scalars(select(ControlCenterAsset).where(ControlCenterAsset.account_id == account_id)).all())
        if account_id
        else []
    )
    data = {
        "ad_groups": [
            {"id": str(item.id), "name": item.name, "status": item.status, "type": item.ad_group_type}
            for item in ad_groups
        ][: context.row_limit],
        "ads": [
            {
                "id": str(item.id),
                "name": item.name,
                "status": item.status,
                "type": item.ad_type,
                "policy_status": item.primary_status,
                "final_urls": [redact(url) for url in (item.final_urls or [])],
            }
            for item in ads
        ][: context.row_limit],
        "assets": [
            {"id": str(item.id), "name": item.name, "type": item.asset_type, "status": item.status} for item in assets
        ][: context.row_limit],
    }
    return _envelope(context, data, "ADS_AND_ASSETS", "GOOGLE_ADS_SNAPSHOT")


def _get_moderation_status(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, EntityIdArgs)
    _require_id(args.entity_id, context.allowed_campaign_ids, "campaign")
    campaign = db.get(ControlCenterCampaign, args.entity_id)
    ads = list(db.scalars(select(ControlCenterAd).where(ControlCenterAd.campaign_id == args.entity_id)).all())
    data = {
        "campaign": {
            "id": str(campaign.id) if campaign else str(args.entity_id),
            "policy_status": campaign.policy_status if campaign else None,
            "policy_issues": redact(campaign.policy_issues if campaign else []),
        },
        "ads": [
            {
                "id": str(item.id),
                "policy_status": item.primary_status,
                "policy_summary": redact(item.policy_summary),
                "disapproval_reasons": redact(item.disapproval_reasons),
            }
            for item in ads
        ][: context.row_limit],
    }
    return _envelope(context, data, "MODERATION_STATUS", "GOOGLE_ADS_SNAPSHOT")


def _get_identity_verification(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, EntityIdArgs)
    _require_id(args.entity_id, context.allowed_account_ids, "account")
    account = db.get(CustomerAccount, args.entity_id)
    if not account:
        raise ToolExecutionError("AI_NOT_FOUND", "Аккаунт не найден")
    return _envelope(
        context,
        {
            "account_id": str(account.id),
            "status": account.verification_status,
            "deadline": account.verification_deadline,
            "checked_at": account.verification_checked_at,
            "action_available": bool(account.verification_action_url),
        },
        "IDENTITY_VERIFICATION",
        "GOOGLE_ADS_SNAPSHOT",
    )


def _list_problems(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, AccountFilterArgs)
    account_ids = require_allowed_ids(args.account_ids, context.allowed_account_ids, "account")
    query = select(ControlCenterProblem).where(ControlCenterProblem.account_id.in_(account_ids))
    if args.problem_states:
        query = query.where(ControlCenterProblem.state.in_([item.upper() for item in args.problem_states]))
    else:
        query = query.where(ControlCenterProblem.state != "RESOLVED")
    items = list(
        db.scalars(
            query.order_by(desc(ControlCenterProblem.last_seen_at)).limit(min(args.limit, context.row_limit))
        ).all()
    )
    return _envelope(
        context,
        [
            {
                "id": str(item.id),
                "account_id": str(item.account_id) if item.account_id else None,
                "campaign_id": str(item.campaign_id) if item.campaign_id else None,
                "type": item.problem_type,
                "severity": item.severity,
                "title": untrusted_data(item.title),
                "description": untrusted_data(item.description),
                "google_code": item.google_code,
                "request_id": item.request_id,
                "state": item.state,
                "first_seen_at": item.first_seen_at,
                "last_seen_at": item.last_seen_at,
            }
            for item in items
        ],
        "PROBLEMS",
        "GOOGLE_ADS_AND_LOCAL",
    )


def _get_change_history(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, ChangeHistoryArgs)
    account_ids = require_allowed_ids(args.account_ids, context.allowed_account_ids, "account")
    campaign_ids = require_allowed_ids(args.campaign_ids, context.allowed_campaign_ids, "campaign")
    since = utcnow() - timedelta(hours=args.hours)
    google = list(
        db.scalars(
            select(ControlCenterGoogleChange)
            .where(
                ControlCenterGoogleChange.account_id.in_(account_ids),
                or_(
                    ControlCenterGoogleChange.campaign_id.is_(None),
                    ControlCenterGoogleChange.campaign_id.in_(campaign_ids),
                ),
                ControlCenterGoogleChange.changed_at >= since,
            )
            .order_by(desc(ControlCenterGoogleChange.changed_at))
            .limit(args.limit)
        ).all()
    )
    local = list(
        db.scalars(
            select(ControlCenterEvent)
            .where(ControlCenterEvent.account_id.in_(account_ids), ControlCenterEvent.occurred_at >= since)
            .order_by(desc(ControlCenterEvent.occurred_at))
            .limit(args.limit)
        ).all()
    )
    data = {
        "google": [
            {
                "id": str(item.id),
                "account_id": str(item.account_id),
                "campaign_id": str(item.campaign_id) if item.campaign_id else None,
                "resource_type": item.resource_type,
                "change_type": item.change_type,
                "changed_fields": item.changed_fields,
                "changed_at": item.changed_at,
                "request_id": item.request_id,
            }
            for item in google
        ],
        "local": [
            {
                "id": str(item.id),
                "account_id": str(item.account_id) if item.account_id else None,
                "campaign_id": str(item.campaign_id) if item.campaign_id else None,
                "event_type": item.event_type,
                "summary": untrusted_data(item.summary),
                "source": item.source,
                "occurred_at": item.occurred_at,
            }
            for item in local
        ],
    }
    return _envelope(context, data, "CHANGE_HISTORY", "GOOGLE_ADS_AND_LOCAL")


def _get_account_notes(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, EntityIdArgs)
    _require_id(args.entity_id, context.allowed_account_ids, "account")
    account = db.get(CustomerAccount, args.entity_id)
    if not account:
        raise ToolExecutionError("AI_NOT_FOUND", "Аккаунт не найден")
    notes = list(
        db.scalars(
            select(AccountNoteHistory)
            .where(AccountNoteHistory.account_id == account.id)
            .order_by(desc(AccountNoteHistory.changed_at))
            .limit(context.row_limit)
        ).all()
    )
    statuses = list(
        db.scalars(
            select(AccountWorkStatusHistory)
            .where(AccountWorkStatusHistory.account_id == account.id)
            .order_by(desc(AccountWorkStatusHistory.changed_at))
            .limit(context.row_limit)
        ).all()
    )
    tags = list(
        db.scalars(
            select(AccountTagHistory)
            .where(AccountTagHistory.account_id == account.id)
            .order_by(desc(AccountTagHistory.changed_at))
            .limit(context.row_limit)
        ).all()
    )
    data = untrusted_data(
        {
            "current_note": account.current_note,
            "pinned_note": account.pinned_note,
            "note_history": [
                {"kind": item.note_kind, "note": item.note, "changed_at": item.changed_at} for item in notes
            ],
            "status_history": [
                {"from": item.previous_status, "to": item.status, "changed_at": item.changed_at} for item in statuses
            ],
            "tag_history": [
                {"tag": item.tag_name, "action": item.action, "changed_at": item.changed_at} for item in tags
            ],
        }
    )
    return _envelope(context, data, "ACCOUNT_NOTES", "LOCAL")


def _list_saved_views(db: Session, context: ToolContext, args: BaseModel) -> dict[str, Any]:
    del args
    items = list(
        db.scalars(
            select(ControlCenterSavedView)
            .where(
                or_(ControlCenterSavedView.owner_user_id == context.user_id, ControlCenterSavedView.is_shared.is_(True))
            )
            .order_by(ControlCenterSavedView.name)
        ).all()
    )
    return _envelope(
        context,
        [
            {
                "id": str(item.id),
                "name": item.name,
                "entity_level": item.entity_level,
                "config": item.config,
                "is_shared": item.is_shared,
            }
            for item in items
        ][: context.row_limit],
        "SAVED_VIEWS",
        "LOCAL",
    )


def _get_job_status(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, EntityIdArgs)
    job = db.get(Job, args.entity_id)
    if not job or (job.created_by_id not in {None, context.user_id} and context.role != UserRole.ADMIN.value):
        raise ToolExecutionError("AI_NOT_FOUND", "Задание не найдено")
    events = list(
        db.scalars(
            select(JobEvent).where(JobEvent.job_id == job.id).order_by(JobEvent.created_at).limit(context.row_limit)
        ).all()
    )
    return _envelope(
        context,
        {
            "id": str(job.id),
            "type": job.type,
            "status": job.status,
            "progress": {"current": job.progress_current, "total": job.progress_total},
            "error": redact(job.error_message),
            "events": [
                {"level": item.level, "message": redact(item.message), "created_at": item.created_at} for item in events
            ],
        },
        "JOB_STATUS",
        "LOCAL",
    )


def _get_plans_and_schedules(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, PlansSchedulesArgs)
    connection_ids = require_allowed_ids(args.connection_ids, context.allowed_connection_ids, "connection")
    plan_query = select(DeploymentPlan).where(DeploymentPlan.connection_id.in_(connection_ids))
    schedule_query = select(DeploymentSchedule).where(DeploymentSchedule.connection_id.in_(connection_ids))
    if args.statuses:
        plan_query = plan_query.where(DeploymentPlan.status.in_(args.statuses))
        schedule_query = schedule_query.where(DeploymentSchedule.status.in_(args.statuses))
    plans = list(db.scalars(plan_query.order_by(desc(DeploymentPlan.created_at)).limit(args.limit)).all())
    schedules = list(db.scalars(schedule_query.order_by(desc(DeploymentSchedule.created_at)).limit(args.limit)).all())
    return _envelope(
        context,
        {
            "plans": [
                {
                    "id": str(item.id),
                    "status": item.status,
                    "mode": item.execution_mode,
                    "validated_at": item.validated_at,
                }
                for item in plans
            ],
            "schedules": [
                {
                    "id": str(item.id),
                    "status": item.status,
                    "mode": item.mode,
                    "start_at": item.start_at,
                    "end_at": item.end_at,
                }
                for item in schedules
            ],
        },
        "PLANS_AND_SCHEDULES",
        "LOCAL",
    )


def _get_finance_summary(db: Session, context: ToolContext, args: BaseModel) -> dict[str, Any]:
    del args
    profiles = list(db.scalars(select(FinanceProfile).order_by(FinanceProfile.name)).all())
    items = []
    for profile in profiles:
        snapshot = db.scalar(
            select(FinanceSnapshot)
            .where(FinanceSnapshot.profile_id == profile.id)
            .order_by(desc(FinanceSnapshot.created_at))
            .limit(1)
        )
        items.append(
            {
                "profile_id": str(profile.id),
                "name": profile.name,
                "provider": profile.provider,
                "status": profile.status,
                "snapshot": (
                    {
                        "balance": snapshot.balance,
                        "currency": snapshot.currency,
                        "cards_total": snapshot.cards_total,
                        "cards_active": snapshot.cards_active,
                        "observed_at": snapshot.created_at,
                    }
                    if snapshot
                    else None
                ),
                "limitations": ["Google Ads API не предоставляет баланс карты или следующий automatic charge."],
            }
        )
    return _envelope(context, items, "FINANCE_SNAPSHOT", "CONFIGURED_FINANCE_PROVIDER")


def _get_sync_freshness(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, AccountFilterArgs)
    account_ids = require_allowed_ids(args.account_ids, context.allowed_account_ids, "account")
    accounts = list(
        db.scalars(
            select(CustomerAccount)
            .where(CustomerAccount.id.in_(account_ids))
            .order_by(CustomerAccount.last_sync_success_at)
        ).all()
    )
    now = utcnow()
    data = [
        {
            "account_id": str(item.id),
            "customer_id": item.customer_id,
            "last_sync_attempt_at": item.last_sync_attempt_at,
            "last_sync_success_at": item.last_sync_success_at,
            "age_seconds": int((now - item.last_sync_success_at).total_seconds())
            if item.last_sync_success_at
            else None,
            "sync_error": redact(item.sync_error),
            "next_sync_at": item.next_sync_at,
        }
        for item in accounts[: min(args.limit, context.row_limit)]
    ]
    return _envelope(context, data, "SYNC_FRESHNESS", "LOCAL")


def _get_geo_analytics_profile(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, EntityIdArgs)
    account: CustomerAccount | None = None
    campaign: ControlCenterCampaign | None = None
    if args.entity_id in context.allowed_campaign_ids:
        campaign = db.get(ControlCenterCampaign, args.entity_id)
        account = db.get(CustomerAccount, campaign.account_id) if campaign else None
    elif args.entity_id in context.allowed_account_ids:
        account = db.get(CustomerAccount, args.entity_id)
    else:
        raise ToolExecutionError("AI_SCOPE_ESCAPE", "Объект не входит в разрешённый scope")
    if not account:
        raise ToolExecutionError("AI_NOT_FOUND", "Аккаунт не найден")
    levels = [
        ("CAMPAIGN", campaign.id if campaign else None),
        ("ACCOUNT", account.id),
        ("MCC", account.primary_mcc_id),
        ("GEO", account.geo_override_id or account.geo_id),
        ("GLOBAL", None),
    ]
    selected_profile: GeoAnalyticsProfile | None = None
    applied_override: GeoAnalyticsOverride | None = None
    applied_level = None
    for level, scope_id in levels:
        if level != "GLOBAL" and scope_id is None:
            continue
        override = (
            db.scalar(
                select(GeoAnalyticsOverride).where(
                    GeoAnalyticsOverride.scope_type == level,
                    GeoAnalyticsOverride.scope_id == scope_id,
                    GeoAnalyticsOverride.is_active.is_(True),
                )
            )
            if scope_id
            else None
        )
        profile = db.get(GeoAnalyticsProfile, override.profile_id) if override and override.profile_id else None
        if not profile:
            query = select(GeoAnalyticsProfile).where(
                GeoAnalyticsProfile.scope_type == level, GeoAnalyticsProfile.is_active.is_(True)
            )
            query = (
                query.where(GeoAnalyticsProfile.scope_id == scope_id)
                if scope_id
                else query.where(GeoAnalyticsProfile.scope_id.is_(None))
            )
            profile = db.scalar(query.order_by(desc(GeoAnalyticsProfile.version)).limit(1))
        if profile:
            selected_profile, applied_override, applied_level = profile, override, level
            break
    if not selected_profile:
        return _envelope(
            context,
            {"configured": False, "reason": "NO_PROFILE"},
            "GEO_ANALYTICS_PROFILE",
            "LOCAL",
            completeness="MISSING",
        )
    payload = _profile_payload(selected_profile)
    if applied_override:
        payload.update(applied_override.override_values or {})
    return _envelope(
        context,
        {
            "configured": True,
            "applied_level": applied_level,
            "profile": payload,
            "override_id": str(applied_override.id) if applied_override else None,
        },
        "GEO_ANALYTICS_PROFILE",
        "LOCAL",
    )


def _get_metric_source_mappings(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    args = _typed(raw, EntityIdArgs)
    scope_ids = {args.entity_id}
    if args.entity_id in context.allowed_account_ids:
        account = db.get(CustomerAccount, args.entity_id)
        if account:
            scope_ids.update(
                item for item in (account.primary_mcc_id, account.geo_override_id or account.geo_id) if item
            )
    elif (
        args.entity_id not in context.allowed_campaign_ids
        and args.entity_id not in context.allowed_geo_ids
        and args.entity_id not in context.allowed_mcc_ids
    ):
        raise ToolExecutionError("AI_SCOPE_ESCAPE", "Объект не входит в разрешённый scope")
    rows = list(
        db.scalars(
            select(MetricSourceMapping)
            .where(
                or_(MetricSourceMapping.scope_id.in_(scope_ids), MetricSourceMapping.scope_id.is_(None)),
                MetricSourceMapping.is_active.is_(True),
            )
            .order_by(MetricSourceMapping.semantic_metric, MetricSourceMapping.provider)
        ).all()
    )
    data = [
        {
            "id": str(item.id),
            "scope_type": item.scope_type,
            "scope_id": str(item.scope_id) if item.scope_id else None,
            "semantic_metric": item.semantic_metric,
            "provider": item.provider,
            "source_id": item.source_id,
            "source_name": item.source_name,
            "attribution_model": item.attribution_model,
        }
        for item in rows[: context.row_limit]
    ]
    return _envelope(context, data, "METRIC_SOURCE_MAPPING", "LOCAL")


def _request_metrics_refresh(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    return _request_refresh(db, context, raw, "AI_METRICS_REFRESH")


def _request_entity_sync(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    return _request_refresh(db, context, raw, "AI_ENTITY_SYNC")


def _request_policy_verification_refresh(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    return _request_refresh(db, context, raw, "AI_POLICY_VERIFICATION_REFRESH")


def _request_refresh(db: Session, context: ToolContext, raw: BaseModel, tool_name: str) -> dict[str, Any]:
    args = _typed(raw, RefreshArgs)
    account_ids = require_allowed_ids(args.account_ids, context.allowed_account_ids, "account")
    idempotency = f"ai-refresh:{tool_name}:{args.idempotency_key}"
    existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency))
    if existing:
        return _envelope(
            context, {"job_id": str(existing.id), "status": existing.status, "reused": True}, "SYNC_JOB", "LOCAL"
        )
    accounts = list(db.scalars(select(CustomerAccount).where(CustomerAccount.id.in_(account_ids))).all())
    connection_ids = {item.connection_id for item in accounts}
    job = Job(
        type=tool_name,
        status=JobStatus.QUEUED.value,
        connection_id=next(iter(connection_ids)) if len(connection_ids) == 1 else None,
        created_by_id=context.user_id,
        idempotency_key=idempotency,
        progress_current=0,
        progress_total=len(accounts),
        payload={"account_ids": [str(item.id) for item in accounts], "reason": args.reason, "source": "AI_ANALYST"},
    )
    db.add(job)
    db.flush()
    sync_run = ControlCenterSyncRun(
        connection_id=job.connection_id,
        job_id=job.id,
        requested_by_id=context.user_id,
        scope="SELECTED",
        mode="READ_ONLY",
        status="QUEUED",
        estimated_operations=len(accounts) * 3,
        actual_operations=0,
        successful_accounts=0,
        failed_accounts=0,
        selection=[str(item.id) for item in accounts],
        cursor={},
        request_ids=[],
        statistics={"source": "AI_ANALYST", "reason": args.reason},
        idempotency_key=idempotency,
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
                cursor_before={},
                cursor_after={},
            )
        )
    db.commit()
    from app.jobs.control_center_tasks import run_control_center_sync

    run_control_center_sync.delay(str(sync_run.id))
    return _envelope(
        context,
        {
            "job_id": str(job.id),
            "sync_run_id": str(sync_run.id),
            "status": "QUEUED",
            "reused": False,
            "estimated_operations": sync_run.estimated_operations,
        },
        "SYNC_JOB",
        "LOCAL",
    )


def _create_draft(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    return _persist_draft(db, context, raw, status="EDITABLE")


def _create_preview_draft(db: Session, context: ToolContext, raw: BaseModel) -> dict[str, Any]:
    result = _persist_draft(db, context, raw, status="READY_FOR_USER_PREVIEW")
    result["data"]["validation"] = {
        "ok": True,
        "local_only": True,
        "google_contacted": False,
        "requires_ui_button": True,
        "target_set_locked": True,
    }
    return result


def _persist_draft(db: Session, context: ToolContext, raw: BaseModel, *, status: str) -> dict[str, Any]:
    payload = raw.model_dump(mode="json")
    account_ids = [UUID(value) for value in payload.get("account_ids", [])]
    campaign_ids = [UUID(value) for value in payload.get("campaign_ids", [])]
    if account_ids:
        require_allowed_ids(account_ids, context.allowed_account_ids, "account")
    if campaign_ids:
        require_allowed_ids(campaign_ids, context.allowed_campaign_ids, "campaign")
    if isinstance(raw, DemandGenPlanDraftArgs):
        _require_id(raw.connection_id, context.allowed_connection_ids, "connection")
    if isinstance(raw, ScheduleDraftArgs):
        plan = db.get(DeploymentPlan, raw.deployment_plan_id)
        if not plan or (plan.connection_id and plan.connection_id not in context.allowed_connection_ids):
            raise ToolExecutionError("AI_SCOPE_ESCAPE", "План не входит в разрешённый scope")
    draft_type = _draft_type(raw)
    fingerprint = hashlib.sha256(
        json.dumps(
            {"type": draft_type, "payload": payload, "scope": context.public_scope()}, sort_keys=True, default=str
        ).encode()
    ).hexdigest()
    source_snapshot = {
        "observed_at": utcnow().isoformat(),
        "scope": context.public_scope(),
        "locked_account_ids": sorted(str(item) for item in account_ids),
        "locked_campaign_ids": sorted(str(item) for item in campaign_ids),
        "target_set_locked": status == "READY_FOR_USER_PREVIEW",
        "tool_schema_version": "axyro-tools-v1",
        "stale_after_minutes": 15,
    }
    run = db.get(AiRun, context.ai_run_id)
    if not run:
        raise ToolExecutionError("AI_RUN_NOT_FOUND", "Запуск AI не найден")
    draft = AiDraft(
        owner_user_id=context.user_id,
        conversation_id=run.conversation_id,
        run_id=context.ai_run_id,
        draft_type=draft_type,
        status=status,
        authority_mode=context.authority_mode,
        google_environment=context.google_environment,
        scope=context.public_scope(),
        payload=payload,
        source_snapshot=source_snapshot,
        fingerprint=fingerprint,
        version=1,
        expires_at=utcnow() + timedelta(minutes=30),
    )
    db.add(draft)
    db.flush()
    return _envelope(
        context,
        {
            "draft_id": str(draft.id),
            "draft_type": draft.draft_type,
            "status": draft.status,
            "fingerprint": draft.fingerprint,
            "expires_at": draft.expires_at,
            "editor_path": f"/ai-analyst?draft={draft.id}",
            "business_data_changed": False,
            "google_contacted": False,
        },
        "AI_DRAFT",
        "LOCAL",
    )


def _account_rows(
    db: Session, context: ToolContext, selected: set[UUID], args: AccountFilterArgs
) -> list[dict[str, Any]]:
    query = select(CustomerAccount).where(CustomerAccount.id.in_(selected))
    if args.connection_ids:
        connection_ids = require_allowed_ids(args.connection_ids, context.allowed_connection_ids, "connection")
        query = query.where(CustomerAccount.connection_id.in_(connection_ids))
    if args.mcc_ids:
        mcc_ids = require_allowed_ids(args.mcc_ids, context.allowed_mcc_ids, "MCC")
        query = query.where(CustomerAccount.primary_mcc_id.in_(mcc_ids))
    if args.geo_ids:
        geo_ids = require_allowed_ids(args.geo_ids, context.allowed_geo_ids, "GEO")
        query = query.where(or_(CustomerAccount.geo_override_id.in_(geo_ids), CustomerAccount.geo_id.in_(geo_ids)))
    if args.work_statuses:
        query = query.where(CustomerAccount.work_status.in_([item.value for item in args.work_statuses]))
    if args.google_statuses:
        query = query.where(CustomerAccount.status.in_([item.upper() for item in args.google_statuses]))
    if args.activity_statuses:
        query = query.where(CustomerAccount.activity_status.in_([item.upper() for item in args.activity_statuses]))
    if args.currency:
        query = query.where(CustomerAccount.currency_code == args.currency.upper())
    accounts = list(db.scalars(query).all())
    start, end = period_bounds(args.period, args.start_date, args.end_date)
    if (end - start).days > context.date_limit:
        raise ToolExecutionError("AI_DATE_RANGE_LIMIT", "Период превышает разрешённый предел")
    metrics = monitoring_state_map(db, [item.id for item in accounts], start, end, "ACCOUNT")
    tags = tag_map_for_accounts(db, [item.id for item in accounts])
    connections = {
        item.id: item
        for item in db.scalars(
            select(GoogleConnection).where(GoogleConnection.id.in_({item.connection_id for item in accounts}))
        ).all()
    }
    mcc = {
        item.id: item
        for item in db.scalars(
            select(MccAccount).where(
                MccAccount.id.in_({item.primary_mcc_id for item in accounts if item.primary_mcc_id})
            )
        ).all()
    }
    effective_geo_ids = {
        item.geo_override_id or item.geo_id for item in accounts if item.geo_override_id or item.geo_id
    }
    geos = {
        item.id: item
        for item in db.scalars(select(GeoDefinition).where(GeoDefinition.id.in_(effective_geo_ids))).all()
    }
    rows = []
    for item in accounts:
        connection = connections.get(item.connection_id)
        rows.append(
            account_payload(
                item,
                connection.name if connection else None,
                tags.get(item.id, []),
                metrics.get(item.id, {}),
                mcc=mcc.get(item.primary_mcc_id) if item.primary_mcc_id else None,
                geo=geos.get(item.geo_override_id or item.geo_id) if item.geo_override_id or item.geo_id else None,
            )
        )
    result = []
    for row in rows:
        values = row.get("metrics") or {}
        row_tags = {str(item.get("name", "")).casefold() for item in row.get("tags") or []}
        if args.tags and not set(item.casefold() for item in args.tags).intersection(row_tags):
            continue
        if args.freshness and values.get("freshness") not in args.freshness:
            continue
        if args.cost_min_micros is not None and (
            values.get("cost_micros") is None or values["cost_micros"] < args.cost_min_micros
        ):
            continue
        if args.impressions_min is not None and (
            values.get("impressions") is None or values["impressions"] < args.impressions_min
        ):
            continue
        if args.clicks_min is not None and (values.get("clicks") is None or values["clicks"] < args.clicks_min):
            continue
        if args.conversions_min is not None and (
            values.get("conversions") is None or values["conversions"] < args.conversions_min
        ):
            continue
        if args.registrations_min is not None and (
            values.get("registrations") is None or values["registrations"] < args.registrations_min
        ):
            continue
        if args.deposits_min is not None and (values.get("deposits") is None or values["deposits"] < args.deposits_min):
            continue
        result.append(row)
    return result


def _envelope(
    context: ToolContext,
    data: Any,
    semantic_metric: str,
    provider: str,
    *,
    completeness: str = "COMPLETE",
    observed_at: datetime | None = None,
    synced_at: datetime | None = None,
    period: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utcnow()
    facts = _provenance_facts(data)
    observed = observed_at or (min(facts["observed_at"]) if facts["observed_at"] else None)
    synced = synced_at or (min(facts["synced_at"]) if facts["synced_at"] else None)
    reference_time = observed or synced
    age_seconds = max(0, int((now - reference_time).total_seconds())) if reference_time else None
    freshness_values = facts["freshness"]
    warnings: list[str] = []
    if "ERROR" in freshness_values:
        freshness = "ERROR"
        warnings.append("SOURCE_SYNC_ERROR")
    elif "STALE" in freshness_values or (age_seconds is not None and age_seconds > 86_400):
        freshness = "STALE"
        warnings.append("STALE_SNAPSHOT")
    elif freshness_values.intersection({"NO_DATA", "MISSING", "UNKNOWN"}):
        freshness = "PARTIAL"
        warnings.append("SOURCE_DATA_INCOMPLETE")
    elif reference_time:
        freshness = "FRESH"
    elif provider in {"LOCAL", "AXYRO_LOCAL"}:
        observed = now
        synced = now
        age_seconds = 0
        freshness = "CURRENT_LOCAL_STATE"
    else:
        freshness = "UNKNOWN"
        warnings.append("SOURCE_TIMESTAMP_UNAVAILABLE")
    effective_completeness = completeness
    if freshness in {"ERROR", "PARTIAL", "UNKNOWN"} and completeness == "COMPLETE":
        effective_completeness = "PARTIAL"
    currencies = sorted(facts["currencies"])
    timezones = sorted(facts["timezones"])
    if len(currencies) > 1:
        warnings.append("MIXED_CURRENCIES_NOT_AGGREGATED")
    if len(timezones) > 1:
        warnings.append("MULTIPLE_ACCOUNT_TIMEZONES")
    return {
        "data": data,
        "provenance": {
            "provider": provider,
            "source": provider,
            "semantic_metric": semantic_metric,
            "attribution": "Stored Axyro snapshot; no source remapping unless explicitly listed.",
            "scope": context.public_scope(),
            "period": period or {"start_date": context.period_start, "end_date": context.period_end},
            "timezone": timezones[0] if len(timezones) == 1 else context.timezone,
            "timezones": timezones or [context.timezone],
            "original_currency": currencies[0] if len(currencies) == 1 else None,
            "currency_groups": currencies,
            "observed_at": observed,
            "synced_at": synced,
            "freshness": freshness,
            "freshness_age_seconds": age_seconds,
            "completeness": effective_completeness,
            "warnings": warnings,
            "tool_version": "1.0",
        },
    }


def _provenance_facts(data: Any) -> dict[str, set[Any]]:
    facts: dict[str, set[Any]] = {
        "observed_at": set(),
        "synced_at": set(),
        "freshness": set(),
        "currencies": set(),
        "timezones": set(),
    }
    observed_keys = {"observed_at", "data_observed_at", "verification_checked_at"}
    synced_keys = {"synced_at", "last_synced_at", "last_sync_success_at"}

    def timestamp(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and "T" in value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for raw_key, item in value.items():
                key = str(raw_key).casefold()
                if key in observed_keys:
                    parsed = timestamp(item)
                    if parsed and parsed.tzinfo is not None:
                        facts["observed_at"].add(parsed)
                elif key in synced_keys:
                    parsed = timestamp(item)
                    if parsed and parsed.tzinfo is not None:
                        facts["synced_at"].add(parsed)
                elif key == "freshness" and item:
                    facts["freshness"].add(str(item).upper())
                elif key in {"currency", "currency_code", "original_currency"} and item:
                    facts["currencies"].add(str(item).upper())
                elif key in {"time_zone", "timezone"} and item:
                    facts["timezones"].add(str(item))
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)
    return facts


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(schema))

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                properties = node.get("properties") or {}
                node["additionalProperties"] = False
                node["required"] = list(properties)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(result)
    return result


def _typed(value: BaseModel, expected: type[BaseModel]) -> Any:
    if not isinstance(value, expected):
        raise ToolExecutionError("AI_INTERNAL_SCHEMA_MISMATCH", expected.__name__)
    return value


def _require_id(value: UUID, allowed: frozenset[UUID], label: str) -> None:
    if value not in allowed:
        raise ToolExecutionError("AI_SCOPE_ESCAPE", f"Недоступный объект: {label}")


def _sum_daily(rows: list[AccountMetricDaily]) -> dict[str, Any]:
    return {
        "impressions": sum(int(item.impressions or 0) for item in rows),
        "clicks": sum(int(item.clicks or 0) for item in rows),
        "cost_micros": sum(int(item.cost_micros or 0) for item in rows),
        "conversions": sum(float(item.conversions or 0) for item in rows),
        "registrations": sum(float(item.registrations or 0) for item in rows)
        if any(item.registration_data_available for item in rows)
        else None,
        "deposits": sum(float(item.deposits or 0) for item in rows)
        if any(item.deposit_data_available for item in rows)
        else None,
    }


def _delta(first: Any, second: Any) -> Any:
    if first is None or second is None:
        return None
    return second - first


def _group_key(row: dict[str, Any], grouping: str) -> str:
    if grouping == "geo":
        return str((row.get("geo") or {}).get("display_name") or "GEO не назначено")
    if grouping == "mcc":
        return str(row.get("mcc_name") or row.get("mcc_customer_id") or "MCC не определён")
    if grouping == "status":
        return str(row.get("work_status") or "UNKNOWN")
    return str(row.get("currency_code") or "UNKNOWN")


def _profile_payload(item: GeoAnalyticsProfile) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "scope_type": item.scope_type,
        "scope_id": str(item.scope_id) if item.scope_id else None,
        "geo_id": str(item.geo_id) if item.geo_id else None,
        "version": item.version,
        "time_zone": item.time_zone,
        "expected_currencies": item.expected_currencies,
        "default_reporting_period": item.default_reporting_period,
        "primary_metric_source": item.primary_metric_source,
        "target_cpl": item.target_cpl,
        "target_registration_cpa": item.target_registration_cpa,
        "target_deposit_cpa": item.target_deposit_cpa,
        "target_roas": item.target_roas,
        "max_spend_without_lead": item.max_spend_without_lead,
        "max_spend_without_registration": item.max_spend_without_registration,
        "max_spend_without_deposit": item.max_spend_without_deposit,
        "minimum_clicks": item.minimum_clicks,
        "minimum_impressions": item.minimum_impressions,
        "minimum_spend": item.minimum_spend,
        "conversion_lag_hours": item.conversion_lag_hours,
        "alert_thresholds": item.alert_thresholds,
        "owner_comment": untrusted_data(item.owner_comment),
    }


def _draft_type(value: BaseModel) -> str:
    mapping = {
        AccountNoteDraftArgs: "ACCOUNT_NOTE",
        WorkStatusDraftArgs: "WORK_STATUS",
        TagsDraftArgs: "TAGS",
        SavedViewDraftArgs: "SAVED_VIEW",
        RuleDraftArgs: "RULE",
        DemandGenPlanDraftArgs: "DEMAND_GEN_PLAN",
        ScheduleDraftArgs: "SCHEDULE",
        ActionSelectionDraftArgs: "ACTION_SELECTION",
        ReportDraftArgs: "REPORT",
    }
    return mapping.get(type(value), type(value).__name__.removesuffix("Args").upper())
