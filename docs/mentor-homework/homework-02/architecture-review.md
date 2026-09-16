# Architecture Review — Homework #2

## Metadata

- Homework: #2
- Project: Project 0 — Axyro
- Level: Level 2 — Application Structure
- Tracks: Track B — Architecture; Track C — Domain Modelling
- Checkpoint: CP2 — Structure checkpoint
- Homework status: Активно
- Artifact status: Draft — assembled from verified code, not yet committed to the required repository path
- Repository: `ruiskhakov2017-sys/demand-upload`
- Reviewed branch: `codex/explorer-production-access`
- Required repository path: `docs/mentor-homework/homework-02/architecture-review.md`

## Logical Areas

### 1. Auto-upload / Campaign Launch

**Responsibility**

Turns user launch settings into concrete Demand Gen campaign instances, validates the launch plan, and after explicit confirmation sends creation requests to Google Ads.

**Main concepts and data**

- `CampaignUpload`
- `LaunchBatch`
- `AccountTestBundle`
- `CampaignInstance`
- `DeploymentPlan`
- `MediaAsset`
- Google Ads connection / target `customer_id`

**Evidence in Axyro**

- `backend/app/api/routes/uploads.py` — `create_upload`, `update_upload`
- `backend/app/api/routes/batches.py` — `generate_launch_batch`
- `backend/app/domain/batch_generator.py` — `generate_batch_matrix`
- `backend/app/api/routes/plans.py` — `build_plan`, `validate_plan`, `confirm_plan`
- `backend/app/jobs/tasks.py` — `deploy_plan`
- `backend/app/google_ads/versions/v24_2/adapter.py` — `validate_plan`, `deploy_plan`, `_execute_plan`

**Boundary**

The business area owns preparation and orchestration of a launch. Google Ads itself is an external infrastructure boundary. MCC/account connectivity is a supporting integration for this area, not a separate business area in this review.

---

### 2. Analytics / Statistics

**Responsibility**

Collects advertising results and turns raw Google Ads data into metrics that can be viewed and used by other parts of Axyro.

**Main concepts and data**

- impressions
- clicks
- cost
- conversions
- registrations / deposits where mappings exist
- metric snapshots
- moderation/statistics snapshots

**Evidence in Axyro**

- `backend/app/jobs/tasks.py` — `sync_google_data`, `sync_launch_group_metrics`
- `backend/app/google_ads/versions/v24_2/adapter.py` — `fetch_statistics`, performance/metrics reads
- database models such as metric/performance snapshots in `backend/app/db/models.py`

**Boundary**

Analytics answers mainly **“what happened?”** It collects and aggregates facts. It does not own the operational lifecycle of accounts and campaigns; that is the Control Center boundary.

---

### 3. AI Contour

**Responsibility**

Provides the AI layer: conversations, model runs, tool calls, drafts, policies and controlled AI actions over Axyro data.

**Main concepts and data**

- `AiConversation`
- `AiRun`
- `AiMessage`
- `AiToolCall`
- `AiDraft`
- model profiles / authority modes / usage

**Evidence in Axyro**

- `backend/app/api/routes/ai_analyst.py`
- `backend/app/ai/gateway.py`
- `backend/app/ai/orchestrator.py`
- `backend/app/ai/policy.py`
- `backend/app/ai/providers.py`
- `backend/app/ai/tools.py`
- AI ORM models in `backend/app/db/models.py`

**Boundary**

The AI contour can read data, use permitted tools and prepare or request actions, but it is not the owner of Google account state, campaign-launch generation or analytics storage.

---

### 4. Control Center

**Responsibility**

Maintains and operates the current working state of Google Ads accounts and campaigns: statuses, problems, rules, notes, tags, actions, synchronization and operational monitoring.

**Main concepts and data**

- `CustomerAccount`
- `ControlCenterCampaign`
- `ControlCenterProblem`
- `ControlCenterRule`
- action requests
- work statuses
- monitoring state
- sync runs/items

**Evidence in Axyro**

- `backend/app/api/routes/control_center.py`
- `backend/app/control_center/query.py`
- `backend/app/control_center/rule_engine.py`
- `backend/app/control_center/rules.py`
- `backend/app/control_center/service.py`
- `backend/app/jobs/control_center_tasks.py`

**Boundary**

Control Center answers mainly **“what is the operational state and what should we do with it?”** It can consume metrics, but analytics is the source of measured results. It can operate campaigns created by Auto-upload, but it is not responsible for generating a launch matrix.

---

## Scenario Trace

### Scenario

One MCC contains three child Google Ads accounts. The user wants Axyro to create **one Demand Gen campaign in each child account**.

