import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from app.core.config import settings

password_hasher = PasswordHasher()


def utcnow() -> datetime:
    return datetime.now(UTC)


def expires_in(minutes: int) -> datetime:
    return utcnow() + timedelta(minutes=minutes)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def generate_token(prefix: str = "dgu") -> str:
    return f"{prefix}_{secrets.token_urlsafe(48)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.app_encryption_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_json(payload: dict[str, Any]) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return _fernet().encrypt(raw)


def decrypt_json(payload: bytes) -> dict[str, Any]:
    raw = _fernet().decrypt(payload)
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Encrypted payload is not a JSON object")
    return data


SENSITIVE_KEYS = {
    "developer_token",
    "client_secret",
    "refresh_token",
    "private_key",
    "authorization",
    "password",
    "session",
}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "***REDACTED***" if key.lower() in SENSITIVE_KEYS else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
