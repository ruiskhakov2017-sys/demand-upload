from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from openpyxl import Workbook
from PIL import Image

from app.db.models import CampaignUpload, MediaAsset
from app.domain.media import inspect_media
from app.domain.planner import build_plan_snapshot, validate_plan_snapshot
from app.domain.tabular import parse_tabular
from app.google_ads.mock_adapter import MockGoogleAdsAdapter


def test_csv_import_normalizes_columns_and_lists() -> None:
    content = (
        b"Customer ID;Campaign name;Headlines;Descriptions\n"
        b"123-456-7890;Launch;First|Second;Description one|Description two\n"
    )
    rows = parse_tabular("campaigns.csv", content)
    assert rows == [
        {
            "customer_id": "123-456-7890",
            "campaign_name": "Launch",
            "headlines": ["First", "Second"],
            "descriptions": ["Description one", "Description two"],
        }
    ]


def test_xlsx_import_normalizes_the_same_campaign_fields() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Customer ID", "Campaign name", "Headlines", "Descriptions"])
    sheet.append([
        "123-456-7890",
        "XLSX launch",
        "First|Second",
        "Description one|Description two",
    ])
    content = BytesIO()
    workbook.save(content)

    rows = parse_tabular("campaigns.xlsx", content.getvalue())

    assert rows == [
        {
            "customer_id": "123-456-7890",
            "campaign_name": "XLSX launch",
            "headlines": ["First", "Second"],
            "descriptions": ["Description one", "Description two"],
        }
    ]


@pytest.mark.parametrize(
    ("dimensions", "expected_role"),
    [
        ((1200, 1200), "SQUARE"),
        ((1200, 628), "LANDSCAPE"),
        ((960, 1200), "PORTRAIT"),
        ((720, 1280), "TALL"),
    ],
)
def test_image_inspection_assigns_demand_gen_roles(
    tmp_path: Path,
    dimensions: tuple[int, int],
    expected_role: str,
) -> None:
    path = tmp_path / f"{expected_role.lower()}.png"
    Image.new("RGB", dimensions, color=(240, 240, 240)).save(path, "PNG")

    inspection = inspect_media(path, "image/png")

    assert inspection["validation"]["valid"] is True
    assert inspection["validation"]["suggested_role"] == expected_role


def test_plan_is_canonical_paused_and_valid_for_video_simulation() -> None:
    logo_id = uuid4()
    upload = CampaignUpload(
        id=uuid4(),
        name="Acceptance",
        source_type="MANUAL",
        source_rows=[],
        draft={
            "campaign": {
                "customer_id": "123-456-7890",
                "campaign_name": "Demand Gen acceptance",
                "ad_group_name": "Main",
                "final_url": "https://example.com",
                "ad_type": "VIDEO",
                "daily_budget": "10",
                "target_cpa": "5",
                "business_name": "Example",
                "headlines": ["First headline"],
                "long_headline": "A valid long headline",
                "descriptions": ["A valid description"],
                "youtube_video_id": "dQw4w9WgXcQ",
                "media_ids": [str(logo_id)],
                "logo_media_id": str(logo_id),
            }
        },
        current_step=0,
        created_by_id=uuid4(),
    )
    logo = MediaAsset(
        id=logo_id,
        kind="IMAGE",
        source="UPLOAD",
        name="Logo",
        sha256="1" * 64,
        storage_key="media/logo.png",
        content_type="image/png",
        size_bytes=100,
        width=1200,
        height=1200,
        aspect_ratio=1.0,
        status="READY",
        validation={"valid": True, "suggested_role": "LOGO"},
        google_asset_resources={},
        details={},
        created_by_id=upload.created_by_id,
    )
    snapshot, first_fingerprint = build_plan_snapshot(upload, [logo], "SIMULATION")
    second_snapshot, second_fingerprint = build_plan_snapshot(upload, [logo], "SIMULATION")
    validation = validate_plan_snapshot(snapshot)
    assert first_fingerprint == second_fingerprint
    assert snapshot == second_snapshot
    assert snapshot["campaigns"][0]["campaign_status"] == "PAUSED"
    assert snapshot["campaigns"][0]["daily_budget_micros"] == 10_000_000
    assert snapshot["media"][0]["id"] == str(logo_id)
    assert validation["valid"] is True


def test_mock_adapter_is_explicit_and_deterministic() -> None:
    snapshot = {
        "upload_id": "upload-1",
        "campaigns": [{"customer_id": "1234567890", "campaign_name": "Acceptance"}],
    }
    adapter = MockGoogleAdsAdapter()
    validation = adapter.validate_plan(snapshot)
    first = adapter.deploy_plan(snapshot)
    second = adapter.deploy_plan(snapshot)
    assert validation.mode == "SIMULATION"
    assert validation.details["google_contacted"] is False
    assert first.resource_names == second.resource_names
    assert first.request_ids == []


