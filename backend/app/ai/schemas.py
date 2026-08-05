from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import AccountWorkStatus, AiAuthorityMode, GoogleConnectionMode


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AiScope(StrictModel):
    connection_ids: list[UUID] = Field(default_factory=list, max_length=20)
    mcc_ids: list[UUID] = Field(default_factory=list, max_length=100)
    geo_ids: list[UUID] = Field(default_factory=list, max_length=100)
    account_ids: list[UUID] = Field(default_factory=list, max_length=500)
    campaign_ids: list[UUID] = Field(default_factory=list, max_length=500)
    period: Literal["today", "yesterday", "3d", "7d", "30d", "custom"] = "7d"
    start_date: date | None = None
    end_date: date | None = None
    metric_source: Literal["GOOGLE_ADS", "KEITARO", "BROCARD", "BUSINESS"] = "GOOGLE_ADS"
    currency: str | None = Field(default=None, max_length=16)

    @model_validator(mode="after")
    def validate_period(self) -> AiScope:
        if self.period == "custom" and (self.start_date is None or self.end_date is None):
            raise ValueError("Для произвольного периода нужны обе даты")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("Начальная дата не может быть позже конечной")
        return self


class ConversationCreateIn(StrictModel):
    title: str = Field(default="Новый диалог", min_length=1, max_length=180)
    authority_mode: AiAuthorityMode = AiAuthorityMode.READ_ONLY
    google_environment: GoogleConnectionMode = GoogleConnectionMode.SIMULATION
    scope: AiScope = Field(default_factory=AiScope)
    locale: Literal["ru", "en"] = "ru"
    time_zone: str = Field(default="Europe/Moscow", max_length=80)


class ConversationPatchIn(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    authority_mode: AiAuthorityMode | None = None
    google_environment: GoogleConnectionMode | None = None
    scope: AiScope | None = None
    archived: bool | None = None


class AiMessageIn(StrictModel):
    content: str = Field(min_length=1, max_length=20_000)
    model_profile: Literal["FAST", "BALANCED", "DEEP"] = "BALANCED"
    idempotency_key: str = Field(min_length=16, max_length=180)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Сообщение не может быть пустым")
        return normalized


class ResolvedScopeInfo(StrictModel):
    connection_ids: list[str]
    mcc_ids: list[str]
    geo_ids: list[str]
    account_ids: list[str]
    campaign_ids: list[str]
    metric_source: str = "GOOGLE_ADS"
    currency: str | None = None
    label: str


class PeriodInfo(StrictModel):
    preset: str
    start_date: date | None
    end_date: date | None


class SourceReference(StrictModel):
    provider: str
    semantic_metric: str
    attribution: str
    scope: ResolvedScopeInfo
    period: PeriodInfo
    timezone: str
    original_currency: str | None
    observed_at: datetime | None
    synced_at: datetime | None
    freshness: str
    freshness_age_seconds: int | None
    completeness: str
    warnings: list[str]
    tool_version: str


class EvidenceItem(StrictModel):
    label: str
    value: str
    source_index: int | None
    object_type: str | None
    object_id: str | None


class Finding(StrictModel):
    title: str
    detail: str
    severity: Literal["INFO", "SUCCESS", "WARNING", "ERROR"]
    condition: str
    conclusion: str
    confidence: float = Field(ge=0, le=1)
    evidence_indexes: list[int]


class CurrencyGroup(StrictModel):
    currency_code: str
    cost_micros: int | None
    conversion_value: float | None
    accounts: int


class TableColumn(StrictModel):
    key: str
    label: str
    format: Literal["TEXT", "NUMBER", "MONEY", "PERCENT", "DATE", "STATUS"]


class TableCell(StrictModel):
    key: str
    value: str
    numeric_value: float | None
    currency_code: str | None


class TableRow(StrictModel):
    object_type: str | None
    object_id: str | None
    cells: list[TableCell] = Field(max_length=20)


class TableBlock(StrictModel):
    title: str
    columns: list[TableColumn] = Field(max_length=20)
    rows: list[TableRow] = Field(max_length=100)


class ChartPoint(StrictModel):
    label: str
    value: float


class ChartSeries(StrictModel):
    name: str
    color: str
    points: list[ChartPoint] = Field(max_length=100)


class ChartBlock(StrictModel):
    title: str
    kind: Literal["BAR", "LINE"]
    unit: str
    series: list[ChartSeries] = Field(max_length=8)


class ObjectLink(StrictModel):
    label: str
    path: str
    object_type: str
    object_id: str

    @field_validator("path")
    @classmethod
    def internal_paths_only(cls, value: str) -> str:
        if not value.startswith("/") or value.startswith("//"):
            raise ValueError("Разрешены только внутренние ссылки Axyro")
        return value


class DraftReference(StrictModel):
    draft_id: str
    draft_type: str
    status: str
    expires_at: datetime
    editor_path: str


class AiStructuredAnswer(StrictModel):
    answer: str
    resolved_scope: ResolvedScopeInfo
    period: PeriodInfo
    timezones: list[str]
    sources: list[SourceReference]
    freshness: str
    completeness: str
    currency_groups: list[CurrencyGroup]
    findings: list[Finding]
    evidence: list[EvidenceItem]
    exact_backend_condition: str
    conclusion: str
    confidence: float = Field(ge=0, le=1)
    caveats: list[str]
    warnings: list[str]
    tables: list[TableBlock] = Field(max_length=4)
    charts: list[ChartBlock] = Field(max_length=4)
    object_links: list[ObjectLink] = Field(max_length=20)
    draft: DraftReference | None


class EmptyArgs(StrictModel):
    pass


class AccountFilterArgs(StrictModel):
    account_ids: list[UUID] = Field(default_factory=list, max_length=500)
    connection_ids: list[UUID] = Field(default_factory=list, max_length=20)
    mcc_ids: list[UUID] = Field(default_factory=list, max_length=100)
    geo_ids: list[UUID] = Field(default_factory=list, max_length=100)
    work_statuses: list[AccountWorkStatus] = Field(default_factory=list, max_length=8)
    google_statuses: list[str] = Field(default_factory=list, max_length=20)
    activity_statuses: list[str] = Field(default_factory=list, max_length=20)
    problem_states: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=30)
    currency: str | None = Field(default=None, max_length=16)
    period: Literal["today", "yesterday", "3d", "7d", "30d", "custom"] = "7d"
    start_date: date | None = None
    end_date: date | None = None
    freshness: list[str] = Field(default_factory=list, max_length=10)
    cost_min_micros: int | None = Field(default=None, ge=0)
    impressions_min: int | None = Field(default=None, ge=0)
    clicks_min: int | None = Field(default=None, ge=0)
    conversions_min: float | None = Field(default=None, ge=0)
    registrations_min: float | None = Field(default=None, ge=0)
    deposits_min: float | None = Field(default=None, ge=0)
    sort_by: Literal[
        "name",
        "cost",
        "impressions",
        "clicks",
        "ctr",
        "cpc",
        "conversions",
        "registrations",
        "deposits",
        "cpa_registration",
        "cpa_deposit",
        "roas",
        "last_sync_success_at",
    ] = "name"
    direction: Literal["asc", "desc"] = "asc"
    grouping: Literal["none", "geo", "mcc", "status", "currency"] = "none"
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10_000)


