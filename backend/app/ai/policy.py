from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.providers import provider_by_id
from app.ai.schemas import AiScope, ToolRisk
from app.control_center.service import period_bounds
from app.core.config import settings
from app.db.models import (
    AiAdminSetting,
    AiAuthorityMode,
    ControlCenterCampaign,
    CustomerAccount,
    GeoDefinition,
    GoogleConnection,
    GoogleConnectionMode,
    MccAccount,
    User,
    UserRole,
)


@dataclass(frozen=True)
class ToolContext:
    user_id: UUID
    role: str
    session_id: UUID
    authority_mode: str
    google_environment: str
    allowed_connection_ids: frozenset[UUID]
    allowed_mcc_ids: frozenset[UUID]
    allowed_geo_ids: frozenset[UUID]
    allowed_account_ids: frozenset[UUID]
    allowed_campaign_ids: frozenset[UUID]
    request_id: str
    ai_run_id: UUID
    locale: str
    timezone: str
    row_limit: int
    date_limit: int
    deadline: datetime
    period_start: date | None
    period_end: date | None
    metric_source: str = "GOOGLE_ADS"
    currency: str | None = None

    def public_scope(self) -> dict[str, Any]:
        return {
            "connection_ids": sorted(str(item) for item in self.allowed_connection_ids),
            "mcc_ids": sorted(str(item) for item in self.allowed_mcc_ids),
            "geo_ids": sorted(str(item) for item in self.allowed_geo_ids),
            "account_ids": sorted(str(item) for item in self.allowed_account_ids),
            "campaign_ids": sorted(str(item) for item in self.allowed_campaign_ids),
            "metric_source": self.metric_source,
            "currency": self.currency,
        }


DEFAULT_ADMIN_SETTINGS: dict[str, Any] = {
    "enabled": True,
    "kill_switch": False,
    "deterministic_routing": False,
    "production_read_enabled": False,
    "production_actions_enabled": False,
    "pause_actions_enabled": False,
    "enable_actions_enabled": False,
    "budget_actions_enabled": False,
    "demand_gen_actions_enabled": False,
    "live_rules_enabled": False,
    "daily_soft_budget_usd": 5.0,
    "daily_hard_budget_usd": 10.0,
    "monthly_hard_budget_usd": 100.0,
    "user_daily_hard_budget_usd": 5.0,
    "user_monthly_hard_budget_usd": 50.0,
    "provider_circuit_failure_threshold": 3,
    "provider_circuit_cooldown_seconds": 300,
    "retention_days": 30,
    "second_approval_threshold_micros": None,
    "circuit_breaker_open": False,
}


def effective_ai_settings(db: Session) -> dict[str, Any]:
    runtime = {
        **DEFAULT_ADMIN_SETTINGS,
        "enabled": settings.ai_enabled,
        "kill_switch": settings.ai_kill_switch,
        "production_read_enabled": settings.ai_production_read_enabled,
        "production_actions_enabled": settings.ai_production_actions_enabled,
        "pause_actions_enabled": settings.ai_pause_actions_enabled,
        "enable_actions_enabled": settings.ai_enable_actions_enabled,
        "budget_actions_enabled": settings.ai_budget_actions_enabled,
        "demand_gen_actions_enabled": settings.ai_demand_gen_actions_enabled,
        "live_rules_enabled": settings.ai_live_rules_enabled,
        "daily_soft_budget_usd": settings.ai_daily_soft_budget_usd,
        "daily_hard_budget_usd": settings.ai_daily_hard_budget_usd,
        "monthly_hard_budget_usd": settings.ai_monthly_hard_budget_usd,
        "user_daily_hard_budget_usd": settings.ai_user_daily_hard_budget_usd,
        "user_monthly_hard_budget_usd": settings.ai_user_monthly_hard_budget_usd,
        "provider_circuit_failure_threshold": settings.ai_provider_circuit_failure_threshold,
        "provider_circuit_cooldown_seconds": settings.ai_provider_circuit_cooldown_seconds,
        "retention_days": settings.ai_retention_days,
    }
    item = db.scalar(select(AiAdminSetting).where(AiAdminSetting.key == "global"))
    if item:
        runtime.update(item.settings or {})
    open_until = runtime.get("provider_circuit_open_until")
    if open_until:
        try:
            parsed = datetime.fromisoformat(str(open_until))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            runtime["circuit_breaker_open"] = bool(runtime.get("circuit_breaker_open")) or parsed > datetime.now(UTC)
        except ValueError:
            runtime["circuit_breaker_open"] = True
    return runtime


def require_ai_available(db: Session) -> dict[str, Any]:
    gates = effective_ai_settings(db)
    if not gates["enabled"]:
        raise HTTPException(status_code=503, detail="AI_DISABLED: AI-аналитик выключен администратором")
    if gates["kill_switch"]:
        raise HTTPException(status_code=503, detail="AI_KILL_SWITCH_ACTIVE: запуски AI временно остановлены")
    if gates.get("circuit_breaker_open"):
        raise HTTPException(status_code=503, detail="AI_CIRCUIT_BREAKER_OPEN: провайдер временно недоступен")
    return gates


