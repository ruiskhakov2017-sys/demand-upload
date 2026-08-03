from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.control_center.service import with_derived_metrics

SORT_FIELDS = {
    "name": "display_name",
    "customer_id": "customer_id",
    "geo": "geo.display_name",
    "mcc": "mcc_name",
    "work_status": "work_status",
    "activity_status": "activity_status",
    "google_status": "google_status",
    "currency_code": "currency_code",
    "cost": "metrics.cost_micros",
    "cost_micros": "metrics.cost_micros",
    "budget": "metrics.budget_micros",
    "budget_micros": "metrics.budget_micros",
    "impressions": "metrics.impressions",
    "clicks": "metrics.clicks",
    "ctr": "metrics.ctr",
    "cpc": "metrics.cpc_micros",
    "cpc_micros": "metrics.cpc_micros",
    "conversions": "metrics.conversions",
    "all_conversions": "metrics.all_conversions",
    "registrations": "metrics.registrations",
    "deposits": "metrics.deposits",
    "cpa_registration": "metrics.cpa_registration_micros",
    "cpa_deposit": "metrics.cpa_deposit_micros",
    "registration_rate": "metrics.registration_rate",
    "registration_to_deposit_rate": "metrics.registration_to_deposit_rate",
    "conversion_value": "metrics.conversion_value",
    "roas": "metrics.roas",
    "active_campaigns": "metrics.active_campaigns",
    "disapproved_ads": "metrics.disapproved_ads",
    "last_sync_success_at": "last_sync_success_at",
    "problem_count": "active_problem_count",
}


def apply_account_filters(rows: list[dict], filters: dict[str, Any]) -> list[dict]:
    result = []
    for row in rows:
        metrics = row.get("metrics") or {}
        activity_status = str(filters.get("activity_status") or "").upper()
        if activity_status and row.get("activity_status") != activity_status:
            continue
        has_problems = filters.get("has_problems")
        if has_problems is not None and bool(row.get("has_problem")) is not has_problems:
            continue
        problem_type = str(filters.get("problem_type") or "")
        if problem_type and problem_type not in (row.get("problem_types") or []):
            continue
        if not _passes_bound(metrics.get("cost_micros"), filters, "cost"):
            continue
        if not _passes_bound(metrics.get("registrations"), filters, "registrations"):
            continue
        if not _passes_bound(metrics.get("deposits"), filters, "deposits"):
            continue
        if not _passes_bound(metrics.get("cpa_registration_micros"), filters, "cpa"):
            continue
        if not _passes_bound(metrics.get("active_campaigns"), filters, "active_campaigns"):
            continue
        if not _passes_bound(metrics.get("disapproved_ads"), filters, "disapproved_ads"):
            continue
        if filters.get("registrations_without_deposits"):
            registrations = metrics.get("registrations")
            deposits = metrics.get("deposits")
            if registrations in (None, 0) or deposits != 0:
                continue
        result.append(row)
    return result


def sort_account_rows(
    rows: list[dict],
    sort_fields: list[str],
    directions: list[str],
) -> list[dict]:
    result = list(rows)
    normalized_fields = [field for field in sort_fields if field in SORT_FIELDS] or ["name"]
    normalized_directions = [value.lower() if value.lower() in {"asc", "desc"} else "asc" for value in directions]
    while len(normalized_directions) < len(normalized_fields):
        normalized_directions.append(normalized_directions[-1] if normalized_directions else "asc")
    for field, direction in reversed(list(zip(normalized_fields, normalized_directions, strict=False))):
        path = SORT_FIELDS[field]
        present = [row for row in result if _nested(row, path) is not None]
        missing = [row for row in result if _nested(row, path) is None]
        present.sort(
            key=lambda row: _sortable(_nested(row, path)),
            reverse=direction == "desc",
        )
        result = [*present, *missing]
    return result


