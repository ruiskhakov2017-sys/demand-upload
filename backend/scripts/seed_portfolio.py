import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.db.models import (
    AccountMetricDaily,
    AccountMonitoringState,
    AccountWorkStatus,
    ControlCenterCampaign,
    CustomerAccount,
    GoogleConnection,
    User,
    UserRole,
)
from app.domain.portfolio_access import PORTFOLIO_USERNAME
from scripts.portfolio_dataset import prepare_dataset

WORKSPACE = "Atlas Performance"
MANAGER_ID = "9900000100"
MARKETS = (
    ("North America", AccountWorkStatus.WORKING, 820, 21),
    ("DACH", AccountWorkStatus.WORKING, 610, 14),
    ("UK & Ireland", AccountWorkStatus.WORKING, 430, 11),
    ("Nordics", AccountWorkStatus.MANUAL_PAUSE, 310, 8),
    ("Benelux", AccountWorkStatus.PREPARATION, 0, 0),
)


def seed() -> None:
    if settings.app_env != "portfolio":
        raise SystemExit("Set APP_ENV=portfolio on the separate portfolio database")
    password = os.environ.get("PORTFOLIO_PASSWORD", "")
    if len(password) < 16:
        raise SystemExit("PORTFOLIO_PASSWORD must contain at least 16 characters")

    now = datetime.now(UTC)
    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).where(User.username == PORTFOLIO_USERNAME)) and db.scalar(
            select(GoogleConnection.id).where(GoogleConnection.name == WORKSPACE)
        ):
            prepare_dataset(db)
            print("Portfolio workspace already initialized")
            return
        if db.scalar(select(User.id).limit(1)) or db.scalar(select(GoogleConnection.id).limit(1)):
            raise SystemExit("Portfolio setup requires an empty Axyro database")

        user = User(
            username=PORTFOLIO_USERNAME,
            password_hash=hash_password(password),
            role=UserRole.OPERATOR.value,
            is_active=True,
            is_setup_admin=False,
        )
        db.add(user)
        db.flush()
        connection = GoogleConnection(
            name=WORKSPACE,
            login_customer_id=MANAGER_ID,
            auth_type="SERVICE_ACCOUNT",
            environment="TEST",
            connection_mode="SIMULATION",
            status="DRAFT",
            created_by_id=user.id,
        )
        db.add(connection)
        db.flush()

        for index, (market, status, spend, leads) in enumerate(MARKETS, start=1):
            customer_id = str(int(MANAGER_ID) + index)
            account = CustomerAccount(
                connection_id=connection.id,
                customer_id=customer_id,
                manager_customer_id=MANAGER_ID,
                descriptive_name=market,
                local_name=market,
                currency_code="USD",
                time_zone="UTC",
                status="ENABLED",
                work_status=status.value,
                link_status="ACTIVE",
                first_seen_at=now - timedelta(days=45),
                last_seen_at=now,
                last_sync_success_at=now,
            )
            db.add(account)
            db.flush()
            daily_metrics = []
            for day in range(30):
                daily_leads = max(0, leads + (day % 5 - 2) * 2) if leads else 0
                daily_cost = (spend + (day % 7 - 3) * 19) * 1_000_000 if spend else 0
                daily_metrics.append(AccountMetricDaily(
                    account_id=account.id,
                    metric_date=now.date() - timedelta(days=day),
                    impressions=daily_leads * 380,
                    clicks=daily_leads * 32,
                    conversions=daily_leads,
                    all_conversions=daily_leads,
                    cost_micros=daily_cost,
                    source="PORTFOLIO_DATASET",
                    observed_at=now,
                ))
            db.add_all(daily_metrics)
            db.add(AccountMonitoringState(
                account_id=account.id,
                period_start=now - timedelta(days=6),
                period_end=now,
                impressions=sum(row.impressions for row in daily_metrics[:7]),
                clicks=sum(row.clicks for row in daily_metrics[:7]),
                conversions=sum(row.conversions for row in daily_metrics[:7]),
                cost_micros=sum(row.cost_micros for row in daily_metrics[:7]),
                active_campaigns=int(status == AccountWorkStatus.WORKING),
                freshness="FRESH",
                data_observed_at=now,
                aggregated_at=now,
            ))
            campaign_id = str(99100 + index)
            db.add(ControlCenterCampaign(
                account_id=account.id,
                connection_id=connection.id,
                resource_name=f"customers/{customer_id}/campaigns/{campaign_id}",
                campaign_id=campaign_id,
                name=f"{market} · Prospecting",
                source="PORTFOLIO_DATASET",
                channel_type="DEMAND_GEN",
                status="ENABLED" if status == AccountWorkStatus.WORKING else "PAUSED",
                budget_micros=spend * 1_000_000,
                last_synced_at=now,
            ))
        db.flush()
        prepare_dataset(db)
    print("Portfolio workspace initialized")


if __name__ == "__main__":
    seed()
