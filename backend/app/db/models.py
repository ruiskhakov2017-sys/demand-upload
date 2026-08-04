from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
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


class GoogleConnectionMode(StrEnum):
    SIMULATION = "SIMULATION"
    GOOGLE_TEST = "GOOGLE_TEST"
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


class AccountWorkStatus(StrEnum):
    PREPARATION = "PREPARATION"
    READY = "READY"
    WORKING = "WORKING"
    MANUAL_PAUSE = "MANUAL_PAUSE"
    PROBLEM = "PROBLEM"
    APPEAL = "APPEAL"
    ARCHIVED = "ARCHIVED"
    DO_NOT_USE = "DO_NOT_USE"


class AiAuthorityMode(StrEnum):
    READ_ONLY = "READ_ONLY"
    DRAFT_ONLY = "DRAFT_ONLY"
    CONFIRM_REQUIRED = "CONFIRM_REQUIRED"


class AiRunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


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
    time_zone: Mapped[str] = mapped_column(String(80), default="Europe/Moscow")

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
    connection_mode: Mapped[str] = mapped_column(String(24), default=GoogleConnectionMode.PRODUCTION.value, index=True)
    developer_token_credential_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_credentials.id"), nullable=True
    )
    auth_credential_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("google_credentials.id"), nullable=True)
    oauth_client_credential_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_credentials.id"), nullable=True
    )
    oauth_refresh_credential_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_credentials.id"), nullable=True
    )
    api_version: Mapped[str] = mapped_column(String(24), default="v24.2")
    status: Mapped[str] = mapped_column(String(40), default=ConnectionStatus.DRAFT.value)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_hierarchy_root_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    hierarchy_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hierarchy_request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    created_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(default=60)
    retry_count: Mapped[int] = mapped_column(default=3)
    sync_failure_count: Mapped[int] = mapped_column(Integer, default=0)
    sync_circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    developer_token_credential: Mapped[GoogleCredential | None] = relationship(
        foreign_keys=[developer_token_credential_id]
    )
    auth_credential: Mapped[GoogleCredential | None] = relationship(foreign_keys=[auth_credential_id])
    oauth_client_credential: Mapped[GoogleCredential | None] = relationship(foreign_keys=[oauth_client_credential_id])
    oauth_refresh_credential: Mapped[GoogleCredential | None] = relationship(foreign_keys=[oauth_refresh_credential_id])


class GeoDefinition(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "geo_definitions"

    iso_code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), index=True)
    default_currency_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    default_time_zone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    color: Mapped[str] = mapped_column(String(20), default="#64748b")
    short_label: Mapped[str | None] = mapped_column(String(16), nullable=True)


class MccAccount(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mcc_accounts"
    __table_args__ = (UniqueConstraint("connection_id", "customer_id", name="uq_mcc_connection_customer"),)

    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("google_connections.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    parent_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    descriptive_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_test_account: Mapped[bool] = mapped_column(Boolean, default=False)
    is_root: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    hierarchy_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    geo_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("geo_definitions.id"), nullable=True, index=True)
    geo_assigned_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    geo_assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    detached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    last_sync_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CustomerAccount(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_accounts"
    __table_args__ = (UniqueConstraint("connection_id", "customer_id", name="uq_customer_connection_customer"),)

    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("google_connections.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    manager_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    primary_mcc_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("mcc_accounts.id"), nullable=True, index=True)
    descriptive_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    can_manage_clients: Mapped[bool] = mapped_column(Boolean, default=False)
    is_test_account: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    parent_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    hierarchy_root_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    hierarchy_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    account_type: Mapped[str] = mapped_column(String(24), default="CLIENT", index=True)
    link_status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    local_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    geo_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("geo_definitions.id"), nullable=True, index=True)
    geo_override_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("geo_definitions.id"), nullable=True, index=True
    )
    geo_override_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    geo_override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    work_status: Mapped[str] = mapped_column(String(40), default=AccountWorkStatus.PREPARATION.value, index=True)
    current_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note_updated_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    pinned_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    pinned_note_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pinned_note_updated_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_sync_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_account_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_google_request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    verification_status: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    verification_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_action_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activity_status: Mapped[str] = mapped_column(String(40), default="NO_DATA", index=True)
    activity_period_days: Mapped[int] = mapped_column(Integer, default=7)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=360)


