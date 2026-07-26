from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class AuthType(StrEnum):
    SERVICE_ACCOUNT = "SERVICE_ACCOUNT"
    OAUTH_WEB = "OAUTH_WEB"


class EnvironmentType(StrEnum):
    TEST = "TEST"
    PRODUCTION = "PRODUCTION"


class ConnectionStatus(StrEnum):
    DRAFT = "DRAFT"
    NEEDS_CREDENTIALS = "NEEDS_CREDENTIALS"
    CONNECTED = "CONNECTED"
    VERIFIED = "VERIFIED"
    ERROR = "ERROR"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class UploadStatus(StrEnum):
    DRAFT = "DRAFT"
    PLAN_READY = "PLAN_READY"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class MediaKind(StrEnum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    YOUTUBE = "YOUTUBE"


class MediaStatus(StrEnum):
    READY = "READY"
    INVALID = "INVALID"
    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"


class PlanStatus(StrEnum):
    READY = "READY"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ScheduleStatus(StrEnum):
    DRAFT = "DRAFT"
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    OBSERVATION = "OBSERVATION"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    CANCELLED = "CANCELLED"


class ScheduleRunStatus(StrEnum):
    WAITING = "WAITING"
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    CREATING = "CREATING"
    SUCCEEDED = "SUCCEEDED"
    RETRY_WAIT = "RETRY_WAIT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class ScheduleWaveStatus(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    OBSERVATION = "OBSERVATION"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class User(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.ADMIN.value, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_setup_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    sessions: Mapped[list[UserSession]] = relationship(back_populates="user")


class UserSession(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(160))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class GoogleCredential(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "google_credentials"

    kind: Mapped[str] = mapped_column(String(40), index=True)
    encrypted_payload: Mapped[bytes] = mapped_column(LargeBinary)
    created_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GoogleConnection(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "google_connections"

    name: Mapped[str] = mapped_column(String(160), unique=True)
    login_customer_id: Mapped[str] = mapped_column(String(32), index=True)
    auth_type: Mapped[str] = mapped_column(String(40), index=True)
    environment: Mapped[str] = mapped_column(String(20), default=EnvironmentType.TEST.value)
    developer_token_credential_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_credentials.id"), nullable=True
    )
    auth_credential_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("google_credentials.id"), nullable=True)
    api_version: Mapped[str] = mapped_column(String(24), default="v24.2")
    status: Mapped[str] = mapped_column(String(40), default=ConnectionStatus.DRAFT.value)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(default=60)
    retry_count: Mapped[int] = mapped_column(default=3)

    developer_token_credential: Mapped[GoogleCredential | None] = relationship(
        foreign_keys=[developer_token_credential_id]
    )
    auth_credential: Mapped[GoogleCredential | None] = relationship(foreign_keys=[auth_credential_id])


class MccAccount(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mcc_accounts"
    __table_args__ = (UniqueConstraint("connection_id", "customer_id", name="uq_mcc_connection_customer"),)

    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("google_connections.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    descriptive_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String(80), nullable=True)


class CustomerAccount(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_accounts"
    __table_args__ = (UniqueConstraint("connection_id", "customer_id", name="uq_customer_connection_customer"),)

    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("google_connections.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    manager_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    descriptive_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    can_manage_clients: Mapped[bool] = mapped_column(Boolean, default=False)
    is_test_account: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Job(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), default=JobStatus.QUEUED.value, index=True)
    connection_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("google_connections.id"))
    created_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(180), unique=True, nullable=True)
    progress_current: Mapped[int] = mapped_column(default=0)
    progress_total: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)


class JobEvent(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_events"

    job_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)


class CampaignUpload(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_uploads"

    name: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(40), default=UploadStatus.DRAFT.value, index=True)
    source_type: Mapped[str] = mapped_column(String(20), default="MANUAL")
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_rows: Mapped[list] = mapped_column(JSONB, default=list)
    draft: Mapped[dict] = mapped_column(JSONB, default=dict)
    current_step: Mapped[int] = mapped_column(default=0)
    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_connections.id"), nullable=True, index=True
    )
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class MediaAsset(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "media_assets"
    __table_args__ = (UniqueConstraint("kind", "sha256", name="uq_media_kind_sha256"),)

    kind: Mapped[str] = mapped_column(String(20), index=True)
    source: Mapped[str] = mapped_column(String(30), default="UPLOAD")
    name: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(default=0)
    width: Mapped[int | None] = mapped_column(nullable=True)
    height: Mapped[int | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    aspect_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default=MediaStatus.PENDING.value, index=True)
    validation: Mapped[dict] = mapped_column(JSONB, default=dict)
    youtube_video_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    youtube_upload_resource: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_asset_resources: Mapped[dict] = mapped_column(JSONB, default=dict)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class CampaignTemplate(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_templates"

    name: Mapped[str] = mapped_column(String(180), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    semantic_key: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    current_version: Mapped[int] = mapped_column(default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class DeploymentPlan(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deployment_plans"

    upload_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("campaign_uploads.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_connections.id"), nullable=True, index=True
    )
    launch_batch_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("launch_batches.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(40), default=PlanStatus.READY.value, index=True)
    execution_mode: Mapped[str] = mapped_column(String(20), default="SIMULATION", index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    local_validation: Mapped[dict] = mapped_column(JSONB, default=dict)
    google_validation: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    resource_names: Mapped[list] = mapped_column(JSONB, default=list)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class CampaignTemplateVersion(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_template_versions"
    __table_args__ = (UniqueConstraint("template_id", "version_number", name="uq_template_version"),)

    template_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("campaign_templates.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_campaign_resource: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class LaunchBatch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "launch_batches"

    upload_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("campaign_uploads.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_connections.id"), nullable=True, index=True
    )
    template_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("campaign_template_versions.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    version_number: Mapped[int] = mapped_column(default=1)
    creation_mode: Mapped[str] = mapped_column(String(40), default="FULL_SETUP")
    execution_mode: Mapped[str] = mapped_column(String(20), default="SIMULATION", index=True)
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    generation_seed: Mapped[str] = mapped_column(String(160))
    generation_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    name_pattern: Mapped[str] = mapped_column(String(512))
    builder_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    financial_preview: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class AccountTestBundle(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "account_test_bundles"
    __table_args__ = (UniqueConstraint("launch_batch_id", "customer_id", name="uq_batch_customer_bundle"),)

    launch_batch_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("launch_batches.id", ondelete="CASCADE"), index=True
    )
    customer_account_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("customer_accounts.id"), nullable=True, index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    account_name: Mapped[str] = mapped_column(String(255))
    currency_code: Mapped[str] = mapped_column(String(16))
    time_zone: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    campaigns_count: Mapped[int] = mapped_column(default=1)
    override_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BudgetGenerationConfig(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "budget_generation_configs"

    launch_batch_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("launch_batches.id", ondelete="CASCADE"), unique=True, index=True
    )
    mode: Mapped[str] = mapped_column(String(40), default="FIXED")
    distribution: Mapped[str] = mapped_column(String(40), default="BALANCED_RANDOM")
    fixed_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    minimum_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    maximum_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    step_micros: Mapped[int] = mapped_column(BigInteger, default=1_000_000)
    decimal_places: Mapped[int] = mapped_column(default=2)
    allow_repeats: Mapped[bool] = mapped_column(Boolean, default=True)
    seed: Mapped[str] = mapped_column(String(160))
    manual_values: Mapped[list] = mapped_column(JSONB, default=list)
    per_currency: Mapped[dict] = mapped_column(JSONB, default=dict)


class CampaignInstance(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_instances"
    __table_args__ = (
        UniqueConstraint("account_test_bundle_id", "campaign_sequence", name="uq_bundle_campaign_sequence"),
        UniqueConstraint("launch_batch_id", "campaign_name", name="uq_batch_campaign_name"),
        UniqueConstraint("deployment_key", name="uq_campaign_instance_deployment_key"),
    )

    launch_batch_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("launch_batches.id", ondelete="CASCADE"), index=True
    )
    account_test_bundle_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("account_test_bundles.id", ondelete="CASCADE"), index=True
    )
    deployment_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("deployment_plans.id"), nullable=True, index=True
    )
    template_version_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("campaign_template_versions.id"), nullable=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    campaign_sequence: Mapped[int] = mapped_column()
    campaign_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="DRAFT", index=True)
    policy_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    budget_micros: Mapped[int] = mapped_column(BigInteger)
    currency_code: Mapped[str] = mapped_column(String(16))
    budget_mode: Mapped[str] = mapped_column(String(40))
    generation_seed: Mapped[str] = mapped_column(String(160))
    copy_mode: Mapped[str] = mapped_column(String(40))
    deployment_key: Mapped[str] = mapped_column(String(64), index=True)
    campaign_settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    bidding: Mapped[dict] = mapped_column(JSONB, default=dict)
    targeting: Mapped[dict] = mapped_column(JSONB, default=dict)
    url_settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    texts: Mapped[dict] = mapped_column(JSONB, default=dict)
    creative_assignment: Mapped[dict] = mapped_column(JSONB, default=dict)
    override_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    local_validation: Mapped[dict] = mapped_column(JSONB, default=dict)
    google_validation: Mapped[dict] = mapped_column(JSONB, default=dict)
    resource_names: Mapped[list] = mapped_column(JSONB, default=list)
    request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class DeploymentSchedule(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deployment_schedules"
    __table_args__ = (
        UniqueConstraint("launch_batch_id", "version_number", name="uq_schedule_batch_version"),
        Index("ix_schedule_batch_current", "launch_batch_id", "is_current"),
    )

    deployment_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("deployment_plans.id"), nullable=True, index=True
    )
    upload_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("campaign_uploads.id", ondelete="CASCADE"), index=True
    )
    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_connections.id"), nullable=True, index=True
    )
    launch_batch_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("launch_batches.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("jobs.id"), nullable=True, index=True)
    parent_schedule_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("deployment_schedules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mcc_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(
        String(40), default=ScheduleStatus.DRAFT.value, index=True
    )
    time_zone: Mapped[str] = mapped_column(String(80), default="UTC")
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_accounts_per_hour: Mapped[int] = mapped_column(default=50)
    max_accounts_per_day: Mapped[int] = mapped_column(default=500)
    max_parallel: Mapped[int] = mapped_column(default=1)
    circuit_breaker_threshold: Mapped[int] = mapped_column(default=2)
    consecutive_serious_errors: Mapped[int] = mapped_column(default=0)
    version_number: Mapped[int] = mapped_column(default=1)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    manual_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    pause_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovery_required: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class DeploymentWave(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deployment_waves"
    __table_args__ = (
        UniqueConstraint("schedule_id", "wave_number", name="uq_schedule_wave_number"),
    )

    schedule_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("deployment_schedules.id", ondelete="CASCADE"), index=True
    )
    wave_number: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(
        String(40), default=ScheduleWaveStatus.PLANNED.value, index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observation_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    config: Mapped[dict] = mapped_column(JSONB, default=dict)


class ScheduledAccountRun(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_account_runs"
    __table_args__ = (
        UniqueConstraint("schedule_id", "account_test_bundle_id", name="uq_schedule_bundle_run"),
        Index("ix_scheduled_runs_due", "status", "scheduled_for", "next_retry_at"),
    )

    schedule_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("deployment_schedules.id", ondelete="CASCADE"), index=True
    )
    wave_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("deployment_waves.id", ondelete="CASCADE"), index=True
    )
    deployment_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("deployment_plans.id"), nullable=True, index=True
    )
    account_test_bundle_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("account_test_bundles.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    account_name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column()
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actual_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    campaigns_count: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(
        String(40), default=ScheduleRunStatus.WAITING.value, index=True
    )
    attempts: Mapped[int] = mapped_column(default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deployment_key: Mapped[str] = mapped_column(String(64), index=True)
    resource_names: Mapped[list] = mapped_column(JSONB, default=list)
    request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    structured_error: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class ScheduleEvent(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedule_events"

    schedule_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("deployment_schedules.id", ondelete="CASCADE"), index=True
    )
    wave_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("deployment_waves.id", ondelete="CASCADE"), nullable=True, index=True
    )
    account_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("scheduled_account_runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)


class CampaignInstanceOverride(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_instance_overrides"

    launch_batch_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("launch_batches.id", ondelete="CASCADE"), index=True
    )
    account_test_bundle_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("account_test_bundles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    campaign_instance_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("campaign_instances.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scope: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class CreativeAssignment(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "creative_assignments"

    campaign_instance_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("campaign_instances.id", ondelete="CASCADE"), index=True
    )
    media_asset_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("media_assets.id"), nullable=True, index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    role: Mapped[str] = mapped_column(String(40))
    position: Mapped[int] = mapped_column(default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    google_resource_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assignment: Mapped[dict] = mapped_column(JSONB, default=dict)


class PerformanceSnapshot(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "performance_snapshots"

    campaign_instance_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("campaign_instances.id", ondelete="CASCADE"), index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    account_time_zone: Mapped[str] = mapped_column(String(80))
    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_micros: Mapped[int] = mapped_column(BigInteger, default=0)
    conversions: Mapped[float] = mapped_column(Float, default=0)
    conversion_value: Mapped[float] = mapped_column(Float, default=0)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)


class CampaignStatusAction(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_status_actions"

    account_test_bundle_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("account_test_bundles.id", ondelete="CASCADE"), index=True
    )
    campaign_instance_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("campaign_instances.id", ondelete="CASCADE"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(40))
    previous_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    requested_status: Mapped[str] = mapped_column(String(40))
    execution_mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(40), default="QUEUED", index=True)
    selected_instance_ids: Mapped[list] = mapped_column(JSONB, default=list)
    request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    resource_names: Mapped[list] = mapped_column(JSONB, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ApplicationSetting(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)


class OAuthAuthorization(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "oauth_authorizations"

    state_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("google_connections.id", ondelete="CASCADE"), index=True
    )
    redirect_uri: Mapped[str] = mapped_column(String(512))
    code_verifier_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class ModerationRecord(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "moderation_records"
    __table_args__ = (UniqueConstraint("customer_id", "resource_name", name="uq_moderation_customer_resource"),)

    plan_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("deployment_plans.id"), nullable=True)
    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_connections.id"), nullable=True, index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    resource_name: Mapped[str] = mapped_column(String(255))
    approval_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    policy_topics: Mapped[list] = mapped_column(JSONB, default=list)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MetricSnapshot(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "metric_snapshots"

    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_connections.id"), nullable=True, index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    snapshot_date: Mapped[str] = mapped_column(String(10), index=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)


class FinanceProfile(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "finance_profiles"

    name: Mapped[str] = mapped_column(String(160), unique=True)
    provider: Mapped[str] = mapped_column(String(40), default="BROCARD")
    status: Mapped[str] = mapped_column(String(40), default="NOT_CONFIGURED", index=True)
    credential_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("google_credentials.id"), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class FinanceSnapshot(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "finance_snapshots"

    profile_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("finance_profiles.id", ondelete="CASCADE"), index=True)
    balance: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(16), default="USD")
    cards_total: Mapped[int] = mapped_column(default=0)
    cards_active: Mapped[int] = mapped_column(default=0)
    provider_payload: Mapped[dict] = mapped_column(JSONB, default=dict)


class Notification(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    severity: Mapped[str] = mapped_column(String(20), default="INFO", index=True)
    title: Mapped[str] = mapped_column(String(180))
    message: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(UuidPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)


Index("ix_customer_accounts_connection_manager", CustomerAccount.connection_id, CustomerAccount.manager_customer_id)
