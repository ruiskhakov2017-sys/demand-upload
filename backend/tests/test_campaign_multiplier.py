from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.api.routes import plans as plans_route
from app.api.routes.launch_groups import _select_instances
from app.api.workflow_schemas import CampaignStatusIn, PlanBuildIn
from app.db.models import (
    AccountTestBundle,
    Base,
    CampaignInstance,
    CampaignStatusAction,
    CampaignUpload,
    DeploymentPlan,
    LaunchBatch,
    User,
)
from app.domain.batch_generator import GenerationError, generate_batch_matrix, generate_budgets
from app.domain.planner import validate_plan_snapshot
from app.google_ads.mock_adapter import MockGoogleAdsAdapter
from app.jobs.tasks import _apply_local_status
from app.main import app


def _accounts(counts: list[int]) -> list[dict]:
    return [
        {
            "customer_id": str(900_000_0001 + index),
            "account_name": f"Account-{index + 1}",
            "currency_code": "USD" if index % 2 == 0 else "EUR",
            "time_zone": "Europe/Prague",
            "campaigns_count": count,
            "overrides": {},
        }
        for index, count in enumerate(counts)
    ]


def _config(counts: list[int], **updates: object) -> dict:
    config = {
        "batch_name": "Acceptance",
        "template_name": "DemandGen",
        "accounts": _accounts(counts),
        "campaigns_per_account": 3,
        "copy_mode": "EXACT_COPY",
        "name_pattern": "{account_name}_{date}_{sequence}",
        "generation_seed": "stable-seed",
        "template_defaults": {
            "campaign": {"ad_type": "VIDEO", "ad_group_name": "Main"},
            "bidding": {"strategy": "TARGET_CPA", "target_cpa": 25},
            "targeting": {"location_ids": ["2203"], "language_ids": ["1000"]},
            "url": {
                "final_url": "https://example.com",
                "tracking_template": "https://tracker.example/click?url={lpurl}&cid={campaignid}",
            },
            "texts": {
                "business_name": "Example",
                "headlines": ["First headline"],
                "long_headline": "A valid long headline",
                "descriptions": ["A valid description"],
            },
        },
        "budget": {"mode": "FIXED", "fixed": 25},
        "creative": {
            "media_ids": ["logo", "asset-1", "asset-2", "asset-3"],
            "logo_media_id": "logo",
        },
        "campaign_overrides": {},
    }
    config.update(updates)
    return config


def _matrix(config: dict, batch_id: UUID | None = None) -> dict:
    return generate_batch_matrix(
        batch_id or UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        config,
        datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    )


def test_twenty_accounts_keep_each_manual_copy_count() -> None:
    counts = [10, 7, 5, 3, 1] * 4
    matrix = _matrix(_config(counts))
    assert len(matrix["bundles"]) == 20
    assert [item["campaigns_count"] for item in matrix["bundles"]] == counts
    assert len(matrix["instances"]) == sum(counts)
    assert matrix["financial_preview"]["accounts"] == 20
    assert matrix["financial_preview"]["launch_groups"] == 20


def test_arbitrary_copy_count_is_supported() -> None:
    matrix = _matrix(_config([17]))
    assert len(matrix["instances"]) == 17
    assert [item["campaign_sequence"] for item in matrix["instances"]] == list(range(1, 18))


def test_exact_copy_preserves_all_user_settings() -> None:
    instances = _matrix(_config([3]))["instances"]
    fields = ["campaign_settings", "bidding", "targeting", "url_settings", "texts", "creative_assignment"]
    for field in fields:
        assert instances[0][field] == instances[1][field] == instances[2][field]
    assert len({item["id"] for item in instances}) == 3
    assert len({item["campaign_name"] for item in instances}) == 3
    assert len({item["deployment_key"] for item in instances}) == 3
    assert all(item["campaign_status"] == "PAUSED" for item in instances)


def test_range_budgets_follow_minimum_maximum_and_step() -> None:
    budget = {
        "mode": "RANGE",
        "minimum": 10,
        "maximum": 20,
        "step": 2.5,
        "distribution": "RANDOM",
        "seed": "range",
    }
    values = generate_budgets(budget, 40, "USD", "fallback")
    assert all(10_000_000 <= item <= 20_000_000 for item in values)
    assert all((item - 10_000_000) % 2_500_000 == 0 for item in values)


def test_balanced_random_includes_both_range_boundaries() -> None:
    values = generate_budgets(
        {
            "mode": "RANGE",
            "minimum": 10,
            "maximum": 20,
            "step": 1,
            "distribution": "BALANCED_RANDOM",
            "seed": "balanced",
        },
        7,
        "USD",
        "fallback",
    )
    assert min(values) == 10_000_000
    assert max(values) == 20_000_000


