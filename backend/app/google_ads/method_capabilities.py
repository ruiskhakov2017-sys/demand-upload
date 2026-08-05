from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AdapterMethodCapability:
    method: str
    operation: str
    supports_validate_only: bool
    supports_partial_failure: bool
    production_acceptance_required: bool


READ_METHODS = (
    "test_connection",
    "list_customer_accounts",
    "discover_customer_hierarchy",
    "fetch_campaign_performance",
    "fetch_account_catalog",
    "fetch_control_center_metrics",
    "read_control_center_account",
    "fetch_identity_verification",
    "fetch_billing_summary",
    "list_control_center_campaigns",
    "list_conversion_actions",
    "list_control_center_ad_groups",
    "list_control_center_ads",
    "list_control_center_asset_links",
    "fetch_control_center_changes",
    "read_control_center_campaign",
    "read_campaign",
    "read_demand_gen_resources",
    "get_youtube_video_upload",
)

VALIDATE_METHODS = (
    "validate_plan",
    "validate_campaign_status",
)

WRITE_METHODS = (
    "deploy_plan",
    "change_campaign_status",
    "change_campaign_budget",
    "start_youtube_video_upload",
)


def _registry_for_version(api_version: str) -> tuple[AdapterMethodCapability, ...]:
    reads = tuple(
        AdapterMethodCapability(
            method=name,
            operation="READ",
            supports_validate_only=False,
            supports_partial_failure=False,
            production_acceptance_required=True,
        )
        for name in READ_METHODS
    )
    validates = tuple(
        AdapterMethodCapability(
            method=name,
            operation="VALIDATE",
            supports_validate_only=True,
            supports_partial_failure=True,
            production_acceptance_required=True,
        )
        for name in VALIDATE_METHODS
    )
    writes = tuple(
        AdapterMethodCapability(
            method=name,
            operation="WRITE_OR_VALIDATE" if name == "change_campaign_budget" else "WRITE",
            supports_validate_only=name == "change_campaign_budget",
            supports_partial_failure=name in {"deploy_plan", "change_campaign_status"},
            production_acceptance_required=True,
        )
        for name in WRITE_METHODS
    )
    del api_version
    return (*reads, *validates, *writes)


ADAPTER_METHOD_CAPABILITIES = {
    "v24.2": _registry_for_version("v24.2"),
    "v25": _registry_for_version("v25"),
    "v25.0": _registry_for_version("v25"),
}


def get_adapter_method_capabilities(api_version: str) -> list[dict[str, Any]]:
    normalized = api_version.strip().lower()
    capabilities = ADAPTER_METHOD_CAPABILITIES.get(normalized)
    if capabilities is None:
        raise ValueError(f"Неподдерживаемая версия Google Ads API: {api_version}")
    return [asdict(item) | {"api_version": normalized} for item in capabilities]


def assert_adapter_contract(adapter_type: type, api_version: str) -> None:
    missing = [
        item["method"]
        for item in get_adapter_method_capabilities(api_version)
        if not callable(getattr(adapter_type, item["method"], None))
    ]
    if missing:
        raise TypeError(f"{adapter_type.__name__} нарушает adapter contract: {', '.join(missing)}")
