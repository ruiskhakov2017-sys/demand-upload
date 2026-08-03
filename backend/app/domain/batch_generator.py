from __future__ import annotations

import hashlib
import json
import random
import re
from copy import deepcopy
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid5

COPY_MODES = {
    "EXACT_COPY",
    "SAME_SETTINGS_RANDOM_BUDGET",
    "RANDOM_CREATIVE_SUBSET",
    "ROTATE_CREATIVE_SETS",
    "BIDDING_VARIATIONS",
    "AUDIENCE_VARIATIONS",
    "CUSTOM_MATRIX",
}
BUDGET_MODES = {"FIXED", "RANGE", "MANUAL_LIST", "PER_ACCOUNT_OVERRIDE", "PER_CAMPAIGN_OVERRIDE"}
DISTRIBUTIONS = {"RANDOM", "BALANCED_RANDOM", "SEQUENTIAL", "MANUAL_AFTER_GENERATION"}
DEFAULT_NAME_PATTERN = "{account_name}_{template_name}_{date}_{sequence}"


class GenerationError(ValueError):
    pass


def generate_batch_matrix(
    batch_id: UUID,
    config: dict,
    generation_time: datetime,
    media_catalog: list[dict] | None = None,
) -> dict:
    accounts = deepcopy(config.get("accounts") or [])
    if not accounts:
        raise GenerationError("Выберите хотя бы один аккаунт")
    copy_mode = str(config.get("copy_mode") or "EXACT_COPY").upper()
    if copy_mode not in COPY_MODES:
        raise GenerationError(f"Неизвестный режим копий: {copy_mode}")
    default_count = _positive_int(config.get("campaigns_per_account", 1), "campaigns_per_account")
    seed = str(config.get("generation_seed") or batch_id)
    name_pattern = str(config.get("name_pattern") or DEFAULT_NAME_PATTERN)
    template_defaults = deepcopy(config.get("template_defaults") or {})
    batch_overrides = deepcopy(config.get("batch_overrides") or {})
    campaign_overrides = deepcopy(config.get("campaign_overrides") or {})
    media_catalog = media_catalog or []

    bundles: list[dict] = []
    all_instances: list[dict] = []
    used_names: set[str] = set()
    for account_index, account in enumerate(accounts):
        customer_id = _digits(account.get("customer_id"))
        if len(customer_id) < 6:
            raise GenerationError(f"Некорректный customer_id: {account.get('customer_id')}")
        account_name = str(account.get("account_name") or account.get("descriptive_name") or customer_id)
        currency = str(account.get("currency_code") or "USD").upper()
        time_zone = str(account.get("time_zone") or "UTC")
        account_overrides = deepcopy(account.get("overrides") or {})
        requested_count = account.get("campaigns_count")
        count = _positive_int(
            default_count if requested_count is None else requested_count,
            f"{customer_id}.campaigns_count",
        )
        bundle_id = uuid5(batch_id, f"bundle:{customer_id}")
        bundle_seed = f"{seed}:{customer_id}"
        budgets = generate_budgets(config.get("budget") or {}, count, currency, bundle_seed, account_overrides)
        creative_state = _creative_state(config.get("creative") or {}, media_catalog, bundle_seed)
        instances: list[dict] = []

        for offset in range(count):
            sequence = offset + 1
            instance_id = uuid5(bundle_id, f"campaign:{sequence}")
            override = deepcopy(
                campaign_overrides.get(f"{customer_id}:{sequence}")
                or campaign_overrides.get(str(instance_id))
                or {}
            )
            budget_micros = _campaign_budget_override(override, budgets[offset])
            inherited = deep_merge(template_defaults, batch_overrides)
            inherited = deep_merge(inherited, account_overrides)
            inherited = deep_merge(inherited, override)
            inherited = _apply_variation(inherited, config, copy_mode, offset)
            creative = assign_creatives(
                config.get("creative") or {},
                media_catalog,
                copy_mode,
                offset,
                creative_state,
            )
            budget_units = _micros_to_decimal(budget_micros)
            url_settings = _instance_url_settings(inherited.get("url") or {}, instance_id)
            context = {
                "account_name": account_name,
                "customer_id": customer_id,
                "geo": _first(inherited.get("targeting", {}).get("location_ids"), "ALL"),
                "template_name": str(config.get("template_name") or "DemandGen"),
                "batch_name": str(config.get("batch_name") or "LaunchBatch"),
                "date": generation_time.strftime("%Y%m%d"),
                "time": generation_time.strftime("%H%M%S"),
                "sequence": f"{sequence:02d}",
                "budget": _decimal_text(budget_units),
                "creative_set": str(creative.get("set_key") or "default"),
                "random_suffix": _random_suffix(bundle_seed, sequence),
            }
            campaign_name = render_campaign_name(name_pattern, context)
            if campaign_name in used_names:
                campaign_name = f"{campaign_name}_{customer_id[-4:]}_{sequence:02d}"[:255]
            if campaign_name in used_names:
                raise GenerationError(f"Шаблон названия не обеспечивает уникальность: {campaign_name}")
            used_names.add(campaign_name)

            payload = {
                "id": str(instance_id),
                "launch_batch_id": str(batch_id),
                "account_test_bundle_id": str(bundle_id),
                "customer_id": customer_id,
                "account_name": account_name,
                "currency_code": currency,
                "time_zone": time_zone,
                "campaign_sequence": sequence,
                "campaign_name": campaign_name,
                "campaign_status": "PAUSED",
                "budget_micros": budget_micros,
                "budget": _decimal_text(budget_units),
                "budget_mode": str((config.get("budget") or {}).get("mode") or "FIXED").upper(),
                "generation_seed": seed,
                "copy_mode": copy_mode,
                "campaign_settings": deepcopy(inherited.get("campaign") or {}),
                "bidding": deepcopy(inherited.get("bidding") or {}),
                "targeting": deepcopy(inherited.get("targeting") or {}),
                "url_settings": url_settings,
                "texts": deepcopy(inherited.get("texts") or {}),
                "ads": deepcopy(inherited.get("ads") or {}),
                "creative_assignment": creative,
                "override_payload": override,
                "included": bool(override.get("included", True)),
            }
            payload["deployment_key"] = build_deployment_key(payload)
            instances.append(payload)
            all_instances.append(payload)

        bundles.append(
            {
                "id": str(bundle_id),
                "launch_batch_id": str(batch_id),
                "customer_account_id": account.get("id") or account.get("customer_account_id"),
                "customer_id": customer_id,
                "account_name": account_name,
                "currency_code": currency,
                "time_zone": time_zone,
                "campaigns_count": count,
                "override_payload": account_overrides,
                "instances": instances,
                "account_index": account_index,
            }
        )

    financial = build_financial_preview(all_instances, config.get("budget") or {})
    return {
        "schema_version": 2,
        "batch_id": str(batch_id),
        "generation_seed": seed,
        "generation_time": generation_time.isoformat(),
        "name_pattern": name_pattern,
        "copy_mode": copy_mode,
        "bundles": bundles,
        "instances": all_instances,
        "financial_preview": financial,
    }


