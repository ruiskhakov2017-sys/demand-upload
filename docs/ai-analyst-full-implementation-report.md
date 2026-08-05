# Полный отчёт по реализации AI-аналитика Axyro

Дата финальной проверки: 2026-08-05  
Публичный адрес: <https://axyro.tech>  
Работающий production commit: `6ca275f718eec64aab62886c339c381dfb428114`  
Финальный annotated release tag: `ai-analyst-full-20260805.3`

## 1. Итог

| Область | Статус | Результат |
|---|---|---|
| Сохранение исходного состояния, GitHub и Timeweb delivery | **РЕАЛИЗОВАНО И ПРОВЕРЕНО** | Baseline, локальные и серверные backup, private GitHub, CI, exact-SHA deploy и rollback-контур работают. |
| AI backend, UI, drawer, история, отчёты, usage, GEO и mappings | **РЕАЛИЗОВАНО И ПРОВЕРЕНО** | Код, миграции, mocked contracts, security, evals, desktop/mobile и production browser acceptance пройдены. |
| Live OpenAI-ответ и live voice transcription | **РЕАЛИЗОВАНО, НО LIVE-ПРОВЕРКА ЗАБЛОКИРОВАНА ВНЕШНИМ ДОСТУПОМ** | В production отсутствует OpenAI API key; интерфейс корректно блокирует ввод и показывает причину. |
| Google Test hierarchy и безопасное чтение | **РЕАЛИЗОВАНО И ПРОВЕРЕНО** | `google-test` имеет статус `VERIFIED`; сохранены два test account. |
| AI-команда через live OpenAI до Google Test pipeline | **РЕАЛИЗОВАНО, НО LIVE-ПРОВЕРКА ЗАБЛОКИРОВАНА ВНЕШНИМ ДОСТУПОМ** | Policy, tools и pipeline покрыты тестами, но live model run невозможен без OpenAI API key. |
| Production Google Ads read для `vcc2` | **РЕАЛИЗОВАНО, НО LIVE-ПРОВЕРКА ЗАБЛОКИРОВАНА ВНЕШНИМ ДОСТУПОМ** | Подключение сохранено; production read gate выключен, `vcc2` остаётся в `ERROR` до внешнего доступа/повторной официальной проверки. |
| Production Google Ads mutate acceptance | **СОЗНАТЕЛЬНО ИСКЛЮЧЕНО ИЗ ЭТОГО ЗАДАНИЯ** | Кодовые gates и обычный action pipeline сохранены, но ни одного production mutate не выполнялось. |
| Live Keitaro и Brocard connectors | **СОЗНАТЕЛЬНО ИСКЛЮЧЕНО ИЗ ЭТОГО ЗАДАНИЯ** | Реализованы typed provider contract, registry, disabled states, provenance и mapping UI; неподтверждённые live connectors не имитируются. |

## 2. Инвентаризация трёх копий

### Локальная копия

- Путь: `D:\Cursor AI\demand-gen-uploader`.
- Git-репозиторий с `origin` на private GitHub.
- Исходный baseline: `6abae5aac5b3c59ad529ab631f24f092deac7951`, 232 tracked files.
- Финальное release-дерево: 273 tracked files.
- Проверенные локальные версии: Python `3.12.10`, Node `24.13.0`, npm `11.6.2`, Docker Engine/Client `29.2.0`, Compose `5.0.2`.
- Контейнерные runtime pins: Python `3.12-slim`, Node `24-alpine`, nginx `1.27-alpine`, PostgreSQL `16-alpine`, Redis `7-alpine`, Caddy `2.8-alpine`.

### Timeweb

- Постоянные данные и production `.env`: `/opt/demand-gen-uploader`.
- Неизменяемые release-каталоги: `/opt/demand-gen-uploader-releases/<full-sha>`.
- Активная ссылка: `/opt/demand-gen-uploader-current`.
- Backup root: `/var/backups/demand-gen-uploader`.
- Активный release SHA после финального deploy: `6ca275f718eec64aab62886c339c381dfb428114`.
- Runtime состоит из семи сервисов: `postgres`, `redis`, `api`, `worker`, `scheduler`, `frontend`, `reverse-proxy`.

