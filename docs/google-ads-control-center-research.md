# Исследование «Центра контроля» Google Ads

Дата проверки: **2026-07-27**. Режим работы: исследование и проектирование, без
изменения приложения и без live-запросов к Google Ads.

## 1. Как читать доказательства

Каждое техническое утверждение сопровождается источником, версией, датой и одной
из обязательных пометок:

- `CONFIRMED_BY_OFFICIAL_DOCS` - подтверждено официальной документацией Google
  Ads API или официальной базой FBTOOL;
- `CONFIRMED_BY_CURRENT_CODE` - подтверждено текущим исходным кодом проекта;
- `REQUIRES_LIVE_VALIDATION` - должно быть проверено безопасным read-only
  запросом после получения Basic Access;
- `NOT_SUPPORTED` - в официальном Google Ads API v25 нет требуемой общей
  возможности или поля;
- `UNKNOWN` - официальный источник не позволяет сделать достоверный вывод.

Для проектных рекомендаций используется слово «решение». Это не утверждение о
наличии функции в Google Ads API. Все пути к коду ниже относятся к текущей ветке
проекта на дату проверки.

## 2. Краткий вывод

1. Полноценный «Центр контроля» реализуем на официальном Google Ads API без
   браузерной автоматизации. Google отдаёт иерархию MCC, статусы аккаунтов,
   статистику, кампании, объявления, policy summaries, advertiser identity
   verification, часть monthly-invoicing billing и историю изменений.
   [Google Ads API v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview),
   v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