def generate_budgets(
    budget_config: dict,
    count: int,
    currency: str,
    seed: str,
    account_overrides: dict | None = None,
) -> list[int]:
    merged = deepcopy(budget_config)
    merged = deep_merge(merged, (budget_config.get("per_currency") or {}).get(currency) or {})
    merged = deep_merge(merged, (account_overrides or {}).get("budget") or {})
    mode = str(merged.get("mode") or "FIXED").upper()
    if mode not in BUDGET_MODES:
        raise GenerationError(f"Неизвестный режим бюджета: {mode}")
    if mode == "FIXED" or (
        mode == "PER_ACCOUNT_OVERRIDE"
        and merged.get("fixed", merged.get("value")) not in (None, "")
        and not any(merged.get(key) not in (None, "") for key in ("minimum", "min", "maximum", "max"))
    ):
        value = _money_to_micros(merged.get("fixed", merged.get("value", 0)))
        if value <= 0:
            raise GenerationError("Фиксированный бюджет должен быть больше нуля")
        return [value] * count

    manual = merged.get("manual_values") or []
    if mode in {"MANUAL_LIST", "PER_ACCOUNT_OVERRIDE", "PER_CAMPAIGN_OVERRIDE"} and manual:
        values = [_money_to_micros(item) for item in manual]
        if len(values) < count:
            raise GenerationError(f"Для {count} кампаний указано только {len(values)} бюджетов")
        if any(item <= 0 for item in values[:count]):
            raise GenerationError("Все ручные бюджеты должны быть больше нуля")
        return values[:count]

    minimum = _money_to_micros(merged.get("minimum", merged.get("min", 0)))
    maximum = _money_to_micros(merged.get("maximum", merged.get("max", 0)))
    step = _money_to_micros(merged.get("step", 1))
    if minimum <= 0 or maximum < minimum or step <= 0:
        raise GenerationError("Проверьте минимум, максимум и шаг диапазона бюджета")
    grid_size = ((maximum - minimum) // step) + 1
    if grid_size > 100_000:
        raise GenerationError("Диапазон бюджета содержит больше 100 000 значений; увеличьте шаг")
    grid = list(range(minimum, maximum + 1, step))
    if grid[-1] != maximum and maximum - grid[-1] >= step // 2:
        grid.append(maximum)
    allow_repeats = bool(merged.get("allow_repeats", True))
    if not allow_repeats and count > len(grid):
        raise GenerationError("Диапазон не содержит достаточно уникальных значений")
    distribution = str(merged.get("distribution") or "BALANCED_RANDOM").upper()
    if distribution not in DISTRIBUTIONS:
        raise GenerationError(f"Неизвестное распределение бюджета: {distribution}")
    rng = random.Random(f"{merged.get('seed') or seed}:{currency}")

    if distribution in {"BALANCED_RANDOM", "MANUAL_AFTER_GENERATION"}:
        values = _balanced_values(grid, count, rng, allow_repeats)
    elif distribution == "SEQUENTIAL":
        values = [grid[index % len(grid)] for index in range(count)]
    else:
        values = [rng.choice(grid) for _ in range(count)] if allow_repeats else rng.sample(grid, count)
    return values


def _balanced_values(grid: list[int], count: int, rng: random.Random, allow_repeats: bool) -> list[int]:
    if count == 1:
        return [rng.choice(grid)]
    if not allow_repeats and count <= len(grid):
        selected: list[int] = []
        for index in range(count):
            start = index * len(grid) // count
            stop = max(start + 1, (index + 1) * len(grid) // count)
            available = [item for item in grid[start:stop] if item not in selected]
            selected.append(rng.choice(available or [item for item in grid if item not in selected]))
    else:
        selected = []
        for index in range(count):
            start = index * len(grid) // count
            stop = max(start + 1, (index + 1) * len(grid) // count)
            selected.append(rng.choice(grid[start:stop] or grid))
    if count >= 2 and len(grid) >= 2:
        selected[0] = grid[0]
        selected[-1] = grid[-1]
    rng.shuffle(selected)
    return selected


def assign_creatives(
    creative_config: dict,
    media_catalog: list[dict],
    copy_mode: str,
    offset: int,
    state: dict,
) -> dict:
    sets = creative_config.get("sets") or []
    if sets:
        if copy_mode == "ROTATE_CREATIVE_SETS":
            selected_set = sets[offset % len(sets)]
        elif copy_mode == "RANDOM_CREATIVE_SUBSET":
            selected_set = state["rng"].choice(sets)
        else:
            selected_set = sets[0]
        ids = [str(item) for item in selected_set.get("media_ids") or []]
        ids = _include_required_logo(ids, creative_config)
        return {
            "set_key": selected_set.get("key") or f"set-{offset + 1}",
            "media_ids": ids,
            "items": ids,
            "logo_media_id": creative_config.get("logo_media_id"),
        }

    pool = [str(item) for item in creative_config.get("media_ids") or []]
    if not pool:
        pool = [str(item.get("id")) for item in media_catalog if item.get("id")]
    if copy_mode != "RANDOM_CREATIVE_SUBSET":
        selected = _include_required_logo(pool, creative_config)
        return {
            "set_key": "default",
            "media_ids": selected,
            "items": selected,
            "logo_media_id": creative_config.get("logo_media_id"),
        }

    logo_media_id = str(creative_config.get("logo_media_id") or "")
    subset_pool = [item for item in pool if item != logo_media_id]
    minimum = max(1, int(creative_config.get("minimum_count") or 1))
    maximum = max(
        minimum,
        int(creative_config.get("maximum_count") or len(subset_pool) or minimum),
    )
    amount = min(len(subset_pool), state["rng"].randint(minimum, maximum))
    allow_repeats = bool(creative_config.get("allow_repeats", True))
    if not allow_repeats:
        available = [
            item
            for item in state["shuffled_pool"]
            if item != logo_media_id and item not in state["used"]
        ]
        if len(available) < amount:
            raise GenerationError("Пул креативов закончился, а повторение отключено")
        selected = available[:amount]
        state["used"].update(selected)
    else:
        selected = state["rng"].sample(subset_pool, amount) if amount else []
    selected = _include_required_logo(selected, creative_config)
    return {
        "set_key": f"random-{offset + 1}",
        "media_ids": selected,
        "items": selected,
        "logo_media_id": creative_config.get("logo_media_id"),
    }


def _include_required_logo(ids: list[str], creative_config: dict) -> list[str]:
    logo_media_id = str(creative_config.get("logo_media_id") or "")
    ordered = list(dict.fromkeys(str(item) for item in ids if item))
    if not logo_media_id:
        return ordered
    return [logo_media_id, *[item for item in ordered if item != logo_media_id]]


def _creative_state(config: dict, media_catalog: list[dict], seed: str) -> dict:
    pool = [str(item) for item in config.get("media_ids") or []]
    if not pool:
        pool = [str(item.get("id")) for item in media_catalog if item.get("id")]
    rng = random.Random(f"creative:{config.get('seed') or seed}")
    shuffled = list(pool)
    rng.shuffle(shuffled)
    return {"rng": rng, "shuffled_pool": shuffled, "used": set()}


def _apply_variation(settings: dict, config: dict, copy_mode: str, offset: int) -> dict:
    result = deepcopy(settings)
    if copy_mode == "BIDDING_VARIATIONS":
        variants = config.get("bidding_variations") or []
        if variants:
            result["bidding"] = deep_merge(result.get("bidding") or {}, variants[offset % len(variants)])
    elif copy_mode == "AUDIENCE_VARIATIONS":
        variants = config.get("audience_variations") or []
        if variants:
            result["targeting"] = deep_merge(result.get("targeting") or {}, variants[offset % len(variants)])
    elif copy_mode == "CUSTOM_MATRIX":
        variants = config.get("custom_matrix") or []
        if variants:
            result = deep_merge(result, variants[offset % len(variants)])
    return result


def build_deployment_key(instance: dict) -> str:
    material = {
        "launch_batch_id": instance.get("launch_batch_id"),
        "account_test_bundle_id": instance.get("account_test_bundle_id"),
        "instance_id": instance.get("id"),
        "customer_id": instance.get("customer_id"),
        "campaign_sequence": instance.get("campaign_sequence"),
        "template_version": instance.get("template_version_id"),
        "campaign_name": instance.get("campaign_name"),
        "final_url": instance.get("url_settings", {}).get("final_url"),
        "budget_micros": instance.get("budget_micros"),
        "bidding": instance.get("bidding"),
        "targeting": instance.get("targeting"),
        "texts": instance.get("texts"),
        "creative_assignment": instance.get("creative_assignment"),
    }
    return _hash(material)


def render_campaign_name(pattern: str, values: dict[str, str]) -> str:
    allowed = set(values)
    unknown = set(re.findall(r"\{([^{}]+)\}", pattern)) - allowed
    if unknown:
        raise GenerationError("Неизвестные переменные названия: " + ", ".join(sorted(unknown)))
    rendered = pattern
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", _clean_name_part(value))
    rendered = re.sub(r"\s+", "_", rendered).strip("_ ")
    if not rendered:
        raise GenerationError("Шаблон названия создаёт пустое имя")
    return rendered[:255]


def build_financial_preview(instances: list[dict], budget_config: dict) -> dict:
    by_currency: dict[str, dict] = {}
    for item in instances:
        if not item.get("included", True):
            continue
        currency = item["currency_code"]
        group = by_currency.setdefault(
            currency,
            {"currency_code": currency, "campaigns": 0, "assigned_micros": 0, "minimum_micros": 0, "maximum_micros": 0},
        )
        group["campaigns"] += 1
        group["assigned_micros"] += int(item["budget_micros"])
        effective = deep_merge(budget_config, (budget_config.get("per_currency") or {}).get(currency) or {})
        minimum = effective.get("minimum", effective.get("fixed", effective.get("value", 0)))
        maximum = effective.get("maximum", effective.get("fixed", effective.get("value", 0)))
        group["minimum_micros"] += _money_to_micros(minimum)
        group["maximum_micros"] += _money_to_micros(maximum)
    for value in by_currency.values():
        value["assigned"] = _decimal_text(_micros_to_decimal(value["assigned_micros"]))
        value["minimum"] = _decimal_text(_micros_to_decimal(value["minimum_micros"]))
        value["maximum"] = _decimal_text(_micros_to_decimal(value["maximum_micros"]))
    return {
        "accounts": len({item["customer_id"] for item in instances}),
        "launch_groups": len({item["account_test_bundle_id"] for item in instances}),
        "campaigns": sum(1 for item in instances if item.get("included", True)),
        "created_status": "PAUSED",
        "enabled_campaigns": 0,
        "by_currency": list(by_currency.values()),
    }


def deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        elif value is not None:
            result[key] = deepcopy(value)
    return result


def _campaign_budget_override(override: dict, fallback_micros: int) -> int:
    value = (override or {}).get("budget")
    if value in (None, ""):
        return fallback_micros
    if isinstance(value, dict):
        value = value.get("fixed", value.get("value"))
    micros = _money_to_micros(value)
    if micros <= 0:
        raise GenerationError("Индивидуальный бюджет кампании должен быть больше нуля")
    return micros


def _instance_url_settings(value: dict, instance_id: UUID) -> dict:
    result = deepcopy(value)
    if not result.get("append_dgu_instance"):
        return result
    suffix = str(result.get("final_url_suffix") or "").strip().strip("?&")
    parameter = f"dgu_instance={instance_id}"
    result["final_url_suffix"] = f"{suffix}&{parameter}" if suffix else parameter
    result["dgu_instance_code"] = str(instance_id)
    return result


def _hash(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _money_to_micros(value: object) -> int:
    amount = Decimal(str(value or 0).replace(",", "."))
    return int((amount * Decimal(1_000_000)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _micros_to_decimal(value: int) -> Decimal:
    return Decimal(value) / Decimal(1_000_000)


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _positive_int(value: object, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise GenerationError(f"{field} должен быть целым числом") from exc
    if result < 1:
        raise GenerationError(f"{field} должен быть больше нуля")
    return result


def _digits(value: object) -> str:
    return "".join(item for item in str(value or "") if item.isdigit())


def _first(value: object, default: str) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    return str(value or default)


def _random_suffix(seed: str, sequence: int) -> str:
    return hashlib.sha256(f"{seed}:{sequence}".encode()).hexdigest()[:6]


def _clean_name_part(value: object) -> str:
    text = str(value or "").strip()
    return re.sub(r"[^\w.-]+", "-", text, flags=re.UNICODE).strip("-")