class ComparePeriodsArgs(StrictModel):
    account_ids: list[UUID] = Field(default_factory=list, max_length=100)
    first_start: date
    first_end: date
    second_start: date
    second_end: date


class EntityIdArgs(StrictModel):
    entity_id: UUID


class CampaignListArgs(StrictModel):
    account_ids: list[UUID] = Field(default_factory=list, max_length=100)
    campaign_ids: list[UUID] = Field(default_factory=list, max_length=500)
    statuses: list[str] = Field(default_factory=list, max_length=20)
    search: str | None = Field(default=None, max_length=300)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10_000)


class ChangeHistoryArgs(StrictModel):
    account_ids: list[UUID] = Field(default_factory=list, max_length=100)
    campaign_ids: list[UUID] = Field(default_factory=list, max_length=100)
    hours: int = Field(default=24, ge=1, le=2160)
    limit: int = Field(default=50, ge=1, le=100)


class PlansSchedulesArgs(StrictModel):
    connection_ids: list[UUID] = Field(default_factory=list, max_length=20)
    statuses: list[str] = Field(default_factory=list, max_length=30)
    limit: int = Field(default=50, ge=1, le=100)


class RefreshArgs(StrictModel):
    account_ids: list[UUID] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=3, max_length=300)
    idempotency_key: str = Field(min_length=16, max_length=180)


class AccountNoteDraftArgs(StrictModel):
    account_ids: list[UUID] = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=20_000)
    pinned: bool = False


class WorkStatusDraftArgs(StrictModel):
    account_ids: list[UUID] = Field(min_length=1, max_length=100)
    work_status: AccountWorkStatus
    reason: str = Field(min_length=1, max_length=1000)


class TagsDraftArgs(StrictModel):
    account_ids: list[UUID] = Field(min_length=1, max_length=100)
    add_tags: list[str] = Field(default_factory=list, max_length=20)
    remove_tags: list[str] = Field(default_factory=list, max_length=20)


