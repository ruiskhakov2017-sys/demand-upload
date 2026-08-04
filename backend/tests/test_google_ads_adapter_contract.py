from app.google_ads.interface import GoogleAdsAdapter
from app.google_ads.method_capabilities import (
    ADAPTER_METHOD_CAPABILITIES,
    assert_adapter_contract,
    get_adapter_method_capabilities,
)
from app.google_ads.versions.v24_2 import GoogleAdsV242Adapter
from app.google_ads.versions.v25 import GoogleAdsV25Adapter


def test_every_protocol_method_has_a_versioned_capability_entry() -> None:
    protocol_methods = {
        name
        for name, value in GoogleAdsAdapter.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
    for version in ("v24.2", "v25"):
        registered = {item["method"] for item in get_adapter_method_capabilities(version)}
        assert registered == protocol_methods


def test_v242_and_v25_adapters_satisfy_the_explicit_method_contract() -> None:
    assert_adapter_contract(GoogleAdsV242Adapter, "v24.2")
    assert_adapter_contract(GoogleAdsV25Adapter, "v25")
    assert GoogleAdsV25Adapter.contract_version == "v25"


def test_validate_only_and_partial_failure_are_declared_per_method() -> None:
    methods = {item["method"]: item for item in get_adapter_method_capabilities("v25")}
    assert methods["validate_plan"]["supports_validate_only"] is True
    assert methods["validate_campaign_status"]["supports_validate_only"] is True
    assert methods["change_campaign_budget"]["supports_validate_only"] is True
    assert methods["test_connection"]["supports_validate_only"] is False
    assert methods["fetch_control_center_metrics"]["supports_partial_failure"] is False
    assert methods["deploy_plan"]["supports_partial_failure"] is True
    assert set(ADAPTER_METHOD_CAPABILITIES) == {"v24.2", "v25", "v25.0"}
