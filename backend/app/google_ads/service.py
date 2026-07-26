from sqlalchemy.orm import Session

from app.core.security import decrypt_json
from app.db.models import ConnectionStatus, GoogleConnection
from app.google_ads.client_factory import normalize_customer_id
from app.google_ads.interface import GoogleAdsConnectionConfig
from app.google_ads.versions.v24_2 import GoogleAdsV242Adapter

ACTIVE_GOOGLE_CONNECTION_STATUSES = frozenset(
    {
        ConnectionStatus.CONNECTED.value,
        ConnectionStatus.VERIFIED.value,
    }
)


def is_google_connection_active(connection: GoogleConnection | None) -> bool:
    return bool(connection and connection.status in ACTIVE_GOOGLE_CONNECTION_STATUSES)


def build_google_ads_adapter(db: Session, connection: GoogleConnection) -> GoogleAdsV242Adapter:
    if not connection.developer_token_credential or not connection.auth_credential:
        raise ValueError("Подключение не содержит сохранённых реквизитов Google Ads")

    developer_payload = decrypt_json(connection.developer_token_credential.encrypted_payload)
    auth_payload = decrypt_json(connection.auth_credential.encrypted_payload)
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
        developer_token=developer_token,
        auth_payload=auth_payload,
        timeout_seconds=connection.timeout_seconds,
        retry_count=connection.retry_count,
    )
    return GoogleAdsV242Adapter(config)
