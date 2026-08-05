from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ConnectionStatus, GoogleConnection, MetricSourceMapping


@dataclass(frozen=True)
class ProviderCapabilities:
    provider_id: str
    label: str
    data_kinds: tuple[str, ...]
    semantic_metrics: tuple[str, ...]
    supports_read: bool
    supports_refresh: bool
    provenance_version: str = "1.0"


@dataclass(frozen=True)
class ProviderSetupStatus:
    provider_id: str
    configured: bool
    enabled: bool
    live_verified: bool
    setup_status: str
    explanation: str
    active_mappings: int = 0


@dataclass(frozen=True)
class ProvenanceEnvelope:
    provider: str
    semantic_metric: str
    source_id: str
    attribution: str
    observed_at: str | None
    synced_at: str | None
    original_currency: str | None
    completeness: str
    warnings: tuple[str, ...] = ()
    version: str = "1.0"


class AnalyticsProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...

    def status(self, db: Session) -> ProviderSetupStatus: ...

    def normalize_provenance(self, payload: dict[str, Any]) -> ProvenanceEnvelope: ...


class _BaseProvider:
    provider_id = ""
    label = ""
    data_kinds: tuple[str, ...] = ()
    semantic_metrics: tuple[str, ...] = ()
    supports_read = False
    supports_refresh = False

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            label=self.label,
            data_kinds=self.data_kinds,
            semantic_metrics=self.semantic_metrics,
            supports_read=self.supports_read,
            supports_refresh=self.supports_refresh,
        )

    def normalize_provenance(self, payload: dict[str, Any]) -> ProvenanceEnvelope:
        return ProvenanceEnvelope(
            provider=self.provider_id,
            semantic_metric=str(payload.get("semantic_metric") or "DATA"),
            source_id=str(payload.get("source_id") or self.provider_id),
            attribution=str(payload.get("attribution") or "UNMAPPED"),
            observed_at=_optional_string(payload.get("observed_at")),
            synced_at=_optional_string(payload.get("synced_at")),
            original_currency=_optional_string(payload.get("original_currency")),
            completeness=str(payload.get("completeness") or "UNKNOWN"),
            warnings=tuple(str(item) for item in payload.get("warnings") or ()),
        )

    def _mapping_count(self, db: Session) -> int:
        return int(
            db.scalar(
                select(func.count(MetricSourceMapping.id)).where(
                    MetricSourceMapping.provider == self.provider_id,
                    MetricSourceMapping.is_active.is_(True),
                )
            )
            or 0
        )


class GoogleAdsAnalyticsProvider(_BaseProvider):
    provider_id = "GOOGLE_ADS"
    label = "Google Ads"
    data_kinds = ("ACCOUNT", "CAMPAIGN", "AD", "ASSET", "POLICY", "PERFORMANCE")
    semantic_metrics = ("COST", "IMPRESSIONS", "CLICKS", "CTR", "CPC", "CONVERSIONS", "VALUE")
    supports_read = True
    supports_refresh = True

    def status(self, db: Session) -> ProviderSetupStatus:
        active = int(
            db.scalar(
                select(func.count(GoogleConnection.id)).where(
                    GoogleConnection.status.in_([ConnectionStatus.CONNECTED.value, ConnectionStatus.VERIFIED.value])
                )
            )
            or 0
        )
        configured = active > 0
        return ProviderSetupStatus(
            provider_id=self.provider_id,
            configured=configured,
            enabled=configured,
            live_verified=configured,
            setup_status="READY" if configured else "NOT_CONFIGURED",
            explanation=(
                f"Активных подключений: {active}. Чтение выполняется существующим Google Ads adapter."
                if configured
                else "Сначала настройте и проверьте подключение Google Ads."
            ),
            active_mappings=self._mapping_count(db),
        )


class LocalBusinessProvider(_BaseProvider):
    provider_id = "BUSINESS"
    label = "Локальные business-метрики"
    data_kinds = ("MAPPED_CONVERSION", "BUSINESS_EVENT")
    semantic_metrics = ("LEAD", "REGISTRATION", "DEPOSIT", "PURCHASE", "REVENUE")
    supports_read = True

    def status(self, db: Session) -> ProviderSetupStatus:
        mappings = self._mapping_count(db)
        return ProviderSetupStatus(
            provider_id=self.provider_id,
            configured=mappings > 0,
            enabled=mappings > 0,
            live_verified=mappings > 0,
            setup_status="READY" if mappings else "MAPPING_REQUIRED",
            explanation=(
                "Используются сохранённые локальные сопоставления."
                if mappings
                else "Добавьте сопоставление источника, прежде чем использовать business-метрики."
            ),
            active_mappings=mappings,
        )


class DisabledExternalProvider(_BaseProvider):
    def __init__(self, provider_id: str, label: str, data_kinds: tuple[str, ...]) -> None:
        self.provider_id = provider_id
        self.label = label
        self.data_kinds = data_kinds
        self.semantic_metrics = ("LEAD", "REGISTRATION", "DEPOSIT", "PURCHASE", "REVENUE")

    def status(self, db: Session) -> ProviderSetupStatus:
        mappings = self._mapping_count(db)
        return ProviderSetupStatus(
            provider_id=self.provider_id,
            configured=False,
            enabled=False,
            live_verified=False,
            setup_status="CONNECTOR_NOT_IMPLEMENTED",
            explanation="Live-коннектор сознательно не включён без подтверждённого API-контракта и credentials.",
            active_mappings=mappings,
        )


PROVIDER_REGISTRY: tuple[AnalyticsProvider, ...] = (
    GoogleAdsAnalyticsProvider(),
    LocalBusinessProvider(),
    DisabledExternalProvider("KEITARO", "Keitaro", ("TRACKER_EVENT", "ATTRIBUTION")),
    DisabledExternalProvider("BROCARD", "Brocard", ("CARD", "BALANCE", "TRANSACTION")),
)


def source_registry_payload(db: Session) -> list[dict[str, Any]]:
    return [
        {
            "capabilities": asdict(provider.capabilities()),
            "status": asdict(provider.status(db)),
        }
        for provider in PROVIDER_REGISTRY
    ]


def provider_by_id(provider_id: str) -> AnalyticsProvider | None:
    normalized = provider_id.strip().upper()
    return next(
        (provider for provider in PROVIDER_REGISTRY if provider.capabilities().provider_id == normalized),
        None,
    )


def _optional_string(value: Any) -> str | None:
    return str(value) if value is not None else None