This scenario is primarily inside the **Auto-upload / Campaign Launch** business area and crosses an infrastructure boundary into **Google Ads**. It does not need to cross AI or Analytics to perform the launch.

### Real path through Axyro

1. **Create/update upload draft**
   - `backend/app/api/routes/uploads.py`
   - `create_upload()` creates a `CampaignUpload` in `DRAFT` state.
   - `update_upload()` can attach the Google connection and launch configuration.

2. **Generate a concrete launch batch**
   - `backend/app/api/routes/batches.py`
   - `generate_launch_batch()` validates the selected connection/accounts and calls `generate_batch_matrix()`.

3. **Expand the request by account**
   - `backend/app/domain/batch_generator.py`
   - `generate_batch_matrix()` loops through selected accounts.
   - With three selected accounts and `campaigns_per_account = 1`, the result is three account bundles and three campaign instances.
   - Every generated campaign instance contains its own child account `customer_id`.

4. **Persist launch entities**
   - `generate_launch_batch()` stores `LaunchBatch`, `AccountTestBundle`, `CampaignInstance` and creative assignments.
   - It also marks/enqueues validation.
   - **Evidence boundary:** at this stage campaigns are not yet created in Google Ads.

5. **Build a deployment plan**
   - `backend/app/api/routes/plans.py`
   - `build_plan()` builds a snapshot from the batch and runs local/domain validation.
   - It creates a `DeploymentPlan`.
   - **Evidence boundary:** building the plan still does not create campaigns in Google Ads.

6. **Validate with Google without creating**
   - `plans.py::validate_plan()` builds the real Google Ads adapter and calls `adapter.validate_plan(...)`.
   - `GoogleAdsV242Adapter.validate_plan()` calls `_execute_plan(..., validate_only=True)`.
   - Google is contacted, but `validate_only=True` means this stage validates requests without creating the campaigns.

7. **User confirms the launch**
   - `plans.py::confirm_plan()` requires a prior validation result.
   - It creates/reuses a background `Job` of type `DEPLOY_PLAN`, marks the plan/upload/batch queued and calls `deploy_plan.delay(...)`.

8. **Background worker performs the real deployment**
   - `backend/app/jobs/tasks.py::deploy_plan()` loads the plan and pending campaign instances.
   - For a real Google mode it builds the Google Ads adapter and calls `adapter.deploy_plan(snapshot)`.

9. **Google Ads adapter targets each child account**
   - `backend/app/google_ads/versions/v24_2/adapter.py`
   - `deploy_plan()` calls `_execute_plan(..., validate_only=False)`.
   - `_execute_plan()` loops through campaigns, reads each campaign's `customer_id`, builds `MutateGoogleAdsRequest`, assigns that `customer_id` to the request and sends the mutation.
   - Therefore the MCC is the manager/authentication context; the campaigns are created in the selected child customer accounts.

10. **Store the result**
    - The worker saves Google request IDs/resource names and updates local statuses.
    - Successful campaign instances are stored as `PAUSED` after creation.

### Business-level trace to remember

User selects three accounts and campaign settings → Axyro creates three concrete campaign instances → builds and validates a final plan → Google validates without creation → user confirms → Celery worker sends real requests → each request targets its child account → Google returns results → Axyro stores resource names/statuses.

---

## Two Design Problems

### Problem 1 — Mixed responsibilities in `backend/app/jobs/tasks.py`

#### Observation

The same Celery task module contains background processes from several different functional/business areas, including:

- domain validation — `validate_upload_domains`
- campaign deployment — `deploy_plan`
- campaign status changes — `apply_campaign_status_action`
- campaign metrics synchronization — `sync_launch_group_metrics`
- YouTube upload/polling — `upload_youtube_video`, `poll_youtube_video`
- Google moderation/statistics synchronization — `sync_google_data`
- Brocard finance synchronization — `sync_finance`

The module also directly works with the database, many ORM models, Google Ads adapters, Brocard, audit/job events and notifications.

#### Why this is a problem

The file has **low cohesion**: its contents do not represent one narrow responsibility. It also has broad **coupling** to multiple parts of the system.

The problem is not simply that the file is large. The structural problem is that unrelated processes such as Google Ads deployment and Brocard finance synchronization live in the same general task module and depend on a wide common set of infrastructure/models/helpers.

#### Engineering consequences

- Change-impact analysis becomes harder: when one process changes, a reviewer must understand a larger shared module.
- Regression testing scope is harder to reason about because neighboring task flows and shared helpers/imports must be considered.
- Business boundaries are less visible in the code structure.
- The module becomes harder to read, review and maintain as more background processes are added.

#### If left as-is

The file can continue to work, but as new background jobs are added it is likely to accumulate more unrelated responsibilities. That increases cognitive load and makes safe localized changes progressively harder.

