# ADR 0005: Video upload через официальный Google Ads API

Дата: 2026-07-19

## Решение

Видео загружаются только через поддерживаемый Google Ads API flow. Для Google-managed channel `channel_id` не указывается. Advertiser-owned channel допускается только с пользовательским OAuth, когда это поддерживается API.

## Причина

Документация указывает, что video upload через Google Ads API поддержан в REST и Python client library. Service account не подходит для advertiser-owned YouTube channel.

## Источник

- https://developers.google.com/google-ads/api/docs/assets/upload-videos

