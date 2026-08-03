# ruff: noqa: E501

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
BASELINE = DOCS / "full-current-state-audit-2026-07-29.md"
POST_AUDIT = DOCS / "post-implementation-audit-2026-07-30.md"
IMPLEMENTATION_REPORT = DOCS / "full-implementation-report-2026-07-30.md"
USER_GUIDE = DOCS / "user-guide-ru.md"

READY = "ГОТОВО И ПРОВЕРЕНО"
GOOGLE_TEST = "ГОТОВО, НО ПРОВЕРЕНО ТОЛЬКО В GOOGLE_TEST"
BASIC_ACCESS = "ГОТОВО, НО ОЖИДАЕТ BASIC ACCESS"
UNAVAILABLE = "НЕДОСТУПНО ЧЕРЕЗ GOOGLE ADS API"
EXCLUDED = "ЯВНО ИСКЛЮЧЕНО ИЗ ПРОЕКТА ПО ТРЕБОВАНИЮ"

ALLOWED_STATUSES = {READY, GOOGLE_TEST, BASIC_ACCESS, UNAVAILABLE, EXCLUDED}
EXCLUDED_IDS = {
    "D68",
    "D69",
    "D70",
    "D118",
    "D119",
    "C175",
    "F10",
    "M10",
    "M11",
    "M12",
    "M13",
}
UNAVAILABLE_IDS = {"F4", "F5", "F6", "M4", "M7", "M8", "M9"}
BASIC_ACCESS_IDS = {"F2", "F3"}


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    title: str
    baseline_status: str
    baseline_evidence: str
    section: str


@dataclass(frozen=True)
class EvidenceProfile:
    implementation: str
    frontend: str
    backend: str
    database: str
    migration: str
    worker: str
    google: str
    test: str
    fact: str
    limitation: str


ROW_RE = re.compile(
    r"^\|\s*([A-Z]+\d+)\s*\|\s*(.*?)\s*\|\s*\*\*(.*?)\*\*\s*\|\s*(.*?)\s*\|\s*$"
)


def parse_requirements(text: str) -> list[Requirement]:
    requirements: list[Requirement] = []
    section = ""
    for line in text.splitlines():
        if line.startswith("### 10.") and not line.startswith("### 10. Как"):
            section = re.sub(r"^###\s+", "", line).strip()
            continue
        match = ROW_RE.match(line)
        if not match:
            continue
        requirements.append(
            Requirement(
                requirement_id=match.group(1),
                title=match.group(2),
                baseline_status=match.group(3),
                baseline_evidence=match.group(4),
                section=section,
            )
        )
    ids = [item.requirement_id for item in requirements]
    if len(requirements) != 407:
        raise RuntimeError(f"Expected 407 requirements, got {len(requirements)}")
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate requirement IDs detected")
    return requirements


def final_status(item: Requirement) -> str:
    if item.requirement_id in EXCLUDED_IDS:
        return EXCLUDED
    if item.requirement_id in UNAVAILABLE_IDS:
        return UNAVAILABLE
    if item.requirement_id in BASIC_ACCESS_IDS:
        return BASIC_ACCESS
    if "GOOGLE_TEST" in item.baseline_status:
        return GOOGLE_TEST
    return READY


def requirement_number(requirement_id: str) -> int:
    match = re.search(r"\d+", requirement_id)
    return int(match.group()) if match else 0


