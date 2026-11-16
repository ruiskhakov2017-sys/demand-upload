"""Database acceptance tests; run only against the dedicated local fixture DB."""

import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import func, select

from app.control_center.service import monitoring_state_map
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.db.models import AccountMetricDaily, AccountMonitoringState, CustomerAccount, MetricSnapshot
from app.main import app
from scripts.portfolio_dataset import prepare_dataset

pytestmark = pytest.mark.skipif(
    settings.app_env != "portfolio" or engine.url.database != "axyro_portfolio_reporting_test",
    reason="Requires the dedicated, seeded axyro_portfolio_reporting_test database",
)


@pytest.fixture
def client():
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={
            "username": "portfolio", "password": os.environ["PORTFOLIO_PASSWORD"],
        })
        assert response.status_code == 200
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield client


@pytest.mark.parametrize("timezone", ["ACCOUNT", "MOSCOW"])
@pytest.mark.parametrize("period", ["today", "yesterday", "3d", "7d", "30d", "custom"])
def test_summary_accounts_and_xlsx_share_reporting_window(client, period, timezone):
    params = {"period": period, "timezone_mode": timezone, "quick_filter": "all"}
    if period == "custom":
        today = datetime.now(UTC).date()
        params.update(start_date=str(today - timedelta(days=9)), end_date=str(today - timedelta(days=3)))
    accounts = client.get("/api/control-center/accounts", params=params)
    summary = client.get("/api/control-center/summary", params=params)
    assert accounts.status_code == summary.status_code == 200
    rows = accounts.json()["items"]
    totals = summary.json()["metrics"]
    expected = sum(int(row["metrics"]["cost_micros"]) for row in rows)
    assert totals["cost_micros"] == expected
    assert totals["clicks"] == sum(int(row["metrics"]["clicks"]) for row in rows)
    assert totals["conversions"] == sum(float(row["metrics"]["conversions"]) for row in rows)
    assert summary.json()["period"]["timezone_mode"] == timezone
    export = client.get("/api/control-center/accounts/export", params={
        **params, "format": "xlsx", "columns": "local_name,cost,registrations",
    })
    assert export.status_code == 200
    workbook = load_workbook(BytesIO(export.content), read_only=True)
    sheet_rows = list(workbook.active.values)
    # XLSX reports currency units; the API uses micro-units.
    exported = {row[0]: row[1] for row in sheet_rows[1:] if row[0] in {item["local_name"] for item in rows}}
    assert len(exported) == 5
    assert sum(Decimal(str(value)) * 1_000_000 for value in exported.values()) == expected


def test_empty_date_range_does_not_borrow_a_monitoring_snapshot(client):
    params = {"period": "custom", "start_date": "2020-01-01", "end_date": "2020-01-02", "quick_filter": "all"}
    rows = client.get("/api/control-center/accounts", params=params).json()["items"]
    summary = client.get("/api/control-center/summary", params=params).json()
    assert all(row["metrics"]["cost_micros"] is None for row in rows)
    assert summary["metrics"]["cost_micros"] is None
    assert summary["metrics"]["accounts_with_data"] == 0


def test_invalid_custom_range_is_rejected_by_both_endpoints(client):
    for endpoint in ("accounts", "summary"):
        response = client.get(f"/api/control-center/{endpoint}", params={
            "period": "custom", "start_date": "2026-11-02", "end_date": "2026-11-01",
        })
        assert response.status_code == 422