### GitHub

- Репозиторий: <https://github.com/ruiskhakov2017-sys/demand-upload>.
- Видимость `Private` была подтверждена до отправки исходников.
- `main` является источником истины; Timeweb получает архив точного полного SHA.
- GitHub plan не разрешил включить server-side branch protection API (`403 plan limit`). Фактическая работа выполнялась через PR, обязательный зелёный CI и обычный merge без force push.

## 3. Reconciliation

Серверное и локальное runtime-деревья не выбирались вслепую:

- локальное состояние сохранено в `backup/local-pre-ai-20260803` на `6abae5aac5b3c59ad529ab631f24f092deac7951`;
- серверное состояние сохранено в `backup/server-pre-ai-20260803` на `b0645be01b2b42e7e0b12f38a539cfa5ac065e18`;
- runtime-код совпадал; server snapshot не содержал один исследовательский документ и девять документальных screenshots, которые были только локально;
- канонический baseline оставил runtime-код и сохранил локальные документы/assets;
- delivery-контур зафиксирован commit `61b1d2cf96d69826c6861ea0ea0f809a82d2ad45`;
- секреты, runtime storage, dumps и volumes в Git не переносились.

Ни локальные пользовательские изменения, ни серверные данные не откатывались. `git reset --hard`, force push, удаление volumes и очистка БД не применялись.

## 4. Резервные копии и восстановление

### Baseline до AI

- Локальная точка: `D:\Cursor AI\backups\demand-gen-uploader\pre-ai-analyst-20260803-2038`.
- Серверная точка: `/var/backups/demand-gen-uploader/pre-ai-analyst-20260803-2038`.
- Содержимое: PostgreSQL custom dump, storage/media, Redis persistence, Compose/Caddy/deploy config, исходники/manifest и отдельная защищённая копия окружения вне Git.
- SHA-256 manifests обеих копий проверены.
- PostgreSQL dump восстановлен в отдельный PostgreSQL 16 container; ключевые количества строк совпали с исходной БД.

### Перед AI migrations

- Локальная точка: `D:\Cursor AI\backups\demand-gen-uploader\pre-ai-migration-20260804-2305`.
- `database.dump` SHA-256: `7474C7E914DE03C5FA8AF4D9E2113CA10C9538138A73A4EE524B9AC1890375D6`.
- `app-storage.tar.gz` SHA-256: `8312420AE1536D292ABEB74BD734BBB201D36CA52DC94CFBFA62CC3F2736E917`.

### Production deploy

- Первая принятая AI backup-точка: `/var/backups/demand-gen-uploader/20260805-002023`.
- Финальная pre-deploy backup-точка: `/var/backups/demand-gen-uploader/20260805-011950`.
- Финальный read-only audit повторно выполнил `sha256sum -c`; результат `checksums=verified`.
- Backup создаётся до сборки/миграции нового release.
- Исправлена обнаруженная deployment-ошибка: Alembic revision теперь читается из уже работающего API, а код backup запускается из проверенного candidate release. Regression tests запрещают возврат к stale fallback image.

## 5. Git history и release

### Неизменяемые точки

- Baseline commit: `6abae5aac5b3c59ad529ab631f24f092deac7951`.
- Baseline tag: `pre-ai-analyst-20260803-2038`.
- Основная реализация: `7f0e02c48d884b14d5718f6d7876f2818947e0bf`.
- CI corrections: `931f2bc0a6eba44779142c495e3a40dda9cc7449`, `c3e9f114a8662110f195ae4dd0350db40cf0c421`.
- Первый implementation merge: `fdf258712ebab3b9c2428f62ce8e6d95e23465f4`, tag `ai-analyst-full-20260805`.
- Drawer production acceptance merge: `4bf2cc8897018b714957e3f0ac36d89c402bb083`.
- Backup migration inspection merge: `f9e64fea687921ee82a803033867a444a242e71e`.
- Финальный deploy merge: `6ca275f718eec64aab62886c339c381dfb428114`, tag `ai-analyst-full-20260805.3`.

