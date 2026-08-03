from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.routes.control_center import _action_pre_state, _problem_display_description
from app.control_center.query import (
    apply_account_filters,
    group_account_rows,
    sort_account_rows,
    sort_groups,
)
from app.control_center.rule_engine import (
    _plan_actions,
    _rule_schedule_due,
    _scope_matches,
)
from app.control_center.rules import RuleExecutionBlocked, require_rules_enabled
from app.control_center.schemas import (
    ActionPreviewIn,
    RuleCreateIn,
    RuleLiveModeIn,
)
from app.control_center.service import (
    account_payload,
    campaign_payload,
    currency_totals,
    matches_rule_condition,
    period_bounds,
    with_derived_metrics,
)
from app.db.models import AccountMonitoringState, AccountWorkStatus
from app.google_ads.hierarchy import _deduplicate_accounts
from app.google_ads.interface import CustomerAccountInfo, GoogleAdsConnectionConfig
from app.google_ads.service import ADAPTER_REGISTRY
from app.google_ads.versions.v24_2 import GoogleAdsV242Adapter
from app.google_ads.versions.v25 import GoogleAdsV25Adapter
from app.jobs.control_center_tasks import (
    _fail_sync_item,
    _google_read_error,
    _incremental_metric_start,
    _register_connection_sync_failure,
    _retry_delay_seconds,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _account(**overrides):
    values = {
        "id": uuid4(),
        "connection_id": uuid4(),
        "customer_id": "1234567890",
        "manager_customer_id": "5589335362",
        "parent_customer_id": "5589335362",
        "hierarchy_level": 1,
        "descriptive_name": "Google name",
        "local_name": "Local name",
        "currency_code": "USD",
        "time_zone": "Europe/Moscow",
        "status": "SUSPENDED",
        "work_status": "WORKING",
        "current_note": "Keep budget",
        "note_updated_at": None,
        "note_updated_by_id": None,
        "is_pinned": False,
        "is_test_account": False,
        "is_hidden": False,
        "detached_at": None,
        "last_sync_attempt_at": None,
        "last_sync_success_at": None,
        "sync_error": None,
        "verification_status": None,
        "verification_deadline": None,
        "verification_action_url": None,
        "verification_checked_at": None,
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_work_status_is_independent_from_google_status() -> None:
    account = _account(status="SUSPENDED", work_status="WORKING")
    payload = account_payload(account, "vcc2", [], {}, 0)

    assert payload["work_status"] == "WORKING"
    assert payload["google_status"] == "SUSPENDED"
    assert payload["has_problem"] is True


def test_account_work_status_contract_is_complete() -> None:
    assert {item.value for item in AccountWorkStatus} == {
        "UNCLASSIFIED",
        "PREPARATION",
        "WORKING",
        "PAUSED",
        "ARCHIVED",
    }


def test_missing_metrics_are_not_converted_to_zero() -> None:
    missing = with_derived_metrics(
        {
            "impressions": None,
            "clicks": None,
            "cost_micros": None,
            "conversions": None,
        }
    )
    actual_zero = with_derived_metrics(
        {
            "impressions": 0,
            "clicks": 0,
            "cost_micros": 0,
            "conversions": 0.0,
        }
    )

    assert missing["cost_micros"] is None
    assert actual_zero["cost_micros"] == 0
    assert missing["ctr"] is None
    assert actual_zero["ctr"] is None


@pytest.mark.parametrize("currency", ["USD", "INR", "ZAR", "KES"])
def test_single_currency_summary_keeps_native_currency(currency: str) -> None:
    account_id = uuid4()
    result = currency_totals(
        [SimpleNamespace(id=account_id, currency_code=currency)],
        [SimpleNamespace(account_id=account_id, cost_micros=12_345_678)],
    )

    assert result["currency_code"] == currency
    assert result["cost_micros"] == 12_345_678
    assert result["mixed_currencies"] is False
    assert result["by_currency"] == [
        {
            "currency_code": currency,
            "cost_micros": 12_345_678,
            "accounts_with_data": 1,
        }
    ]


def test_mixed_currency_summary_never_returns_combined_money() -> None:
    accounts = [
        SimpleNamespace(id=uuid4(), currency_code=currency)
        for currency in ("USD", "INR", "ZAR", "KES")
    ]
    states = [
        SimpleNamespace(account_id=account.id, cost_micros=(index + 1) * 1_000_000)
        for index, account in enumerate(accounts)
    ]

    result = currency_totals(accounts, states)

    assert result["cost_micros"] is None
    assert result["currency_code"] is None
    assert result["mixed_currencies"] is True
    assert {
        item["currency_code"]: item["cost_micros"]
        for item in result["by_currency"]
    } == {
        "USD": 1_000_000,
        "INR": 2_000_000,
        "ZAR": 3_000_000,
        "KES": 4_000_000,
    }


def _query_row(
    name: str,
    *,
    geo: str = "IN",
    mcc: str = "IN-01",
    work_status: str = "WORKING",
    activity_status: str = "SPENDING",
    cost_micros: int | None = 10_000_000,
    registrations: float | None = 2,
    deposits: float | None = 1,
    currency: str = "INR",
    problems: bool = False,
) -> dict:
    return {
        "id": name,
        "display_name": name,
        "customer_id": name,
        "geo": {"id": geo, "display_name": geo},
        "primary_mcc_id": mcc,
        "mcc_name": mcc,
        "work_status": work_status,
        "activity_status": activity_status,
        "google_status": "ENABLED",
        "currency_code": currency,
        "has_problem": problems,
        "problem_types": ["POLICY"] if problems else [],
        "active_problem_count": int(problems),
        "metrics": with_derived_metrics(
            {
                "impressions": 1_000,
                "clicks": 100,
                "cost_micros": cost_micros,
                "conversions": registrations,
                "all_conversions": registrations,
                "registrations": registrations,
                "deposits": deposits,
                "registration_data_available": registrations is not None,
                "deposit_data_available": deposits is not None,
                "conversion_value": 30.0,
                "active_campaigns": 1,
                "disapproved_ads": int(problems),
            }
        ),
    }


def test_one_geo_groups_three_mcc_without_losing_accounts() -> None:
    rows = [
        _query_row("in-a", mcc="IN-01"),
        _query_row("in-b", mcc="IN-02"),
        _query_row("in-c", mcc="IN-03"),
    ]

    geo_groups = group_account_rows(rows, "geo")
    mcc_groups = group_account_rows(rows, "mcc")

    assert len(geo_groups) == 1
    assert geo_groups[0]["accounts"] == 3
    assert {group["label"] for group in mcc_groups} == {"IN-01", "IN-02", "IN-03"}


def test_working_activity_filters_do_not_change_manual_status() -> None:
    rows = [
        _query_row("working-spending"),
        _query_row(
            "working-no-spend",
            activity_status="ENABLED_NO_SPEND",
            cost_micros=0,
        ),
        _query_row(
            "not-working-spending",
            work_status="PAUSED",
            activity_status="SPENDING",
        ),
        _query_row(
            "working-suspended",
            activity_status="SUSPENDED",
            problems=True,
        ),
    ]

    no_spend = apply_account_filters(
        [row for row in rows if row["work_status"] == "WORKING"],
        {"activity_status": "ENABLED_NO_SPEND"},
    )
    unexpected_spend = apply_account_filters(
        [row for row in rows if row["work_status"] != "WORKING"],
        {"activity_status": "SPENDING"},
    )
    suspended = apply_account_filters(
        [row for row in rows if row["work_status"] == "WORKING"],
        {"activity_status": "SUSPENDED"},
    )

    assert [row["id"] for row in no_spend] == ["working-no-spend"]
    assert [row["id"] for row in unexpected_spend] == ["not-working-spending"]
    assert [row["id"] for row in suspended] == ["working-suspended"]
    assert suspended[0]["work_status"] == "WORKING"


def test_numeric_filters_and_multi_sort_keep_nulls_last() -> None:
    rows = [
        _query_row("bravo", cost_micros=30_000_000, registrations=5, deposits=0),
        _query_row("alpha", cost_micros=30_000_000, registrations=3, deposits=0),
        _query_row("charlie", cost_micros=5_000_000, registrations=1, deposits=1),
        _query_row("missing", cost_micros=None, registrations=None, deposits=None),
    ]

    filtered = apply_account_filters(
        rows,
        {
            "cost_min": 10_000_000,
            "deposits_eq": 0,
        },
    )
    by_cost = sort_account_rows(rows, ["cost"], ["desc"])
    by_deposits = sort_account_rows(rows, ["deposits"], ["asc"])
    multi = sort_account_rows(rows, ["cost", "registrations", "name"], ["desc", "asc", "asc"])

    assert [row["id"] for row in filtered] == ["bravo", "alpha"]
    assert [row["id"] for row in by_cost] == ["bravo", "alpha", "charlie", "missing"]
    assert [row["id"] for row in by_deposits] == ["bravo", "alpha", "charlie", "missing"]
    assert [row["id"] for row in multi] == ["alpha", "bravo", "charlie", "missing"]


def test_group_money_is_separated_by_currency_and_groups_can_be_sorted() -> None:
    group = group_account_rows(
        [
            _query_row("india", currency="INR", cost_micros=20_000_000),
            _query_row("kenya", geo="KE", mcc="KE-01", currency="KES", cost_micros=10_000_000),
        ],
        "geo",
    )

    sorted_groups = sort_groups(group, ["cost"], ["desc"])

    assert len(sorted_groups) == 2
    assert all(item["mixed_currencies"] is False for item in sorted_groups)
    assert {
        item["currency_totals"][0]["currency_code"] for item in sorted_groups
    } == {"INR", "KES"}


def test_conversion_zero_and_missing_data_are_distinct() -> None:
    zero = _query_row("zero", registrations=4, deposits=0)
    missing = _query_row("missing", registrations=4, deposits=None)

    assert zero["metrics"]["deposits"] == 0
    assert zero["metrics"]["deposit_data_available"] is True
    assert missing["metrics"]["deposits"] is None
    assert missing["metrics"]["deposit_data_available"] is False
    assert apply_account_filters([zero, missing], {"deposits_eq": 0}) == [zero]


def test_google_test_campaign_metrics_are_not_presented_as_real_zeroes() -> None:
    campaign = SimpleNamespace(
        id=uuid4(),
        account_id=uuid4(),
        connection_id=uuid4(),
        resource_name="customers/1833869760/campaigns/24078084651",
        campaign_id="24078084651",
        name="API_TEST_ACCEPTANCE",
        source="GOOGLE_ADS_MANUAL",
        channel_type="DEMAND_GEN",
        channel_subtype=None,
        status="PAUSED",
        primary_status=None,
        primary_status_reasons=[],
        budget_resource_name="customers/1833869760/campaignBudgets/1",
        budget_micros=10_000_000,
        budget_shared=False,
        impressions=0,
        clicks=0,
        cost_micros=0,
        conversions=0.0,
        conversion_value=0.0,
        policy_issues=[],
        manually_paused=False,
        last_synced_at=datetime.now(UTC),
        sync_error=None,
    )

    payload = campaign_payload(
        campaign,
        _account(
            id=campaign.account_id,
            customer_id="1833869760",
            is_test_account=True,
        ),
    )

    assert payload["metrics"]["cost_micros"] is None
    assert payload["metrics"]["clicks"] is None
    assert payload["metrics"]["data_source_mode"] == "GOOGLE_TEST"
    assert (
        payload["metrics"]["no_data_reason"]
        == "Нет данных: тестовые аккаунты не показывают рекламу"
    )


def test_sync_failure_keeps_last_known_metrics() -> None:
    state = AccountMonitoringState(
        account_id=uuid4(),
        impressions=321,
        clicks=12,
        cost_micros=45_000_000,
        conversions=2.0,
        freshness="FRESH",
    )
    account = _account(id=state.account_id)
    item = SimpleNamespace(
        status="RUNNING",
        operations=0,
        completed_at=None,
        error_code=None,
        error_message=None,
    )
    sync_run = SimpleNamespace(requested_by_id=None)

    class FakeDb:
        def __init__(self):
            self.scalar_results = [state, None]
            self.added = []

        def scalar(self, statement):
            return self.scalar_results.pop(0)

        def add(self, value):
            self.added.append(value)

    ok, operations = _fail_sync_item(
        FakeDb(),
        sync_run,
        item,
        account,
        "DEADLINE_EXCEEDED",
        "temporary failure",
        4,
    )

    assert ok is False
    assert operations == 4
    assert state.impressions == 321
    assert state.cost_micros == 45_000_000
    assert state.freshness == "ERROR"
    assert account.sync_error == "temporary failure"


def test_period_bounds_and_custom_validation() -> None:
    start, end = period_bounds("custom", date(2026, 7, 1), date(2026, 7, 7))
    assert start == date(2026, 7, 1)
    assert end == date(2026, 7, 7)
    with pytest.raises(ValueError):
        period_bounds("custom", date(2026, 7, 8), date(2026, 7, 7))


def test_incremental_sync_uses_overlap_instead_of_refetching_thirty_days() -> None:
    history_start = date(2026, 7, 1)
    assert _incremental_metric_start(history_start, None) == history_start
    assert _incremental_metric_start(
        history_start,
        datetime(2026, 7, 29, 18, tzinfo=UTC),
    ) == date(2026, 7, 27)


def test_hierarchy_deduplicates_customer_and_keeps_every_manager_path() -> None:
    common = {
        "customer_id": "1112223333",
        "descriptive_name": "Client",
        "currency_code": "INR",
        "time_zone": "Asia/Kolkata",
        "can_manage_clients": False,
        "is_test_account": False,
        "is_hidden": False,
        "status": "ENABLED",
    }
    rows = (
        CustomerAccountInfo(
            **common,
            manager_customer_id="1000000001",
            parent_customer_id="1000000001",
            access_paths=(("9999999999", "1000000001", "1112223333"),),
            request_ids=("request-one",),
        ),
        CustomerAccountInfo(
            **common,
            manager_customer_id="1000000002",
            parent_customer_id="1000000002",
            access_paths=(("9999999999", "1000000002", "1112223333"),),
            request_ids=("request-two",),
        ),
    )
    deduplicated = _deduplicate_accounts(rows)
    assert len(deduplicated) == 1
    assert deduplicated[0].customer_id == "1112223333"
    assert set(deduplicated[0].access_paths) == {
        ("9999999999", "1000000001", "1112223333"),
        ("9999999999", "1000000002", "1112223333"),
    }
    assert deduplicated[0].request_ids == ("request-one", "request-two")


def test_sync_retry_backoff_and_connection_circuit_are_bounded() -> None:
    account_id = uuid4()
    delays = [_retry_delay_seconds(attempt, account_id) for attempt in (1, 2, 3)]
    assert delays[0] < delays[1] < delays[2] <= 4
    connection = SimpleNamespace(
        sync_failure_count=0,
        sync_circuit_open_until=None,
    )
    _register_connection_sync_failure(connection)
    _register_connection_sync_failure(connection)
    assert connection.sync_circuit_open_until is None
    _register_connection_sync_failure(connection)
    assert connection.sync_failure_count == 3
    assert connection.sync_circuit_open_until is not None


def test_rule_conditions_are_local_and_deterministic() -> None:
    payload = {"campaign": {"metrics": {"cost_micros": 100_000_000}, "status": "ENABLED"}}
    assert matches_rule_condition(
        payload, {"field": "campaign.metrics.cost_micros", "operator": "gte", "value": 90_000_000}
    )
    assert not matches_rule_condition(
        payload, {"field": "campaign.status", "operator": "eq", "value": "PAUSED"}
    )


def test_rules_reject_live_mode() -> None:
    with pytest.raises(ValueError):
        RuleCreateIn(name="Unsafe", mode="LIVE")


def test_live_mode_requires_the_exact_explicit_confirmation() -> None:
    assert (
        RuleLiveModeIn(confirmation="ENABLE LIVE RULES").confirmation
        == "ENABLE LIVE RULES"
    )
    with pytest.raises(ValueError):
        RuleLiveModeIn(confirmation="yes")


def test_rule_budget_limit_and_manual_pause_guard_are_enforced() -> None:
    budget_rule = SimpleNamespace(
        actions=[{"type": "SET_BUDGET", "amount_micros": 130_000_000}],
        safeguards={},
        max_budget_change_percent=20,
        id=uuid4(),
    )
    campaign = SimpleNamespace(
        budget_micros=100_000_000,
        manually_paused=False,
    )
    actions, reason = _plan_actions(budget_rule, campaign)
    assert actions == []
    assert reason == "INVALID_BUDGET_ACTION"

    enable_rule = SimpleNamespace(
        actions=[{"type": "ENABLE"}],
        safeguards={"block_manual_paused_enable": True},
        max_budget_change_percent=20,
        id=uuid4(),
    )
    campaign.manually_paused = True
    actions, reason = _plan_actions(enable_rule, campaign)
    assert actions == []
    assert reason == "MANUAL_PAUSE_GUARD"


def test_rule_scope_combines_geo_mcc_account_status_and_tags() -> None:
    account = _account(
        geo_id=uuid4(),
        geo_override_id=None,
        primary_mcc_id=uuid4(),
        work_status="WORKING",
    )
    scope = {
        "account_ids": [str(account.id)],
        "geo_ids": [str(account.geo_id)],
        "mcc_ids": [str(account.primary_mcc_id)],
        "work_statuses": ["WORKING"],
        "tags": ["priority"],
    }
    assert _scope_matches(
        scope,
        account,
        [{"id": str(uuid4()), "name": "Priority"}],
        None,
    )
    assert not _scope_matches(
        {**scope, "geo_ids": [str(uuid4())]},
        account,
        [{"id": str(uuid4()), "name": "Priority"}],
        None,
    )


def test_rule_schedule_prevents_duplicate_interval_runs() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    rule = SimpleNamespace(
        schedule={"interval_minutes": 15},
        last_evaluated_at=now - timedelta(minutes=14),
    )
    assert _rule_schedule_due(rule, now) is False
    rule.last_evaluated_at = now - timedelta(minutes=15)
    assert _rule_schedule_due(rule, now) is True


def test_kill_switch_is_rechecked_between_evaluation_and_mutate() -> None:
    class FakeDb:
        def __init__(self) -> None:
            self.states = iter(
                [
                    SimpleNamespace(value={"active": False}),
                    SimpleNamespace(value={"active": False}),
                    SimpleNamespace(value={"active": True}),
                ]
            )

        def scalar(self, _statement):
            return next(self.states)

    db = FakeDb()
    require_rules_enabled(db, "BEFORE_EVALUATION")
    require_rules_enabled(db, "BEFORE_ACTION_CREATION")
    with pytest.raises(RuleExecutionBlocked) as exc:
        require_rules_enabled(db, "BEFORE_MUTATE")
    assert exc.value.phase == "BEFORE_MUTATE"


def test_budget_preview_requires_absolute_amount() -> None:
    with pytest.raises(ValueError):
        ActionPreviewIn(
            campaign_ids=[uuid4()],
            action_type="SET_BUDGET",
            execution_mode="SIMULATION",
        )


def test_google_campaign_id_does_not_replace_local_preview_id() -> None:
    local_id = uuid4()

    state = _action_pre_state(
        local_id,
        {
            "campaign_id": "24078086559",
            "resource_name": "customers/8047280949/campaigns/24078086559",
            "status": "PAUSED",
        },
    )

    assert state["campaign_id"] == str(local_id)
    assert state["google_campaign_id"] == "24078086559"


def test_adapter_registry_keeps_v242_and_adds_separate_v25_layer() -> None:
    assert ADAPTER_REGISTRY["v24.2"] is GoogleAdsV242Adapter
    assert ADAPTER_REGISTRY["v25"] is GoogleAdsV25Adapter
    config = GoogleAdsConnectionConfig(
        connection_id="test",
        name="v25-test",
        login_customer_id="5589335362",
        api_version="v25",
        auth_type="OAUTH_WEB",
        environment="TEST",
        developer_token="secret",
        auth_payload={"client_id": "x", "client_secret": "y", "refresh_token": "z"},
    )
    assert isinstance(GoogleAdsV25Adapter(config), GoogleAdsV242Adapter)


def test_control_center_migration_upgrade_is_additive_only() -> None:
    migration = (
        BACKEND_ROOT
        / "migrations"
        / "versions"
        / "fabc2ba828ea_add_google_ads_control_center.py"
    ).read_text(encoding="utf-8")
    upgrade = migration.split("def downgrade", 1)[0]
    assert "op.drop_" not in upgrade
    assert "op.alter_column" not in upgrade
    assert "DELETE FROM" not in upgrade.upper()
    assert "TRUNCATE" not in upgrade.upper()


def test_google_read_error_uses_structured_message_without_grpc_dump() -> None:
    error = SimpleNamespace(
        error_code="query_error: INVALID_DATE_FORMAT",
        message="Dates in conditions should be in 'YYYY-MM-DD' format.",
    )
    exc = Exception("(<_InactiveRpcError debug_error_string=technical dump>)")
    exc.failure = SimpleNamespace(errors=[error])
    exc.request_id = "request-123"

    result = _google_read_error(exc)

    assert result == {
        "code": "query_error: INVALID_DATE_FORMAT",
        "message": "Dates in conditions should be in 'YYYY-MM-DD' format.",
        "request_id": "request-123",
    }


def test_resolved_problem_hides_grpc_dump_but_keeps_human_explanation() -> None:
    problem = SimpleNamespace(
        google_message=None,
        description="(<_InactiveRpcError debug_error_string=technical dump>)",
        google_code="query_error: UNRECOGNIZED_FIELD",
        state="RESOLVED",
    )

    description = _problem_display_description(problem)

    assert "неизвестное поле" in description
    assert "проблема закрыта" in description
    assert "InactiveRpcError" not in description
