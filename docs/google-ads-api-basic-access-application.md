# Axyro Analytics

## Google Ads API Basic Access Application Design Document

**Product:** Axyro Analytics  
**Subtitle:** Private Google Ads Analytics & Control Center

**Operator:** Iskhakov Ruslan

**Legal status:** Individual; no registered company

**Product status:** Independent software project; not a separate legal entity
**Website:** https://axyro.tech  
**Privacy Policy:** https://axyro.tech/privacy  
**Terms of Use:** https://axyro.tech/terms  
**Contact:** support@axyro.tech  
**Developer-token MCC:** 558-933-5362  
**Google Cloud Project Number:** 1044664056304  
**Document date:** August 18, 2026

## 1. Executive summary

Axyro Analytics is an independent Google Ads analytics and operations software
project operated by Iskhakov Ruslan, an individual. Axyro Analytics is the name
of the project, not a registered company or separate legal entity. The private
tool consolidates connected manager and advertising accounts into a single
control center.

The platform synchronizes account hierarchy, campaign performance metrics,
conversion data, policy and verification statuses, operational issues, and
change history. The sole user can analyze accounts across different geographic
markets, apply filters and saved views, compare performance, review alerts,
maintain notes, and export reports.

The primary purpose of the tool is centralized reporting, performance analysis,
account monitoring, and operational control.

The platform also includes secondary campaign management functions. Authorized
users can create validated Demand Gen campaigns, pause or enable selected
campaigns, and update budgets. All write operations are explicitly initiated by
a user, validated before execution, confirmed in the interface, recorded in an
audit log, and protected by production safety controls. Newly created campaigns
are created in a paused state by default.

Only Iskhakov Ruslan currently has access to the platform. There are no
employees, contractors, external clients, or public users. The platform is not
offered as a public self-service advertising product.

## 2. Why Basic Access is required

Basic Access is required to analyze and manage production Google Ads accounts
that Iskhakov Ruslan is authorized to access through his manager account. Test
accounts do not serve ads and therefore
cannot provide the real performance metrics, conversion data, policy statuses,
verification states, account activity, and operational history required to
validate the analytics and monitoring functions of the platform.

The requested access will be used only for accounts that Iskhakov Ruslan is
authorized to manage and that are linked to his Google Ads manager account.

**Primary use:** reporting, analytics and monitoring.  
**Secondary use:** explicitly confirmed campaign management operations.

## 3. Ownership, business model, and audience

The applicant and operator is **Iskhakov Ruslan**, an individual developer and
advertiser. He does not represent a registered company. Axyro Analytics is a
project name used for his privately operated software; it is not a separate
legal entity, advertising agency, public SaaS product, or API resale service.
The project does not resell Google Ads API access, manage unrelated public
customers, provide a white-label API, or expose Google Ads operations to other
people.

The current deployment is used only by Iskhakov Ruslan through the owner ADMIN
account. No employee, contractor, external client, or other user has access.
The software implements the following role types as technical authorization
boundaries, but they do not imply that a team currently uses the application:

- **ADMIN** — manages connections and protected settings, confirms permitted
  operations, and reviews audit evidence.
- **OPERATOR** — analyzes data, prepares plans, and runs permitted workflows.
- **VIEWER** — read-only access to reporting and monitoring views.

## 4. Architecture

The production deployment consists of seven isolated Docker services:

1. Caddy reverse proxy and HTTPS termination.
2. React/Vite frontend.
3. FastAPI backend.
4. PostgreSQL source-of-truth database.
5. Redis task broker.
6. Celery worker.
7. Celery scheduler.

The frontend calls only the protected backend API. Google Ads protocol objects
and credentials stay inside a versioned backend adapter. PostgreSQL stores
configuration, normalized reporting data, plans, action state, and audit
records. Redis transports bounded background work and is not the source of
truth.

## 5. OAuth 2.0 and MCC hierarchy

The application uses the OAuth 2.0 web application flow with:

- the `https://www.googleapis.com/auth/adwords` scope;
- an exact HTTPS callback URI;
- state validation;
- PKCE;
- short-lived authorization records;
- encrypted refresh-token storage;
- no token exposure to frontend code.

The public callback is:

`https://axyro.tech/api/google-connections/oauth/callback`

MCC discovery uses `CustomerService.ListAccessibleCustomers` and recursive GAQL
queries against `customer_client` and `customer`. The application records the
hierarchy root, direct parent, level, account type, Google status, currency,
time zone, synchronization time, and Google Request IDs.

The developer token belongs to production MCC **558-933-5362**. A separate,
isolated Google Test hierarchy was used for real API validation:

- Test MCC: 383-107-3849
- Test client: 183-386-9760
- Test client: 804-728-0949

## 6. Google Ads API read operations

The primary API use is read-only reporting, analytics, and monitoring:

- accessible customers and recursive MCC hierarchy;
- customer names, IDs, currency, time zone, test and manager flags, and status;
- campaign, ad group, ad, asset, budget, and targeting configuration;
- cost, impressions, clicks, CTR, average CPC, and conversion metrics;
- explicitly mapped registration and deposit conversions and calculated CPA;
- policy summaries and policy topic entries;
- advertiser verification state and deadlines when available;
- change events and operational history;
- supported BillingSetup and AccountBudget information for monthly invoicing;
- post-operation GAQL readback and Google Request IDs.

Missing conversion mappings are displayed as unavailable data, not as zero.
Test-account delivery metrics are also displayed as unavailable because test
accounts do not serve ads.

