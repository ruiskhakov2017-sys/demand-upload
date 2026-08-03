# Axyro Analytics — Google Ads API Design Document

## 1. Product purpose

Axyro Analytics is an internal Google Ads analytics and operations platform
designed to consolidate data from multiple manager and advertising accounts into
a single control center.

The platform synchronizes account hierarchy, campaign performance metrics,
conversion data, policy and verification statuses, operational issues, and
change history. Authorized internal users can analyze accounts across different
geographic markets, apply filters and saved views, compare performance, review
alerts, maintain internal notes, and export reports.

The primary purpose of the tool is centralized reporting, performance analysis,
account monitoring, and operational control.

The platform also includes secondary campaign management functions. Authorized
users can create validated Demand Gen campaigns, pause or enable selected
campaigns, and update budgets. All write operations are explicitly initiated by
a user, validated before execution, confirmed in the interface, recorded in an
audit log, and protected by production safety controls. Newly created campaigns
are created in a paused state by default.

The tool is not a public advertising platform, does not resell Google Ads API
access, and does not allow anonymous users to submit Google Ads operations. It
is intended only for authorized internal users and is not offered as a public
self-service advertising product.

`Demand Gen Uploader` remains the internal technical name of the repository and
the secondary **Validated campaign deployment** module. It is not the public
product name or the primary use case.

## 1.1 Why Basic Access is required

Basic Access is required to analyze and manage production Google Ads accounts
linked to our manager account. Test accounts do not serve ads and therefore
cannot provide the real performance metrics, conversion data, policy statuses,
verification states, account activity, and operational history required to
validate the analytics and monitoring functions of the platform.

The requested access will be used only for accounts managed by our internal
team and linked to our Google Ads manager account.

**Primary use:** reporting, analytics and monitoring.

**Secondary use:** explicitly confirmed campaign management operations.

## 2. Owner and users

The tool is owned and operated by the repository owner and is intended for a
small authenticated internal team. Supported roles are:

- `ADMIN`: manages protected connections, confirms changes, and reviews audit
  records.
- `OPERATOR`: prepares uploads and performs permitted operational workflows.
- `VIEWER`: has read-only access.

Authentication uses server-side sessions, CSRF protection, and role checks.

## 3. Architecture

The application runs as seven Docker Compose services:

- React/Vite frontend
- FastAPI API
- Celery worker
- Celery scheduler
- PostgreSQL
- Redis
- Caddy reverse proxy

PostgreSQL is the source of truth. Redis is used only for task transport and
scheduling. Google Ads protocol objects are isolated inside a versioned backend
adapter. Frontend code never receives a Developer Token, OAuth Client Secret,
access token, or refresh token.

## 4. OAuth and credential storage

The application uses the OAuth 2.0 web application flow with state, PKCE,
short-lived authorization records, an exact callback URI, and the
`https://www.googleapis.com/auth/adwords` scope.

Credentials are encrypted at rest with the application encryption key. A
Google Test connection can reference an existing protected credential profile
for the Developer Token and OAuth client identity without copying plaintext.
The Google Test user's refresh token is encrypted in a separate credential
record. Disconnecting the Google Test user does not modify the source
connection or its refresh token.

OAuth errors are retained with their Google error code and safe description.
Tokens and secrets are redacted from logs and API responses.

## 5. MCC discovery

Connection verification is read-only and uses:

1. `CustomerService.ListAccessibleCustomers`
2. recursive GAQL reads of `customer_client`
3. an exact GAQL read of each `customer`
4. verification of `customer.test_account`

For every discovered account, the application stores the Customer ID, direct
parent MCC, hierarchy root, hierarchy level, account type, Google status,
test-account flag, currency, time zone, successful synchronization time, and
Google Request IDs.

The isolated test hierarchy is:

- Test MCC: `3831073849`
- Test client account: `1833869760`
- Test client account: `8047280949`

Both child accounts must be returned before the connection can be marked
verified. A closed test account caused by the absence of billing is treated as
a normal test-account state, not as suspension or deletion.

## 6. Execution-mode separation

The modes are deliberately independent:

- `SIMULATION`: synthetic local data; no Google mutate request.
- `GOOGLE_TEST`: real Google Ads API reads, `validate_only`, and mutate requests
  restricted to recently verified test accounts in the isolated hierarchy.
