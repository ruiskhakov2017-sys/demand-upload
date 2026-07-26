from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from urllib.parse import urlparse

from app.db.models import AccountTestBundle, CampaignInstance, CampaignUpload, LaunchBatch, MediaAsset


def build_plan_snapshot(upload: CampaignUpload, media: list[MediaAsset], execution_mode: str) -> tuple[dict, str]:
    draft = deepcopy(upload.draft or {})
    base_campaign = deepcopy(draft.get("campaign", {}))
    rows = upload.source_rows or [{}]
    campaigns: list[dict] = []
    for index, row in enumerate(rows):
        campaign = _merge_non_empty(base_campaign, row)
        campaign["row_number"] = index + 1
        campaign["customer_id"] = _digits(campaign.get("customer_id") or draft.get("customer_id", ""))
        campaign["headlines"] = _as_list(campaign.get("headlines"))
        campaign["descriptions"] = _as_list(campaign.get("descriptions"))
        campaign["location_ids"] = [_digits(value) for value in _as_list(campaign.get("location_ids") or ["2840"])]
        campaign["language_ids"] = [_digits(value) for value in _as_list(campaign.get("language_ids") or ["1000"])]
        campaign["media_ids"] = [str(value) for value in _as_list(campaign.get("media_ids"))]
        campaign["daily_budget_micros"] = _money_to_micros(
            campaign.get("daily_budget_micros"), campaign.get("daily_budget")
        )
        campaign["target_cpa_micros"] = _money_to_micros(campaign.get("target_cpa_micros"), campaign.get("target_cpa"))
        campaign["ad_type"] = str(campaign.get("ad_type") or "VIDEO").upper()
        campaign["campaign_status"] = "PAUSED"
        campaign["contains_eu_political_advertising"] = "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"
        campaign_key_source = json.dumps(campaign, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        campaign["deployment_key"] = hashlib.sha256(campaign_key_source.encode("utf-8")).hexdigest()[:12]
        campaign["google_campaign_name"] = (
            f"{str(campaign.get('campaign_name') or '')[:180]} [DGU {campaign['deployment_key']}]"
        )[:255]
        campaigns.append(campaign)

    selected_ids = {media_id for campaign in campaigns for media_id in campaign.get("media_ids", [])}
    selected_media = [
        {
            "id": str(item.id),
            "kind": item.kind,
            "name": item.name,
            "sha256": item.sha256,
            "storage_key": item.storage_key,
            "content_type": item.content_type,
            "width": item.width,
            "height": item.height,
            "duration_seconds": item.duration_seconds,
            "status": item.status,
            "youtube_video_id": item.youtube_video_id,
        }
        for item in media
        if str(item.id) in selected_ids
    ]
    snapshot = {
        "schema_version": 1,
        "upload_id": str(upload.id),
        "upload_name": upload.name,
        "execution_mode": execution_mode,
        "connection_id": str(upload.connection_id) if upload.connection_id else None,
        "campaigns": campaigns,
        "media": selected_media,
        "policy": {"campaign_status": "PAUSED", "partial_failure": False, "atomic_per_campaign": True},
    }
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return snapshot, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_batch_plan_snapshot(
    upload: CampaignUpload,
    batch: LaunchBatch,
    bundles: list[AccountTestBundle],
    instances: list[CampaignInstance],
    media: list[MediaAsset],
    execution_mode: str,
) -> tuple[dict, str]:
    bundle_by_id = {str(item.id): item for item in bundles}
    campaigns: list[dict] = []
    for instance in sorted(instances, key=lambda item: (item.customer_id, item.campaign_sequence)):
        if not instance.included:
            continue
        bundle = bundle_by_id[str(instance.account_test_bundle_id)]
        campaign = _instance_to_campaign(instance, bundle)
        campaigns.append(campaign)

    selected_ids = {media_id for campaign in campaigns for media_id in campaign.get("media_ids", [])}
    selected_media = [_media_snapshot(item) for item in media if str(item.id) in selected_ids]
    snapshot = {
        "schema_version": 2,
        "upload_id": str(upload.id),
        "upload_name": upload.name,
        "launch_batch_id": str(batch.id),
        "launch_batch_version": batch.version_number,
        "generation_seed": batch.generation_seed,
        "generation_time": batch.generation_time.isoformat(),
        "execution_mode": execution_mode,
        "connection_id": str(upload.connection_id) if upload.connection_id else None,
        "campaigns": campaigns,
        "media": selected_media,
        "financial_preview": deepcopy(batch.financial_preview),
        "policy": {
            "campaign_status": "PAUSED",
            "partial_failure": True,
            "atomic_per_campaign": True,
            "different_customer_mutations_separated": True,
        },
    }
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return snapshot, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_plan_snapshot(snapshot: dict) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    campaigns = snapshot.get("campaigns") or []
    media_by_id = {item["id"]: item for item in snapshot.get("media") or []}
    if not campaigns:
        errors.append(_issue("campaigns", "EMPTY", "Нет кампаний для создания"))

    for index, campaign in enumerate(campaigns):
        path = f"campaigns.{index}"
        _required(errors, campaign, "customer_id", path, "Выберите Google Ads аккаунт")
        if campaign.get("customer_id") and len(_digits(campaign["customer_id"])) < 6:
            errors.append(_issue(f"{path}.customer_id", "INVALID_CUSTOMER", "Некорректный Customer ID"))
        _required(errors, campaign, "campaign_name", path, "Укажите название кампании")
        _required(errors, campaign, "ad_group_name", path, "Укажите название группы объявлений")
        _required(errors, campaign, "business_name", path, "Укажите название компании")
        if len(str(campaign.get("business_name") or "")) > 25:
            errors.append(_issue(f"{path}.business_name", "TOO_LONG", "Название компании: максимум 25 символов"))

        final_url = str(campaign.get("final_url") or "")
        parsed_url = urlparse(final_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            errors.append(_issue(f"{path}.final_url", "INVALID_URL", "Нужен полный URL с http:// или https://"))

        budget = int(campaign.get("daily_budget_micros") or 0)
        if budget <= 0:
            errors.append(
                _issue(f"{path}.daily_budget_micros", "INVALID_BUDGET", "Дневной бюджет должен быть больше нуля")
            )
        strategy = str(campaign.get("bidding_strategy") or "TARGET_CPA").upper()
        if strategy not in {
            "MAXIMIZE_CONVERSIONS",
            "TARGET_CPA",
            "TARGET_ROAS",
            "MAXIMIZE_CLICKS",
        }:
            errors.append(_issue(f"{path}.bidding_strategy", "UNSUPPORTED_BID", "Стратегия ставок не поддерживается"))
        target_cpa = int(campaign.get("target_cpa_micros") or 0)
        if strategy == "TARGET_CPA" and target_cpa <= 0:
            errors.append(_issue(f"{path}.target_cpa_micros", "INVALID_BID", "Target CPA должен быть больше нуля"))
        target_roas = float(campaign.get("target_roas") or 0)
        if strategy == "TARGET_ROAS" and target_roas <= 0:
            errors.append(_issue(f"{path}.target_roas", "INVALID_BID", "Target ROAS должен быть больше нуля"))

        _validate_account_resources(errors, campaign, path)
        controls = campaign.get("channel_controls") or {}
        selected_channels = controls.get("selected") or controls.get("selected_channels") or {}
        if selected_channels.get("maps"):
            errors.append(
                _issue(
                    f"{path}.channel_controls.selected.maps",
                    "UNAVAILABLE_PROTO_FIELD",
                    "Google Maps пока недоступен в protobuf-схеме установленного Google Ads client",
                )
            )

        _validate_text_assets(errors, campaign.get("headlines") or [], 1, 5, 30, f"{path}.headlines", "заголовков")
        _validate_text_assets(errors, campaign.get("descriptions") or [], 1, 5, 90, f"{path}.descriptions", "описаний")
        long_headline = str(campaign.get("long_headline") or "")
        if campaign.get("ad_type") == "VIDEO" and (not long_headline or len(long_headline) > 90):
            errors.append(_issue(f"{path}.long_headline", "INVALID_LENGTH", "Длинный заголовок: от 1 до 90 символов"))

        if not all(value.isdigit() for value in campaign.get("location_ids") or []):
            errors.append(
                _issue(f"{path}.location_ids", "INVALID_TARGET", "Гео должны быть ID Google GeoTargetConstant")
            )
        if not all(value.isdigit() for value in campaign.get("language_ids") or []):
            errors.append(_issue(f"{path}.language_ids", "INVALID_TARGET", "Языки должны быть ID LanguageConstant"))

        ad_type = campaign.get("ad_type")
        campaign_media = [media_by_id[item] for item in campaign.get("media_ids", []) if item in media_by_id]
        youtube_ids = [campaign.get("youtube_video_id")] + [item.get("youtube_video_id") for item in campaign_media]
        if ad_type == "VIDEO" and not any(youtube_ids):
            errors.append(
                _issue(f"{path}.youtube_video_id", "VIDEO_REQUIRED", "Добавьте YouTube video ID или обработанное видео")
            )
        if ad_type == "IMAGE" and not campaign_media:
            errors.append(_issue(f"{path}.media_ids", "IMAGES_REQUIRED", "Добавьте изображения для объявления"))
        if ad_type == "CAROUSEL" and len(campaign_media) < 3:
            errors.append(
                _issue(
                    f"{path}.media_ids",
                    "CAROUSEL_ASSETS",
                    "Для карусели нужны логотип и минимум две карточки",
                )
            )
        if ad_type not in {"VIDEO", "IMAGE", "CAROUSEL"}:
            errors.append(_issue(f"{path}.ad_type", "UNSUPPORTED_AD_TYPE", "Поддерживаются VIDEO, IMAGE и CAROUSEL"))
        invalid_media = [item["name"] for item in campaign_media if item.get("status") != "READY"]
        if invalid_media:
            errors.append(
                _issue(f"{path}.media_ids", "MEDIA_NOT_READY", "Медиа не готово: " + ", ".join(invalid_media))
            )

        if ad_type == "VIDEO" and not any(item.get("kind") == "IMAGE" for item in campaign_media):
            warnings.append(
                _issue(f"{path}.media_ids", "LOGO_RECOMMENDED", "Для live-запуска добавьте квадратный логотип")
            )

    duplicate_groups: dict[str, list[str]] = {}
    for campaign in campaigns:
        material = {
            key: campaign.get(key)
            for key in (
                "customer_id",
                "daily_budget_micros",
                "bidding_strategy",
                "target_cpa_micros",
                "target_roas",
                "location_ids",
                "language_ids",
                "audience_resource_names",
                "final_url",
                "headlines",
                "descriptions",
                "media_ids",
            )
        }
        signature = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()
        duplicate_groups.setdefault(signature, []).append(str(campaign.get("campaign_name") or ""))
    for names in duplicate_groups.values():
        if len(names) > 1:
            warnings.append(
                _issue(
                    "campaigns",
                    "INTENTIONAL_DUPLICATES",
                    "Полностью одинаковые настройки: " + ", ".join(names[:5]),
                )
            )

    if snapshot.get("execution_mode") == "SIMULATION":
        warnings.append(
            _issue("execution_mode", "SIMULATION", "Проверка выполняется локальным адаптером и не обращается в Google")
        )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "campaign_count": len(campaigns),
        "account_count": len({item.get("customer_id") for item in campaigns if item.get("customer_id")}),
    }


def _instance_to_campaign(instance: CampaignInstance, bundle: AccountTestBundle) -> dict:
    campaign_settings = deepcopy(instance.campaign_settings or {})
    bidding = deepcopy(instance.bidding or {})
    targeting = deepcopy(instance.targeting or {})
    urls = deepcopy(instance.url_settings or {})
    texts = deepcopy(instance.texts or {})
    creative = deepcopy(instance.creative_assignment or {})
    strategy = str(bidding.get("strategy") or "TARGET_CPA").upper()
    campaign = {
        **campaign_settings,
        "campaign_instance_id": str(instance.id),
        "account_test_bundle_id": str(instance.account_test_bundle_id),
        "launch_batch_id": str(instance.launch_batch_id),
        "customer_id": instance.customer_id,
        "account_name": bundle.account_name,
        "currency_code": instance.currency_code,
        "time_zone": bundle.time_zone,
        "campaign_sequence": instance.campaign_sequence,
        "campaign_name": instance.campaign_name,
        "campaign_status": "PAUSED",
        "daily_budget_micros": instance.budget_micros,
        "budget_mode": instance.budget_mode,
        "bidding_strategy": strategy,
        "target_cpa_micros": _money_to_micros(bidding.get("target_cpa_micros"), bidding.get("target_cpa")),
        "target_roas": bidding.get("target_roas"),
        "location_ids": [_digits(item) for item in _as_list(targeting.get("location_ids") or ["2840"])],
        "excluded_location_ids": [_digits(item) for item in _as_list(targeting.get("excluded_location_ids"))],
        "language_ids": [_digits(item) for item in _as_list(targeting.get("language_ids") or ["1000"])],
        "audience_resource_names": _as_list(targeting.get("audience_resource_names")),
        "user_list_resource_names": _as_list(targeting.get("user_list_resource_names")),
        "custom_audience_resource_names": _as_list(targeting.get("custom_audience_resource_names")),
        "user_interest_resource_names": _as_list(targeting.get("user_interest_resource_names")),
        "life_event_ids": _as_list(targeting.get("life_event_ids")),
        "demographics": deepcopy(targeting.get("demographics") or {}),
        "optimized_targeting": bool(targeting.get("optimized_targeting", True)),
        "channel_controls": deepcopy(targeting.get("channel_controls") or {"mode": "ALL_CHANNELS"}),
        "final_url": urls.get("final_url") or campaign_settings.get("final_url"),
        "mobile_final_url": urls.get("mobile_final_url"),
        "tracking_template": urls.get("tracking_template"),
        "final_url_suffix": urls.get("final_url_suffix"),
        "custom_parameters": deepcopy(urls.get("custom_parameters") or []),
        "display_path": urls.get("display_path"),
        "headlines": _as_list(texts.get("headlines")),
        "long_headline": texts.get("long_headline") or "",
        "descriptions": _as_list(texts.get("descriptions")),
        "business_name": texts.get("business_name") or campaign_settings.get("business_name"),
        "call_to_action": texts.get("call_to_action") or "LEARN_MORE",
        "carousel_card_headlines": _as_list(texts.get("carousel_card_headlines")),
        "ad_group_name": campaign_settings.get("ad_group_name") or "Основная группа",
        "ad_type": str(campaign_settings.get("ad_type") or "VIDEO").upper(),
        "youtube_video_id": creative.get("youtube_video_id") or campaign_settings.get("youtube_video_id"),
        "media_ids": [str(item) for item in creative.get("media_ids") or creative.get("items") or []],
        "deployment_key": instance.deployment_key,
        "contains_eu_political_advertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
        "conversion_action_resource_names": _as_list(
            campaign_settings.get("conversion_action_resource_names")
            or bidding.get("conversion_action_resource_names")
        ),
    }
    campaign["google_campaign_name"] = f"{instance.campaign_name[:180]} [DGU {instance.deployment_key[:12]}]"[:255]
    return campaign


def _media_snapshot(item: MediaAsset) -> dict:
    return {
        "id": str(item.id),
        "kind": item.kind,
        "name": item.name,
        "sha256": item.sha256,
        "storage_key": item.storage_key,
        "content_type": item.content_type,
        "width": item.width,
        "height": item.height,
        "duration_seconds": item.duration_seconds,
        "status": item.status,
        "youtube_video_id": item.youtube_video_id,
        "suggested_role": (item.validation or {}).get("suggested_role"),
    }


def _merge_non_empty(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in (override or {}).items():
        if value is not None and value != "" and value != []:
            result[key] = value
    return result


def _digits(value: object) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _as_list(value: object) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [item.strip() for item in value.replace("\n", "|").split("|") if item.strip()]
    return [value]


def _money_to_micros(micros: object, units: object) -> int:
    if micros not in (None, ""):
        return int(float(str(micros).replace(",", ".")))
    if units in (None, ""):
        return 0
    return int(round(float(str(units).replace(",", ".")) * 1_000_000))


def _required(errors: list[dict], obj: dict, key: str, path: str, message: str) -> None:
    if not str(obj.get(key) or "").strip():
        errors.append(_issue(f"{path}.{key}", "REQUIRED", message))


def _validate_text_assets(
    errors: list[dict], values: list, minimum: int, maximum: int, length: int, path: str, label: str
) -> None:
    if not minimum <= len(values) <= maximum:
        errors.append(_issue(path, "INVALID_COUNT", f"Нужно от {minimum} до {maximum} {label}"))
    for index, value in enumerate(values):
        if not str(value).strip() or len(str(value)) > length:
            errors.append(_issue(f"{path}.{index}", "INVALID_LENGTH", f"Максимум {length} символов"))


def _validate_account_resources(errors: list[dict], campaign: dict, path: str) -> None:
    customer_id = str(campaign.get("customer_id") or "")
    fields = {
        "conversion_action_resource_names": "conversionActions",
        "audience_resource_names": "audiences",
        "user_list_resource_names": "userLists",
        "custom_audience_resource_names": "customAudiences",
    }
    for field, collection in fields.items():
        prefix = f"customers/{customer_id}/{collection}/"
        for index, resource_name in enumerate(campaign.get(field) or []):
            if not str(resource_name).startswith(prefix):
                errors.append(
                    _issue(
                        f"{path}.{field}.{index}",
                        "CROSS_ACCOUNT_RESOURCE",
                        f"Ресурс должен принадлежать customer_id {customer_id}",
                    )
                )


def _issue(path: str, code: str, message: str) -> dict:
    return {"path": path, "code": code, "message": message}
