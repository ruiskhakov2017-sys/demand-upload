from __future__ import annotations

import ast
import socket
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from app.api.routes.uploads import get_domain_validation
from app.domain_validation.availability import AvailabilityChecker
from app.domain_validation.providers.base import (
    ProviderResult,
    ProviderUnavailable,
    ReputationTarget,
)
from app.domain_validation.providers.ipqs import IPQualityScoreProvider
from app.domain_validation.providers.spamhaus import SpamhausDqsProvider
from app.domain_validation.providers.web_risk import GoogleWebRiskProvider
from app.domain_validation.reputation import ReputationChecker
from app.domain_validation.service import DomainValidationService, filter_blocked_campaigns
from app.domain_validation.url_tools import safe_url_for_storage

PUBLIC_IP = "93.184.216.34"
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _resolver(host: str, _port: int) -> list[str]:
    if host == "private.test":
        return ["10.0.0.8"]
    return [PUBLIC_IP]


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def _response(status: int, request: httpx.Request, **kwargs) -> httpx.Response:
    return httpx.Response(status, request=request, **kwargs)


def _availability(handler, **kwargs) -> AvailabilityChecker:
    return AvailabilityChecker(
        client=_client(handler),
        resolver=kwargs.pop("resolver", _resolver),
        timeout_seconds=1,
        max_redirects=kwargs.pop("max_redirects", 3),
        attempts=kwargs.pop("attempts", 2),
    )


def test_working_url_preserves_path_and_accepts_2xx() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return _response(204, request)

    result = _availability(handler).check("https://public.test/landing/page?offer=1")
    assert result["status"] == "WORKING"
    assert result["http_status"] == 204
    assert seen == ["https://public.test/landing/page?offer=1"]


def test_dns_error_has_stable_code_and_two_attempts() -> None:
    def resolver(_host: str, _port: int) -> list[str]:
        raise socket.gaierror("not found")

    result = _availability(lambda request: _response(200, request), resolver=resolver).check(
        "https://missing.test/path"
    )
    assert result["status"] == "UNAVAILABLE"
    assert result["code"] == "DNS_ERROR"
    assert result["attempts"] == 2


def test_timeout_has_stable_code_and_two_attempts() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("slow", request=request)

    result = _availability(handler).check("https://public.test/")
    assert result["code"] == "TIMEOUT"
    assert result["attempts"] == 2
    assert calls == 2


@pytest.mark.parametrize(("status", "code"), [(404, "HTTP_4XX"), (500, "HTTP_5XX")])
def test_http_errors_have_stable_codes(status: int, code: str) -> None:
    result = _availability(lambda request: _response(status, request)).check("https://public.test/")
    assert result["status"] == "UNAVAILABLE"
    assert result["code"] == code
    assert result["http_status"] == status


@pytest.mark.parametrize("status", [301, 302])
def test_allowed_redirect_is_followed(status: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/from":
            return _response(status, request, headers={"location": "/to"})
        return _response(200, request)

    result = _availability(handler).check("https://public.test/from")
    assert result["status"] == "WORKING"
    assert result["redirects"] == 1
    assert result["final_url"] == "https://public.test/to"


def test_redirect_loop_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        target = "/two" if request.url.path == "/one" else "/one"
        return _response(302, request, headers={"location": target})

    result = _availability(handler).check("https://public.test/one")
    assert result["code"] == "REDIRECT_LOOP"


def test_tls_error_has_stable_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("TLS certificate verify failed", request=request)

    result = _availability(handler).check("https://public.test/")
    assert result["code"] == "TLS_ERROR"


def test_head_405_falls_back_to_limited_get() -> None:
    methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "HEAD":
            return _response(405, request)
        assert request.headers["range"] == "bytes=0-0"
        return _response(206, request)

    result = _availability(handler).check("https://public.test/")
    assert result["status"] == "WORKING"
    assert methods == ["HEAD", "GET"]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://127.0.0.1/",
        "http://10.0.0.2/",
        "http://169.254.169.254/latest/meta-data/",
        "http://user:password@public.test/",
    ],
)
def test_ssrf_and_embedded_credentials_are_rejected(url: str) -> None:
    result = _availability(lambda request: _response(200, request)).check(url)
    assert result["status"] == "UNAVAILABLE"
    assert result["code"] in {"SSRF_BLOCKED", "CREDENTIALS_IN_URL"}