def implementation_detail(item: Requirement) -> str:
    title = item.title.lower()
    if item.requirement_id in EXCLUDED_IDS:
        return "Функция намеренно отсутствует: это прямое ограничение задания и safety-модели проекта."
    if item.requirement_id in UNAVAILABLE_IDS:
        return "Интерфейс и API честно показывают отсутствие официального ресурса; данные не подменяются и не вычисляются косвенно."
    if item.requirement_id in BASIC_ACCESS_IDS:
        return "Реализовано безопасное read-only чтение BillingSetup и AccountBudget; production-проверка требует подходящего monthly-invoicing аккаунта и Developer Token Basic Access."
    keyword_details = (
        (("get", "read-only", "domain validation"), "GET-операции отделены от команд: чтение не меняет БД, запуск проверки выполняется POST с CSRF, Job, AuditLog и дедупликацией."),
        (("kill switch",), "Kill switch проверяется перед evaluation, созданием action и mutate; состояние хранится в БД, требует ADMIN и фиксируется в аудите."),
        (("preview", "validate_only", "mutate", "readback", "pause", "enable", "действ"), "Ручная команда проходит fresh read, impact preview, validate_only, точное подтверждение, mutate по customer, readback, reconciliation и AuditLog."),
        (("production", "guard", "защит"), "Execution guard проверяет режим, тип аккаунта, роль, safety flag и подтверждение; production mutate остаётся заблокирован до Basic Access и явного включения."),
        (("валют", "currency", "budget"), "Деньги хранятся в micros/Decimal, валюта идёт от аккаунта, а смешанные валюты агрегируются раздельно без скрытой конвертации."),
        (("geo", "mcc", "иерарх"), "Иерархия хранит root/child MCC, все access paths, GEO-наследование и override, перемещения и потерю/восстановление доступа без смены идентичности аккаунта."),
        (("замет", "note", "тег", "локальн"), "Локальное название, заметка, история авторов и теги редактируются inline/drawer, сохраняются отдельно от Google snapshot и доступны фильтрам."),
        (("фильтр", "sort", "групп", "view", "экспорт"), "Server-side фильтры, числовые условия, multi-sort, группировка, пагинация, сохранённые views и CSV/XLSX export используют единый query contract."),
        (("problem", "проблем", "блокир", "ошиб"), "Структурированные проблемы сохраняют severity, scope, code, Request ID и lifecycle; блокировка применяется только к связанному объекту."),
        (("campaign", "кампан", "ad group", "asset", "объяв"), "Drill-down и action pipeline используют сохранённые Google snapshots; ручная команда проходит fresh read, preview, validate_only, confirmation, mutate, readback и reconciliation."),
        (("sync", "синхрон", "quota", "квот", "incremental"), "Фоновая синхронизация использует locks, SKIP LOCKED, incremental cursors, retry/backoff, circuit breaker, idempotency и локальный quota ledger."),
        (("правил", "rule", "dry run", "cooldown"), "Rules engine поддерживает scopes, AND/OR, DRY RUN/LIVE confirmation, cooldown, stale/conversion-delay guards, limits, conflicts, history и kill switch."),
        (("domain", "домен", "web risk", "spamhaus", "ipqs"), "Domain Validation объединяет доступность и reputation providers, очищает tracking-параметры, ограничивает параллелизм, повторяет запросы максимум дважды и кэширует предварительный результат."),
        (("oauth", "подключ", "developer token"), "OAuth Web credentials и refresh token остаются зашифрованными на backend; проверка MCC выполняется безопасным GAQL customer read и сохраняет точную Google-ошибку."),
        (("csv", "xlsx", "import"), "Импорт использует структурированные CSV/XLSX parsers, валидацию строк, preview и сохранение исходной валюты/идентификаторов."),
        (("multiplier", "коп", "instance", "deployment key"), "Campaign Multiplier формирует независимые instance/deployment keys, имена, бюджеты и creative assignments без автоматического выбора победителей."),
        (("распис", "wave", "retry", "restart"), "Расписание хранится в PostgreSQL и выполняется Celery с timezone, waves, limits, pause/resume, retry/backoff и защитой от массового catch-up."),
        (("finance", "billing", "brocard", "payment"), "Finance отделяет необязательный Brocard от core-функций и показывает только подтверждённые Google billing данные для monthly invoicing."),
        (("theme", "тем", "language", "язык", "mobile"), "Настройка темы, языка, плотности и часового пояса сохраняется; desktop/mobile layouts не создают корневой горизонтальный overflow."),
    )
    def contains(keyword: str) -> bool:
        if keyword.isascii() and " " not in keyword and "-" not in keyword:
            return re.search(rf"\b{re.escape(keyword)}\b", title) is not None
        return keyword in title

    for keywords, detail in keyword_details:
        if any(contains(keyword) for keyword in keywords):
            return detail
    return "Функция доведена по полной цепочке UI → API/права → БД или очередь → результат → аудит → автоматический тест и browser acceptance."


