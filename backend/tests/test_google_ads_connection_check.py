from __future__ import annotations

import ast
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.auth.credentials import AnonymousCredentials

from app.google_ads.client_factory import _to_google_ads_client_config
from app.google_ads.errors import GoogleAdsAdapterError
from app.google_ads.interface import GoogleAdsConnectionConfig
from app.google_ads.versions.v24_2 import adapter as adapter_module
from app.google_ads.versions.v24_2.adapter import GoogleAdsV242Adapter
from app.google_ads.versions.v25.adapter import GoogleAdsV25Adapter

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _config(login_customer_id: str = "558-933-5362") -> GoogleAdsConnectionConfig:
    return GoogleAdsConnectionConfig(
        connection_id="test-connection",
        name="vcc2",
        login_customer_id=login_customer_id,
        api_version="v24.2",
        auth_type="OAUTH_WEB",
        environment="TEST",
        developer_token="saved-developer-token",
        auth_payload={
            "client_id": "saved-client-id",
            "client_secret": "saved-client-secret",
            "refresh_token": "saved-refresh-token",
        },
    )


def test_connection_uses_read_only_google_ads_search(monkeypatch) -> None:
    customer = SimpleNamespace(
        id=5589335362,
        descriptive_name="VCC2 MCC",
        manager=True,
        test_account=False,
        currency_code="USD",
        time_zone="Europe/Moscow",
    )

    class FakeGoogleAdsService:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def search(self, *, customer_id: str, query: str) -> list[SimpleNamespace]:
            self.calls.append({"customer_id": customer_id, "query": query})
            return [SimpleNamespace(customer=customer)]

    service = FakeGoogleAdsService()

    class FakeClient:
        def get_service(self, name: str) -> FakeGoogleAdsService:
            assert name == "GoogleAdsService"
            return service

    @contextmanager
    def fake_google_ads_client(config):
        assert config.developer_token == "saved-developer-token"
        assert config.auth_payload["refresh_token"] == "saved-refresh-token"
        yield FakeClient()

    monkeypatch.setattr(adapter_module, "google_ads_client", fake_google_ads_client)

    result = GoogleAdsV242Adapter(_config()).test_connection()

    assert result.ok is True
    assert result.status == "VERIFIED"
    assert result.request_id is None
    assert len(service.calls) == 1
    assert service.calls[0]["customer_id"] == "5589335362"
    query = " ".join(service.calls[0]["query"].split()).lower()
    assert "from customer" in query
    assert "limit 1" in query
    for field in (
        "customer.id",
        "customer.descriptive_name",
        "customer.manager",
        "customer.test_account",
        "customer.currency_code",
        "customer.time_zone",
    ):
        assert field in query
    assert "mutate" not in query


def test_change_event_query_uses_supported_v24_fields(monkeypatch) -> None:
    captured: dict[str, str] = {}
    event = SimpleNamespace(
        resource_name="customers/123/changeEvents/1~0~0",
        change_date_time="2026-07-31 12:00:00",
        change_resource_name="customers/123/campaigns/456",
        change_resource_type=SimpleNamespace(name="CAMPAIGN"),
        client_type=SimpleNamespace(name="GOOGLE_ADS_API"),
        resource_change_operation=SimpleNamespace(name="UPDATE"),
        user_email="operator@example.test",
        changed_fields=SimpleNamespace(paths=["status"]),
        old_resource=None,
        new_resource=None,
    )

    @contextmanager
    def fake_google_ads_client(config):
        yield object()

    def fake_search_rows(self, client, customer_id, query):
        captured["customer_id"] = customer_id
        captured["query"] = " ".join(query.split()).lower()
        return [SimpleNamespace(change_event=event)], ["request-id"]

    monkeypatch.setattr(adapter_module, "google_ads_client", fake_google_ads_client)
    monkeypatch.setattr(GoogleAdsV242Adapter, "_search_rows", fake_search_rows)

    result = GoogleAdsV242Adapter(_config()).fetch_control_center_changes(
        "123-456-7890",
        "2026-07-30T12:00:00+00:00",
        "2026-07-31T12:00:00+00:00",
    )

    assert captured["customer_id"] == "1234567890"
    assert "change_event.client_type" in captured["query"]
    assert "change_event.change_client_type" not in captured["query"]
    assert "change_event.resource_change_operation" in captured["query"]
    assert "change_event.change_date_time >= '2026-07-30'" in captured["query"]
    assert "change_event.change_date_time <= '2026-07-31'" in captured["query"]
    assert "2026-07-30t12:00:00" not in captured["query"]
    assert "+00:00" not in captured["query"]
    assert result[0]["client_type"] == "GOOGLE_ADS_API"
    assert result[0]["change_type"] == "UPDATED"
    assert result[0]["_request_ids"] == ["request-id"]


