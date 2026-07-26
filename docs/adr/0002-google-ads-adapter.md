# ADR 0002: Google Ads API изолирован adapter-слоем

Дата: 2026-07-19

## Решение

Весь доступ к Google Ads API находится в `backend/app/google_ads`. UI, importer, planner и deployments не создают protobuf-объекты напрямую.

## Причина

Google Ads API меняется по версиям. На 2026-07-19 актуальна ветка `v24.2`, но ожидается `v25`. Обновление версии должно затрагивать adapter, а не бизнес-логику.

## Источники

- https://developers.google.com/google-ads/api/docs/release-notes
- https://developers.google.com/google-ads/api/docs/demand-gen/create-campaign

