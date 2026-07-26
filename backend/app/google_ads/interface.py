from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GoogleAdsConnectionConfig:
    connection_id: str
    name: str
    login_customer_id: str
    api_version: str
    auth_type: str
    environment: str
    developer_token: str
    auth_payload: dict
    timeout_seconds: int = 60
    retry_count: int = 3


@dataclass(frozen=True)
class AdapterCheckResult:
    ok: bool
    status: str
    message: str
    api_version: str
    request_id: str | None = None


@dataclass(frozen=True)
class CustomerAccountInfo:
    customer_id: str
    manager_customer_id: str | None
    descriptive_name: str | None
    currency_code: str | None
    time_zone: str | None
    can_manage_clients: bool
    is_test_account: bool
    is_hidden: bool
    status: str | None


@dataclass(frozen=True)
class PlanExecutionResult:
    ok: bool
    mode: str
    errors: list[dict]
    warnings: list[dict]
    request_ids: list[str]
    resource_names: list[str]
    details: dict


@dataclass(frozen=True)
class YouTubeUploadResult:
    state: str
    resource_name: str | None
    video_id: str | None
    message: str


class GoogleAdsAdapter(Protocol):
    def test_connection(self) -> AdapterCheckResult:
        """Run a safe read-only request against the configured MCC."""

    def list_customer_accounts(self) -> list[CustomerAccountInfo]:
        """Return child accounts visible from the configured manager account."""

    def validate_plan(self, snapshot: dict) -> PlanExecutionResult:
        """Submit atomic campaign operations with validate_only enabled."""

    def deploy_plan(self, snapshot: dict) -> PlanExecutionResult:
        """Create a previously validated plan with campaigns forced to PAUSED."""

    def change_campaign_status(self, customer_id: str, campaigns: list[dict], status: str) -> PlanExecutionResult:
        """Enable or pause selected Demand Gen campaigns in one customer account."""

    def fetch_campaign_performance(self, customer_id: str, resource_names: list[str]) -> list[dict]:
        """Return campaign-level performance for a launch group."""

    def fetch_account_catalog(self, customer_id: str) -> dict:
        """Return account-scoped conversion actions, audiences, user lists and assets."""

    def read_campaign(self, customer_id: str, campaign_resource_name: str) -> dict:
        """Read a Demand Gen campaign into the adapter-neutral template shape."""

    def start_youtube_video_upload(
        self, customer_id: str, file_path: str, title: str, description: str
    ) -> YouTubeUploadResult:
        """Start a server-side YouTube video upload."""

    def get_youtube_video_upload(self, customer_id: str, resource_name: str) -> YouTubeUploadResult:
        """Return the current state and resulting YouTube video ID."""