- `PRODUCTION`: real reporting integration. In the currently deployed version,
  all mutate requests, including attempts through legacy `LIVE` values, are
  rejected locally while Basic Access is pending. After access is granted,
  production writes are intended to remain limited to individually authorized,
  previewed, validated, confirmed, audited campaign operations.

There is no global switch that can enable both test and production mutation.
The versioned Google Ads adapter also rejects every mutate request unless its
connection mode is exactly `GOOGLE_TEST`.

## 7. Validated campaign deployment

The secondary Demand Gen Uploader module creates an immutable plan and performs:

1. local schema and policy validation
2. fresh domain availability and reputation validation
3. fresh test-account and hierarchy verification
4. real Google Ads `validate_only`
5. explicit user confirmation
6. atomic-per-campaign Google Ads mutate
7. GAQL readback of every created resource

Each campaign is created `PAUSED`. The operation set includes a non-shared
campaign budget, Demand Gen campaign, ad group, audience, audience criterion,
location and language criteria, required assets, and an ad. Stable names and a
stored acceptance record make the test fixture idempotent.

The implementation follows the official Demand Gen campaign creation workflow:
https://developers.google.com/google-ads/api/docs/demand-gen/create-campaign

## 8. Campaign control

The Control Center supports preview, `PAUSE`, `ENABLE`, and absolute budget
changes for verified Google Test campaigns. Each real action follows this
sequence:

1. read current account and campaign state
2. create a preview
3. receive explicit confirmation from the same user
4. reject stale state
5. perform real `validate_only`
6. perform real mutate
7. retain Google Request IDs
8. read the object again
9. compare requested and actual values
10. report success only after a matching readback

Manager-account targets are always rejected. Production targets are currently
rejected before a Google client is opened; enabling controlled production
actions requires approved Basic Access and a separate deliberate safety change.

## 9. Reporting and metrics

The reporting layer stores source mode with every monitoring and daily metric
record. Simulation metrics are allowed only for `SIMULATION`. Google Test
accounts use real Google reads and normally have no delivery metrics because
test accounts do not serve ads. The interface therefore displays a specific
no-data reason instead of zeros or generated performance.

## 10. Safety controls

Every real mutate requires all of the following:

- connection mode and target are consistent
- `login_customer_id` matches the verified hierarchy root
- target Customer ID belongs to that connection and hierarchy
- a fresh Google read confirms the target is not a manager
- test mode additionally requires a fresh `customer.test_account = true` check
- a user explicitly confirmed the action
- preview state is not stale

The current production guard remains closed while Basic Access is pending. A
future production action must retain all preview, validation, confirmation,
quota, audit, Request ID, and readback controls and may never be enabled merely
by changing a frontend value.

Campaign-level domain blocks affect only campaigns using the unsafe domain.
Automatic rules remain `DRY_RUN` by default and do not call Google mutate.

## 11. Audit and diagnostics

The audit log records actor, action, object, old value, requested value, actual
readback, timestamps, execution mode, resource names, and Request IDs. Google
error codes and Request IDs are preserved for OAuth, authorization, validation,
quota, partial-failure, network, and mutate failures. Secret values and
sensitive URL query parameters are never written to logs.

## 12. Quotas and resilience

The application estimates operation volume before bulk synchronization,
reserves capacity for manual actions, limits parallel execution, and uses
bounded retries only for transient failures. Schedules use database locks,
idempotency keys, immutable fingerprints, and circuit-breaker behavior. A
successful Google response is not inferred from a queued task.

## 13. Test strategy

Normal unit tests use mocks and never call Google. Real integration tests are
opt-in with `RUN_GOOGLE_TEST_INTEGRATION=1` and require a verified
`google-test` connection. They are not part of routine test runs.

The real acceptance suite is designed to:

- create and read back one paused Demand Gen fixture in `1833869760`
- create a separate fixture in `8047280949`
- validate and perform `ENABLE`, `PAUSE`, and budget changes
- retain resource names and Request IDs
- reuse stored fixtures on subsequent runs

## 14. Real test evidence

The test MCC owner completed OAuth and the isolated `google-test` connection
was verified on 2026-07-29. Real hierarchy discovery returned MCC
`3831073849` and both required child accounts, `1833869760` and `8047280949`.
Both children were read from Google as client accounts with
`customer.test_account = true`, `manager = false`, and `CLOSED` status. The
closed status is expected because Google test accounts do not serve ads.

The real Demand Gen acceptance run completed at
`2026-07-29T13:47:30.573516Z` in customer `1833869760`. It created the paused
campaign `customers/1833869760/campaigns/24078084651` with:

- budget `customers/1833869760/campaignBudgets/15761367103`
- audience `customers/1833869760/audiences/355197346`
- ad group `customers/1833869760/adGroups/198049049479`
- location, language, and audience criteria
- image, YouTube video, and call-to-action assets
- video responsive ad
  `customers/1833869760/adGroupAds/198049049479~818830300709`

GAQL readback confirmed the campaign was `PAUSED` and that the budget,
audience, ad group, criteria, assets, and ad all existed.

The separate Control Center fixture completed at
`2026-07-29T13:48:44.496689Z` in customer `8047280949`. It created campaign
`customers/8047280949/campaigns/24078086559`, budget
`customers/8047280949/campaignBudgets/15756376533`, audience
`customers/8047280949/audiences/355196629`, ad group
`customers/8047280949/adGroups/199802059418`, required criteria and assets,
and ad `customers/8047280949/adGroupAds/199802059418~818759140312`.

The normal Control Center API then exercised the full user workflow:

- `ENABLE`: `PAUSED` to `ENABLED`, readback verified
- `PAUSE`: `ENABLED` to `PAUSED`, readback verified
- `SET_BUDGET`: `11,000,000` to `12,000,000` micros, readback verified

Each action included a fresh read, preview, explicit confirmation,
`validate_only`, mutate, Request ID persistence, GAQL readback, comparison,
and audit record. The final campaign state is `PAUSED` with a
`12,000,000`-micros daily budget.

Google Test delivery metrics are intentionally stored and displayed as
missing, with the reason "No data: test accounts do not serve ads." No
synthetic metrics are mixed into Google Test records.

Desktop browser acceptance passed at `http://localhost/control-center` with
two fixture rows, the Google Test mode selected, no browser-console errors,
and no failed application requests. Evidence:
[Google Test Control Center screenshot](screenshots/google-test-control-center-desktop.png).

No production mutate was performed. The pre-existing `vcc2` connection remains
in `PRODUCTION` mode, and every production mutation path is rejected locally
before a Google client is opened.

## 15. Request ID ledger

The following IDs are the persisted Google Request IDs for the real test.
They contain no credentials or tokens.

- Hierarchy discovery:
  `6evDrRBOxaaxfZ1qC0ZOjA`, `ofQk_ZAAgOII-g9iCqDhxw`,
  `hPvgC31NOz3-xV_4poQS9Q`, `o0M0crOQkLVhzd8PGHJ2KA`,
  `qBDiWZWbkAfn1k5JqGgxMg`.
- Demand Gen acceptance in `1833869760`:
  `nx0q3h8bDNb_2MQHSJKJ7w`, `ThcwVxVVRtsYMQ2yXhnQ2A`,
  `CFpWLLHZaHtX465gOFxQBA`, `ETj3sa0uv3lkC1fOI50O_A`,
  `mYqhPA9n3We_Tgt8hvxW7A`, `qJNkZ8Dezl_D75Ig0WAccA`,
  `6D17gZFDzZKAeOW8dM9kFA`, `EcUKgGNgLX81R6h6iaxPwA`,
  `8VNmdNlxrcIXPHspASrBmQ`, `0I9w4grL0iex_h1LHwQfAA`,
  `VGSyr78yndly2hwQ0WsVHA`, `AGuaoWXhuiwO_sg9RSnqXg`,
  `JaMgwXFCcGN7ztSJ6yqu-g`, `GQngsOF6ZuAs5Bom33JkQA`,
  `ogBlCCED1C7zPhqbiGz8Xw`, `Lkbx1BIh3NZySHJ2ZqIhKw`.