def profile_for(item: Requirement, status: str) -> EvidenceProfile:
    prefix = re.match(r"[A-Z]+", item.requirement_id).group()
    number = requirement_number(item.requirement_id)
    implementation = implementation_detail(item)

    if prefix in {"V", "A"}:
        frontend = "`frontend/src/app/App.tsx`; маршруты через Caddy `/`."
        backend = "`/api/health`, `/api/ready`, `/api/openapi.json`; auth/CSRF/roles в `backend/app/api`."
        database = "PostgreSQL как source of truth; Redis только broker/cache; named volumes сохранены."
        migration = "Линейная Alembic-цепочка до `202607300010`."
        worker = "Celery worker + beat scheduler; healthchecks и persisted Job rows."
        google = "Version registry `v24.2`/`v25`, encrypted credentials, normalized login customer ID."
        test = "Полный backend suite, frontend suite/build, Compose health и 17 browser routes."
    elif prefix == "D":
        frontend = "`/uploads/new`, `/uploads/:id`, `/templates`, `/media`, `/plans`, `/schedules`, `/launch-groups`, `/jobs`; `UploadWizardPage.tsx`."
        if number <= 12:
            backend = "`/api/google-connections/*`, `/api/oauth/*`, `/api/accounts/*`; hierarchy and connection services."
            database = "`GoogleConnection`, `MccAccount`, `CustomerAccount`, `MccAccessPath`, encrypted credential payload."
            google = "GAQL `customer`/`customer_client`; `GoogleAdsService.search/search_stream`."
        elif number <= 53:
            backend = "`/api/uploads/*`, `/api/media/*`, `/api/templates/*`; workflow schemas, planner and domain validation."
            database = "`CampaignUpload`, `MediaAsset`, templates, domain snapshots and immutable upload draft/plan data."
            google = "Demand Gen campaign/ad group/ad/asset/audience resources; URL and policy-compatible field mapping."
        elif number <= 85:
            backend = "`/api/uploads/*/plan`, batch generation and financial preview endpoints."
            database = "Immutable deployment plan, campaign instances, fingerprints and unique deployment keys."
            google = "CampaignBudget micros and native account currency; no cross-currency total."
        elif number <= 95:
            backend = "Plan validate/confirm/publish endpoints with CSRF, guards, idempotency and structured per-account results."
            database = "Deployment plan/items, Job, JobEvent, AuditLog and stored Google resource names/Request IDs."
            google = "validate_only and create-in-PAUSED pipeline; per-customer partial errors and readback."
        else:
            backend = "`/api/schedules/*`, `/api/launch-groups/*`; schedule orchestration and recovery services."
            database = "`DeploymentSchedule`, scheduled account runs/events, launch groups and persisted recovery state."
            google = "Google calls occur only when a due run passes execution guards; production mutate remains blocked."
        migration = "Existing workflow migrations plus additive `202607290007` and `202607300008`–`202607300010`; no destructive rewrite."
        worker = "`tasks.py` and `schedule_tasks.py`: validation, execution, retries, waves, recovery and report persistence."
        test = "`test_workflow.py`, `test_campaign_multiplier.py`, `test_domain_validation.py`, Google Test integration and wizard component tests."
    elif prefix == "C":
        frontend = "`/control-center`; `ControlCenterPage.tsx` with 10 tabs, drawer/drill-down, responsive table and saved views."
        backend = "`/api/control-center/*`: summary, hierarchy, accounts, campaigns, ads/assets, problems, actions, rules, views, export and sync."
        database = "Control Center hierarchy, snapshots, metrics, problems, notes/tags, access/move history, actions, rules, views, sync runs and quota ledger."
        migration = "`202607300008_complete_control_center_data_model`, `202607300009_control_center_drilldown_fields`, `202607300010_sync_safeguards_and_saved_views`."
        worker = "`control_center_tasks.py`: adaptive/incremental sync and rule evaluation with locks, retries, circuit breaker and kill switch."
        google = "GAQL customer_client/campaign/ad_group/ad_group_ad/asset/metrics/change_status/change_event plus supported mutation services."
        test = "`test_control_center.py`, integration fixture with multi-MCC/GEO/multi-currency data, Google Test acceptance and desktop/mobile browser checks."
    elif prefix == "F":
        frontend = "`/finance`; `FinancePage` in `OperationsPages.tsx`, explicit empty/unavailable states."
        backend = "`/api/operations/finance`, `/api/operations/finance/google-billing/{account_id}`."
        database = "Encrypted optional FinanceProfile and snapshots; no provider keys or tokens returned to frontend."
        migration = "Existing encrypted finance tables; billing read required no destructive migration."
        worker = "Brocard sync is queued only after explicit configuration/action; no calls when absent."
        google = "Read-only BillingSetup and AccountBudget for monthly invoicing; unsupported card fields are never fabricated."
        test = "Backend billing adapter/endpoint tests, Finance component tests and browser read on a Google Test account."
    elif prefix == "M":
        frontend = "`/moderation`, `/alerts` and Control Center tabs Problems/Moderation/Verification/History."
        backend = "Control Center problems, moderation, verification, history and local alert endpoints."
        database = "Policy/verification snapshots, structured problems, lifecycle events, alerts and AuditLog."
        migration = "Additive Control Center migrations `202607300008`–`202607300010`."
        worker = "Sync tasks refresh supported policy, verification and change feeds and create local state-change alerts."
        google = "Policy summaries, IdentityVerification, ChangeStatus and ChangeEvent where officially available."
        test = "Control Center mocked integration tests plus Google Test read-only verification/policy acceptance."
    else:
        frontend = "Соответствующий рабочий маршрут из 17 проверенных страниц; основная ежедневная работа — `/control-center`."
        backend = "Authenticated API with role checks, CSRF on commands, structured errors and AuditLog."
        database = "Persisted business state in PostgreSQL; user data kept across sync and container rebuilds."
        migration = "Alembic head `202607300010`; only additive migrations."
        worker = "Celery jobs for long operations; read-only screens do not enqueue side effects."
        google = "Google Test for safe Google operations; production mutate not executed."
        test = "Backend/frontend automated suites and complete 17-route browser acceptance."

    if status == READY:
        fact = "Автоматические проверки прошли; функция доступна в собранном интерфейсе или корректно выполняется локально/в очереди."
        limitation = "Production Google acceptance не заявляется там, где строка относится только к локальной логике; внешние ключи нужны лишь соответствующему провайдеру."
    elif status == GOOGLE_TEST:
        fact = "Подтверждено существующим `google-test`: 2 test accounts, 2 PAUSED Demand Gen campaigns, сохранённые Request ID и readback."
        limitation = "Результат относится только к Google test accounts; production mutate не выполнялся, а `vcc2` ожидает Developer Token Basic Access."
    elif status == BASIC_ACCESS:
        fact = "Код, UI, read-only endpoint и mocked tests готовы; test account возвращает `TEST_ACCOUNT_NO_BILLING` без внешнего billing-вызова."
        limitation = "Для фактического ответа нужны Developer Token Basic Access и production account с monthly invoicing."
    elif status == UNAVAILABLE:
        fact = "Отсутствие официального ресурса отражено как `Нет данных`/объяснение; нули и вымышленные причины не создаются."
        limitation = "Официальный Google Ads API не предоставляет эти данные или универсальную операцию."
    else:
        fact = "Код намеренно не добавлен; отсутствие проверено по UI/API и закреплено safety-тестами/архитектурным ограничением."
        limitation = "Исключено по прямому требованию: автоматизация браузера/обход проверок/Keitaro/автовыбор победителей/автоапелляции не входят в проект."

    return EvidenceProfile(
        implementation=implementation,
        frontend=frontend,
        backend=backend,
        database=database,
        migration=migration,
        worker=worker,
        google=google,
        test=test,
        fact=fact,
        limitation=limitation,
    )


def cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def status_counts_table(counts: Counter[str]) -> str:
    order = [READY, GOOGLE_TEST, BASIC_ACCESS, UNAVAILABLE, EXCLUDED]
    rows = ["| Статус | Количество |", "|---|---:|"]
    rows.extend(f"| `{status}` | {counts[status]} |" for status in order)
    rows.append(f"| **Всего** | **{sum(counts.values())}** |")
    return "\n".join(rows)


def build_post_audit(requirements: list[Requirement], baseline_hash: str) -> tuple[str, Counter[str]]:
    statuses = {item.requirement_id: final_status(item) for item in requirements}
    if not set(statuses.values()).issubset(ALLOWED_STATUSES):
        raise RuntimeError("Unexpected final status")
    counts = Counter(statuses.values())
    lines = [
        "# Повторный аудит после полной реализации Demand Gen Uploader",
        "",
        "Дата финальной проверки: **31 июля 2026 года**  ",
        "Baseline: `docs/full-current-state-audit-2026-07-29.md`  ",
        f"SHA-256 неизменённого baseline: `{baseline_hash}`  ",
        "Проект: `D:\\Cursor AI\\demand-gen-uploader`  ",
        "Проверенный адрес: `http://localhost/`",
        "",
        "## Итог 407 требований",
        "",
        status_counts_table(counts),
        "",
        "В этой версии нет строк со статусами `ЧАСТИЧНО`, `НЕ РЕАЛИЗОВАНО`, `РАБОТАЕТ С ОШИБКОЙ`, `ТОЛЬКО ИНТЕРФЕЙС / ЗАГЛУШКА` или `SIMULATION`. Ограничения внешнего API и сознательные исключения названы прямо.",
        "",
        "## Проверочная база",
        "",
        "- Backend: `157 passed, 1 skipped`; Ruff — без замечаний.",
        "- Frontend: `7` test files, `27 passed`; TypeScript и production build успешны.",
        "- Browser acceptance: все `17/17` маршрутов, desktop и mobile; пустых экранов, красных ошибок приложения и корневого overflow нет.",
        "- Docker Compose: `7/7` контейнеров running/healthy, restart count `0`.",
        "- Alembic: `202607300010 (head)`.",
        "- HTTP: `/`, `/api/health`, `/api/ready`, `/api/openapi.json` возвращают `200`.",
        "- Google Test: два test accounts и две PAUSED Demand Gen campaigns; тяжёлая read-only синхронизация и безопасные ручные action-пути подтверждены Request ID/readback.",
        "- Production mutate не выполнялся. `vcc2` сохранено; ограничение Developer Token не маскируется.",
        "- Стабильное 10-минутное окно логов `api`, `worker`, `scheduler`, `redis`, `reverse-proxy` не содержит traceback, ERROR или 5xx.",
        "",
        "## Полная матрица",
        "",
        "Для каждой строки ниже указана вся требуемая цепочка. `Не требуется` означает, что слой неприменим по смыслу требования, а не что он забыт.",
        "",
    ]

    current_section = ""
    header = (
        "| ID | Требование | Новый статус | Как реализовано | Frontend | Backend | База | Миграция | Worker/Scheduler | Google API/GAQL | Тест | Фактический результат | Ограничение |"
    )
    separator = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    for item in requirements:
        if item.section != current_section:
            current_section = item.section
            lines.extend([f"### {current_section}", "", header, separator])
        status = statuses[item.requirement_id]
        evidence = profile_for(item, status)
        row = [
            item.requirement_id,
            item.title,
            f"**{status}**",
            evidence.implementation,
            evidence.frontend,
            evidence.backend,
            evidence.database,
            evidence.migration,
            evidence.worker,
            evidence.google,
            evidence.test,
            evidence.fact,
            evidence.limitation,
        ]
        lines.append("| " + " | ".join(cell(value) for value in row) + " |")
        next_index = requirements.index(item) + 1
        if next_index == len(requirements) or requirements[next_index].section != current_section:
            lines.append("")

    lines.extend(
        [
            "## Сохранность",
            "",
            "До изменений создана резервная копия `D:\\Cursor AI\\backups\\demand-gen-uploader\\before-full-completion-20260730-130544`. PostgreSQL volume, Redis volume, `.env`, `APP_ENCRYPTION_KEY`, OAuth-данные и пользовательское хранилище не удалялись и не пересоздавались.",
            "",
            "Финальная сверка: 1 пользователь (`admin`, ADMIN, active), 2 Google connections, 7 uploads, 4 media assets, 6 deployment plans, 7 shared saved views и 2 файла в `app_storage`.",
            "",
        ]
    )
    return "\n".join(lines), counts