def test_monthly_invoicing_read_uses_only_billing_gaql(monkeypatch) -> None:
    queries: list[str] = []
    setup = SimpleNamespace(
        resource_name="customers/123/billingSetups/1",
        id=1,
        status=SimpleNamespace(name="APPROVED"),
        start_date_time="2026-01-01 00:00:00",
        end_date_time="",
        end_time_type=SimpleNamespace(name="FOREVER"),
        payments_account_info=SimpleNamespace(
            payments_account_name="Monthly account",
            payments_profile_name="Profile",
        ),
    )
    budget = SimpleNamespace(
        resource_name="customers/123/accountBudgets/2",
        status=SimpleNamespace(name="APPROVED"),
        billing_setup=setup.resource_name,
        approved_spending_limit_micros=100_000_000,
        approved_spending_limit_type=SimpleNamespace(name="UNSPECIFIED"),
        adjusted_spending_limit_micros=100_000_000,
        adjusted_spending_limit_type=SimpleNamespace(name="UNSPECIFIED"),
        amount_served_micros=0,
        total_adjustments_micros=0,
        approved_start_date_time="2026-01-01 00:00:00",
        approved_end_date_time="",
        approved_end_time_type=SimpleNamespace(name="FOREVER"),
        purchase_order_number="PO-1",
    )

    @contextmanager
    def fake_google_ads_client(config):
        yield object()

    def fake_search_rows(self, client, customer_id, query):
        del self, client
        normalized = " ".join(query.split())
        queries.append(normalized)
        if "FROM billing_setup" in normalized:
            return [SimpleNamespace(billing_setup=setup)], ["billing-request"]
        return [SimpleNamespace(account_budget=budget)], ["budget-request"]

    monkeypatch.setattr(adapter_module, "google_ads_client", fake_google_ads_client)
    monkeypatch.setattr(GoogleAdsV242Adapter, "_search_rows", fake_search_rows)

    result = GoogleAdsV242Adapter(_config()).fetch_billing_summary("123-456-7890")

    assert len(queries) == 2
    assert all("mutate" not in query.lower() for query in queries)
    assert "billing_setup.payments_account_info.payments_account_name" in queries[0]
    assert "account_budget.approved_spending_limit_micros" in queries[1]
    assert result["billing_setups"][0]["status"] == "APPROVED"
    assert result["account_budgets"][0]["amount_served_micros"] == 0
    assert result["request_ids"] == ["billing-request", "budget-request"]


def test_google_client_config_trims_outer_developer_token_whitespace() -> None:
    config = _config()
    config = GoogleAdsConnectionConfig(
        **{
            **config.__dict__,
            "developer_token": f" \n{config.developer_token}\t",
        }
    )

    google_config = _to_google_ads_client_config(config)

    assert google_config["developer_token"] == "saved-developer-token"
    assert google_config["login_customer_id"] == "5589335362"


def test_connection_error_keeps_google_code_and_request_id(monkeypatch) -> None:
    class FakeGoogleAdsService:
        def search(self, *, customer_id: str, query: str):
            raise RuntimeError("permission denied")

    class FakeClient:
        def get_service(self, name: str) -> FakeGoogleAdsService:
            assert name == "GoogleAdsService"
            return FakeGoogleAdsService()

    @contextmanager
    def fake_google_ads_client(config):
        yield FakeClient()

    monkeypatch.setattr(adapter_module, "google_ads_client", fake_google_ads_client)
    monkeypatch.setattr(
        adapter_module,
        "_google_exception",
        lambda exc, customer_id, campaign_name: (
            [
                {
                    "code": "AUTHORIZATION_ERROR.USER_PERMISSION_DENIED",
                    "message": "User does not have permission",
                }
            ],
            "request-123",
        ),
    )

    result = GoogleAdsV242Adapter(_config()).test_connection()

    assert result.ok is False
    assert result.status == "ERROR"
    assert result.request_id == "request-123"
    assert "AUTHORIZATION_ERROR.USER_PERMISSION_DENIED" in result.message
    assert "Request ID: request-123" in result.message
    assert "не имеет доступа" in result.message


