# Матрица возможностей Google Ads API для «Центра контроля»

Дата проверки: **2026-07-27**. Целевая версия: **Google Ads API v25**. Текущий
адаптер проекта: **v24.2**.

Во всех строках указаны прямой источник, версия, дата и обязательная пометка.
`Основная` означает колонку основной таблицы; `Детали` - карточку объекта или
настраиваемую колонку.

Если в строке не указано более строгое ограничение, production-чтение и mutate
требуют Basic или Standard Access, а Test Account Access разрешает работу только
с test accounts; OAuth principal дополнительно должен иметь доступ к customer.
[Developer Token](https://developers.google.com/google-ads/api/docs/api-policy/developer-token),
все поддерживаемые версии, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 1. Версии, доступ и квоты

| Возможность / ограничение | Результат | Источник и доказательство |
|---|---|---|
| Последняя выпущенная версия | v25, релиз 2026-07-22 | [Release notes](https://developers.google.com/google-ads/api/docs/release-notes), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| v24.2 | Deprecated, но endpoint работает до июня 2027 | [Sunset dates](https://developers.google.com/google-ads/api/docs/sunset-dates), v24.2, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| v25 sunset | Август 2027, дата tentative до объявления Google | [Sunset dates](https://developers.google.com/google-ads/api/docs/sunset-dates), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Python client library | Для v25 минимум `google-ads 31.2.0`; для v24 минимум `30.1.0` | [Supported client libraries](https://developers.google.com/google-ads/api/docs/sunset-dates#python), v25/v24, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Текущий token | Test Account Access работает только с test accounts; production требует Basic/Standard | [Developer Token](https://developers.google.com/google-ads/api/docs/api-policy/developer-token), все версии, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Basic Access daily quota | 15 000 API operations/day на developer token для test + production | [API limits](https://developers.google.com/google-ads/api/docs/best-practices/quotas), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| `Search` / `SearchStream` | Один запрос = одна operation; число stream batches не увеличивает operation count | [Search quotas](https://developers.google.com/google-ads/api/docs/best-practices/quotas#search_requests), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Область одного GAQL request | Request выполняется для одного `customer_id`, а GAQL содержит один `FROM` resource; campaign, ad group, ad, ad-asset и video требуют отдельных query shapes, хотя account rollup можно вычислить локально | [Search requests](https://developers.google.com/google-ads/api/docs/reporting/overview), [GAQL structure](https://developers.google.com/google-ads/api/docs/query/structure), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Mutate limits | До 10 000 mutate operations/request; 100 action operations/request; GoogleAdsFailure тоже расходует quota | [API limits](https://developers.google.com/google-ads/api/docs/best-practices/quotas), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |

## 2. MCC и аккаунты

| Требование | Resource/service/field | Поддержка | Ограничение / локальная логика | Источник и доказательство |
|---|---|---|---|---|
| Доступные аккаунты | `customer_client.id`, `client_customer` | Полная | Запрос выполняется от MCC | [CustomerClient](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerClient), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Прямые/непрямые клиенты | `CustomerClient.level`, `manager` | Полная | Для точных parent edges рекурсивно запросить sub-managers | [Hierarchy guide](https://developers.google.com/google-ads/api/docs/account-management/get-account-hierarchy), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Имя, валюта, timezone | `descriptive_name`, `currency_code`, `time_zone` | Полная | Timezone используется для report windows | [CustomerClient](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerClient), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Test/hidden/manager | `test_account`, `hidden`, `manager` | Полная | Hidden не означает detached | [CustomerClient](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerClient), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Account status | `customer_client.status`: `ENABLED`, `SUSPENDED`, `CANCELED`, `CLOSED` | Полная для статуса | Перед action нужен свежий read | [CustomerStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerStatusEnum.CustomerStatus), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Link status | `customer_client_link.status` | Полная для конкретной manager-client link | `ACTIVE/CANCELED/INACTIVE/PENDING/REFUSED` | [customer_client_link](https://developers.google.com/google-ads/api/fields/v25/customer_client_link), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Появление/исчезновение | Нет готовых дат | Нет | Локальные `first_seen_at`, `last_seen_at`, `detached_at`; исчезновение фиксировать только после полного успешного sync | [CustomerClient](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerClient), v25, 2026-07-27, `NOT_SUPPORTED` |
| История после отвязки | Google больше не гарантирует read access | Частичная | Никогда не удалять локальные snapshots/events; помечать archive/detached | [Authorization headers](https://developers.google.com/google-ads/api/rest/auth), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` для access; локальное сохранение - проектное решение |
| Факт suspension | `CustomerStatus.SUSPENDED` | Полная | Показывать как красный критический статус | [CustomerStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerStatusEnum.CustomerStatus), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Точная причина suspension | Общего поля нет | Нет | Показывать «Причина не предоставлена API»; не угадывать по ошибке | [Customer](https://developers.google.com/google-ads/api/reference/rpc/v25/Customer), [v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Общие UI notifications | Общего `NotificationsService` нет | Нет | Восстанавливать только известные события polling-ом | [v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |

## 3. Advertiser identity verification

| Данные / действие | Service/field | Поддержка | Ограничение | Источник и доказательство |
|---|---|---|---|---|
| Требуется ли verification | `IdentityVerificationService.GetIdentityVerification` | Полная | Пустой response означает «не требуется» | [Verification guide](https://developers.google.com/google-ads/api/docs/account-management/advertiser-identity-verification), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Program | `IdentityVerification.verification_program` | Полная | API поддерживает только `ADVERTISER_IDENTITY_VERIFICATION` | [IdentityVerification](https://developers.google.com/google-ads/api/reference/rpc/v25/IdentityVerification), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Start/completion deadline | `verification_start_deadline_time`, `verification_completion_deadline_time` | Полная | Строковое время надо нормализовать и хранить с raw value | [IdentityVerificationRequirement](https://developers.google.com/google-ads/api/reference/rpc/v25/IdentityVerificationRequirement), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Progress | `program_status` | Полная | `PENDING_USER_ACTION`, `PENDING_REVIEW`, `SUCCESS`, `FAILURE` | [Status enum](https://developers.google.com/google-ads/api/reference/rpc/v25/IdentityVerificationProgramStatusEnum.IdentityVerificationProgramStatus), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Action URL | `verification_progress.action_url` | Полная, если session создана | URL не логировать полностью и не экспортировать | [IdentityVerificationProgress](https://developers.google.com/google-ads/api/reference/rpc/v25/IdentityVerificationProgress), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Expiration | `invitation_link_expiration_time` | Полная | После истечения session можно начать заново | [IdentityVerificationProgress](https://developers.google.com/google-ads/api/reference/rpc/v25/IdentityVerificationProgress), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Polling | `GetIdentityVerification` | Частичная | Более строгий per-minute limit; число не опубликовано; cache + long interval | [Verification guide](https://developers.google.com/google-ads/api/docs/account-management/advertiser-identity-verification), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; точный лимит `UNKNOWN` |
| Start verification | `StartIdentityVerification` | Технически поддерживается | Не включать в первую action surface; требует отдельного подтверждения | [Verification guide](https://developers.google.com/google-ads/api/docs/account-management/advertiser-identity-verification), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Payment/card verification | Нет поля/service | Нет | Не смешивать с advertiser identity | [v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |

## 4. Метрики и свойства основной таблицы

Общая задержка: большинство clicks/impressions/conversions - до 3 часов,
non-last-click conversions - до 15 часов, Analytics imports - 12/24 часа;
география, search terms, impression share и reach могут обновляться реже.
[Data freshness](https://support.google.com/google-ads/answer/2544985?hl=en-ca),
Google Ads reporting/v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

| Показатель | Точное поле v25 | Уровни / совместимые сегменты | Сегодня / ограничения | Размещение / аналог FBTOOL | Источник и доказательство |
|---|---|---|---|---|---|
| Расход | `metrics.cost_micros` | customer, campaign, ad group, ad; date/hour/device/network по совместимости | Да; micros, валюта customer | Основная; аналог есть | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Показы | `metrics.impressions` | Те же основные performance resources | Да; zero rows могут отсутствовать | Основная; аналог есть | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), [zero metrics](https://developers.google.com/google-ads/api/docs/reporting/zero-metrics), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Клики | `metrics.clicks` | Основные performance resources | Да; возможны поздние invalid-traffic adjustments | Основная; аналог есть | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), [freshness](https://support.google.com/google-ads/answer/2544985?hl=en-ca), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| CTR | `metrics.ctr` | Основные performance resources | Да | Основная; аналог есть | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Average CPC | `metrics.average_cpc` | Основные performance resources | Да, micros | Основная; аналог есть | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Average CPM | `metrics.average_cpm` | Основные performance resources | Да, micros | Детали/column chooser | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Google conversions | `metrics.conversions` | Customer/campaign/ad group/ad; `segments.conversion_action` при совместимости | Да, но conversion lag | Основная; аналог FBTOOL частичный без внешнего tracker | [conversion reporting](https://developers.google.com/google-ads/api/docs/conversions/reporting), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| All conversions | `metrics.all_conversions` | Аналогично | Да, состав шире `conversions` | Детали | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Conversion value | `metrics.conversions_value` | Аналогично | Да; модель attribution влияет на задержку | Детали | [conversion reporting](https://developers.google.com/google-ads/api/docs/conversions/reporting), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Google CPA | `metrics.cost_per_conversion` | Основные performance resources | Да; не применять rules до conversion-delay guard | Основная | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), [freshness](https://support.google.com/google-ads/answer/2544985?hl=en-ca), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Interaction rate | `metrics.interaction_rate` | По поддерживаемым форматам | Да; смысл interaction зависит от формата | Детали | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Video views | `metrics.video_trueview_views` | Campaign/ad/video и поддерживаемые Demand Gen views | Да; проверить query combination на Demand Gen | Детали | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), v25, 2026-07-27, `REQUIRES_LIVE_VALIDATION` |
| Video view rate | `metrics.video_trueview_view_rate` | Campaign/ad/video | Да; проверить query combination | Детали | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), v25, 2026-07-27, `REQUIRES_LIVE_VALIDATION` |
| Engagements | `metrics.engagements` | Поддерживаемые campaign/ad/video resources | Да | Детали | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Invalid clicks | `metrics.invalid_clicks`, `invalid_click_rate`, `general_invalid_clicks`, `general_invalid_click_rate` | Customer/campaign по compatibility metadata | Да, но возможны поздние корректировки | Детали/диагностика | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), [freshness](https://support.google.com/google-ads/answer/2544985?hl=en-ca), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Impression share | `metrics.content_impression_share` и content lost-by-budget/rank; search variants только для Search | Channel-specific | Не обещать для каждой Demand Gen кампании; комбинацию проверить | Детали, не default | [metrics](https://developers.google.com/google-ads/api/fields/v25/metrics), v25, 2026-07-27, `REQUIRES_LIVE_VALIDATION` |
| Daily budget | `campaign.campaign_budget` + `campaign_budget.amount_micros` | Campaign/budget | Current state, не metric | Основная/детали | [campaign](https://developers.google.com/google-ads/api/fields/v25/campaign), [CampaignBudget](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignBudget), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Bidding strategy | `campaign.bidding_strategy_type` | Campaign | Current state | Детали/column chooser | [campaign](https://developers.google.com/google-ads/api/fields/v25/campaign), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Campaign status | `campaign.status` | Campaign | Configured status | Основная в campaign mode | [campaign](https://developers.google.com/google-ads/api/fields/v25/campaign), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Serving status | `campaign.primary_status`, `campaign.primary_status_reasons` | Campaign | Причины зависят от доступности Google | Основная status + детали reason | [campaign](https://developers.google.com/google-ads/api/fields/v25/campaign), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Start/end | `campaign.start_date`, `campaign.end_date` | Campaign | Account timezone semantics | Детали | [campaign](https://developers.google.com/google-ads/api/fields/v25/campaign), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Optimization score | `campaign.optimization_score` или `customer.optimization_score` по resource | Customer/campaign | Может быть null/не применим | Детали, не default | [campaign](https://developers.google.com/google-ads/api/fields/v25/campaign), [customer](https://developers.google.com/google-ads/api/fields/v25/customer), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| YouTube social | `metrics.youtube_comments`, `youtube_likes`, `youtube_shares` | v25: customer/campaign/ad group/ad/asset/video | Новый v25 набор; только применимые видео | Детали | [v25 release notes](https://developers.google.com/google-ads/api/docs/release-notes#v25), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |

### 4.1. Уровни и сегменты

| Представление | Базовый resource | Идентификация | Сегменты / примечание | Источник и доказательство |
|---|---|---|---|---|
| Account | `customer` | `customer.id` | `segments.date/hour/device/ad_network_type` по compatibility | [customer fields](https://developers.google.com/google-ads/api/fields/v25/customer), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Campaign | `campaign` | `campaign.resource_name/id/name` | Основная Demand Gen таблица; фильтр `advertising_channel_type = DEMAND_GEN` | [campaign fields](https://developers.google.com/google-ads/api/fields/v25/campaign), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Ad group | `ad_group` | `ad_group.resource_name/id/name` | Date/hour/device/network по metadata | [ad_group fields](https://developers.google.com/google-ads/api/fields/v25/ad_group), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Ad | `ad_group_ad` | `ad_group_ad.resource_name`, `ad.id` | Performance + primary/policy status | [ad_group_ad fields](https://developers.google.com/google-ads/api/fields/v25/ad_group_ad), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Ad-asset link | `ad_group_ad_asset_view` | ad + asset + field type | Demand Gen performance/policy в контексте связи | [ad_group_ad_asset_view](https://developers.google.com/google-ads/api/fields/v25/ad_group_ad_asset_view), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Asset | `asset` | `asset.resource_name/id/type` | Общая агрегация может терять link context | [asset fields](https://developers.google.com/google-ads/api/fields/v25/asset), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Video | `video` | video resource/YouTube ID | Video metrics; v25 social metrics | [video fields](https://developers.google.com/google-ads/api/fields/v25/video), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Conversion action | Основной resource + `segments.conversion_action` | Conversion action resource name | Разбивает conversions; может увеличить rows | [conversion reporting](https://developers.google.com/google-ads/api/docs/conversions/reporting), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Location | `geographic_view`, `user_location_view` | Geo target constants | Данные обновляются не мгновенно; interpretation зависит от view | [geographic_view](https://developers.google.com/google-ads/api/fields/v25/geographic_view), [freshness](https://support.google.com/google-ads/answer/2544985?hl=en-ca), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |

## 5. Часовые пояса

| Режим | Можно ли точно | Что хранить | Ограничение | Источник и доказательство |
|---|---|---|---|---|
| Локальный день аккаунта | Да | `customer.time_zone`, raw `segments.date/hour`, `synced_at` | Пользователь сравнивает разные абсолютные окна | [Timezone help](https://support.google.com/google-ads/answer/17006726?hl=en), v25 reporting, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Московские сутки UTC+3, whole-hour offset | Да из hourly buckets | Raw local date/hour, IANA zone, UTC start/end, Moscow date | DST преобразовывать библиотекой zoneinfo, не фиксированным offset | [Customer](https://developers.google.com/google-ads/api/reference/rpc/v25/Customer), [timezone help](https://support.google.com/google-ads/answer/17006726?hl=en), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Московские сутки, half-hour offset | Только приблизительно | Те же поля + `boundary_precision=APPROXIMATE_30M` | API даёт hour bucket, а граница проходит внутри bucket | [Timezone help](https://support.google.com/google-ads/answer/17006726?hl=en), v25, 2026-07-27, `REQUIRES_LIVE_VALIDATION` |
| DST repeated/missing hour | Требует contract test | IANA zone + raw hour + UTC conversion metadata | Не дедуплицировать только по local date/hour | [Timezone help](https://support.google.com/google-ads/answer/17006726?hl=en), v25, 2026-07-27, `REQUIRES_LIVE_VALIDATION` |

## 6. Модерация

| Состояние | Field/resource | Поддержка | UI и хранение | Источник и доказательство |
|---|---|---|---|---|
| Approval | `ad_group_ad.policy_summary.approval_status` | `APPROVED`, `APPROVED_LIMITED`, `AREA_OF_INTEREST_ONLY`, `DISAPPROVED` | Current + event on change | [PolicyApprovalStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/PolicyApprovalStatusEnum.PolicyApprovalStatus), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Review | `policy_summary.review_status` | `REVIEW_IN_PROGRESS`, `REVIEWED`, `UNDER_APPEAL`, `ELIGIBLE_MAY_SERVE` | Синий pending status + timeline | [PolicyReviewStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/PolicyReviewStatusEnum.PolicyReviewStatus), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Policy topics | `policy_topic_entries` | Полная в пределах returned evidence/constraints | Хранить normalized category + redacted raw diagnostic | [AdGroupAdPolicySummary](https://developers.google.com/google-ads/api/reference/rpc/v25/AdGroupAdPolicySummary), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Effective status/reasons | `ad_group_ad.primary_status`, `primary_status_reasons` | Полная | Не смешивать configured status и serving status | [ad_group_ad](https://developers.google.com/google-ads/api/fields/v25/ad_group_ad), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Asset policy | `ad_group_ad_asset_view.policy_summary` | Поддерживается для Demand Gen links | Детализация ad -> asset -> field type | [ad_group_ad_asset_view](https://developers.google.com/google-ads/api/fields/v25/ad_group_ad_asset_view), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Повторная проверка/appeal | Общего method нет | Нет как универсальная операция | Ссылка в Google Ads UI; не автоматизировать | [v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Policy exemption в mutate | `PolicyValidationParameter.ignorable_policy_topics` | Частичная | Не называть appeal; только для поддерживаемого mutate и после отдельного дизайна | [PolicyValidationParameter](https://developers.google.com/google-ads/api/reference/rpc/v25/PolicyValidationParameter), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |

## 7. Ручные действия

| Действие | Official API | Поддержка / безопасная схема | Источник и доказательство |
|---|---|---|---|
| Campaign PAUSE/ENABLE | `CampaignService.MutateCampaigns`, update `campaign.status` | Да; fresh read -> `validate_only` -> confirm -> mutate -> read-back | [CampaignService](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignService), [MutateCampaignsRequest](https://developers.google.com/google-ads/api/reference/rpc/v25/MutateCampaignsRequest), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Массовый campaign status | Несколько `CampaignOperation` одного customer | Да; group by customer; `partial_failure=True` только для независимых rows | [Partial failures](https://developers.google.com/google-ads/api/docs/best-practices/partial-failures), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Ad group status | `AdGroupService.MutateAdGroups` | Да; та же preflight/confirm схема | [AdGroupService](https://developers.google.com/google-ads/api/reference/rpc/v25/AdGroupService), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Ad status | `AdGroupAdService.MutateAdGroupAds` | Да; та же схема | [MutateAdGroupAdsRequest](https://developers.google.com/google-ads/api/reference/rpc/v25/MutateAdGroupAdsRequest), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Новый бюджет | `CampaignBudgetService.MutateCampaignBudgets`, `amount_micros` | Да; валюта customer, min/max guard, shared-budget impact preview | [CampaignBudgetService](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignBudgetService), [CampaignBudget](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignBudget), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Бюджет +/- сумма или % | Локально вычислить новый `amount_micros`, затем тот же mutate | Да; rounding и final absolute amount показывать до confirm | [CampaignBudget](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignBudget), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Suspended/canceled/closed | Mutate может быть запрещён состоянием/permission | Частичная; UI блокирует action после fresh account status | [CustomerStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerStatusEnum.CustomerStatus), v25, 2026-07-27, `REQUIRES_LIVE_VALIDATION` для точного error code |
| `validate_only` | Поле mutate request | Да; проверяет, но не исполняет | [MutateAdGroupAdsRequest](https://developers.google.com/google-ads/api/reference/rpc/v25/MutateAdGroupAdsRequest), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| `partial_failure` | Поле поддерживаемых mutate requests | Да; successes commit, operation errors возвращаются отдельно | [Partial failures](https://developers.google.com/google-ads/api/docs/best-practices/partial-failures), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Server idempotency key | Общего поля нет | Нет; локальный key + read-back, без blind retry ambiguous mutate | [MutateGoogleAdsRequest](https://developers.google.com/google-ads/api/reference/rpc/v25/MutateGoogleAdsRequest), v25, 2026-07-27, `NOT_SUPPORTED` |
| Request ID | Response metadata / `GoogleAdsFailure`; stream response field | Да на success/failure с оговоркой для stream | [API errors](https://developers.google.com/google-ads/api/docs/best-practices/understand-api-errors), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |

## 8. Local rules, history и notifications

| Возможность | Google API | Решение | Источник и доказательство |
|---|---|---|---|
| Google Ads UI Automated Rules resource | Нет в v25 index | Локальный rules engine в PostgreSQL + scheduler/worker | [v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Общий Notifications API | Нет в v25 index | Локальные alerts из state/policy/verification/error/change transitions | [v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Dirty detector | `change_status` | До 3 минут; 90 дней; latest change per resource; LIMIT <= 10 000 | [ChangeStatus](https://developers.google.com/google-ads/api/docs/change-status), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Field-level history | `change_event` | Old/new, changed_fields, user_email if visible, client_type; 30 дней; LIMIT <= 10 000 | [ChangeEvent](https://developers.google.com/google-ads/api/docs/change-event), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Полный UI Change History | Не гарантирован | Архивировать API events, но честно подписывать источник и неполноту | [ChangeEvent limitations](https://developers.google.com/google-ads/api/docs/change-event), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |

## 9. Billing и финансы

| Функция | Поддержка | Resource/service/fields | Ограничение | Источник и доказательство |
|---|---|---|---|---|
| Billing setup | Да | `BillingSetup`, status/start/end, payments account info | Только billing workflow monthly invoicing | [Billing setup](https://developers.google.com/google-ads/api/docs/billing/billing-setups), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Payments account | Да | `PaymentsAccountService.ListPaymentsAccounts`; ID/name/currency/profile/paying manager | Доступ зависит от authenticating manager | [PaymentsAccountService](https://developers.google.com/google-ads/api/reference/rpc/v25/PaymentsAccountService), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Payments profile identifiers | Частично | `payments_profile_id`, `payments_profile_name` | Не card details и не verification | [PaymentsAccount](https://developers.google.com/google-ads/api/reference/rpc/v25/PaymentsAccount), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Billing status | Частично | `BillingSetup.status`: `PENDING`, `APPROVED_HELD`, `APPROVED`, `CANCELLED` | Не эквивалент automatic-pay debt status | [Billing setup status](https://developers.google.com/google-ads/api/docs/billing/billing-setups#billing_setup_status), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Account budget | Да для monthly invoicing | `AccountBudget`, spending limit, `amount_served_micros`, adjustments, status | Изменения через proposals; первая версия read-only | [AccountBudget](https://developers.google.com/google-ads/api/reference/rpc/v25/AccountBudget), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Invoices | Да для monthly invoicing | `InvoiceService`, issue/due date, totals/tax/adjustments, budget summaries, PDF URL | Месячные документы, не real-time balance | [Invoice](https://developers.google.com/google-ads/api/reference/rpc/v25/Invoice), [billing overview](https://developers.google.com/google-ads/api/docs/billing/overview), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Outstanding balance automatic payments | Нет | Нет общего field/resource | Будущий finance adapter, не выводить догадку | [v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Automatic payment threshold | Нет | Нет | Будущий card/finance provider только отдельным проектом | [v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Next automatic charge | Нет | Нет | Показывать «Недоступно через Google Ads API» | [v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Card charge history | Нет | Нет | Не путать с monthly invoices | [billing overview](https://developers.google.com/google-ads/api/docs/billing/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Payment verification | Нет | Нет | Отличать от advertiser identity | [Identity verification guide](https://developers.google.com/google-ads/api/docs/account-management/advertiser-identity-verification), v25, 2026-07-27, `NOT_SUPPORTED` |
| Failed payment reason | Нет общего read field | Нет | Ошибка отдельной операции не равна состоянию payment profile | [v25 errors/index](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Suspicious payment activity | Нет | Нет | Не делать вывод из `SUSPENDED` | [CustomerStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerStatusEnum.CustomerStatus), v25, 2026-07-27, `NOT_SUPPORTED` |

## 10. Ошибки и retry

| Категория | Хранить | Retry policy | Источник и доказательство |
|---|---|---|---|
| Google error | canonical code, granular `error_code`, message, field path, request ID, customer/service/method, attempt, redacted diagnostic | По конкретному классу | [Understand API errors](https://developers.google.com/google-ads/api/docs/best-practices/understand-api-errors), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Transient | `UNAVAILABLE`, `DEADLINE_EXCEEDED`, `INTERNAL`, `UNKNOWN`, `ABORTED` | Bounded exponential backoff + jitter | [Error handling](https://developers.google.com/google-ads/api/docs/best-practices/understand-api-errors), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Quota | `RESOURCE_EXHAUSTED`, quota details | Отложить, снизить polling; не tight-loop | [API limits](https://developers.google.com/google-ads/api/docs/best-practices/quotas), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Auth/permission | `UNAUTHENTICATED`, `PERMISSION_DENIED`, Google auth/authorization codes | Не retry без исправления credentials/access | [Error types](https://developers.google.com/google-ads/api/docs/best-practices/error-types), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Validation/policy | `INVALID_ARGUMENT`, field path, policy details | Не retry без изменения input; показать понятное объяснение | [Error types](https://developers.google.com/google-ads/api/docs/best-practices/error-types), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Ambiguous mutate timeout | Local action fingerprint + pre-state + intended state | Не повторять вслепую; fresh read/ChangeEvent reconciliation | [Mutate request](https://developers.google.com/google-ads/api/reference/rpc/v25/MutateGoogleAdsRequest), v25, 2026-07-27, `NOT_SUPPORTED` для server idempotency |
