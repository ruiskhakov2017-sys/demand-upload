"""Prepare related portfolio records once, preserving subsequent visitor edits."""

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.db.models import (
    AccountMetricDaily,
    ApplicationSetting,
    ControlCenterAd,
    ControlCenterAdGroup,
    ControlCenterCampaign,
    ControlCenterEvent,
    ControlCenterProblem,
    ControlCenterRule,
    CustomerAccount,
    FinanceProfile,
    FinanceSnapshot,
    GeoDefinition,
    GoogleAccountAccessPath,
    GoogleConnection,
    MccAccount,
    MetricSnapshot,
    ModerationRecord,
    Notification,
    User,
)
from app.domain.portfolio_access import PORTFOLIO_USERNAME

DATASET_KEY = "portfolio.related_dataset.v1"
MARKETS = (
    ("North America", "US", "Северная Америка", "NA"),
    ("DACH", "DE", "Германия, Австрия, Швейцария", "DACH"),
    ("UK & Ireland", "GB", "Великобритания и Ирландия", "UK & IE"),
    ("Nordics", "SE", "Северная Европа", "Nordics"),
    ("Benelux", "BE", "Бельгия, Нидерланды, Люксембург", "Benelux"),
)


def prepare_dataset(db: Session) -> bool:
    if settings.app_env != "portfolio":
        raise RuntimeError("Related data can only be prepared in the isolated portfolio environment")
    if db.scalar(select(ApplicationSetting).where(ApplicationSetting.key == DATASET_KEY)):
        return False
    user = db.scalar(select(User).where(User.username == PORTFOLIO_USERNAME))
    connection = db.scalar(select(GoogleConnection).where(GoogleConnection.name == "Atlas Performance"))
    if not user or not connection or connection.connection_mode != "SIMULATION":
        raise RuntimeError("Initialize the isolated Atlas portfolio workspace first")
    now = datetime.now(UTC)
    root = MccAccount(
        connection_id=connection.id, customer_id=connection.login_customer_id,
        descriptive_name="Atlas Performance", is_root=True, hierarchy_level=0,
        status="ENABLED", first_seen_at=now - timedelta(days=45), last_seen_at=now,
    )
    db.add(root)
    db.flush()
    spent_micros = 0
    for index, (market, iso, display_name, short_label) in enumerate(MARKETS, start=1):
        account = db.scalar(select(CustomerAccount).where(
            CustomerAccount.connection_id == connection.id, CustomerAccount.customer_id == str(9900000100 + index),
        ))
        if not account:
            raise RuntimeError(f"Portfolio account missing: {market}")
        geo = db.scalar(select(GeoDefinition).where(GeoDefinition.iso_code == iso))
        if not geo:
            geo = GeoDefinition(iso_code=iso, display_name=display_name, short_label=short_label,
                                default_currency_code="USD", color="#244bb9")
            db.add(geo)
            db.flush()
        manager_id = str(9900000200 + index)
        manager = MccAccount(
            connection_id=connection.id, customer_id=manager_id,
            parent_customer_id=connection.login_customer_id, descriptive_name=f"Atlas · {short_label}",
            is_root=False, hierarchy_level=1, status="ENABLED", geo_id=geo.id,
            first_seen_at=now - timedelta(days=45), last_seen_at=now, last_sync_success_at=now,
        )
        db.add(manager)
        db.flush()
        account.primary_mcc_id = manager.id
        account.manager_customer_id = manager_id
        account.parent_customer_id = manager_id
        account.geo_id = geo.id
        account.hierarchy_root_customer_id = connection.login_customer_id
        account.hierarchy_level = 2
        # These fictional accounts belong to one Moscow-based media team.
        # Their account and Moscow reporting calendars therefore coincide.
        account.time_zone = "Europe/Moscow"
        account.verification_status = "REQUIRED" if market == "Benelux" else "SUCCESS"
        if market == "Benelux":
            account.verification_deadline = now + timedelta(days=14)
        path = [connection.login_customer_id, manager_id, account.customer_id]
        db.add(GoogleAccountAccessPath(
            connection_id=connection.id, account_id=account.id, mcc_account_id=manager.id,
            target_customer_id=account.customer_id, root_customer_id=connection.login_customer_id,
            manager_customer_id=manager_id, customer_path=path,
            path_fingerprint=hashlib.sha256("/".join(path).encode()).hexdigest(),
            depth=2, is_primary=True, first_seen_at=now - timedelta(days=45), last_seen_at=now,
        ))
        daily_rows = list(db.scalars(select(AccountMetricDaily).where(
            AccountMetricDaily.account_id == account.id, AccountMetricDaily.timezone_mode == "ACCOUNT",
        ).order_by(AccountMetricDaily.metric_date)).all())
        total_cost = total_clicks = total_impressions = total_registrations = total_deposits = 0
        for daily in daily_rows:
            registrations = int(Decimal(str(daily.conversions or 0)) * Decimal("0.8"))
            deposits = registrations // 5
            daily.registrations = registrations
            daily.deposits = deposits
            daily.registration_data_available = True
            daily.deposit_data_available = True
            daily.conversion_value = deposits * 190
            daily.deposit_value = deposits * 190
            daily.data_source_mode = "SIMULATION"
            daily.active_campaigns = int(account.work_status == "WORKING")
            daily.disapproved_ads = int(market == "Nordics")
            total_cost += daily.cost_micros or 0
            total_clicks += daily.clicks or 0
            total_impressions += daily.impressions or 0
            total_registrations += registrations
            total_deposits += deposits
            db.add(AccountMetricDaily(
                account_id=account.id, metric_date=daily.metric_date, timezone_mode="MOSCOW",
                data_source_mode="SIMULATION", source="PORTFOLIO_DATASET", observed_at=daily.observed_at,
                impressions=daily.impressions, clicks=daily.clicks, cost_micros=daily.cost_micros,
                conversions=daily.conversions, all_conversions=daily.all_conversions,
                registrations=registrations, deposits=deposits, conversion_value=deposits * 190,
                deposit_value=deposits * 190, registration_data_available=True, deposit_data_available=True,
                active_campaigns=daily.active_campaigns, disapproved_ads=daily.disapproved_ads,
            ))
            db.add(MetricSnapshot(
                connection_id=connection.id, customer_id=account.customer_id,
                snapshot_date=daily.metric_date.isoformat(), metrics={
                    "impressions": daily.impressions, "clicks": daily.clicks,
                    "cost_micros": daily.cost_micros, "conversions": daily.conversions,
                    "source": "PORTFOLIO_DATASET",
                },
            ))
        spent_micros += total_cost
        campaign = db.scalar(select(ControlCenterCampaign).where(ControlCenterCampaign.account_id == account.id))
        if not campaign:
            raise RuntimeError(f"Portfolio campaign missing: {market}")
        campaign.cost_micros = total_cost
        campaign.clicks = total_clicks
        campaign.impressions = total_impressions
        campaign.registrations = total_registrations
        campaign.deposits = total_deposits
        campaign.registration_data_available = True
        campaign.deposit_data_available = True
        campaign.policy_status = "DISAPPROVED" if market == "Nordics" else "APPROVED"
        ad_group = ControlCenterAdGroup(
            account_id=account.id, campaign_id=campaign.id,
            resource_name=f"customers/{account.customer_id}/adGroups/{99200 + index}",
            ad_group_id=str(99200 + index), name=f"{short_label} · Prospecting",
            status=campaign.status, ad_group_type="DEMAND_GEN", last_synced_at=now,
        )
        db.add(ad_group)
        db.flush()
        resource = f"customers/{account.customer_id}/adGroupAds/{99200 + index}~{99300 + index}"
        policy = "DISAPPROVED" if market == "Nordics" else "APPROVED"
        db.add(ControlCenterAd(
            account_id=account.id, campaign_id=campaign.id, ad_group_id=ad_group.id,
            resource_name=resource, ad_id=str(99300 + index), name=f"{short_label} · Creative 01",
            ad_type="DEMAND_GEN_MULTI_ASSET_AD", status=campaign.status, primary_status=policy,
            policy_summary={"approval_status": policy},
            disapproval_reasons=["DESTINATION_NOT_WORKING"] if market == "Nordics" else [],
            last_synced_at=now,
        ))
        db.add(ModerationRecord(
            connection_id=connection.id, customer_id=account.customer_id, resource_name=resource,
            approval_status=policy, checked_at=now,
            policy_topics=[{"topic": "DESTINATION_NOT_WORKING"}] if market == "Nordics" else [],
        ))
        db.add(ControlCenterEvent(
            account_id=account.id, actor_user_id=user.id, source="PORTFOLIO_DATASET",
            event_type="PORTFOLIO_WORKSPACE_PREPARED", summary=f"{market}: подготовлен рабочий набор данных",
            details={"source": "PORTFOLIO_DATASET"}, occurred_at=now,
        ))
        if market in {"Nordics", "Benelux"}:
            title = (
                "Nordics: проверить посадочную страницу" if market == "Nordics"
                else "Benelux: требуется верификация"
            )
            problem_type = "AD_DISAPPROVED" if market == "Nordics" else "VERIFICATION_REQUIRED"
            description = (
                "Объявление отклонено: посадочная страница недоступна. После исправления нужна повторная проверка."
                if market == "Nordics" else "Подтвердите рекламодателя до запуска кампании."
            )
            db.add(ControlCenterProblem(
                fingerprint=hashlib.sha256(f"portfolio-v1:{account.id}:{problem_type}".encode()).hexdigest(),
                connection_id=connection.id, account_id=account.id, campaign_id=campaign.id,
                source="PORTFOLIO_DATASET", problem_type=problem_type, severity="WARNING",
                title=title, description=description, first_seen_at=now, last_seen_at=now,
            ))
            db.add(Notification(
                user_id=user.id, severity="WARNING", title=title, message=description,
                entity_type="customer_account", entity_id=str(account.id),
            ))
    profile = FinanceProfile(
        name="Atlas · Медиабюджет", provider="INTERNAL_BUDGET", status="READY", created_by_id=user.id,
        details={"source": "PORTFOLIO_DATASET", "planned_budget": 100_000,
                 "spent": spent_micros / 1_000_000},
    )
    db.add(profile)
    db.flush()
    db.add(FinanceSnapshot(
        profile_id=profile.id, balance=100_000 - spent_micros / 1_000_000, currency="USD",
        provider_payload={"source": "PORTFOLIO_DATASET"},
    ))
    db.add(ControlCenterRule(
        name="Контроль CPA регистрации", mode="DRY_RUN", enabled=False,
        scope={"connection_ids": [str(connection.id)]},
        conditions=[{"field": "cpa_registration", "operator": "gt", "value": 60}],
        actions=[{"type": "NOTIFY"}], created_by_id=user.id,
    ))
    db.add(ApplicationSetting(key=DATASET_KEY, value={"prepared_at": now.isoformat(), "source": "PORTFOLIO_DATASET"}))
    return True


if __name__ == "__main__":
    with SessionLocal.begin() as session:
        changed = prepare_dataset(session)
    print("Related portfolio data prepared" if changed else "Related portfolio data already prepared")