def test_manual_budget_list_assigns_one_value_per_copy() -> None:
    values = generate_budgets(
        {"mode": "MANUAL_LIST", "manual_values": [11, 12.5, 14]},
        3,
        "USD",
        "manual",
    )
    assert values == [11_000_000, 12_500_000, 14_000_000]


def test_per_account_budget_override_is_applied() -> None:
    config = _config([2, 2], budget={"mode": "PER_ACCOUNT_OVERRIDE", "minimum": 10, "maximum": 20, "step": 1})
    config["accounts"][0]["overrides"] = {"budget": {"mode": "FIXED", "fixed": 31}}
    config["accounts"][1]["overrides"] = {"budget": {"mode": "FIXED", "fixed": 47}}
    matrix = _matrix(config)
    assert [item["budget_micros"] for item in matrix["bundles"][0]["instances"]] == [31_000_000] * 2
    assert [item["budget_micros"] for item in matrix["bundles"][1]["instances"]] == [47_000_000] * 2


def test_per_campaign_budget_override_is_applied() -> None:
    config = _config([3])
    customer_id = config["accounts"][0]["customer_id"]
    config["campaign_overrides"] = {f"{customer_id}:2": {"budget": 99}}
    values = [item["budget_micros"] for item in _matrix(config)["instances"]]
    assert values == [25_000_000, 99_000_000, 25_000_000]


def test_generation_is_stable_across_reload_validate_and_retry() -> None:
    batch_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    config = _config(
        [10, 7, 5],
        budget={
            "mode": "RANGE",
            "minimum": 10,
            "maximum": 100,
            "step": 5,
            "distribution": "BALANCED_RANDOM",
            "seed": "immutable",
        },
    )
    first = _matrix(config, batch_id)
    second = _matrix(config, batch_id)
    assert first == second
    assert [item["budget_micros"] for item in first["instances"]] == [
        item["budget_micros"] for item in second["instances"]
    ]
    assert [item["id"] for item in first["instances"]] == [item["id"] for item in second["instances"]]


def test_random_creative_assignment_is_seeded() -> None:
    config = _config(
        [8],
        copy_mode="RANDOM_CREATIVE_SUBSET",
        creative={
            "media_ids": ["logo", "a", "b", "c", "d", "e"],
            "logo_media_id": "logo",
            "minimum_count": 2,
            "maximum_count": 4,
            "seed": "creative-seed",
        },
    )
    first = _matrix(config)
    second = _matrix(config)
    assert [item["creative_assignment"] for item in first["instances"]] == [
        item["creative_assignment"] for item in second["instances"]
    ]
    assert all(
        item["creative_assignment"]["media_ids"][0] == "logo"
        and item["creative_assignment"]["logo_media_id"] == "logo"
        for item in first["instances"]
    )


@pytest.mark.parametrize(
    ("copy_mode", "creative"),
    [
        (
            "EXACT_COPY",
            {
                "media_ids": ["asset-1", "logo", "asset-2"],
                "logo_media_id": "logo",
            },
        ),
        (
            "ROTATE_CREATIVE_SETS",
            {
                "logo_media_id": "logo",
                "sets": [
                    {"key": "one", "media_ids": ["asset-1"]},
                    {"key": "two", "media_ids": ["asset-2"]},
                ],
            },
        ),
        (
            "RANDOM_CREATIVE_SUBSET",
            {
                "media_ids": ["asset-1", "asset-2", "logo", "asset-3"],
                "logo_media_id": "logo",
                "minimum_count": 1,
                "maximum_count": 2,
                "seed": "required-logo",
            },
        ),
    ],
)
def test_required_logo_is_preserved_by_every_creative_distribution(
    copy_mode: str,
    creative: dict,
) -> None:
    instances = _matrix(
        _config([7], copy_mode=copy_mode, creative=creative)
    )["instances"]

    assert all(item["creative_assignment"]["logo_media_id"] == "logo" for item in instances)
    assert all(item["creative_assignment"]["media_ids"][0] == "logo" for item in instances)


