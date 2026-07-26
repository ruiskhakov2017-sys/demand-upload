from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.core.config import Settings, settings
from app.domain_validation.providers import (
    GoogleWebRiskProvider,
    IPQualityScoreProvider,
    SpamhausDqsProvider,
)
from app.domain_validation.providers.base import (
    ProviderResult,
    ProviderUnavailable,
    ReputationProvider,
    ReputationTarget,
)
from app.domain_validation.url_tools import domain_from_url, safe_url_for_storage

REQUIRED_FOR_BLOCK = {"GOOGLE_WEB_RISK", "SPAMHAUS_DQS"}


class ReputationChecker:
    def __init__(
        self,
        *,
        providers: list[ReputationProvider] | None = None,
        config: Settings = settings,
        client: httpx.Client | None = None,
        attempts: int = 2,
    ) -> None:
        self.config = config
        self.attempts = max(1, min(attempts, 2))
        if providers is not None:
            self.providers = providers
            return
        shared_client = client or httpx.Client(
            timeout=httpx.Timeout(config.domain_validation_timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "DemandGenUploader-Reputation/1.0"},
        )
        self.providers = [
            GoogleWebRiskProvider(
                enabled=config.web_risk_enabled,
                api_key=config.web_risk_api_key,
                client=shared_client,
            ),
            SpamhausDqsProvider(
                enabled=config.spamhaus_dqs_enabled,
                api_key=config.spamhaus_dqs_key,
                client=shared_client,
            ),
            IPQualityScoreProvider(
                enabled=config.ipqs_enabled,
                api_key=config.ipqs_api_key,
                client=shared_client,
            ),
        ]

    def check(self, value: str) -> dict:
        safe_url = safe_url_for_storage(value)
        target = ReputationTarget(url=safe_url, domain=domain_from_url(safe_url))
        checked_at = datetime.now(UTC)
        results = [self._check_provider(provider, target) for provider in self.providers]
        serious = [item for item in results if item.verdict == "THREAT"]
        low = [item for item in results if item.verdict == "LOW_REPUTATION"]
        missing = [item for item in results if item.verdict == "NOT_CONFIGURED"]
        unavailable = [item for item in results if item.verdict == "UNAVAILABLE"]
        enabled = [item for item in results if item.verdict != "DISABLED"]
        by_name = {item.provider: item for item in results}
        required_problem = any(
            by_name.get(name) is None
            or by_name[name].verdict in {"DISABLED", "NOT_CONFIGURED", "UNAVAILABLE"}
            for name in REQUIRED_FOR_BLOCK
        )
        if serious:
            status = "THREAT"
        elif low:
            status = "LOW_REPUTATION"
        elif unavailable:
            status = "CHECK_UNAVAILABLE"
        elif missing or not enabled:
            status = "NOT_CONFIGURED"
        else:
            status = "CLEAN"
        enforcement = self.config.domain_reputation_enforcement
        would_block = bool(serious) or (enforcement == "block" and required_problem)
        blocking = enforcement == "block" and would_block
        categories = sorted({category for item in results for category in item.categories})
        return {
            "status": status,
            "enforcement": enforcement,
            "blocking": blocking,
            "would_block": would_block,
            "required_providers_ready": not required_problem,
            "categories": categories,
            "providers": [item.as_dict() for item in results],
            "checked_at": checked_at.isoformat(),
        }

    def _check_provider(self, provider: ReputationProvider, target: ReputationTarget) -> ProviderResult:
        last_error: ProviderUnavailable | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                result = provider.check(target)
                result.attempts = attempt
                return result
            except ProviderUnavailable as exc:
                last_error = exc
        assert last_error is not None
        return ProviderResult(
            provider=provider.name,
            verdict="UNAVAILABLE",
            diagnostics={"code": last_error.code, **last_error.diagnostics},
            attempts=self.attempts,
        )