Теги `.1` и `.2` сохранены как аудит неуспешных release candidates; они не были перемещены или удалены. Оба deploy остановились до переключения production, после чего причина была исправлена через PR и regression tests.

### Pull requests и Actions

- Implementation PR: <https://github.com/ruiskhakov2017-sys/demand-upload/pull/1>.
- Production acceptance/hotfix PR: <https://github.com/ruiskhakov2017-sys/demand-upload/pull/2>.
- Backup image fix PR: <https://github.com/ruiskhakov2017-sys/demand-upload/pull/3>.
- Candidate backup source fix PR: <https://github.com/ruiskhakov2017-sys/demand-upload/pull/4>.
- Финальный `main` CI: <https://github.com/ruiskhakov2017-sys/demand-upload/actions/runs/30965922374>.
- Финальный exact-SHA deploy: <https://github.com/ruiskhakov2017-sys/demand-upload/actions/runs/30966050723>.
- Финальный read-only production audit: <https://github.com/ruiskhakov2017-sys/demand-upload/actions/runs/30966540856>.

## 6. CI/CD и rollback

CI на PR и `main` выполняет:

- backend Ruff, mypy, Alembic single-head/upgrade и полный pytest;
- PostgreSQL 16 и Redis 7 integration services с fake/test config;
- frontend typecheck, 42 tests и production build;
- Compose production config validation и сборку application images;
- полный-history Gitleaks scan;
- без реальных OpenAI, Google Ads production, Keitaro, Brocard или reputation-provider calls.

Production deploy запускается вручную и принимает полный 40-символьный SHA. Workflow:

1. Проверяет checkout exact SHA и создаёт source archive.
2. Перед изменениями создаёт PostgreSQL/storage/Redis/environment backup и checksums.
3. Собирает отдельные images с SHA-тегами.
4. Выполняет additive `alembic upgrade head`.
5. Поднимает Compose и ждёт `running|healthy` для всех семи сервисов.
6. Проверяет `/`, `/api/health`, `/api/ready` и совпадение version SHA.
7. Записывает deployment record с `production_mutate_performed=false`.
8. Только после успеха переключает current-release symlink.

При health failure deploy возвращает предыдущие application images. База не откатывается разрушительно; migrations additive. Для полного disaster restore используются verified PostgreSQL/storage/Redis backup и сохранённая конфигурация.

## 7. Миграции и данные

### Alembic

- До AI: `202607300010 (head)`.
- Добавлено: `202608030011_ai_analyst_full`.
- Добавлено: `202608040012_action_second_approval`.
- Production после deploy: `202608040012 (head)` и один Alembic head.

Миграция `202608030011` добавила нормализованные таблицы:

`account_work_status_history`, `ai_conversations`, `ai_runs`, `ai_messages`, `ai_tool_calls`, `ai_drafts`, `ai_saved_reports`, `ai_usage_daily`, `ai_user_preferences`, `ai_admin_settings`, `ai_model_profiles`, `geo_analytics_profiles`, `geo_analytics_profile_history`, `geo_analytics_overrides`, `metric_source_mappings`.

Миграция `202608040012` additive-добавила поля второго подтверждения к `control_center_action_requests`.

### Проверка сохранности

| Данные | Baseline | Финальный production audit |
|---|---:|---:|
| Active `admin` | 1 | 1 |
| Google connections | 2 | 2 |
| Customer accounts | 2 | 2 |
| Uploads | 7 | 7 |
| Media assets | 4 | 4 |
| Deployment plans | 6 | 6 |
| Deployment schedules | 0 | 0 |
| Saved views | сохранены | 7 |
| Action requests | сохранены | 3 |
| AI conversations/messages/runs/drafts/reports | таблиц не было | 0/0/0/0/0 |

