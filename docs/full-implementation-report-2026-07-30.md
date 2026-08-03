# Полный отчёт о реализации Demand Gen Uploader

Дата: **31 июля 2026 года**  
Проект: `D:\Cursor AI\demand-gen-uploader`  
Рабочий адрес: `http://localhost/`

## Результат

Проект доведён от исследовательского стенда до работающего массового Demand Gen uploader и ежедневного Control Center. Исходный аудит не изменён (SHA-256 `e3b99e5837aa9712ffa8307975023321f67bc3bf81309af2e33a5dea16ad9964`), а все его 407 строк повторно классифицированы только разрешёнными финальными статусами.

| Статус | Количество |
|---|---:|
| `ГОТОВО И ПРОВЕРЕНО` | 332 |
| `ГОТОВО, НО ПРОВЕРЕНО ТОЛЬКО В GOOGLE_TEST` | 55 |
| `ГОТОВО, НО ОЖИДАЕТ BASIC ACCESS` | 2 |
| `НЕДОСТУПНО ЧЕРЕЗ GOOGLE ADS API` | 7 |
| `ЯВНО ИСКЛЮЧЕНО ИЗ ПРОЕКТА ПО ТРЕБОВАНИЮ` | 11 |
| **Всего** | **407** |

## Сохранность до работы

Автоматическая резервная копия находится в:

`D:\Cursor AI\backups\demand-gen-uploader\before-full-completion-20260730-130544`

В неё вошли PostgreSQL dump, Redis RDB, `.env`, source/storage hashes и копия пользовательских данных. Volumes не удалялись и не пересоздавались. Финально сохранены `admin`, `vcc2`, `google-test`, 7 загрузок, 4 media rows, 6 планов, OAuth ciphertext, журналы и Google Request ID.

## Исправленные блокирующие ошибки

1. GET Domain Validation стал строго read-only. Запуск вынесен в POST с CSRF, Job, AuditLog и дедупликацией.
2. Денежные значения хранятся в micros/Decimal и агрегируются по currency code. USD, INR, ZAR и KES не складываются между собой.
3. Global kill switch реально проверяется перед evaluation, созданием action и mutate; состояние переживает рестарт.
4. Смешанная валютная сводка больше не подписывается USD.
5. Английский Control Center локализован, включая тексты, пришедшие из сохранённых backend rows.
6. Мобильный корневой overflow устранён; горизонтальный scroll остаётся внутри рабочих таблиц.
7. Старый экран статистики показывает `Нет данных`, а настоящее числовое значение `0` остаётся нулём.
8. Неверный `CustomerServiceClient.get_customer` удалён; MCC читается через `GoogleAdsService.search/search_stream` и GAQL `customer`.
9. ChangeEvent использует поддерживаемое поле `change_event.client_type` и корректный формат даты `YYYY-MM-DD`.
10. Ошибки Google сохраняют code, Request ID и понятное русское объяснение без masking.

## Demand Gen uploader

- 21-шаговый wizard, сохранение/восстановление draft и структурированный CSV/XLSX import.
- Templates, media library, image roles, обязательные logos, video/YouTube status, creative assignment.
- GEO, languages, age, gender, audiences/interests, devices, optimized targeting, CTA и URL/tracking fields.
- Domain availability + provider-based reputation checks; fresh pre-publication check blocks только элементы опасного домена.
- Campaign Multiplier: 1/3/5/7/10/custom, per-account count, names, budgets, unique instance/deployment keys, exact copy/rotation/random subset.
- FIXED, RANGE, RANDOM, BALANCED_RANDOM, SEQUENTIAL, MANUAL_LIST и account/campaign overrides в native currency.
- Immutable plan, fingerprint, local validation, validate_only, create in PAUSED, idempotency, partial errors, stored resource names, CSV/XLSX reports.
- IMMEDIATE, EVEN, WAVES и MANUAL schedules с timezone, limits, retries, circuit breaker, pause/resume и persisted recovery.

## Control Center

