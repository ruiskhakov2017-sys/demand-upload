from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, func, or_, select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.db.models import (
    AccountMetricDaily,
    AccountMonitoringState,
    AccountNoteHistory,
    AccountTag,
    AccountTagHistory,
    AuditLog,
    CampaignUpload,
    ControlCenterActionItem,
    ControlCenterActionRequest,
    ControlCenterCampaign,
    ControlCenterEvent,
    ControlCenterProblem,
    ControlCenterQuotaLedger,
    ControlCenterRule,
    ControlCenterRuleEvaluation,
    ControlCenterSavedView,
    ControlCenterSyncItem,
    ControlCenterSyncRun,
    ControlCenterTag,
    CustomerAccount,
    GoogleConnection,
    Job,
    ModerationRecord,
    User,
    UserSession,
)

PREFIX = "[CC-ACCEPTANCE-20260727]"
USERNAME = "cc_acceptance_20260727"
CUSTOMER_IDS = [f"9901{index:06d}" for index in range(1, 51)]
TAG_NAMES = [
    f"{PREFIX} Приоритет",
    f"{PREFIX} Финансы",
    f"{PREFIX} Агентство",
]
QUOTA_REQUEST_PREFIX = "cc-acceptance-20260727"


def _fixture_accounts(db) -> list[CustomerAccount]:
    return list(
        db.scalars(
            select(CustomerAccount).where(
                CustomerAccount.customer_id.in_(CUSTOMER_IDS),
                CustomerAccount.local_name.like(f"{PREFIX}%"),
            )
        ).all()
    )