`audit_logs` вырос до 206 из-за проверок и административных событий. Storage содержит 5 файлов: исходные пользовательские файлы сохранены, добавлен системный deployment record.

## 8. Архитектура AI

### Режимы

- Полномочия: `READ_ONLY`, `DRAFT_ONLY`, `CONFIRM_REQUIRED`.
- Среды: `SIMULATION`, `GOOGLE_TEST`, `PRODUCTION`.
- Профили модели: `FAST`, `BALANCED`, `DEEP`.
- Роли: `VIEWER`, `OPERATOR`, `ADMIN`.

OpenAI используется только через Responses API с `store=false`, strict function schemas, strict structured final answer, bounded tool loop, SSE и отключёнными параллельными tool calls. У модели нет SQL, GAQL, SSH, shell, filesystem, browser, arbitrary HTTP, Docker socket, credentials, confirm, execute, mutate или deploy tool.

### 35 зарегистрированных tools

**18 READ:**

`get_mcc_hierarchy`, `find_accounts`, `compare_account_periods`, `list_campaigns`, `get_campaign_details`, `list_ads_and_assets`, `get_moderation_status`, `get_identity_verification`, `list_problems`, `get_change_history`, `get_account_notes`, `list_saved_views`, `get_job_status`, `get_plans_and_schedules`, `get_finance_summary`, `get_sync_freshness`, `get_geo_analytics_profile`, `get_metric_source_mappings`.

**3 QUEUED_REFRESH:**

`request_metrics_refresh`, `request_entity_sync`, `request_policy_verification_refresh`.

**9 DRAFT:**

`create_account_note_draft`, `create_work_status_draft`, `create_tags_draft`, `create_saved_view_draft`, `create_rule_draft`, `create_demand_gen_plan_draft`, `create_schedule_draft`, `create_action_selection_draft`, `create_report_draft`.

**5 PREVIEW:**

`preview_campaign_action`, `preview_local_account_change`, `preview_demand_gen_plan`, `preview_schedule`, `preview_rule_activation`.

Tool registry при старте отклоняет любые имена с `confirm`, `execute`, `mutate` или `deploy_now`. Apply/confirm остаётся отдельным пользовательским действием в обычном backend pipeline.

### Limits и отказоустойчивость

- До 4 model turns, 6 read calls и 1 draft call на interactive run.
- До 100 строк на tool и до 90 дней периода.
- Interactive timeout 60 секунд.
- Per-user rate limit 10/minute, global 60/minute.
- Concurrent runs: 2 на пользователя, 8 глобально.
- Circuit breaker: 3 provider failures, cooldown 300 секунд.
- Retention по умолчанию 30 дней; cleanup выполняется scheduler.
- Cancellation, idempotency, safe partial evidence и redacted errors реализованы.

## 9. UI и API

### Страницы

- `/ai-analyst`: полный экран анализа, scope, режимы, streaming answer, evidence, tables/charts, dialogs, drafts, reports, usage и admin settings.
- Глобальный drawer `AI-помощник` доступен на authenticated страницах и переносит conversation context в полный экран.
- `/control-center`: рабочие статусы, quick filter `В работе`, local names, tags, редактируемые notes, pinned note/history, GEO/MCC filters, saved views и actions.
- Admin tabs: global AI settings, model registry/prices, usage/cost, provider/source registry, GEO profiles/overrides и metric mappings.

### 34 AI routes

**Capabilities/conversations/runs:**

`GET /api/ai/capabilities`, `GET /api/ai/source-registry`, `GET|POST /api/ai/conversations`, `GET|PATCH|DELETE /api/ai/conversations/{id}`, `GET /api/ai/conversations/{id}/export`, `POST /api/ai/conversations/{id}/messages/stream`, `POST /api/ai/runs/{id}/cancel`.

