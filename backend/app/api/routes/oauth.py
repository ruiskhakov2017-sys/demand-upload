from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_csrf
from app.api.workflow_schemas import OAuthStartOut
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decrypt_json, encrypt_json, hash_token, utcnow
from app.db.models import (
    AuthType,
    ConnectionStatus,
    GoogleConnection,
    OAuthAuthorization,
    User,
)
from app.domain.audit import record_audit

router = APIRouter(prefix="/google-connections", tags=["google-oauth"])
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"


@router.post("/{connection_id}/oauth/start", response_model=OAuthStartOut)
def start_oauth(
    connection_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> OAuthStartOut:
    connection = _oauth_connection(db, connection_id)
    auth_payload = decrypt_json(connection.auth_credential.encrypted_payload)
    client_id = auth_payload.get("client_id")
    client_secret = auth_payload.get("client_secret")
    if not client_id or not client_secret:
        raise HTTPException(status_code=409, detail="Сначала сохраните OAuth Client ID и Client Secret")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    redirect_uri = f"{settings.app_public_base_url.rstrip('/')}{settings.api_prefix}/google-connections/oauth/callback"
    expires_at = utcnow() + timedelta(minutes=10)
    authorization = OAuthAuthorization(
        state_hash=hash_token(state),
        connection_id=connection.id,
        redirect_uri=redirect_uri,
        code_verifier_encrypted=encrypt_json({"code_verifier": verifier}),
        expires_at=expires_at,
        created_by_id=user.id,
    )
    db.add(authorization)
    record_audit(db, request, user, "google_oauth.start", "google_connection", str(connection.id))
    db.commit()
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_ADS_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return OAuthStartOut(authorization_url=f"{GOOGLE_AUTH_URL}?{query}", expires_at=expires_at)


@router.get("/oauth/callback", include_in_schema=False)
def oauth_callback(
    state: str = Query(min_length=20),
    code: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    authorization = db.scalar(select(OAuthAuthorization).where(OAuthAuthorization.state_hash == hash_token(state)))
    if not authorization or authorization.used_at or authorization.expires_at <= utcnow():
        return _oauth_redirect("error", "OAuth state недействителен или истёк")
    connection = _oauth_connection(db, authorization.connection_id)
    actor = db.get(User, authorization.created_by_id)
    if error or not code:
        authorization.used_at = utcnow()
        connection.status = ConnectionStatus.NEEDS_CREDENTIALS.value
        connection.last_error = f"OAuth отменён: {error or 'authorization code отсутствует'}"
        record_audit(
            db,
            None,
            actor,
            "google_oauth.cancel",
            "google_connection",
            str(connection.id),
            {"error": error},
        )
        db.commit()
        return _oauth_redirect("error", "Google authorization не завершена")

    auth_payload = decrypt_json(connection.auth_credential.encrypted_payload)
    verifier = decrypt_json(authorization.code_verifier_encrypted)["code_verifier"]
    try:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": auth_payload["client_id"],
                "client_secret": auth_payload["client_secret"],
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
                "redirect_uri": authorization.redirect_uri,
            },
            timeout=30,
        )
        response.raise_for_status()
        token_payload = response.json()
        refresh_token = token_payload.get("refresh_token") or auth_payload.get("refresh_token")
        if not refresh_token:
            raise ValueError("Google не вернул refresh token; повторите вход с выдачей доступа")
    except Exception as exc:
        connection.status = ConnectionStatus.ERROR.value
        connection.last_error = f"Обмен OAuth code не выполнен: {exc}"
        record_audit(
            db,
            None,
            actor,
            "google_oauth.exchange_failed",
            "google_connection",
            str(connection.id),
            {"error": str(exc)},
        )
        db.commit()
        return _oauth_redirect("error", "Не удалось получить OAuth token")

    connection.auth_credential.encrypted_payload = encrypt_json(
        {
            "client_id": auth_payload["client_id"],
            "client_secret": auth_payload["client_secret"],
            "refresh_token": refresh_token,
        }
    )
    connection.status = ConnectionStatus.DRAFT.value
    connection.last_error = None
    authorization.used_at = utcnow()
    record_audit(db, None, actor, "google_oauth.complete", "google_connection", str(connection.id))
    db.commit()
    return _oauth_redirect("success", "OAuth подключён; выполните проверку MCC")


@router.post("/{connection_id}/oauth/disconnect")
def disconnect_oauth(
    connection_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    connection = _oauth_connection(db, connection_id)
    auth_payload = decrypt_json(connection.auth_credential.encrypted_payload)
    connection.auth_credential.encrypted_payload = encrypt_json(
        {"client_id": auth_payload.get("client_id"), "client_secret": auth_payload.get("client_secret")}
    )
    connection.status = ConnectionStatus.NEEDS_CREDENTIALS.value
    connection.last_error = None
    record_audit(db, request, user, "google_oauth.disconnect", "google_connection", str(connection.id))
    db.commit()
    return {"ok": True, "status": connection.status}


def _oauth_connection(db: Session, connection_id: UUID) -> GoogleConnection:
    connection = db.get(GoogleConnection, connection_id)
    if not connection or connection.auth_type != AuthType.OAUTH_WEB.value or not connection.auth_credential:
        raise HTTPException(status_code=404, detail="OAuth Web подключение не найдено")
    return connection


def _oauth_redirect(result: str, message: str) -> RedirectResponse:
    query = urlencode({"oauth": result, "message": message})
    return RedirectResponse(f"{settings.app_public_base_url.rstrip('/')}/connections?{query}", status_code=302)