def seed() -> None:
    password = os.environ.get("CC_ACCEPTANCE_PASSWORD")
    if not password or len(password) < 16:
        raise RuntimeError("CC_ACCEPTANCE_PASSWORD must contain at least 16 characters")

    with SessionLocal() as db:
        if _fixture_accounts(db) or db.scalar(select(User).where(User.username == USERNAME)):
            raise RuntimeError("Acceptance fixture already exists; run cleanup first")

        connection = db.scalar(select(GoogleConnection).where(GoogleConnection.name == "vcc2"))
        if not connection:
            raise RuntimeError("Existing connection vcc2 was not found")

        now = datetime.now(UTC)
        user = User(
            username=USERNAME,
            email="cc-acceptance-20260727@example.invalid",
            password_hash=hash_password(password),
            role="ADMIN",
            is_active=True,
            is_setup_admin=False,
        )
        db.add(user)
        db.flush()

        tags = [
            ControlCenterTag(
                name=name,
                color=color,
                created_by_id=user.id,
            )
            for name, color in zip(TAG_NAMES, ["#2563a8", "#2e7d52", "#b7791f"], strict=True)
        ]
        db.add_all(tags)
        db.flush()

        work_statuses = ["WORKING", "PREPARATION", "PAUSED", "UNCLASSIFIED", "ARCHIVED"]
        google_statuses = ["ENABLED", "SUSPENDED", "CANCELED", "ENABLED"]

        for index, customer_id in enumerate(CUSTOMER_IDS, start=1):
            work_status = work_statuses[(index - 1) % len(work_statuses)]
            google_status = google_statuses[(index - 1) % len(google_statuses)]
            has_sync_error = index in {7, 8}
            note = f"acceptance-search-note-{index:02d}; владелец: команда {index % 4 + 1}"
            if index == 1:
                note += "; priority-blue"

            account = CustomerAccount(
                connection_id=connection.id,
                customer_id=customer_id,
                manager_customer_id=connection.login_customer_id,
                parent_customer_id=connection.login_customer_id,
                hierarchy_level=1 if index < 46 else 2,
                link_status="ACTIVE" if index != 50 else "DETACHED",
                descriptive_name=f"Google Acceptance Account {index:02d}",
                local_name=f"{PREFIX} Аккаунт {index:02d}",
                currency_code=["USD", "EUR", "RUB"][index % 3],
                time_zone=["Europe/Moscow", "America/New_York", "UTC"][index % 3],
                can_manage_clients=index > 45,
                is_test_account=False,
                is_hidden=False,
                status=google_status,
                work_status=work_status,
                current_note=note,
                note_updated_at=now - timedelta(hours=index),
                note_updated_by_id=user.id,
                is_pinned=index in {1, 2, 7},
                first_seen_at=now - timedelta(days=120),
                last_seen_at=now - timedelta(minutes=index),
                detached_at=now - timedelta(days=1) if index == 50 else None,
                last_sync_attempt_at=now + timedelta(days=1),
                last_sync_success_at=now - timedelta(minutes=index * 3),
                sync_error="DEADLINE_EXCEEDED: сохранены последние показатели" if has_sync_error else None,
                verification_status=(
                    "REQUIRED" if index % 10 == 0 else "VERIFIED" if index % 10 == 1 else "NOT_REQUIRED"
                ),
                verification_deadline=now + timedelta(days=7) if index % 10 == 0 else None,
                verification_action_url=(
                    "https://ads.google.com/aw/identity-verification" if index % 10 == 0 else None
                ),
                verification_checked_at=now - timedelta(hours=2),
            )
            db.add(account)
            db.flush()

            db.add(
                AccountNoteHistory(
                    account_id=account.id,
                    previous_note=None,
                    note=note,
                    changed_by_id=user.id,
                    changed_at=now - timedelta(days=2),
                )
            )

            assigned_tags = [tags[index % len(tags)]]
            if index in {1, 10, 20}:
                assigned_tags.append(tags[0])
            for tag in {item.id: item for item in assigned_tags}.values():
                db.add(
                    AccountTag(
                        account_id=account.id,
                        tag_id=tag.id,
                        assigned_by_id=user.id,
                        assigned_at=now - timedelta(days=1),
                    )
                )
                db.add(
                    AccountTagHistory(
                        account_id=account.id,
                        tag_name=tag.name,
                        action="ASSIGNED",
                        changed_by_id=user.id,
                        changed_at=now - timedelta(days=1),
                    )
                )

            no_metrics = index == 8
            db.add(
                AccountMonitoringState(
                    account_id=account.id,
                    period_start=now - timedelta(days=7),
                    period_end=now,
                    timezone_mode="ACCOUNT",
                    boundary_precision="EXACT",
                    impressions=None if no_metrics else index * 10_000,
                    clicks=None if no_metrics else index * 430,
                    cost_micros=None if no_metrics else index * 12_500_000,
                    conversions=None if no_metrics else float(index * 3),
                    conversion_value=None if no_metrics else float(index * 120),
                    active_campaigns=None if no_metrics else 1,
                    policy_issues=1 if index % 9 == 0 else 0,
                    freshness="ERROR" if has_sync_error else "FRESH",
                    data_observed_at=now - timedelta(minutes=index * 3),
                    aggregated_at=now - timedelta(minutes=index * 2),
                    last_error_code="DEADLINE_EXCEEDED" if has_sync_error else None,
                    last_request_id=f"acceptance-request-{index:02d}",
                )
            )

            if not no_metrics:
                for day_offset in range(7):
                    metric_date = (now - timedelta(days=6 - day_offset)).date()
                    db.add(
                        AccountMetricDaily(
                            account_id=account.id,
                            metric_date=metric_date,
                            timezone_mode="ACCOUNT",
                            boundary_precision="EXACT",
                            impressions=index * (900 + day_offset * 10),
                            clicks=index * (35 + day_offset),
                            cost_micros=index * (1_000_000 + day_offset * 50_000),
                            conversions=float(index + day_offset / 10),
                            conversion_value=float(index * 25 + day_offset),
                            source="ACCEPTANCE_FIXTURE",
                            observed_at=now - timedelta(minutes=index),
                        )
                    )

            campaigns: list[ControlCenterCampaign] = []
            for campaign_index in (1, 2):
                campaign_number = 9_000_000_000 + index * 10 + campaign_index
                has_policy_issue = index % 9 == 0 and campaign_index == 1
                campaign = ControlCenterCampaign(
                    account_id=account.id,
                    connection_id=connection.id,
                    resource_name=f"customers/{customer_id}/campaigns/{campaign_number}",
                    campaign_id=str(campaign_number),
                    name=f"{PREFIX} Campaign {index:02d}-{campaign_index}",
                    source="UPLOADER" if campaign_index == 1 else "EXTERNAL",
                    channel_type="DEMAND_GEN" if campaign_index == 1 else "SEARCH",
                    channel_subtype="DEMAND_GEN",
                    status="ENABLED" if campaign_index == 1 else "PAUSED",
                    primary_status="ELIGIBLE" if not has_policy_issue else "NOT_ELIGIBLE",
                    primary_status_reasons=[] if not has_policy_issue else ["POLICY"],
                    budget_resource_name=f"customers/{customer_id}/campaignBudgets/{campaign_number}",
                    budget_micros=index * 5_000_000,
                    budget_shared=index == 10 and campaign_index == 1,
                    impressions=None if no_metrics else index * 4_000,
                    clicks=None if no_metrics else index * 170,
                    cost_micros=None if no_metrics else index * 5_000_000,
                    conversions=None if no_metrics else float(index),
                    conversion_value=None if no_metrics else float(index * 50),
                    policy_issues=["MISREPRESENTATION"] if has_policy_issue else [],
                    manually_paused=False,
                    last_synced_at=now - timedelta(minutes=index),
                    sync_error="snapshot retained after timeout" if has_sync_error else None,
                )
                db.add(campaign)
                db.flush()
                campaigns.append(campaign)

            if index % 9 == 0:
                db.add(
                    ModerationRecord(
                        connection_id=connection.id,
                        customer_id=customer_id,
                        resource_name=f"customers/{customer_id}/adGroupAds/{index}",
                        approval_status="DISAPPROVED",
                        policy_topics=["MISREPRESENTATION"],
                        checked_at=now - timedelta(hours=1),
                    )
                )

            is_problem = (work_status == "WORKING" and google_status != "ENABLED") or index % 7 == 0
            if is_problem:
                fingerprint = hashlib.sha256(f"{PREFIX}:{customer_id}:STATUS".encode()).hexdigest()
                db.add(
                    ControlCenterProblem(
                        fingerprint=fingerprint,
                        connection_id=connection.id,
                        account_id=account.id,
                        campaign_id=campaigns[0].id if index % 9 == 0 else None,
                        source="ACCEPTANCE_FIXTURE",
                        problem_type="ACCOUNT_STATUS" if google_status != "ENABLED" else "SYNC_ERROR",
                        severity="ERROR" if google_status != "ENABLED" else "WARNING",
                        title=(
                            "Google аккаунт недоступен"
                            if google_status != "ENABLED"
                            else "Синхронизация временно недоступна"
                        ),
                        description=f"Acceptance diagnostic for account {index:02d}",
                        google_code=google_status if google_status != "ENABLED" else "DEADLINE_EXCEEDED",
                        request_id=f"acceptance-request-{index:02d}",
                        state="NEW",
                        first_seen_at=now - timedelta(days=1),
                        last_seen_at=now - timedelta(minutes=index),
                        diagnostics={"fixture": PREFIX, "last_known_metrics_preserved": has_sync_error},
                    )
                )

            db.add(
                ControlCenterEvent(
                    account_id=account.id,
                    actor_user_id=user.id,
                    event_type="ACCEPTANCE_FIXTURE_CREATED",
                    source="ACCEPTANCE_FIXTURE",
                    summary=f"Создан временный аккаунт {index:02d}",
                    details={"fixture": PREFIX},
                    occurred_at=now - timedelta(hours=3),
                )
            )

        db.add_all(
            [
                ControlCenterQuotaLedger(
                    connection_id=connection.id,
                    operation_date=date.today(),
                    category="BACKGROUND_SYNC",
                    operation_count=123,
                    succeeded=True,
                    request_id=f"{QUOTA_REQUEST_PREFIX}-ok",
                ),
                ControlCenterQuotaLedger(
                    connection_id=connection.id,
                    operation_date=date.today(),
                    category="BACKGROUND_SYNC",
                    operation_count=2,
                    succeeded=False,
                    request_id=f"{QUOTA_REQUEST_PREFIX}-failed",
                ),
            ]
        )
        db.commit()

        print(
            json.dumps(
                {
                    "username": USERNAME,
                    "accounts": len(CUSTOMER_IDS),
                    "campaigns": len(CUSTOMER_IDS) * 2,
                    "customer_id_first": CUSTOMER_IDS[0],
                    "customer_id_last": CUSTOMER_IDS[-1],
                },
                ensure_ascii=False,
            )
        )


