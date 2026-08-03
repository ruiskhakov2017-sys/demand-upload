from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.auth.credentials import AnonymousCredentials

from app.api.routes import oauth as oauth_module
from app.api.routes.google_connections import connection_create_audit_summary
from app.api.schemas import GoogleConnectionCreateIn
from app.api.workflow_schemas import PlanBuildIn, UploadCreateIn
from app.control_center.schemas import ActionPreviewIn
from app.control_center.service import account_payload
from app.core.security import decrypt_json, encrypt_json, hash_token, utcnow
from app.db.models import (
    AuthType,
    CustomerAccount,
    GoogleConnection,
    GoogleCredential,
)
from app.google_ads.connection_credentials import (
    merged_auth_payload,
    store_refresh_token,
)
from app.google_ads.errors import GoogleAdsAdapterError
from app.google_ads.interface import GoogleAdsConnectionConfig
from app.google_ads.request_metadata import unary_call_with_request_id
from app.google_ads.safety import (
    GoogleAdsSafetyError,
    require_execution_mode_for_connection,
    require_fresh_google_test_state,
    require_google_test_connection_target,
)
from app.google_ads.versions.v24_2 import adapter as adapter_module
from app.google_ads.versions.v24_2.adapter import GoogleAdsV242Adapter

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _connection(mode: str = "GOOGLE_TEST") -> GoogleConnection:
    return GoogleConnection(
        id=uuid4(),
        name="google-test" if mode == "GOOGLE_TEST" else "vcc2",
        login_customer_id="3831073849" if mode == "GOOGLE_TEST" else "5589335362",
        auth_type=AuthType.OAUTH_WEB.value,
        environment="TEST",
        connection_mode=mode,
        api_version="v24.2",
        status="VERIFIED",
        test_hierarchy_root_customer_id=(
            "3831073849" if mode == "GOOGLE_TEST" else None
        ),
    )


def _account(connection: GoogleConnection, **overrides) -> CustomerAccount:
    values = {
        "id": uuid4(),
        "connection_id": connection.id,
        "customer_id": "1833869760",
        "manager_customer_id": "3831073849",
        "parent_customer_id": "3831073849",
        "hierarchy_root_customer_id": "3831073849",
        "hierarchy_level": 1,
        "account_type": "CLIENT",
        "can_manage_clients": False,
        "is_test_account": True,
        "is_hidden": False,
        "status": "CLOSED",
        "work_status": "WORKING",
        "test_account_verified_at": utcnow(),
    }
    values.update(overrides)
    return CustomerAccount(**values)


def test_three_execution_modes_are_explicit_and_legacy_live_is_rejected() -> None:
    for mode in ("SIMULATION", "GOOGLE_TEST", "PRODUCTION"):
        assert UploadCreateIn(name="Mode test", execution_mode=mode).execution_mode == mode
        assert PlanBuildIn(execution_mode=mode).execution_mode == mode
        assert (
            ActionPreviewIn(
                campaign_ids=[uuid4()],
                action_type="PAUSE",
                execution_mode=mode,
            ).execution_mode
            == mode
        )
    with pytest.raises(ValueError):
        ActionPreviewIn(
            campaign_ids=[uuid4()],
            action_type="PAUSE",
            execution_mode="LIVE",
        )


def test_google_test_credential_source_is_json_serializable_for_audit() -> None:
    source_id = uuid4()
    payload = GoogleConnectionCreateIn(
        name="google-test",
        login_customer_id="3831073849",
        auth_type="OAUTH_WEB",
        environment="TEST",
        connection_mode="GOOGLE_TEST",
        credential_source_connection_id=source_id,
    )

    summary = connection_create_audit_summary(payload)

    assert summary["credential_source_connection_id"] == str(source_id)
    json.dumps(summary)


