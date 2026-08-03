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
    connection_mode: str = "PRODUCTION"
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
    parent_customer_id: str | None = None
    hierarchy_level: int | None = None
    account_type: str = "CLIENT"
    request_ids: tuple[str, ...] = ()
    access_paths: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class CustomerHierarchyResult:
    root: CustomerAccountInfo
    accounts: tuple[CustomerAccountInfo, ...]
    accessible_customer_ids: tuple[str, ...]
    request_ids: tuple[str, ...]


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

    def discover_customer_hierarchy(self) -> CustomerHierarchyResult:
        """Read accessible customers and recursively discover the configured MCC tree."""

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

    def fetch_control_center_metrics(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        conversion_actions: dict[str, list[str]] | None = None,
    ) -> dict:
        """Return adapter-neutral account metrics for an inclusive date range."""

    def read_control_center_account(self, customer_id: str) -> dict:
        """Return current Google account state without changing it."""

    def fetch_identity_verification(self, customer_id: str) -> dict:
        """Return the available advertiser identity-verification state."""

    def fetch_billing_summary(self, customer_id: str) -> dict:
        """Return read-only monthly-invoicing billing setups and account budgets."""

    def list_control_center_campaigns(
        self,
        customer_id: str,
        start_date: str,
        end_date: str,
        conversion_actions: dict[str, list[str]] | None = None,
    ) -> list[dict]:
        """Return every visible campaign with current state and optional period metrics."""

    def list_conversion_actions(self, customer_id: str) -> list[dict]:
        """Return readable conversion actions for explicit registration/deposit mapping."""

    def list_control_center_ad_groups(self, customer_id: str) -> list[dict]:
        """Return current ad groups and their campaign ownership."""

    def list_control_center_ads(self, customer_id: str) -> list[dict]:
        """Return current ads and policy summaries."""

    def list_control_center_asset_links(self, customer_id: str) -> list[dict]:
        """Return ad-to-asset links with asset metadata."""

    def fetch_control_center_changes(
        self,
        customer_id: str,
        start_date_time: str,
        end_date_time: str,
    ) -> list[dict]:
        """Return the ChangeEvent history available from Google Ads."""

    def read_control_center_campaign(self, customer_id: str, resource_name: str) -> dict:
        """Return current state used by action preview and read-back."""

    def validate_campaign_status(self, customer_id: str, campaigns: list[dict], status: str) -> PlanExecutionResult:
        """Validate a campaign status mutation without applying it."""

    def change_campaign_budget(
        self, customer_id: str, budget_resource_name: str, amount_micros: int, validate_only: bool
    ) -> PlanExecutionResult:
        """Validate or apply one absolute campaign budget amount."""

    def read_campaign(self, customer_id: str, campaign_resource_name: str) -> dict:
        """Read a Demand Gen campaign into the adapter-neutral template shape."""

    def read_demand_gen_resources(
        self,
        customer_id: str,
        campaign_resource_name: str,
        known_resource_names: list[str] | None = None,
    ) -> dict:
        """Read the created Demand Gen campaign and its dependent resources."""

    def start_youtube_video_upload(
        self, customer_id: str, file_path: str, title: str, description: str
    ) -> YouTubeUploadResult:
        """Start a server-side YouTube video upload."""

    def get_youtube_video_upload(self, customer_id: str, resource_name: str) -> YouTubeUploadResult:
        """Return the current state and resulting YouTube video ID."""