def test_mixed_currency_summary_keeps_currencies_separate(client):
    with SessionLocal.begin() as db:
        account = db.scalar(select(CustomerAccount).where(CustomerAccount.local_name == "DACH"))
        original = account.currency_code
        account.currency_code = "EUR"
    try:
        rows = client.get("/api/control-center/accounts", params={
            "period": "30d", "quick_filter": "all",
        }).json()["items"]
        summary = client.get("/api/control-center/summary", params={"period": "30d"}).json()["metrics"]
        expected = Counter()
        for row in rows:
            expected[row["currency_code"]] += int(row["metrics"]["cost_micros"])
        assert summary["mixed_currencies"] is True
        assert summary["cost_micros"] is None
        assert {row["currency_code"]: row["cost_micros"] for row in summary["by_currency"]} == expected
    finally:
        with SessionLocal.begin() as db:
            account = db.scalar(select(CustomerAccount).where(CustomerAccount.local_name == "DACH"))
            account.currency_code = original


def test_dataset_is_related_and_preparation_preserves_edits(client):
    accounts = client.get("/api/control-center/accounts", params={
        "period": "30d", "quick_filter": "all",
    }).json()["items"]
    assert all(row["geo"] and row["mcc_name"] for row in accounts)
    assert any(row["metrics"]["cpa_registration_micros"] for row in accounts)
    for endpoint in ("statistics", "moderation", "finance", "alerts"):
        response = client.get(f"/api/operations/{endpoint}")
        assert response.status_code == 200
        assert response.json()
    finance = client.get("/api/operations/finance").json()[0]
    assert finance["provider"] == "INTERNAL_BUDGET"
    assert finance["details"]["planned_budget"] == finance["details"]["spent"] + finance["latest_snapshot"]["balance"]
    account = accounts[0]
    url = f"/api/control-center/accounts/{account['id']}"
    original = {key: account[key] for key in ("current_note", "work_status")}
    changes = {"current_note": "Portfolio acceptance: retained visitor edit", "work_status": "MANUAL_PAUSE"}
    try:
        assert client.patch(url, json=changes).status_code == 200
        with SessionLocal.begin() as db:
            count = db.scalar(select(func.count()).select_from(MetricSnapshot))
            assert prepare_dataset(db) is False
            assert db.scalar(select(func.count()).select_from(MetricSnapshot)) == count
        stored = client.get(url).json()["account"]
        assert stored["current_note"] == changes["current_note"]
        assert stored["work_status"] == changes["work_status"]
    finally:
        assert client.patch(url, json=original).status_code == 200


def test_portfolio_fixture_never_runs_in_production(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    with SessionLocal.begin() as db, pytest.raises(RuntimeError, match="isolated portfolio"):
        prepare_dataset(db)


def test_daily_reporting_fixtures_have_both_matching_calendars():
    with SessionLocal() as db:
        for account in db.scalars(select(CustomerAccount)).all():
            rows = db.scalars(select(AccountMetricDaily).where(AccountMetricDaily.account_id == account.id)).all()
            assert {row.timezone_mode for row in rows} == {"ACCOUNT", "MOSCOW"}
            assert account.time_zone == "Europe/Moscow"


def test_cached_monitoring_data_is_used_only_for_its_exact_window_and_timezone():
    with SessionLocal() as db:
        original = db.scalar(select(CustomerAccount))
        account = CustomerAccount(connection_id=original.connection_id, customer_id="9900099999", currency_code="USD")
        db.add(account)
        db.flush()
        start = datetime(2035, 1, 1, tzinfo=UTC)
        end = start + timedelta(days=6)
        db.add(AccountMonitoringState(
            account_id=account.id, period_start=start, period_end=end, timezone_mode="ACCOUNT",
            cost_micros=12_000_000, clicks=8, freshness="FRESH",
        ))
        db.flush()
        matching = monitoring_state_map(db, [account.id], start.date(), end.date(), "ACCOUNT")[account.id]
        wrong_dates = monitoring_state_map(db, [account.id], start.date(), start.date(), "ACCOUNT")[account.id]
        wrong_timezone = monitoring_state_map(db, [account.id], start.date(), end.date(), "MOSCOW")[account.id]
        assert matching["cost_micros"] == 12_000_000
        assert wrong_dates["cost_micros"] is None
        assert wrong_timezone["cost_micros"] is None
        # The surrounding uncommitted session rolls the temporary account back.
