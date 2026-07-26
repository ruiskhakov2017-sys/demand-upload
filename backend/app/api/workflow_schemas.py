from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UploadCreateIn(BaseModel):
    name: str = Field(default="Новая загрузка", min_length=2, max_length=180)
    execution_mode: Literal["SIMULATION", "LIVE"] = "SIMULATION"


class UploadPatchIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    connection_id: UUID | None = None
    current_step: int | None = Field(default=None, ge=0, le=20)
    draft: dict | None = None


class ManualRowsIn(BaseModel):
    rows: list[dict] = Field(min_length=1, max_length=5000)


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    source_type: str
    source_name: str | None
    source_rows: list
    draft: dict
    current_step: int
    connection_id: UUID | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class ImportOut(BaseModel):
    upload: UploadOut
    row_count: int
    columns: list[str]
    preview: list[dict]


class MediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    source: str
    name: str
    sha256: str
    content_type: str | None
    size_bytes: int
    width: int | None
    height: int | None
    duration_seconds: float | None
    aspect_ratio: float | None
    status: str
    validation: dict
    youtube_video_id: str | None
    youtube_upload_resource: str | None
    google_asset_resources: dict
    details: dict
    created_at: datetime
    updated_at: datetime


class YouTubeRegisterIn(BaseModel):
    video_id: str
    name: str | None = Field(default=None, max_length=255)

    @field_validator("video_id")
    @classmethod
    def normalize_video_id(cls, value: str) -> str:
        value = value.strip()
        for marker in ("youtu.be/", "youtube.com/watch?v="):
            if marker in value:
                value = value.split(marker, 1)[1].split("&", 1)[0].split("?", 1)[0]
        if len(value) != 11 or not all(ch.isalnum() or ch in "-_" for ch in value):
            raise ValueError("Нужен корректный YouTube video ID из 11 символов")
        return value


class YouTubeUploadIn(BaseModel):
    connection_id: UUID | None = None
    customer_id: str = Field(min_length=6, max_length=32)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    execution_mode: Literal["SIMULATION", "LIVE"] = "SIMULATION"


class TemplateCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    semantic_key: str | None = Field(default=None, min_length=2, max_length=160)
    payload: dict = Field(default_factory=dict)


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    payload: dict
    semantic_key: str | None
    current_version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PlanBuildIn(BaseModel):
    execution_mode: Literal["SIMULATION", "LIVE"] = "SIMULATION"
    schedule_id: UUID | None = None


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    upload_id: UUID
    connection_id: UUID | None
    launch_batch_id: UUID | None
    status: str
    execution_mode: str
    fingerprint: str
    snapshot: dict
    local_validation: dict
    google_validation: dict
    result: dict
    request_ids: list
    resource_names: list
    validated_at: datetime | None
    confirmed_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PlanValidationOut(BaseModel):
    plan: PlanOut
    ok: bool
    mode: str
    errors: list[dict]
    warnings: list[dict]
    request_ids: list[str]


class PlanConfirmIn(BaseModel):
    confirmation: Literal["CREATE_PAUSED"]
    allow_partial: bool = False


class PlanConfirmOut(BaseModel):
    plan: PlanOut
    job_id: UUID
    reused: bool


class ManualScheduleRunIn(BaseModel):
    account_test_bundle_id: UUID
    scheduled_local: str | None = None
    scheduled_for: datetime | None = None
    wave_number: int = Field(default=1, ge=1, le=1000)


class ScheduleConfigIn(BaseModel):
    mode: Literal["IMMEDIATE", "EVEN", "WAVES", "MANUAL"] = "IMMEDIATE"
    time_zone: str = Field(default="UTC", min_length=1, max_length=80)
    start_local: str | None = None
    end_local: str | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=525_600)
    account_order: list[UUID] = Field(default_factory=list, max_length=500)
    max_accounts_per_hour: int = Field(default=50, ge=1, le=500)
    max_accounts_per_day: int = Field(default=500, ge=1, le=5000)
    max_parallel: int = Field(default=1, ge=1, le=50)
    circuit_breaker_threshold: int = Field(default=2, ge=1, le=100)
    manual_approval: bool = True
    first_wave_size: int = Field(default=5, ge=1, le=500)
    observation_minutes: int = Field(default=720, ge=0, le=525_600)
    next_wave_size: int = Field(default=10, ge=1, le=500)
    between_waves_minutes: int = Field(default=360, ge=0, le=525_600)
    first_wave_spread_minutes: int = Field(default=240, ge=0, le=525_600)
    next_wave_spread_minutes: int = Field(default=480, ge=0, le=525_600)
    retry_max_attempts: int = Field(default=3, ge=1, le=20)
    retry_base_seconds: int = Field(default=60, ge=1, le=86_400)
    recovery_pause_after_seconds: int = Field(default=300, ge=30, le=86_400)
    manual_runs: list[ManualScheduleRunIn] = Field(default_factory=list, max_length=500)


