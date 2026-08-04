from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.ai import orchestrator
from app.ai.policy import ToolContext, authorize_tool, enforce_mode_for_role, require_allowed_ids
from app.ai.providers import PROVIDER_REGISTRY, ProvenanceEnvelope, provider_by_id
from app.ai.schemas import (
    AccountFilterArgs,
    ActionSelectionDraftArgs,
    AiScope,
    ConversationCreateIn,
    EntityIdArgs,
    RuleDraftArgs,
    ToolRisk,
    validate_draft_payload,
)
from app.ai.tools import ALL_ROLES, EDIT_ROLES, ToolRegistry, _envelope, _get_moderation_status
from app.control_center.service import with_derived_metrics
from app.db.models import AccountWorkStatus


def context(*, role: str = "ADMIN", authority: str = "READ_ONLY", environment: str = "SIMULATION") -> ToolContext:
    account_id = uuid4()
    return ToolContext(
        user_id=uuid4(),
        role=role,
        session_id=uuid4(),
        authority_mode=authority,
        google_environment=environment,
        allowed_connection_ids=frozenset({uuid4()}),
        allowed_mcc_ids=frozenset({uuid4()}),
        allowed_geo_ids=frozenset({uuid4()}),
        allowed_account_ids=frozenset({account_id}),
        allowed_campaign_ids=frozenset({uuid4()}),
        request_id="request-id",
        ai_run_id=uuid4(),
        locale="ru",
        timezone="Europe/Moscow",
        row_limit=100,
        date_limit=90,
        deadline=datetime.now(UTC) + timedelta(minutes=1),
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 4),
    )


def gates(**overrides: bool) -> dict[str, bool]:
    value = {
        "production_read_enabled": False,
        "production_actions_enabled": False,
        "pause_actions_enabled": False,
        "enable_actions_enabled": False,
        "budget_actions_enabled": False,
        "demand_gen_actions_enabled": False,
        "live_rules_enabled": False,
    }
    value.update(overrides)
    return value


def test_strict_input_schemas_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        AiScope.model_validate({"period": "7d", "secret_override": "ADMIN"})
    with pytest.raises(ValidationError):
        ConversationCreateIn.model_validate({"title": "x", "role": "ADMIN"})
    with pytest.raises(ValidationError):
        AccountFilterArgs.model_validate({"limit": 10, "raw_sql": "select *"})
    with pytest.raises(ValidationError):
        AiScope.model_validate({"metric_source": "FAKE_TRACKER"})


def test_rule_draft_supports_bounded_nested_and_or_groups() -> None:
    payload = {
        "name": "Nested rule",
        "scope": {},
        "logic": "AND",
        "conditions": [
            {
                "logic": "OR",
                "conditions": [
                    {"field": "campaign.metrics.cost_micros", "operator": "gte", "value": 100},
                    {"field": "campaign.status", "operator": "eq", "value": "PAUSED"},
                ],
            }
        ],
        "actions": ["NOTIFY"],
        "explanation": "Deterministic nested condition",
    }
    assert RuleDraftArgs.model_validate(payload).conditions[0].logic == "OR"

    node = payload["conditions"][0]
    for _ in range(5):
        node = {"logic": "AND", "conditions": [node]}
    payload["conditions"] = [node]
    with pytest.raises(ValidationError, match="Глубина"):
        RuleDraftArgs.model_validate(payload)


