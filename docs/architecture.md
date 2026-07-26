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
```

## Главный принцип

Google Ads API изолирован в `backend/app/google_ads`. Остальные модули работают с интерфейсом adapter и не знают о конкретных protobuf-полях выбранной версии API.

## Поток операций

1. Администратор создаёт Google connection.
2. API сохраняет секреты в `google_credentials` в зашифрованном виде.
3. Adapter выполняет read-only проверку MCC.
4. Аккаунты синхронизируются в `customer_accounts`.
5. Следующие этапы будут добавлять import -> validation -> immutable plan -> validate_only -> confirm-create.

