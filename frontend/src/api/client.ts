import { t } from "../i18n";

export type User = {
  id: string;
  username: string;
  email: string | null;
  role: "ADMIN" | "OPERATOR" | "VIEWER";
  is_active: boolean;
};

export type Session = { user: User; csrf_token: string };
export type ExecutionMode = "SIMULATION" | "GOOGLE_TEST" | "PRODUCTION";
export type AiAuthorityMode = "READ_ONLY" | "DRAFT_ONLY" | "CONFIRM_REQUIRED";

export type AiScope = {
  connection_ids: string[];
  mcc_ids: string[];
  geo_ids: string[];
  account_ids: string[];
  campaign_ids: string[];
  period: "today" | "yesterday" | "3d" | "7d" | "30d" | "custom";
  start_date: string | null;
  end_date: string | null;
  metric_source: string;
  currency: string | null;
};

export type AiConversation = {
  id: string;
  title: string;
  authority_mode: AiAuthorityMode;
  google_environment: ExecutionMode;
  scope: AiScope;
  locale: "ru" | "en";
  time_zone: string;
  last_message_at: string | null;
  archived_at: string | null;
  retention_until: string | null;
  created_at: string;
  updated_at: string;
  messages?: AiMessage[];
};

export type AiToolTimelineItem = {
  id: string;
  tool_name: string;
  tool_version: string;
  risk_class: string;
  status: string;
  error_code: string | null;
  duration_ms: number | null;
  job_id: string | null;
  job_status: string | null;
  job_path: string | null;
  created_at: string;
};

export type AiStructuredAnswer = {
  answer: string;
  resolved_scope: Record<string, any>;
  period: Record<string, any>;
  timezones: string[];
  sources: Array<Record<string, any>>;
  freshness: string;
  completeness: string;
  currency_groups: Array<{ currency_code: string; cost_micros: number | null; conversion_value: number | null; accounts: number }>;
  findings: Array<{ title: string; detail: string; severity: "INFO" | "SUCCESS" | "WARNING" | "ERROR"; condition: string; conclusion: string; confidence: number; evidence_indexes: number[] }>;
  evidence: Array<Record<string, any>>;
  exact_backend_condition: string;
  conclusion: string;
  confidence: number;
  caveats: string[];
  warnings: string[];
  tables: Array<{ title: string; columns: Array<{ key: string; label: string; format: string }>; rows: Array<{ object_type: string | null; object_id: string | null; cells: Array<{ key: string; value: string; numeric_value: number | null; currency_code: string | null }> }> }>;
  charts: Array<{ title: string; kind: "BAR" | "LINE"; unit: string; series: Array<{ name: string; color: string; points: Array<{ label: string; value: number }> }> }>;
  object_links: Array<{ label: string; path: string; object_type: string; object_id: string }>;
  draft: Record<string, any> | null;
};

export type AiMessage = {
  id: string;
  role: "USER" | "ASSISTANT";
  content: string;
  structured_content: Partial<AiStructuredAnswer>;
  status: string;
  run_id: string | null;
  tool_timeline: AiToolTimelineItem[];
  created_at: string;
};

export type AiDraft = {
  id: string;
  conversation_id: string | null;
  draft_type: string;
  status: string;
  authority_mode: AiAuthorityMode;
  google_environment: ExecutionMode;
  scope: Record<string, any>;
  payload: Record<string, any>;
  source_snapshot: Record<string, any>;
  fingerprint: string;
  version: number;
  expires_at: string;
  linked_entity_type: string | null;
  linked_entity_id: string | null;
  action_request_id: string | null;
  created_at: string;
  updated_at: string;
};

