from __future__ import annotations

from collections.abc import Callable

import httpx

from app.domain_validation.providers.base import ProviderResult, ProviderUnavailable, ReputationTarget

WEB_RISK_ENDPOINT = "https://webrisk.googleapis.com/v1/uris:search"
THREAT_TYPES = ("MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE")


class GoogleWebRiskProvider:
    name = "GOOGLE_WEB_RISK"

    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str | None,
        client: httpx.Client,
        access_token_provider: Callable[[], str] | None = None,
    ) -> None:
        self.enabled = enabled
        self.api_key = (api_key or "").strip() or None
        self.client = client
        self.access_token_provider = access_token_provider

    def check(self, target: ReputationTarget) -> ProviderResult:
        if not self.enabled:
            return ProviderResult(self.name, "DISABLED")
        headers: dict[str, str] = {}
        params: list[tuple[str, str]] = [("uri", target.url)]
        params.extend(("threatTypes", item) for item in THREAT_TYPES)
        if self.api_key:
            params.append(("key", self.api_key))
        else:
            token = self._access_token()
            if not token:
                return ProviderResult(self.name, "NOT_CONFIGURED", diagnostics={"code": "MISSING_CREDENTIALS"})
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self.client.get(WEB_RISK_ENDPOINT, params=params, headers=headers)
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
        categories = sorted(set((payload.get("threat") or {}).get("threatTypes") or []))
        return ProviderResult(
            self.name,
            "THREAT" if categories else "CLEAN",
            categories=categories,
            diagnostics={"http_status": response.status_code},
        )

    def _access_token(self) -> str | None:
        if self.access_token_provider:
            try:
                return self.access_token_provider()
            except Exception:
                return None
        try:
            import google.auth
            from google.auth.transport.requests import Request

            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(Request())
            return credentials.token
        except Exception:
            return None
