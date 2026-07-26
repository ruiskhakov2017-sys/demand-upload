from __future__ import annotations

from dataclasses import asdict, dataclass

CURRENT_GOOGLE_ADS_API_VERSION = "v24.2"


@dataclass(frozen=True)
class CapabilityField:
    key: str
    label: str
    level: str
    min_api_version: str
    demand_gen: bool
    supports_create: bool
    supports_read: bool
    reason: str | None = None


@dataclass(frozen=True)
class DemandGenCapabilities:
    api_version: str
    supports_image_multi_asset: bool
    supports_video_responsive: bool
    supports_carousel: bool
    supports_classic_display_images: bool
    supports_google_ads_video_upload_python: bool
    campaign_create_status: str
    max_headlines: int
    max_descriptions: int
    max_logo_images: int
    max_total_image_assets: int


def get_demand_gen_capabilities(api_version: str = CURRENT_GOOGLE_ADS_API_VERSION) -> DemandGenCapabilities:
    return DemandGenCapabilities(
        api_version=api_version,
        supports_image_multi_asset=True,
        supports_video_responsive=True,
        supports_carousel=True,
        supports_classic_display_images=True,
        supports_google_ads_video_upload_python=True,
        campaign_create_status="PAUSED",
        max_headlines=5,
        max_descriptions=5,
        max_logo_images=5,
        max_total_image_assets=20,
    )


def get_demand_gen_capability_registry(api_version: str = CURRENT_GOOGLE_ADS_API_VERSION) -> list[dict]:
    unavailable_api = "Эта настройка пока недоступна через Google Ads API для Demand Gen."
    unavailable_runtime = "Поле есть в v24.2, но отсутствует в protobuf-схеме установленного Python client."
    fields = [
        _field("campaign.name", "Название кампании", "CAMPAIGN"),
        _field("campaign.status", "Статус при создании", "CAMPAIGN"),
        _field("campaign.conversion_goals", "Цели конверсий", "CAMPAIGN"),
        _field("campaign.conversion_actions", "Выбранные conversion actions", "CAMPAIGN"),
        _field("bidding.maximize_clicks", "Максимум кликов", "CAMPAIGN"),
        _field("bidding.target_cpa", "Целевая цена за конверсию", "CAMPAIGN"),
        _field("bidding.maximize_conversions", "Максимум конверсий", "CAMPAIGN"),
        _field("bidding.target_roas", "Целевая рентабельность", "CAMPAIGN"),
        _field(
            "bidding.maximize_conversion_value",
            "Максимум ценности конверсий",
            "CAMPAIGN",
            create=False,
            reason=(
                "Официальный список стратегий Demand Gen v24 не включает отдельную стратегию "
                "Maximize Conversion Value."
            ),
        ),
        _field("budget.daily", "Средний дневной бюджет", "CAMPAIGN"),
        _field("budget.total", "Общий бюджет кампании", "CAMPAIGN"),
        _field("campaign.start_date_time", "Дата и время начала", "CAMPAIGN"),
        _field("campaign.end_date_time", "Дата и время окончания", "CAMPAIGN"),
        _field("campaign.schedule", "Расписание показов", "CAMPAIGN"),
        _field("url.tracking_template", "Tracking template", "CAMPAIGN"),
        _field("url.final_url_suffix", "Final URL suffix", "CAMPAIGN"),
        _field("url.custom_parameters", "Custom parameters", "CAMPAIGN"),
        _field("targeting.locations", "География", "AD_GROUP"),
        _field("targeting.excluded_locations", "Исключённая география", "AD_GROUP"),
        _field("targeting.languages", "Языки", "AD_GROUP"),
        _field("targeting.audiences", "Аудитории", "AD_GROUP"),
        _field("targeting.user_lists", "User lists и Customer Match", "AD_GROUP"),
        _field("targeting.custom_audiences", "Пользовательские сегменты", "AD_GROUP"),
        _field("targeting.interests", "Интересы и in-market", "AD_GROUP"),
        _field("targeting.life_events", "Life events", "AD_GROUP"),
        _field("targeting.demographics", "Демография", "AD_GROUP"),
        _field("targeting.optimized", "Оптимизированный таргетинг", "AD_GROUP"),
        _field("channels.all", "Все каналы", "AD_GROUP", minimum="v21"),
        _field("channels.google_owned", "Собственные каналы Google", "AD_GROUP", minimum="v21"),
        _field("channels.youtube_in_stream", "YouTube In-stream", "AD_GROUP", minimum="v21"),
        _field("channels.youtube_in_feed", "YouTube In-feed", "AD_GROUP", minimum="v21"),
        _field("channels.youtube_shorts", "YouTube Shorts", "AD_GROUP", minimum="v21"),
        _field("channels.discover", "Discover", "AD_GROUP", minimum="v21"),
        _field("channels.gmail", "Gmail", "AD_GROUP", minimum="v21"),
        _field("channels.display", "Display", "AD_GROUP", minimum="v21"),
        _field("channels.maps", "Google Maps", "AD_GROUP", minimum="v24.2", create=False, reason=unavailable_runtime),
        _field("targeting.devices", "Устройства", "AD_GROUP", create=False, reason=unavailable_api),
        _field("targeting.operating_systems", "Операционные системы", "AD_GROUP", create=False, reason=unavailable_api),
        _field("ads.multi_asset", "Demand Gen multi-asset ad", "AD"),
        _field("ads.video_responsive", "Demand Gen video responsive ad", "AD"),
        _field("ads.carousel", "Demand Gen carousel ad", "AD", minimum="v24"),
        _field("ads.final_url", "Final URL", "AD"),
        _field("ads.mobile_final_url", "Mobile final URL", "AD"),
        _field("ads.display_path", "Display path", "AD"),
        _field("assets.classic_display_images", "Classic display images", "AD"),
        _field("assets.companion_banner", "Companion banner", "AD"),
        _field("assets.local_video_upload", "Локальная загрузка видео", "ASSET"),
        _field("ads.preview", "Предпросмотр объявления Google", "AD", create=False, reason=unavailable_api),
    ]
    return [asdict(item) | {"api_version": api_version} for item in fields]


def _field(
    key: str,
    label: str,
    level: str,
    *,
    minimum: str = "v24",
    create: bool = True,
    read: bool = True,
    reason: str | None = None,
) -> CapabilityField:
    return CapabilityField(
        key=key,
        label=label,
        level=level,
        min_api_version=minimum,
        demand_gen=True,
        supports_create=create,
        supports_read=read,
        reason=reason,
    )
