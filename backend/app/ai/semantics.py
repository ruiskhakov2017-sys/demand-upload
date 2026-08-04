from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

OPERATOR_ALIASES = {
    ">": "gt",
    "больше": "gt",
    "выше": "gt",
    "over": "gt",
    "greater than": "gt",
    ">=": "gte",
    "не меньше": "gte",
    "не менее": "gte",
    "at least": "gte",
    "<": "lt",
    "меньше": "lt",
    "ниже": "lt",
    "under": "lt",
    "less than": "lt",
    "<=": "lte",
    "не больше": "lte",
    "не более": "lte",
    "at most": "lte",
    "=": "eq",
    "равно": "eq",
    "equal": "eq",
    "без": "eq",
    "нет": "eq",
    "!=": "neq",
    "не равно": "neq",
    "not equal": "neq",
}

METRIC_ALIASES = {
    "расход": "cost_micros",
    "расходы": "cost_micros",
    "spend": "cost_micros",
    "cost": "cost_micros",
    "клики": "clicks",
    "кликов": "clicks",
    "clicks": "clicks",
    "показы": "impressions",
    "показов": "impressions",
    "impressions": "impressions",
    "конверсии": "conversions",
    "конверсий": "conversions",
    "conversions": "conversions",
    "регистрации": "registrations",
    "регистраций": "registrations",
    "registrations": "registrations",
    "депозиты": "deposits",
    "депозитов": "deposits",
    "deposits": "deposits",
}


@dataclass(frozen=True)
class NumericCondition:
    field: str
    operator: str
    value: Decimal


def parse_numeric_condition(text: str) -> NumericCondition | None:
    normalized = " ".join(text.casefold().replace(",", ".").split())
    metric_match = next(((alias, field) for alias, field in METRIC_ALIASES.items() if alias in normalized), None)
    if not metric_match:
        return None
    operator_match = next(
        (
            (alias, operator)
            for alias, operator in sorted(OPERATOR_ALIASES.items(), key=lambda item: -len(item[0]))
            if alias in normalized
        ),
        None,
    )
    if not operator_match:
        return None
    number = re.search(r"(?<![\w.])(\d+(?:\.\d+)?)\s*([kкmм]?)\b", normalized)
    if not number:
        if operator_match[0] in {"без", "нет"}:
            value = Decimal("0")
        else:
            return None
    else:
        value = Decimal(number.group(1))
        suffix = number.group(2)
        if suffix in {"k", "к"}:
            value *= 1_000
        elif suffix in {"m", "м"}:
            value *= 1_000_000
    field = metric_match[1]
    if field == "cost_micros":
        value *= 1_000_000
    return NumericCondition(field=field, operator=operator_match[1], value=value)


def group_currency_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        currency = str(row.get("currency_code") or "UNKNOWN").upper()
        target = grouped.setdefault(currency, {"currency_code": currency, "cost_micros": 0, "accounts": 0})
        target["accounts"] += 1
        cost = row.get("cost_micros")
        if cost is not None:
            target["cost_micros"] += int(cost)
    return [grouped[key] for key in sorted(grouped)]


def freshness_status(
    observed_at: datetime | None, *, now: datetime | None = None, stale_after: timedelta
) -> tuple[str, int | None]:
    if observed_at is None:
        return "MISSING", None
    current = now or datetime.now(UTC)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)
    age = max(0, int((current.astimezone(UTC) - observed_at.astimezone(UTC)).total_seconds()))
    return ("STALE" if age > int(stale_after.total_seconds()) else "FRESH"), age


def evidence_confidence(*, freshness: str, completeness: str, source_count: int, conflicting: bool = False) -> float:
    score = Decimal("0.95")
    if source_count <= 0:
        return 0.0
    if freshness in {"STALE", "UNKNOWN"}:
        score -= Decimal("0.20")
    if freshness == "MISSING":
        score -= Decimal("0.45")
    if completeness != "COMPLETE":
        score -= Decimal("0.25")
    if conflicting:
        score -= Decimal("0.25")
    if source_count == 1:
        score -= Decimal("0.05")
    return float(max(Decimal("0"), min(Decimal("1"), score)))


def local_day_bounds(day: date, time_zone: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(time_zone)
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return start.astimezone(UTC), end.astimezone(UTC)


def resolve_profile_precedence(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    priority = {"CAMPAIGN": 0, "ACCOUNT": 1, "MCC": 2, "GEO": 3, "GLOBAL": 4}
    active = [item for item in candidates if item.get("is_active", True)]
    if not active:
        return None
    return min(active, key=lambda item: (priority.get(str(item.get("scope_type")), 99), -int(item.get("version", 1))))