def test_valuetrack_is_preserved_and_internal_parameter_is_opt_in() -> None:
    without_parameter = _matrix(_config([1]))["instances"][0]["url_settings"]
    assert without_parameter["tracking_template"].endswith("cid={campaignid}")
    assert "dgu_instance=" not in str(without_parameter.get("final_url_suffix") or "")

    config = _config([1])
    config["template_defaults"]["url"]["append_dgu_instance"] = True
    config["template_defaults"]["url"]["final_url_suffix"] = "utm_source=dgu&cid={campaignid}"
    with_parameter = _matrix(config)["instances"][0]["url_settings"]
    assert with_parameter["final_url_suffix"].startswith("utm_source=dgu&cid={campaignid}&dgu_instance=")
    assert with_parameter["dgu_instance_code"] in with_parameter["final_url_suffix"]


def test_duplicate_exact_copies_are_a_warning_not_an_error() -> None:
    campaign = {
        "customer_id": "1234567890",
        "campaign_name": "Copy 1",
        "ad_group_name": "Main",
        "business_name": "Example",
        "final_url": "https://example.com",
        "daily_budget_micros": 10_000_000,
        "bidding_strategy": "TARGET_CPA",
        "target_cpa_micros": 5_000_000,
        "location_ids": ["2203"],
        "language_ids": ["1000"],
        "ad_type": "VIDEO",
        "headlines": ["First headline"],
        "long_headline": "A valid long headline",
        "descriptions": ["A valid description"],
        "youtube_video_id": "dQw4w9WgXcQ",
        "media_ids": ["logo"],
        "logo_media_id": "logo",
    }
    second = deepcopy(campaign)
    second["campaign_name"] = "Copy 2"
    result = validate_plan_snapshot(
        {
            "campaigns": [campaign, second],
            "media": [
                {
                    "id": "logo",
                    "kind": "IMAGE",
                    "name": "Logo",
                    "width": 1200,
                    "height": 1200,
                    "status": "READY",
                }
            ],
            "execution_mode": "SIMULATION",
        }
    )
    assert result["valid"] is True
    assert any(item["code"] == "INTENTIONAL_DUPLICATES" for item in result["warnings"])


def test_local_validation_checks_url_options_and_account_owned_audiences() -> None:
    campaign = {
        "customer_id": "1234567890",
        "campaign_name": "Validated options",
        "ad_group_name": "Main",
        "business_name": "Example",
        "final_url": "https://example.com",
        "mobile_final_url": "not-a-url",
        "tracking_template": "https://tracker.example/click",
        "final_url_suffix": "?utm_source=test",
        "display_path": "this-part-is-far-too-long/second/third",
        "custom_parameters": [{"key": "invalid-key", "value": "ok"}],
        "daily_budget_micros": 10_000_000,
        "bidding_strategy": "TARGET_CPA",
        "target_cpa_micros": 5_000_000,
        "location_ids": ["2203"],
        "language_ids": ["1000"],
        "ad_type": "VIDEO",
        "headlines": ["First headline"],
        "long_headline": "A valid long headline",
        "descriptions": ["A valid description"],
        "youtube_video_id": "dQw4w9WgXcQ",
        "media_ids": ["logo"],
        "logo_media_id": "logo",
        "user_interest_resource_names": ["customers/9999999999/userInterests/1"],
        "life_event_ids": ["not-numeric"],
    }
    result = validate_plan_snapshot(
        {
            "campaigns": [campaign],
            "media": [
                {
                    "id": "logo",
                    "kind": "IMAGE",
                    "name": "Logo",
                    "width": 1200,
                    "height": 1200,
                    "status": "READY",
                }
            ],
            "execution_mode": "SIMULATION",
        }
    )

    codes = {item["code"] for item in result["errors"]}
    assert {
        "INVALID_MOBILE_URL",
        "TRACKING_TEMPLATE_LPURL_REQUIRED",
        "INVALID_FINAL_URL_SUFFIX",
        "INVALID_DISPLAY_PATH",
        "INVALID_CUSTOM_PARAMETER_KEY",
        "CROSS_ACCOUNT_RESOURCE",
        "INVALID_LIFE_EVENT",
    } <= codes


def test_mock_validation_and_deployment_never_contact_google_and_stay_paused() -> None:
    campaigns = _matrix(_config([3]))["instances"]
    snapshot = {"upload_id": "upload", "campaigns": campaigns}
    adapter = MockGoogleAdsAdapter()
    validation = adapter.validate_plan(snapshot)
    first = adapter.deploy_plan(snapshot)
    retry = adapter.deploy_plan(snapshot)
    assert validation.details["google_contacted"] is False
    assert validation.details["campaigns_checked"] == 3
    assert first.details["campaign_status"] == "PAUSED"
    assert first.details["google_contacted"] is False
    assert first.resource_names == retry.resource_names
    assert len(first.resource_names) == 3


