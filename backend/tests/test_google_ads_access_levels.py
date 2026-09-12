from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.auth.credentials import AnonymousCredentials

from app.api.routes.plans import deployment_idempotency_key
from app.core.security import utcnow
from app.db.models import AuthType, CustomerAccount, GoogleConnection
from app.google_ads.access import (
    GoogleAdsOperationNotSupported,
    access_summary,
    require_operation_supported,
)
from app.google_ads.errors import GoogleAdsAdapterError
from app.google_ads.interface import GoogleAdsConnectionConfig
from app.google_ads.safety import (
    GoogleAdsSafetyError,
    require_connection_target,
    require_execution_mode_for_connection,
)
from app.google_ads.versions.v24_2 import adapter as adapter_module
from app.google_ads.versions.v24_2.adapter import GoogleAdsV242Adapter


def _connection(mode: str) -> GoogleConnection:
    root = "3831073849" if mode == "GOOGLE_TEST" else "5589335362"
    return GoogleConnection(
        id=uuid4(),
        name=f"connection-{mode.lower()}",
        login_customer_id=root,
        auth_type=AuthType.OAUTH_WEB.value,
        environment="TEST" if mode == "GOOGLE_TEST" else "PRODUCTION",
        connection_mode=mode,
        api_version="v24.2",
        status="VERIFIED",
        test_hierarchy_root_customer_id=root if mode == "GOOGLE_TEST" else None,
    )


def _account(connection: GoogleConnection, *, test_account: bool) -> CustomerAccount:
    return CustomerAccount(
        id=uuid4(),
        connection_id=connection.id,
        customer_id="1833869760",
        manager_customer_id=connection.login_customer_id,
        parent_customer_id=connection.login_customer_id,
        hierarchy_root_customer_id=connection.login_customer_id,
        hierarchy_level=1,
        account_type="CLIENT",
        can_manage_clients=False,
        is_test_account=test_account,
        is_hidden=False,
        status="ENABLED",
        work_status="WORKING",
        test_account_verified_at=utcnow() if test_account else None,
        last_sync_success_at=utcnow(),
    )


def _adapter(level: str, mode: str = "PRODUCTION") -> GoogleAdsV242Adapter:
    return GoogleAdsV242Adapter(
        GoogleAdsConnectionConfig(
            connection_id="connection",
            name="connection",
            login_customer_id="5589335362",
            api_version="v24.2",
            auth_type="OAUTH_WEB",
            environment="PRODUCTION",
            connection_mode=mode,
            access_level=level,
            developer_token="secret",
            auth_payload={},
        )
    )


def test_test_access_allows_test_target_and_denies_production_target() -> None:
    test_connection = _connection("GOOGLE_TEST")
    require_execution_mode_for_connection(test_connection, "GOOGLE_TEST", "TEST")
    require_connection_target(
        test_connection,
        _account(test_connection, test_account=True),
        "1833869760",
        "GOOGLE_TEST",
    )

    production_connection = _connection("PRODUCTION")
    with pytest.raises(GoogleAdsSafetyError) as error:
        require_execution_mode_for_connection(
            production_connection,
            "PRODUCTION",
            "TEST",
        )
    assert error.value.code == "PRODUCTION_MUTATE_ACCESS_DENIED"


def test_explorer_allows_production_read_and_supported_mutate() -> None:
    connection = _connection("PRODUCTION")
    account = _account(connection, test_account=False)
    access = access_summary("EXPLORER")

    assert access["level"] == "EXPLORER"
    assert access["production_read_enabled"] is True
    assert access["production_mutate_enabled"] is True
    require_execution_mode_for_connection(connection, "PRODUCTION", "EXPLORER")
    require_connection_target(connection, account, account.customer_id, "PRODUCTION")
    _adapter("EXPLORER")._require_mutate_access()


@pytest.mark.parametrize("level", ["BASIC", "STANDARD"])
def test_basic_and_standard_allow_production_mutate(level: str) -> None:
    connection = _connection("PRODUCTION")
    require_execution_mode_for_connection(connection, "PRODUCTION", level)
    _adapter(level)._require_mutate_access()


def test_unknown_access_level_fails_before_opening_google(monkeypatch) -> None:
    entered_google = False

    @contextmanager
    def forbidden_google_client(config):
        del config
        nonlocal entered_google
        entered_google = True
        yield None

    monkeypatch.setattr(adapter_module, "google_ads_client", forbidden_google_client)
    with pytest.raises(GoogleAdsAdapterError, match="UNKNOWN_GOOGLE_ADS_ACCESS_LEVEL"):
        _adapter("UNKNOWN").validate_campaign_status(
            "1833869760",
            [{"resource_name": "customers/1833869760/campaigns/1"}],
            "PAUSED",
        )
    assert entered_google is False


def test_explorer_is_not_masked_as_basic_and_has_exact_limits() -> None:
    access = access_summary("explorer")
    assert access["level"] == "EXPLORER"
    assert access["production_operation_limit"] == 2_880
    assert access["test_operation_limit"] == 15_000
    assert access["basic_access_status"] == "PENDING_BRAND_VERIFICATION"


def test_explorer_unsupported_operation_has_exact_error() -> None:
    with pytest.raises(GoogleAdsOperationNotSupported) as error:
        require_operation_supported("EXPLORER", "CUSTOMER_ACCOUNT_CREATE")
    assert error.value.code == "EXPLORER_OPERATION_UNSUPPORTED"
    assert error.value.operation == "CUSTOMER_ACCOUNT_CREATE"


def test_quota_error_is_returned_with_request_id_without_mutate_retry(monkeypatch) -> None:
    real_client = GoogleAdsClient(
        credentials=AnonymousCredentials(),
        developer_token="test",
        version="v24",
        use_proto_plus=True,
    )
    fake_client = SimpleNamespace(
        get_type=real_client.get_type,
        get_service=lambda name: SimpleNamespace(name=name),
    )
    calls = 0

    @contextmanager
    def fake_google_client(config):
        del config
        yield fake_client

    def fail_once(*args, **kwargs):
        del args, kwargs
        nonlocal calls
        calls += 1
        raise RuntimeError("quota exhausted")

    monkeypatch.setattr(adapter_module, "google_ads_client", fake_google_client)
    monkeypatch.setattr(adapter_module, "unary_call_with_request_id", fail_once)
    monkeypatch.setattr(
        adapter_module,
        "_google_exception",
        lambda exc, customer_id, campaign_name: (
            [
                {
                    "customer_id": customer_id,
                    "campaign_name": campaign_name,
                    "code": "QUOTA_ERROR.RESOURCE_EXHAUSTED",
                    "message": str(exc),
                }
            ],
            "quota-request-id",
        ),
    )

    result = _adapter("EXPLORER").change_campaign_budget(
        "1833869760",
        "customers/1833869760/campaignBudgets/1",
        1_000_000,
        validate_only=False,
    )

    assert calls == 1
    assert result.ok is False
    assert result.errors[0]["code"] == "QUOTA_ERROR.RESOURCE_EXHAUSTED"
    assert result.request_ids == ["quota-request-id"]


def test_deployment_idempotency_key_is_stable_for_repeated_confirmation() -> None:
    first = deployment_idempotency_key("fingerprint", ["b", "a"])
    repeated = deployment_idempotency_key("fingerprint", ["a", "b"])
    assert first == repeated
    assert first != deployment_idempotency_key("fingerprint", ["a"])
