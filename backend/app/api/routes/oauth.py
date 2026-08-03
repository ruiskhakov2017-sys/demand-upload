from __future__ import annotations

import base64
import hashlib
import html
import secrets
from datetime import timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
from app.google_ads.connection_credentials import (
    clear_refresh_token,
    oauth_client_payload,
    oauth_refresh_payload,
    store_refresh_token,
)
from app.google_ads.hierarchy import sync_google_ads_hierarchy

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
    auth_payload = oauth_client_payload(connection)
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
def oauth_callback_form(
    state: str = Query(min_length=20),
    code: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    action = f"{settings.api_prefix}/google-connections/oauth/callback"
    fields = [
        ("state", state),
        ("code", code),
        ("error", error),
    ]
    inputs = "".join(
        (
            f'<input type="hidden" name="{name}" '
            f'value="{html.escape(value, quote=True)}">'
        )
        for name, value in fields
        if value is not None
    )
    page = f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Завершение подключения Google</title>
</head>
<body>
  <form method="post" action="{html.escape(action, quote=True)}">
    {inputs}
    <button type="submit">Завершить подключение Google</button>
  </form>
  <script>document.forms[0].submit();</script>
</body>
</html>"""
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


@router.post("/oauth/callback", include_in_schema=False)
def oauth_callback(
    state: str = Form(min_length=20),
    code: str | None = Form(default=None),
    error: str | None = Form(default=None),
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

    auth_payload = oauth_client_payload(connection)
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
        if response.is_error:
            raise OAuthExchangeError.from_response(response)
        token_payload = response.json()
        refresh_token = token_payload.get("refresh_token") or oauth_refresh_payload(
            connection
        ).get("refresh_token")
        if not refresh_token:
            raise ValueError("Google не вернул refresh token; повторите вход с выдачей доступа")
    except Exception as exc:
        connection.status = ConnectionStatus.ERROR.value
        safe_error = _oauth_error_message(exc)
        connection.last_error = f"Обмен OAuth code не выполнен: {safe_error}"
        record_audit(
            db,
            None,
            actor,
            "google_oauth.exchange_failed",
            "google_connection",
            str(connection.id),
            {"error": safe_error},
        )
        db.commit()
        return _oauth_redirect("error", safe_error)

    store_refresh_token(
        db,
        connection,
        refresh_token,
        authorization.created_by_id,
    )
    connection.status = ConnectionStatus.DRAFT.value
    connection.last_error = None
    authorization.used_at = utcnow()
    record_audit(db, None, actor, "google_oauth.complete", "google_connection", str(connection.id))
    try:
        accounts, request_ids = sync_google_ads_hierarchy(db, connection)
        connection.status = ConnectionStatus.VERIFIED.value
        record_audit(
            db,
            None,
            actor,
            "google_oauth.hierarchy_verified",
            "google_connection",
            str(connection.id),
            {
                "accounts": len(accounts),
                "request_ids": request_ids,
                "connection_mode": connection.connection_mode,
            },
        )
        db.commit()
        return _oauth_redirect(
            "success",
            f"OAuth подключён; тестовая иерархия подтверждена, аккаунтов: {len(accounts)}",
        )
    except Exception as exc:
        safe_error = str(exc)
        connection.status = ConnectionStatus.ERROR.value
        connection.last_error = safe_error
        record_audit(
            db,
            None,
            actor,
            "google_oauth.hierarchy_failed",
            "google_connection",
            str(connection.id),
            {"error": safe_error},
        )
        db.commit()
        return _oauth_redirect(
            "error",
            f"OAuth подключён, но иерархия Google Ads не подтверждена: {safe_error}",
        )


@router.post("/{connection_id}/oauth/disconnect")
def disconnect_oauth(
    connection_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_csrf),
) -> dict:
    connection = _oauth_connection(db, connection_id)
    clear_refresh_token(connection)
    connection.status = ConnectionStatus.NEEDS_CREDENTIALS.value
    connection.last_error = None
    record_audit(db, request, user, "google_oauth.disconnect", "google_connection", str(connection.id))
    db.commit()
    return {"ok": True, "status": connection.status}


def _oauth_connection(db: Session, connection_id: UUID) -> GoogleConnection:
    connection = db.get(GoogleConnection, connection_id)
    if (
        not connection
        or connection.auth_type != AuthType.OAUTH_WEB.value
        or not (connection.oauth_client_credential or connection.auth_credential)
    ):
        raise HTTPException(status_code=404, detail="OAuth Web подключение не найдено")
    return connection


def _oauth_redirect(result: str, message: str) -> RedirectResponse:
    query = urlencode({"oauth": result, "message": message})
    return RedirectResponse(f"{settings.app_public_base_url.rstrip('/')}/connections?{query}", status_code=302)


class OAuthExchangeError(RuntimeError):
    def __init__(self, code: str, description: str, status_code: int) -> None:
        self.code = code
        self.description = description
        self.status_code = status_code
        super().__init__(f"{code}: {description}")

    @classmethod
    def from_response(cls, response: httpx.Response) -> OAuthExchangeError:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        code = str(payload.get("error") or f"HTTP_{response.status_code}")
        description = str(
            payload.get("error_description")
            or payload.get("error_uri")
            or "Google OAuth отклонил обмен authorization code"
        )
        return cls(code, description, response.status_code)


def _oauth_error_message(exc: Exception) -> str:
    if isinstance(exc, OAuthExchangeError):
        testing_hint = ""
        lowered = f"{exc.code} {exc.description}".lower()
        if "access_denied" in lowered or "403" in lowered or "test user" in lowered:
            testing_hint = (
                " Добавьте email тестового пользователя в "
                "OAuth consent screen → Test users."
            )
        return (
            f"Google OAuth error {exc.code} (HTTP {exc.status_code}): "
            f"{exc.description}.{testing_hint}"
        )
    return str(exc)