- 10 внутренних вкладок: Accounts, Campaigns, Ads & Assets, Problems, Moderation, Verification, History, Rules, Views, Sync.
- Root/child MCC, произвольная глубина, несколько access paths, GEO directory, inheritance/override, move/access history.
- Account identity — `connection_id + customer_id`; notes/tags/local name/work status переживают перемещение.
- Рабочие статусы отделены от фактической активности; заблокированный аккаунт остаётся `В работе` и выделяется проблемой.
- Server-side filters, numeric filters, multi-sort, GEO/MCC grouping, pagination, configurable columns/density and saved/shared/default views.
- Registrations/deposits mapping из Conversion Actions, честные missing values, metrics in account timezone, per-currency totals.
- Full drill-down account → campaign → ad group → ad → asset; policy, verification, ChangeStatus/ChangeEvent and structured problem lifecycle.
- Safe manual PAUSE/ENABLE/budget and bulk pipeline: fresh read → preview → validate_only → exact confirmation → per-customer mutate → readback → reconciliation → AuditLog.
- Adaptive incremental sync, locks, SKIP LOCKED, jitter/retry/backoff, circuit breaker, idempotency and quota ledger.
- Rules engine with scopes, AND/OR, DRY RUN by default, LIVE confirmation, limits, cooldown, stale/conversion-delay guards, conflicts and persisted kill switch.

## Domain reputation

Provider interface реализован классами `GoogleWebRiskProvider`, `SpamhausDqsProvider` и `IpQualityScoreProvider`. Автотесты полностью mocked и не выполняют реальные запросы.

Для подключения нужны backend-only переменные:

- `WEB_RISK_ENABLED`, `WEB_RISK_API_KEY` или штатная Google Cloud authentication;
- `SPAMHAUS_DQS_ENABLED`, `SPAMHAUS_DQS_KEY`;
- `IPQS_ENABLED`, `IPQS_API_KEY`;
- `DOMAIN_REPUTATION_ENFORCEMENT`.

Без ключей система остаётся в `monitor` и не считает reputation «чистой». После подключения минимум Web Risk и Spamhaus режим переключается на `block` значением `DOMAIN_REPUTATION_ENFORCEMENT=block` с последующим пересозданием backend-контейнеров.

## Finance

Brocard остаётся необязательным и без профиля не вызывается. Реализовано безопасное чтение Google `BillingSetup` и `AccountBudget` для monthly invoicing. Automatic payment threshold, дата следующего карточного списания и полная card charge history официальным Google Ads API не предоставляются и не имитируются.

## Google Ads

- SDK `google-ads 31.2.0`; registry поддерживает `v24.2`, `v25`, `v25.0` через отдельную v25 boundary.
- `google-test` VERIFIED; safe hierarchy/campaign reads и тяжёлая sync завершились для 2/2 accounts.
- Существуют две PAUSED Demand Gen test campaigns: бюджеты 10 и 12 USD/day.
- Ранее разрешённые PAUSE/ENABLE/budget actions имеют validation/mutate/readback Request ID.
- Во время этой завершающей работы production mutate не выполнялся.
- `vcc2` сохранено; Google limitation `AUTHORIZATION_ERROR.DEVELOPER_TOKEN_NOT_APPROVED` не маскируется.

## Миграции

- `202607290007_google_test_mode.py`
- `fabc2ba828ea_add_google_ads_control_center.py`
- `202607300008_complete_control_center_data_model.py`
- `202607300009_control_center_drilldown_fields.py`
- `202607300010_sync_safeguards_and_saved_views.py`

Финальный current/head: `202607300010 (head)`. Миграции additive; таблицы/volumes не очищались.

## Проверка

- Backend: `157 passed, 1 skipped in 90.01s`; Ruff — clean.
- Frontend: `7` files, `27 passed`; TypeScript и Vite production build — успешно.
- Build разбит по route/vendor chunks; крупнейший runtime chunk `vendor-mui` около 335 kB, предупреждения Vite о крупном chunk нет.
- Browser: `17/17` маршрутов, desktop + mobile Control Center; нет пустых экранов, красных app errors или root overflow.
- Browser console: app errors отсутствуют; единственная служебная запись относится к clipboard bridge инструмента acceptance.
- Docker: все 7 сервисов `running/healthy`, restart count `0`.
- HTTP: `/`, `/api/health`, `/api/ready`, `/api/openapi.json` — `200`.
- Свежие стабильные логи за 10 минут: нет traceback, ERROR или 5xx.
- Production npm dependencies: `0 vulnerabilities`; остаются 5 известных dev-only advisory в Vite/Vitest/esbuild toolchain, без принудительного major-upgrade.

## Ограничения

1. Production Google operations ждут Developer Token Basic Access и осознанного включения серверных safeguards. Production mutate намеренно не запускался.
2. Реальный monthly-invoicing billing нельзя подтвердить на test accounts; endpoint возвращает честный `TEST_ACCOUNT_NO_BILLING`.
3. Reputation providers работают в monitor до установки backend keys; отсутствие ключа не превращается в verdict «чистый».
4. Browser automation Google Ads, CAPTCHA bypass, proxy rotation, Keitaro, automatic appeals и automatic winner/loser decisions явно исключены.
