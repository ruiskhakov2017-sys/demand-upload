# Google Ads API Basic Access — prepared answers

Prepared on August 2, 2026. These answers match the current 11-question form at
`https://support.google.com/adspolicy/contact/new_token_application?hl=en`.

The application is **not submitted**. The three confirmation checkboxes remain
unchecked for the owner's final review.

## 1. API contact email is accurate and up-to-date

**Form action:** Leave unchecked until the owner reviews the updated API Center
contact `support@axyro.tech`.

**Русский:** Не отмечать до финальной проверки владельцем контактного адреса
`support@axyro.tech` в API Center.

## 2. Google Cloud project number

**English / form value:** `1044664056304`

**Русский:** Номер проекта Google Cloud — `1044664056304`.

## 3. Developer-token MCC ID

**English / form value:** `558-933-5362`

**Русский:** MCC, которому принадлежит Developer Token, — `558-933-5362`.

## 4. Contact email

**English / form value:** `support@axyro.tech`

**Русский:** Контактный адрес для рассмотрения заявки — `support@axyro.tech`.

## 5. Ongoing relationship with a Google representative

**English / form value:** `No`

**English explanation:** No ongoing relationship with a Google representative
has been identified for this application.

**Русский:** Нет. Для этой заявки не установлены действующие отношения с
представителем Google.

## 6. Primary website

**English / form value:** `https://axyro.tech`

**Русский:** Основной сайт — `https://axyro.tech`.

## 7. Business model, API tool, and intended audience

**English / form answer:**

Axyro Analytics is an internally developed Google Ads analytics and operations
platform used by an individual advertiser and a small authorized internal team
to manage advertising accounts linked to our own manager account. Our business
model is internal advertising operations; we do not resell Google Ads API
access, provide a public self-service advertising product, or give unrelated
clients access to the tool.

The platform's primary purpose is centralized reporting, performance analysis,
and monitoring across multiple MCC and advertising accounts. It synchronizes
account hierarchy, cost, impressions, clicks, CTR, CPC, mapped registration and
deposit conversions, CPA, campaign status, policy and advertiser verification
status, operational issues, and change history. Internal users can compare
markets, use filters and saved views, maintain notes and tags, review alerts,
and export reports.

The platform also has secondary campaign-management functions. Authorized users
can create validated Demand Gen campaigns, pause or enable selected campaigns,
and update budgets. Every write action is initiated by a user, previewed,
validated locally and with Google Ads `validate_only`, explicitly confirmed,
recorded in AuditLog with Google Request IDs, and verified by readback. New
campaigns are created PAUSED and are never enabled automatically. Production
write operations are currently blocked while Basic Access is pending.

Basic Access is required because test accounts do not serve ads and cannot
provide the real delivery metrics, conversion data, policy statuses,
verification states, account activity, and operational history needed to
validate the platform's primary analytics and monitoring functions. Access will
be used only for accounts managed by our internal team and linked to our MCC.

**Русский перевод:**

Axyro Analytics — разработанная внутри компании платформа аналитики и
операционного управления Google Ads. Индивидуальный рекламодатель и небольшая
авторизованная внутренняя команда используют её для работы с рекламными
аккаунтами, связанными с собственным MCC. Наша бизнес-модель — внутренние
рекламные операции; мы не перепродаём доступ к Google Ads API, не предоставляем
публичный рекламный сервис самообслуживания и не даём несвязанным клиентам
доступ к инструменту.

Основное назначение платформы — централизованная отчётность, анализ
эффективности и мониторинг нескольких MCC и рекламных аккаунтов. Она
синхронизирует иерархию аккаунтов, расходы, показы, клики, CTR, CPC,
сопоставленные регистрации и депозиты, CPA, статусы кампаний, policy и
advertiser verification, операционные проблемы и историю изменений. Внутренние
пользователи могут сравнивать рынки, применять фильтры и сохранённые
представления, вести заметки и теги, просматривать уведомления и выгружать
отчёты.

Платформа также содержит вторичные функции управления кампаниями.
Авторизованные пользователи могут создавать проверенные Demand Gen кампании,
приостанавливать или включать выбранные кампании и изменять бюджеты. Каждое
изменяющее действие запускается пользователем, показывается в preview,
проверяется локально и через Google Ads `validate_only`, явно подтверждается,
записывается в AuditLog с Google Request ID и проверяется повторным чтением.
Новые кампании создаются в PAUSED и никогда не включаются автоматически.
Изменяющие операции в production сейчас заблокированы, пока ожидается Basic
Access.

Basic Access необходим, потому что тестовые аккаунты не показывают рекламу и не
могут предоставить реальные метрики, данные конверсий, policy statuses,
verification states, активность аккаунта и операционную историю, необходимые
для проверки основной аналитики и мониторинга. Доступ будет использоваться
только для аккаунтов, которыми управляет наша внутренняя команда и которые
связаны с нашим MCC.

## 8. Tool documentation

**English / form attachment:**
`google-ads-api-basic-access-application.pdf`

**Public URL:**
`https://axyro.tech/docs/google-ads-api-basic-access-application.pdf`

**Русский:** Приложить англоязычный PDF-документ с архитектурой, OAuth,
операциями чтения и записи, предохранителями, аудитом и скриншотами.

## 9. Who will have access?

**English / form value:**
`Internal users - employees only (outsourcing, contractor included)`

**Русский:** Только внутренние пользователи, включая при необходимости
подрядчиков, которым владелец явно предоставил доступ.

## 10. Token used with a tool developed by someone else?

**English / form value:** `No`

**English explanation:** Axyro Analytics was developed internally for this
owner. Open-source frameworks and official Google client libraries are used as
implementation dependencies, but no third-party Google Ads management product
uses the token.

**Русский:** Нет. Axyro Analytics разработан внутри для этого владельца.
Open-source фреймворки и официальный Google client library используются как
зависимости, но Developer Token не передаётся стороннему продукту управления
Google Ads.

## 11. App Conversion Tracking and Remarketing API

**English / form value:** `No`

**English explanation:** The tool reads Google Ads conversion metrics through
Google Ads API reporting and can map selected conversion actions for internal
analytics. It does not use the separate App Conversion Tracking and Remarketing
API referenced by this question.

**Русский:** Нет. Инструмент читает метрики конверсий через отчётность Google Ads
API и может сопоставлять выбранные conversion actions для внутренней аналитики,
но не использует отдельный App Conversion Tracking and Remarketing API,
указанный в вопросе.

## Confirmation checkboxes

The following remain unchecked:

- API contact email is accurate and up-to-date.
- I acknowledge that all the information above is accurate.
- I accept the Terms and Conditions and Privacy Policy notice.

**Русский:** Все три подтверждающих флажка остаются пустыми до отдельного
указания владельца. Кнопка Submit не нажимается.

## Supplemental facts used in documentation

- Owner: Individual.
- Primary business country: Bulgaria.
- Tool developed by: internal development for the owner.
- Expected operation volume: typical use below 15,000 operations/day; internal
  planning limit 15,000/day with a 20% reserve for manual operations.
- Security: HTTPS, server-side sessions, CSRF, roles, encrypted credentials,
  secret redaction, exact OAuth callback, state, PKCE, AuditLog, Request IDs,
  idempotency, bounded retries, circuit breaker, and readback.
- Data retention: active operational need; OAuth disconnect clears the refresh
  token; production backups rotate after 14 days; deletion requests use
  support@axyro.tech.