def test_public_redirect_to_private_ip_is_rejected_before_second_request() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return _response(302, request, headers={"location": "http://private.test/secret"})

    result = _availability(handler).check("https://public.test/start")
    assert result["code"] == "SSRF_BLOCKED"
    assert requests == ["https://public.test/start"]


def test_tracking_and_fragment_are_removed_for_reputation() -> None:
    sanitized = safe_url_for_storage(
        "https://public.test/path?utm_source=secret&offer=42&gclid=hidden#fragment"
    )
    assert sanitized == "https://public.test/path?offer=42"


def test_domain_validation_get_does_not_change_database_state() -> None:
    upload = SimpleNamespace(id=uuid4(), draft={}, source_rows=[], updated_at=datetime.now(UTC))
    before = deepcopy(upload.__dict__)

    class ReadOnlyDb:
        def get(self, _model, identifier):
            assert identifier == upload.id
            return upload

    report = get_domain_validation(upload.id, db=ReadOnlyDb(), user=SimpleNamespace())

    assert upload.__dict__ == before
    assert report["status"] == "NOT_RUN"
    assert report["checked_at"] is None


def test_get_routes_do_not_call_database_write_methods() -> None:
    forbidden = {"add", "add_all", "delete", "flush", "commit"}
    violations: list[str] = []
    for path in (BACKEND_ROOT / "app" / "api" / "routes").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            is_get = any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "get"
                for decorator in node.decorator_list
            )
            if not is_get:
                continue
            for item in ast.walk(node):
                if (
                    isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Attribute)
                    and isinstance(item.func.value, ast.Name)
                    and item.func.value.id == "db"
                    and item.func.attr in forbidden
                ):
                    violations.append(
                        f"{path.name}:{item.lineno}:{node.name}:{item.func.attr}"
                    )
    assert violations == []


def test_google_web_risk_clean_and_threat() -> None:
    payloads = [{}, {"threat": {"threatTypes": ["MALWARE", "SOCIAL_ENGINEERING"]}}]

    def handler(request: httpx.Request) -> httpx.Response:
        return _response(200, request, json=payloads.pop(0))

    provider = GoogleWebRiskProvider(enabled=True, api_key="test-key", client=_client(handler))
    target = ReputationTarget("https://public.test/path", "public.test")
    assert provider.check(target).verdict == "CLEAN"
    threat = provider.check(target)
    assert threat.verdict == "THREAT"
    assert threat.categories == ["MALWARE", "SOCIAL_ENGINEERING"]


@pytest.mark.parametrize(
    ("code", "category"),
    [
        (2002, "SPAM"),
        (2004, "PHISHING"),
        (2005, "MALWARE"),
        (2006, "BOTNET_C2"),
        (2105, "ABUSED_LEGITIMATE_MALWARE"),
    ],
)
def test_spamhaus_dbl_serious_categories(code: int, category: str) -> None:
    provider = SpamhausDqsProvider(
        enabled=True,
        api_key="test-key",
        client=_client(lambda request: _response(200, request, json={"resp": code})),
    )
    result = provider.check(ReputationTarget("https://public.test/", "public.test"))
    assert result.verdict == "THREAT"
    assert result.categories == [category]


def test_spamhaus_zrd_is_warning_not_threat() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/DBL/" in request.url.path:
            return _response(404, request)
        return _response(200, request, json={"resp": 3007})

    result = SpamhausDqsProvider(enabled=True, api_key="test-key", client=_client(handler)).check(
        ReputationTarget("https://public.test/", "public.test")
    )
    assert result.verdict == "LOW_REPUTATION"
    assert result.categories == ["ZERO_REPUTATION_DOMAIN"]


