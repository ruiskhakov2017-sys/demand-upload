from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import UTC, datetime, timedelta

from app.core.config import Settings, settings
from app.domain_validation.availability import AvailabilityChecker
from app.domain_validation.reputation import ReputationChecker
from app.domain_validation.url_tools import domain_from_url, normalized_url, safe_url_for_storage, url_fingerprint

FINAL_URL_KEYS = {"final_url", "final_urls", "finalurl", "finalurls"}


class DomainValidationService:
    def __init__(
        self,
        *,
        availability: AvailabilityChecker | None = None,
        reputation: ReputationChecker | None = None,
        config: Settings = settings,
    ) -> None:
        self.config = config
        self.availability = availability or AvailabilityChecker()
        self.reputation = reputation or ReputationChecker(config=config)

    def validate(
        self,
        references: list[dict],
        *,
        cached_report: dict | None = None,
        force: bool = False,
    ) -> dict:
        started = datetime.now(UTC)
        grouped = _group_references(references)
        cached = {
            item.get("url_hash"): item
            for item in (cached_report or {}).get("results") or []
            if _cache_valid(item, started)
        }
        results: list[dict] = []
        pending: dict = {}
        for url_hash, item in grouped.items():
            if not force and url_hash in cached:
                reused = deepcopy(cached[url_hash])
                reused["references"] = item["references"]
                reused["cached"] = True
                results.append(reused)
            else:
                pending[url_hash] = item
        with ThreadPoolExecutor(max_workers=self.config.domain_validation_max_parallel) as executor:
            futures = {
                executor.submit(self._validate_one, item["url"], item["references"]): key
                for key, item in pending.items()
            }
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda item: (item.get("domain") or "", item.get("checked_url") or ""))
        completed = datetime.now(UTC)
        blocking = [item for item in results if item.get("blocking")]
        warnings = [item for item in results if item.get("warning")]
        domains = {item.get("domain") for item in results if item.get("domain")}
        return {
            "status": "COMPLETED",
            "fresh": force,
            "enforcement": self.config.domain_reputation_enforcement,
            "checked_at": completed.isoformat(),
            "duration_ms": round((completed - started).total_seconds() * 1000),
            "summary": {
                "urls": len(results),
                "domains": len(domains),
                "working": sum(item.get("availability", {}).get("status") == "WORKING" for item in results),
                "blocked": len(blocking),
                "warnings": len(warnings),
            },
            "results": results,
        }

    def _validate_one(self, value: str, references: list[dict]) -> dict:
        checked_at = datetime.now(UTC)
        availability = self.availability.check(value)
        if availability.get("code") in {
            "EMPTY_URL",
            "INVALID_URL",
            "UNSUPPORTED_SCHEME",
            "CREDENTIALS_IN_URL",
            "SSRF_BLOCKED",
        }:
            reputation = {
                "status": "NOT_CHECKED",
                "enforcement": self.config.domain_reputation_enforcement,
                "blocking": False,
                "would_block": False,
                "required_providers_ready": False,
                "categories": [],
                "providers": [],
                "checked_at": None,
            }
        else:
            reputation = self.reputation.check(value)
        if availability["status"] != "WORKING":
            status = "UNAVAILABLE"
            blocking = True
            warning = False
            code = availability["code"]
            params = availability.get("params") or {}
        else:
            reputation_status = reputation["status"]
            status = {
                "CLEAN": "WORKING_CLEAN",
                "THREAT": "THREAT",
                "LOW_REPUTATION": "LOW_REPUTATION",
                "CHECK_UNAVAILABLE": "CHECK_UNAVAILABLE",
                "NOT_CONFIGURED": "REPUTATION_NOT_CONFIGURED",
            }.get(reputation_status, "CHECK_UNAVAILABLE")
            blocking = bool(reputation.get("blocking"))
            warning = status in {
                "LOW_REPUTATION",
                "CHECK_UNAVAILABLE",
                "REPUTATION_NOT_CONFIGURED",
            } or bool(reputation.get("would_block") and not blocking)
            code = {
                "THREAT": "DOMAIN_REPUTATION_THREAT",
                "LOW_REPUTATION": "DOMAIN_LOW_REPUTATION",
                "CHECK_UNAVAILABLE": "DOMAIN_REPUTATION_UNAVAILABLE",
                "REPUTATION_NOT_CONFIGURED": "DOMAIN_REPUTATION_NOT_CONFIGURED",
            }.get(status, "OK")
            params = {
                "domain": availability["domain"],
                "categories": reputation.get("categories") or [],
                "enforcement": reputation.get("enforcement"),
            }
        return {
            "url_hash": url_fingerprint(value),
            "domain": availability.get("domain") or domain_from_url(value),
            "checked_url": safe_url_for_storage(value),
            "status": status,
            "code": code,
            "params": params,
            "blocking": blocking,
            "warning": warning,
            "cached": False,
            "checked_at": checked_at.isoformat(),
            "expires_at": (
                checked_at + timedelta(minutes=self.config.domain_validation_cache_minutes)
            ).isoformat(),
            "availability": availability,
            "reputation": reputation,
            "references": references,
        }

    @staticmethod
    def pending(references: list[dict], previous: dict | None = None) -> dict:
        now = datetime.now(UTC).isoformat()
        previous_by_hash = {
            item.get("url_hash"): item for item in (previous or {}).get("results") or []
        }
        results = []
        for url_hash, item in _group_references(references).items():
            prior = previous_by_hash.get(url_hash)
            results.append(
                {
                    "url_hash": url_hash,
                    "domain": domain_from_url(item["url"]),
                    "checked_url": safe_url_for_storage(item["url"]),
                    "status": "RECHECK_REQUIRED" if prior else "PENDING",
                    "code": "DOMAIN_RECHECK_REQUIRED" if prior else "DOMAIN_CHECK_PENDING",
                    "params": {"domain": domain_from_url(item["url"])},
                    "blocking": True,
                    "warning": False,
                    "cached": False,
                    "checked_at": prior.get("checked_at") if prior else None,
                    "expires_at": prior.get("expires_at") if prior else None,
                    "availability": prior.get("availability", {}) if prior else {},
                    "reputation": prior.get("reputation", {}) if prior else {},
                    "references": item["references"],
                }
            )
        return {
            "status": "PENDING",
            "fresh": False,
            "enforcement": settings.domain_reputation_enforcement,
            "checked_at": now,
            "summary": {
                "urls": len(results),
                "domains": len({item["domain"] for item in results if item["domain"]}),
                "working": 0,
                "blocked": len(results),
                "warnings": 0,
            },
            "results": results,
        }