def test_build_plan_from_matrix_passes_media_and_execution_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    user = User(id=uuid4(), username="qa", password_hash="hash", role="ADMIN", is_active=True)
    upload = CampaignUpload(
        id=uuid4(),
        name="Acceptance",
        status="DRAFT",
        draft={},
        current_step=15,
        created_by_id=user.id,
    )
    batch = LaunchBatch(
        id=uuid4(),
        upload_id=upload.id,
        name="Acceptance",
        generation_seed="stable",
        generation_time=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
        name_pattern="{account_name}_{sequence}",
        financial_preview={},
        created_by_id=user.id,
    )

    class EmptyRows:
        def all(self) -> list:
            return []

    class FakeDb:
        def get(self, model: type, entity_id: UUID):
            return upload if model is CampaignUpload and entity_id == upload.id else None

        def scalars(self, statement: object) -> EmptyRows:
            return EmptyRows()

        def scalar(self, statement: object) -> None:
            return None

        def add(self, item: object) -> None:
            if isinstance(item, DeploymentPlan) and item.id is None:
                item.id = uuid4()

        def flush(self) -> None:
            return None

        def commit(self) -> None:
            return None

        def refresh(self, item: object) -> None:
            return None

    captured: dict[str, object] = {}

    def fake_batch_snapshot(
        upload_arg: CampaignUpload,
        batch_arg: LaunchBatch,
        bundles_arg: list,
        instances_arg: list,
        media_arg: list,
        execution_mode_arg: str,
    ) -> tuple[dict, str]:
        captured.update(media=media_arg, execution_mode=execution_mode_arg)
        return {"campaigns": [], "media": [], "execution_mode": execution_mode_arg}, "fingerprint"

    monkeypatch.setattr(plans_route, "_load_batch_context", lambda db, item: (batch, [], []))
    monkeypatch.setattr(plans_route, "build_batch_plan_snapshot", fake_batch_snapshot)
    monkeypatch.setattr(
        plans_route,
        "validate_plan_snapshot",
        lambda snapshot: {"valid": True, "errors": [], "warnings": []},
    )
    monkeypatch.setattr(plans_route, "record_audit", lambda *args, **kwargs: None)

    plan = plans_route.build_plan(
        upload.id,
        PlanBuildIn(execution_mode="SIMULATION"),
        None,
        FakeDb(),
        user,
    )

    assert captured == {"media": [], "execution_mode": "SIMULATION"}
    assert plan.launch_batch_id == batch.id


def test_only_manual_enable_and_pause_status_actions_are_accepted() -> None:
    assert CampaignStatusIn(action="ENABLE").action == "ENABLE"
    assert CampaignStatusIn(action="PAUSE").action == "PAUSE"
    with pytest.raises(ValidationError):
        CampaignStatusIn(action="KEEP_ONLY_WINNER")
    with pytest.raises(ValidationError):
        CampaignStatusIn(action="RETURN_TO_TEST")


def test_manual_status_updates_selected_campaigns_only() -> None:
    group = AccountTestBundle(status="READY")
    instances = [
        CampaignInstance(id=uuid4(), status="PAUSED"),
        CampaignInstance(id=uuid4(), status="PAUSED"),
    ]
    selected = _select_instances(instances, [instances[0].id])
    enable = CampaignStatusAction(action="ENABLE", requested_status="ENABLED")
    _apply_local_status(enable, group, selected)
    assert instances[0].status == "ENABLED"
    assert instances[1].status == "PAUSED"
    assert group.status == "ACTIVE"

    pause = CampaignStatusAction(action="PAUSE", requested_status="PAUSED")
    _apply_local_status(pause, group, instances)
    assert [item.status for item in instances] == ["PAUSED", "PAUSED"]
    assert group.status == "PAUSED"


def test_no_automatic_decision_models_or_api_endpoints_exist() -> None:
    prohibited_tables = {"winner_decisions", "evaluation_rules", "evaluation_runs", "automatic_pause_rules"}
    assert prohibited_tables.isdisjoint(Base.metadata.tables)
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/launch-groups/{group_id}/winner" not in paths
    assert "/api/launch-groups/{group_id}/evaluate" not in paths
    assert "/api/launch-groups/{group_id}/rules" not in paths
    assert not any("keitaro" in path.lower() for path in paths)


def test_invalid_copy_count_and_insufficient_manual_budgets_fail_early() -> None:
    with pytest.raises(GenerationError):
        _matrix(_config([0]))
    with pytest.raises(GenerationError):
        generate_budgets({"mode": "MANUAL_LIST", "manual_values": [1]}, 2, "USD", "manual")
