from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import decrypt_json, encrypt_json, utcnow
from app.db.models import GoogleConnection, GoogleCredential


def oauth_client_payload(connection: GoogleConnection) -> dict:
    credential = connection.oauth_client_credential or connection.auth_credential
    if not credential:
        return {}
    payload = decrypt_json(credential.encrypted_payload)
    return {
        "client_id": payload.get("client_id"),
        "client_secret": payload.get("client_secret"),
    }


def oauth_refresh_payload(connection: GoogleConnection) -> dict:
    if connection.oauth_refresh_credential:
        payload = decrypt_json(connection.oauth_refresh_credential.encrypted_payload)
        return {"refresh_token": payload.get("refresh_token")}
    if connection.auth_credential:
        payload = decrypt_json(connection.auth_credential.encrypted_payload)
        return {"refresh_token": payload.get("refresh_token")}
    return {}


def merged_auth_payload(connection: GoogleConnection) -> dict:
    if connection.auth_type == "SERVICE_ACCOUNT":
        if not connection.auth_credential:
            return {}
        return decrypt_json(connection.auth_credential.encrypted_payload)
    return {**oauth_client_payload(connection), **oauth_refresh_payload(connection)}


def store_refresh_token(
    db: Session,
    connection: GoogleConnection,
    refresh_token: str,
    created_by_id,
) -> GoogleCredential:
    credential = connection.oauth_refresh_credential
    if credential is None:
        credential = GoogleCredential(
            kind="OAUTH_REFRESH_TOKEN",
            encrypted_payload=encrypt_json({"refresh_token": refresh_token}),
            created_by_id=created_by_id,
        )
        db.add(credential)
        db.flush()
        connection.oauth_refresh_credential_id = credential.id
        connection.oauth_refresh_credential = credential
    else:
        credential.encrypted_payload = encrypt_json({"refresh_token": refresh_token})
        credential.last_rotated_at = utcnow()
    return credential


def clear_refresh_token(connection: GoogleConnection) -> None:
    if connection.oauth_refresh_credential:
        connection.oauth_refresh_credential.encrypted_payload = encrypt_json(
            {"refresh_token": None}
        )
        connection.oauth_refresh_credential.last_rotated_at = utcnow()
        return
    if connection.auth_credential:
        payload = decrypt_json(connection.auth_credential.encrypted_payload)
        connection.auth_credential.encrypted_payload = encrypt_json(
            {
                "client_id": payload.get("client_id"),
                "client_secret": payload.get("client_secret"),
            }
        )
        connection.auth_credential.last_rotated_at = utcnow()