- Control fixture creation and direct acceptance in `8047280949`:
  `9dZ9peEFMcjH9zsIfzxKuA`, `TVFmkyQ5pi_Sx1_cncMzEw`,
  `RdO-GDgeqa6DSwb7s3n5LQ`, `mUh-hQw61qwlPONy3WdpfA`,
  `uS8qhsBC9XDG6XXI61U7ow`, `wQp44tO5imkiKqNNiNCD7w`,
  `dgR0YdjJacQZtDTF8xpCnA`, `EgTYJYTl1IjE0cP4Kn00Ug`,
  `T7UVMwWOnOtp31ss6wy0Aw`, `v-B02fS6Il67KER7ADSVSw`,
  `lS-vs3HpxSbQ48VGXYcI9A`, `f0Psw3Hq_3jmsWDu8c5qJA`,
  `LDpwyCR9cg-GtxdSd_2-VQ`, `Paq_XG_F78IEMiR_BNgaXA`,
  `vOuZVv-MUejpzKHp9K5NNQ`, `Nq4wlObREspwPddMhOSC7Q`,
  `dpyI2N4MTB7cokGB4vPDTw`, `NWSaM_6yGznYuFeqNwF5Lw`,
  `UR53pCe5IR2KWhBURr5AWw`, `dOupeIl4HPqH6WpvKk1iUA`,
  `DQAUSQW7ZNiStDpd-gBJ9w`, `Vwox9qfUOaegW7Tk_NAGfg`,
  `3kOrYCbps6HTb-P278Nz0g`, `5UbIrUEzZ9gFdd4IrvHj5Q`,
  `EAeSddz1TyrK9APdS8ht1w`, `1ZFtNLWppGO3TP-EFLMSuQ`,
  `XGn6kK3q5jMf1MHeiw0PPQ`, `QbvfLGnJFHYVwlpWp25VnQ`,
  `_PqFa6JYUotWVBO3cegwRQ`, `4IdSMRiKCP6xFks2YabzqQ`,
  `yRgvuuzorf8g8XKk6ej93w`.
- Control Center sync in `1833869760`:
  `Zq_-K1FI-YWOXyBpY7Fmsg`, `zoC-U6Q_WjEqoplCXffn8g`,
  `awtteTUBHiwP-qB9-F17iw`, `nH5NSf4izl27G_er2HHXkw`.
- Control Center sync in `8047280949`:
  `GCNClDcS5KMdPdfwPRQU0A`, `-meVeuYPwXQfIX3iQT9Htg`,
  `JU9-POLk5c85egnRmPElxg`, `XR-a5O9E9b5nq1vzB_F41Q`.
- Control Center API `ENABLE`: preview/read
  `KwvJJC__zFnv2bR7BZKqXw`, `0GmcRsSASyW8II-iymxP_A`;
  confirmation guard/read `Jb2ldwSoB1gvZ6IYJOue2A`,
  `Kts9wGk_jkTqMKaLlQWYsA`; `validate_only`
  `MsaamvjOy7Pr4-pTkQRaWw`; mutate `4JZxggO0y7LuWPKlwf9agQ`;
  readback `Grp-s5F5TGA0z-ngtGQOuA`.
- Control Center API `PAUSE`: preview/read `Oj9wUpGjvv2xYkNLHYHyPg`,
  `wKcSvuiyhkIkzAJfHXCLAg`; confirmation guard/read
  `sKZpAevgr2QfQX_O8GVhgQ`, `EXOdH_bmM8Yue85Zmn0FJA`;
  `validate_only` `lOCWmwRofP7KDpux9btLnA`; mutate
  `n1-e4b2iyTABPpcOZHDK2g`; readback `luntWOK5jwUm8eASgK4v0g`.
- Control Center API `SET_BUDGET`: preview/read
  `xuusPIwPXCiVEdDJXxLzbg`, `29z6vRFVL1SXeELlvPxK0g`;
  confirmation guard/read `kZE9F_P87jVI_rWk7CgyQA`,
  `ODH0SGsnQPQ0NveMBeTd8A`; `validate_only`
  `wU09_2FRgjrS8WEAW5NrpA`; mutate `Th3JHBpIEhBjGHLoOLoDAg`;
  readback `izJFGVxxuqMABl-Zam23ng`.

Failed pre-mutate diagnostics were also preserved and never masked:

- unsupported page size: `REQUEST_ERROR.PAGE_SIZE_NOT_SUPPORTED`,
  Request ID `BSTbbDN5hqYGbb59gPp3Kw`
- conversion tracking and invalid age-dimension validation:
  `CAMPAIGN_ERROR.CONVERSION_TRACKING_NOT_ENABLED` and
  `AUDIENCE_ERROR.DIMENSION_INVALID`, Request IDs
  `TIxKzJcWoEe00BibiTgDEA`, `sxUt5CIRqhmQ8f2IfWCtwg`,
  `Qcu_Ha26Mm8SG1VVazJH5A`
- missing bidding-strategy message:
  `FIELD_ERROR.REQUIRED`, Request ID `Hg7utlVDiYsFL4isfS9wHw`
- missing video-responsive logo:
  `COLLECTION_SIZE_ERROR.TOO_FEW`, Request ID
  `cHtfv9kLkRhjitHt1tucJA`
