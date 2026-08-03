from sqlalchemy.orm import Session

from app.core.security import decrypt_json
from app.db.models import ConnectionStatus, GoogleConnection
from app.google_ads.client_factory import normalize_customer_id
from app.google_ads.connection_credentials import merged_auth_payload
from app.google_ads.interface import GoogleAdsConnectionConfig
from app.google_ads.versions.v24_2 import GoogleAdsV242Adapter
from app.google_ads.versions.v25 import GoogleAdsV25Adapter

ACTIVE_GOOGLE_CONNECTION_STATUSES = frozenset(
    {
        ConnectionStatus.CONNECTED.value,
        ConnectionStatus.VERIFIED.value,
    }
)


def is_google_connection_active(connection: GoogleConnection | None) -> bool:
    return bool(connection and connection.status in ACTIVE_GOOGLE_CONNECTION_STATUSES)


ADAPTER_REGISTRY = {
    "v24.2": GoogleAdsV242Adapter,
    "v25": GoogleAdsV25Adapter,
    "v25.0": GoogleAdsV25Adapter,
}


def build_google_ads_adapter(
    db: Session, connection: GoogleConnection
) -> GoogleAdsV242Adapter | GoogleAdsV25Adapter:
    if not connection.developer_token_credential:
        raise ValueError("Подключение не содержит сохранённых реквизитов Google Ads")

    developer_payload = decrypt_json(connection.developer_token_credential.encrypted_payload)
    auth_payload = merged_auth_payload(connection)
    developer_token = developer_payload.get("developer_token")
    if not developer_token:
        raise ValueError("Developer token отсутствует в сохранённых реквизитах")

    config = GoogleAdsConnectionConfig(
        connection_id=str(connection.id),
        name=connection.name,
        login_customer_id=normalize_customer_id(connection.login_customer_id),
        api_version=connection.api_version,
        auth_type=connection.auth_type,
        environment=connection.environment,
        connection_mode=connection.connection_mode,
        developer_token=developer_token,
        auth_payload=auth_payload,
        timeout_seconds=connection.timeout_seconds,
        retry_count=connection.retry_count,
    )
    version = connection.api_version.strip().lower()
    adapter_class = ADAPTER_REGISTRY.get(version)
    if adapter_class is None:
        supported = ", ".join(sorted(ADAPTER_REGISTRY))
        raise ValueError(
            f"Версия Google Ads API {connection.api_version!r} не поддерживается. "
            f"Доступны: {supported}."
        )
    return adapter_class(config)
