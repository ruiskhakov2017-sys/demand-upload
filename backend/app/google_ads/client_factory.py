from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from app.google_ads.errors import GoogleAdsCredentialsError
from app.google_ads.interface import GoogleAdsConnectionConfig


def normalize_customer_id(value: str) -> str:
    customer_id = "".join(character for character in str(value) if character.isdigit())
    if not customer_id:
        raise GoogleAdsCredentialsError("MCC Customer ID должен содержать цифры")
    return customer_id


@contextmanager
def google_ads_client(config: GoogleAdsConnectionConfig) -> Iterator[Any]:
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except Exception as exc:  # pragma: no cover - depends on optional runtime package
        raise GoogleAdsCredentialsError("Пакет google-ads недоступен в runtime") from exc

    temp_key_path: str | None = None
    google_config = _to_google_ads_client_config(config)
    try:
        if "json_key" in config.auth_payload:
            temp_file = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
            json.dump(config.auth_payload["json_key"], temp_file)
            temp_file.close()
            temp_key_path = temp_file.name
            google_config["json_key_file_path"] = temp_key_path

        version = config.api_version.split(".", 1)[0]
        client = GoogleAdsClient.load_from_dict(google_config, version=version)
        yield client
    finally:
        if temp_key_path:
            Path(temp_key_path).unlink(missing_ok=True)


def _to_google_ads_client_config(config: GoogleAdsConnectionConfig) -> dict[str, Any]:
    developer_token = str(config.developer_token).strip()
    if not developer_token:
        raise GoogleAdsCredentialsError("Developer token отсутствует в сохранённых реквизитах")
    base: dict[str, Any] = {
        "developer_token": developer_token,
        "login_customer_id": normalize_customer_id(config.login_customer_id),
        "use_proto_plus": True,
    }

    if config.auth_type == "SERVICE_ACCOUNT":
        if "json_key_file_path" in config.auth_payload:
            base["json_key_file_path"] = config.auth_payload["json_key_file_path"]
            return base
        if "json_key" in config.auth_payload:
            return base
        raise GoogleAdsCredentialsError("Для service account нужен JSON key или путь к JSON key")

    if config.auth_type == "OAUTH_WEB":
        required = ["client_id", "client_secret", "refresh_token"]
        missing = [key for key in required if not config.auth_payload.get(key)]
        if missing:
            raise GoogleAdsCredentialsError("Для OAuth не хватает полей: " + ", ".join(missing))
        base.update(
            {
                "client_id": config.auth_payload["client_id"],
                "client_secret": config.auth_payload["client_secret"],
                "refresh_token": config.auth_payload["refresh_token"],
            }
        )
        return base

    raise GoogleAdsCredentialsError(f"Неподдерживаемый тип авторизации: {config.auth_type}")