@pytest.mark.parametrize(
    "payload",
    [
        {"success": True, "unsafe": True, "risk_score": 10, "domain_trust": "trusted"},
        {"success": True, "phishing": True, "risk_score": 10, "domain_trust": "trusted"},
        {"success": True, "malware": True, "risk_score": 10, "domain_trust": "trusted"},
        {"success": True, "spamming": True, "risk_score": 10, "domain_trust": "trusted"},
        {"success": True, "risk_score": 85, "domain_trust": "trusted"},
        {"success": True, "parking": True, "risk_score": 10, "domain_trust": "trusted"},
    ],
)
def test_ipqs_serious_verdicts(payload: dict) -> None:
    provider = IPQualityScoreProvider(
        enabled=True,
        api_key="test-key",
        client=_client(lambda request: _response(200, request, json=payload)),
    )
    result = provider.check(ReputationTarget("https://public.test/", "public.test"))
    assert result.verdict == "THREAT"


def test_ipqs_new_domain_is_warning() -> None:
    created = int((datetime.now(UTC) - timedelta(days=3)).timestamp())
    payload = {
        "success": True,
        "risk_score": 15,
        "domain_trust": "new",
        "domain_age": {"timestamp": created},
    }
    provider = IPQualityScoreProvider(
        enabled=True,
        api_key="test-key",
        client=_client(lambda request: _response(200, request, json=payload)),
    )
    result = provider.check(ReputationTarget("https://public.test/", "public.test"))
    assert result.verdict == "LOW_REPUTATION"
    assert result.categories == ["NEW_DOMAIN"]


class _FakeProvider:
    def __init__(self, name: str, verdict: str = "CLEAN", *, failures: int = 0) -> None:
        self.name = name
        self.enabled = True
        self.verdict = verdict
        self.failures = failures
        self.calls = 0

    def check(self, _target: ReputationTarget) -> ProviderResult:
        self.calls += 1
        if self.calls <= self.failures:
            raise ProviderUnavailable("PROVIDER_TIMEOUT", {"provider": self.name})
        return ProviderResult(self.name, self.verdict)


def _config(enforcement: str = "monitor"):
    return SimpleNamespace(
        domain_reputation_enforcement=enforcement,
        domain_validation_timeout_seconds=1,
        domain_validation_max_parallel=4,
        domain_validation_cache_minutes=60,
        web_risk_enabled=False,
        web_risk_api_key=None,
        spamhaus_dqs_enabled=False,
        spamhaus_dqs_key=None,
        ipqs_enabled=False,
        ipqs_api_key=None,
    )


def test_missing_api_key_is_not_clean() -> None:
    provider = GoogleWebRiskProvider(
        enabled=True,
        api_key=None,
        client=_client(lambda request: _response(200, request)),
    )
    checker = ReputationChecker(providers=[provider], config=_config())
    result = checker.check("https://public.test/")
    assert result["status"] == "NOT_CONFIGURED"
    assert result["providers"][0]["verdict"] == "NOT_CONFIGURED"


def test_provider_timeout_is_retried_exactly_twice() -> None:
    provider = _FakeProvider("GOOGLE_WEB_RISK", failures=2)
    checker = ReputationChecker(providers=[provider], config=_config(), attempts=2)
    result = checker.check("https://public.test/")
    assert provider.calls == 2
    assert result["status"] == "CHECK_UNAVAILABLE"
    assert result["providers"][0]["attempts"] == 2


def test_provider_disagreement_serious_threat_wins() -> None:
    checker = ReputationChecker(
        providers=[
            _FakeProvider("GOOGLE_WEB_RISK", "CLEAN"),
            _FakeProvider("SPAMHAUS_DQS", "THREAT"),
            _FakeProvider("IPQUALITYSCORE", "CLEAN"),
        ],
        config=_config("block"),
    )
    result = checker.check("https://public.test/")
    assert result["status"] == "THREAT"
    assert result["blocking"] is True


def test_monitor_reports_threat_without_blocking() -> None:
    checker = ReputationChecker(
        providers=[
            _FakeProvider("GOOGLE_WEB_RISK", "THREAT"),
            _FakeProvider("SPAMHAUS_DQS", "CLEAN"),
        ],
        config=_config("monitor"),
    )
    result = checker.check("https://public.test/")
    assert result["status"] == "THREAT"
    assert result["would_block"] is True
    assert result["blocking"] is False


