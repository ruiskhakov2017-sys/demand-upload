# ADR 0003: Auth, sessions и секреты

Дата: 2026-07-19

## Решение

Панель имеет собственных пользователей, роли, HTTP-only session cookie и CSRF. Google developer token, OAuth refresh token и service account JSON хранятся в `google_credentials` в зашифрованном виде.

## Причина

Даже один пользователь работает через серверную панель, где есть опасные операции создания и включения кампаний. Секреты не должны попадать в Git, логи и frontend bundle.