class GoogleAccountAccessPath(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "google_account_access_paths"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "target_customer_id",
            "path_fingerprint",
            name="uq_google_account_access_path",
        ),
    )

    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("google_connections.id", ondelete="CASCADE"), index=True
    )
    target_customer_id: Mapped[str] = mapped_column(String(32), index=True)
    account_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("customer_accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    mcc_account_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("mcc_accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    root_customer_id: Mapped[str] = mapped_column(String(32), index=True)
    manager_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    customer_path: Mapped[list] = mapped_column(JSONB, default=list)
    path_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_request_id: Mapped[str | None] = mapped_column(String(180), nullable=True)


class AccountManagerHistory(UuidPrimaryKeyMixin, Base):
    __tablename__ = "account_manager_history"

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id", ondelete="CASCADE"), index=True)
    previous_mcc_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("mcc_accounts.id"), nullable=True, index=True)
    current_mcc_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("mcc_accounts.id"), nullable=True, index=True)
    previous_manager_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_manager_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    previous_path: Mapped[list] = mapped_column(JSONB, default=list)
    current_path: Mapped[list] = mapped_column(JSONB, default=list)
    reason: Mapped[str] = mapped_column(String(60), default="HIERARCHY_SYNC")
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    request_id: Mapped[str | None] = mapped_column(String(180), nullable=True)