**Important evidence limit:** sharing one file does not prove that changing Brocard will automatically break Google deployment. The proven issue is mixed responsibility and broad dependency surface; actual runtime coupling must be checked separately.

---

### Problem 2 — Many different data areas in `backend/app/db/models.py`

#### Observation

A single ORM module describes models from many different areas of Axyro, including:

- users/auth/session models
- Google credentials/connections/MCC/customer accounts
- Control Center campaigns, ads, assets, problems, rules and history
- Auto-upload entities such as `CampaignUpload`, `LaunchBatch`, `AccountTestBundle`, `CampaignInstance`, `DeploymentPlan`, schedules and media
- jobs/events
- AI conversations, runs, messages, tool calls, drafts and settings
- analytics/metric-related models

There are also direct cross-area database links. A concrete example is `ControlCenterCampaign.uploader_campaign_instance_id`, which is a foreign key to `campaign_instances` from the uploader flow.

#### Why this is a problem

Again, the problem is not file size by itself. The issue is that the persistence structure makes business ownership/boundaries difficult to see and can encourage different areas to depend directly on each other's internal data models.

#### Engineering consequences

- It is harder to locate which models belong to which business area.
- Schema changes require more careful impact analysis across a central module.
- Cross-area dependencies can become hidden or accidental.
- The code structure does not clearly reflect the logical boundaries identified above.

#### If left as-is

The project can continue working, but as new models appear the central ORM module can become increasingly difficult to navigate and cross-area coupling can grow without being obvious.

**Important evidence limit:** splitting the file alone would not remove database coupling. Existing foreign keys and other cross-area contracts would remain until explicitly reviewed.

---

## Decision Trace — `backend/app/jobs/tasks.py`

### Observation

`backend/app/jobs/tasks.py` mixes unrelated background processes: campaign deployment, status actions, metrics, YouTube processing, Google data sync, domain validation and Brocard finance sync. The module also imports/uses a broad set of database models and external integrations.

### User hypothesis

Split `tasks.py` into several parts by business logic so that each part is responsible for its own area of the system.

### AI challenge

Physical file splitting alone does not automatically reduce coupling. If the new task modules continue to depend directly on each other's internal services/models or share the same tightly coupled helpers, the dependencies remain; the code is only distributed across more files.

### Evidence

The current module contains clearly different operations, for example:

- `deploy_plan` — deployment of Google Ads campaigns
- `upload_youtube_video` / `poll_youtube_video` — media/YouTube processing
- `sync_google_data` — Google Ads moderation/statistics synchronization
- `sync_finance` — Brocard finance synchronization

It imports database models covering deployment, media, metrics, moderation, finance and Google connections, and also calls Google Ads and Brocard integrations.

### User final decision

Split the tasks by business areas **and at the same time review the direct dependencies between the resulting task modules/areas**. Keep only dependencies that are actually necessary instead of assuming that file splitting by itself solves coupling.

### Trade-off

**Benefit:**

- clearer business boundaries;
- easier localization of changes;
- easier code review and reasoning about what a change can affect;
- lower risk of accidentally touching unrelated areas;
- more focused testing where dependencies really are isolated.

**Cost / risk:**

- the refactoring itself is additional work;
- existing dependencies must first be identified and understood;
- imports/call paths/helpers must be moved carefully;
- regression checks are needed to confirm that background flows still work after the change;
- if real cross-area dependencies remain, wider integration/regression testing will still be necessary.

### Why this option was chosen

A simple “large file → several small files” change would improve readability but could leave the architectural coupling unchanged. The chosen option tries to improve both physical organization and the actual boundaries between business areas.

---

## Open Questions for Mentor

1. For Axyro at its current size, would you already split `tasks.py` by business area, or would you leave it centralized until a specific maintenance/testability problem appears?
2. When splitting background tasks, what boundary would you prefer: business context (`finance`, `media`, `deployment`, `analytics`) or another grouping principle?
3. Do you consider the direct `ControlCenterCampaign -> CampaignInstance` foreign key an acceptable integration between contexts, or would you prefer a weaker/stabler contract between Control Center and Uploader?
4. How far should we go in separating ORM models by bounded context before the extra modules/import management becomes overengineering for Axyro?

---

## Evidence Boundaries / What Is Not Proven Yet

- No architecture refactor was implemented as part of this review.
- No production systems were changed.
- No push, PR or merge was performed for this artifact.
- The review identifies concrete structural evidence, but it does not claim that every direct dependency is wrong.
- We have not exhaustively mapped every dependency between all Axyro contexts.
- The proposed design is a design decision for discussion/defense, not proof that the refactor will improve production behavior without implementation and tests.
- Roadmap topics remain `In progress` until the required Defense/review criteria are satisfied.
