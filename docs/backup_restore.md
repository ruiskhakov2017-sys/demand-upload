# Backup и восстановление

В 1.0 backup должен сохранять:

- PostgreSQL dump;
- asset storage;
- report exports;
- idempotency keys;
- Google resource mappings;
- audit history.

Восстановление считается рабочим только после тестового restore на отдельном окружении.