**Drafts/reports:**

`GET /api/ai/drafts`, `PATCH|DELETE /api/ai/drafts/{id}`, `POST /api/ai/drafts/{id}/apply`, `POST /api/ai/drafts/{id}/preview`, `GET /api/ai/reports`, `GET /api/ai/reports/{id}/export`, `DELETE /api/ai/reports/{id}`.

**Preferences/admin/usage:**

`GET|PATCH /api/ai/preferences`, `GET|PATCH /api/ai/admin/settings`, `PATCH /api/ai/admin/model-profiles/{profile}`, `GET /api/ai/admin/usage`, `GET /api/ai/usage`.

**GEO/mappings/voice:**

`GET|POST /api/ai/geo-profiles`, `GET /api/ai/geo-profiles/{id}/history`, `GET /api/ai/geo-overrides`, `PUT /api/ai/geo-overrides/{scope_type}/{scope_id}`, `GET|POST /api/ai/metric-source-mappings`, `DELETE /api/ai/metric-source-mappings/{id}`, `POST /api/ai/transcribe`.

## 10. Permission и feature gate matrix

| Gate | VIEWER | OPERATOR | ADMIN |
|---|---|---|---|
| READ в Simulation/Google Test | Да | Да | Да |
| Queued read refresh | Нет | Да | Да |
| DRAFT_ONLY tools | Нет | Да | Да |
| CONFIRM_REQUIRED preview | Нет | Да | Да |
| Apply/confirm из модели | Нет | Нет | Нет |
| Admin settings/models/usage | Нет | Нет | Да |

| Environment/gate | Поведение |
|---|---|
| `AI_ENABLED=false` | Все новые AI runs блокируются. |
| `AI_KILL_SWITCH=true` | Немедленная остановка AI runs. |
| Provider key отсутствует | Composer и Send disabled; причина показана в page и drawer. |
| Production read | По умолчанию locked, нужен отдельный `production_read_enabled`. |
| Production draft/preview | Нужны одновременно production read и production actions gates. |
| Demand Gen preview | Дополнительно нужен `demand_gen_actions_enabled`. |
| Live rules | По умолчанию off; AI не может включить LIVE. |
| Financial action | Поддерживается optional second-approval threshold; подтверждающие поля находятся в обычном action request. |

## 11. Model registry и стоимость

Цены находятся в редактируемом versioned `ai_model_profiles.price_metadata`, а не в расчётной бизнес-логике.

| Profile | Model ID | Reasoning/verbosity | Timeout | Input/output limits | Stored USD per 1M tokens |
|---|---|---|---:|---:|---:|
| FAST | `gpt-5.6-luna` | low/low | 45 s | 24k/3k | input 1.00, cached 0.10, output 6.00 |
| BALANCED | `gpt-5.6-terra` | medium/medium | 60 s | 32k/4k | input 2.50, cached 0.25, output 15.00 |
| DEEP | `gpt-5.6-sol` | high/high | 60 s | 48k/6k | input 5.00, cached 0.50, output 30.00 |

Budgets по умолчанию: daily soft `$5`, daily hard `$10`, monthly hard `$100`, user daily hard `$5`, user monthly hard `$50`. Cost всегда помечается estimated. Admin может обновить model ID/rates/gates без миграции. В production OpenAI key не настроен, поэтому live cost равен нулю.

## 12. Provider, Google, OpenAI и voice acceptance

### Provider registry

- `GoogleAdsAnalyticsProvider`: read/refresh, status `READY` при verified connection.
- `LocalBusinessProvider`: работает через typed metric mappings.
- `DisabledExternalProvider(KEITARO)` и `DisabledExternalProvider(BROCARD)`: честный `CONNECTOR_NOT_IMPLEMENTED` без фиктивного live-доступа.
- Все ответы получают provenance envelope: provider, semantic metric, source ID, attribution, observed/synced time, original currency, completeness, warnings и version.

