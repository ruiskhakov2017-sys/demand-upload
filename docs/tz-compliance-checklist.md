# Demand Gen Uploader: compliance checklist

This checklist records the product audit against the supplied final technical brief. It is kept in
the repository so implementation and verification can be tracked against observable behavior.

## Audit baseline (2026-07-21)

- [x] Docker services, authentication, encrypted credentials, MCC account sync, jobs and audit log exist.
- [x] Initial administrator exists; public setup is closed once a user exists.
- [x] Dashboard actions are wired to backend state and navigation.
- [x] Browser OAuth is the default connection workflow and completes server-side token exchange.
- [x] New Upload opens a persisted multi-step workflow.
- [x] CSV/XLSX/manual sources produce normalized campaign rows.
- [x] Media is validated, hashed, deduplicated, persisted and available through authenticated preview.
- [x] Existing YouTube IDs and server-side YouTube uploads are supported.
- [x] A canonical immutable plan is built and locally validated.
- [x] Google Ads `validate_only` is a separate required step.
- [x] Confirmation creates Demand Gen campaigns in `PAUSED` state only.
- [x] Retries are idempotent and results preserve request IDs/resource names.
- [x] Templates, Media, Plans, Jobs, Moderation, Statistics, Finance, Alerts, Audit and Settings use APIs.
- [x] Brocard API v2 account/card synchronization persists financial snapshots and provider request IDs.
- [x] Live Google operations and deterministic local simulation are visibly distinguished.
- [x] Backend tests, frontend tests, Docker health checks and browser acceptance pass.

## Baseline stubs found

- Dashboard `Refresh` and `New Upload` buttons had no handlers.
- Navigation was component state only, so routes did not survive refresh or support deep links.
- Connections defaulted to service-account JSON; OAuth did not perform an authorization-code flow.
- Jobs contained only a ping task and no campaign/media execution.
- Google Ads adapter contained connection testing and account listing only.
- No upload, media, template, deployment-plan, moderation, statistics, finance or notification models/routes existed.

## Acceptance rule

The application is not considered ready until `/uploads/new` opens a persisted workflow, a plan can
pass local validation and `validate_only` (live or explicitly labeled simulation), confirmation is
required, and a refresh restores the same upload and results from PostgreSQL.