2. Текущий Developer Token с Test Account Access не может читать production MCC
   `5589335362`; для production нужны Basic или Standard Access.
   [Developer Token](https://developers.google.com/google-ads/api/docs/api-policy/developer-token),
   все поддерживаемые версии, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
3. На дату проверки последняя выпущенная версия - v25 от 2026-07-22. Текущий
   адаптер проекта v24.2 ещё работает до июня 2027 года, но уже считается
   deprecated; для нового модуля сначала нужен совместимый адаптер v25 и Python
   client library не ниже `31.2.0`.
   [Release notes](https://developers.google.com/google-ads/api/docs/release-notes),
   [sunset table](https://developers.google.com/google-ads/api/docs/sunset-dates),
   v25/v24.2, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
4. Google Ads API не даёт общий поток уведомлений Google Ads UI, точную
   account-level причину каждой блокировки, автоматические правила из интерфейса
   Google Ads, payment threshold/следующее автосписание/историю карточных
   списаний или payment verification для automatic payments.
   [v25 service/resource index](https://developers.google.com/google-ads/api/reference/rpc/v25/overview),
   [billing overview](https://developers.google.com/google-ads/api/docs/billing/overview),
   v25, 2026-07-27, `NOT_SUPPORTED`.
5. Поэтому финальная архитектура должна хранить локальные current states,
   snapshots, events, sync runs и структурированные ошибки, а уведомления и
   автоправила восстанавливать локально через polling, scheduler и worker.
   Текущий scheduler уже содержит подходящие шаблоны блокировок, heartbeat,
   retry/backoff и circuit breaker.
   [schedule_tasks.py](../backend/app/jobs/schedule_tasks.py),
   текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.

## 3. Аудит текущего проекта

### 3.1. Карта пользовательских разделов

| Область | Что реально сделано | Оценка | Переиспользование / запрет дублирования | Доказательство |
|---|---|---|---|---|
| «Статистика» | Выбор подключения, ручной запуск фоновой синхронизации и таблица `date/customer/impressions/clicks/cost/conversions`; интерфейс опрашивает локальный API | Частично; готово к LIVE только для узкого запроса после Basic Access; требует переработки для уровней и фильтров | Переиспользовать endpoint/job как переходный источник, затем читать общие monitoring snapshots; старую страницу не удалять и не дублировать её назначение | [OperationsPages.tsx](../frontend/src/pages/OperationsPages.tsx), [operations.py](../backend/app/api/routes/operations.py), [tasks.py](../backend/app/jobs/tasks.py), текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| «Модерация» | Ручная синхронизация `ad_group_ad.policy_summary.approval_status` и строковых policy topics; хранится только последний срез | Частично; нет `review_status`, primary status/reasons, asset policy и истории | Старую страницу оставить как простой журнал; новый раздел использует расширенные policy snapshots/events | [adapter.py](../backend/app/google_ads/versions/v24_2/adapter.py), [models.py](../backend/app/db/models.py), текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| «Финансы» | Настройка и синхронизация внешнего Brocard-профиля через реальный HTTP client | Частично и только сторонний источник; не Google billing | Не делать Brocard обязательным; оставить существующий раздел и предусмотреть будущий `FinanceProvider` | [OperationsPages.tsx](../frontend/src/pages/OperationsPages.tsx), [brocard.py](../backend/app/integrations/brocard.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| «Уведомления» | Локальные записи `Notification`, список и read/unread | Частично; нет генератора полного набора Google-событий | Переиспользовать хранилище/паттерн чтения, но добавить типизированные monitoring alerts без копирования существующего экрана | [operations.py](../backend/app/api/routes/operations.py), [models.py](../backend/app/db/models.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| «Аккаунты MCC» | Таблица сохранённых `CustomerAccount`; имя, ID, MCC, валюта, timezone, status, test/hidden | Частично; нет полной иерархии, first/last seen, detached, history, tags, notes и freshness | Сохранить как административный справочник подключения; «Центр контроля» читает общую модель наблюдения | [AccountsPage.tsx](../frontend/src/pages/AccountsPage.tsx), [accounts.py](../backend/app/api/routes/accounts.py), текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| «Подключения Google» | OAuth/service account, зашифрованные credentials, read-only MCC test, запуск sync аккаунтов, disconnect | Рабочая основа; OAuth LIVE зависит от access level | Переиспользовать без переноса секретов в новый модуль; не создавать второй экран подключения | [ConnectionsPage.tsx](../frontend/src/pages/ConnectionsPage.tsx), [google_connections.py](../backend/app/api/routes/google_connections.py), текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| «Группы запуска» | Метрики и подтверждаемые ENABLE/PAUSE только для `CampaignInstance`, созданных загрузчиком | Полностью для своего ограниченного контекста; часть путей работает в SIMULATION | Не расширять эти таблицы на все Google-кампании; переиспользовать UX подтверждения и аудит | [launch_groups.py](../backend/app/api/routes/launch_groups.py), [tasks.py](../backend/app/jobs/tasks.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| «Задания» | `Job`/`JobEvent`, idempotency key, Celery-статусы и события | Рабочая общая инфраструктура | Переиспользовать оболочку задания; добавить monitoring-specific run/item таблицы | [models.py](../backend/app/db/models.py), [tasks.py](../backend/app/jobs/tasks.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| «Журнал» | Локальный `AuditLog` для действий приложения | Рабочая основа, но это не Google Change History | Переиспользовать и связывать с `action_request`, `action_run`, Google request ID | [models.py](../backend/app/db/models.py), [audit.py](../backend/app/api/routes/audit.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |

### 3.2. Google Ads adapter

- `test_connection()` уже правильно использует `GoogleAdsService.search` с
  GAQL по ресурсу `customer`, проверяет MCC и сохраняет Google errors/request ID.
  [adapter.py](../backend/app/google_ads/versions/v24_2/adapter.py),
  текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.
- `list_customer_accounts()` запрашивает `customer_client` только с
  `WHERE level <= 1`; текущая реализация не строит полную рекурсивную иерархию и
  не сохраняет `level`.
  [adapter.py](../backend/app/google_ads/versions/v24_2/adapter.py),
  текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.
- `fetch_statistics()` агрегирует только базовые campaign metrics за
  `LAST_30_DAYS` в строки account/day. Отдельных campaign/ad group/ad/asset
  snapshots нет.
  [adapter.py](../backend/app/google_ads/versions/v24_2/adapter.py),
  текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.
- `fetch_moderation()` читает только часть `ad_group_ad.policy_summary`;
  `review_status`, `primary_status`, `primary_status_reasons` и
  `ad_group_ad_asset_view.policy_summary` отсутствуют.
  [adapter.py](../backend/app/google_ads/versions/v24_2/adapter.py),
  текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.
- `change_campaign_status()` умеет только `ENABLED`/`PAUSED`, использует
  `partial_failure=False`, не делает обязательный `validate_only` preflight и
  применяется только через uploader-owned campaign instances.
  [adapter.py](../backend/app/google_ads/versions/v24_2/adapter.py),
  [tasks.py](../backend/app/jobs/tasks.py), текущий код/v24.2,
  2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.
- Адаптер v24.2 жёстко выбирается фабрикой; registry нескольких версий и
  compatibility contract для monitoring-запросов отсутствуют.
  [service.py](../backend/app/google_ads/service.py),
  [interface.py](../backend/app/google_ads/interface.py), текущий код/v24.2,
  2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.

### 3.3. PostgreSQL, worker и scheduler

- `CustomerAccount` не содержит parent customer, hierarchy level, link status,
  first/last seen, detached/archive markers, GEO, notes, tags и freshness.
  [models.py](../backend/app/db/models.py), текущий код, 2026-07-27,
  `CONFIRMED_BY_CURRENT_CODE`.
- `ModerationRecord` хранит только последний approval status/topics, а
  `MetricSnapshot` - JSON account/day. Истории state transitions и общих
  campaign/ad snapshots нет.
  [models.py](../backend/app/db/models.py), текущий код, 2026-07-27,
  `CONFIRMED_BY_CURRENT_CODE`.
- Sync аккаунтов выполняется синхронно в HTTP request, только upsert-ит найденные
  записи и не отмечает исчезнувшие связи.
  [accounts.py](../backend/app/api/routes/accounts.py), текущий код/v24.2,
  2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.
- Статистика и модерация запускаются вручную; в Celery beat есть регулярный
  dispatcher uploader schedules, но нет monitoring polling.
  [operations.py](../backend/app/api/routes/operations.py),
  [celery_app.py](../backend/app/jobs/celery_app.py), текущий код,
  2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.
- Существующий schedule worker уже реализует `FOR UPDATE SKIP LOCKED`,
  heartbeat/recovery, parallel/hour/day limits, retry/backoff, idempotency и
  circuit breaker. Эти алгоритмы можно извлечь в общие helpers, не используя
  uploader schedule tables как monitoring tables.
  [schedule_tasks.py](../backend/app/jobs/schedule_tasks.py),
  [models.py](../backend/app/db/models.py), текущий код, 2026-07-27,
  `CONFIRMED_BY_CURRENT_CODE`.

### 3.4. Сводная готовность технических узлов

| Узел | Фактическое состояние | Классификация для «Центра контроля» | Переиспользование / запрет дублирования | Доказательство |
|---|---|---|---|---|
| Выбор версии adapter | `service.py` всегда создаёт `GoogleAdsV242Adapter`, даже если версия записана в connection; `capability_registry.py` описывает продуктовые поля Demand Gen, но не выбирает adapter | Требует переработки до v25; текущий v24.2 готов к существующим LIVE-вызовам после соответствующего access level | Оставить один adapter interface и добавить version registry; не создавать второй путь credentials/OAuth | [service.py](../backend/app/google_ads/service.py), [capability_registry.py](../backend/app/google_ads/capability_registry.py), текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Google resource names | `CampaignInstance.resource_names` и `CampaignStatusAction.resource_names` хранят списки в JSONB; `CreativeAssignment.google_resource_name` хранит одну ссылку | Полностью для ограниченного uploader workflow, частично для общего каталога; нет нормализованных campaign/ad group/ad/asset identities и FK между ними | Переиспользовать уже сохранённые names при bootstrap uploader-owned кампаний, затем сверять с Google; не переносить JSONB-списки как основную monitoring model | [models.py](../backend/app/db/models.py), [tasks.py](../backend/app/jobs/tasks.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Google errors и Request ID | `AdapterCheckResult` и `PlanExecutionResult` поддерживают request IDs и structured issues; connection check пишет request ID в `AuditLog`, deployment/status actions сохраняют IDs. Account/statistics/moderation sync в части ошибок сворачивает диагностику в HTTP/job text | Реализовано частично; пригодно для LIVE в существующих flows, но требует общей redacted `google_api_errors` модели | Переиспользовать parser Google exceptions и текущие result contracts; не создавать второй несовместимый parser | [interface.py](../backend/app/google_ads/interface.py), [adapter.py](../backend/app/google_ads/versions/v24_2/adapter.py), [google_connections.py](../backend/app/api/routes/google_connections.py), [tasks.py](../backend/app/jobs/tasks.py), текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Ручные `ENABLE/PAUSE` | Работают для `CampaignInstance`, принадлежащих launch group; SIMULATION использует mock, LIVE вызывает `GoogleAdsService.Mutate` и сохраняет результат | Полностью в своём ограниченном контексте; готово к LIVE после Basic Access и явного подтверждения; недостаточно для произвольных Google campaigns | Переиспользовать permission/password-confirm UX, audit и per-item result; не расширять `CampaignStatusAction` до универсальной monitoring action model | [launch_groups.py](../backend/app/api/routes/launch_groups.py), [tasks.py](../backend/app/jobs/tasks.py), [adapter.py](../backend/app/google_ads/versions/v24_2/adapter.py), текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Audit trail | `AuditLog` фиксирует локальные действия пользователя/worker, но не импортирует Google `ChangeEvent` | Рабочая основа, реализована частично относительно целевой истории | Сохранить `AuditLog` как локальный источник и связать с action/sync IDs; не выдавать его за полный Google Change History | [models.py](../backend/app/db/models.py), [audit.py](../backend/app/api/routes/audit.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Notifications | `Notification` поддерживает severity/read state; worker создаёт в основном failure alerts | Частично; генератор account/policy/verification/change transitions отсутствует | Переиспользовать существующую выдачу и read/unread semantics либо общий notification facade; не дублировать пользовательский inbox | [models.py](../backend/app/db/models.py), [operations.py](../backend/app/api/routes/operations.py), [tasks.py](../backend/app/jobs/tasks.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Scheduler/worker | Deployment scheduler имеет locks, heartbeat, recovery, limits, retry/backoff и circuit breaker; monitoring beat/jobs отсутствуют | Полностью для schedule-owned workflow, не реализовано для monitoring | Извлечь общие primitives; не использовать deployment schedule rows как monitoring policy/run rows | [schedule_tasks.py](../backend/app/jobs/schedule_tasks.py), [celery_app.py](../backend/app/jobs/celery_app.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Brocard/finance | Есть отдельный HTTP client, profile/snapshot и UI для внешнего provider | Реализовано частично как самостоятельный модуль; это не Google billing и не обязательная зависимость | Оставить без изменений; для будущего использовать независимый `FinanceProvider` extension point | [brocard.py](../backend/app/integrations/brocard.py), [models.py](../backend/app/db/models.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |

Итог аудита: ни название страницы, ни наличие таблицы не считаются доказательством
полной функции. Для нового раздела можно безопасно переиспользовать OAuth,
adapter contract, jobs/audit, exception parsing и scheduler primitives, но
нормализованный monitoring catalog, history, polling, saved views и rules
отсутствуют. Это вывод из приведённого текущего кода, 2026-07-27,
`CONFIRMED_BY_CURRENT_CODE`.

## 4. Подтверждённые возможности Google Ads API

### 4.1. MCC, аккаунты и связи

- `CustomerClient` возвращает прямых и непрямых клиентов, включая сам MCC, и
  поля `id`, `client_customer`, `level`, `manager`, `test_account`, `hidden`,
  `status`, `descriptive_name`, `currency_code`, `time_zone`.
  [CustomerClient](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerClient),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- Для точного дерева официальный алгоритм начинает с root MCC и рекурсивно
  запрашивает менеджеров. Root query показывает всех потомков и их расстояние,
  но запросы подменеджеров нужны для точного parent edge.
  [Get account hierarchy](https://developers.google.com/google-ads/api/docs/account-management/get-account-hierarchy),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- `CustomerClientLink.status` показывает состояние конкретной manager-client
  связи: `ACTIVE`, `CANCELED`, `INACTIVE`, `PENDING`, `REFUSED`.
  [customer_client_link fields](https://developers.google.com/google-ads/api/fields/v25/customer_client_link),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- `CustomerStatus` позволяет отличить `ENABLED`, `SUSPENDED`, `CANCELED` и
  `CLOSED`. `SUSPENDED` подтверждает, что аккаунт не может обслуживать рекламу,
  но общего поля с точной причиной suspension нет.
  [CustomerStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerStatusEnum.CustomerStatus),
  [Customer](https://developers.google.com/google-ads/api/reference/rpc/v25/Customer),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` для статуса;
  `NOT_SUPPORTED` для общей точной причины.
- Даты появления/исчезновения и история после отвязки не приходят из Google.
  Их надо вычислять локально как `first_seen_at`, `last_seen_at`,
  `detached_at`, не удаляя прежние snapshots.
  [CustomerClient reference](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerClient),
  v25, 2026-07-27, `NOT_SUPPORTED` для готовых исторических дат.

### 4.2. Advertiser identity verification

- `IdentityVerificationService.GetIdentityVerification` возвращает требование,
  deadline и progress. Пустой список означает, что обязательная advertiser
  identity verification для аккаунта не требуется.
  [Advertiser identity verification](https://developers.google.com/google-ads/api/docs/account-management/advertiser-identity-verification),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- Поддерживаются `PENDING_USER_ACTION`, `PENDING_REVIEW`, `SUCCESS`, `FAILURE`;
  progress может содержать `action_url` и
  `invitation_link_expiration_time`.
  [status enum](https://developers.google.com/google-ads/api/reference/rpc/v25/IdentityVerificationProgramStatusEnum.IdentityVerificationProgramStatus),
  [progress](https://developers.google.com/google-ads/api/reference/rpc/v25/IdentityVerificationProgress),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- Метод имеет более строгий per-minute rate limit, чем обычные services; Google
  не публикует число в руководстве и рекомендует cache + long polling interval.
  [verification guide](https://developers.google.com/google-ads/api/docs/account-management/advertiser-identity-verification),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; точная величина лимита `UNKNOWN`.
- API поддерживает только программу `ADVERTISER_IDENTITY_VERIFICATION`; payment
  verification и проверка банковской карты этим service не покрываются.
  [verification guide](https://developers.google.com/google-ads/api/docs/account-management/advertiser-identity-verification),
  v25, 2026-07-27, `NOT_SUPPORTED` для payment verification.

### 4.3. Reporting и свежесть

- GAQL выполняется через `GoogleAdsService.Search` или `SearchStream`; один
  `SearchStream` считается одной API operation независимо от числа batches.
  [Reporting](https://developers.google.com/google-ads/api/docs/reporting/overview),
  [quotas](https://developers.google.com/google-ads/api/docs/best-practices/quotas),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- Доступны уровни `customer`, `campaign`, `ad_group`, `ad_group_ad`, `asset`,
  `video` и link view `ad_group_ad_asset_view`, а также сегменты даты, часа,
  устройства, сети, conversion action и отдельные geographic views.
  Совместимость конкретного набора fields/segments проверяется по reporting
  metadata и должна иметь отдельный GAQL contract test.
  [v25 reporting fields](https://developers.google.com/google-ads/api/fields/v25/overview),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
  конкретные Demand Gen combinations `REQUIRES_LIVE_VALIDATION`.
- Основные данные обычно запаздывают до 3 часов, non-last-click conversions -
  до 15 часов, Analytics imports - примерно 12/24 часа; некоторые гео,
  impression-share и reach отчёты обновляются реже. Значения могут быть
  скорректированы позже.
  [Data freshness](https://support.google.com/google-ads/answer/2544985?hl=en-ca),
  Google Ads reporting, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- При сегментации Google не возвращает строки, где все выбранные metrics равны
  нулю. Гранулярная история ограничена 37 месяцами, high-level и billing -
  11 годами.
  [Zero metrics](https://developers.google.com/google-ads/api/docs/reporting/zero-metrics),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

### 4.4. Часовые пояса

- `segments.date` и `segments.hour` формируются в timezone самого customer.
  Google Ads поддерживает часовые зоны с целым или получасовым GMT offset, но
  не quarter-hour offsets.
  [Google Ads timezone](https://support.google.com/google-ads/answer/17006726?hl=en),
  Google Ads reporting, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- «Локальный день аккаунта» можно показать точно, сохранив raw
  `segments.date/hour` и `customer.time_zone`.
  [Customer.time_zone](https://developers.google.com/google-ads/api/reference/rpc/v25/Customer),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- Для «Московских суток UTC+3» нужно хранить IANA timezone, raw local hour и
  UTC-границы окна. При получасовом смещении часовых buckets недостаточно для
  точной границы московских суток; результат будет приближённым на половину часа
  либо такие аккаунты надо исключать из точного итога.
  [timezone limitations](https://support.google.com/google-ads/answer/17006726?hl=en),
  v25, 2026-07-27, `REQUIRES_LIVE_VALIDATION` для поведения пограничного bucket.

### 4.5. Модерация

- `ad_group_ad.policy_summary` содержит `approval_status`, `review_status` и
  `policy_topic_entries`; отдельно доступны `primary_status` и
  `primary_status_reasons`.
  [ad_group_ad fields](https://developers.google.com/google-ads/api/fields/v25/ad_group_ad),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- Для Demand Gen связка ad-asset и её policy/performance читается через
  `ad_group_ad_asset_view`, а не только через общий `asset`.
  [ad_group_ad_asset_view](https://developers.google.com/google-ads/api/fields/v25/ad_group_ad_asset_view),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- Общей official API операции «подать account-level appeal» нет. Policy
  exemption в mutate через `PolicyValidationParameter.ignorable_policy_topics`
  не является общей апелляцией и не гарантирует eligibility.
  [PolicyValidationParameter](https://developers.google.com/google-ads/api/reference/rpc/v25/PolicyValidationParameter),
  v25, 2026-07-27, `NOT_SUPPORTED` для общей appeal.

### 4.6. Ручные действия, история и ошибки

- Статусы campaign/ad group/ad меняются update operations соответствующих
  services с `FieldMask`; campaign budget меняется через
  `CampaignBudgetService.MutateCampaignBudgets`.
  [Mutates](https://developers.google.com/google-ads/api/docs/mutating/overview),
  [CampaignService](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignService),
  [CampaignBudgetService](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignBudgetService),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- Mutate requests поддерживают `validate_only` и, для независимых operations,
  `partial_failure`. Shared `CampaignBudget` может влиять на несколько кампаний,
  поэтому preflight обязан показывать все связанные кампании.
  [MutateAdGroupAdsRequest](https://developers.google.com/google-ads/api/reference/rpc/v25/MutateAdGroupAdsRequest),
  [CampaignBudget](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignBudget),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- Общего server-side idempotency key для mutate в v25 reference нет. Локальная
  идемпотентность обязательна, а неоднозначный timeout нельзя слепо повторять:
  сначала read-back/ChangeEvent reconciliation.
  [Mutate request](https://developers.google.com/google-ads/api/reference/rpc/v25/MutateGoogleAdsRequest),
  v25, 2026-07-27, `NOT_SUPPORTED` для общего idempotency key.
- `ChangeStatus` даёт широкий dirty signal за 90 дней, максимум 10 000 строк и
  задержку до 3 минут. `ChangeEvent` даёт old/new values, changed fields,
  client type и видимый user email за последние 30 дней, тоже до 10 000 строк и
  с задержкой до 3 минут; не все UI-события представлены.
  [ChangeStatus](https://developers.google.com/google-ads/api/docs/change-status),
  [ChangeEvent](https://developers.google.com/google-ads/api/docs/change-event),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- `GoogleAdsFailure`/`GoogleAdsError` содержат granular error code, message,
  location/field path и request ID. Request ID доступен в успешных и ошибочных
  metadata, а streaming response несёт свой `request_id`.
  [Understand API errors](https://developers.google.com/google-ads/api/docs/best-practices/understand-api-errors),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

### 4.7. Billing, notifications и automated rules

- Официальные billing workflows (`BillingSetup`, `AccountBudget`,
  `PaymentsAccount`, `Invoice`) предназначены для monthly invoicing.
  [Billing overview](https://developers.google.com/google-ads/api/docs/billing/overview),
  [Billing setup](https://developers.google.com/google-ads/api/docs/billing/billing-setups),
  v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
- Outstanding automatic-pay balance, payment threshold, next card charge,
  card-charge history, failed-card reason, payment verification и suspicious
  payment activity не представлены этими resources.
  [v25 billing resources](https://developers.google.com/google-ads/api/reference/rpc/v25/overview),
  v25, 2026-07-27, `NOT_SUPPORTED`.
- В v25 service/resource index нет общего `NotificationsService` и ресурса
  Google Ads UI automated rules. События надо восстанавливать polling-ом, а
  rules engine делать локально.
  [v25 service/resource index](https://developers.google.com/google-ads/api/reference/rpc/v25/overview),
  v25, 2026-07-27, `NOT_SUPPORTED`.

## 5. Главные разрывы между текущим и целевым состоянием

| Разрыв | Последствие | Целевое решение | Основание |
|---|---|---|---|
| Adapter v24.2 после релиза v25 | Новые разработки стартуют на deprecated contract | Версионный registry, adapter v25, contract tests v24.2/v25, затем v25 default | [release/sunset](https://developers.google.com/google-ads/api/docs/sunset-dates), v25/v24.2, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Только прямые MCC children | Теряются точные parent edges и sub-manager структура | Полная рекурсивная hierarchy sync, current link state + history | [hierarchy guide](https://developers.google.com/google-ads/api/docs/account-management/get-account-hierarchy), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Упрощённые snapshots без истории | Нельзя объяснить бан, freshness или изменение | Additive current/snapshot/event/run/error tables | [models.py](../backend/app/db/models.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Ручные sync endpoints без общего scheduler | Данные быстро становятся stale | Quota-aware adaptive polling через отдельные queues | [operations.py](../backend/app/api/routes/operations.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Actions только uploader-owned | Нельзя безопасно управлять произвольными Google resources | Независимый action request/preflight/confirm/run/reconcile pipeline | [tasks.py](../backend/app/jobs/tasks.py), текущий код/v24.2, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Нет Google notifications/rules API | Нельзя подписаться на общий event stream | Локальные alerts и rules engine на snapshots/events | [v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |

## 6. Граница первой финальной версии

Включить: read-only MCC hierarchy, account/campaign/ad/ad-asset monitoring,
statistics, policy, advertiser identity verification, Google errors, local
notifications, ChangeStatus/ChangeEvent archive, saved views, exports, явно
подтверждаемые PAUSE/ENABLE/budget/status actions и локальные guarded rules.

Не включать: Selenium/cookies/капчи, автоматические appeal/unban, обход
ограничений, Keitaro/Binom/Brocard как обязательную зависимость, изменение
billing setup, создание payment profiles, payment-card operations и
автоматический `StartIdentityVerification`. Эти ограничения согласуются с
официальной поверхностью v25 и текущим заданием.
[v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` для API-границы;
[техническое задание](google-ads-control-center-plan.md), проектное решение,
2026-07-27.