class ConversionActionMapping(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversion_action_mappings"
    __table_args__ = (
        UniqueConstraint(
            "scope_key",
            "semantic_type",
            "resource_name",
            name="uq_conversion_action_mapping",
        ),
    )

    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("google_connections.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("customer_accounts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    scope_type: Mapped[str] = mapped_column(String(24), default="CONNECTION", index=True)
    scope_key: Mapped[str] = mapped_column(String(80), index=True)
    semantic_type: Mapped[str] = mapped_column(String(24), index=True)
    resource_name: Mapped[str] = mapped_column(String(255))
    conversion_action_id: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    is_cross_account: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AccountMonitoringState(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "account_monitoring_states"

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), unique=True, index=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone_mode: Mapped[str] = mapped_column(String(30), default="ACCOUNT")
    boundary_precision: Mapped[str] = mapped_column(String(30), default="EXACT")
    data_source_mode: Mapped[str] = mapped_column(String(24), default="UNKNOWN", index=True)
    impressions: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    clicks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversions: Mapped[float | None] = mapped_column(Float, nullable=True)
    all_conversions: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    conversion_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    registrations: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    deposits: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    registration_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    deposit_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    registration_data_available: Mapped[bool] = mapped_column(Boolean, default=False)
    deposit_data_available: Mapped[bool] = mapped_column(Boolean, default=False)
    budget_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    active_campaigns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disapproved_ads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policy_issues: Mapped[int | None] = mapped_column(Integer, nullable=True)
    freshness: Mapped[str] = mapped_column(String(30), default="NO_DATA", index=True)
    data_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aggregated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_request_id: Mapped[str | None] = mapped_column(String(180), nullable=True)


class AccountMetricDaily(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "account_metric_daily"
    __table_args__ = (UniqueConstraint("account_id", "metric_date", "timezone_mode", name="uq_account_metric_daily"),)

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), index=True)
    metric_date: Mapped[date] = mapped_column(Date, index=True)
    timezone_mode: Mapped[str] = mapped_column(String(30), default="ACCOUNT")
    boundary_precision: Mapped[str] = mapped_column(String(30), default="EXACT")
    data_source_mode: Mapped[str] = mapped_column(String(24), default="UNKNOWN", index=True)
    impressions: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    clicks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversions: Mapped[float | None] = mapped_column(Float, nullable=True)
    all_conversions: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    conversion_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    registrations: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    deposits: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    registration_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    deposit_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    registration_data_available: Mapped[bool] = mapped_column(Boolean, default=False)
    deposit_data_available: Mapped[bool] = mapped_column(Boolean, default=False)
    budget_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    active_campaigns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disapproved_ads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="GOOGLE_ADS")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ControlCenterCampaign(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_campaigns"
    __table_args__ = (UniqueConstraint("account_id", "resource_name", name="uq_control_center_campaign_resource"),)

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), index=True)
    connection_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("google_connections.id"), index=True)
    uploader_campaign_instance_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("campaign_instances.id"), nullable=True, index=True
    )
    resource_name: Mapped[str] = mapped_column(String(255))
    campaign_id: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(40), default="UNKNOWN", index=True)
    channel_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    channel_subtype: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    primary_status: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    primary_status_reasons: Mapped[list] = mapped_column(JSONB, default=list)
    budget_resource_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    budget_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    budget_shared: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bidding_strategy_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    impressions: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    clicks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversions: Mapped[float | None] = mapped_column(Float, nullable=True)
    all_conversions: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    registrations: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    deposits: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    conversion_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    registration_data_available: Mapped[bool] = mapped_column(Boolean, default=False)
    deposit_data_available: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_status: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    last_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    policy_issues: Mapped[list] = mapped_column(JSONB, default=list)
    manually_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ControlCenterAdGroup(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_ad_groups"
    __table_args__ = (UniqueConstraint("account_id", "resource_name", name="uq_control_center_ad_group_resource"),)

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("control_center_campaigns.id", ondelete="CASCADE"), index=True
    )
    resource_name: Mapped[str] = mapped_column(String(255))
    ad_group_id: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    ad_group_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    optimized_targeting_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    impressions: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    clicks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversions: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    conversion_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    policy_issues: Mapped[list] = mapped_column(JSONB, default=list)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ControlCenterAd(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_ads"
    __table_args__ = (UniqueConstraint("account_id", "resource_name", name="uq_control_center_ad_resource"),)

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("control_center_campaigns.id", ondelete="CASCADE"), index=True
    )
    ad_group_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("control_center_ad_groups.id", ondelete="CASCADE"), index=True
    )
    resource_name: Mapped[str] = mapped_column(String(255))
    ad_id: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ad_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    primary_status: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    final_urls: Mapped[list] = mapped_column(JSONB, default=list)
    policy_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    disapproval_reasons: Mapped[list] = mapped_column(JSONB, default=list)
    impressions: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    clicks: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cost_micros: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    conversions: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    conversion_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ControlCenterAsset(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_assets"
    __table_args__ = (UniqueConstraint("account_id", "resource_name", name="uq_control_center_asset_resource"),)

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id", ondelete="CASCADE"), index=True)
    resource_name: Mapped[str] = mapped_column(String(255))
    asset_id: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    asset_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    source: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    policy_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    youtube_video_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    youtube_video_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    youtube_processing_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ControlCenterAdAssetLink(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_ad_asset_links"
    __table_args__ = (
        UniqueConstraint(
            "ad_id",
            "asset_id",
            "field_type",
            name="uq_control_center_ad_asset_link",
        ),
    )

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("control_center_campaigns.id", ondelete="CASCADE"), index=True
    )
    ad_group_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("control_center_ad_groups.id", ondelete="CASCADE"), index=True
    )
    ad_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("control_center_ads.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("control_center_assets.id", ondelete="CASCADE"), index=True)
    resource_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    field_type: Mapped[str] = mapped_column(String(80), index=True)
    performance_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    policy_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ControlCenterGoogleChange(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_google_changes"
    __table_args__ = (UniqueConstraint("event_fingerprint", name="uq_control_center_google_change"),)

    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("google_connections.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id", ondelete="CASCADE"), index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("control_center_campaigns.id", ondelete="CASCADE"), nullable=True, index=True
    )
    event_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    change_resource_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    changed_resource_name: Mapped[str] = mapped_column(String(512), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), index=True)
    change_type: Mapped[str] = mapped_column(String(40), index=True)
    client_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    old_resource: Mapped[dict] = mapped_column(JSONB, default=dict)
    new_resource: Mapped[dict] = mapped_column(JSONB, default=dict)
    changed_fields: Mapped[list] = mapped_column(JSONB, default=list)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    request_id: Mapped[str | None] = mapped_column(String(180), nullable=True)