## 7. Secondary write operations

The tool truthfully includes these secondary write capabilities:

- create validated Demand Gen campaigns and their required budgets, ad groups,
  targeting, assets, and ads;
- pause selected campaigns;
- enable selected campaigns;
- update selected campaign budgets.

Every write operation must be started by the authenticated owner. The current
production build rejects production mutations while Basic Access is pending.
No production mutation has been performed.

## 8. Validated Demand Gen deployment workflow

The secondary **Validated campaign deployment** module uses this sequence:

1. Select an authorized connection, MCC, and child accounts.
2. Build an immutable preliminary campaign plan.
3. Validate schema, budgets, targeting, assets, URLs, and domain availability.
4. Perform configured domain reputation checks.
5. Refresh account and hierarchy state.
6. Call Google Ads API with `validate_only=true`.
7. Present the complete plan and financial preview to the user.
8. Require explicit confirmation from the same authenticated user.
9. Create each campaign atomically in `PAUSED` status.
10. Read every created resource back through GAQL.
11. Compare requested and actual state.
12. Store the result, resource names, errors, and Google Request IDs in AuditLog.

New campaigns are never enabled automatically as part of creation.

## 9. Manual campaign-control workflow

PAUSE, ENABLE, and budget changes follow a separate controlled workflow:

1. Read fresh account and campaign state.
2. Create a preview with estimated API operations.
3. Require explicit confirmation by the initiating user.
4. Reject stale previews or changed target state.
5. Run `validate_only`.
6. Perform the requested mutation.
7. Read the campaign or budget again.
8. Report success only when readback matches the requested value.
9. Record actor, target, previous value, requested value, actual value, result,
   timestamp, and Request IDs.

## 10. Production safety controls

The application currently enforces a hard production-mutation block while the
developer token has Test Account Access. After Basic Access approval, any
deliberate production enablement must retain all of these controls:

- server-side authorization and ADMIN/OPERATOR role checks;
- connection and target hierarchy consistency;
- exact `login_customer_id` without separators;
- fresh confirmation that a target is a client account, not an MCC;
- immutable preview fingerprint and stale-state rejection;
- local validation and Google `validate_only`;
- explicit user confirmation;
- idempotency keys and duplicate protection;
- bounded retries only for transient errors;
- per-account execution and campaign-level failure isolation;
- daily planning limit, manual-operation reserve, and circuit breaker;
- AuditLog and Google Request ID persistence;
- post-mutation GAQL readback.

Automatic rules are DRY RUN by default. Production writes cannot be enabled by
a frontend value and are not the application's default behavior.

## 11. Auditability and diagnostics

AuditLog records the actor, action, object, old value, requested value, actual
readback, timestamps, execution mode, affected resource names, and Google
Request IDs. Google error code, failure category, and Request ID are retained
for OAuth, authorization, validation, quota, network, and mutation failures.
Errors are shown to the internal user rather than masked as success.

Secrets, tokens, passwords, private keys, and sensitive URL query parameters are
excluded from API responses, exports, screenshots, and logs.

## 12. Credential and application security

- HTTPS and HSTS protect the public production service.
- Server-side sessions use secure cookies and CSRF protection.
- Trusted hosts, CORS restrictions, role checks, and audit middleware protect
  the backend.
- OAuth refresh tokens, OAuth client credentials, and the Developer Token are
  encrypted at rest with a server-side encryption key.
- The frontend never receives the Developer Token, OAuth Client Secret, access
  token, refresh token, or encryption key.
- Credentials are redacted from logs and error messages.
- PostgreSQL volumes, uploads, environment files, and backups are excluded from
  the source repository.

## 13. Data retention and deletion

Connected account data and operational records are retained only while needed
for internal analytics, security, and audit purposes. Disconnecting OAuth clears
the stored refresh token for that connection immediately. The owner can remove
connections and related operational data, subject to security and legal record
requirements.

Production backups use a 14-day rotation. Data removed from the active system
may remain in encrypted backups until that rotation expires. Access and deletion
requests are handled through support@axyro.tech.

## 14. Quota planning and reliability

The application uses an internal planning limit of **15,000 Google Ads API
operations per day**, with a 20% reserve for manual actions. Typical initial use
is expected to remain below this limit. The system estimates operations before
multi-account synchronization, throttles background work near the reserve,
limits parallelism, and retries only transient failures.

PostgreSQL is the source of truth for schedules and action state. Workers use
database locks, immutable fingerprints, and idempotency keys. A queued job is
never reported as a successful Google operation.

## 15. Verification evidence

The OAuth callback at `axyro.tech` completed successfully for the isolated
Google Test connection. Real hierarchy discovery returned the test MCC and both
test clients. Real `validate_only`, Demand Gen creation, PAUSE, ENABLE, budget
update, Request ID capture, and GAQL readback were exercised only in verified
Google test accounts. New test campaigns were confirmed as `PAUSED`.

The production connection remains protected. API Center shows Test Account
Access and offers **Apply for Basic Access**. Production mutation count remains
zero.

## 16. Public information

- Product: https://axyro.tech/
- Privacy Policy: https://axyro.tech/privacy
- Terms of Use: https://axyro.tech/terms
- Documentation PDF: https://axyro.tech/docs/google-ads-api-basic-access-application.pdf
- Contact: support@axyro.tech

Axyro Analytics is an independent software project operated by Iskhakov Ruslan,
an individual. It is not a registered company or separate legal entity and is
not affiliated with, endorsed by, or sponsored by Google.
