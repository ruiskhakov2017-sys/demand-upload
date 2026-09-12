from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.db.models import CustomerAccount, GoogleConnection
from app.google_ads.interface import GoogleAdsAdapter
from app.google_ads.safety import (
    require_connection_target,
    require_execution_mode_for_connection,
    require_fresh_account_state,
)


def refresh_google_ads_target(
    db: Session,
    connection: GoogleConnection,
    adapter: GoogleAdsAdapter,
    customer_id: str,
    *,
    confirmed_at: datetime | None = None,
    require_confirmation: bool = False,
) -> tuple[CustomerAccount, dict, list[str]]:
    require_execution_mode_for_connection(connection, connection.connection_mode)
    account = db.scalar(
        select(CustomerAccount).where(
            CustomerAccount.connection_id == connection.id,
            CustomerAccount.customer_id == customer_id,
        )
    )
    require_connection_target(
        connection,
        account,
        customer_id,
        connection.connection_mode,
    )
    assert account is not None

    fresh_state = adapter.read_control_center_account(customer_id)
    now = utcnow()
    account.last_sync_attempt_at = now
    account.last_google_request_ids = list(
        dict.fromkeys(
            [
                *(account.last_google_request_ids or []),
                *(fresh_state.get("_request_ids") or []),
            ]
        )
    )
    if not fresh_state.get("manager"):
        account.is_test_account = bool(fresh_state.get("test_account"))
        account.can_manage_clients = False
        if account.is_test_account:
            account.test_account_verified_at = now
        account.last_sync_success_at = now
        account.sync_error = None
    require_fresh_account_state(
        connection,
        account,
        customer_id,
        fresh_state,
        execution_mode=connection.connection_mode,
        confirmed_at=confirmed_at,
        require_confirmation=require_confirmation,
    )
    db.flush()
    return account, fresh_state, list(fresh_state.get("_request_ids") or [])


def refresh_google_ads_snapshot_targets(
    db: Session,
    connection: GoogleConnection,
    adapter: GoogleAdsAdapter,
    snapshot: dict,
    *,
    confirmed_at: datetime | None = None,
    require_confirmation: bool = False,
) -> list[str]:
    request_ids: list[str] = []
    customer_ids = {
        str(campaign.get("customer_id") or "")
        for campaign in snapshot.get("campaigns") or []
    }
    for customer_id in sorted(item for item in customer_ids if item):
        _, _, target_request_ids = refresh_google_ads_target(
            db,
            connection,
            adapter,
            customer_id,
            confirmed_at=confirmed_at,
            require_confirmation=require_confirmation,
        )
        request_ids.extend(target_request_ids)
    return list(dict.fromkeys(request_ids))


# Compatibility aliases for older integrations. Both now enforce the actual
# connection mode and configured access level instead of assuming test-only.
refresh_google_test_target = refresh_google_ads_target
refresh_google_test_snapshot_targets = refresh_google_ads_snapshot_targets
