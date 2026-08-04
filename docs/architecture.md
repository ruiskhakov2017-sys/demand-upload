# Архитектура

```text
Browser
  -> Caddy
    -> React frontend
    -> FastAPI API
      -> PostgreSQL
      -> Redis / Celery
      -> FilesystemStorage
      -> Google Ads adapter
      -> bounded AI orchestrator
        -> OpenAI Responses API
        -> typed Axyro tools
```

## Главный принцип

Google Ads API изолирован в `backend/app/google_ads`. Остальные модули работают с интерфейсом adapter и не знают о конкретных protobuf-полях выбранной версии API.

AI-модель не имеет прямого доступа к SQL, GAQL, HTTP, Docker, SSH, браузеру,
файлам или секретам. Backend разрешает каждый typed tool повторно по роли,
scope, режиму, среде и feature gates. Модель не располагает инструментом
подтверждения или выполнения операции.

## Поток операций

1. Администратор создаёт Google connection.
2. API сохраняет секреты в `google_credentials` в зашифрованном виде.
3. Adapter выполняет read-only проверку MCC.
4. Аккаунты синхронизируются в `customer_accounts`.
5. Control Center и AI читают нормализованные snapshots с provenance,
   freshness, completeness, timezone и исходной валютой.
6. Изменение создаётся как редактируемый draft или preview.
7. Только отдельная кнопка пользователя передаёт подтверждённый request в
   существующий action/deployment pipeline: fresh read -> capability check ->
   validate_only -> mutate -> readback -> audit.
8. Demand Gen использует import -> validation -> immutable plan ->
   validate_only -> confirm-create; новые кампании создаются только `PAUSED`.

## AI-контур

- `backend/app/ai/gateway.py` вызывает Responses API с `store=false`.
- `orchestrator.py` ограничивает turns, tools, rows, dates, tokens, timeout,
  concurrency, бюджеты и повторные вызовы.
- `policy.py` строит неизменяемый `ToolContext` и применяет серверную матрицу
  прав.
- `tools.py` содержит 18 read, 3 queued refresh, 9 draft и 5 preview tools.
- PostgreSQL хранит диалоги, очищенные ответы, tool timeline, drafts, reports,
  model/prompt versions и usage; raw audio и chain-of-thought не хранятся.
- Celery выполняет refresh и retention cleanup. Redis не является источником
  истины для пользовательских данных.
- `SIMULATION`, `GOOGLE_TEST` и `PRODUCTION` независимы от режимов
  `READ_ONLY`, `DRAFT_ONLY` и `CONFIRM_REQUIRED`.