def test_snapshot_provenance_never_claims_current_time_without_source_timestamp() -> None:
    missing = _envelope(context(), {"items": []}, "ACCOUNT_PERFORMANCE", "GOOGLE_ADS_SNAPSHOT")
    assert missing["provenance"]["observed_at"] is None
    assert missing["provenance"]["freshness"] == "UNKNOWN"
    assert missing["provenance"]["completeness"] == "PARTIAL"
    assert "SOURCE_TIMESTAMP_UNAVAILABLE" in missing["provenance"]["warnings"]

    observed = datetime.now(UTC) - timedelta(days=2)
    stale = _envelope(
        context(),
        {
            "items": [
                {"currency_code": "USD", "time_zone": "UTC", "metrics": {"data_observed_at": observed}},
                {
                    "currency_code": "KES",
                    "time_zone": "Africa/Nairobi",
                    "metrics": {"data_observed_at": observed},
                },
            ]
        },
        "ACCOUNT_PERFORMANCE",
        "GOOGLE_ADS_SNAPSHOT",
    )
    assert stale["provenance"]["observed_at"] == observed
    assert stale["provenance"]["freshness"] == "STALE"
    assert stale["provenance"]["original_currency"] is None
    assert "MIXED_CURRENCIES_NOT_AGGREGATED" in stale["provenance"]["warnings"]
    assert "MULTIPLE_ACCOUNT_TIMEZONES" in stale["provenance"]["warnings"]


def test_moderation_tool_uses_the_real_ad_primary_status_field() -> None:
    current = context()
    campaign_id = next(iter(current.allowed_campaign_ids))

    class Result:
        def all(self):
            return [
                SimpleNamespace(
                    id=uuid4(),
                    primary_status="NOT_ELIGIBLE",
                    policy_summary={"review": "complete"},
                    disapproval_reasons=["POLICY"],
                )
            ]

    class Db:
        def get(self, _model, _id):
            return SimpleNamespace(id=campaign_id, policy_status="LIMITED", policy_issues=[])

        def scalars(self, _statement):
            return Result()

    result = _get_moderation_status(Db(), current, EntityIdArgs(entity_id=campaign_id))
    assert result["data"]["ads"][0]["policy_status"] == "NOT_ELIGIBLE"


def test_action_budget_requires_positive_amount() -> None:
    with pytest.raises(ValidationError):
        ActionSelectionDraftArgs(campaign_ids=[uuid4()], action_type="SET_BUDGET", amount_micros=None)
    with pytest.raises(ValidationError):
        ActionSelectionDraftArgs(campaign_ids=[uuid4()], action_type="SET_BUDGET", amount_micros=0)


def test_draft_editor_payload_is_revalidated() -> None:
    account_id = uuid4()
    payload = validate_draft_payload(
        "WORK_STATUS", {"account_ids": [str(account_id)], "work_status": "READY", "reason": "Проверено"}
    )
    assert payload["work_status"] == "READY"
    with pytest.raises(ValidationError):
        validate_draft_payload(
            "WORK_STATUS", {"account_ids": [str(account_id)], "work_status": "SUSPENDED", "reason": "bad"}
        )


def test_tool_registry_is_complete_strict_and_has_callable_handlers() -> None:
    registry = ToolRegistry()
    names = {item.name for item in registry.specs}
    assert len([item for item in registry.specs if item.risk == ToolRisk.READ]) == 18
    assert len([item for item in registry.specs if item.risk == ToolRisk.QUEUED_REFRESH]) == 3
    assert len([item for item in registry.specs if item.risk == ToolRisk.DRAFT]) == 9
    assert len([item for item in registry.specs if item.risk == ToolRisk.PREVIEW]) == 5
    assert all(callable(item.handler) for item in registry.specs)
    assert not any(word in name for name in names for word in ("confirm", "execute", "mutate", "deploy_now"))
    for item in registry.specs:
        schema = item.openai_schema()
        assert schema["strict"] is True
        assert schema["parameters"]["additionalProperties"] is False
        assert set(schema["parameters"].get("properties", {})) == set(schema["parameters"].get("required", []))


def test_tool_context_is_immutable() -> None:
    value = context()
    assert value.public_scope()["metric_source"] == "GOOGLE_ADS"
    assert value.public_scope()["currency"] is None
    with pytest.raises(FrozenInstanceError):
        value.role = "VIEWER"  # type: ignore[misc]