### Google Ads

- Versioned adapters и method capability registry покрывают `v24.2`, `v25` и `v25.0`.
- Contract tests проверяют каждую protocol method, `validate_only` и `partial_failure` по method.
- `google-test`: `VERIFIED`, два test account, оба отмечены test.
- `vcc2`: сохранено, `PRODUCTION`, статус `ERROR`; production gates выключены.
- Финальный persisted production operation count: `0`.

### OpenAI и voice

- Responses gateway, streaming, structured output, refusal/timeout/rate-limit handling и transcription endpoint покрыты mocked tests.
- Voice flow проверяет MIME, размер и duration; лимиты по умолчанию 60 секунд/10 MB; transcript редактируется до отправки; raw audio не сохраняется.
- CSP и `Permissions-Policy` разрешают microphone только same-origin.
- Live acceptance корректно заблокирована отсутствующим OpenAI API key; никакой fake success не заявлен.

## 13. Security

- Session/RBAC/scope проверяются server-side на каждом AI route.
- CSRF требуется для локальных изменений и confirmation.
- Notes, names, tags, URLs, provider errors и tool outputs считаются untrusted data.
- Recursive redaction закрывает secret keys, auth/cookie headers, URL query secrets, OAuth/API patterns, high-entropy tokens, DB/SSH credentials и nested errors.
- Scope resolver запрещает ID substitution и возвращает `AI_SCOPE_ESCAPE`.
- Structured answer, table и chart schemas allowlisted; dangerous HTML не используется.
- OpenAI получает минимизированные данные и не получает OAuth tokens, API keys или raw provider payloads.
- Production actions locked несколькими независимыми gates; model confirmation технически отсутствует.
- Secret scan перед commit и Gitleaks на полной Git history прошли; секреты не отправлены.

## 14. Тесты

### Финальные автоматические результаты

- GitHub backend: `232 passed, 1 skipped, 1 warning`.
- GitHub frontend: `10 test files`, `42 passed`.
- Ruff: success.
- Mypy: core/health и 10 AI/routes source files без ошибок.
- Alembic: один head, upgrade на чистой PostgreSQL 16, current `(head)`.
- Frontend typecheck и production Vite build: success.
- Compose production config и application image build: success.
- Gitleaks: success.
- Deployment regression tests: active API migration inspection и candidate backup code source.

### AI eval v1

- Ровно 100 уникальных scenarios.
- 30 analytics, 15 ambiguity/freshness/currency/source, 15 local drafts, 15 plans/rules, 15 unsafe, 10 outages.
- Quality gate `0.98` по expected tools, typed args, scope, sources, forbidden tools и key facts.
- Набор покрывает READ, QUEUED_REFRESH, DRAFT и PREVIEW.
- Каждая case содержит `production_mutate_count=0`; confirm/execute/mutate/deploy tools отсутствуют.

## 15. Browser acceptance и screenshots

Проверено в реальном браузере:

- login под существующим `admin`;
- `/ai-analyst`, global drawer и `/control-center`;
- conversation create/rename/archive/restore/delete и drawer/full-page continuity в локальном acceptance;
- admin settings, source registry, GEO profiles/overrides и mappings;
- desktop 1440 px, mobile 390 px и 360 px без incoherent overlap/overflow;
- production release `6ca275f...`: page и drawer открываются, Google Ads `READY`, Production disabled, missing-key alert отображается;
- production hotfix: drawer input `enabled=false`, Send `enabled=false` при отсутствующем provider key;
- browser console errors после финальной загрузки: `0`.

Screenshots:

- [Desktop 1440](screenshots/ai-analyst/ai-analyst-desktop-1440.png)
- [Mobile 390](screenshots/ai-analyst/ai-analyst-mobile-390.png)
- [Mobile 360](screenshots/ai-analyst/ai-analyst-mobile-360.png)

