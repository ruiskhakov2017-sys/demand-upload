from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes.schedules import schedule_action
from app.api.workflow_schemas import ScheduleActionIn
from app.domain.scheduling import (
    TRANSIENT_ERROR_CODES,
    build_schedule_preview,
    circuit_breaker_decision,
    is_run_due,
    is_transient_error,
    rate_limit_conflicts,
    retry_delay_seconds,
    schedule_fingerprint,
    should_pause_after_downtime,
)
from app.google_ads.mock_adapter import MockGoogleAdsAdapter

NOW = datetime(2026, 7, 25, 0, 0, tzinfo=UTC)


class _EmptyScalarResult:
    def all(self) -> list[Any]:
        return []


class _EmptyScheduleDb:
    def __init__(self, schedule: SimpleNamespace) -> None:
        self.schedule = schedule

    def get(self, _model: Any, _identifier: Any) -> SimpleNamespace:
        return self.schedule

    def scalars(self, _statement: Any) -> _EmptyScalarResult:
        return _EmptyScalarResult()


def _accounts(count: int, campaigns: int = 3) -> list[dict]:
    return [
        {
            "id": str(uuid4()),
            "customer_id": str(800_000_0000 + index),
            "account_name": f"Account {index + 1}",
            "campaigns_count": campaigns,
            "budget_micros": campaigns * 10_000_000,
        }
        for index in range(count)
    ]


