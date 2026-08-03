# Wireframes «Центра контроля»

Дата проектирования: **2026-07-27**. Документ описывает целевой UX/UI без
реализации.

## 1. Принципы интерфейса

1. Это рабочий операционный экран, а не landing page: высокая плотность,
   предсказуемая навигация, минимум декоративных блоков.
2. «Центр контроля» является отдельным пунктом главного меню и не заменяет
   существующие «Статистика», «Модерация», «Финансы», «Уведомления»,
   «Аккаунты MCC» и «Подключения Google».
3. Данные читаются из локального PostgreSQL read model; кнопка обновления
   создаёт background sync job и не держит браузерный запрос до ответа Google.
   Текущий проект уже использует `Job`/`JobEvent` и Celery.
   [models.py](../backend/app/db/models.py),
   [tasks.py](../backend/app/jobs/tasks.py), текущий код,
   2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.
4. Статус всегда представлен иконкой, текстом и цветом; цвет не является
   единственным носителем смысла.
5. Любое Google значение сопровождается source/freshness. Google performance
   data не является real-time и может запаздывать/корректироваться.
   [Data freshness](https://support.google.com/google-ads/answer/2544985?hl=en-ca),
   Google Ads reporting/v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.
6. Опасные действия не выполняются inline одним кликом: preview,
   `validate_only`, confirmation, result.
   [Mutate request](https://developers.google.com/google-ads/api/reference/rpc/v25/MutateGoogleAdsRequest),
   v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 2. Information architecture

```text
Главное меню
├─ Загрузчик
│  └─ существующие страницы без изменений
├─ Операции
│  ├─ Центр контроля                NEW
│  ├─ Модерация                     existing
│  ├─ Статистика                    existing
│  ├─ Финансы                       existing
│  ├─ Уведомления                   existing
│  └─ Журнал                        existing
└─ Настройки
   ├─ Подключения Google            existing
   └─ Аккаунты MCC                  existing
```

Внутри `/control-center`:

```text
Обзор | Аккаунты | Кампании | Объявления и ассеты | Модерация
Верификация | Ошибки | История | Автоправила | Представления | Синхронизация
```

Google API предоставляет соответствующие account/campaign/ad/ad-asset,
policy, verification и change resources, кроме local rules/views/sync
settings.
[v25 fields](https://developers.google.com/google-ads/api/fields/v25/overview),
[v25 services](https://developers.google.com/google-ads/api/reference/rpc/v25/overview),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`;
local rules/views `NOT_SUPPORTED` Google и реализуются приложением.

## 3. Общая оболочка desktop

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Центр контроля                                  [Обновить] [⋮]             │
│ Google Ads через MCC · API v25 · Production access: Basic / Test only      │
├──────────────────────────────────────────────────────────────────────────────┤
│ Обзор  Аккаунты  Кампании  Объявления и ассеты  Модерация  Верификация ... │
├──────────────────────────────────────────────────────────────────────────────┤
│ Scope: [Все подключения ▾] [MCC ▾] [Группа ▾]   Период [Сегодня ▾]         │
│ День: (•) Локальный аккаунта  ( ) Москва UTC+3   [Поиск____________]        │
│ [Фильтры 3] [Колонки] [Группировка ▾] [Вид: Рабочий ▾] [Экспорт ▾]        │
├──────────────────────────────────────────────────────────────────────────────┤
│ Последняя полная синхронизация 12:42  ·  Google delay до 3/15 ч  ·  43% кв │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                           СОДЕРЖИМОЕ РАЗДЕЛА                                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

Правила:

- Верхняя tab bar остаётся sticky после прокрутки.
- Scope, period, timezone, search и filters общие между compatible tabs.
- Saved view сохраняет scope policy, filters, sort, grouping, period/timezone
  mode и column preset, но не текущие checkbox selections.
- Строка freshness не скрывается, когда данные stale.
- В Test Account Access banner объясняет, что production MCC недоступен, без
  показа token value.
  [Developer Token](https://developers.google.com/google-ads/api/docs/api-policy/developer-token),
  все версии, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 4. «Обзор»

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Аккаунты: 100   Работают: 82   Требуют действия: 9   Critical: 4   Stale: 5│
├───────────────────────────────┬──────────────────────────────────────────────┤
│ Расход сегодня                │ Статусы аккаунтов                           │
│ 12 430 USD (72 accounts)      │ ENABLED 82 · SUSPENDED 4 · CLOSED 3 · ... │
│ Локальные дни аккаунтов       │ [Открыть проблемные]                       │
├───────────────────────────────┼──────────────────────────────────────────────┤
│ Модерация                     │ Верификация                                 │
│ Review 18 · Limited 7         │ User action 3 · Review 2 · Deadline 1      │
│ Disapproved 11               │ [Открыть]                                   │
├───────────────────────────────┼──────────────────────────────────────────────┤
│ Ошибки синхронизации          │ Изменения / действия                        │
│ Auth 1 · Quota 0 · Other 3    │ Google UI 14 · Manual 3 · Rules dry 22     │
├───────────────────────────────┴──────────────────────────────────────────────┤
│ Последние критические события                                               │
│ 12:41  [!] Account 123... SUSPENDED  Причина API не предоставлена [Открыть]│
│ 12:33  [!] 4 ads DISAPPROVED   Request ID: отсутствует            [Открыть]│
└──────────────────────────────────────────────────────────────────────────────┘
```

Не использовать nested cards: summary - full-width metric strip, нижние блоки -
нефреймленные bands с разделителями. Точная account suspension reason общим
полем не предоставляется.
[CustomerStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerStatusEnum.CustomerStatus),
[Customer](https://developers.google.com/google-ads/api/reference/rpc/v25/Customer),
v25, 2026-07-27, `NOT_SUPPORTED` для общей причины suspension.

## 5. «Аккаунты»

### 5.1. Основная таблица

```text
┌──┬───────────────┬──────────────┬──────────┬──────────┬──────────┬──────────┐
│□ │ Аккаунт       │ Customer ID  │ MCC/GEO  │ Статус   │ Verify   │ Сегодня  │
├──┼───────────────┼──────────────┼──────────┼──────────┼──────────┼──────────┤
│□ │ Alpha DE      │ 123-456-7890 │ Root/DE  │ ● Работ. │ ! Дейст. │ $ 421.20 │
│  │ USD · Berlin  │ link ACTIVE  │ tags...  │ ENABLED  │ до 29.07 │ cached 9m│
├──┼───────────────┼──────────────┼──────────┼──────────┼──────────┼──────────┤
│□ │ Beta US       │ 987-654-3210 │ Sub/US   │ ✕ Блок.  │ ✓ Успех  │ $ 0.00   │
│  │ USD · Chicago │ link ACTIVE  │          │ SUSPENDED│          │ stale 4h │
└──┴───────────────┴──────────────┴──────────┴──────────┴──────────┴──────────┘
│ 2 выбрано  [Пауза кампаний] [Включить...] [Назначить правило] [Теги] [Ещё] │
└──────────────────────────────────────────────────────────────────────────────┘
```

Configured Customer ID показывается с дефисами только визуально; API использует
digits-only. `login-customer-id` также передаётся без дефисов.
[REST authentication](https://developers.google.com/google-ads/api/rest/auth),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

### 5.2. Полный каталог колонок

Default pinned:

1. checkbox;
2. имя аккаунта;
3. Customer ID;
4. MCC;
5. GEO;
6. account status;
7. verification status;
8. spend today;
9. Google conversions;
10. Google CPA;
11. freshness;
12. latest error.

Optional identity/state:

- link status;
- manager/client;
- hierarchy level;
- test/hidden;
- причина/пояснение, только если точное поле доступно;
- currency;
- timezone;
- first seen/last seen/detached;
- last status change;
- notes;
- tags.

Optional metrics:

- spend yesterday;
- spend selected period;
- impressions;
- clicks;
- CTR;
- average CPC;
- average CPM;
- conversions/all conversions;
- conversion value;
- cost per conversion;
- interaction rate;
- video views/view rate;
- engagements;
- invalid clicks/rate.

Optional operations:

- active campaigns;
- paused campaigns;
- ads in review;
- limited ads;
- disapproved ads;
- billing capability/status;
- last successful sync;
- per-domain freshness;
- last Google error;
- request ID;
- assigned rules.

Поля account/campaign/metrics подтверждены v25; точная suspension reason и
automatic-pay threshold отсутствуют.
[CustomerClient](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerClient),
[metrics](https://developers.google.com/google-ads/api/fields/v25/metrics),
[billing overview](https://developers.google.com/google-ads/api/docs/billing/overview),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS` для доступных полей;
`NOT_SUPPORTED` для suspension reason/automatic threshold.

### 5.3. Column manager

```text
┌─ Колонки ───────────────────────────────────────┐
│ Preset [Рабочий ▾]                 [Сохранить] │
│ Поиск колонки [______________________________] │
│ ☑ Аккаунт             [pin] [drag]  240 px    │
│ ☑ Статус              [   ] [drag]  140 px    │
│ ☑ Расход сегодня      [   ] [drag]  120 px    │
│ ☐ Average CPM         [   ] [drag]  120 px    │
│ ...                                             │
│ [Сбросить]                         [Применить] │
└─────────────────────────────────────────────────┘
```

Допустимые ширины ограничены min/max. Самая длинная status label переносится на
две строки, но не меняет высоту одной строки без режима `comfortable`.

### 5.4. Filter builder

```text
Фильтр: ALL
  [Статус аккаунта] [is any of] [SUSPENDED, CLOSED]
  AND [Freshness]   [older than] [2] [hours]
  AND (
       [Spend today] [>] [100 USD]
       OR [Disapproved ads] [>] [0]
      )
[+ Условие] [+ Группа]                   [Применить]
```

Currency comparison по умолчанию выполняется внутри одной currency; cross-
currency total не показывается без явной conversion source. Google metrics
возвращаются в currency аккаунта через micros.
[Customer.currency_code](https://developers.google.com/google-ads/api/reference/rpc/v25/Customer),
[metrics.cost_micros](https://developers.google.com/google-ads/api/fields/v25/metrics),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 6. Карточка аккаунта

Desktop - правый drawer шириной 560-720 px для быстрого просмотра; кнопка
«Открыть полностью» ведёт на `/control-center/accounts/{id}`.

```text
┌─ Alpha DE · 123-456-7890 ─────────────────────────────── [×] ┐
│ ● Работает  ·  ACTIVE link  ·  cached 9 min                 │
│ [Открыть в Google Ads ↗] [Обновить] [⋮]                     │
├──────────────────────────────────────────────────────────────┤
│ Общее | Статистика | Кампании | Модерация | Verification ...│
├──────────────────────────────────────────────────────────────┤
│ MCC path: Root > Submanager EU > Alpha DE                    │
│ Currency USD    Timezone Europe/Berlin    GEO DE             │
│ First seen 2026-...   Last seen ...   Detached -             │
├──────────────────────────────────────────────────────────────┤
│ Timeline                                                     │
│ 12:40  ENABLED (Google API)                                  │
│ 10:12  Verification PENDING_USER_ACTION                      │
│ 09:45  Sync partial · 1 query failed · Request ID ...        │
├──────────────────────────────────────────────────────────────┤
│ Notes                                                        │
│ [__________________________________________________________] │
│ Tags [DE] [Priority] [+]                                     │
└──────────────────────────────────────────────────────────────┘
```

Tabs full page:

- «Общее» - identity, hierarchy, capabilities, freshness;
- «Временная шкала» - account/link/policy/verification/change/action events;
- «Статистика» - local/Moscow periods and chart/table;
- «Кампании» - campaign table in account scope;
- «Модерация» - ads/assets policy;
- «Верификация» - requirement, deadlines, status, safe action link;
- «Ошибки» - current/resolved Google errors;
- «Действия» - manual/rule actions with result/request IDs;
- «Синхронизация» - runs/items/durations/rows;
- «Заметки» - local notes/tags.

`action_url` advertiser verification не показывается в export/log; UI открывает
его как external link после permission check.
[IdentityVerificationProgress](https://developers.google.com/google-ads/api/reference/rpc/v25/IdentityVerificationProgress),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 7. «Кампании»

```text
Режим: [Кампании] [Ad groups] [Ads]       Channel [Demand Gen ▾]
┌──┬──────────────┬────────────┬──────────┬─────────┬──────────┬─────────────┐
│□ │ Кампания     │ Аккаунт    │ Status   │ Бюджет │ Расход   │ Conv / CPA  │
├──┼──────────────┼────────────┼──────────┼─────────┼──────────┼─────────────┤
│□ │ DG | DE | 01 │ Alpha DE   │ ● Elig.  │ $50/day│ $42.10   │ 3 / $14.03  │
│  │              │            │ ENABLED  │ shared │ cached 9m│             │
└──┴──────────────┴────────────┴──────────┴─────────┴──────────┴─────────────┘
│ 1 выбрано [Пауза] [Включить] [Изменить бюджет] [Только уведомлять]         │
```

Primary/default columns:

- name, account, configured `campaign.status`;
- `campaign.primary_status` + reasons popover;
- daily budget + shared marker;
- bidding strategy;
- spend, impressions, clicks, CTR, CPC, conversions, CPA;
- start/end, latest change, freshness, error.

`campaign.status`, `primary_status`, `primary_status_reasons`,
`campaign_budget`, bidding/start/end доступны в campaign report.
[campaign fields](https://developers.google.com/google-ads/api/fields/v25/campaign),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

Shared budget marker открывает список всех campaigns, которые затронет изменение.
Один budget resource может быть shared.
[CampaignBudget](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignBudget),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 8. «Объявления и ассеты»

```text
Level: [Ads] [Ad-asset links] [Assets]       Policy [Все ▾]
┌──┬─────────────┬─────────────┬──────────┬────────────┬──────────┬──────────┐
│□ │ Preview/name│ Campaign/ad │ Status   │ Approval   │ Asset    │ Metrics  │
├──┼─────────────┼─────────────┼──────────┼────────────┼──────────┼──────────┤
│□ │ Image ad 17 │ DG-DE / AG1 │ ● Eligible│ ! Limited │ IMAGE    │ 12k imp  │
│  │ thumbnail   │             │ ENABLED  │ Topic: ... │ HEADLINE │ 231 click│
└──┴─────────────┴─────────────┴──────────┴────────────┴──────────┴──────────┘
```

- Ads mode использует `ad_group_ad`.
- Ad-asset links mode использует `ad_group_ad_asset_view` и показывает field
  type/performance label/policy в контексте конкретного объявления.
- Assets mode не должен выдавать общую asset aggregation за link-level
  performance.

[ad_group_ad](https://developers.google.com/google-ads/api/fields/v25/ad_group_ad),
[ad_group_ad_asset_view](https://developers.google.com/google-ads/api/fields/v25/ad_group_ad_asset_view),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 9. «Модерация»

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Review 18  ·  Limited 7  ·  Disapproved 11  ·  Changed last 24h: 5         │
├──┬──────────────┬─────────┬──────────────┬─────────────┬──────────┬──────────┤
│  │ Object       │ Account │ Approval     │ Review      │ Topics   │ Checked  │
├──┼──────────────┼─────────┼──────────────┼─────────────┼──────────┼──────────┤
│  │ Ad 123       │ Alpha   │ ✕ DISAPPROVED│ REVIEWED    │ 2 [view] │ 12:41    │
│  │ Asset image  │ Beta    │ ! LIMITED    │ UNDER_APPEAL│ 1 [view] │ 12:35    │
└──┴──────────────┴─────────┴──────────────┴─────────────┴──────────┴──────────┘
```

Details popover:

```text
Policy topic: DESTINATION_NOT_WORKING
Evidence: безопасное структурированное описание
Constraint: ...
Observed: 2026-07-27 12:41
Previous: APPROVED at 09:10
Source: Google Ads API v25
[Открыть объект в Google Ads]
```

Не показывать кнопку автоматической account appeal. Общего official appeal
method нет; `PolicyValidationParameter` не является общей апелляцией.
[PolicyValidationParameter](https://developers.google.com/google-ads/api/reference/rpc/v25/PolicyValidationParameter),
v25, 2026-07-27, `NOT_SUPPORTED` для общей appeal.

## 10. «Верификация»

```text
┌──────────────┬──────────────────────┬────────────┬────────────┬─────────────┐
│ Account      │ Program              │ Status     │ Deadline   │ Action      │
├──────────────┼──────────────────────┼────────────┼────────────┼─────────────┤
│ Alpha DE     │ Advertiser identity  │ ! Действие │ 29.07 23:59│ [Продолжить]│
│ Beta US      │ Advertiser identity  │ ◉ Проверка │ -          │ -           │
│ Gamma FR     │ Не требуется         │ ✓          │ -          │ -           │
└──────────────┴──────────────────────┴────────────┴────────────┴─────────────┘
```

Mapping:

- `PENDING_USER_ACTION` - жёлтый, «Требуется действие»;
- `PENDING_REVIEW` - синий, «Google проверяет»;
- `SUCCESS` - зелёный, «Пройдено»;
- `FAILURE` - красный, «Не пройдено»;
- empty response - серый/зелёный neutral, «Не требуется»;
- stale/error - серый или красный отдельно от verification result.

[IdentityVerification status](https://developers.google.com/google-ads/api/reference/rpc/v25/IdentityVerificationProgramStatusEnum.IdentityVerificationProgramStatus),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

Кнопка «Продолжить» только открывает сохранённый `action_url`, если он не истёк;
автоматический `StartIdentityVerification` не входит в первую action surface.
[Verification guide](https://developers.google.com/google-ads/api/docs/account-management/advertiser-identity-verification),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 11. «Ошибки»

```text
Filters: [Active] [Auth] [Quota] [Policy] [Billing] [Sync] [Resolved]
┌──────────┬────────────┬───────────────┬──────────────┬─────────┬───────────┐
│ Time     │ Account    │ Code          │ Explanation  │ Retry   │ Request ID│
├──────────┼────────────┼───────────────┼──────────────┼─────────┼───────────┤
│ 12:41    │ Alpha DE   │ AUTH...       │ Доступ ...   │ Нет     │ AbCd...    │
│ 12:39    │ Beta US    │ UNAVAILABLE   │ Временно ... │ 2/3     │ EfGh...    │
└──────────┴────────────┴───────────────┴──────────────┴─────────┴───────────┘
```

Error drawer:

- canonical gRPC/HTTP code;
- Google granular error code;
- русский user explanation;
- original Google message с redaction;
- field path;
- customer, service/method, API version;
- request ID with copy icon;
- attempt/backoff/next retry;
- first/last seen/count;
- related sync/action and resolution.

Google errors предоставляют code/message/location/request ID, а retry policy
должна различать transient и input/auth errors.
[Understand API errors](https://developers.google.com/google-ads/api/docs/best-practices/understand-api-errors),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 12. «История изменений»

```text
Source: [Все] [Google UI] [Google API] [Наше ручное] [Автоправило]
┌──────────┬────────────┬──────────┬────────────┬───────────┬────────────────┐
│ Time     │ Account    │ Actor    │ Client     │ Resource  │ Change         │
├──────────┼────────────┼──────────┼────────────┼───────────┼────────────────┤
│ 12:31    │ Alpha DE   │ a@...    │ WEB        │ Campaign  │ budget 50→60  │
│ 12:25    │ Beta US    │ admin    │ OUR_APP    │ Campaign  │ ENABLED→PAUSED│
└──────────┴────────────┴──────────┴────────────┴───────────┴────────────────┘
```

- Google events из `ChangeEvent` имеют old/new/changed fields, visible user и
  client type, но доступны только за 30 дней и не полностью совпадают с UI.
- `ChangeStatus` - широкий dirty signal за 90 дней, не field-level event.
- Local manual/rule actions показываются рядом, но имеют `source=OUR_APP`.

[ChangeEvent](https://developers.google.com/google-ads/api/docs/change-event),
[ChangeStatus](https://developers.google.com/google-ads/api/docs/change-status),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 13. «Автоправила»

### 13.1. List

```text
┌────────────────────────────────────────────────────────── [Создать правило] ┐
│ [KILL SWITCH: правила разрешены]                                             │
├───────────────┬───────────┬──────────┬───────────┬──────────┬────────────────┤
│ Rule          │ Mode      │ Scope    │ Schedule  │ Last run │ Result         │
├───────────────┼───────────┼──────────┼───────────┼──────────┼────────────────┤
│ Spend no conv │ DRY RUN   │ 20 acc   │ hourly    │ 12:00    │ 3 matched      │
│ Pause reject  │ NOTIFY    │ DE group │ 30 min    │ 12:30    │ 1 alert        │
└───────────────┴───────────┴──────────┴───────────┴──────────┴────────────────┘
```

### 13.2. Editor

```text
Название [Пауза при расходе без конверсий________________]
Mode     [DRY RUN ▾]          Priority [50]
Scope    [Группа DE ▾]        Level [Campaign ▾]
Period   [Последние 24 часа]  Timezone [Локальный аккаунта ▾]
Run      [Каждый час ▾]

Условия: ALL
  [Spend]       [>] [100] [account currency]
  AND [Conversions] [=] [0]
  AND [Campaign status] [=] [ENABLED]

Action [PAUSE]

Safeguards
☑ Запрет при stale/incomplete data
☑ Conversion delay 15h
Cooldown [24 h]
Max actions [5/hour] [20/day]
Max accounts [10/run]
Circuit breaker [3 errors]

[Проверить на истории] [Сохранить черновик]
```

Rule detail tabs: definition versions, assignments, dry-run preview,
evaluations with «почему сработало», actions/skips/conflicts, errors, audit.

Google v25 не содержит resource Google Ads UI Automated Rules, поэтому все
элементы этого экрана - локальный engine.
[v25 reference index](https://developers.google.com/google-ads/api/reference/rpc/v25/overview),
v25, 2026-07-27, `NOT_SUPPORTED`.

### 13.3. Kill switch

```text
┌─ Отключить все действия автоправил ──────────────────────────┐
│ Read-only evaluation и уведомления могут продолжиться.       │
│ Новые Google mutates не будут создаваться.                   │
│ Причина [_______________________________________________]    │
│ Введите ОТКЛЮЧИТЬ ПРАВИЛА [____________________________]     │
│ [Отмена]                                  [Отключить]        │
└───────────────────────────────────────────────────────────────┘
```

## 14. «Сохранённые представления»

```text
┌──────────────────────┬──────────────┬───────────┬─────────────┬─────────────┐
│ Name                 │ Level        │ Owner     │ Shared      │ Updated     │
├──────────────────────┼──────────────┼───────────┼─────────────┼─────────────┤
│ Проблемные DE        │ Accounts     │ admin     │ Team        │ 12:00       │
│ DG spend today       │ Campaigns    │ me        │ Private     │ 11:40       │
└──────────────────────┴──────────────┴───────────┴─────────────┴─────────────┘
```

Actions: apply, rename, duplicate, set default, share/unshare, delete. Shared
view сохраняет filter schema, но пользователь видит только объекты в своём
permission scope. Preset колонок может быть отдельным reusable object.

FBTOOL официально подтверждает saved presets для порядка fields.
[FBTOOL fields](https://help.fbtool.pro/knowledge-bases/2/articles/28-nastrojki-polej),
продукт FBTOOL, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 15. «Настройки синхронизации»

```text
Google API
  Version                  v25
  Access                   Test Account Access [Production недоступен]
  Planned operations       8 544 / 15 000  [███████████░░░░░]
  Background forecast      7 044
  Manual/error reserve     1 500
  Remaining quota          6 456

Cadence tier               [100 accounts ▾]
  Campaign metrics         60 min
  Ad group/ad/ad-asset     6 h
  Video/asset detail       24 h
  ChangeStatus             60 min
  Verification             12 h
  Billing                  24 h

Adaptive polling           [on]
Archive polling            [24 h]
Stale thresholds           [Настроить]
Global read sync           [on]
Global rule actions        [off/on with permission]

Recent sync health
  Succeeded 94% · Partial 4% · Failed 2% · Queue age 32s
  [Открыть runs]
```

Basic Access quota 15 000 operations/day; one Search/SearchStream request is one
operation.
[Quota guide](https://developers.google.com/google-ads/api/docs/best-practices/quotas),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

Секреты, OAuth refresh token и Developer Token не показываются даже admin.

## 16. Action flows

### 16.1. PAUSE/ENABLE preview

```text
┌─ Поставить кампании на паузу ─────────────────────────────────┐
│ Выбрано: 8 campaigns в 3 accounts                             │
│ Fresh state: 7 ready · 1 blocked                              │
├───────────────────────────────────────────────────────────────┤
│ Ready                                                         │
│ Alpha / DG-1   ENABLED → PAUSED   validated                   │
│ ...                                                           │
│ Blocked                                                       │
│ Beta / DG-8    Account SUSPENDED                              │
├───────────────────────────────────────────────────────────────┤
│ Estimated operations: 16 validate+mutate, plus reads          │
│ Partial failure: per independent item                         │
│ Введите PAUSE 7 КАМПАНИЙ [________________________]           │
│ [Отмена]                              [Подтвердить и выполнить]│
└───────────────────────────────────────────────────────────────┘
```

### 16.2. Budget preview

```text
┌─ Изменить дневной бюджет ─────────────────────────────────────┐
│ Mode: ( ) amount  (•) + percent  Value [10] %                 │
│ Alpha / Budget A  $50 → $55   shared by 3 campaigns [details]│
│ Beta  / Budget B  $80 → $88   one campaign                    │
│ Total displayed by currency: USD $130 → $143                  │
│ Guard: max +20% ✓   Fresh state ✓   validate_only ✓           │
│ [Отмена]                                      [Продолжить]    │
└───────────────────────────────────────────────────────────────┘
```

### 16.3. Result

```text
Action completed with partial failures
Succeeded 6 · Failed 1 · Skipped 1
[Export results] [Open audit]

Campaign DG-1  SUCCESS  Request ID AbCd...
Campaign DG-2  FAILED   POLICY... · field status · Request ID ...
Campaign DG-8  SKIPPED  Account SUSPENDED
```

`partial_failure` возвращает operation failures отдельно, а request ID нужен
для troubleshooting.
[Partial failures](https://developers.google.com/google-ads/api/docs/best-practices/partial-failures),
[API errors](https://developers.google.com/google-ads/api/docs/best-practices/understand-api-errors),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 17. Freshness и status language

### 17.1. Цвета и иконки

| Семантика | Цвет | Иконка | Обязательный текст |
|---|---|---|---|
| Работает / success | зелёный | check-circle | «Работает», `ENABLED`, «Пройдено» |
| Critical / blocked | красный | error/stop | `SUSPENDED`, «Критическая ошибка», `DISAPPROVED` |
| Требуется действие | жёлтый | warning | «Требуется действие», deadline |
| На рассмотрении | синий | schedule/progress | «Google проверяет», «На модерации» |
| Disabled/archive/stale | серый | pause/archive/history | «Отключён», «Архив», «Устарело» |

Account enum semantics:
`ENABLED`, `SUSPENDED`, `CANCELED`, `CLOSED`.
[CustomerStatus](https://developers.google.com/google-ads/api/reference/rpc/v25/CustomerStatusEnum.CustomerStatus),
v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

### 17.2. Freshness labels

- `LIVE_SYNC`: «Получено сейчас», но не «Google real-time»;
- `CACHED`: «Кэш · 9 мин»;
- `STALE`: «Устарело · 4 ч», с причиной;
- `ARCHIVED`: «Архив · доступ потерян 12.07»;
- `PARTIAL`: «Частично · 1 из 4 запросов не выполнен».

Tooltip:

```text
Период данных: 27.07 00:00-12:00 Europe/Berlin
Получено: 27.07 12:09 MSK
Google может задерживать основные данные до 3 часов,
а некоторые конверсии до 15 часов.
Query: campaign-core v3 · API v25
```

[Data freshness](https://support.google.com/google-ads/answer/2544985?hl=en-ca),
Google Ads reporting/v25, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

### 17.3. Moscow precision

При whole-hour account timezone:
`Москва UTC+3 · точные часовые границы`.

При half-hour timezone:
`Москва UTC+3 · приблизительно, граница ±30 мин`; строка не включается в exact
grand total по умолчанию.
[Timezone help](https://support.google.com/google-ads/answer/17006726?hl=en),
Google Ads reporting/v25, 2026-07-27, `REQUIRES_LIVE_VALIDATION`.

## 18. Mobile

На ширине до 767 px основная таблица заменяется компактным list-row, не набором
вложенных cards.

```text
┌──────────────────────────────┐
│ Центр контроля        [↻][⋮]│
│ [Аккаунты ▾]                 │
│ [Scope: Все MCC ▾]           │
│ [Сегодня ▾] [Фильтры 3]      │
│ [Поиск___________________]   │
├──────────────────────────────┤
│ □ Alpha DE                   │
│   123-456-7890 · DE · USD    │
│   ● Работает  ! Верификация  │
│   Сегодня $421 · CPA $14.03  │
│   cached 9m              [›] │
├──────────────────────────────┤
│ □ Beta US                    │
│   ✕ SUSPENDED · stale 4h     │
│   Сегодня $0             [›] │
├──────────────────────────────┤
│ 2 выбрано       [Действия ▾] │
└──────────────────────────────┘
```

- Horizontal table доступна как optional «Таблица», но default mobile mode -
  list.
- Tabs заменяются select/menu с текущим section name.
- Account details открываются full-screen.
- Bulk action bar закреплён снизу и учитывает safe-area.
- Column manager на mobile управляет полями compact row отдельно от desktop
  preset.
- Любой confirmation показывает полный count/impact без горизонтального
  скролла.

## 19. Empty, loading и failure states

| State | Сообщение | Действие |
|---|---|---|
| Нет Google connection | «Нет активного подключения Google» | Link «Открыть Подключения Google» |
| Test token + production MCC | «Production недоступен с Test Account Access» | Без кнопки обхода; ссылка на access status |
| First sync | Skeleton rows + «Получаем иерархию MCC» | Background progress, можно уйти со страницы |
| No rows by filter | «По текущим фильтрам ничего не найдено» | «Сбросить фильтры» |
| Partial sync | Данные остаются видимыми с PARTIAL banner | «Открыть ошибки» / safe retry |
| Stale | Старые данные не скрываются | «Обновить» с rate-limit feedback |
| Detached | Archived data remains | Показать last seen/detached; actions disabled |
| Quota guard | «Фоновое обновление замедлено для сохранения квоты» | Quota details, без бесконечного retry |
| Permission denied | Не раскрывать существование чужих accounts | Вернуться в allowed scope |

Test Account Access действительно ограничен test accounts.
[Developer Token](https://developers.google.com/google-ads/api/docs/api-policy/developer-token),
все версии, 2026-07-27, `CONFIRMED_BY_OFFICIAL_DOCS`.

## 20. Accessibility и keyboard

- Все icon-only buttons имеют tooltip и accessible name.
- Checkbox selection поддерживает Shift range на desktop.
- `Tab` проходит toolbar -> table header -> rows -> bulk bar; focus не
  теряется после local refresh.
- Status icon имеет текстовое имя; charts имеют table alternative.
- Sort state читается screen reader; resize handle доступен клавиатурой.
- Dialog focus trap и возврат focus к инициирующей строке обязательны.
- Error/status live announcements используют polite region, action completion -
  assertive только для критического результата.
- Minimum touch target 44x44 px на mobile.
- Контраст текста/иконок соответствует WCAG AA; red/yellow/green всегда
  сопровождаются label.

## 21. Как избежать дублирования существующих страниц

| Existing page | Остаётся ответственной за | «Центр контроля» добавляет |
|---|---|---|
| «Статистика» | Простой текущий ручной Google data view | Cross-account hierarchy, levels, filters, periods, history, freshness |
| «Модерация» | Простой текущий список moderation records | Ad + asset policy, review/primary status, timeline и scope |
| «Финансы» | Existing Brocard profiles/sync | Только Google monthly-invoicing capability/state; link в существующий finance |
| «Уведомления» | Общий inbox/read state | Monitoring event filters и deep links; alert может появляться в общем inbox |
| «Аккаунты MCC» | Administrative account catalog | Operational row, snapshots, notes/tags/history |
| «Подключения Google» | OAuth, test, sync/disconnect | Только connection status/link; no secrets/config editor |
| «Группы запуска» | Uploader-owned campaigns и действия | Все доступные Google campaigns, отдельный action pipeline |
| «Журнал» | Общий app audit | Combined Google ChangeEvent + local action/rule history с link в audit |

Текущее разделение routes подтверждено frontend navigation.
[App.tsx](../frontend/src/app/App.tsx), текущий код,
2026-07-27, `CONFIRMED_BY_CURRENT_CODE`.