class ScheduleActionIn(BaseModel):
    action: Literal[
        "PAUSE",
        "RESUME",
        "APPROVE_NEXT_WAVE",
        "RUN_NEXT_NOW",
        "RESCHEDULE_REMAINING",
        "MOVE_ACCOUNT",
        "RETRY",
        "CANCEL_SELECTED",
        "CANCEL_FUTURE",
    ]
    confirmation: bool
    run_ids: list[UUID] = Field(default_factory=list, max_length=500)
    shift_minutes: int | None = Field(default=None, ge=-525_600, le=525_600)
    start_local: str | None = None
    end_local: str | None = None
    target_wave_number: int | None = Field(default=None, ge=1, le=1000)
    recovery_strategy: Literal["SEQUENTIAL", "KEEP_TIMES"] = "SEQUENTIAL"


class OAuthStartOut(BaseModel):
    authorization_url: str
    expires_at: datetime


class AlertReadIn(BaseModel):
    read: bool = True


class FinanceProfileIn(BaseModel):
    name: str = Field(default="Brocard", min_length=2, max_length=160)
    api_token: str = Field(min_length=1, max_length=4000)
    api_base_url: str = Field(default="https://private.mybrocard.com", max_length=512)

    @field_validator("api_base_url")
    @classmethod
    def validate_api_base_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("API base URL должен быть HTTPS-адресом без логина и пароля")
        if parsed.query or parsed.fragment:
            raise ValueError("API base URL не должен содержать query или fragment")
        return value.strip().rstrip("/")


class TemplateVersionCreateIn(BaseModel):
    payload: dict
    change_summary: str | None = Field(default=None, max_length=2000)


class TemplateCopyIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    semantic_key: str | None = Field(default=None, min_length=2, max_length=160)


class TemplateFromCampaignIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    semantic_key: str | None = Field(default=None, min_length=2, max_length=160)
    connection_id: UUID
    customer_id: str = Field(min_length=6, max_length=32)
    campaign_resource_name: str = Field(min_length=10, max_length=255)


class TemplateVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    version_number: int
    payload: dict
    change_summary: str | None
    source_campaign_resource: str | None
    created_at: datetime


class BatchAccountIn(BaseModel):
    id: UUID | None = None
    customer_id: str = Field(min_length=6, max_length=32)
    account_name: str = Field(min_length=1, max_length=255)
    currency_code: str = Field(default="USD", min_length=3, max_length=16)
    time_zone: str = Field(default="UTC", min_length=1, max_length=80)
    campaigns_count: int | None = Field(default=None, ge=1, le=500)
    overrides: dict = Field(default_factory=dict)


class BatchGenerateIn(BaseModel):
    batch_name: str = Field(min_length=2, max_length=180)
    execution_mode: Literal["SIMULATION", "LIVE"] = "SIMULATION"
    creation_mode: Literal["FROM_TEMPLATE", "FULL_SETUP", "FROM_EXISTING", "FILE"] = "FULL_SETUP"
    template_id: UUID | None = None
    template_version_id: UUID | None = None
    template_name: str = Field(default="DemandGen", max_length=180)
    template_defaults: dict = Field(default_factory=dict)
    batch_overrides: dict = Field(default_factory=dict)
    accounts: list[BatchAccountIn] = Field(min_length=1, max_length=500)
    campaigns_per_account: int = Field(default=1, ge=1, le=500)
    copy_mode: Literal[
        "EXACT_COPY",
        "SAME_SETTINGS_RANDOM_BUDGET",
        "RANDOM_CREATIVE_SUBSET",
        "ROTATE_CREATIVE_SETS",
        "BIDDING_VARIATIONS",
        "AUDIENCE_VARIATIONS",
        "CUSTOM_MATRIX",
    ] = "EXACT_COPY"
    budget: dict = Field(default_factory=lambda: {"mode": "FIXED", "fixed": 10})
    creative: dict = Field(default_factory=dict)
    name_pattern: str = Field(default="{account_name}_{template_name}_{date}_{sequence}", max_length=512)
    generation_seed: str = Field(default="dgu-seed", min_length=1, max_length=160)
    campaign_overrides: dict = Field(default_factory=dict)
    bidding_variations: list[dict] = Field(default_factory=list)
    audience_variations: list[dict] = Field(default_factory=list)
    custom_matrix: list[dict] = Field(default_factory=list)
    password_confirmation: str | None = Field(default=None, max_length=1024)


class CampaignInstancePatchIn(BaseModel):
    campaign_name: str | None = Field(default=None, min_length=1, max_length=255)
    budget: float | None = Field(default=None, gt=0)
    included: bool | None = None
    campaign_settings: dict | None = None
    bidding: dict | None = None
    targeting: dict | None = None
    url_settings: dict | None = None
    texts: dict | None = None
    creative_assignment: dict | None = None
    override_payload: dict | None = None


class CampaignStatusIn(BaseModel):
    action: Literal["ENABLE", "PAUSE"]
    campaign_instance_ids: list[UUID] = Field(default_factory=list, max_length=500)
    confirmation: bool = True
    password_confirmation: str | None = Field(default=None, max_length=1024)


class GuardrailsPatchIn(BaseModel):
    max_campaigns_per_account: int = Field(default=50, ge=1, le=1000)
    max_campaigns_per_job: int = Field(default=500, ge=1, le=10000)
    max_parallel_enabled: int = Field(default=20, ge=1, le=1000)
    max_budget_by_currency: dict[str, float] = Field(default_factory=dict)