def test_cancel_future_refuses_to_change_completed_schedule_without_future_runs() -> None:
    schedule_id = uuid4()
    schedule = SimpleNamespace(id=schedule_id, status="COMPLETED")
    with pytest.raises(HTTPException) as exc:
        schedule_action(
            schedule_id,
            ScheduleActionIn(action="CANCEL_FUTURE", confirmation=True),
            request=SimpleNamespace(),
            db=_EmptyScheduleDb(schedule),
            user=SimpleNamespace(),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail == "Будущих запусков нет"
    assert schedule.status == "COMPLETED"


def test_fifty_accounts_are_distributed_across_twenty_four_hours() -> None:
    preview = build_schedule_preview(
        _accounts(50),
        {
            "mode": "EVEN",
            "time_zone": "UTC",
            "start_local": "2026-07-25T00:00",
            "end_local": "2026-07-26T00:00",
            "max_accounts_per_hour": 50,
            "max_accounts_per_day": 500,
        },
        now=NOW,
    )
    times = [datetime.fromisoformat(item["scheduled_for"]) for item in preview["runs"]]
    assert len(times) == 50
    assert times[0] == NOW
    assert times[-1] == NOW + timedelta(hours=23, minutes=31, seconds=12)
    assert all(left < right for left, right in zip(times, times[1:], strict=False))


def test_first_wave_contains_only_five_accounts() -> None:
    preview = build_schedule_preview(
        _accounts(25),
        {
            "mode": "WAVES",
            "time_zone": "UTC",
            "start_local": "2026-07-25T00:00",
            "first_wave_size": 5,
            "next_wave_size": 10,
        },
        now=NOW,
    )
    assert sum(item["wave_number"] == 1 for item in preview["runs"]) == 5
    assert [item["accounts"] for item in preview["waves"]] == [5, 10, 10]


def test_observation_period_follows_first_wave_window() -> None:
    preview = build_schedule_preview(
        _accounts(15),
        {
            "mode": "WAVES",
            "time_zone": "UTC",
            "start_local": "2026-07-25T00:00",
            "first_wave_size": 5,
            "first_wave_spread_minutes": 240,
            "observation_minutes": 720,
        },
        now=NOW,
    )
    assert datetime.fromisoformat(preview["waves"][0]["observation_until"]) == NOW + timedelta(hours=16)


def test_next_wave_requires_explicit_approval_by_default() -> None:
    preview = build_schedule_preview(
        _accounts(15),
        {
            "mode": "WAVES",
            "time_zone": "UTC",
            "start_local": "2026-07-25T00:00",
            "first_wave_size": 5,
            "next_wave_size": 10,
        },
        now=NOW,
    )
    assert preview["waves"][0]["approval_required"] is False
    assert preview["waves"][1]["approval_required"] is True


def test_automatic_wave_continuation_can_be_enabled() -> None:
    preview = build_schedule_preview(
        _accounts(15),
        {
            "mode": "WAVES",
            "time_zone": "UTC",
            "start_local": "2026-07-25T00:00",
            "manual_approval": False,
        },
        now=NOW,
    )
    assert all(item["approval_required"] is False for item in preview["waves"])


def test_run_is_not_due_before_planned_time() -> None:
    assert not is_run_due(
        status="WAITING",
        scheduled_for=NOW + timedelta(minutes=1),
        next_retry_at=None,
        now=NOW,
    )
    assert is_run_due(
        status="WAITING",
        scheduled_for=NOW,
        next_retry_at=None,
        now=NOW,
    )


def test_one_account_is_one_indivisible_launch_group_run() -> None:
    preview = build_schedule_preview(
        _accounts(3, campaigns=7),
        {"mode": "IMMEDIATE", "time_zone": "UTC"},
        now=NOW,
    )
    assert len(preview["runs"]) == 3
    assert [item["campaigns_count"] for item in preview["runs"]] == [7, 7, 7]
    assert preview["summary"]["campaigns"] == 21


def test_mock_creates_entire_group_in_paused_without_google() -> None:
    campaigns = [
        {
            "campaign_instance_id": str(uuid4()),
            "customer_id": "1234567890",
            "campaign_name": f"Copy {index}",
        }
        for index in range(1, 8)
    ]
    result = MockGoogleAdsAdapter().deploy_plan({"upload_id": "test", "campaigns": campaigns})
    assert result.ok is True
    assert result.details["campaign_status"] == "PAUSED"
    assert result.details["google_contacted"] is False
    assert len(result.details["instances"]) == 7


def test_hourly_and_daily_limits_are_applied_to_immediate_mode() -> None:
    preview = build_schedule_preview(
        _accounts(25),
        {
            "mode": "IMMEDIATE",
            "time_zone": "UTC",
            "max_accounts_per_hour": 2,
            "max_accounts_per_day": 20,
        },
        now=NOW,
    )
    times = [datetime.fromisoformat(item["scheduled_for"]) for item in preview["runs"]]
    assert rate_limit_conflicts(times, 2, 20) == []
    assert times[2] > NOW + timedelta(hours=1)
    assert times[20] > NOW + timedelta(days=1)


def test_default_parallelism_is_one_account() -> None:
    preview = build_schedule_preview(_accounts(3), {"mode": "IMMEDIATE"}, now=NOW)
    assert preview["summary"]["max_parallel"] == 1


def test_two_serious_errors_open_circuit_breaker() -> None:
    count, pause = circuit_breaker_decision(
        consecutive_serious_errors=0,
        threshold=2,
        errors=[{"code": "POLICY_ERROR"}],
    )
    assert (count, pause) == (1, False)
    count, pause = circuit_breaker_decision(
        consecutive_serious_errors=count,
        threshold=2,
        errors=[{"code": "INVALID_ARGUMENT"}],
    )
    assert (count, pause) == (2, True)


def test_authorization_error_opens_circuit_immediately() -> None:
    count, pause = circuit_breaker_decision(
        consecutive_serious_errors=0,
        threshold=10,
        errors=[{"code": "UNAUTHENTICATED"}],
    )
    assert count == 1
    assert pause is True


def test_only_transient_codes_are_automatically_retried() -> None:
    for code in TRANSIENT_ERROR_CODES:
        assert is_transient_error([{"code": code}])
    assert not is_transient_error([{"code": "PERMISSION_DENIED"}])
    assert not is_transient_error([{"code": "POLICY_ERROR"}])


def test_retry_backoff_is_exponential_with_small_stable_jitter() -> None:
    delays = [retry_delay_seconds("stable-key", attempt) for attempt in (1, 2, 3)]
    assert 60 <= delays[0] <= 75
    assert 120 <= delays[1] <= 135
    assert 240 <= delays[2] <= 255
    assert delays == [retry_delay_seconds("stable-key", attempt) for attempt in (1, 2, 3)]


def test_restart_does_not_change_schedule_fingerprint_or_mock_resources() -> None:
    accounts = _accounts(5)
    first = build_schedule_preview(accounts, {"mode": "IMMEDIATE"}, now=NOW)
    second = build_schedule_preview(accounts, {"mode": "IMMEDIATE"}, now=NOW)
    assert first["fingerprint"] == second["fingerprint"]
    snapshot = {"upload_id": "stable", "campaigns": first["runs"]}
    adapter = MockGoogleAdsAdapter()
    assert adapter.deploy_plan(snapshot).resource_names == adapter.deploy_plan(snapshot).resource_names


def test_downtime_with_many_overdue_accounts_requires_recovery() -> None:
    assert should_pause_after_downtime(
        now=NOW,
        last_dispatch_at=NOW - timedelta(minutes=10),
        overdue_count=10,
        max_parallel=1,
    )
    assert not should_pause_after_downtime(
        now=NOW,
        last_dispatch_at=NOW - timedelta(seconds=15),
        overdue_count=10,
        max_parallel=1,
    )


def test_manual_schedule_reports_unassigned_accounts() -> None:
    accounts = _accounts(2)
    preview = build_schedule_preview(
        accounts,
        {
            "mode": "MANUAL",
            "time_zone": "UTC",
            "manual_runs": [
                {
                    "account_test_bundle_id": accounts[0]["id"],
                    "scheduled_local": "2026-07-25T10:00",
                }
            ],
        },
        now=NOW,
    )
    assert preview["valid"] is False
    assert len(preview["unassigned_accounts"]) == 1


def test_manual_schedule_preserves_exact_time_and_wave() -> None:
    account = _accounts(1)[0]
    preview = build_schedule_preview(
        [account],
        {
            "mode": "MANUAL",
            "time_zone": "Europe/Moscow",
            "manual_runs": [
                {
                    "account_test_bundle_id": account["id"],
                    "scheduled_local": "2026-07-25T10:30",
                    "wave_number": 3,
                }
            ],
        },
        now=NOW,
    )
    assert preview["runs"][0]["scheduled_for"] == "2026-07-25T07:30:00+00:00"
    assert preview["runs"][0]["wave_number"] == 3


def test_schedule_fingerprint_changes_when_time_changes() -> None:
    first = build_schedule_preview(_accounts(2), {"mode": "IMMEDIATE"}, now=NOW)
    changed = {**first, "runs": [dict(item) for item in first["runs"]]}
    changed["runs"][0]["scheduled_for"] = (NOW + timedelta(minutes=1)).isoformat()
    assert schedule_fingerprint(first) != schedule_fingerprint(changed)