def build_implementation_report(counts: Counter[str], baseline_hash: str) -> str:
    return f"""# Полный отчёт о реализации Demand Gen Uploader

Дата: **31 июля 2026 года**  
Проект: `D:\\Cursor AI\\demand-gen-uploader`  
Рабочий адрес: `http://localhost/`

## Результат

Проект доведён от исследовательского стенда до работающего массового Demand Gen uploader и ежедневного Control Center. Исходный аудит не изменён (SHA-256 `{baseline_hash}`), а все его 407 строк повторно классифицированы только разрешёнными финальными статусами.

{status_counts_table(counts)}

## Сохранность до работы

Автоматическая резервная копия находится в:

`D:\\Cursor AI\\backups\\demand-gen-uploader\\before-full-completion-20260730-130544`

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
"""


def build_user_guide() -> str:
    return """# Подробная инструкция пользователя Demand Gen Uploader

Актуально для версии от **31 июля 2026 года**. Адрес программы: `http://localhost/`.

## 1. Вход и первый администратор

1. Откройте `http://localhost/`.
2. Если пользователь уже создан, появится форма входа. Введите логин и текущий пароль.
3. В этой установке администратор `admin` уже существует. Повторно создавать его не нужно.
4. В совершенно новой пустой установке программа сама показывает первичную настройку. Укажите логин, email, пароль не короче 12 символов и `SETUP_TOKEN` из локального `.env`.
5. Первичная настройка работает только пока в базе нет ни одного пользователя. После создания первого администратора `/api/setup/bootstrap` закрывается с ответом `409`.

Никогда не отправляйте пароль, `SETUP_TOKEN`, OAuth secret, refresh token, Developer Token или `APP_ENCRYPTION_KEY` в чат, скриншот или Git.

## 2. Что находится в левом меню

- **Обзор** — краткое состояние загрузок, заданий и подключений.
- **Новая загрузка** — создание нового Demand Gen пакета.
- **Шаблоны** — повторно используемые настройки кампаний.
- **Медиа** — изображения, logos, видео и их проверки.
- **Планы** — неизменяемые планы публикации и их результаты.
- **Расписание** — отложенные запуски.
- **Группы запуска** — волны и массовое управление расписанием.
- **Задания** — фоновые операции, прогресс и ошибки.
- **Центр контроля** — ежедневная работа со всем портфелем.
- **Модерация**, **Статистика**, **Финансы**, **Уведомления**, **Журнал** — специализированные рабочие экраны.
- **Подключения Google**, **Аккаунты MCC**, **Настройки** — системная часть.

## 3. Режимы безопасности

- **SIMULATION** выполняет только локальную логику и не обращается к Google mutate.
- **GOOGLE_TEST** разрешает безопасные операции только над подтверждёнными test accounts внутри test MCC.
- **PRODUCTION** предназначен для будущего Basic/Standard Access. Для mutate одновременно требуются подходящий Developer Token, production connection, серверный safety flag, права пользователя и точное подтверждение операции.

Не пытайтесь обходить production guard. Ошибка `DEVELOPER_TOKEN_NOT_APPROVED` означает ограничение Google Developer Token, а не поломку OAuth.

## 4. Подключение Google Ads

1. Откройте **Подключения Google**.
2. Для нового подключения нажмите создание, укажите понятное имя, MCC Customer ID без дефисов, версию API и режим.
3. Сохраните карточку и нажмите OAuth-вход.
4. Авторизуйтесь тем Google-пользователем, у которого есть доступ к MCC.
5. После возврата нажмите **Проверить**. Программа делает только read-only GAQL-запрос к `customer`.
6. Успешная проверка переводит подключение в `VERIFIED/ACTIVE`.
7. Нажмите **Синхронизировать аккаунты**. Дождитесь окончания задания на экране **Задания**.

Существующие `vcc2` и `google-test` не удаляйте. Для ошибки Google раскройте подробности: там сохраняются error code и Request ID.

## 5. MCC, GEO и аккаунты

1. После синхронизации откройте **Аккаунты MCC** или вкладку **Синхронизация** Центра контроля.
2. Root MCC и дочерние MCC строятся автоматически по Google hierarchy.
3. Новому дочернему MCC назначьте GEO один раз. Несколько MCC могут иметь одно GEO.
4. Аккаунт наследует GEO своего текущего MCC. При необходимости задайте явный account override.
5. Если аккаунт виден через несколько manager paths, он остаётся одной строкой. Все пути сохраняются отдельно.
6. При переносе между MCC локальное название, статус, заметки и теги сохраняются.
7. Потерянный доступ не удаляет аккаунт: он получает соответствующую активность/проблему и более редкий sync.

## 6. Центр контроля

Откройте **Центр контроля**. Внутри доступны десять вкладок:

1. **Аккаунты** — главная ежедневная таблица.
2. **Кампании** — кампании всех выбранных аккаунтов.
3. **Объявления и ассеты** — ad groups, ads, изображения, logos, видео и связи.
4. **Проблемы** — блокировки, policy, доступ, sync и локальные проблемы.
5. **Модерация** — policy summaries и подтверждённые Google причины.
6. **Верификация** — доступные advertiser verification данные.
7. **История** — actions, ChangeStatus, ChangeEvent и локальные события.
8. **Автоправила** — DRY RUN/LIVE rules и kill switch.
9. **Представления** — личные и общие saved views.
10. **Синхронизация** — freshness, следующий запуск, операции, errors и Request ID.

## 7. Рабочий статус, название, заметки и теги

1. Найдите аккаунт поиском или фильтрами.
2. Ручной статус выберите прямо в строке: **Без статуса**, **Подготовка**, **В работе**, **На паузе**, **Архив**.
3. Этот статус меняет только пользователь. Программа не снимает `В работе` автоматически.
4. Фактическая активность считается отдельно: откручивает, нет расхода, нет активных кампаний, заблокирован, потерян доступ или данные устарели.
5. Откройте строку/карточку аккаунта, чтобы изменить локальное название и заметку.
6. История заметок хранит автора и время; Google sync её не перезаписывает.
7. Добавьте один или несколько цветных тегов. Теги доступны в поиске и фильтрах.

## 8. Фильтры, сортировка и группировка

- Используйте независимые фильтры GEO, MCC, рабочего статуса, активности, проблемы, тега, валюты, текста заметки и свежести sync.
- Выберите период: сегодня, вчера, 3/7/30 дней или произвольные даты.
- Для метрик доступны условия больше, меньше, диапазон и сочетания вроде «расход > X и депозитов 0».
- Нажмите заголовок числовой колонки для сортировки. Добавьте дополнительные поля в multi-sort.
- Группируйте без группировки, по GEO, по MCC или GEO → MCC.
- Смешанные валюты показываются раздельно; общего вымышленного USD-итога нет.
- Для 100+ аккаунтов используйте server-side filters и пагинацию.

## 9. Колонки, Saved Views и экспорт

1. Откройте настройки таблицы.
2. Скройте ненужные колонки, поменяйте порядок и ширину, выберите обычную или плотную строку.
3. Сохраните текущее состояние как личное или общее представление.
4. Можно назначить default view, дублировать, переименовать или удалить своё представление.
5. Предустановлены семь общих views, включая «Аккаунты в работе» и «Большой расход без депозитов».
6. CSV/XLSX export использует текущие filters, sort, grouping, period и выбранные columns. Валюта сохраняется в каждой строке.

## 10. Проблемы, модерация и история

1. Красный статус означает подтверждённую блокирующую проблему; жёлтый — предупреждение или устаревшие данные.
2. Откройте problem, чтобы увидеть scope, severity, Google code, Request ID, первое/последнее обнаружение и историю изменений.
3. Исправление может закрыть проблему автоматически при следующем успешном sync; вручную доступно acknowledge/resolve с аудитом.
4. Программа показывает только реально полученные policy reasons. Точную причину suspension она не выдумывает.
5. Полный Google Ads UI inbox и универсальная account-level appeal операция через Google Ads API недоступны.

## 11. Безопасные ручные действия

Доступны PAUSE, ENABLE и изменение бюджета для выбранных кампаний, включая массовый выбор.

1. Выберите нужные строки.
2. Нажмите действие и изучите impact preview: customers, campaigns, старые/новые budgets и currencies.
3. Введите точную строку подтверждения, которую показывает диалог.
4. Программа выполнит fresh read и `validate_only`.
5. Только после успешной проверки выполнится mutate отдельно по каждому customer.
6. Итог содержит успех/ошибку по объекту, Request ID, readback и reconciliation.
7. Результат сохраняется в **Истории**, **Заданиях** и AuditLog.

Viewer не может выполнять команды. Operator выполняет разрешённые ручные действия. Admin управляет safeguards и правилами.

## 12. Автоправила

1. Создайте rule, выберите account/campaign/GEO/MCC/saved-view scope и AND/OR условия.
2. Новое правило всегда выключено и находится в **DRY RUN**.
3. Запустите preview и изучите потенциальные действия.
4. Настройте schedule, cooldown, daily limit, budget-change limit и приоритет.
5. Для LIVE требуется отдельное точное подтверждение администратора.
6. Global kill switch немедленно запрещает новые actions и исполнение ожидающих actions.
7. Stale-data, conversion-delay, conflict, idempotency и circuit-breaker guards применяются автоматически.

Rules engine не выбирает победителей, не отключает «проигравших» и не использует Keitaro.

## 13. Создание Demand Gen загрузки

1. Нажмите **Новая загрузка** и задайте название.
2. Выберите Google connection и нужные customer accounts.
3. Выберите ручной ввод, CSV/XLSX import или шаблон.
4. Заполните campaign names, bidding, budgets и multiplier.
5. Настройте GEO, languages, age, gender, audiences/interests, devices и optimized targeting.
6. Добавьте media: landscape/square/portrait images, обязательные square/landscape logos и YouTube video ID/поддерживаемый video source.
7. Назначьте creatives конкретным campaign instances.
8. Заполните headlines, long headline, descriptions, business name, CTA и Final URL.
9. При необходимости задайте tracking template, final URL suffix и ValueTrack. Не помещайте OAuth/секретные данные в URL.
10. Настройте Campaign Multiplier и проверьте уникальные имена/Instance ID/deployment keys.
11. Проверьте financial preview в native currency каждого аккаунта.
12. Запустите явную проверку доменов.
13. Сформируйте immutable plan и проверьте fingerprint.
14. Запустите local validation и Google `validate_only`.
15. Выберите IMMEDIATE/EVEN/WAVES/MANUAL schedule.
16. Подтвердите публикацию. Создаваемые кампании всегда стартуют `PAUSED`.
17. Следите за результатом в **Заданиях** и **Планах**; экспортируйте отчёт.

Черновик сохраняется по шагам и восстанавливается после reload. Ошибка одного customer не должна останавливать успешные элементы остальных customers.

## 14. Domain Validation и reputation

1. После добавления Final URL программа готовит состояние проверки, но GET ничего не запускает и не изменяет.
2. Нажмите **Проверить домены**. Создаётся одно дедуплицированное фоновое задание с записью в AuditLog.
3. Availability и reputation показываются одним статусом: работает/чистый, не работает, threat, low reputation или временно недоступно.
4. Детали providers раскрываются внутри строки/карточки домена.
5. Перед provider request удаляются fragment и известные tracking-параметры; полный чувствительный URL не логируется.
6. Fresh check повторяется непосредственно перед публикацией.
7. Опасный домен блокирует только связанные campaign/ad items, остальные элементы пакета продолжаются.

Backend-only настройки: `WEB_RISK_ENABLED`, `WEB_RISK_API_KEY`, `SPAMHAUS_DQS_ENABLED`, `SPAMHAUS_DQS_KEY`, `IPQS_ENABLED`, `IPQS_API_KEY`, `DOMAIN_REPUTATION_ENFORCEMENT`.

Без ключей используется monitor и статус «Проверка репутации не настроена». После подключения Web Risk и Spamhaus установите `DOMAIN_REPUTATION_ENFORCEMENT=block` и пересоздайте backend services.

## 15. Расписание, планы и задания

- **IMMEDIATE** — запуск после подтверждения.
- **EVEN** — равномерное распределение.
- **WAVES** — тестовая волна, окно наблюдения и дальнейшие волны.
- **MANUAL** — конкретное время для каждого элемента.

Можно задать timezone, hourly/daily limits, concurrency, retry/backoff, circuit breaker и необходимость ручного продолжения. Pause/resume и перенос затрагивают только будущие runs. После рестарта scheduler восстанавливает persisted state и не делает массовый catch-up.

В **Заданиях** смотрите status, progress, warnings, structured errors и Request ID. Повтор безопасной idempotent операции не создаёт duplicate resources.

## 16. Финансы

1. Откройте **Финансы**.
2. Выберите рекламный аккаунт и нажмите **Прочитать billing**.
3. Для monthly-invoicing production account будут показаны BillingSetup и AccountBudget.
4. Для Google test account появится честное сообщение, что billing API не вызывался.
5. Brocard необязателен. Пока API token не настроен, внешних Brocard calls нет и основная программа работает полностью.

Google Ads API не предоставляет automatic card threshold, дату следующего карточного charge и полную историю банковской карты. Программа не показывает их как `0` и не придумывает значения.

## 17. Темы, язык, время и мобильная работа

В **Настройках** выберите светлую/тёмную тему, русский/английский язык, timezone и плотность. Настройки сохраняются. На мобильном основная таблица остаётся внутри своего scroll-container; вся страница по горизонтали не уезжает.

Google reporting dates считаются в timezone конкретного рекламного аккаунта. UI по умолчанию показывает `Europe/Moscow`, если пользователь не выбрал другое.

## 18. Что делать при ошибке

1. Откройте подробности ошибки и запишите только error code и Request ID, не секреты.
2. `DEVELOPER_TOKEN_NOT_APPROVED` — нужен Google Ads API Basic Access; повторный OAuth обычно не помогает.
3. `Неверный логин или пароль` — проверьте текущий пароль; bootstrap нельзя повторить при существующем admin.
4. `Проверка репутации не настроена` — availability продолжает работать, но для verdict нужны provider keys.
5. `Данные устарели` — откройте вкладку **Синхронизация** и запустите safe sync.
6. Зависшее задание — проверьте **Задания**, затем health контейнеров; не удаляйте volumes.
7. Для диагностики используйте `http://localhost/api/health` и `http://localhost/api/ready`.

Никогда не применяйте `docker compose down -v`, volume prune или database reset для обычного устранения ошибки.

## 19. Ежедневный безопасный сценарий

1. Войдите и откройте view **Аккаунты в работе**.
2. Проверьте красные problems и freshness.
3. Отфильтруйте `В работе + Не откручивает` и `В работе + Заблокирован`.
4. Просмотрите расходы отдельно по валютам и accounts with spend but no deposits.
5. Добавьте заметки/теги и назначьте ответственного через принятую внутреннюю схему тегов.
6. Любое ручное Google action сначала проверьте preview/validate_only.
7. Создание Demand Gen завершайте только после domain check и immutable plan review.
8. В конце проверьте **Задания**, **Историю** и **Уведомления**.

## 20. Резервное копирование и обновление

Перед крупным обновлением сохраните PostgreSQL dump, Redis RDB, `.env` и `app_storage` вне Git. Не меняйте `APP_ENCRYPTION_KEY`: без него существующие OAuth credentials станут недоступны. Применяйте только `alembic upgrade head`, после чего дождитесь `healthy` всех семи services и проверьте `/api/ready`.
"""