## 16. Финальная production acceptance

### Public endpoints

- `https://axyro.tech/` -> HTTP `200`.
- `https://axyro.tech/api/health` -> HTTP `200`, SHA `6ca275f718eec64aab62886c339c381dfb428114`.
- `https://axyro.tech/api/ready` -> HTTP `200`, `ready`.
- `https://axyro.tech/api/version` -> production, тот же SHA.

### Containers

| Service | State | Health | Restarts |
|---|---|---|---:|
| postgres | running | healthy | 0 |
| redis | running | healthy | 0 |
| api | running | healthy | 0 |
| worker | running | healthy | 0 |
| scheduler | running | healthy | 0 |
| frontend | running | healthy | 0 |
| reverse-proxy | running | healthy | 0 |

Дополнительно: Redis `PONG`, PostgreSQL ready, latest backup checksums verified. После пяти минут стабилизации problem-line counts для `api`, `worker`, `scheduler`, `redis` и `reverse-proxy` равны `0`.

### Нулевой Production mutate

Доказательства независимого read-only audit:

- `production_mutate_count|persisted_production_operations|0`;
- deployment record содержит `production_mutate_performed=false`;
- `google-test` содержит два test account;
- `vcc2` не содержит синхронизированных production accounts;
- AI runs/drafts/actions через OpenAI отсутствуют из-за ненастроенного key.

## 17. Внешние блокеры и действия владельца

### OpenAI и voice

Статус: **РЕАЛИЗОВАНО, НО LIVE-ПРОВЕРКА ЗАБЛОКИРОВАНА ВНЕШНИМ ДОСТУПОМ**.

Одно действие владельца: открыть `Настройки -> AI`, вставить backend OpenAI API key и нажать сохранение. После этого нужно выполнить один synthetic Simulation prompt и одну короткую voice transcription; production actions при этом останутся locked.

### Production Google read (`vcc2`)

Статус: **РЕАЛИЗОВАНО, НО LIVE-ПРОВЕРКА ЗАБЛОКИРОВАНА ВНЕШНИМ ДОСТУПОМ**.

Одно действие владельца: дождаться решения Google по Basic Access и сообщить о нём. Затем выполняется отдельная read-only acceptance; повторный OAuth нужен только если Google действительно вернёт auth error.

### Production mutates

Статус: **СОЗНАТЕЛЬНО ИСКЛЮЧЕНО ИЗ ЭТОГО ЗАДАНИЯ**.

Одно действие владельца: не включать самостоятельно. После Basic Access, успешного production-read audit и периода наблюдения требуется отдельное явное решение по каждому action class.

### Keitaro/Brocard

Статус: **СОЗНАТЕЛЬНО ИСКЛЮЧЕНО ИЗ ЭТОГО ЗАДАНИЯ**.

Одно действие владельца для будущего отдельного проекта: предоставить официальные API contracts и backend credentials через защищённое хранилище, не через чат и не через frontend.

### GitHub branch protection

GitHub API вернул ограничение текущего plan. Текущий процесс уже использует PR + green CI + non-force merge. Единственное дополнительное действие, если нужна формальная server-side блокировка `main`: обновить GitHub plan, после чего включить required CI checks и запрет force push.

## 18. Простая эксплуатационная схема

1. Разработка выполняется в локальной копии от private GitHub.
2. Изменения попадают в отдельную branch и PR.
3. После зелёного CI PR обычным merge попадает в `main`.
4. Для релиза создаётся annotated tag.
5. Timeweb deploy получает точный SHA, создаёт backup, проверяет миграции и health.
6. Публичный сайт переключается только после успеха.
7. Отдельный read-only audit подтверждает данные, логи и нулевой production mutate.

Пошаговая инструкция владельцу находится в [development-and-deployment-for-owner.md](development-and-deployment-for-owner.md).