def cleanup() -> None:
    with SessionLocal() as db:
        accounts = _fixture_accounts(db)
        account_ids = [item.id for item in accounts]
        customer_ids = [item.customer_id for item in accounts]
        user = db.scalar(select(User).where(User.username == USERNAME))
        user_id = user.id if user else None
        campaign_ids = list(
            db.scalars(
                select(ControlCenterCampaign.id).where(
                    ControlCenterCampaign.account_id.in_(account_ids)
                )
            ).all()
        ) if account_ids else []

        action_filters = []
        if user_id:
            action_filters.append(ControlCenterActionRequest.requested_by_id == user_id)
        if account_ids:
            action_filters.append(ControlCenterActionRequest.account_id.in_(account_ids))
        if campaign_ids:
            action_filters.append(ControlCenterActionRequest.campaign_id.in_(campaign_ids))
        action_ids = list(
            db.scalars(
                select(ControlCenterActionRequest.id).where(or_(*action_filters))
            ).all()
        ) if action_filters else []
        if action_ids:
            db.execute(
                delete(ControlCenterActionItem).where(
                    ControlCenterActionItem.action_request_id.in_(action_ids)
                )
            )
            db.execute(
                delete(ControlCenterActionRequest).where(
                    ControlCenterActionRequest.id.in_(action_ids)
                )
            )

        rule_ids = list(
            db.scalars(
                select(ControlCenterRule.id).where(ControlCenterRule.name.like(f"{PREFIX}%"))
            ).all()
        )
        evaluation_filters = []
        if account_ids:
            evaluation_filters.append(
                ControlCenterRuleEvaluation.account_id.in_(account_ids)
            )
        if campaign_ids:
            evaluation_filters.append(
                ControlCenterRuleEvaluation.campaign_id.in_(campaign_ids)
            )
        if evaluation_filters:
            db.execute(
                delete(ControlCenterRuleEvaluation).where(
                    or_(*evaluation_filters)
                )
            )
        if rule_ids:
            db.execute(
                delete(ControlCenterRuleEvaluation).where(
                    ControlCenterRuleEvaluation.rule_id.in_(rule_ids)
                )
            )
            db.execute(delete(ControlCenterRule).where(ControlCenterRule.id.in_(rule_ids)))

        if account_ids:
            sync_run_ids = list(
                db.scalars(
                    select(ControlCenterSyncItem.sync_run_id).where(
                        ControlCenterSyncItem.account_id.in_(account_ids)
                    )
                ).all()
            )
            db.execute(
                delete(ControlCenterSyncItem).where(
                    ControlCenterSyncItem.account_id.in_(account_ids)
                )
            )
            for sync_run_id in set(sync_run_ids):
                remaining = db.scalar(
                    select(func.count())
                    .select_from(ControlCenterSyncItem)
                    .where(ControlCenterSyncItem.sync_run_id == sync_run_id)
                )
                if not remaining:
                    db.execute(
                        delete(ControlCenterSyncRun).where(
                            ControlCenterSyncRun.id == sync_run_id
                        )
                    )

        if user_id:
            db.execute(
                delete(ControlCenterSavedView).where(
                    ControlCenterSavedView.owner_user_id == user_id
                )
            )
            db.execute(
                delete(CampaignUpload).where(CampaignUpload.created_by_id == user_id)
            )
            db.execute(delete(Job).where(Job.created_by_id == user_id))
            db.execute(delete(AuditLog).where(AuditLog.actor_user_id == user_id))
            db.execute(delete(UserSession).where(UserSession.user_id == user_id))

        if account_ids:
            db.execute(
                delete(ControlCenterEvent).where(
                    or_(
                        ControlCenterEvent.account_id.in_(account_ids),
                        ControlCenterEvent.actor_user_id == user_id if user_id else False,
                    )
                )
            )
            db.execute(
                delete(ControlCenterProblem).where(
                    or_(
                        ControlCenterProblem.account_id.in_(account_ids),
                        ControlCenterProblem.campaign_id.in_(campaign_ids) if campaign_ids else False,
                    )
                )
            )
            db.execute(
                delete(AccountTagHistory).where(
                    AccountTagHistory.account_id.in_(account_ids)
                )
            )
            db.execute(
                delete(AccountNoteHistory).where(
                    AccountNoteHistory.account_id.in_(account_ids)
                )
            )
            db.execute(delete(AccountTag).where(AccountTag.account_id.in_(account_ids)))
            db.execute(
                delete(AccountMetricDaily).where(
                    AccountMetricDaily.account_id.in_(account_ids)
                )
            )
            db.execute(
                delete(AccountMonitoringState).where(
                    AccountMonitoringState.account_id.in_(account_ids)
                )
            )
            db.execute(
                delete(ControlCenterCampaign).where(
                    ControlCenterCampaign.account_id.in_(account_ids)
                )
            )
            db.execute(
                delete(CustomerAccount).where(CustomerAccount.id.in_(account_ids))
            )

        if customer_ids:
            db.execute(
                delete(ModerationRecord).where(
                    ModerationRecord.customer_id.in_(customer_ids)
                )
            )
        db.execute(
            delete(ControlCenterQuotaLedger).where(
                ControlCenterQuotaLedger.request_id.like(f"{QUOTA_REQUEST_PREFIX}%")
            )
        )
        db.execute(delete(ControlCenterTag).where(ControlCenterTag.name.in_(TAG_NAMES)))
        if user_id:
            db.execute(delete(User).where(User.id == user_id))
        db.commit()

        remaining_accounts = len(_fixture_accounts(db))
        remaining_user = int(
            db.scalar(
                select(func.count()).select_from(User).where(User.username == USERNAME)
            )
            or 0
        )
        print(
            json.dumps(
                {
                    "removed_accounts": len(account_ids),
                    "remaining_accounts": remaining_accounts,
                    "remaining_user": remaining_user,
                }
            )
        )
        if remaining_accounts or remaining_user:
            raise RuntimeError("Acceptance fixture cleanup is incomplete")


def verify() -> None:
    with SessionLocal() as db:
        accounts = _fixture_accounts(db)
        user_exists = bool(db.scalar(select(User.id).where(User.username == USERNAME)))
        campaigns = int(
            db.scalar(
                select(func.count())
                .select_from(ControlCenterCampaign)
                .where(
                    ControlCenterCampaign.account_id.in_([item.id for item in accounts])
                )
            )
            or 0
        ) if accounts else 0
        print(
            json.dumps(
                {
                    "accounts": len(accounts),
                    "campaigns": campaigns,
                    "user_exists": user_exists,
                }
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["seed", "cleanup", "verify"])
    args = parser.parse_args()
    {"seed": seed, "cleanup": cleanup, "verify": verify}[args.command]()