def resolve_tool_context(
    db: Session,
    *,
    user: User,
    session_id: UUID,
    scope: AiScope,
    authority_mode: str,
    google_environment: str,
    request_id: str,
    ai_run_id: UUID,
    deadline: datetime,
    locale: str = "ru",
    time_zone: str = "UTC",
) -> ToolContext:
    enforce_mode_for_role(user.role, authority_mode, google_environment, effective_ai_settings(db))
    provider = provider_by_id(scope.metric_source)
    provider_status = provider.status(db) if provider else None
    if not provider_status or not provider_status.enabled:
        explanation = provider_status.explanation if provider_status else "Неизвестный источник данных"
        raise HTTPException(
            status_code=409,
            detail=f"AI_METRIC_SOURCE_UNAVAILABLE: {scope.metric_source}. {explanation}",
        )
    all_connections = set(db.scalars(select(GoogleConnection.id)).all())
    connection_ids = _select_scope("connection", scope.connection_ids, all_connections)
    all_mcc = set(db.scalars(select(MccAccount.id).where(MccAccount.connection_id.in_(connection_ids))).all())
    mcc_ids = _select_scope("MCC", scope.mcc_ids, all_mcc)
    all_geo = set(db.scalars(select(GeoDefinition.id).where(GeoDefinition.is_active.is_(True))).all())
    geo_ids = _select_scope("GEO", scope.geo_ids, all_geo)
    account_query = select(CustomerAccount.id).where(CustomerAccount.connection_id.in_(connection_ids))
    if scope.mcc_ids:
        account_query = account_query.where(CustomerAccount.primary_mcc_id.in_(mcc_ids))
    if scope.geo_ids:
        account_query = account_query.where(
            or_(CustomerAccount.geo_override_id.in_(geo_ids), CustomerAccount.geo_id.in_(geo_ids))
        )
    all_accounts = set(db.scalars(account_query).all())
    account_ids = _select_scope("account", scope.account_ids, all_accounts)
    all_campaigns = set(
        db.scalars(select(ControlCenterCampaign.id).where(ControlCenterCampaign.account_id.in_(account_ids))).all()
    )
    campaign_ids = _select_scope("campaign", scope.campaign_ids, all_campaigns)
    period_start, period_end = period_bounds(scope.period, scope.start_date, scope.end_date)
    if period_start and period_end and (period_end - period_start).days > settings.ai_max_date_range_days:
        raise HTTPException(status_code=422, detail="AI_DATE_RANGE_LIMIT: выбран слишком большой период")
    return ToolContext(
        user_id=user.id,
        role=user.role,
        session_id=session_id,
        authority_mode=authority_mode,
        google_environment=google_environment,
        allowed_connection_ids=frozenset(connection_ids),
        allowed_mcc_ids=frozenset(mcc_ids),
        allowed_geo_ids=frozenset(geo_ids),
        allowed_account_ids=frozenset(account_ids),
        allowed_campaign_ids=frozenset(campaign_ids),
        request_id=request_id,
        ai_run_id=ai_run_id,
        locale=locale,
        timezone=time_zone,
        row_limit=settings.ai_max_rows_per_tool,
        date_limit=settings.ai_max_date_range_days,
        deadline=deadline,
        period_start=period_start,
        period_end=period_end,
        metric_source=scope.metric_source,
        currency=scope.currency,
    )


def enforce_mode_for_role(role: str, authority_mode: str, environment: str, gates: dict[str, Any]) -> None:
    if role == UserRole.VIEWER.value and authority_mode != AiAuthorityMode.READ_ONLY.value:
        raise HTTPException(status_code=403, detail="AI_MODE_FORBIDDEN: VIEWER доступен только READ_ONLY")
    if environment == GoogleConnectionMode.PRODUCTION.value:
        if not gates.get("production_read_enabled"):
            raise HTTPException(status_code=409, detail="AI_PRODUCTION_READ_LOCKED: Production-чтение ещё не принято")
        if authority_mode != AiAuthorityMode.READ_ONLY.value and not gates.get("production_actions_enabled"):
            raise HTTPException(status_code=409, detail="AI_PRODUCTION_ACTIONS_LOCKED: Production-действия выключены")


def authorize_tool(
    context: ToolContext,
    *,
    risk: ToolRisk,
    required_roles: frozenset[str],
    feature_flag: str | None,
    gates: dict[str, Any],
) -> None:
    if context.role not in required_roles:
        raise PermissionError("AI_TOOL_ROLE_FORBIDDEN")
    if risk == ToolRisk.DRAFT and context.authority_mode == AiAuthorityMode.READ_ONLY.value:
        raise PermissionError("AI_DRAFT_MODE_REQUIRED")
    if risk == ToolRisk.PREVIEW and context.authority_mode != AiAuthorityMode.CONFIRM_REQUIRED.value:
        raise PermissionError("AI_CONFIRM_REQUIRED_MODE_REQUIRED")
    if risk == ToolRisk.QUEUED_REFRESH and context.role == UserRole.VIEWER.value:
        raise PermissionError("AI_REFRESH_ROLE_FORBIDDEN")
    if feature_flag and not gates.get(feature_flag, False):
        raise PermissionError(f"AI_FEATURE_LOCKED:{feature_flag}")
    if context.google_environment == GoogleConnectionMode.PRODUCTION.value:
        if risk == ToolRisk.READ and not gates.get("production_read_enabled"):
            raise PermissionError("AI_PRODUCTION_READ_LOCKED")
        if risk in {ToolRisk.DRAFT, ToolRisk.PREVIEW} and not gates.get("production_actions_enabled"):
            raise PermissionError("AI_PRODUCTION_ACTIONS_LOCKED")


def require_allowed_ids(values: list[UUID], allowed: frozenset[UUID], label: str) -> list[UUID]:
    selected = values or list(allowed)
    escaped = set(selected) - set(allowed)
    if escaped:
        raise PermissionError(f"AI_SCOPE_ESCAPE:{label}")
    return selected


def _select_scope(label: str, requested: list[UUID], available: set[UUID]) -> set[UUID]:
    if not requested:
        return available
    escaped = set(requested) - available
    if escaped:
        raise HTTPException(status_code=403, detail=f"AI_SCOPE_ESCAPE: недоступный {label}")
    return set(requested)
