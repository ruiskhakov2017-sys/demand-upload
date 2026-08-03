from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.models import (
    AuthType,
    ConnectionStatus,
    EnvironmentType,
    GoogleConnectionMode,
    UserRole,
)


def normalize_customer_id(value: str) -> str:
    normalized = "".join(ch for ch in value if ch.isdigit())
    if len(normalized) < 6:
        raise ValueError("Customer ID должен содержать цифры Google Ads аккаунта")
    return normalized


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    email: str | None
    role: UserRole
    is_active: bool


class SetupStatusOut(BaseModel):
    setup_required: bool
    users_count: int


class BootstrapAdminIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=256)
    email: str | None = Field(default=None, max_length=255)
    setup_token: str | None = None


class LoginIn(BaseModel):
    username: str
    password: str


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


class GoogleConnectionCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    login_customer_id: str
    auth_type: AuthType
    environment: EnvironmentType = EnvironmentType.TEST
    connection_mode: GoogleConnectionMode = GoogleConnectionMode.PRODUCTION
    credential_source_connection_id: UUID | None = None
    developer_token: str | None = Field(default=None, max_length=512)
    service_account_json: dict | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    oauth_refresh_token: str | None = None

    @field_validator("login_customer_id")
    @classmethod
    def validate_login_customer_id(cls, value: str) -> str:
        return normalize_customer_id(value)

    @model_validator(mode="after")
    def validate_connection_mode(self) -> GoogleConnectionCreateIn:
        if self.connection_mode == GoogleConnectionMode.GOOGLE_TEST:
            if self.auth_type != AuthType.OAUTH_WEB:
                raise ValueError("GOOGLE_TEST поддерживает только OAuth Web")
            if self.environment != EnvironmentType.TEST:
                raise ValueError("GOOGLE_TEST должен использовать среду TEST")
            if self.credential_source_connection_id is None:
                raise ValueError(
                    "Для GOOGLE_TEST выберите защищённый credential profile"
                )
        return self


class GoogleConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    login_customer_id: str
    auth_type: AuthType
    environment: EnvironmentType
    connection_mode: GoogleConnectionMode
    api_version: str
    status: ConnectionStatus
    last_checked_at: datetime | None
    last_error: str | None
    test_hierarchy_root_customer_id: str | None
    hierarchy_verified_at: datetime | None
    hierarchy_request_ids: list
    created_at: datetime
    updated_at: datetime


class AdapterCheckOut(BaseModel):
    ok: bool
    status: str
    message: str
    request_id: str | None = None
    api_version: str


class CustomerAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    connection_id: UUID
    customer_id: str
    manager_customer_id: str | None
    descriptive_name: str | None
    currency_code: str | None
    time_zone: str | None
    can_manage_clients: bool
    is_test_account: bool
    is_hidden: bool
    status: str | None
    parent_customer_id: str | None
    hierarchy_root_customer_id: str | None
    hierarchy_level: int | None
    account_type: str
    last_sync_success_at: datetime | None
    test_account_verified_at: datetime | None
    last_google_request_ids: list
    updated_at: datetime


class SyncAccountsOut(BaseModel):
    synced: int
    accounts: list[CustomerAccountOut]


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    status: str
    progress_current: int
    progress_total: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
