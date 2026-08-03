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
    EnvironmentType,
    GoogleConnection,
    GoogleConnectionMode,
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
    if db.scalar(select(GoogleConnection).where(GoogleConnection.name == payload.name)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Подключение с таким названием уже существует",
        )
    developer_credential = None
    auth_credential = None
    oauth_client_credential = None
    credential_source = None
    if payload.credential_source_connection_id:
        credential_source = db.get(
            GoogleConnection, payload.credential_source_connection_id
        )
        if not credential_source:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Источник защищённых реквизитов не найден",
            )
        developer_credential = credential_source.developer_token_credential
        oauth_client_credential = (
            credential_source.oauth_client_credential
            or credential_source.auth_credential
        )
        if not developer_credential or not oauth_client_credential:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "В выбранном credential profile нет Developer Token "
                    "или OAuth Client"
                ),
            )
    elif payload.developer_token:
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

    if any(value for value in auth_payload.values()) and not credential_source:
        auth_credential = GoogleCredential(
            kind=payload.auth_type.value,
            encrypted_payload=encrypt_json(auth_payload),
            created_by_id=user.id,
        )
        db.add(auth_credential)
        if payload.auth_type == AuthType.OAUTH_WEB:
            oauth_client_credential = auth_credential

    has_refresh_token = bool(payload.oauth_refresh_token)
    connection = GoogleConnection(
        name=payload.name,
        login_customer_id=payload.login_customer_id,
        auth_type=payload.auth_type.value,
        environment=(
            EnvironmentType.TEST.value
            if payload.connection_mode == GoogleConnectionMode.GOOGLE_TEST
            else payload.environment.value
        ),
        connection_mode=payload.connection_mode.value,
        developer_token_credential=developer_credential,
        auth_credential=auth_credential,
        oauth_client_credential=oauth_client_credential,
        api_version=settings.google_ads_api_version,
        test_hierarchy_root_customer_id=(
            payload.login_customer_id
            if payload.connection_mode == GoogleConnectionMode.GOOGLE_TEST
            else None
        ),
        status=(
            ConnectionStatus.DRAFT.value
            if developer_credential
            and (auth_credential or oauth_client_credential)
            and (payload.auth_type == AuthType.SERVICE_ACCOUNT or has_refresh_token)
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
            summary=connection_create_audit_summary(payload),
        )
    )
    db.commit()
    db.refresh(connection)
    return connection


def connection_create_audit_summary(
    payload: GoogleConnectionCreateIn,
) -> dict:
    return redact(payload.model_dump(mode="json"))


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
        if connection.connection_mode == GoogleConnectionMode.GOOGLE_TEST.value:
            try:
                from app.google_ads.hierarchy import sync_google_ads_hierarchy

                _, hierarchy_request_ids = sync_google_ads_hierarchy(db, connection)
                if hierarchy_request_ids and not result.request_id:
                    result.request_id = hierarchy_request_ids[-1]
            except Exception as exc:
                result = AdapterCheckOut(
                    ok=False,
                    status=ConnectionStatus.ERROR.value,
                    message=str(exc),
                    api_version=connection.api_version,
                )
        if result.ok:
            connection.status = ConnectionStatus.VERIFIED.value
            connection.last_error = None
        else:
            connection.status = ConnectionStatus.ERROR.value
            connection.last_error = result.message
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