def test_production_and_vcc2_mutate_are_blocked_before_google(monkeypatch) -> None:
    entered_google_client = False

    def forbidden_client(config):
        nonlocal entered_google_client
        entered_google_client = True
        raise AssertionError("Google client must not be opened")

    monkeypatch.setattr(adapter_module, "google_ads_client", forbidden_client)
    config = GoogleAdsConnectionConfig(
        connection_id="vcc2",
        name="vcc2",
        login_customer_id="5589335362",
        api_version="v24.2",
        auth_type="OAUTH_WEB",
        environment="TEST",
        connection_mode="PRODUCTION",
        developer_token="secret",
        auth_payload={
            "client_id": "client",
            "client_secret": "secret",
            "refresh_token": "refresh",
        },
    )
    with pytest.raises(GoogleAdsAdapterError, match="PRODUCTION_MUTATE_BLOCKED"):
        GoogleAdsV242Adapter(config).validate_campaign_status(
            "1234567890",
            [{"resource_name": "customers/1234567890/campaigns/1"}],
            "PAUSED",
        )
    assert entered_google_client is False

    vcc2 = _connection("PRODUCTION")
    with pytest.raises(GoogleAdsSafetyError) as error:
        require_google_test_connection_target(vcc2, None, "1234567890")
    assert error.value.code == "GOOGLE_TEST_TARGET_NOT_FOUND"
    with pytest.raises(GoogleAdsSafetyError) as error:
        require_execution_mode_for_connection(vcc2, "PRODUCTION")
    assert error.value.code == "PRODUCTION_MUTATE_BLOCKED"


def test_test_account_membership_freshness_and_confirmation_are_required() -> None:
    connection = _connection()
    account = _account(connection)
    require_google_test_connection_target(
        connection, account, account.customer_id
    )
    fresh = {
        "customer_id": account.customer_id,
        "test_account": True,
        "manager": False,
    }
    require_fresh_google_test_state(
        connection,
        account,
        account.customer_id,
        fresh,
        confirmed_at=utcnow(),
    )

    with pytest.raises(GoogleAdsSafetyError) as missing_confirmation:
        require_fresh_google_test_state(
            connection, account, account.customer_id, fresh
        )
    assert missing_confirmation.value.code == "ACTION_NOT_CONFIRMED"

    account.hierarchy_root_customer_id = "9999999999"
    with pytest.raises(GoogleAdsSafetyError) as wrong_hierarchy:
        require_google_test_connection_target(
            connection, account, account.customer_id
        )
    assert wrong_hierarchy.value.code == "TEST_HIERARCHY_MEMBERSHIP_FAILED"


def test_stale_and_manager_test_targets_are_rejected() -> None:
    connection = _connection()
    stale = _account(
        connection,
        test_account_verified_at=utcnow() - timedelta(hours=1),
    )
    with pytest.raises(GoogleAdsSafetyError) as stale_error:
        require_fresh_google_test_state(
            connection,
            stale,
            stale.customer_id,
            {
                "customer_id": stale.customer_id,
                "test_account": True,
                "manager": False,
            },
            confirmed_at=utcnow(),
        )
    assert stale_error.value.code == "STALE_TEST_ACCOUNT_STATE"

    manager = _account(
        connection,
        customer_id="3831073849",
        account_type="MANAGER",
        can_manage_clients=True,
    )
    with pytest.raises(GoogleAdsSafetyError) as manager_error:
        require_google_test_connection_target(
            connection, manager, manager.customer_id
        )
    assert manager_error.value.code == "MANAGER_MUTATE_BLOCKED"


def test_closed_test_account_is_benign_and_has_honest_no_data_reason() -> None:
    connection = _connection()
    account = _account(connection)
    payload = account_payload(
        account,
        connection.name,
        [],
        {
            "cost_micros": None,
            "data_source_mode": "GOOGLE_TEST",
        },
        0,
    )
    assert payload["has_problem"] is False
    assert (
        payload["google_status_label"]
        == "Тестовый аккаунт — показ рекламы отключён Google"
    )
    assert (
        payload["metrics"]["no_data_reason"]
        == "Нет данных: тестовые аккаунты не показывают рекламу"
    )


def test_refresh_token_is_separate_encrypted_and_does_not_modify_source() -> None:
    source_payload = {
        "client_id": "shared-client",
        "client_secret": "shared-secret",
        "refresh_token": "vcc2-refresh",
    }
    source_credential = GoogleCredential(
        id=uuid4(),
        kind="OAUTH_WEB",
        encrypted_payload=encrypt_json(source_payload),
    )
    original_ciphertext = source_credential.encrypted_payload
    connection = _connection()
    connection.oauth_client_credential = source_credential
    connection.oauth_client_credential_id = source_credential.id

    class FakeDb:
        def add(self, value) -> None:
            if value.id is None:
                value.id = uuid4()

        def flush(self) -> None:
            return None

    store_refresh_token(
        FakeDb(),
        connection,
        "test-user-refresh",
        uuid4(),
    )

    assert source_credential.encrypted_payload == original_ciphertext
    assert decrypt_json(source_credential.encrypted_payload) == source_payload
    assert connection.oauth_refresh_credential is not None
    assert decrypt_json(
        connection.oauth_refresh_credential.encrypted_payload
    ) == {"refresh_token": "test-user-refresh"}
    assert merged_auth_payload(connection) == {
        "client_id": "shared-client",
        "client_secret": "shared-secret",
        "refresh_token": "test-user-refresh",
    }