class SavedViewDraftArgs(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    filters: AccountFilterArgs


class RuleCondition(StrictModel):
    field: str = Field(min_length=1, max_length=120)
    operator: Literal["gt", "gte", "lt", "lte", "eq", "neq"]
    value: float | int | str
    source: str = Field(default="GOOGLE_ADS", max_length=40)


class RuleConditionGroup(StrictModel):
    logic: Literal["AND", "OR"] = "AND"
    conditions: list[RuleCondition | RuleConditionGroup] = Field(min_length=1, max_length=20)


class RuleDraftArgs(StrictModel):
    name: str = Field(min_length=2, max_length=160)
    scope: AccountFilterArgs
    logic: Literal["AND", "OR"] = "AND"
    conditions: list[RuleCondition | RuleConditionGroup] = Field(min_length=1, max_length=20)
    actions: list[Literal["NOTIFY", "PROPOSE_PAUSE", "PROPOSE_ENABLE", "PROPOSE_BUDGET"]] = Field(
        min_length=1, max_length=10
    )
    explanation: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_condition_tree(self) -> RuleDraftArgs:
        def count(items: list[RuleCondition | RuleConditionGroup], depth: int) -> int:
            if depth > 4:
                raise ValueError("Глубина групп условий не может превышать 4")
            total = 0
            for item in items:
                total += count(item.conditions, depth + 1) if isinstance(item, RuleConditionGroup) else 1
            return total

        if count(self.conditions, 1) > 20:
            raise ValueError("В правиле разрешено не более 20 условий")
        return self


class DemandGenPlanDraftArgs(StrictModel):
    upload_id: UUID
    connection_id: UUID
    account_ids: list[UUID] = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=180)


class ScheduleDraftArgs(StrictModel):
    deployment_plan_id: UUID
    start_at: datetime
    end_at: datetime
    time_zone: str = Field(max_length=80)
    mode: Literal["IMMEDIATE", "EVEN", "WAVES", "MANUAL"]


class ActionSelectionDraftArgs(StrictModel):
    campaign_ids: list[UUID] = Field(min_length=1, max_length=100)
    action_type: Literal["PAUSE", "ENABLE", "SET_BUDGET"]
    amount_micros: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def budget_requires_amount(self) -> ActionSelectionDraftArgs:
        if self.action_type == "SET_BUDGET" and self.amount_micros is None:
            raise ValueError("Для изменения бюджета нужна сумма")
        return self


class ReportDraftArgs(StrictModel):
    title: str = Field(min_length=1, max_length=180)
    account_ids: list[UUID] = Field(default_factory=list, max_length=100)
    period: Literal["today", "yesterday", "3d", "7d", "30d"] = "7d"
    sections: list[Literal["SUMMARY", "PERFORMANCE", "PROBLEMS", "CHANGES", "RECOMMENDATIONS"]] = Field(
        min_length=1, max_length=5
    )


class DraftPatchIn(StrictModel):
    payload: dict[str, Any]
    expected_version: int = Field(ge=1)


class DraftApplyIn(StrictModel):
    expected_version: int = Field(ge=1)
    fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class ModelProfilePatchIn(StrictModel):
    model_id: str | None = Field(default=None, min_length=3, max_length=80)
    reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] | None = None
    verbosity: Literal["low", "medium", "high"] | None = None
    timeout_seconds: int | None = Field(default=None, ge=10, le=180)
    max_input_tokens: int | None = Field(default=None, ge=1000, le=1_000_000)
    max_output_tokens: int | None = Field(default=None, ge=500, le=128_000)
    enabled: bool | None = None
    price_metadata: dict[str, float | str] | None = None
    accepted_eval_version: str | None = Field(default=None, max_length=80)


class GeoAnalyticsOverrideIn(StrictModel):
    scope_type: Literal["MCC", "ACCOUNT", "CAMPAIGN"]
    scope_id: UUID
    profile_id: UUID | None = None
    override_values: dict[str, float | int | str | list[str] | None] = Field(default_factory=dict)
    is_active: bool = True


class UserPreferencePatchIn(StrictModel):
    default_authority_mode: AiAuthorityMode | None = None
    default_environment: GoogleConnectionMode | None = None
    default_model_profile: Literal["FAST", "BALANCED", "DEEP"] | None = None
    default_scope: AiScope | None = None
    locale: Literal["ru", "en"] | None = None
    time_zone: str | None = Field(default=None, max_length=80)


