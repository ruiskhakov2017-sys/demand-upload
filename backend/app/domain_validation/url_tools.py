from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_KEYS = {
    "_ga",
    "_gl",
    "campaignid",
    "dclid",
    "fbclid",
    "gbraid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "msclkid",
    "ref",
    "referrer",
    "srsltid",
    "wbraid",
    "yclid",
}
TRACKING_PREFIXES = ("utm_", "pk_", "mtm_")


def normalized_url(value: str) -> str:
    return str(value or "").strip()


def url_fingerprint(value: str) -> str:
    return hashlib.sha256(normalized_url(value).encode("utf-8")).hexdigest()


def safe_url_for_storage(value: str) -> str:
    """Remove fragments and common tracking values before persistence or provider calls."""
    raw = normalized_url(value)
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw.split("#", 1)[0]
    filtered = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_key(key)
    ]
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port:
        host = f"{host}:{port}"
    return urlunsplit((parsed.scheme.lower(), host.lower(), parsed.path or "/", urlencode(filtered), ""))


def domain_from_url(value: str) -> str:
    try:
        return (urlsplit(normalized_url(value)).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _is_tracking_key(key: str) -> bool:
    normalized = key.strip().lower()
    return normalized in TRACKING_KEYS or normalized.startswith(TRACKING_PREFIXES)