def group_account_rows(rows: list[dict], grouping: str) -> list[dict]:
    if grouping not in {"geo", "mcc", "geo_mcc"}:
        return []
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        geo = row.get("geo") or {}
        if grouping == "geo":
            key = (
                geo.get("id") or "UNASSIGNED",
                geo.get("display_name") or "GEO не назначено",
            )
        elif grouping == "mcc":
            key = (
                row.get("primary_mcc_id") or "NO_MCC",
                row.get("mcc_name") or row.get("mcc_customer_id") or "MCC не определён",
            )
        else:
            key = (
                geo.get("id") or "UNASSIGNED",
                geo.get("display_name") or "GEO не назначено",
                row.get("primary_mcc_id") or "NO_MCC",
                row.get("mcc_name") or row.get("mcc_customer_id") or "MCC не определён",
            )
        grouped[key].append(row)
    return [_group_payload(grouping, key, items) for key, items in sorted(grouped.items(), key=lambda item: item[0])]


def sort_groups(
    groups: list[dict],
    sort_fields: list[str],
    directions: list[str],
) -> list[dict]:
    rows = []
    for group in groups:
        rows.append(
            {
                **group,
                "display_name": group["label"],
                "metrics": group["metrics"],
            }
        )
    return sort_account_rows(rows, sort_fields, directions)


def _passes_bound(value: Any, filters: dict[str, Any], prefix: str) -> bool:
    minimum = filters.get(f"{prefix}_min")
    maximum = filters.get(f"{prefix}_max")
    equal = filters.get(f"{prefix}_eq")
    if minimum is not None and (value is None or value <= minimum):
        return False
    if maximum is not None and (value is None or value >= maximum):
        return False
    if equal is not None and value != equal:
        return False
    return True


def _nested(payload: dict, path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _sortable(value: Any) -> Any:
    return value.casefold() if isinstance(value, str) else value


def _group_payload(grouping: str, key: tuple, rows: list[dict]) -> dict:
    if grouping == "geo":
        group_id, label = key
        geo_id = group_id
        mcc_id = None
    elif grouping == "mcc":
        group_id, label = key
        geo_id = None
        mcc_id = group_id
    else:
        geo_id, geo_label, mcc_id, mcc_label = key
        group_id = f"{geo_id}:{mcc_id}"
        label = f"{geo_label} · {mcc_label}"
    metrics = _aggregate_metrics(rows)
    currency_totals = metrics.pop("currency_totals")
    mixed_currencies = metrics.pop("mixed_currencies")
    return {
        "id": str(group_id),
        "label": label,
        "grouping": grouping,
        "geo_id": str(geo_id) if geo_id else None,
        "mcc_id": str(mcc_id) if mcc_id else None,
        "accounts": len(rows),
        "working_accounts": sum(row.get("work_status") == "WORKING" for row in rows),
        "problem_accounts": sum(bool(row.get("has_problem")) for row in rows),
        "metrics": metrics,
        "currency_totals": currency_totals,
        "mixed_currencies": mixed_currencies,
        "items": rows,
    }


def _aggregate_metrics(rows: list[dict]) -> dict:
    metric_names = (
        "impressions",
        "clicks",
        "conversions",
        "all_conversions",
        "registrations",
        "deposits",
        "conversion_value",
        "active_campaigns",
        "disapproved_ads",
    )
    result: dict[str, Any] = {}
    for name in metric_names:
        values = [
            (row.get("metrics") or {}).get(name) for row in rows if (row.get("metrics") or {}).get(name) is not None
        ]
        result[name] = sum(values) if values else None
    result["registration_data_available"] = any(
        bool((row.get("metrics") or {}).get("registration_data_available")) for row in rows
    )
    result["deposit_data_available"] = any(
        bool((row.get("metrics") or {}).get("deposit_data_available")) for row in rows
    )
    currency_totals: dict[str, int] = defaultdict(int)
    for row in rows:
        cost = (row.get("metrics") or {}).get("cost_micros")
        if cost is None:
            continue
        currency_totals[row.get("currency_code") or "UNKNOWN"] += int(cost)
    result["currency_totals"] = [
        {"currency_code": currency, "cost_micros": value} for currency, value in sorted(currency_totals.items())
    ]
    result["mixed_currencies"] = len(currency_totals) > 1
    result["cost_micros"] = next(iter(currency_totals.values())) if len(currency_totals) == 1 else None
    return with_derived_metrics(result)