export type AiReport = {
  id: string;
  conversation_id: string | null;
  run_id: string | null;
  title: string;
  report: Record<string, any>;
  scope: Record<string, any>;
  observed_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AiCapabilities = {
  enabled: boolean;
  kill_switch: boolean;
  provider: { name: string; configured: boolean; key_source: string; store: boolean; live_model_access_verified: boolean };
  role: User["role"];
  authority_modes: AiAuthorityMode[];
  environments: ExecutionMode[];
  production: Record<string, boolean>;
  models: Array<Record<string, any>>;
  tools: Array<{ name: string; risk: string; version: string }>;
  limits: Record<string, number>;
};

export type AiSourceRegistryItem = {
  capabilities: {
    provider_id: string;
    label: string;
    data_kinds: string[];
    semantic_metrics: string[];
    supports_read: boolean;
    supports_refresh: boolean;
    provenance_version: string;
  };
  status: {
    provider_id: string;
    configured: boolean;
    enabled: boolean;
    live_verified: boolean;
    setup_status: string;
    explanation: string;
    active_mappings: number;
  };
};

export type GoogleConnection = {
  id: string;
  name: string;
  login_customer_id: string;
  auth_type: "SERVICE_ACCOUNT" | "OAUTH_WEB";
  environment: "TEST" | "PRODUCTION";
  connection_mode: ExecutionMode;
  api_version: string;
  status: "DRAFT" | "NEEDS_CREDENTIALS" | "CONNECTED" | "VERIFIED" | "ERROR";
  last_checked_at: string | null;
  last_error: string | null;
  test_hierarchy_root_customer_id: string | null;
  hierarchy_verified_at: string | null;
  hierarchy_request_ids: string[];
  created_at: string;
  updated_at: string;
};

export type CustomerAccount = {
  id: string;
  connection_id: string;
  customer_id: string;
  manager_customer_id: string | null;
  descriptive_name: string | null;
  currency_code: string | null;
  time_zone: string | null;
  can_manage_clients: boolean;
  is_test_account: boolean;
  is_hidden: boolean;
  status: string | null;
  parent_customer_id: string | null;
  hierarchy_root_customer_id: string | null;
  hierarchy_level: number | null;
  account_type: "MANAGER" | "CLIENT";
  last_sync_success_at: string | null;
  test_account_verified_at: string | null;
  last_google_request_ids: string[];
  updated_at: string;
};

export type ControlCenterTag = {
  id: string;
  name: string;
  color: string;
  accounts_count?: number;
};

export type ControlCenterMetrics = {
  impressions: number | null;
  clicks: number | null;
  cost_micros: number | null;
  conversions: number | null;
  all_conversions: number | null;
  registrations: number | null;
  deposits: number | null;
  registration_value: number | null;
  deposit_value: number | null;
  registration_data_available: boolean;
  deposit_data_available: boolean;
  budget_micros: number | null;
  conversion_value: number | null;
  active_campaigns: number | null;
  disapproved_ads: number | null;
  policy_issues: number | null;
  ctr: number | null;
  cpc_micros: number | null;
  cost_per_conversion_micros: number | null;
  cpa_registration_micros: number | null;
  cpa_deposit_micros: number | null;
  registration_rate: number | null;
  registration_to_deposit_rate: number | null;
  roas: number | null;
  freshness: string;
  data_observed_at: string | null;
  boundary_precision: string;
  last_error_code: string | null;
  last_request_id: string | null;
  data_source_mode: ExecutionMode | "UNKNOWN";
  no_data_reason: string | null;
};

export type ControlCenterAccount = {
  id: string;
  connection_id: string;
  connection_name: string | null;
  customer_id: string;
  manager_customer_id: string | null;
  parent_customer_id: string | null;
  primary_mcc_id: string | null;
  mcc_customer_id: string | null;
  mcc_name: string | null;
  hierarchy_level: number | null;
  access_path_count: number;
  descriptive_name: string | null;
  local_name: string | null;
  display_name: string;
  currency_code: string | null;
  time_zone: string | null;
  geo: {
    id: string;
    iso_code: string;
    display_name: string;
    color: string;
    short_label: string | null;
  } | null;
  geo_id: string | null;
  geo_source: "MCC" | "ACCOUNT_OVERRIDE";
  geo_override_id: string | null;
  google_status: string;
  google_status_label: string;
  work_status: "PREPARATION" | "READY" | "WORKING" | "MANUAL_PAUSE" | "PROBLEM" | "APPEAL" | "ARCHIVED" | "DO_NOT_USE";
  work_status_label: string;
  current_note: string | null;
  note_updated_at: string | null;
  note_updated_by_id: string | null;
  pinned_note: string | null;
  pinned_note_updated_at: string | null;
  pinned_note_updated_by_id: string | null;
  tags: ControlCenterTag[];
  is_pinned: boolean;
  is_test_account: boolean;
  is_hidden: boolean;
  is_detached: boolean;
  detached_at: string | null;
  last_sync_attempt_at: string | null;
  last_sync_success_at: string | null;
  sync_error: string | null;
  verification_status: string | null;
  verification_deadline: string | null;
  verification_action_url: string | null;
  verification_checked_at: string | null;
  has_problem: boolean;
  active_problem_count: number;
  problem_types?: string[];
  activity_status: string;
  activity_period_days: number;
  metrics: ControlCenterMetrics;
  updated_at: string;
};

export type ControlCenterCampaign = {
  id: string;
  account_id: string;
  customer_id: string | null;
  account_name: string | null;
  resource_name: string;
  campaign_id: string;
  name: string;
  source: string;
  channel_type: string | null;
  channel_subtype: string | null;
  status: string | null;
  primary_status: string | null;
  primary_status_reasons: string[];
  budget_resource_name: string | null;
  budget_micros: number | null;
  budget_shared: boolean | null;
  bidding_strategy_type: string | null;
  currency_code: string | null;
  metrics: ControlCenterMetrics;
  policy_issues: Array<Record<string, unknown>>;
  policy_status: string | null;
  last_change_at: string | null;
  manually_paused: boolean;
  last_synced_at: string | null;
  sync_error: string | null;
};

export type SavedControlCenterView = {
  id: string;
  owner_user_id: string;
  is_owner: boolean;
  name: string;
  entity_level: "ACCOUNT" | "CAMPAIGN";
  config: Record<string, any>;
  is_default: boolean;
  is_shared: boolean;
  description: string | null;
  source_view_id: string | null;
  created_at: string;
  updated_at: string;
};

export type ControlCenterGeo = {
  id: string;
  iso_code: string;
  display_name: string;
  default_currency_code: string | null;
  default_time_zone: string | null;
  is_active: boolean;
  color: string;
  short_label: string | null;
};

export type ControlCenterMcc = {
  id: string;
  connection_id: string;
  connection_name: string | null;
  customer_id: string;
  parent_customer_id: string | null;
  descriptive_name: string | null;
  currency_code: string | null;
  time_zone: string | null;
  is_root: boolean;
  hierarchy_level: number | null;
  status: string | null;
  geo: ControlCenterGeo | null;
  geo_assignment_status: "ASSIGNED" | "UNASSIGNED";
  first_seen_at: string | null;
  last_seen_at: string | null;
  last_sync_success_at: string | null;
  detached_at: string | null;
};

export type ControlCenterAdGroup = {
  id: string;
  account_id: string;
  campaign_id: string;
  resource_name: string;
  ad_group_id: string;
  name: string;
  status: string | null;
  ad_group_type: string | null;
  optimized_targeting_enabled: boolean | null;
  metrics: ControlCenterMetrics;
  policy_issues: Array<Record<string, unknown>>;
  last_synced_at: string | null;
};

export type ControlCenterAd = {
  id: string;
  account_id: string;
  campaign_id: string;
  ad_group_id: string;
  resource_name: string;
  ad_id: string;
  name: string | null;
  ad_type: string | null;
  status: string | null;
  policy_status: string | null;
  final_urls: string[];
  policy_summary: Record<string, any>;
  disapproval_reasons: Array<Record<string, any>>;
  metrics: ControlCenterMetrics;
  last_synced_at: string | null;
};

export type ControlCenterAsset = {
  id: string;
  account_id: string;
  resource_name: string;
  asset_id: string;
  name: string | null;
  asset_type: string | null;
  source: string | null;
  status: string | null;
  image_url: string | null;
  image_width: number | null;
  image_height: number | null;
  youtube_video_id: string | null;
  youtube_processing_status: string | null;
  processing_note: string | null;
  last_synced_at: string | null;
};

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export type ControlCenterProblem = {
  id: string;
  account_id: string | null;
  account_name: string | null;
  customer_id: string | null;
  campaign_id: string | null;
  source: string;
  problem_type: string;
  severity: string;
  title: string;
  description: string;
  google_code: string | null;
  request_id: string | null;
  state: "NEW" | "SEEN" | "RESOLVED";
  first_seen_at: string;
  last_seen_at: string;
  resolved_at: string | null;
  diagnostics: Record<string, unknown>;
};

export type ControlCenterRule = {
  id: string;
  name: string;
  enabled: boolean;
  mode: "DRY_RUN" | "LIVE";
  scope: Record<string, any>;
  condition_logic: "AND" | "OR";
  conditions: Array<Record<string, any>>;
  actions: Array<Record<string, any>>;
  safeguards: Record<string, any>;
  cooldown_minutes: number;
  max_actions_per_run: number;
  max_actions_per_day: number;
  priority: number;
  schedule: Record<string, any>;
  max_budget_change_percent: number | null;
  live_confirmed_at: string | null;
  live_confirmed_by_id: string | null;
  last_evaluated_at: string | null;
  last_action_at: string | null;
  circuit_open_until: string | null;
  created_at: string;
  updated_at: string;
};

export type CampaignDraft = {
  execution_mode?: ExecutionMode;
  source_mode?: "MANUAL" | "FILE";
  campaign?: Record<string, unknown>;
  launch_batch_id?: string;
  schedule_id?: string;
  builder?: Record<string, any>;
  domain_validation?: DomainValidationReport;
};

export type DomainProviderResult = {
  provider: string;
  verdict: string;
  categories: string[];
  diagnostics: Record<string, unknown>;
  attempts: number;
};

export type DomainValidationResult = {
  url_hash: string;
  domain: string;
  checked_url: string;
  status: string;
  code: string;
  params: Record<string, any>;
  blocking: boolean;
  warning: boolean;
  cached: boolean;
  checked_at: string | null;
  expires_at: string | null;
  availability: {
    status?: string;
    code?: string;
    http_status?: number | null;
    final_url?: string | null;
    response_ms?: number | null;
    attempts?: number;
  };
  reputation: {
    status?: string;
    enforcement?: "monitor" | "block";
    blocking?: boolean;
    would_block?: boolean;
    categories?: string[];
    providers?: DomainProviderResult[];
    checked_at?: string | null;
  };
  references: Array<Record<string, unknown>>;
};

export type DomainValidationReport = {
  status: string;
  fresh: boolean;
  enforcement: "monitor" | "block";
  checked_at: string | null;
  duration_ms?: number;
  summary: {
    urls: number;
    domains: number;
    working: number;
    blocked: number;
    warnings: number;
  };
  results: DomainValidationResult[];
};

export type DomainValidationStartResult = {
  job_id: string;
  job_status: string;
  reused: boolean;
  report: DomainValidationReport;
};

export type CampaignUpload = {
  id: string;
  name: string;
  status: string;
  source_type: string;
  source_name: string | null;
  source_rows: Array<Record<string, unknown>>;
  draft: CampaignDraft;
  current_step: number;
  connection_id: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type MediaAsset = {
  id: string;
  kind: "IMAGE" | "VIDEO" | "YOUTUBE";
  source: string;
  name: string;
  sha256: string;
  content_type: string | null;
  size_bytes: number;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  aspect_ratio: number | null;
  status: string;
  validation: { valid?: boolean; errors?: string[]; warnings?: string[]; suggested_role?: string };
  youtube_video_id: string | null;
  youtube_upload_resource: string | null;
  google_asset_resources: Record<string, string>;
  details: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type DeploymentPlan = {
  id: string;
  upload_id: string;
  connection_id: string | null;
  launch_batch_id: string | null;
  status: string;
  execution_mode: ExecutionMode;
  fingerprint: string;
  snapshot: Record<string, unknown> & { campaigns?: Array<Record<string, unknown>> };
  local_validation: Validation;
  google_validation: Validation & { mode?: string; details?: Record<string, unknown> };
  result: Record<string, unknown>;
  request_ids: string[];
  resource_names: string[];
  validated_at: string | null;
  confirmed_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type Validation = {
  valid?: boolean;
  ok?: boolean;
  errors?: Array<{ path?: string; code?: string; message: string }>;
  warnings?: Array<{ path?: string; code?: string; message: string }>;
  campaign_count?: number;
  account_count?: number;
};

export type Job = {
  id: string;
  type: string;
  status: string;
  progress_current: number;
  progress_total: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type CampaignTemplate = {
  id: string;
  name: string;
  description: string | null;
  payload: Record<string, unknown>;
  semantic_key: string | null;
  current_version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type CampaignInstance = {
  id: string;
  launch_batch_id: string;
  account_test_bundle_id: string;
  customer_id: string;
  account_name: string;
  currency_code: string;
  time_zone: string;
  campaign_sequence: number;
  campaign_name: string;
  status: string;
  policy_status: string;
  included: boolean;
  budget_micros: number;
  budget: number;
  budget_mode: string;
  copy_mode: string;
  deployment_key: string;
  campaign_settings: Record<string, any>;
  bidding: Record<string, any>;
  targeting: Record<string, any>;
  url_settings: Record<string, any>;
  texts: Record<string, any>;
  creative_assignment: Record<string, any>;
  local_validation: Validation;
  google_validation: Validation & { mode?: string; google_contacted?: boolean };
  resource_names: string[];
  request_ids: string[];
  metrics: Record<string, any>;
  enabled_at: string | null;
  last_synced_at: string | null;
  error_message: string | null;
};

export type LaunchGroup = {
  id: string;
  launch_batch_id: string;
  launch_batch_name?: string | null;
  execution_mode?: ExecutionMode;
  customer_id: string;
  account_name: string;
  currency_code: string;
  time_zone: string;
  status: string;
  campaigns_count: number;
  total_cost_micros?: number;
  total_conversions?: number;
  instances?: CampaignInstance[];
};

export type LaunchBatch = {
  id: string;
  upload_id: string;
  name: string;
  version_number: number;
  creation_mode: string;
  execution_mode: ExecutionMode;
  status: string;
  generation_seed: string;
  financial_preview: Record<string, any>;
  bundles_count: number;
  campaigns_count: number;
  template_version_id?: string | null;
  builder_config?: Record<string, any>;
  bundles?: Array<LaunchGroup & { instances: CampaignInstance[] }>;
  created_at: string;
  updated_at: string;
};

export type ScheduleRun = {
  id: string;
  wave_id: string;
  wave_number: number;
  account_test_bundle_id: string;
  customer_id: string;
  account_name: string;
  position: number;
  scheduled_for: string;
  actual_started_at: string | null;
  actual_completed_at: string | null;
  campaigns_count: number;
  status: string;
  attempts: number;
  next_retry_at: string | null;
  deployment_key: string;
  resource_names: string[];
  request_ids: string[];
  structured_error: Record<string, any>;
};

export type DeploymentSchedule = {
  id: string;
  deployment_plan_id: string | null;
  upload_id: string;
  connection_id: string | null;
  launch_batch_id: string;
  parent_schedule_id: string | null;
  mcc_customer_id: string | null;
  mode: "IMMEDIATE" | "EVEN" | "WAVES" | "MANUAL";
  status: string;
  time_zone: string;
  start_at: string;
  end_at: string;
  max_accounts_per_hour: number;
  max_accounts_per_day: number;
  max_parallel: number;
  circuit_breaker_threshold: number;
  consecutive_serious_errors: number;
  version_number: number;
  fingerprint: string;
  is_current: boolean;
  manual_approval: boolean;
  config: Record<string, any>;
  summary: Record<string, any>;
  pause_reason: string | null;
  recovery_required: boolean;
  confirmed_at: string | null;
  paused_at: string | null;
  completed_at: string | null;
  last_dispatch_at: string | null;
  created_at: string;
  updated_at: string;
  progress: {
    total_accounts: number;
    completed_accounts: number;
    successful_accounts: number;
    failed_accounts: number;
    waiting_accounts: number;
    created_campaigns: number;
    current_wave: number | null;
    next_account: string | null;
    next_run_at: string | null;
  };
  waves: Array<{
    id: string;
    wave_number: number;
    status: string;
    starts_at: string;
    ends_at: string;
    observation_until: string | null;
    approval_required: boolean;
    approved_at: string | null;
  }>;
  runs: ScheduleRun[];
  events: Array<Record<string, any>>;
};

export type SchedulePreview = {
  mode: DeploymentSchedule["mode"];
  time_zone: string;
  fingerprint: string;
  valid: boolean;
  warnings: Array<{ code: string; message: string }>;
  unassigned_accounts: Array<Record<string, any>>;
  summary: Record<string, any>;
  waves: Array<Record<string, any>>;
  runs: Array<{
    account_test_bundle_id: string;
    customer_id: string;
    account_name: string;
    campaigns_count: number;
    budget_micros: number;
    wave_number: number;
    position: number;
    scheduled_for: string;
  }>;
};

const CSRF_KEY = "dgu.csrf";

export function setCsrfToken(token: string) {
  sessionStorage.setItem(CSRF_KEY, token);
}

export function getCsrfToken() {
  return sessionStorage.getItem(CSRF_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const csrf = getCsrfToken();
  if (csrf && ["POST", "PUT", "PATCH", "DELETE"].includes((init.method || "GET").toUpperCase())) {
    headers.set("X-CSRF-Token", csrf);
  }
  const response = await fetch(`/api${path}`, { ...init, headers, credentials: "include" });
  if (!response.ok) {
    let message = t("api.errorStatus", { status: response.status });
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data);
    } catch {
      // Keep the status-based message for non-JSON responses.
    }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  setupStatus: () => request<{ setup_required: boolean; users_count: number }>("/setup/status"),
  bootstrap: (payload: { username: string; password: string; email?: string; setup_token?: string }) =>
    request<Session>("/setup/bootstrap", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: { username: string; password: string }) =>
    request<Session>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<Session>("/auth/me"),
  dashboard: () => request<Record<string, any>>("/dashboard/summary"),

  listConnections: () => request<GoogleConnection[]>("/google-connections"),
  createConnection: (payload: unknown) =>
    request<GoogleConnection>("/google-connections", { method: "POST", body: JSON.stringify(payload) }),
  testConnection: (id: string) =>
    request<{ ok: boolean; status: string; message: string; request_id: string | null; api_version: string }>(
      `/google-connections/${id}/test`,
      { method: "POST" }
    ),
  startOauth: (id: string) =>
    request<{ authorization_url: string; expires_at: string }>(`/google-connections/${id}/oauth/start`, {
      method: "POST"
    }),
  disconnectOauth: (id: string) =>
    request<{ ok: boolean; status: string }>(`/google-connections/${id}/oauth/disconnect`, {
      method: "POST"
    }),
  listAccounts: () => request<CustomerAccount[]>("/accounts"),
  getAccountCatalog: (accountId: string) => request<Record<string, any>>(`/accounts/${accountId}/catalog`),
  syncAccounts: (connectionId: string) =>
    request<{ synced: number; accounts: CustomerAccount[] }>(`/accounts/sync/${connectionId}`, {
      method: "POST"
    }),

  controlCenterSummary: () => request<Record<string, any>>("/control-center/summary"),
  controlCenterAccounts: (params: QueryParams) =>
    request<{
      items: ControlCenterAccount[];
      groups: Array<Record<string, any>>;
      grouping: string;
      total: number;
      counts: Record<string, number>;
      period: Record<string, string>;
      sort: Array<{ field: string; direction: "asc" | "desc" }>;
      filters: Record<string, any>;
    }>(`/control-center/accounts?${queryString(params)}`),
  controlCenterAccount: (id: string, params: Record<string, string | undefined> = {}) =>
    request<Record<string, any>>(
      `/control-center/accounts/${encodeURIComponent(id)}?${queryString(params)}`
    ),
  updateControlCenterAccount: (id: string, payload: Record<string, unknown>) =>
    request<ControlCenterAccount>(`/control-center/accounts/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  bulkControlCenterWorkStatus: (accountIds: string[], workStatus: string) =>
    request<{ updated: number; work_status: string }>("/control-center/accounts/bulk-work-status", {
      method: "POST",
      body: JSON.stringify({ account_ids: accountIds, work_status: workStatus })
    }),
  controlCenterTags: () => request<ControlCenterTag[]>("/control-center/tags"),
  createControlCenterTag: (payload: { name: string; color: string }) =>
    request<ControlCenterTag>("/control-center/tags", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  assignControlCenterTag: (accountId: string, tagId: string) =>
    request<ControlCenterTag>(
      `/control-center/accounts/${encodeURIComponent(accountId)}/tags/${encodeURIComponent(tagId)}`,
      { method: "POST" }
    ),
  removeControlCenterTag: (accountId: string, tagId: string) =>
    request<void>(
      `/control-center/accounts/${encodeURIComponent(accountId)}/tags/${encodeURIComponent(tagId)}`,
      { method: "DELETE" }
    ),
  controlCenterSavedViews: () =>
    request<SavedControlCenterView[]>("/control-center/saved-views?entity_level=ACCOUNT"),
  createControlCenterSavedView: (payload: Record<string, unknown>) =>
    request<SavedControlCenterView>("/control-center/saved-views", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateControlCenterSavedView: (id: string, payload: Record<string, unknown>) =>
    request<SavedControlCenterView>(`/control-center/saved-views/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteControlCenterSavedView: (id: string) =>
    request<void>(`/control-center/saved-views/${encodeURIComponent(id)}`, { method: "DELETE" }),
  duplicateControlCenterSavedView: (id: string) =>
    request<SavedControlCenterView>(
      `/control-center/saved-views/${encodeURIComponent(id)}/duplicate`,
      { method: "POST" }
    ),
  controlCenterGeos: () => request<ControlCenterGeo[]>("/control-center/geos"),
  createControlCenterGeo: (payload: Record<string, unknown>) =>
    request<ControlCenterGeo>("/control-center/geos", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateControlCenterGeo: (id: string, payload: Record<string, unknown>) =>
    request<ControlCenterGeo>(`/control-center/geos/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  controlCenterMcc: (params: QueryParams = {}) =>
    request<ControlCenterMcc[]>(`/control-center/mcc?${queryString(params)}`),
  assignControlCenterMccGeo: (id: string, geoId: string | null) =>
    request<ControlCenterMcc>(`/control-center/mcc/${encodeURIComponent(id)}/geo`, {
      method: "PATCH",
      body: JSON.stringify({ geo_id: geoId })
    }),
  controlCenterHierarchy: (connectionId?: string) =>
    request<Record<string, any>>(
      `/control-center/hierarchy?${queryString({ connection_id: connectionId })}`
    ),
  controlCenterAccessPaths: (accountId: string) =>
    request<Array<Record<string, any>>>(
      `/control-center/accounts/${encodeURIComponent(accountId)}/access-paths`
    ),
  controlCenterManagerHistory: (accountId: string) =>
    request<Array<Record<string, any>>>(
      `/control-center/accounts/${encodeURIComponent(accountId)}/manager-history`
    ),
  controlCenterConversionMappings: (params: QueryParams = {}) =>
    request<Array<Record<string, any>>>(
      `/control-center/conversion-action-mappings?${queryString(params)}`
    ),
  controlCenterConversionCatalog: (accountId: string) =>
    request<Record<string, any>>(
      `/control-center/conversion-actions/catalog?${queryString({ account_id: accountId })}`
    ),
  createControlCenterConversionMapping: (payload: Record<string, unknown>) =>
    request<Record<string, any>>("/control-center/conversion-action-mappings", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deleteControlCenterConversionMapping: (id: string) =>
    request<void>(
      `/control-center/conversion-action-mappings/${encodeURIComponent(id)}`,
      { method: "DELETE" }
    ),
  controlCenterCampaigns: (params: QueryParams) =>
    request<{ items: ControlCenterCampaign[]; total: number }>(
      `/control-center/campaigns?${queryString(params)}`
    ),
  controlCenterAdGroups: (params: QueryParams = {}) =>
    request<{ items: ControlCenterAdGroup[]; total: number }>(
      `/control-center/ad-groups?${queryString(params)}`
    ),
  controlCenterAds: (params: QueryParams = {}) =>
    request<{ items: ControlCenterAd[]; total: number }>(
      `/control-center/ads?${queryString(params)}`
    ),
  controlCenterAssets: (params: QueryParams = {}) =>
    request<{ items: ControlCenterAsset[]; total: number }>(
      `/control-center/assets?${queryString(params)}`
    ),
  controlCenterAssetLinks: (params: QueryParams = {}) =>
    request<Array<Record<string, any>>>(
      `/control-center/asset-links?${queryString(params)}`
    ),
  controlCenterModeration: (params: QueryParams = {}) =>
    request<{ items: ControlCenterAd[]; total: number; data_note: string }>(
      `/control-center/moderation?${queryString(params)}`
    ),
  controlCenterVerification: (params: QueryParams = {}) =>
    request<Array<Record<string, any>>>(
      `/control-center/verification?${queryString(params)}`
    ),
  controlCenterChanges: (params: QueryParams = {}) =>
    request<{ items: Array<Record<string, any>>; total: number; history_depth: string }>(
      `/control-center/changes?${queryString(params)}`
    ),
  controlCenterSyncRuns: () =>
    request<Array<Record<string, any>>>("/control-center/sync-runs"),
  controlCenterProblems: (params: Record<string, string | undefined> = {}) =>
    request<ControlCenterProblem[]>(`/control-center/problems?${queryString(params)}`),
  updateControlCenterProblem: (id: string, state: string) =>
    request<ControlCenterProblem>(`/control-center/problems/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ state })
    }),
  controlCenterHistory: (params: Record<string, string | number | undefined> = {}) =>
    request<Array<Record<string, any>>>(`/control-center/history?${queryString(params)}`),
  estimateControlCenterSync: (scope: string, accountIds: string[]) =>
    request<Record<string, any>>("/control-center/sync/estimate", {
      method: "POST",
      body: JSON.stringify({ scope, account_ids: accountIds })
    }),
  startControlCenterSync: (scope: string, accountIds: string[], estimateToken: string) =>
    request<Record<string, any>>("/control-center/sync", {
      method: "POST",
      body: JSON.stringify({
        scope,
        account_ids: accountIds,
        estimate_token: estimateToken
      })
    }),
  getControlCenterSync: (id: string) =>
    request<Record<string, any>>(`/control-center/sync/${encodeURIComponent(id)}`),
  previewControlCenterAction: (payload: Record<string, unknown>) =>
    request<Record<string, any>>("/control-center/actions/preview", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  confirmControlCenterAction: (id: string, confirmationToken: string) =>
    request<Record<string, any>>(`/control-center/actions/${encodeURIComponent(id)}/confirm`, {
      method: "POST",
      body: JSON.stringify({ confirmation_token: confirmationToken })
    }),
  secondApproveControlCenterAction: (id: string) =>
    request<Record<string, any>>(`/control-center/actions/${encodeURIComponent(id)}/second-approve`, {
      method: "POST"
    }),
  getControlCenterAction: (id: string) =>
    request<Record<string, any>>(`/control-center/actions/${encodeURIComponent(id)}`),
  controlCenterRules: () => request<ControlCenterRule[]>("/control-center/rules"),
  createControlCenterRule: (payload: Record<string, unknown>) =>
    request<ControlCenterRule>("/control-center/rules", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateControlCenterRule: (id: string, payload: Record<string, unknown>) =>
    request<ControlCenterRule>(`/control-center/rules/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  changeControlCenterRuleLiveMode: (
    id: string,
    confirmation: "ENABLE LIVE RULES" | "RETURN TO DRY RUN"
  ) =>
    request<ControlCenterRule>(`/control-center/rules/${encodeURIComponent(id)}/live-mode`, {
      method: "POST",
      body: JSON.stringify({ confirmation })
    }),
  evaluateControlCenterRule: (id: string) =>
    request<Record<string, any>>(`/control-center/rules/${encodeURIComponent(id)}/evaluate`, {
      method: "POST"
    }),
  controlCenterKillSwitch: () =>
    request<{ active: boolean }>("/control-center/rules/kill-switch"),
  updateControlCenterKillSwitch: (active: boolean) =>
    request<{ active: boolean }>("/control-center/rules/kill-switch", {
      method: "PATCH",
      body: JSON.stringify({ active })
    }),
  controlCenterExportUrl: (
    format: "csv" | "xlsx",
    params: QueryParams
  ) => `/api/control-center/accounts/export?${queryString({ format, ...params })}`,

  listUploads: () => request<CampaignUpload[]>("/uploads"),
  createUpload: (payload: { name: string; execution_mode: ExecutionMode }) =>
    request<CampaignUpload>("/uploads", { method: "POST", body: JSON.stringify(payload) }),
  getUpload: (id: string) => request<CampaignUpload>(`/uploads/${id}`),
  updateUpload: (id: string, payload: unknown) =>
    request<CampaignUpload>(`/uploads/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  setManualRows: (id: string, rows: Array<Record<string, unknown>>) =>
    request<CampaignUpload>(`/uploads/${id}/manual-rows`, {
      method: "POST",
      body: JSON.stringify({ rows })
    }),
  importUpload: (id: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<{ upload: CampaignUpload; row_count: number; columns: string[]; preview: any[] }>(
      `/uploads/${id}/import`,
      { method: "POST", body }
    );
  },
  getDomainValidation: (id: string) =>
    request<DomainValidationReport>(`/uploads/${id}/domain-validation`),
  retryDomainValidation: (id: string) =>
    request<DomainValidationStartResult>(`/uploads/${id}/domain-validation`, { method: "POST" }),

  listMedia: () => request<MediaAsset[]>("/media"),
  mediaContentUrl: (id: string) => `/api/media/${encodeURIComponent(id)}/content`,
  uploadMedia: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<MediaAsset>("/media/upload", { method: "POST", body });
  },
  registerYoutube: (video_id: string, name?: string) =>
    request<MediaAsset>("/media/youtube", {
      method: "POST",
      body: JSON.stringify({ video_id, name })
    }),
  queueYoutubeUpload: (id: string, payload: unknown) =>
    request<{ job_id: string; reused: boolean }>(`/media/${id}/youtube-upload`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),

  listTemplates: () => request<CampaignTemplate[]>("/templates"),
  createTemplate: (payload: unknown) =>
    request<CampaignTemplate>("/templates", { method: "POST", body: JSON.stringify(payload) }),
  deleteTemplate: (id: string) => request<void>(`/templates/${id}`, { method: "DELETE" }),
  listTemplateVersions: (id: string) => request<Array<Record<string, any>>>(`/templates/${id}/versions`),
  createTemplateVersion: (id: string, payload: unknown) =>
    request<Record<string, any>>(`/templates/${id}/versions`, { method: "POST", body: JSON.stringify(payload) }),
  copyTemplate: (id: string, payload: unknown) =>
    request<CampaignTemplate>(`/templates/${id}/copy`, { method: "POST", body: JSON.stringify(payload) }),

  getCapabilities: () => request<{ summary: Record<string, any>; fields: Array<Record<string, any>> }>(
    "/google-ads/capabilities"
  ),
  listLaunchBatches: () => request<LaunchBatch[]>("/launch-batches"),
  getLaunchBatch: (id: string) => request<LaunchBatch>(`/launch-batches/${id}`),
  generateLaunchBatch: (uploadId: string, payload: unknown) =>
    request<LaunchBatch>(`/launch-batches/from-upload/${uploadId}/generate`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  patchCampaignInstance: (id: string, payload: unknown) =>
    request<CampaignInstance>(`/campaign-instances/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  launchBatchExportUrl: (id: string, format: "xlsx" | "csv") =>
    `/api/launch-batches/${encodeURIComponent(id)}/export?format=${format}`,

  listPlans: () => request<DeploymentPlan[]>("/plans"),
  getPlan: (id: string) => request<DeploymentPlan>(`/plans/${id}`),
  buildPlan: (uploadId: string, execution_mode: ExecutionMode, schedule_id?: string | null) =>
    request<DeploymentPlan>(`/plans/from-upload/${uploadId}`, {
      method: "POST",
      body: JSON.stringify({ execution_mode, schedule_id: schedule_id || null })
    }),
  validatePlan: (id: string) =>
    request<{
      plan: DeploymentPlan;
      ok: boolean;
      mode: string;
      errors: Array<{ message: string; code?: string }>;
      warnings: Array<{ message: string; code?: string }>;
      request_ids: string[];
    }>(`/plans/${id}/validate`, { method: "POST" }),
  confirmPlan: (id: string, allow_partial = false) =>
    request<{ plan: DeploymentPlan; job_id: string; reused: boolean }>(`/plans/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ confirmation: "CREATE_PAUSED", allow_partial })
    }),

  listSchedules: () => request<DeploymentSchedule[]>("/schedules"),
  getSchedule: (id: string) => request<DeploymentSchedule>(`/schedules/${id}`),
  previewSchedule: (launchBatchId: string, payload: unknown) =>
    request<SchedulePreview>(`/schedules/preview/${launchBatchId}`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createSchedule: (launchBatchId: string, payload: unknown) =>
    request<DeploymentSchedule>(`/schedules/from-launch-batch/${launchBatchId}`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  scheduleAction: (id: string, payload: unknown) =>
    request<DeploymentSchedule>(`/schedules/${id}/actions`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  scheduleReportUrl: (id: string) => `/api/schedules/${encodeURIComponent(id)}/report.csv`,

  listLaunchGroups: () => request<LaunchGroup[]>("/launch-groups"),
  getLaunchGroup: (id: string) => request<LaunchGroup>(`/launch-groups/${id}`),
  createCampaignStatusAction: (id: string, payload: unknown) =>
    request<Record<string, any>>(`/launch-groups/${id}/status-actions`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  syncLaunchGroupMetrics: (id: string) =>
    request<Record<string, any>>(`/launch-groups/${id}/sync-metrics`, { method: "POST" }),
  getLaunchGroupHistory: (id: string) => request<Record<string, any>>(`/launch-groups/${id}/history`),
  getCampaignBuilderGuardrails: () => request<Record<string, any>>("/settings/campaign-builder-guardrails"),
  updateCampaignBuilderGuardrails: (payload: unknown) =>
    request<Record<string, any>>("/settings/campaign-builder-guardrails", {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),

  listJobs: () => request<Job[]>("/jobs"),
  listAudit: () => request<Array<Record<string, unknown>>>("/audit"),
  listModeration: () => request<Array<Record<string, any>>>("/operations/moderation"),
  listStatistics: () => request<Array<Record<string, any>>>("/operations/statistics"),
  queueOperationSync: (kind: "moderation" | "statistics", connection_id: string) =>
    request<{ job_id: string; status: string }>(`/operations/${kind}/sync`, {
      method: "POST",
      body: JSON.stringify({ connection_id })
    }),
  listFinance: () => request<Array<Record<string, any>>>("/operations/finance"),
  getGoogleBilling: (accountId: string) =>
    request<Record<string, any>>(
      `/operations/finance/google-billing/${encodeURIComponent(accountId)}`
    ),
  configureFinance: (payload: unknown) =>
    request<Record<string, any>>("/operations/finance", { method: "POST", body: JSON.stringify(payload) }),
  syncFinance: (id: string) =>
    request<{ job_id: string; status: string }>(`/operations/finance/${id}/sync`, { method: "POST" }),
  listAlerts: () => request<Array<Record<string, any>>>("/operations/alerts"),
  setAlertRead: (id: string, read: boolean) =>
    request<Record<string, any>>(`/operations/alerts/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ read })
    }),
  getSettings: () => request<Record<string, any>>("/operations/settings"),
  aiCapabilities: () => request<AiCapabilities>("/ai/capabilities"),
  aiSourceRegistry: () => request<AiSourceRegistryItem[]>("/ai/source-registry"),
  aiConversations: (archived = false) => request<AiConversation[]>(`/ai/conversations?archived=${archived}`),
  createAiConversation: (payload: Record<string, unknown>) =>
    request<AiConversation>("/ai/conversations", { method: "POST", body: JSON.stringify(payload) }),
  getAiConversation: (id: string) => request<AiConversation>(`/ai/conversations/${encodeURIComponent(id)}`),
  patchAiConversation: (id: string, payload: Record<string, unknown>) =>
    request<AiConversation>(`/ai/conversations/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteAiConversation: (id: string) =>
    request<void>(`/ai/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
  aiConversationExportUrl: (id: string) => `/api/ai/conversations/${encodeURIComponent(id)}/export`,
  cancelAiRun: (id: string) => request<Record<string, any>>(`/ai/runs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  aiDrafts: (status?: string) => request<AiDraft[]>(`/ai/drafts?${queryString({ status })}`),
  patchAiDraft: (id: string, payload: Record<string, unknown>) =>
    request<AiDraft>(`/ai/drafts/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) }),
  applyAiDraft: (id: string, version: number, fingerprint: string) =>
    request<AiDraft & { result: Record<string, any> }>(`/ai/drafts/${encodeURIComponent(id)}/apply`, {
      method: "POST", body: JSON.stringify({ expected_version: version, fingerprint })
    }),
  previewAiDraft: (id: string, version: number, fingerprint: string) =>
    request<{ draft: AiDraft; preview: Record<string, any> }>(`/ai/drafts/${encodeURIComponent(id)}/preview`, {
      method: "POST", body: JSON.stringify({ expected_version: version, fingerprint })
    }),
  deleteAiDraft: (id: string) => request<void>(`/ai/drafts/${encodeURIComponent(id)}`, { method: "DELETE" }),
  aiReports: () => request<AiReport[]>("/ai/reports"),
  aiReportExportUrl: (id: string) => `/api/ai/reports/${encodeURIComponent(id)}/export`,
  deleteAiReport: (id: string) => request<void>(`/ai/reports/${encodeURIComponent(id)}`, { method: "DELETE" }),
  aiPreferences: () => request<Record<string, any>>("/ai/preferences"),
  patchAiPreferences: (payload: Record<string, unknown>) =>
    request<Record<string, any>>("/ai/preferences", { method: "PATCH", body: JSON.stringify(payload) }),
  aiAdminSettings: () => request<Record<string, any>>("/ai/admin/settings"),
  patchAiAdminSettings: (payload: Record<string, unknown>) =>
    request<Record<string, any>>("/ai/admin/settings", { method: "PATCH", body: JSON.stringify(payload) }),
  patchAiModelProfile: (name: string, payload: Record<string, unknown>) =>
    request<Record<string, any>>(`/ai/admin/model-profiles/${encodeURIComponent(name)}`, {
      method: "PATCH", body: JSON.stringify(payload)
    }),
  aiMyUsage: (days = 30) => request<Record<string, any>>(`/ai/usage?days=${days}`),
  aiUsage: (days = 30) => request<Record<string, any>>(`/ai/admin/usage?days=${days}`),
  aiGeoProfiles: () => request<Array<Record<string, any>>>("/ai/geo-profiles"),
  aiGeoOverrides: () => request<Array<Record<string, any>>>("/ai/geo-overrides"),
  createAiGeoProfile: (payload: Record<string, unknown>) =>
    request<Record<string, any>>("/ai/geo-profiles", { method: "POST", body: JSON.stringify(payload) }),
  aiGeoProfileHistory: (id: string) =>
    request<Array<Record<string, any>>>(`/ai/geo-profiles/${encodeURIComponent(id)}/history`),
  putAiGeoOverride: (scopeType: string, scopeId: string, payload: Record<string, unknown>) =>
    request<Record<string, any>>(`/ai/geo-overrides/${encodeURIComponent(scopeType)}/${encodeURIComponent(scopeId)}`, {
      method: "PUT", body: JSON.stringify(payload)
    }),
  aiMetricMappings: () => request<Array<Record<string, any>>>("/ai/metric-source-mappings"),
  createAiMetricMapping: (payload: Record<string, unknown>) =>
    request<Record<string, any>>("/ai/metric-source-mappings", { method: "POST", body: JSON.stringify(payload) }),
  deleteAiMetricMapping: (id: string) =>
    request<void>(`/ai/metric-source-mappings/${encodeURIComponent(id)}`, { method: "DELETE" }),
  transcribeAiAudio: (blob: Blob) => {
    const body = new FormData();
    body.append("file", blob, "voice.webm");
    return request<{ transcript: string; duration_seconds: number; editable: boolean; sent_automatically: boolean }>(
      "/ai/transcribe", { method: "POST", body }
    );
  }
};

export async function streamAiMessage(
  conversationId: string,
  payload: { content: string; model_profile: "FAST" | "BALANCED" | "DEEP"; idempotency_key: string },
  onEvent: (event: string, data: any) => void,
  signal?: AbortSignal
) {
  const headers = new Headers({ "Content-Type": "application/json" });
  const csrf = getCsrfToken();
  if (csrf) headers.set("X-CSRF-Token", csrf);
  const response = await fetch(`/api/ai/conversations/${encodeURIComponent(conversationId)}/messages/stream`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(payload),
    signal
  });
  if (!response.ok || !response.body) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch { /* Keep status. */ }
    throw new Error(detail);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) {
      let event = "message";
      const dataLines: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length) onEvent(event, JSON.parse(dataLines.join("\n")));
    }
    if (done) break;
  }
}

function queryString(params: QueryParams) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") query.set(key, String(value));
  }
  return query.toString();
}
