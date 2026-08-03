from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

from app.db.models import AccountWorkStatus


class AccountPatchIn(BaseModel):
    local_name: str | None = Field(default=None, max_length=255)
    work_status: AccountWorkStatus | None = None
    current_note: str | None = Field(default=None, max_length=20_000)
    is_pinned: bool | None = None
    geo_override_id: UUID | None = None


class BulkWorkStatusIn(BaseModel):
    account_ids: list[UUID] = Field(min_length=1, max_length=500)
    work_status: AccountWorkStatus


class TagCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#64748b", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("Название тега не может быть пустым")
        return normalized


class SavedViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    entity_level: Literal["ACCOUNT", "CAMPAIGN"] = "ACCOUNT"
    config: dict = Field(default_factory=dict)
    is_default: bool = False
    is_shared: bool = False
    description: str | None = Field(default=None, max_length=2_000)


class SavedViewPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    config: dict | None = None
    is_default: bool | None = None
    is_shared: bool | None = None
    description: str | None = Field(default=None, max_length=2_000)


class GeoCreateIn(BaseModel):
    iso_code: str = Field(min_length=2, max_length=8, pattern=r"^[A-Za-z0-9_-]+$")
    display_name: str = Field(min_length=2, max_length=120)
    default_currency_code: str | None = Field(default=None, min_length=3, max_length=16, pattern=r"^[A-Za-z]+$")
    default_time_zone: str | None = Field(default=None, max_length=80)
    is_active: bool = True
    color: str = Field(default="#64748b", pattern=r"^#[0-9a-fA-F]{6}$")
    short_label: str | None = Field(default=None, max_length=16)

    @field_validator("iso_code")
    @classmethod
    def normalize_iso_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("default_currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None

    @field_validator("default_time_zone")
    @classmethod
    def validate_time_zone(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Неизвестный часовой пояс IANA") from exc
        return value


class GeoPatchIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    default_currency_code: str | None = Field(default=None, min_length=3, max_length=16, pattern=r"^[A-Za-z]+$")
    default_time_zone: str | None = Field(default=None, max_length=80)
    is_active: bool | None = None
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    short_label: str | None = Field(default=None, max_length=16)

    @field_validator("default_currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None

    @field_validator("default_time_zone")
    @classmethod
    def validate_time_zone(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Неизвестный часовой пояс IANA") from exc
        return value


class MccGeoAssignmentIn(BaseModel):
    geo_id: UUID | None = None


class ConversionActionMappingIn(BaseModel):
    connection_id: UUID
    account_id: UUID | None = None
    semantic_type: Literal["REGISTRATION", "DEPOSIT"]
    resource_name: str = Field(
        min_length=10,
        max_length=255,
        pattern=r"^customers/\d+/conversionActions/\d+$",
    )
    conversion_action_id: str = Field(min_length=1, max_length=40, pattern=r"^\d+$")
    name: str | None = Field(default=None, max_length=255)
    owner_customer_id: str | None = Field(default=None, max_length=32, pattern=r"^\d+$")
    is_cross_account: bool = False
    is_active: bool = True


class SyncEstimateIn(BaseModel):
    scope: Literal["SELECTED", "WORKING", "ALL"]
    account_ids: list[UUID] = Field(default_factory=list, max_length=500)


class SyncStartIn(SyncEstimateIn):
    estimate_token: str


class ActionPreviewIn(BaseModel):
    campaign_ids: list[UUID] = Field(min_length=1, max_length=100)
    action_type: Literal["PAUSE", "ENABLE", "SET_BUDGET"]
    execution_mode: Literal["SIMULATION", "GOOGLE_TEST", "PRODUCTION"] = "SIMULATION"
    amount_micros: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_budget(self) -> ActionPreviewIn:
        if self.action_type == "SET_BUDGET" and self.amount_micros is None:
            raise ValueError("Для изменения бюджета нужна абсолютная сумма")
        return self


class ActionConfirmIn(BaseModel):
    confirmation_token: str = Field(min_length=20, max_length=256)


class ProblemPatchIn(BaseModel):
    state: Literal["NEW", "SEEN", "RESOLVED"]


class RuleCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    enabled: bool = False
    mode: Literal["DRY_RUN"] = "DRY_RUN"
    scope: dict = Field(default_factory=dict)
    condition_logic: Literal["AND", "OR"] = "AND"
    conditions: list[dict] = Field(default_factory=list, max_length=20)
    actions: list[dict] = Field(default_factory=list, max_length=10)
    safeguards: dict = Field(default_factory=dict)
    cooldown_minutes: int = Field(default=1440, ge=5, le=43_200)
    max_actions_per_run: int = Field(default=10, ge=1, le=100)
    max_actions_per_day: int = Field(default=25, ge=1, le=1000)
    priority: int = Field(default=100, ge=1, le=10_000)
    schedule: dict = Field(default_factory=lambda: {"interval_minutes": 15})
    max_budget_change_percent: float | None = Field(default=20, gt=0, le=100)

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, value: list[dict]) -> list[dict]:
        allowed = {
            "NOTIFY",
            "PAUSE",
            "PROPOSE_PAUSE",
            "ENABLE",
            "PROPOSE_ENABLE",
            "SET_BUDGET",
            "PROPOSE_BUDGET",
        }
        unknown = {
            str(action.get("type") or "").upper()
            for action in value
        } - allowed
        if unknown:
            raise ValueError(f"Неподдерживаемые действия: {', '.join(sorted(unknown))}")
        return value


class RulePatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    enabled: bool | None = None
    mode: Literal["DRY_RUN"] | None = None
    scope: dict | None = None
    condition_logic: Literal["AND", "OR"] | None = None
    conditions: list[dict] | None = Field(default=None, max_length=20)
    actions: list[dict] | None = Field(default=None, max_length=10)
    safeguards: dict | None = None
    cooldown_minutes: int | None = Field(default=None, ge=5, le=43_200)
    max_actions_per_run: int | None = Field(default=None, ge=1, le=100)
    max_actions_per_day: int | None = Field(default=None, ge=1, le=1000)
    priority: int | None = Field(default=None, ge=1, le=10_000)
    schedule: dict | None = None
    max_budget_change_percent: float | None = Field(default=None, gt=0, le=100)

    @field_validator("actions")
    @classmethod
    def validate_actions(cls, value: list[dict] | None) -> list[dict] | None:
        if value is None:
            return value
        RuleCreateIn.validate_actions(value)
        return value


class RuleLiveModeIn(BaseModel):
    confirmation: Literal["ENABLE LIVE RULES", "RETURN TO DRY RUN"]


class PeriodQuery(BaseModel):
    period: Literal["today", "yesterday", "3d", "7d", "30d", "custom"] = "7d"
    start_date: date | None = None
    end_date: date | None = None
