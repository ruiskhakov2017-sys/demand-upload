from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_csrf, require_role
from app.api.schemas import (
    AdapterCheckOut,
    GoogleConnectionCreateIn,
    GoogleConnectionOut,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.security import encrypt_json, redact, utcnow
from app.db.models import (
    AuditLog,
    AuthType,
    ConnectionStatus,
    GoogleConnection,
    GoogleCredential,
    User,
    UserRole,
)
from app.google_ads.service import build_google_ads_adapter

router = APIRouter(prefix="/google-connections", tags=["google-connections"])


@router.get("", response_model=list[GoogleConnectionOut])
def list_connections(
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR, UserRole.VIEWER)),
) -> list[GoogleConnection]:
    return list(db.scalars(select(GoogleConnection).order_by(GoogleConnection.created_at.desc())).all())


@router.post("", response_model=GoogleConnectionOut, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: GoogleConnectionCreateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> GoogleConnection:
    developer_credential = None
    auth_credential = None
    if payload.developer_token:
        developer_credential = GoogleCredential(
            kind="DEVELOPER_TOKEN",
            encrypted_payload=encrypt_json({"developer_token": payload.developer_token}),
            created_by_id=user.id,
        )
        db.add(developer_credential)

    if payload.auth_type == AuthType.SERVICE_ACCOUNT:
        if payload.service_account_json:
            auth_payload = {"json_key": payload.service_account_json}
        else:
            auth_payload = {}
    else:
        auth_payload = {
            "client_id": payload.oauth_client_id,
            "client_secret": payload.oauth_client_secret,
            "refresh_token": payload.oauth_refresh_token,
        }

    if any(value for value in auth_payload.values()):
        auth_credential = GoogleCredential(
            kind=payload.auth_type.value,
            encrypted_payload=encrypt_json(auth_payload),
            created_by_id=user.id,
        )
        db.add(auth_credential)

    connection = GoogleConnection(
        name=payload.name,
        login_customer_id=payload.login_customer_id,
        auth_type=payload.auth_type.value,
        environment=payload.environment.value,
        developer_token_credential=developer_credential,
        auth_credential=auth_credential,
        api_version=settings.google_ads_api_version,
        status=(
            ConnectionStatus.DRAFT.value
            if developer_credential
            and auth_credential
            and (payload.auth_type == AuthType.SERVICE_ACCOUNT or payload.oauth_refresh_token)
            else ConnectionStatus.NEEDS_CREDENTIALS.value
        ),
        created_by_id=user.id,
    )
    db.add(connection)
    db.flush()
    db.add(
        AuditLog(
            created_at=utcnow(),
            actor_user_id=user.id,
            action="google_connection.create",
            entity_type="google_connection",
            entity_id=str(connection.id),
            ip_address=request.client.host if request.client else None,
            summary=redact(payload.model_dump()),
        )
    )
    db.commit()
    db.refresh(connection)
    return connection


@router.post("/{connection_id}/test", response_model=AdapterCheckOut)
def test_connection(
    connection_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
    _: User = Depends(require_csrf),
) -> AdapterCheckOut:
    connection = db.get(GoogleConnection, connection_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Подключение не найдено")
    try:
        adapter_result = build_google_ads_adapter(db, connection).test_connection()
        result = AdapterCheckOut(**adapter_result.__dict__)
    except Exception as exc:
        result = AdapterCheckOut(
            ok=False,
            status=ConnectionStatus.ERROR.value,
            message=str(exc),
            api_version=connection.api_version,
        )

    connection.last_checked_at = utcnow()
    if result.ok:
        connection.status = ConnectionStatus.VERIFIED.value
        connection.last_error = None
    else:
        connection.status = ConnectionStatus.ERROR.value
        connection.last_error = result.message

    db.add(
        AuditLog(
            created_at=utcnow(),
            actor_user_id=user.id,
            action="google_connection.test",
            entity_type="google_connection",
            entity_id=str(connection.id),
            ip_address=request.client.host if request.client else None,
            summary={"ok": result.ok, "status": connection.status, "request_id": result.request_id},
        )
    )
    db.commit()
    return result
