from __future__ import annotations

import ast
from contextlib import contextmanager
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
        "CampaignBudgetService": ("campaign_budget_path",),
        "CampaignService": ("campaign_path",),
        "AdGroupService": ("ad_group_path",),
        "AssetService": ("asset_path",),
        "YouTubeVideoUploadService": ("create_you_tube_video_upload",),
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
