# ADR 0001: Server-first архитектура

Дата: 2026-07-19

## Решение

Проект создаётся как серверное web-приложение с Docker Compose, PostgreSQL, Redis/Celery, FastAPI, React и Caddy.

## Причина

Финальное ТЗ требует production server application, несколько MCC, очереди, аудит, backup и восстановление после перезапуска. Локальный одноразовый скрипт не подходит.