def test_oauth_callback_stores_own_refresh_and_runs_hierarchy(monkeypatch) -> None:
    source_credential = GoogleCredential(
        id=uuid4(),
        kind="OAUTH_WEB",
        encrypted_payload=encrypt_json(
            {
                "client_id": "shared-client",
                "client_secret": "shared-secret",
                "refresh_token": "vcc2-refresh",
            }
        ),
    )
    original_ciphertext = source_credential.encrypted_payload
    connection = _connection()
    connection.oauth_client_credential = source_credential
    connection.oauth_client_credential_id = source_credential.id
    actor = SimpleNamespace(id=uuid4())
    state = "state-" + "x" * 32
    authorization = SimpleNamespace(
        state_hash=hash_token(state),
        connection_id=connection.id,
        redirect_uri="http://localhost/api/google-connections/oauth/callback",
        code_verifier_encrypted=encrypt_json({"code_verifier": "verifier"}),
        expires_at=utcnow() + timedelta(minutes=5),
        used_at=None,
        created_by_id=actor.id,
    )

    class FakeDb:
        def __init__(self) -> None:
            self.added = []
            self.commits = 0

        def scalar(self, statement):
            return authorization

        def get(self, model, object_id):
            if model is GoogleConnection:
                return connection
            return actor

        def add(self, value) -> None:
            if getattr(value, "id", None) is None:
                value.id = uuid4()
            self.added.append(value)

        def flush(self) -> None:
            return None

        def commit(self) -> None:
            self.commits += 1

    class TokenResponse:
        is_error = False

        @staticmethod
        def json() -> dict:
            return {"refresh_token": "test-user-refresh"}

    monkeypatch.setattr(
        oauth_module.httpx,
        "post",
        lambda *args, **kwargs: TokenResponse(),
    )
    monkeypatch.setattr(
        oauth_module,
        "sync_google_ads_hierarchy",
        lambda db, target: ([SimpleNamespace(), SimpleNamespace()], ["req-hierarchy"]),
    )

    response = oauth_module.oauth_callback(
        state=state,
        code="authorization-code",
        error=None,
        db=FakeDb(),
    )

    assert response.status_code == 302
    assert connection.status == "VERIFIED"
    assert authorization.used_at is not None
    assert source_credential.encrypted_payload == original_ciphertext
    assert connection.oauth_refresh_credential is not None
    assert decrypt_json(
        connection.oauth_refresh_credential.encrypted_payload
    )["refresh_token"] == "test-user-refresh"


def test_success_request_id_is_read_from_google_metadata() -> None:
    class Call:
        @staticmethod
        def initial_metadata():
            return (("request-id", "request-success-123"),)

        @staticmethod
        def trailing_metadata():
            return ()

    class Rpc:
        def with_call(self, request, timeout, metadata):
            assert request == "wire-request"
            assert ("x-goog-request-params", "customer_id=1833869760") in metadata
            return SimpleNamespace(ok=True), Call()

    service = SimpleNamespace(transport=SimpleNamespace(search=Rpc()))
    response, request_id = unary_call_with_request_id(
        service,
        "search",
        SimpleNamespace(_pb="wire-request"),
        timeout=10,
        routing_fields=(("customer_id", "1833869760"),),
    )
    assert response.ok is True
    assert request_id == "request-success-123"


def test_search_request_omits_unsupported_page_size(monkeypatch) -> None:
    google_client = GoogleAdsClient(
        credentials=AnonymousCredentials(),
        developer_token="test",
        version="v24",
        use_proto_plus=True,
    )
    service = SimpleNamespace(transport=SimpleNamespace())
    client = SimpleNamespace(
        get_service=lambda name: service,
        get_type=google_client.get_type,
    )
    response = google_client.get_type("SearchGoogleAdsResponse")

    def fake_unary_call(
        service_arg,
        method,
        request,
        **kwargs,
    ):
        del service_arg, method, kwargs
        populated_fields = {
            field.name for field, _value in request._pb.ListFields()
        }
        assert "page_size" not in populated_fields
        return response._pb, "search-request-id"

    monkeypatch.setattr(
        adapter_module,
        "unary_call_with_request_id",
        fake_unary_call,
    )
    adapter = GoogleAdsV242Adapter(
        GoogleAdsConnectionConfig(
            connection_id="google-test",
            name="google-test",
            login_customer_id="3831073849",
            api_version="v24.2",
            auth_type="OAUTH_WEB",
            environment="TEST",
            connection_mode="GOOGLE_TEST",
            developer_token="test",
            auth_payload={},
        )
    )

    rows, request_ids = adapter._search_rows(
        client,
        "3831073849",
        "SELECT customer.id FROM customer",
    )

    assert rows == []
    assert request_ids == ["search-request-id"]