def extract_final_url_references(value: object, *, source: str = "upload") -> list[dict]:
    found: list[dict] = []

    def walk(item: object, path: str) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                normalized_key = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
                next_path = f"{path}.{key}" if path else str(key)
                if normalized_key in FINAL_URL_KEYS:
                    values = nested if isinstance(nested, list) else [nested]
                    for candidate in values:
                        if isinstance(candidate, str) and candidate.strip():
                            found.append(
                                {
                                    "url": normalized_url(candidate),
                                    "source": source,
                                    "path": next_path,
                                }
                            )
                else:
                    walk(nested, next_path)
        elif isinstance(item, list):
            for index, nested in enumerate(item):
                walk(nested, f"{path}.{index}")

    walk(value, "")
    return found


def snapshot_url_references(snapshot: dict) -> list[dict]:
    references = []
    for index, campaign in enumerate(snapshot.get("campaigns") or []):
        value = normalized_url(campaign.get("final_url") or "")
        if not value:
            continue
        references.append(
            {
                "url": value,
                "source": "plan",
                "path": f"campaigns.{index}.final_url",
                "campaign_index": index,
                "campaign_instance_id": campaign.get("campaign_instance_id"),
                "campaign_name": campaign.get("campaign_name"),
            }
        )
    return references


def filter_blocked_campaigns(snapshot: dict, report: dict) -> tuple[dict, list[dict]]:
    blocked_hashes = {
        item["url_hash"]: item for item in report.get("results") or [] if item.get("blocking")
    }
    allowed = deepcopy(snapshot)
    kept: list[dict] = []
    skipped: list[dict] = []
    for index, campaign in enumerate(allowed.get("campaigns") or []):
        result = blocked_hashes.get(url_fingerprint(str(campaign.get("final_url") or "")))
        if result:
            skipped.append(
                {
                    "ok": False,
                    "skipped": True,
                    "campaign_index": index,
                    "campaign_instance_id": campaign.get("campaign_instance_id"),
                    "campaign_name": campaign.get("campaign_name"),
                    "domain": result.get("domain"),
                    "code": result.get("code"),
                    "params": result.get("params") or {},
                    "request_ids": [],
                    "resource_names": [],
                }
            )
        else:
            kept.append(campaign)
    allowed["campaigns"] = kept
    allowed["domain_validation"] = report
    return allowed, skipped


