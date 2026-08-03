# Карта продуктовых функций FBTOOL для Google Ads

Дата проверки: **2026-07-27**.

## 1. Методика

Исследована только официальная база знаний FBTOOL. Переносятся продуктовые
паттерны: единая таблица, выбор объектов, режимы уровней, настраиваемые поля,
массовые действия, правила, статусы, ошибки и разграничение доступа.

Не переносятся Facebook-specific cookies, proxy, browser automation,
multitokens, cards, Fan Pages, comments, bypass/unban и любые действия вне
официального Google Ads API. Это ограничение соответствует отсутствию таких
Google resources/services в официальном индексе v25.
[Google Ads API v25 overview](https://developers.google.com/google-ads/api/reference/rpc/v25/overview),
v25, 2026-07-27, `NOT_SUPPORTED`.

Основные официальные источники FBTOOL:

- [База знаний](https://help.fbtool.pro/knowledge-bases/2-baza-znanij),
  продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
- [Рекламные кабинеты](https://help.fbtool.pro/knowledge-bases/2/articles/56-razdel-reklamnyie-kabinetyi-obschaya-informatsiya),
  продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
- [Настройки полей](https://help.fbtool.pro/knowledge-bases/2/articles/28-nastrojki-polej),
  продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
- [Статусы](https://help.fbtool.pro/knowledge-bases/2/articles/29-statusyi-reklamnyih-kabinetov-kampanij-adsetov-i-obyavlenij),
  продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
- [Действия](https://help.fbtool.pro/knowledge-bases/2/articles/27-dejstviya-nad-obyavleniyami-adsetami-i-kampaniyami),
  продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
- [Создание автоправила](https://help.fbtool.pro/knowledge-bases/2/articles/13-kak-sozdat-avtopravilo)
  и [применение автоправила](https://help.fbtool.pro/knowledge-bases/2/articles/26-kak-primenit-avtopravilo),
  продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
- [Консоль управления рекламой](https://help.fbtool.pro/knowledge-bases/2/articles/51-konsol-upravleniya-reklamoj-funktsional),
  продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
- [Работа с командой](https://help.fbtool.pro/knowledge-bases/2/articles/54-rabota-s-komandoj-funktsional),
  продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 2. Матрица переноса

| Функция FBTOOL | Зачем нужна | Аналог Google Ads / точный API | Поддержка | Включать и где | Ограничения, риски и доказательство |
|---|---|---|---|---|---|
| Выбор аккаунта или группы перед показом кабинетов | Быстро ограничить рабочий набор | MCC hierarchy из `CustomerClient`; группы в Google API не обязательны, поэтому пользовательские группы локальные | Частичная | Да: глобальный scope selector и «Сохранённые представления» | FBTOOL подтверждает account/group selector: [кабинеты](https://help.fbtool.pro/knowledge-bases/2/articles/56-razdel-reklamnyie-kabinetyi-obschaya-informatsiya), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`. Google hierarchy: [CustomerClient](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerClient), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Мультивыбор аккаунтов из разных групп | Разовая работа с произвольным набором | Локальная selection model; каждый Google request всё равно выполняется по `customer_id` | Полная как UX, API частичная | Да: checkbox + sticky bulk bar | Google Ads mutates не являются одним cross-customer transaction; группировать операции по customer. [MutateGoogleAdsRequest](https://developers.google.com/google-ads/api/reference/rpc/v25/MutateGoogleAdsRequest), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; FBTOOL source выше |
| Единая таблица множества кабинетов | Сканирование статуса и метрик без переходов | `CustomerClient` + локальные state/snapshot aggregates | Полная после локальной агрегации | Да: «Обзор» и «Аккаунты» | Google не возвращает одним cross-account GAQL запросом все client metrics; нужен per-customer polling. [Reporting](https://developers.google.com/google-ads/api/docs/reporting/overview), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Фильтр кабинетов по статусу и другим признакам | Быстро найти проблемные объекты | Server-side фильтры по локальным current states; source `CustomerStatus` | Полная | Да: filter builder + quick chips | FBTOOL status filters: [кабинеты](https://help.fbtool.pro/knowledge-bases/2/articles/56-razdel-reklamnyie-kabinetyi-obschaya-informatsiya), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; Google status: [CustomerStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerStatusEnum.CustomerStatus), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Сортировка | Сравнение расходов, ошибок, freshness | Сортировка локальной materialized read model | Полная | Да: все разрешённые колонки | При больших наборах нужна server-side stable sort с tie-breaker `id`; это проектное решение, основанное на существующем PostgreSQL |
| Настраиваемые поля | Не перегружать таблицу | Поля Google metrics/state + локальные tags/notes | Полная | Да: column chooser, порядок, pin, width | FBTOOL позволяет выбирать и упорядочивать fields: [настройки полей](https://help.fbtool.pro/knowledge-bases/2/articles/28-nastrojki-polej), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Пресеты полей | Повторяемые рабочие представления | Локальные `saved_views` + `column_presets` | Полная | Да: персональные и общие saved views | FBTOOL сохраняет пресеты полей: [настройки полей](https://help.fbtool.pro/knowledge-bases/2/articles/28-nastrojki-polej), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; Google resource не нужен |
| Показывать объекты без статистики | Не терять новые/paused entities | Отдельный entity catalog LEFT JOIN metric aggregates | Полная при локальном merge | Да: toggle «Включая без статистики» | Google segmented reports исключают all-zero rows: [Zero metrics](https://developers.google.com/google-ads/api/docs/reporting/zero-metrics), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; FBTOOL pattern: [настройки полей](https://help.fbtool.pro/knowledge-bases/2/articles/28-nastrojki-polej), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Режимы «Объявления / Адсеты / Кампании» | Одинаковая логика управления на разных уровнях | `ad_group_ad`, `ad_group`, `campaign`; отдельный assets mode | Полная | Да: segmented control «Аккаунты / Кампании / Группы / Объявления / Ассеты» | FBTOOL modes: [консоль](https://help.fbtool.pro/knowledge-bases/2/articles/51-konsol-upravleniya-reklamoj-funktsional), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; Google resources: [v25 fields](https://developers.google.com/google-ads/api/fields/v25/overview), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Видимый effective status и причина в tooltip | Понять, почему объект не работает | `primary_status`, `primary_status_reasons`, policy summary, account status | Частичная | Да: текст + иконка + details popover | Точная account suspension reason отсутствует, поэтому нельзя имитировать FBTOOL ban reason. [campaign](https://developers.google.com/google-ads/api/fields/v25/campaign), [ad_group_ad](https://developers.google.com/google-ads/api/fields/v25/ad_group_ad), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; [Customer](https://developers.google.com/google-ads/api/reference/rpc/v25/Customer), v25, 2026-07-27, `NOT_SUPPORTED` для причины suspension |
| Быстрый переход из кабинета в статистику/консоль/финансы | Сохранять контекст объекта | Account detail tabs + deep link Google Ads UI | Полная как UX | Да: row action и account drawer/page | FBTOOL pattern: [кабинеты](https://help.fbtool.pro/knowledge-bases/2/articles/56-razdel-reklamnyie-kabinetyi-obschaya-informatsiya), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Одиночные PAUSE/ENABLE | Быстрая реакция | `CampaignService`, `AdGroupService`, `AdGroupAdService` mutates | Полная | Да: row action с preview + confirm | Google mutates поддерживают status update, но первая версия требует явного подтверждения. [Mutates](https://developers.google.com/google-ads/api/docs/mutating/overview), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; FBTOOL pattern: [действия](https://help.fbtool.pro/knowledge-bases/2/articles/27-dejstviya-nad-obyavleniyami-adsetami-i-kampaniyami), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Массовые PAUSE/ENABLE | Реакция на группу объектов | Несколько independent operations, сгруппированных по customer | Полная с ограничениями | Да: sticky bulk bar, двухэтапное подтверждение | `partial_failure` допустим для независимых operations; cross-customer atomicity отсутствует. [Partial failures](https://developers.google.com/google-ads/api/docs/best-practices/partial-failures), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Inline изменение бюджета на сумму/% | Быстрая корректировка | `CampaignBudgetService.MutateCampaignBudgets`, `amount_micros` | Полная с guardrails | Да: campaign mode, не ad mode | Shared budget может влиять на несколько campaigns; impact preview обязателен. [CampaignBudget](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignBudget), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; FBTOOL pattern: [действия](https://help.fbtool.pro/knowledge-bases/2/articles/27-dejstviya-nad-obyavleniyami-adsetami-i-kampaniyami), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Подробные ошибки в «Консоли» | Не искать причину в логах | `GoogleAdsError` + field path + request ID; serving/policy reasons | Частичная | Да: «Ошибки» и details drawer | Google отдаёт structured API errors, но не все UI explanations. [Understand API errors](https://developers.google.com/google-ads/api/docs/best-practices/understand-api-errors), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; FBTOOL pattern: [консоль](https://help.fbtool.pro/knowledge-bases/2/articles/51-konsol-upravleniya-reklamoj-funktsional), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Повторная модерация / appeal | Оспорить отклонение | Общего account/ad appeal API нет; `PolicyValidationParameter` - не общий appeal | Отсутствующая/частичная | Нет автоматизации; только link to Google Ads UI | [PolicyValidationParameter](https://developers.google.com/google-ads/api/reference/rpc/v25/PolicyValidationParameter), v25, 2026-07-27, `NOT_SUPPORTED` для общей appeal; FBTOOL описывает свою Facebook-функцию: [статусы](https://help.fbtool.pro/knowledge-bases/2/articles/29-statusyi-reklamnyih-kabinetov-kampanij-adsetov-i-obyavlenij), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Создание rule: имя, частота, уровень, период, status filter, conditions | Повторяемая автоматизация | Отдельного Google Automated Rules resource нет; локальный scheduler/worker | Google API отсутствует, локально полная | Да: «Автоправила» | FBTOOL pattern: [создание правила](https://help.fbtool.pro/knowledge-bases/2/articles/13-kak-sozdat-avtopravilo), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; [v25 index](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` для Google UI rules |
| Несколько условий | Более точные решения | Локальное expression tree `AND/OR`; metrics из snapshots | Полная локально | Да: визуальный condition builder | FBTOOL подтверждает несколько условий, но не документирует сложную вложенную логику. [создание правила](https://help.fbtool.pro/knowledge-bases/2/articles/13-kak-sozdat-avtopravilo), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; вложенные группы `REQUIRES_LIVE_VALIDATION` как UX |
| Rule groups | Назначать набор правил | Локальные rule sets/assignments | Полная локально | Да: группы правил + assignment | [создание правила](https://help.fbtool.pro/knowledge-bases/2/articles/13-kak-sozdat-avtopravilo), [применение правила](https://help.fbtool.pro/knowledge-bases/2/articles/26-kak-primenit-avtopravilo), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Назначение rules на account/group и будущие objects | Массовое применение | Локальные scope selectors и dynamic membership | Полная локально | Да, но будущие объекты должны попадать по явному dynamic scope | FBTOOL применяет правила на account/cabinet и будущие ads: [применение правила](https://help.fbtool.pro/knowledge-bases/2/articles/26-kak-primenit-avtopravilo), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Ограничение увеличения бюджета и частоты | Защита от разгона расходов | Local max delta/final budget/cooldown/actions per period | Полная локально | Обязательно | В примере FBTOOL есть +10%, не чаще раза в день и потолок бюджета: [создание правила](https://help.fbtool.pro/knowledge-bases/2/articles/13-kak-sozdat-avtopravilo), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; наш набор guards шире как проектное решение |
| Уведомления по billing/moderation/status | Не пропустить проблему | Локальные alerts из polling; общего Google Notifications API нет | Частичная | Да: «Ошибки», overview alerts и существующий «Уведомления» | FBTOOL показывает toggles уведомлений: [кабинеты](https://help.fbtool.pro/knowledge-bases/2/articles/56-razdel-reklamnyie-kabinetyi-obschaya-informatsiya), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; Google Notifications API: [v25 index](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Финансы рядом со статусом кабинета | Быстро увидеть платёжный риск | `BillingSetup`, `AccountBudget`, `Invoice` только monthly invoicing | Частичная | Да: optional billing columns/details, «Недоступно» для automatic-pay | [Billing overview](https://developers.google.com/google-ads/api/docs/billing/overview), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; FBTOOL pattern: [кабинеты](https://help.fbtool.pro/knowledge-bases/2/articles/56-razdel-reklamnyie-kabinetyi-obschaya-informatsiya), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Скрыть кабинет, не удаляя | Убирать шум, сохраняя историю | Локальный archive/hidden flag; Google `CustomerClient.hidden` отдельно | Полная локально | Да: archive action, обратимая | FBTOOL pattern: [кабинеты](https://help.fbtool.pro/knowledge-bases/2/articles/56-razdel-reklamnyie-kabinetyi-obschaya-informatsiya), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; Google hidden: [CustomerClient](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerClient), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` |
| Сохранение данных после блокировки/отвязки | Аналитика и расследование | Локальные immutable snapshots/events | Полная локально | Обязательно | FBTOOL official help не подтверждает срок/гарантию хранения после отвязки: продукт FBTOOL, 2026-07-27, `UNKNOWN`. Google historical link dates не отдаёт: [CustomerClient](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerClient), v25, 2026-07-27, `NOT_SUPPORTED` |
| Командные роли и ограниченный scope | Разделять просмотр и действия | Текущие project roles + новые permissions/scopes | Частичная в проекте | Да: `control_center.read`, `control_center.act`, `rules.manage`, `export` | FBTOOL role/scope pattern: [команда](https://help.fbtool.pro/knowledge-bases/2/articles/54-rabota-s-komandoj-funktsional), продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; текущие роли: [models.py](../backend/app/db/models.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |
| Экспорт | Работа вне системы | Локальный CSV/XLSX export из filtered read model | FBTOOL не подтверждён; локально реализуемо | Да | В просмотренных официальных статьях FBTOOL export не описан: продукт FBTOOL, 2026-07-27, `UNKNOWN`. Google export service не требуется; это проектная функция |
| История действий | Аудит и объяснимость | Local `AuditLog` + `action_runs` + `ChangeEvent` | Полная при объединении источников | Да: «История изменений» | Google ChangeEvent: [guide](https://developers.google.com/google-ads/api/docs/change-event), v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`; отдельная продуктовая история FBTOOL в изученных статьях не документирована, 2026-07-27, `UNKNOWN` |

## 3. Что переносить в первую очередь

1. **Единый рабочий экран**: account scope, search, filters, saved view, dense
   table, multiselect и contextual bulk bar. Основание - официальный раздел
   FBTOOL «Рекламные кабинеты».
   [Источник FBTOOL](https://help.fbtool.pro/knowledge-bases/2/articles/56-razdel-reklamnyie-kabinetyi-obschaya-informatsiya),
   продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
2. **Переключение уровня без потери фильтров**:
   accounts/campaigns/ad groups/ads/assets. Основание - режимы консоли FBTOOL;
   ресурсы Google официально существуют.
   [FBTOOL console](https://help.fbtool.pro/knowledge-bases/2/articles/51-konsol-upravleniya-reklamoj-funktsional),
   продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
   [Google fields](https://developers.google.com/google-ads/api/fields/v25/overview),
   v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
3. **Настраиваемые колонки и пресеты** с отдельным entity catalog, чтобы не
   исчезали объекты с нулевыми metrics.
   [FBTOOL fields](https://help.fbtool.pro/knowledge-bases/2/articles/28-nastrojki-polej),
   продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
   [Google zero metrics](https://developers.google.com/google-ads/api/docs/reporting/zero-metrics),
   v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
4. **Быстрые, но безопасные действия**: preview, `validate_only`, impact,
   explicit confirmation, per-item result, request ID.
   [Google mutate](https://developers.google.com/google-ads/api/docs/mutating/overview),
   v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
5. **Локальные rules** с scope, schedule, period, conditions, action и
   assignments, но с более строгими safeguards, чем описаны в FBTOOL.
   [FBTOOL rules](https://help.fbtool.pro/knowledge-bases/2/articles/13-kak-sozdat-avtopravilo),
   продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
   [Google v25 index](https://developers.google.com/google-ads/api/reference/rpc/v25/overview),
   v25, 2026-07-27, `NOT_SUPPORTED` для Google UI Automated Rules.

## 4. Что сознательно не переносить

| FBTOOL-specific область | Причина отказа | Доказательство |
|---|---|---|
| Cookies, proxy, browser emulation, multitokens | Проект работает только через OAuth + official Google Ads API | [Google authentication](https://developers.google.com/google-ads/api/docs/oauth/overview), v25, 2026-07-27, `NOT_SUPPORTED` как Google Ads API resource |
| Cards, автоматическая привязка payment methods | Google Ads API billing surface не предоставляет card-management workflow | [Billing overview](https://developers.google.com/google-ads/api/docs/billing/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Fan Pages и комментарии | Facebook-specific модель, прямого Google Ads аналога нет | [Google v25 resources](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Автоматический unban/appeal, captcha bypass | Общего official service нет; противоречит границам проекта | [Google v25 resources](https://developers.google.com/google-ads/api/reference/rpc/v25/overview), v25, 2026-07-27, `NOT_SUPPORTED` |
| Facebook billing statuses и ban reasons | Нельзя маппить на Google enums по названию | [CustomerStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerStatusEnum.CustomerStatus), v25, 2026-07-27, `NOT_SUPPORTED` для такого маппинга |
| Keitaro/Binom/Brocard как обязательная основа rules | Первая версия использует только Google metrics; текущий Brocard остаётся независимым | [brocard.py](../backend/app/integrations/brocard.py), текущий код, 2026-07-27, `CONFIRMED_BY_CURRENT_CODE` |

## 5. Итог продуктового сопоставления

FBTOOL полезен как референс рабочей плотности интерфейса и массовой операционной
логики. Он не является техническим источником возможностей Google. Любая
перенесённая функция должна сначала маппиться на конкретный Google resource,
field или local-only capability; отсутствие маппинга означает
`NOT_SUPPORTED`, а не скрытую браузерную автоматизацию.
[Google Ads API policies and overview](https://developers.google.com/google-ads/api/),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