class AccountNoteHistory(UuidPrimaryKeyMixin, Base):
    __tablename__ = "account_note_history"

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), index=True)
    previous_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    note_kind: Mapped[str] = mapped_column(String(20), default="REGULAR", index=True)
    changed_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AccountWorkStatusHistory(UuidPrimaryKeyMixin, Base):
    __tablename__ = "account_work_status_history"

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    changed_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="LOCAL", index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ControlCenterTag(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_tags"

    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    color: Mapped[str] = mapped_column(String(20), default="#64748b")
    created_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)


class AccountTag(UuidPrimaryKeyMixin, Base):
    __tablename__ = "account_tags"
    __table_args__ = (UniqueConstraint("account_id", "tag_id", name="uq_account_tag"),)

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), index=True)
    tag_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("control_center_tags.id"), index=True)
    assigned_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AccountTagHistory(UuidPrimaryKeyMixin, Base):
    __tablename__ = "account_tag_history"

    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), index=True)
    tag_name: Mapped[str] = mapped_column(String(80), index=True)
    action: Mapped[str] = mapped_column(String(20), index=True)
    changed_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ControlCenterSavedView(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_saved_views"
    __table_args__ = (UniqueConstraint("owner_user_id", "entity_level", "name", name="uq_control_center_saved_view"),)

    owner_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    entity_level: Mapped[str] = mapped_column(String(30), default="ACCOUNT", index=True)
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_view_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("control_center_saved_views.id"), nullable=True
    )


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


class ControlCenterProblem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_problems"
    __table_args__ = (UniqueConstraint("fingerprint", name="uq_control_center_problem_fingerprint"),)

    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_connections.id"), nullable=True, index=True
    )
    account_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), nullable=True, index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("control_center_campaigns.id"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(40), default="LOCAL_MONITORING")
    problem_type: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="WARNING", index=True)
    title: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text)
    resource_name: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    google_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    google_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="NEW", index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    current_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    diagnostics: Mapped[dict] = mapped_column(JSONB, default=dict)


class ControlCenterSyncRun(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_sync_runs"

    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_connections.id"), nullable=True, index=True
    )
    job_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("jobs.id"), nullable=True, index=True)
    requested_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    scope: Mapped[str] = mapped_column(String(30), index=True)
    mode: Mapped[str] = mapped_column(String(20), default="READ_ONLY")
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    estimated_operations: Mapped[int] = mapped_column(Integer, default=0)
    actual_operations: Mapped[int] = mapped_column(Integer, default=0)
    successful_accounts: Mapped[int] = mapped_column(Integer, default=0)
    failed_accounts: Mapped[int] = mapped_column(Integer, default=0)
    selection: Mapped[list] = mapped_column(JSONB, default=list)
    cursor: Mapped[dict] = mapped_column(JSONB, default=dict)
    request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    statistics: Mapped[dict] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ControlCenterSyncItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_sync_items"
    __table_args__ = (UniqueConstraint("sync_run_id", "account_id", name="uq_control_center_sync_item"),)

    sync_run_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("control_center_sync_runs.id"), index=True)
    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    operations: Mapped[int] = mapped_column(Integer, default=0)
    request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    cursor_before: Mapped[dict] = mapped_column(JSONB, default=dict)
    cursor_after: Mapped[dict] = mapped_column(JSONB, default=dict)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ControlCenterQuotaLedger(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_quota_ledger"

    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_connections.id"), nullable=True, index=True
    )
    operation_date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    operation_count: Mapped[int] = mapped_column(Integer, default=1)
    succeeded: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    request_id: Mapped[str | None] = mapped_column(String(180), nullable=True)