def test_media_content_is_served_inline_from_storage(tmp_path, monkeypatch) -> None:
    from app.api.routes.media import get_media_content
    from app.core.config import settings
    from app.db.models import MediaAsset

    monkeypatch.setattr(settings, "storage_root", tmp_path)
    media_path = tmp_path / "media" / "aa" / "asset.png"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"image-content")
    asset = MediaAsset(
        id=uuid4(),
        kind="IMAGE",
        source="UPLOAD",
        name="asset.png",
        sha256="a" * 64,
        storage_key="media/aa/asset.png",
        content_type="image/png",
        size_bytes=13,
        status="READY",
        validation={"valid": True},
        google_asset_resources={},
        details={},
        created_by_id=uuid4(),
    )

    class FakeSession:
        def get(self, _model, media_id):
            return asset if media_id == asset.id else None

    response = get_media_content(asset.id, db=FakeSession(), user=None)
    assert Path(response.path).read_bytes() == b"image-content"
    assert response.media_type == "image/png"
    assert response.headers["content-disposition"].startswith("inline;")


def test_brocard_client_aggregates_accounts_cards_and_request_ids() -> None:
    from app.integrations.brocard import BrocardClient

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret"
        if request.url.path.endswith("/accounts"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"balance": "40.31", "available": "35.00", "currency": "usd"},
                        {"balance": "100.00", "available": "90.00", "currency": "usd"},
                    ],
                    "last_page": 1,
                    "request_id": "accounts-request",
                },
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {"archived": False, "state": {"label": "Active"}},
                    {"archived": False, "state": {"label": "Paused"}},
                    {"archived": True, "state": {"label": "Active"}},
                ],
                "last_page": 1,
                "request_id": "cards-request",
            },
        )

    with BrocardClient("https://private.mybrocard.com", "secret", transport=httpx.MockTransport(handler)) as client:
        snapshot = client.fetch_snapshot()

    assert snapshot.balance == 140.31
    assert snapshot.currency == "USD"
    assert snapshot.cards_total == 3
    assert snapshot.cards_active == 1
    assert snapshot.provider_payload["available"] == "125.00"
    assert snapshot.provider_payload["request_ids"] == ["accounts-request", "cards-request"]


def test_upload_progress_does_not_reset_completed_status(monkeypatch) -> None:
    from app.api.routes import uploads as upload_routes
    from app.api.workflow_schemas import UploadPatchIn

    upload = CampaignUpload(
        id=uuid4(),
        name="Acceptance",
        status="SUCCEEDED",
        source_type="MANUAL",
        source_rows=[],
        draft={"campaign": {"campaign_name": "Acceptance"}},
        current_step=6,
        created_by_id=uuid4(),
        last_error="previous error",
    )

    class FakeSession:
        def commit(self) -> None:
            pass

        def refresh(self, _upload) -> None:
            pass

    monkeypatch.setattr(upload_routes, "_get_upload", lambda _db, _upload_id: upload)
    monkeypatch.setattr(upload_routes, "record_audit", lambda *_args, **_kwargs: None)

    upload_routes.update_upload(
        upload.id,
        UploadPatchIn(current_step=7, draft=upload.draft),
        request=None,
        db=FakeSession(),
        user=None,
    )
    assert upload.status == "SUCCEEDED"
    assert upload.last_error == "previous error"

    upload_routes.update_upload(
        upload.id,
        UploadPatchIn(draft={"campaign": {"campaign_name": "Changed"}}),
        request=None,
        db=FakeSession(),
        user=None,
    )
    assert upload.status == "DRAFT"
    assert upload.last_error is None


def test_v24_operation_builder_forces_paused_campaign() -> None:
    from google.ads.googleads.client import GoogleAdsClient
    from google.auth.credentials import AnonymousCredentials

    from app.google_ads.interface import GoogleAdsConnectionConfig
    from app.google_ads.versions.v24_2.adapter import GoogleAdsV242Adapter

    client = GoogleAdsClient(
        credentials=AnonymousCredentials(),
        developer_token="test",
        version="v24",
        use_proto_plus=True,
    )
    adapter = GoogleAdsV242Adapter(
        GoogleAdsConnectionConfig(
            connection_id="test",
            name="test",
            login_customer_id="1234567890",
            api_version="v24.2",
            auth_type="OAUTH_WEB",
            environment="TEST",
            developer_token="test",
            auth_payload={},
        )
    )
    campaign = {
        "customer_id": "1234567890",
        "campaign_name": "Acceptance",
        "google_campaign_name": "Acceptance [DGU test]",
        "daily_budget_micros": 10_000_000,
        "target_cpa_micros": 5_000_000,
        "ad_group_name": "Main",
        "location_ids": ["2840"],
        "language_ids": ["1000"],
        "media_ids": [],
        "youtube_video_id": "dQw4w9WgXcQ",
        "ad_type": "VIDEO",
        "business_name": "Example",
        "headlines": ["First headline"],
        "long_headline": "A valid long headline",
        "descriptions": ["A valid description"],
        "final_url": "https://example.com",
    }
    operations = adapter._build_operations(client, "1234567890", campaign, [])
    created_campaign = operations[1].campaign_operation.create
    assert created_campaign.status == client.enums.CampaignStatusEnum.PAUSED
    assert created_campaign.advertising_channel_type == client.enums.AdvertisingChannelTypeEnum.DEMAND_GEN
    assert operations[-1].ad_group_ad_operation.create.ad.demand_gen_video_responsive_ad.videos
