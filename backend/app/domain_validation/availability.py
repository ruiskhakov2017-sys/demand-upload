from __future__ import annotations

import ipaddress
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.config import settings
from app.domain_validation.url_tools import domain_from_url, normalized_url, safe_url_for_storage

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
GET_FALLBACK_STATUSES = {405, 501}
METADATA_HOSTS = {
    "169.254.169.254",
    "100.100.100.200",
    "metadata.google.internal",
    "metadata.google.internal.",
    "instance-data",
    "instance-data.",
}


@dataclass(frozen=True)
class AvailabilityFailure(Exception):
    code: str
    params: dict
    retryable: bool = False


Resolver = Callable[[str, int], list[str]]


class AvailabilityChecker:
    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        resolver: Resolver | None = None,
        timeout_seconds: float | None = None,
        max_redirects: int | None = None,
        attempts: int = 2,
    ) -> None:
        timeout = timeout_seconds or settings.domain_validation_timeout_seconds
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": "DemandGenUploader-DomainValidator/1.0"},
        )
        self.resolver = resolver or _resolve_public_addresses
        self.max_redirects = max_redirects or settings.domain_validation_max_redirects
        self.attempts = max(1, min(attempts, 2))

    def check(self, value: str) -> dict:
        url = normalized_url(value)
        started = time.perf_counter()
        last_failure: AvailabilityFailure | None = None
        for attempt in range(1, self.attempts + 1):
            try:
                result = self._check_once(url)
                result["attempts"] = attempt
                result["response_ms"] = round((time.perf_counter() - started) * 1000)
                return result
            except AvailabilityFailure as exc:
                last_failure = exc
                if not exc.retryable or attempt >= self.attempts:
                    break
        assert last_failure is not None
        return {
            "status": "UNAVAILABLE",
            "code": last_failure.code,
            "params": last_failure.params,
            "domain": domain_from_url(url),
            "checked_url": safe_url_for_storage(url),
            "final_url": None,
            "http_status": last_failure.params.get("http_status"),
            "response_ms": round((time.perf_counter() - started) * 1000),
            "attempts": attempt,
        }

    def _check_once(self, url: str) -> dict:
        self._validate_destination(url)
        current = url
        visited: set[str] = set()
        method = "HEAD"
        redirects = 0
        while True:
            if current in visited:
                raise AvailabilityFailure("REDIRECT_LOOP", {"domain": domain_from_url(current)})
            visited.add(current)
            self._validate_destination(current)
            response = self._request(method, current)
            if method == "HEAD" and response.status_code in GET_FALLBACK_STATUSES:
                method = "GET"
                response = self._request(method, current)
            if response.status_code in REDIRECT_STATUSES:
                location = response.headers.get("location")
                if not location:
                    raise AvailabilityFailure(
                        "REDIRECT_MISSING_LOCATION",
                        {"domain": domain_from_url(current), "http_status": response.status_code},
                    )
                redirects += 1
                if redirects > self.max_redirects:
                    raise AvailabilityFailure(
                        "TOO_MANY_REDIRECTS",
                        {"domain": domain_from_url(current), "max_redirects": self.max_redirects},
                    )
                try:
                    redirected = urljoin(current, location)
                    self._validate_destination(redirected)
                except (ValueError, AvailabilityFailure) as exc:
                    if isinstance(exc, AvailabilityFailure):
                        raise
                    raise AvailabilityFailure("INVALID_REDIRECT", {"domain": domain_from_url(current)}) from exc
                current = redirected
                continue
            if 200 <= response.status_code <= 399:
                return {
                    "status": "WORKING",
                    "code": "OK",
                    "params": {},
                    "domain": domain_from_url(url),
                    "checked_url": safe_url_for_storage(url),
                    "final_url": safe_url_for_storage(current),
                    "http_status": response.status_code,
                    "redirects": redirects,
                }
            code = "HTTP_4XX" if response.status_code < 500 else "HTTP_5XX"
            raise AvailabilityFailure(
                code,
                {"domain": domain_from_url(url), "http_status": response.status_code},
            )

    def _request(self, method: str, url: str) -> httpx.Response:
        headers = {"Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1"}
        if method == "GET":
            headers["Range"] = "bytes=0-0"
        try:
            request = self.client.build_request(method, url, headers=headers)
            response = self.client.send(request, stream=True)
            response.close()
            return response
        except httpx.TimeoutException as exc:
            raise AvailabilityFailure("TIMEOUT", {"domain": domain_from_url(url)}, retryable=True) from exc
        except httpx.ConnectError as exc:
            message = str(exc).lower()
            code = (
                "TLS_ERROR"
                if any(token in message for token in ("ssl", "tls", "certificate"))
                else "CONNECTION_ERROR"
            )
            raise AvailabilityFailure(code, {"domain": domain_from_url(url)}, retryable=True) from exc
        except httpx.TransportError as exc:
            raise AvailabilityFailure(
                "CONNECTION_ERROR",
                {"domain": domain_from_url(url)},
                retryable=True,
            ) from exc
        except (UnicodeError, ValueError) as exc:
            raise AvailabilityFailure("INVALID_URL", {"domain": domain_from_url(url)}) from exc

    def _validate_destination(self, value: str) -> None:
        if not value:
            raise AvailabilityFailure("EMPTY_URL", {"domain": ""})
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise AvailabilityFailure("INVALID_URL", {"domain": ""}) from exc
        if parsed.scheme.lower() not in {"http", "https"}:
            raise AvailabilityFailure("UNSUPPORTED_SCHEME", {"scheme": parsed.scheme.lower(), "domain": ""})
        if not parsed.hostname:
            raise AvailabilityFailure("INVALID_URL", {"domain": ""})
        if parsed.username is not None or parsed.password is not None:
            raise AvailabilityFailure("CREDENTIALS_IN_URL", {"domain": parsed.hostname.lower()})
        host = parsed.hostname.lower().rstrip(".")
        if host == "localhost" or host.endswith(".localhost") or host in METADATA_HOSTS:
            raise AvailabilityFailure("SSRF_BLOCKED", {"domain": host, "reason": "forbidden_host"})
        try:
            literal_ip = ipaddress.ip_address(host.split("%", 1)[0])
        except ValueError:
            literal_ip = None
        if literal_ip is not None and not literal_ip.is_global:
            raise AvailabilityFailure("SSRF_BLOCKED", {"domain": host, "reason": "non_public_ip"})
        try:
            addresses = self.resolver(host, port or (443 if parsed.scheme.lower() == "https" else 80))
        except socket.gaierror as exc:
            raise AvailabilityFailure("DNS_ERROR", {"domain": host}, retryable=True) from exc
        except OSError as exc:
            raise AvailabilityFailure("DNS_ERROR", {"domain": host}, retryable=True) from exc
        if not addresses:
            raise AvailabilityFailure("DNS_ERROR", {"domain": host}, retryable=True)
        for address in addresses:
            try:
                parsed_ip = ipaddress.ip_address(address.split("%", 1)[0])
            except ValueError as exc:
                raise AvailabilityFailure("DNS_ERROR", {"domain": host}, retryable=True) from exc
            if not parsed_ip.is_global:
                raise AvailabilityFailure("SSRF_BLOCKED", {"domain": host, "reason": "non_public_ip"})


def _resolve_public_addresses(host: str, port: int) -> list[str]:
    try:
        literal = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        literal = None
    if literal is not None:
        return [str(literal)]
    records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(record[4][0]) for record in records})