class ControlCenterActionRequest(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_action_requests"

    account_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), nullable=True, index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("control_center_campaigns.id"), nullable=True, index=True
    )
    requested_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(40), index=True)
    execution_mode: Mapped[str] = mapped_column(String(20), default="SIMULATION", index=True)
    status: Mapped[str] = mapped_column(String(30), default="PREVIEWED", index=True)
    requested_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    pre_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    preview: Mapped[dict] = mapped_column(JSONB, default=dict)
    validation: Mapped[dict] = mapped_column(JSONB, default=dict)
    readback: Mapped[dict] = mapped_column(JSONB, default=dict)
    confirmation_token_hash: Mapped[str] = mapped_column(String(64))
    confirmation_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    second_approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    second_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    second_approved_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ControlCenterActionItem(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_action_items"

    action_request_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("control_center_action_requests.id"), index=True)
    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), index=True)
    campaign_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("control_center_campaigns.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    previous_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(180), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ControlCenterRule(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_rules"

    name: Mapped[str] = mapped_column(String(160), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), default="DRY_RUN", index=True)
    scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    condition_logic: Mapped[str] = mapped_column(String(10), default="AND")
    conditions: Mapped[list] = mapped_column(JSONB, default=list)
    actions: Mapped[list] = mapped_column(JSONB, default=list)
    safeguards: Mapped[dict] = mapped_column(JSONB, default=dict)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    max_actions_per_run: Mapped[int] = mapped_column(Integer, default=10)
    max_actions_per_day: Mapped[int] = mapped_column(Integer, default=25)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    schedule: Mapped[dict] = mapped_column(JSONB, default=dict)
    max_budget_change_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    live_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    live_confirmed_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class ControlCenterRuleEvaluation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "control_center_rule_evaluations"

    rule_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("control_center_rules.id"), index=True)
    account_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), nullable=True, index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("control_center_campaigns.id"), nullable=True, index=True
    )
    matched: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="DRY_RUN", index=True)
    evaluation: Mapped[dict] = mapped_column(JSONB, default=dict)
    proposed_actions: Mapped[list] = mapped_column(JSONB, default=list)
    mutation_performed: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_reason: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(180), nullable=True, unique=True)
    action_request_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("control_center_action_requests.id"), nullable=True, index=True
    )


class ControlCenterEvent(UuidPrimaryKeyMixin, Base):
    __tablename__ = "control_center_events"

    account_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("customer_accounts.id"), nullable=True, index=True)
    campaign_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("control_center_campaigns.id"), nullable=True, index=True
    )
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    source: Mapped[str] = mapped_column(String(40), default="LOCAL", index=True)
    summary: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GoogleTestAcceptanceRun(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "google_test_acceptance_runs"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "customer_id",
            "purpose",
            name="uq_google_test_acceptance_run",
        ),
    )

    connection_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("google_connections.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(32), index=True)
    purpose: Mapped[str] = mapped_column(String(40), index=True)
    fixture_name: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", index=True)
    upload_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("campaign_uploads.id"), nullable=True)
    plan_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("deployment_plans.id"), nullable=True)
    resource_names: Mapped[list] = mapped_column(JSONB, default=list)
    request_ids: Mapped[list] = mapped_column(JSONB, default=list)
    readback: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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

    template_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("campaign_templates.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column()
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_campaign_resource: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class LaunchBatch(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "launch_batches"

    upload_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("campaign_uploads.id", ondelete="CASCADE"), index=True)
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

    launch_batch_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("launch_batches.id", ondelete="CASCADE"), index=True)
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

    launch_batch_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("launch_batches.id", ondelete="CASCADE"), index=True)
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
    upload_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("campaign_uploads.id", ondelete="CASCADE"), index=True)
    connection_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("google_connections.id"), nullable=True, index=True
    )
    launch_batch_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("launch_batches.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("jobs.id"), nullable=True, index=True)
    parent_schedule_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("deployment_schedules.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mcc_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(40), default=ScheduleStatus.DRAFT.value, index=True)
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
    __table_args__ = (UniqueConstraint("schedule_id", "wave_number", name="uq_schedule_wave_number"),)

    schedule_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("deployment_schedules.id", ondelete="CASCADE"), index=True
    )
    wave_number: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(40), default=ScheduleWaveStatus.PLANNED.value, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observation_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
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
    wave_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("deployment_waves.id", ondelete="CASCADE"), index=True)
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
    status: Mapped[str] = mapped_column(String(40), default=ScheduleRunStatus.WAITING.value, index=True)
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
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    level: Mapped[str] = mapped_column(String(20), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)