def test_google_test_migration_is_additive_and_sets_existing_to_production() -> None:
    migration = (
        BACKEND_ROOT
        / "migrations"
        / "versions"
        / "202607290007_google_test_mode.py"
    ).read_text(encoding="utf-8")
    upgrade = migration.split("def downgrade", 1)[0]
    assert "server_default=sa.text(\"'PRODUCTION'\")" in upgrade
    assert "oauth_client_credential_id = auth_credential_id" in upgrade
    assert "op.drop_" not in upgrade
    assert "DELETE FROM" not in upgrade.upper()
    assert "TRUNCATE" not in upgrade.upper()


def test_demand_gen_builder_includes_real_audience_and_paused_campaign(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logo_path = tmp_path / "logo.png"
    logo_path.write_bytes(b"neutral-test-logo")
    monkeypatch.setattr(adapter_module.settings, "storage_root", tmp_path)
    client = GoogleAdsClient(
        credentials=AnonymousCredentials(),
        developer_token="test",
        version="v24",
        use_proto_plus=True,
    )
    adapter = GoogleAdsV242Adapter(
        GoogleAdsConnectionConfig(
            connection_id="google-test",
            name="google-test",
            login_customer_id="3831073849",
            api_version="v24.2",
            auth_type="OAUTH_WEB",
            environment="TEST",
            connection_mode="GOOGLE_TEST",
            developer_token="test",
            auth_payload={},
        )
    )
    operations = adapter._build_operations(
        client,
        "1833869760",
        {
            "customer_id": "1833869760",
            "campaign_name": "API_TEST_ACCEPTANCE",
            "google_campaign_name": "API_TEST_ACCEPTANCE [DGU unit]",
            "deployment_key": "unit",
            "daily_budget_micros": 10_000_000,
            "bidding_strategy": "MAXIMIZE_CLICKS",
            "ad_group_name": "API_TEST_ACCEPTANCE_AD_GROUP",
            "location_ids": ["2840"],
            "language_ids": ["1000"],
            "media_ids": ["logo"],
            "youtube_video_id": "dQw4w9WgXcQ",
            "ad_type": "VIDEO",
            "business_name": "API Test",
            "headlines": ["API test headline"],
            "long_headline": "Neutral Google Ads API test campaign",
            "descriptions": ["Created only in a Google Ads test account"],
            "final_url": "https://example.com/",
            "create_audience": {"name": "API_TEST_ACCEPTANCE_AUDIENCE"},
        },
        [
            {
                "id": "logo",
                "kind": "IMAGE",
                "name": "Google Test acceptance logo",
                "sha256": "1" * 64,
                "storage_key": "logo.png",
                "width": 1254,
                "height": 1254,
                "status": "READY",
            }
        ],
    )
    operation_types = [
        item._pb.WhichOneof("operation") for item in operations
    ]
    assert "audience_operation" in operation_types
    assert "ad_group_criterion_operation" in operation_types
    campaign = next(
        item.campaign_operation.create
        for item in operations
        if item._pb.WhichOneof("operation") == "campaign_operation"
    )
    assert campaign.status == client.enums.CampaignStatusEnum.PAUSED
    assert (
        campaign.bidding_strategy_type
        == client.enums.BiddingStrategyTypeEnum.TARGET_SPEND
    )
    assert campaign._pb.WhichOneof("campaign_bidding_strategy") == "target_spend"
    audience = next(
        item.audience_operation.create
        for item in operations
        if item._pb.WhichOneof("operation") == "audience_operation"
    )
    age_range = audience.dimensions[0].age.age_ranges[0]
    assert age_range.min_age == 18
    assert age_range.max_age == 64
    ad = next(
        item.ad_group_ad_operation.create.ad
        for item in operations
        if item._pb.WhichOneof("operation") == "ad_group_ad_operation"
    )
    assert len(ad.demand_gen_video_responsive_ad.logo_images) == 1