def test_source_provider_registry_is_typed_and_external_connectors_stay_disabled() -> None:
    identifiers = {provider.capabilities().provider_id for provider in PROVIDER_REGISTRY}
    assert identifiers == {"GOOGLE_ADS", "BUSINESS", "KEITARO", "BROCARD"}
    assert provider_by_id("google_ads") is not None
    assert provider_by_id("unknown") is None
    external = [
        provider
        for provider in PROVIDER_REGISTRY
        if provider.capabilities().provider_id in {"KEITARO", "BROCARD"}
    ]
    for provider in external:
        status = provider.status(SimpleNamespace(scalar=lambda _statement: 0))
        assert status.configured is False
        assert status.enabled is False
        assert status.setup_status == "CONNECTOR_NOT_IMPLEMENTED"


def test_provider_normalizes_a_common_provenance_envelope() -> None:
    provider = provider_by_id("GOOGLE_ADS")
    assert provider is not None
    envelope = provider.normalize_provenance(
        {
            "semantic_metric": "COST",
            "source_id": "customer.metric",
            "attribution": "GOOGLE_ADS_ATTRIBUTED",
            "observed_at": "2026-08-04T10:00:00Z",
            "synced_at": "2026-08-04T10:05:00Z",
            "original_currency": "USD",
            "completeness": "COMPLETE",
        }
    )
    assert isinstance(envelope, ProvenanceEnvelope)
    assert envelope.provider == "GOOGLE_ADS"
    assert envelope.original_currency == "USD"


def test_global_rate_and_per_user_cost_limits_are_independently_enforced() -> None:
    class ScalarDb:
        def __init__(self, values):
            self.values = iter(values)

        def scalar(self, _statement):
            return next(self.values)

    limits = {
        "daily_hard_budget_usd": 100,
        "monthly_hard_budget_usd": 1000,
        "user_daily_hard_budget_usd": 5,
        "user_monthly_hard_budget_usd": 50,
    }
    with pytest.raises(orchestrator.ToolExecutionError, match="Общий лимит AI-запросов") as global_limit:
        orchestrator._enforce_usage_limits(
            ScalarDb([0, orchestrator.settings.ai_global_rate_limit_per_minute]), context(), limits
        )
    assert global_limit.value.code == "AI_GLOBAL_RATE_LIMIT"
    with pytest.raises(orchestrator.ToolExecutionError, match="Ваш дневной лимит") as user_limit:
        orchestrator._enforce_usage_limits(ScalarDb([0, 0, 0, 0, 0, 0, 5, 0]), context(), limits)
    assert user_limit.value.code == "AI_USER_DAILY_BUDGET_EXHAUSTED"


def test_provider_circuit_opens_after_threshold_and_success_resets_it() -> None:
    setting = SimpleNamespace(
        settings={
            "provider_circuit_failure_threshold": 2,
            "provider_circuit_cooldown_seconds": 60,
        }
    )

    class CircuitDb:
        def __init__(self):
            self.commits = 0

        @staticmethod
        def scalar(_statement):
            return setting

        def commit(self):
            self.commits += 1

    db = CircuitDb()
    orchestrator._record_provider_failure(db)
    assert setting.settings["provider_failure_count"] == 1
    orchestrator._record_provider_failure(db)
    assert "provider_circuit_open_until" in setting.settings
    orchestrator._record_provider_success(db)
    assert setting.settings["provider_failure_count"] == 0
    assert "provider_circuit_open_until" not in setting.settings


@pytest.mark.parametrize(
    ("role", "authority", "risk", "roles", "allowed"),
    [
        ("VIEWER", "READ_ONLY", ToolRisk.READ, ALL_ROLES, True),
        ("VIEWER", "READ_ONLY", ToolRisk.QUEUED_REFRESH, EDIT_ROLES, False),
        ("VIEWER", "DRAFT_ONLY", ToolRisk.DRAFT, EDIT_ROLES, False),
        ("OPERATOR", "READ_ONLY", ToolRisk.DRAFT, EDIT_ROLES, False),
        ("OPERATOR", "DRAFT_ONLY", ToolRisk.DRAFT, EDIT_ROLES, True),
        ("ADMIN", "CONFIRM_REQUIRED", ToolRisk.PREVIEW, EDIT_ROLES, True),
        ("ADMIN", "DRAFT_ONLY", ToolRisk.PREVIEW, EDIT_ROLES, False),
    ],
)
def test_role_mode_tool_policy(role: str, authority: str, risk: ToolRisk, roles: frozenset[str], allowed: bool) -> None:
    if allowed:
        authorize_tool(
            context(role=role, authority=authority), risk=risk, required_roles=roles, feature_flag=None, gates=gates()
        )
    else:
        with pytest.raises(PermissionError):
            authorize_tool(
                context(role=role, authority=authority),
                risk=risk,
                required_roles=roles,
                feature_flag=None,
                gates=gates(),
            )