class CampaignInstanceOverride(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaign_instance_overrides"

    launch_batch_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("launch_batches.id", ondelete="CASCADE"), index=True)
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
    media_asset_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("media_assets.id"), nullable=True, index=True)
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


class AiConversation(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_conversations"

    owner_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180), default="Новый диалог")
    authority_mode: Mapped[str] = mapped_column(String(30), default=AiAuthorityMode.READ_ONLY.value, index=True)
    google_environment: Mapped[str] = mapped_column(
        String(24), default=GoogleConnectionMode.SIMULATION.value, index=True
    )
    scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    locale: Mapped[str] = mapped_column(String(12), default="ru")
    time_zone: Mapped[str] = mapped_column(String(80), default="Europe/Moscow")
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class AiRun(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_runs"

    conversation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default=AiRunStatus.QUEUED.value, index=True)
    model_profile: Mapped[str] = mapped_column(String(24), default="BALANCED", index=True)
    model_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    prompt_version: Mapped[str] = mapped_column(String(40), default="ai-analyst-v1")
    tool_schema_version: Mapped[str] = mapped_column(String(40), default="axyro-tools-v1")
    authority_mode: Mapped[str] = mapped_column(String(30), index=True)
    google_environment: Mapped[str] = mapped_column(String(24), index=True)
    resolved_scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_turns: Mapped[int] = mapped_column(Integer, default=0)
    read_tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    draft_tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    partial: Mapped[bool] = mapped_column(Boolean, default=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiMessage(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_messages"

    conversation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20), index=True)
    content: Mapped[str] = mapped_column(Text)
    structured_content: Mapped[dict] = mapped_column(JSONB, default=dict)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(30), default="COMPLETE", index=True)


class AiToolCall(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_tool_calls"
    __table_args__ = (UniqueConstraint("run_id", "call_fingerprint", name="uq_ai_tool_call_fingerprint"),)

    run_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ai_runs.id", ondelete="CASCADE"), index=True)
    tool_call_id: Mapped[str] = mapped_column(String(180), index=True)
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    tool_version: Mapped[str] = mapped_column(String(40))
    risk_class: Mapped[str] = mapped_column(String(30), index=True)
    arguments: Mapped[dict] = mapped_column(JSONB, default=dict)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="RUNNING", index=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    call_fingerprint: Mapped[str] = mapped_column(String(64), index=True)


class AiDraft(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_drafts"

    owner_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True)
    draft_type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(30), default="EDITABLE", index=True)
    authority_mode: Mapped[str] = mapped_column(String(30))
    google_environment: Mapped[str] = mapped_column(String(24))
    scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    source_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    linked_entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    linked_entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action_request_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("control_center_action_requests.id"), nullable=True, index=True
    )
    deployment_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("deployment_plans.id"), nullable=True, index=True
    )


