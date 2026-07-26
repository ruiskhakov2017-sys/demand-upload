from __future__ import annotations

import httpx

from app.domain_validation.providers.base import ProviderResult, ProviderUnavailable, ReputationTarget

SPAMHAUS_ENDPOINT = "https://apibl.spamhaus.net/lookup/v1"
DBL_CATEGORIES = {
    2002: "SPAM",
    2003: "SPAM_REDIRECTOR",
    2004: "PHISHING",
    2005: "MALWARE",
    2006: "BOTNET_C2",
    2102: "ABUSED_LEGITIMATE_SPAM",
    2103: "ABUSED_LEGITIMATE_REDIRECTOR",
    2104: "ABUSED_LEGITIMATE_PHISHING",
    2105: "ABUSED_LEGITIMATE_MALWARE",
    2106: "ABUSED_LEGITIMATE_BOTNET_C2",
}


class SpamhausDqsProvider:
    name = "SPAMHAUS_DQS"

    def __init__(self, *, enabled: bool, api_key: str | None, client: httpx.Client) -> None:
        self.enabled = enabled
        self.api_key = (api_key or "").strip() or None
        self.client = client

    def check(self, target: ReputationTarget) -> ProviderResult:
        if not self.enabled:
            return ProviderResult(self.name, "DISABLED")
        if not self.api_key:
            return ProviderResult(self.name, "NOT_CONFIGURED", diagnostics={"code": "MISSING_API_KEY"})
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        dbl = self._lookup("DBL", target.domain, headers)
        if dbl is not None:
            category = DBL_CATEGORIES.get(dbl, "LISTED")
            return ProviderResult(
                self.name,
                "THREAT",
                categories=[category],
                diagnostics={"zone": "DBL", "response_code": dbl},
            )
        zrd = self._lookup("ZRD", target.domain, headers)
        if zrd is not None:
            return ProviderResult(
                self.name,
                "LOW_REPUTATION",
                categories=["ZERO_REPUTATION_DOMAIN"],
                diagnostics={"zone": "ZRD", "response_code": zrd},
            )
        return ProviderResult(self.name, "CLEAN", diagnostics={"zones": ["DBL", "ZRD"]})

    def _lookup(self, zone: str, domain: str, headers: dict[str, str]) -> int | None:
        try:
            response = self.client.get(f"{SPAMHAUS_ENDPOINT}/{zone}/{domain}", headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise ProviderUnavailable("PROVIDER_TIMEOUT", {"provider": self.name, "zone": zone}) from exc
        if response.status_code == 404:
            return None
        if response.status_code in {401, 403}:
            raise ProviderUnavailable(
                "PROVIDER_AUTH_REJECTED",
                {"provider": self.name, "zone": zone, "http_status": response.status_code},
            )
        if response.status_code in {429, 500, 502, 503, 504}:
            raise ProviderUnavailable(
                "PROVIDER_UNAVAILABLE",
                {"provider": self.name, "zone": zone, "http_status": response.status_code},
            )
        if response.status_code >= 400:
            raise ProviderUnavailable(
                "PROVIDER_ERROR",
                {"provider": self.name, "zone": zone, "http_status": response.status_code},
            )
        payload = response.json()
        value = payload.get("resp")
        if isinstance(value, list):
            value = value[0] if value else None
        try:
            return int(value)
        except (TypeError, ValueError):
            return 1