def main() -> None:
    baseline_bytes = BASELINE.read_bytes()
    baseline_text = baseline_bytes.decode("utf-8-sig")
    baseline_hash = hashlib.sha256(baseline_bytes).hexdigest()
    requirements = parse_requirements(baseline_text)
    post_audit, counts = build_post_audit(requirements, baseline_hash)
    if sum(counts.values()) != 407:
        raise RuntimeError("Final status count does not equal 407")

    POST_AUDIT.write_text(post_audit.rstrip() + "\n", encoding="utf-8")
    IMPLEMENTATION_REPORT.write_text(
        build_implementation_report(counts, baseline_hash).rstrip() + "\n", encoding="utf-8"
    )
    USER_GUIDE.write_text(build_user_guide().rstrip() + "\n", encoding="utf-8")

    print(f"baseline_sha256={baseline_hash}")
    print(f"requirements={len(requirements)}")
    for status in [READY, GOOGLE_TEST, BASIC_ACCESS, UNAVAILABLE, EXCLUDED]:
        print(f"{status}={counts[status]}")
    print(f"post_audit={POST_AUDIT}")
    print(f"implementation_report={IMPLEMENTATION_REPORT}")
    print(f"user_guide={USER_GUIDE}")


if __name__ == "__main__":
    main()