def merge_domain_skips(result, skipped: list[dict], report: dict):
    if not skipped:
        details = {**(result.details or {}), "domain_validation": report}
        return result.__class__(
            ok=result.ok,
            mode=result.mode,
            errors=result.errors,
            warnings=result.warnings,
            request_ids=result.request_ids,
            resource_names=result.resource_names,
            details=details,
        )
    rows = []
    for item in skipped:
        rows.append(
            {
                **item,
                "errors": [
                    {
                        "code": item["code"],
                        "message": item["code"],
                        "params": item.get("params") or {},
                    }
                ],
                "warnings": [],
            }
        )
    details = {
        **(result.details or {}),
        "instances": [*((result.details or {}).get("instances") or []), *rows],
        "domain_validation": report,
        "domain_skipped": len(rows),
    }
    return result.__class__(
        ok=result.ok,
        mode=result.mode,
        errors=result.errors,
        warnings=[
            *result.warnings,
            {
                "code": "DOMAIN_ITEMS_SKIPPED",
                "message": "DOMAIN_ITEMS_SKIPPED",
                "params": {"count": len(rows)},
            },
        ],
        request_ids=result.request_ids,
        resource_names=result.resource_names,
        details=details,
    )


def blocked_execution_result(mode: str, skipped: list[dict], report: dict):
    from app.google_ads.interface import PlanExecutionResult

    errors = [
        {
            "code": item["code"],
            "message": item["code"],
            "params": item.get("params") or {},
        }
        for item in skipped
    ]
    empty = PlanExecutionResult(
        ok=False,
        mode=mode,
        errors=errors or [{"code": "DOMAIN_VALIDATION_BLOCKED", "message": "DOMAIN_VALIDATION_BLOCKED"}],
        warnings=[],
        request_ids=[],
        resource_names=[],
        details={"validate_only": False, "google_contacted": False, "instances": []},
    )
    return merge_domain_skips(empty, skipped, report)


def _group_references(references: list[dict]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for reference in references:
        url = normalized_url(reference.get("url") or "")
        if not url:
            continue
        key = url_fingerprint(url)
        grouped.setdefault(key, {"url": url, "references": []})
        safe_reference = {key: value for key, value in reference.items() if key != "url"}
        if safe_reference not in grouped[key]["references"]:
            grouped[key]["references"].append(safe_reference)
    return grouped


def _cache_valid(item: dict, now: datetime) -> bool:
    try:
        expires = datetime.fromisoformat(str(item.get("expires_at") or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires > now and item.get("status") not in {"PENDING", "CHECKING", "RECHECK_REQUIRED"}
