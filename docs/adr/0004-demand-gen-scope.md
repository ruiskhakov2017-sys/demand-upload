# ADR 0004: Scope Demand Gen 1.0

Дата: 2026-07-19

## Решение

Версия 1.0 ограничивается Demand Gen campaign, `DemandGenMultiAssetAdInfo` и `DemandGenVideoResponsiveAdInfo`. Carousel и Product Ads не входят в первую область.

## Причина

ТЗ требует безопасный массовый flow. Расширение ad types без отдельного плана повышает риск ошибок в API payload, ассетах и модерации.

## Источники

- https://developers.google.com/google-ads/api/docs/demand-gen/create-campaign
- https://developers.google.com/google-ads/api/reference/rpc/v24/DemandGenMultiAssetAdInfo
- https://developers.google.com/google-ads/api/reference/rpc/v24/DemandGenVideoResponsiveAdInfo

