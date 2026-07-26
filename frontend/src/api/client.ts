import { t } from "../i18n";

export type User = {
  id: string;
  username: string;
  email: string | null;
  role: "ADMIN" | "OPERATOR" | "VIEWER";
  is_active: boolean;
};

export type Session = { user: User; csrf_token: string };

export type GoogleConnection = {
  id: string;
  name: string;
  login_customer_id: string;
  auth_type: "SERVICE_ACCOUNT" | "OAUTH_WEB";
  environment: "TEST" | "PRODUCTION";
  api_version: string;
  status: "DRAFT" | "NEEDS_CREDENTIALS" | "CONNECTED" | "VERIFIED" | "ERROR";
  last_checked_at: string | null;
  last_error: string | null;
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
  updated_at: string;
};

export type CampaignDraft = {
  execution_mode?: "SIMULATION" | "LIVE";
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
  checked_at: string;
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
  execution_mode: "SIMULATION" | "LIVE";
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
  execution_mode?: "SIMULATION" | "LIVE";
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
  execution_mode: "SIMULATION" | "LIVE";
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
  if (csrf && ["POST", "PATCH", "DELETE"].includes((init.method || "GET").toUpperCase())) {
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

  listUploads: () => request<CampaignUpload[]>("/uploads"),
  createUpload: (payload: { name: string; execution_mode: "SIMULATION" | "LIVE" }) =>
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
    request<DomainValidationReport>(`/uploads/${id}/domain-validation/retry`, { method: "POST" }),

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
  buildPlan: (uploadId: string, execution_mode: "SIMULATION" | "LIVE", schedule_id?: string | null) =>
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
  getSettings: () => request<Record<string, any>>("/operations/settings")
};
