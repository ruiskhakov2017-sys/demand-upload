from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.domain_validation.providers.base import ProviderResult, ProviderUnavailable, ReputationTarget

IPQS_ENDPOINT = "https://ipqualityscore.com/api/json/url"


class IPQualityScoreProvider:
    name = "IPQUALITYSCORE"

    def __init__(self, *, enabled: bool, api_key: str | None, client: httpx.Client) -> None:
        self.enabled = enabled
        self.api_key = (api_key or "").strip() or None
        self.client = client

    def check(self, target: ReputationTarget) -> ProviderResult:
        if not self.enabled:
            return ProviderResult(self.name, "DISABLED")
        if not self.api_key:
            return ProviderResult(self.name, "NOT_CONFIGURED", diagnostics={"code": "MISSING_API_KEY"})
        try:
            response = self.client.get(
                IPQS_ENDPOINT,
                headers={"IPQS-KEY": self.api_key, "Accept": "application/json"},
                params={"url": target.url, "strictness": 1, "fast": "true", "timeout": 7},
            )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ProviderUnavailable("PROVIDER_TIMEOUT", {"provider": self.name}) from exc
        if response.status_code in {429, 500, 502, 503, 504}:
            raise ProviderUnavailable(
                "PROVIDER_UNAVAILABLE",
                {"provider": self.name, "http_status": response.status_code},
            )
        if response.status_code in {401, 403}:
            return ProviderResult(
                self.name,
                "NOT_CONFIGURED",
                diagnostics={"code": "AUTH_REJECTED", "http_status": response.status_code},
            )
        if response.status_code >= 400:
            raise ProviderUnavailable(
                "PROVIDER_ERROR",
                {"provider": self.name, "http_status": response.status_code},
            )
        payload = response.json()
        if payload.get("success") is False:
            raise ProviderUnavailable(
                "PROVIDER_ERROR",
                {
                    "provider": self.name,
                    "request_id": payload.get("request_id"),
                    "code": "UNSUCCESSFUL_RESPONSE",
                },
            )
        risk_score = _integer(payload.get("risk_score"))
        categories = [
            label
            for key, label in (
                ("unsafe", "UNSAFE"),
                ("phishing", "PHISHING"),
                ("malware", "MALWARE"),
                ("spamming", "SPAM"),
                ("parking", "PARKED_DOMAIN"),
            )
            if payload.get(key) is True
        ]
        if risk_score >= 85:
            categories.append("HIGH_RISK_SCORE")
        age_days = _domain_age_days(payload.get("domain_age"))
        diagnostics = {
            "risk_score": risk_score,
            "domain_age_days": age_days,
            "domain_trust": payload.get("domain_trust"),
            "domain_rank": payload.get("domain_rank"),
            "request_id": payload.get("request_id"),
        }
        if categories:
            return ProviderResult(self.name, "THREAT", sorted(set(categories)), diagnostics)
        if (age_days is not None and age_days <= 30) or payload.get("domain_trust") in {None, "N/A"}:
            warning_categories = ["NEW_DOMAIN"] if age_days is not None and age_days <= 30 else ["NO_HISTORY"]
            return ProviderResult(self.name, "LOW_REPUTATION", warning_categories, diagnostics)
        if risk_score >= 40:
            return ProviderResult(self.name, "LOW_REPUTATION", ["MEDIUM_RISK_SCORE"], diagnostics)
        return ProviderResult(self.name, "CLEAN", diagnostics=diagnostics)


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _domain_age_days(value: object) -> int | None:
    if not isinstance(value, dict):
        return None
    timestamp = value.get("timestamp")
    try:
        created = datetime.fromtimestamp(int(timestamp), tz=UTC)
    except (TypeError, ValueError, OSError):
        return None
    return max(0, (datetime.now(UTC) - created).days)