class AiSavedReport(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_saved_reports"

    owner_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(180))
    report: Mapped[dict] = mapped_column(JSONB, default=dict)
    scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class AiUsageDaily(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_usage_daily"
    __table_args__ = (UniqueConstraint("usage_date", "user_id", "model_id", name="uq_ai_usage_daily_user_model"),)

    usage_date: Mapped[date] = mapped_column(Date, index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[str] = mapped_column(String(80), index=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(14, 8), default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms_total: Mapped[int] = mapped_column(BigInteger, default=0)


class AiUserPreference(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_user_preferences"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    default_authority_mode: Mapped[str] = mapped_column(String(30), default=AiAuthorityMode.READ_ONLY.value)
    default_environment: Mapped[str] = mapped_column(String(24), default=GoogleConnectionMode.SIMULATION.value)
    default_model_profile: Mapped[str] = mapped_column(String(24), default="BALANCED")
    default_scope: Mapped[dict] = mapped_column(JSONB, default=dict)
    locale: Mapped[str] = mapped_column(String(12), default="ru")
    time_zone: Mapped[str] = mapped_column(String(80), default="Europe/Moscow")


class AiAdminSetting(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_admin_settings"

    key: Mapped[str] = mapped_column(String(80), unique=True, index=True, default="global")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    openai_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    openai_key_last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    updated_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)


class AiModelProfile(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_model_profiles"

    name: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    model_id: Mapped[str] = mapped_column(String(80), index=True)
    reasoning_effort: Mapped[str] = mapped_column(String(20), default="medium")
    verbosity: Mapped[str] = mapped_column(String(20), default="medium")
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    max_input_tokens: Mapped[int] = mapped_column(Integer, default=32_000)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=4_000)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    price_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    eval_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    eval_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GeoAnalyticsProfile(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "geo_analytics_profiles"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "version", name="uq_geo_analytics_profile_scope_version"),
    )

    scope_type: Mapped[str] = mapped_column(String(24), index=True)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    geo_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("geo_definitions.id"), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_zone: Mapped[str] = mapped_column(String(80), default="UTC")
    expected_currencies: Mapped[list] = mapped_column(JSONB, default=list)
    default_reporting_period: Mapped[str] = mapped_column(String(30), default="7d")
    primary_metric_source: Mapped[str] = mapped_column(String(40), default="GOOGLE_ADS")
    target_cpl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_registration_cpa: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_deposit_cpa: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_roas: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    max_spend_without_lead: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    max_spend_without_registration: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    max_spend_without_deposit: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    minimum_clicks: Mapped[int] = mapped_column(Integer, default=0)
    minimum_impressions: Mapped[int] = mapped_column(Integer, default=0)
    minimum_spend: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0)
    conversion_lag_hours: Mapped[int] = mapped_column(Integer, default=24)
    alert_thresholds: Mapped[dict] = mapped_column(JSONB, default=dict)
    owner_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class GeoAnalyticsProfileHistory(UuidPrimaryKeyMixin, Base):
    __tablename__ = "geo_analytics_profile_history"

    profile_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("geo_analytics_profiles.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, index=True)
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    changed_by_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class GeoAnalyticsOverride(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "geo_analytics_overrides"
    __table_args__ = (UniqueConstraint("scope_type", "scope_id", name="uq_geo_analytics_override_scope"),)

    scope_type: Mapped[str] = mapped_column(String(24), index=True)
    scope_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    profile_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("geo_analytics_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    override_values: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


class MetricSourceMapping(UuidPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "metric_source_mappings"
    __table_args__ = (
        UniqueConstraint(
            "scope_type",
            "scope_id",
            "semantic_metric",
            "provider",
            "source_id",
            name="uq_metric_source_mapping",
        ),
    )

    scope_type: Mapped[str] = mapped_column(String(24), index=True)
    scope_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    semantic_metric: Mapped[str] = mapped_column(String(40), index=True)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[str] = mapped_column(String(255))
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attribution_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)


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
