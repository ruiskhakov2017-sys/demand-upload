from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_csrf, require_role
from app.api.schemas import CustomerAccountOut, SyncAccountsOut
from app.core.database import get_db
from app.core.security import utcnow
from app.db.models import AuditLog, CustomerAccount, GoogleConnection, User, UserRole
from app.google_ads.errors import GoogleAdsAdapterError
from app.google_ads.hierarchy import sync_google_ads_hierarchy
from app.google_ads.service import build_google_ads_adapter, is_google_connection_active

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[CustomerAccountOut])
def list_accounts(
    connection_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CustomerAccount]:
    query = select(CustomerAccount).order_by(CustomerAccount.descriptive_name, CustomerAccount.customer_id)
    if connection_id:
        query = query.where(CustomerAccount.connection_id == connection_id)
    return list(db.scalars(query).all())


@router.post("/sync/{connection_id}", response_model=SyncAccountsOut)
def sync_accounts(
    connection_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
    _: User = Depends(require_csrf),
) -> SyncAccountsOut:
    connection = db.get(GoogleConnection, connection_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Подключение не найдено")

    try:
        synced_accounts, request_ids = sync_google_ads_hierarchy(db, connection)
    except (GoogleAdsAdapterError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    db.add(
        AuditLog(
            created_at=utcnow(),
            actor_user_id=user.id,
            action="accounts.sync",
            entity_type="google_connection",
            entity_id=str(connection.id),
            ip_address=request.client.host if request.client else None,
            summary={
                "synced": len(synced_accounts),
                "request_ids": request_ids,
                "connection_mode": connection.connection_mode,
            },
        )
    )
    db.commit()
    for account in synced_accounts:
        db.refresh(account)
    return SyncAccountsOut(
        synced=len(synced_accounts),
        accounts=[CustomerAccountOut.model_validate(account) for account in synced_accounts],
    )


@router.get("/{account_id}/catalog")
def get_account_catalog(
    account_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)),
) -> dict:
    account = db.get(CustomerAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    connection = db.get(GoogleConnection, account.connection_id)
    if not is_google_connection_active(connection):
        raise HTTPException(status_code=409, detail="Google connection недоступен")
    return build_google_ads_adapter(db, connection).fetch_account_catalog(account.customer_id)