class AiAdminSettingsPatchIn(StrictModel):
    enabled: bool | None = None
    kill_switch: bool | None = None
    deterministic_routing: bool | None = None
    production_read_enabled: bool | None = None
    production_actions_enabled: bool | None = None
    pause_actions_enabled: bool | None = None
    enable_actions_enabled: bool | None = None
    budget_actions_enabled: bool | None = None
    demand_gen_actions_enabled: bool | None = None
    live_rules_enabled: bool | None = None
    daily_soft_budget_usd: float | None = Field(default=None, ge=0)
    daily_hard_budget_usd: float | None = Field(default=None, ge=0)
    monthly_hard_budget_usd: float | None = Field(default=None, ge=0)
    user_daily_hard_budget_usd: float | None = Field(default=None, ge=0)
    user_monthly_hard_budget_usd: float | None = Field(default=None, ge=0)
    provider_circuit_failure_threshold: int | None = Field(default=None, ge=1, le=20)
    provider_circuit_cooldown_seconds: int | None = Field(default=None, ge=30, le=3600)
    retention_days: int | None = Field(default=None, ge=1, le=365)
    second_approval_threshold_micros: int | None = Field(default=None, ge=0)
    openai_api_key: str | None = Field(default=None, min_length=20, max_length=500)
    clear_stored_openai_key: bool = False


class GeoAnalyticsProfileIn(StrictModel):
    scope_type: Literal["GLOBAL", "GEO", "MCC", "ACCOUNT", "CAMPAIGN"]
    scope_id: UUID | None = None
    geo_id: UUID | None = None
    time_zone: str = Field(default="UTC", max_length=80)
    expected_currencies: list[str] = Field(default_factory=list, max_length=10)
    default_reporting_period: Literal["today", "yesterday", "3d", "7d", "30d"] = "7d"
    primary_metric_source: Literal["GOOGLE_ADS", "KEITARO", "BROCARD", "BUSINESS"] = "GOOGLE_ADS"
    target_cpl: float | None = Field(default=None, ge=0)
    target_registration_cpa: float | None = Field(default=None, ge=0)
    target_deposit_cpa: float | None = Field(default=None, ge=0)
    target_roas: float | None = Field(default=None, ge=0)
    max_spend_without_lead: float | None = Field(default=None, ge=0)
    max_spend_without_registration: float | None = Field(default=None, ge=0)
    max_spend_without_deposit: float | None = Field(default=None, ge=0)
    minimum_clicks: int = Field(default=0, ge=0)
    minimum_impressions: int = Field(default=0, ge=0)
    minimum_spend: float = Field(default=0, ge=0)
    conversion_lag_hours: int = Field(default=24, ge=0, le=720)
    alert_thresholds: dict[str, float] = Field(default_factory=dict)
    owner_comment: str | None = Field(default=None, max_length=5000)
    effective_from: datetime | None = None
    effective_until: datetime | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> GeoAnalyticsProfileIn:
        if self.scope_type != "GLOBAL" and self.scope_id is None:
            raise ValueError("Для выбранного уровня нужен scope_id")
        if self.scope_type == "GLOBAL" and self.scope_id is not None:
            raise ValueError("Глобальному профилю scope_id не нужен")
        return self


class MetricSourceMappingIn(StrictModel):
    scope_type: Literal["GLOBAL", "GEO", "MCC", "ACCOUNT", "CAMPAIGN"]
    scope_id: UUID | None = None
    semantic_metric: Literal["LEAD", "REGISTRATION", "DEPOSIT", "PURCHASE", "REVENUE"]
    provider: Literal["GOOGLE_ADS", "KEITARO", "BROCARD", "BUSINESS"]
    source_id: str = Field(min_length=1, max_length=255)
    source_name: str | None = Field(default=None, max_length=255)
    attribution_model: str | None = Field(default=None, max_length=80)
    is_active: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)


class ToolRisk(StrEnum):
    READ = "READ"
    QUEUED_REFRESH = "QUEUED_REFRESH"
    DRAFT = "DRAFT"
    PREVIEW = "PREVIEW"


DRAFT_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "ACCOUNT_NOTE": AccountNoteDraftArgs,
    "WORK_STATUS": WorkStatusDraftArgs,
    "TAGS": TagsDraftArgs,
    "SAVED_VIEW": SavedViewDraftArgs,
    "RULE": RuleDraftArgs,
    "DEMAND_GEN_PLAN": DemandGenPlanDraftArgs,
    "SCHEDULE": ScheduleDraftArgs,
    "ACTION_SELECTION": ActionSelectionDraftArgs,
    "REPORT": ReportDraftArgs,
}


def validate_draft_payload(draft_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    model = DRAFT_PAYLOAD_MODELS.get(draft_type)
    if not model:
        raise ValueError(f"Неизвестный тип AI-черновика: {draft_type}")
    return model.model_validate(payload).model_dump(mode="json")