def test_block_mode_blocks_when_required_provider_failed_twice() -> None:
    checker = ReputationChecker(
        providers=[
            _FakeProvider("GOOGLE_WEB_RISK", failures=2),
            _FakeProvider("SPAMHAUS_DQS", "CLEAN"),
        ],
        config=_config("block"),
    )
    result = checker.check("https://public.test/")
    assert result["status"] == "CHECK_UNAVAILABLE"
    assert result["blocking"] is True


class _StaticAvailability:
    def __init__(self, failing_hosts: set[str] | None = None) -> None:
        self.failing_hosts = failing_hosts or set()
        self.calls = 0

    def check(self, value: str) -> dict:
        self.calls += 1
        domain = httpx.URL(value).host
        if domain in self.failing_hosts:
            return {
                "status": "UNAVAILABLE",
                "code": "HTTP_5XX",
                "params": {"domain": domain, "http_status": 500},
                "domain": domain,
                "checked_url": value,
                "final_url": value,
                "http_status": 500,
                "response_ms": 5,
                "attempts": 1,
            }
        return {
            "status": "WORKING",
            "code": "OK",
            "params": {},
            "domain": domain,
            "checked_url": value,
            "final_url": value,
            "http_status": 200,
            "response_ms": 5,
            "attempts": 1,
        }


class _StaticReputation:
    def __init__(self, threat_hosts: set[str] | None = None, enforcement: str = "block") -> None:
        self.threat_hosts = threat_hosts or set()
        self.enforcement = enforcement

    def check(self, value: str) -> dict:
        domain = httpx.URL(value).host
        threat = domain in self.threat_hosts
        return {
            "status": "THREAT" if threat else "CLEAN",
            "enforcement": self.enforcement,
            "blocking": threat and self.enforcement == "block",
            "would_block": threat,
            "required_providers_ready": True,
            "categories": ["PHISHING"] if threat else [],
            "providers": [],
            "checked_at": datetime.now(UTC).isoformat(),
        }


def test_identical_urls_are_checked_once_and_cache_is_reused() -> None:
    availability = _StaticAvailability()
    service = DomainValidationService(
        availability=availability,
        reputation=_StaticReputation(),
        config=_config("block"),
    )
    references = [
        {"url": "https://clean.test/path", "campaign_instance_id": "one"},
        {"url": "https://clean.test/path", "campaign_instance_id": "two"},
    ]
    first = service.validate(references)
    second = service.validate(references, cached_report=first)
    assert availability.calls == 1
    assert first["summary"]["urls"] == 1
    assert len(first["results"][0]["references"]) == 2
    assert second["results"][0]["cached"] is True


def test_mixed_package_filters_only_bad_campaigns() -> None:
    service = DomainValidationService(
        availability=_StaticAvailability(),
        reputation=_StaticReputation({"bad.test"}),
        config=_config("block"),
    )
    snapshot = {
        "campaigns": [
            {"campaign_instance_id": "good", "campaign_name": "Good", "final_url": "https://clean.test/"},
            {"campaign_instance_id": "bad", "campaign_name": "Bad", "final_url": "https://bad.test/"},
        ]
    }
    references = [
        {
            "url": item["final_url"],
            "campaign_instance_id": item["campaign_instance_id"],
        }
        for item in snapshot["campaigns"]
    ]
    report = service.validate(references)
    filtered, skipped = filter_blocked_campaigns(snapshot, report)
    assert [item["campaign_instance_id"] for item in filtered["campaigns"]] == ["good"]
    assert [item["campaign_instance_id"] for item in skipped] == ["bad"]
    assert skipped[0]["code"] == "DOMAIN_REPUTATION_THREAT"


def test_recovered_site_passes_forced_retry() -> None:
    availability = _StaticAvailability({"recover.test"})
    service = DomainValidationService(
        availability=availability,
        reputation=_StaticReputation(),
        config=_config("block"),
    )
    references = [{"url": "https://recover.test/path"}]
    failed = service.validate(references)
    availability.failing_hosts.clear()
    recovered = service.validate(references, cached_report=failed, force=True)
    assert failed["results"][0]["status"] == "UNAVAILABLE"
    assert recovered["results"][0]["status"] == "WORKING_CLEAN"
    assert recovered["results"][0]["blocking"] is False
