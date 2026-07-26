from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import AuthType, ConnectionStatus, EnvironmentType, UserRole


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
    developer_token: str | None = Field(default=None, max_length=512)
    service_account_json: dict | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    oauth_refresh_token: str | None = None

    @field_validator("login_customer_id")
    @classmethod
    def validate_login_customer_id(cls, value: str) -> str:
        return normalize_customer_id(value)


class GoogleConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    login_customer_id: str
    auth_type: AuthType
    environment: EnvironmentType
    api_version: str
    status: ConnectionStatus
    last_checked_at: datetime | None
    last_error: str | None
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