def test_feature_flag_and_production_policy_are_backend_enforced() -> None:
    with pytest.raises(PermissionError, match="AI_FEATURE_LOCKED"):
        authorize_tool(
            context(authority="CONFIRM_REQUIRED"),
            risk=ToolRisk.PREVIEW,
            required_roles=EDIT_ROLES,
            feature_flag="demand_gen_actions_enabled",
            gates=gates(),
        )
    with pytest.raises(PermissionError, match="AI_PRODUCTION_READ_LOCKED"):
        authorize_tool(
            context(environment="PRODUCTION"),
            risk=ToolRisk.READ,
            required_roles=ALL_ROLES,
            feature_flag=None,
            gates=gates(),
        )
    authorize_tool(
        context(environment="PRODUCTION"),
        risk=ToolRisk.READ,
        required_roles=ALL_ROLES,
        feature_flag=None,
        gates=gates(production_read_enabled=True),
    )


def test_viewer_cannot_select_draft_mode_and_production_requires_gates() -> None:
    with pytest.raises(HTTPException) as exc:
        enforce_mode_for_role("VIEWER", "DRAFT_ONLY", "SIMULATION", gates())
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException, match="AI_PRODUCTION_READ_LOCKED"):
        enforce_mode_for_role("ADMIN", "READ_ONLY", "PRODUCTION", gates())
    with pytest.raises(HTTPException, match="AI_PRODUCTION_ACTIONS_LOCKED"):
        enforce_mode_for_role("ADMIN", "DRAFT_ONLY", "PRODUCTION", gates(production_read_enabled=True))


def test_scope_escape_is_rejected() -> None:
    allowed = frozenset({uuid4()})
    assert require_allowed_ids([], allowed, "account") == list(allowed)
    with pytest.raises(PermissionError, match="AI_SCOPE_ESCAPE"):
        require_allowed_ids([uuid4()], allowed, "account")


def test_backend_metric_formulas_and_zero_denominators() -> None:
    result = with_derived_metrics(
        {
            "impressions": 1_000,
            "clicks": 100,
            "cost_micros": 50_000_000,
            "conversions": 10,
            "registrations": 5,
            "deposits": 2,
            "registration_data_available": True,
            "deposit_data_available": True,
            "conversion_value": 125,
        }
    )
    assert result["ctr"] == 10
    assert result["cpc_micros"] == 500_000
    assert result["cost_per_conversion_micros"] == 5_000_000
    assert result["cpa_registration_micros"] == 10_000_000
    assert result["cpa_deposit_micros"] == 25_000_000
    assert result["roas"] == 2.5

    zero = with_derived_metrics(
        {
            "impressions": 0,
            "clicks": 0,
            "cost_micros": 0,
            "conversions": 0,
            "registrations": 0,
            "deposits": 0,
            "registration_data_available": True,
            "deposit_data_available": True,
            "conversion_value": 0,
        }
    )
    assert zero["ctr"] is None
    assert zero["cpc_micros"] is None
    assert zero["cost_per_conversion_micros"] is None
    assert zero["cpa_registration_micros"] is None
    assert zero["roas"] is None


def test_final_work_status_contract_is_exact() -> None:
    assert [item.value for item in AccountWorkStatus] == [
        "PREPARATION",
        "READY",
        "WORKING",
        "MANUAL_PAUSE",
        "PROBLEM",
        "APPEAL",
        "ARCHIVED",
        "DO_NOT_USE",
    ]