def test_account_sync_error_keeps_google_code_and_request_id(monkeypatch) -> None:
    class FakeGoogleAdsService:
        def search_stream(self, *, customer_id: str, query: str):
            raise RuntimeError("invalid token")

    class FakeClient:
        def get_service(self, name: str) -> FakeGoogleAdsService:
            assert name == "GoogleAdsService"
            return FakeGoogleAdsService()

    @contextmanager
    def fake_google_ads_client(config):
        yield FakeClient()

    monkeypatch.setattr(adapter_module, "google_ads_client", fake_google_ads_client)
    monkeypatch.setattr(
        adapter_module,
        "_google_exception",
        lambda exc, customer_id, campaign_name: (
            [{"code": "AUTHENTICATION_ERROR.DEVELOPER_TOKEN_INVALID", "message": "Token is invalid"}],
            "request-456",
        ),
    )

    with pytest.raises(GoogleAdsAdapterError) as error:
        GoogleAdsV242Adapter(_config()).list_customer_accounts()

    assert "AUTHENTICATION_ERROR.DEVELOPER_TOKEN_INVALID" in str(error.value)
    assert "Request ID: request-456" in str(error.value)


def test_removed_get_customer_is_not_called_anywhere_in_backend() -> None:
    calls: list[str] = []
    for path in (BACKEND_ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get_customer":
                calls.append(f"{path.relative_to(BACKEND_ROOT)}:{node.lineno}")
    assert calls == []


def test_adapter_service_methods_exist_in_installed_google_ads_sdk() -> None:
    client = GoogleAdsClient(
        credentials=AnonymousCredentials(),
        developer_token="test-token",
        login_customer_id="5589335362",
        version="v24",
        use_proto_plus=True,
    )
    expected_methods = {
        "GoogleAdsService": ("search", "search_stream", "mutate"),
        "CustomerService": ("list_accessible_customers",),
        "CampaignBudgetService": ("campaign_budget_path", "mutate_campaign_budgets"),
        "CampaignService": ("campaign_path",),
        "AdGroupService": ("ad_group_path",),
        "AssetService": ("asset_path",),
        "AudienceService": ("audience_path",),
        "YouTubeVideoUploadService": ("create_you_tube_video_upload",),
        "IdentityVerificationService": ("get_identity_verification",),
    }

    source = (BACKEND_ROOT / "app" / "google_ads" / "versions" / "v24_2" / "adapter.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    requested_services = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_service"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert requested_services == set(expected_methods)

    missing: list[str] = []
    for service_name, methods in expected_methods.items():
        service = client.get_service(service_name)
        missing.extend(f"{service_name}.{method}" for method in methods if not hasattr(service, method))
    assert missing == []


def test_account_catalog_reads_supported_user_interest_resource() -> None:
    source = (
        BACKEND_ROOT / "app" / "google_ads" / "versions" / "v24_2" / "adapter.py"
    ).read_text(encoding="utf-8")

    assert "FROM user_interest" in source
    assert "user_interest.resource_name" in source
    assert "user_interest.user_interest_id" in source
    assert "user_interest.taxonomy_type" in source


def test_v25_adapter_boundary_uses_the_installed_v25_sdk_contract() -> None:
    config = replace(_config(), api_version="v25")
    adapter = GoogleAdsV25Adapter(config)
    client = GoogleAdsClient(
        credentials=AnonymousCredentials(),
        developer_token="test-token",
        login_customer_id="5589335362",
        version="v25",
        use_proto_plus=True,
    )

    assert adapter.config.api_version == "v25"
    assert hasattr(client.get_service("GoogleAdsService"), "search")
    assert hasattr(client.get_service("GoogleAdsService"), "mutate")
    assert client.get_type("CampaignOperation") is not None
    with pytest.raises(ValueError):
        GoogleAdsV25Adapter(_config())
