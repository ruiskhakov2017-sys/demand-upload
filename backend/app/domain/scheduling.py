from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEDULE_MODES = {"IMMEDIATE", "EVEN", "WAVES", "MANUAL"}
TRANSIENT_ERROR_CODES = {
    "RESOURCE_EXHAUSTED",
    "RESOURCE_TEMPORARILY_EXHAUSTED",
    "UNAVAILABLE",
    "INTERNAL",
    "DEADLINE_EXCEEDED",
    "ABORTED",
}
FATAL_ERROR_CODES = {
    "UNAUTHENTICATED",
    "PERMISSION_DENIED",
    "DEVELOPER_TOKEN_NOT_APPROVED",
    "DEVELOPER_TOKEN_PROHIBITED",
    "MCC_ACCESS_LOST",
    "PLAN_FINGERPRINT_MISMATCH",
    "MEDIA_NOT_READY",
    "ASSET_MISSING",
    "CONNECTION_UNAVAILABLE",
}


class ScheduleValidationError(ValueError):
    pass


def local_to_utc(value: str | datetime | None, time_zone: str, *, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        zone = ZoneInfo(time_zone)
    except ZoneInfoNotFoundError as exc:
        raise ScheduleValidationError(f"Неизвестный часовой пояс: {time_zone}") from exc
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ScheduleValidationError(f"Некорректная дата в поле {field}") from exc
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return parsed.astimezone(UTC)


def build_schedule_preview(
    accounts: list[dict],
    config: dict,
    *,
    now: datetime | None = None,
) -> dict:
    now = _utc(now or datetime.now(UTC))
    mode = str(config.get("mode") or "IMMEDIATE").upper()
    if mode not in SCHEDULE_MODES:
        raise ScheduleValidationError("Неизвестный режим расписания")
    if not accounts:
        raise ScheduleValidationError("В Launch Batch нет аккаунтов")

    time_zone = str(config.get("time_zone") or "UTC")
    local_to_utc(now, time_zone, field="time_zone")
    ordered = _ordered_accounts(accounts, config.get("account_order") or [])
    hourly_limit = _positive_int(config.get("max_accounts_per_hour"), 50, "Лимит аккаунтов в час")
    daily_limit = _positive_int(config.get("max_accounts_per_day"), 500, "Лимит аккаунтов в сутки")
    max_parallel = _positive_int(config.get("max_parallel"), 1, "Максимальная параллельность")
    circuit_threshold = _positive_int(
        config.get("circuit_breaker_threshold"),
        2,
        "Порог аварийной остановки",
    )

    warnings: list[dict] = []
    unassigned: list[dict] = []
    if mode == "IMMEDIATE":
        desired = [(account, 1, now) for account in ordered]
        desired = _apply_rate_limits(desired, hourly_limit, daily_limit)
        waves = [{"wave_number": 1, "approval_required": False, "observation_until": None}]
    elif mode == "EVEN":
        start_at = local_to_utc(config.get("start_local") or config.get("start_at"), time_zone, field="start")
        end_at = local_to_utc(config.get("end_local") or config.get("end_at"), time_zone, field="end")
        if not start_at:
            raise ScheduleValidationError("Укажите начало равномерного расписания")
        if not end_at:
            duration = _positive_int(config.get("duration_minutes"), 0, "Продолжительность")
            end_at = start_at + timedelta(minutes=duration)
        if end_at <= start_at:
            raise ScheduleValidationError("Окончание должно быть позже начала")
        interval = (end_at - start_at) / len(ordered)
        desired = [(account, 1, start_at + interval * index) for index, account in enumerate(ordered)]
        limited = _apply_rate_limits(desired, hourly_limit, daily_limit)
        if limited[-1][2] > end_at:
            warnings.append(
                _warning(
                    "LIMIT_EXTENDS_WINDOW",
                    "Из-за лимитов последний аккаунт перенесён за выбранное время окончания",
                )
            )
        desired = limited
        waves = [{"wave_number": 1, "approval_required": False, "observation_until": None}]
    elif mode == "WAVES":
        desired, waves = _build_waves(ordered, config, time_zone, now)
        limited = _apply_rate_limits(desired, hourly_limit, daily_limit)
        if [item[2] for item in limited] != [item[2] for item in desired]:
            warnings.append(
                _warning(
                    "RATE_LIMIT_ADJUSTMENT",
                    "Часть запусков сдвинута, чтобы соблюсти лимиты в час и сутки",
                )
            )
        desired = limited
    else:
        desired, waves, unassigned = _build_manual(ordered, config, time_zone)
        conflicts = rate_limit_conflicts([item[2] for item in desired], hourly_limit, daily_limit)
        if conflicts:
            warnings.append(
                _warning(
                    "MANUAL_RATE_CONFLICT",
                    f"Ручное расписание содержит конфликтов с лимитами: {len(conflicts)}",
                )
            )

    if unassigned:
        warnings.append(
            _warning(
                "UNASSIGNED_ACCOUNTS",
                f"Без времени осталось аккаунтов: {len(unassigned)}",
            )
        )
    runs = []
    for position, (account, wave_number, scheduled_for) in enumerate(desired, start=1):
        budget_micros = int(account.get("budget_micros") or account.get("total_budget_micros") or 0)
        runs.append(
            {
                "account_test_bundle_id": str(account["id"]),
                "customer_id": str(account["customer_id"]),
                "account_name": str(account.get("account_name") or account["customer_id"]),
                "campaigns_count": int(account.get("campaigns_count") or 0),
                "budget_micros": budget_micros,
                "wave_number": wave_number,
                "position": position,
                "scheduled_for": _utc(scheduled_for).isoformat(),
                "deployment_key": _deployment_key(account),
            }
        )

    wave_rows = _summarize_waves(runs, waves)
    total_campaigns = sum(item["campaigns_count"] for item in runs)
    start_at = min((_parse_utc(item["scheduled_for"]) for item in runs), default=now)
    end_at = max((_parse_utc(item["scheduled_for"]) for item in runs), default=now)
    normalized_config = {
        **config,
        "mode": mode,
        "time_zone": time_zone,
        "max_accounts_per_hour": hourly_limit,
        "max_accounts_per_day": daily_limit,
        "max_parallel": max_parallel,
        "circuit_breaker_threshold": circuit_threshold,
        "manual_approval": bool(config.get("manual_approval", True)),
    }
    snapshot = {
        "schema_version": 1,
        "mode": mode,
        "time_zone": time_zone,
        "config": normalized_config,
        "runs": runs,
        "waves": wave_rows,
    }
    fingerprint = schedule_fingerprint(snapshot)
    return {
        **snapshot,
        "fingerprint": fingerprint,
        "valid": not unassigned,
        "warnings": warnings,
        "unassigned_accounts": unassigned,
        "summary": {
            "accounts": len(runs),
            "campaigns": total_campaigns,
            "waves": len(wave_rows),
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "max_accounts_per_hour": hourly_limit,
            "max_accounts_per_day": daily_limit,
            "max_parallel": max_parallel,
            "circuit_breaker_threshold": circuit_threshold,
            "unassigned_accounts": len(unassigned),
            "warnings": len(warnings),
        },
    }


def schedule_fingerprint(snapshot: dict) -> str:
    material = {
        "schema_version": snapshot.get("schema_version"),
        "mode": snapshot.get("mode"),
        "time_zone": snapshot.get("time_zone"),
        "config": snapshot.get("config") or {},
        "runs": snapshot.get("runs") or [],
        "waves": snapshot.get("waves") or [],
    }
    canonical = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def snapshot_fingerprint(snapshot: dict) -> str:
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_error_codes(errors: list[dict] | dict | str | None) -> set[str]:
    text = json.dumps(errors or {}, ensure_ascii=False, sort_keys=True).upper()
    known = TRANSIENT_ERROR_CODES | FATAL_ERROR_CODES | {
        "POLICY_ERROR",
        "INVALID_ARGUMENT",
        "ASSET_ERROR",
        "DOMAIN_ERROR",
    }
    result = {code for code in known if code in text}
    if result:
        return result
    if isinstance(errors, list):
        return {
            str(item.get("code") or "UNKNOWN").upper()
            for item in errors
            if isinstance(item, dict)
        } or {"UNKNOWN"}
    return {"UNKNOWN"}


def is_transient_error(errors: list[dict] | dict | str | None) -> bool:
    codes = normalize_error_codes(errors)
    return bool(codes) and codes.issubset(TRANSIENT_ERROR_CODES)


def is_fatal_error(errors: list[dict] | dict | str | None) -> bool:
    return bool(normalize_error_codes(errors) & FATAL_ERROR_CODES)


def retry_delay_seconds(
    deployment_key: str,
    attempt: int,
    *,
    base_seconds: int = 60,
    maximum_seconds: int = 3600,
) -> int:
    exponent = max(0, attempt - 1)
    backoff = min(maximum_seconds, base_seconds * (2**exponent))
    digest = hashlib.sha256(f"{deployment_key}:{attempt}".encode()).digest()
    jitter = digest[0] % 16
    return backoff + jitter


def should_pause_after_downtime(
    *,
    now: datetime,
    last_dispatch_at: datetime | None,
    overdue_count: int,
    max_parallel: int,
    threshold_seconds: int = 300,
) -> bool:
    if not last_dispatch_at or overdue_count <= max_parallel:
        return False
    return _utc(now) - _utc(last_dispatch_at) > timedelta(seconds=threshold_seconds)


def is_run_due(
    *,
    status: str,
    scheduled_for: datetime,
    next_retry_at: datetime | None,
    now: datetime,
) -> bool:
    if status == "WAITING":
        return _utc(scheduled_for) <= _utc(now)
    if status == "RETRY_WAIT":
        return bool(next_retry_at and _utc(next_retry_at) <= _utc(now))
    return False


def rate_limit_conflicts(times: list[datetime], hourly_limit: int, daily_limit: int) -> list[int]:
    conflicts = []
    accepted: list[datetime] = []
    for index, current in enumerate(sorted(_utc(item) for item in times)):
        if sum(item > current - timedelta(hours=1) for item in accepted) >= hourly_limit:
            conflicts.append(index)
        elif sum(item > current - timedelta(days=1) for item in accepted) >= daily_limit:
            conflicts.append(index)
        accepted.append(current)
    return conflicts


def circuit_breaker_decision(
    *,
    consecutive_serious_errors: int,
    threshold: int,
    errors: list[dict] | dict | str | None,
) -> tuple[int, bool]:
    next_count = consecutive_serious_errors + 1
    return next_count, is_fatal_error(errors) or next_count >= threshold


def _build_waves(
    accounts: list[dict],
    config: dict,
    time_zone: str,
    now: datetime,
) -> tuple[list[tuple[dict, int, datetime]], list[dict]]:
    start_at = local_to_utc(config.get("start_local") or config.get("start_at"), time_zone, field="start") or now
    first_size = _positive_int(config.get("first_wave_size"), 5, "Размер первой волны")
    next_size = _positive_int(config.get("next_wave_size"), 10, "Размер следующих волн")
    first_spread = _non_negative_int(config.get("first_wave_spread_minutes"), 240, "Длительность первой волны")
    next_spread = _non_negative_int(config.get("next_wave_spread_minutes"), 480, "Длительность следующих волн")
    observation = _non_negative_int(config.get("observation_minutes"), 720, "Период наблюдения")
    between = _non_negative_int(config.get("between_waves_minutes"), 360, "Период между волнами")
    manual_approval = bool(config.get("manual_approval", True))

    chunks: list[list[dict]] = []
    remaining = list(accounts)
    chunks.append(remaining[:first_size])
    remaining = remaining[first_size:]
    while remaining:
        chunks.append(remaining[:next_size])
        remaining = remaining[next_size:]

    desired: list[tuple[dict, int, datetime]] = []
    waves: list[dict] = []
    wave_start = start_at
    for index, chunk in enumerate(chunks, start=1):
        spread_minutes = first_spread if index == 1 else next_spread
        spread = timedelta(minutes=spread_minutes)
        interval = spread / max(1, len(chunk))
        for position, account in enumerate(chunk):
            desired.append((account, index, wave_start + interval * position))
        wave_end = wave_start + spread
        observation_until = wave_end + timedelta(minutes=observation) if index == 1 and len(chunks) > 1 else None
        waves.append(
            {
                "wave_number": index,
                "approval_required": manual_approval and index > 1,
                "observation_until": observation_until.isoformat() if observation_until else None,
                "window_start": wave_start.isoformat(),
                "window_end": wave_end.isoformat(),
            }
        )
        if index == 1:
            wave_start = wave_end + timedelta(minutes=observation)
        else:
            wave_start = wave_end + timedelta(minutes=between)
    return desired, waves


def _build_manual(
    accounts: list[dict],
    config: dict,
    time_zone: str,
) -> tuple[list[tuple[dict, int, datetime]], list[dict], list[dict]]:
    manual_by_id = {
        str(item.get("account_test_bundle_id")): item
        for item in config.get("manual_runs") or []
        if item.get("account_test_bundle_id")
    }
    desired = []
    unassigned = []
    wave_numbers = set()
    for account in accounts:
        row = manual_by_id.get(str(account["id"]))
        if not row or not (row.get("scheduled_local") or row.get("scheduled_for")):
            unassigned.append(
                {
                    "account_test_bundle_id": str(account["id"]),
                    "customer_id": str(account["customer_id"]),
                    "account_name": str(account.get("account_name") or account["customer_id"]),
                }
            )
            continue
        scheduled_for = local_to_utc(
            row.get("scheduled_local") or row.get("scheduled_for"),
            time_zone,
            field="manual_runs.scheduled_local",
        )
        wave_number = _positive_int(row.get("wave_number"), 1, "Номер волны")
        wave_numbers.add(wave_number)
        desired.append((account, wave_number, scheduled_for))
    desired.sort(key=lambda item: item[2])
    waves = [
        {
            "wave_number": number,
            "approval_required": bool(config.get("manual_approval", False)) and number > min(wave_numbers or {1}),
            "observation_until": None,
        }
        for number in sorted(wave_numbers)
    ]
    return desired, waves, unassigned


def _apply_rate_limits(
    desired: list[tuple[dict, int, datetime]],
    hourly_limit: int,
    daily_limit: int,
) -> list[tuple[dict, int, datetime]]:
    result: list[tuple[dict, int, datetime]] = []
    accepted: list[datetime] = []
    for account, wave, desired_time in desired:
        candidate = _utc(desired_time)
        while True:
            hour_rows = [item for item in accepted if item > candidate - timedelta(hours=1) and item <= candidate]
            day_rows = [item for item in accepted if item > candidate - timedelta(days=1) and item <= candidate]
            targets = []
            if len(hour_rows) >= hourly_limit:
                targets.append(hour_rows[-hourly_limit] + timedelta(hours=1, microseconds=1))
            if len(day_rows) >= daily_limit:
                targets.append(day_rows[-daily_limit] + timedelta(days=1, microseconds=1))
            if not targets:
                break
            candidate = max(targets)
        accepted.append(candidate)
        result.append((account, wave, candidate))
    return result


def _summarize_waves(runs: list[dict], definitions: list[dict]) -> list[dict]:
    by_number = {int(item["wave_number"]): item for item in definitions}
    result = []
    for number in sorted({int(item["wave_number"]) for item in runs}):
        rows = [item for item in runs if int(item["wave_number"]) == number]
        definition = by_number.get(number, {})
        starts_at = min(_parse_utc(item["scheduled_for"]) for item in rows)
        ends_at = max(_parse_utc(item["scheduled_for"]) for item in rows)
        result.append(
            {
                "wave_number": number,
                "accounts": len(rows),
                "campaigns": sum(int(item["campaigns_count"]) for item in rows),
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "observation_until": definition.get("observation_until"),
                "approval_required": bool(definition.get("approval_required")),
                "config": {
                    key: value
                    for key, value in definition.items()
                    if key not in {"wave_number", "approval_required", "observation_until"}
                },
            }
        )
    return result


def _ordered_accounts(accounts: list[dict], order: list) -> list[dict]:
    positions = {str(account_id): index for index, account_id in enumerate(order)}
    return sorted(
        accounts,
        key=lambda item: (
            positions.get(str(item["id"]), len(positions)),
            str(item.get("account_name") or ""),
            str(item["customer_id"]),
        ),
    )


def _deployment_key(account: dict) -> str:
    material = f"{account['id']}:{account['customer_id']}:{account.get('campaigns_count') or 0}"
    return hashlib.sha256(material.encode()).hexdigest()


def _positive_int(value: object, default: int, label: str) -> int:
    parsed = int(value if value not in (None, "") else default)
    if parsed <= 0:
        raise ScheduleValidationError(f"{label} должен быть больше нуля")
    return parsed


def _non_negative_int(value: object, default: int, label: str) -> int:
    parsed = int(value if value not in (None, "") else default)
    if parsed < 0:
        raise ScheduleValidationError(f"{label} не может быть отрицательным")
    return parsed


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ScheduleValidationError("Дата должна содержать часовой пояс")
    return value.astimezone(UTC)


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _warning(code: str, message: str) -> dict:
    return {"code": code, "message": message}
