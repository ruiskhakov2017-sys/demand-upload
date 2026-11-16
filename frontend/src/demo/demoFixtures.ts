import type { ControlCenterMetrics } from "../api/client";
import { demoAccounts } from "../domain/demoAccounts";
import { demoCopy } from "../i18n/demoApi";

export type DemoRecord = Record<string, any>;
export const sampleDate = "2026-09-30T12:00:00.000Z";
export const demoUser = { id: "demo-user", username: "Demo", email: null, role: "ADMIN", is_active: true };

export function metrics(spend: number, conversions: number, weight = 1): ControlCenterMetrics {
  const cost = Math.round(spend * weight * 1_000_000);
  const count = Math.round(conversions * weight);
  const clicks = Math.round(conversions * 22 * weight);
  const impressions = clicks * 20;
  return {
    impressions, clicks, cost_micros: cost, conversions: count, all_conversions: count,
    registrations: count, deposits: Math.round(count * .3), registration_value: count * 100,
    deposit_value: count * 100, registration_data_available: true, deposit_data_available: true,
    budget_micros: 1_200_000_000, conversion_value: count * 100, active_campaigns: 2,
    disapproved_ads: 0, policy_issues: 0, ctr: clicks / Math.max(1, impressions) * 100,
    cpc_micros: cost / Math.max(1, clicks), cost_per_conversion_micros: cost / Math.max(1, count),
    cpa_registration_micros: cost / Math.max(1, count), cpa_deposit_micros: cost / Math.max(1, Math.round(count * .3)),
    registration_rate: count / Math.max(1, clicks) * 100, registration_to_deposit_rate: 30,
    roas: count * 100 / Math.max(1, spend * weight), freshness: "FRESH", data_observed_at: sampleDate,
    boundary_precision: "EXACT", last_error_code: null, last_request_id: null, data_source_mode: "SIMULATION", no_data_reason: null,
  };
}

export function createDemoState() {
  const copy = demoCopy();
  const geos = [
    { id: "geo-us", iso_code: "US", display_name: "North America", short_label: "US", default_time_zone: "America/New_York", color: "#315ba8" },
    { id: "geo-de", iso_code: "DE", display_name: "DACH", short_label: "DE", default_time_zone: "Europe/Berlin", color: "#6c65aa" },
    { id: "geo-gb", iso_code: "GB", display_name: "UK & Ireland", short_label: "UK", default_time_zone: "Europe/London", color: "#3b7c75" }
  ].map(item => ({ ...item, default_currency_code: "USD", is_active: true }));
  const tags = [{ id: "tag-priority", name: copy.tag, color: "#315ba8", accounts_count: 1 }];
  const accounts: DemoRecord[] = demoAccounts.map((item, index) => ({
    id: "demo-account-" + (index + 1), connection_id: "demo-connection", connection_name: copy.connection,
    customer_id: "100000000" + index, manager_customer_id: "1000000099", parent_customer_id: "1000000099",
    primary_mcc_id: "demo-mcc-" + index, mcc_customer_id: "1000000099", mcc_name: item.name + " MCC",
    hierarchy_level: 1, access_path_count: 1, descriptive_name: item.name, local_name: item.name, display_name: item.name,
    currency_code: "USD", time_zone: geos[index].default_time_zone, geo: geos[index], geo_id: geos[index].id,
    geo_source: "MCC", geo_override_id: null, google_status: "ENABLED", google_status_label: "ENABLED",
    work_status: index === 2 ? "MANUAL_PAUSE" : "WORKING", work_status_label: "WORKING",
    current_note: index === 0 ? copy.note : null, note_updated_at: sampleDate, note_updated_by_id: "demo-user",
    pinned_note: null, pinned_note_updated_at: null, pinned_note_updated_by_id: null,
    tags: index === 0 ? tags : [], is_pinned: false, is_test_account: true, is_hidden: false, is_detached: false,
    detached_at: null, last_sync_attempt_at: sampleDate, last_sync_success_at: sampleDate, sync_error: null,
    verification_status: index === 1 ? "REQUIRED" : "SUCCESS", verification_deadline: index === 1 ? "2026-10-15T00:00:00Z" : null,
    verification_action_url: null, verification_checked_at: sampleDate,
    has_problem: index === 1, active_problem_count: index === 1 ? 2 : 0, problem_types: index === 1 ? ["POLICY", "VERIFICATION"] : [],
    activity_status: index === 2 ? "NO_ACTIVE_CAMPAIGNS" : "SPENDING", activity_period_days: 7,
    metrics: metrics(item.values[30][0], item.values[30][1]), updated_at: sampleDate,
  }));
  const campaigns: DemoRecord[] = accounts.flatMap((account, index) => [0, 1].map(sequence => ({
    id: "demo-campaign-" + index + "-" + sequence, account_id: account.id, customer_id: account.customer_id, account_name: account.display_name,
    resource_name: "customers/" + account.customer_id + "/campaigns/" + (100 + sequence),
    campaign_id: String(100 + index * 10 + sequence), name: account.display_name + (sequence ? " · Remarketing" : " · Demand Gen"),
    source: "GOOGLE_ADS_MANUAL", channel_type: "DEMAND_GEN", channel_subtype: null,
    status: index === 2 ? "PAUSED" : "ENABLED", primary_status: index === 2 ? "PAUSED" : "ELIGIBLE", primary_status_reasons: [],
    budget_resource_name: "sample-budget-" + index + "-" + sequence, budget_micros: (sequence ? 300 : 900) * 1_000_000,
    budget_shared: false, bidding_strategy_type: "MAXIMIZE_CONVERSIONS", currency_code: "USD",
    metrics: metrics(demoAccounts[index].values[30][0], demoAccounts[index].values[30][1], sequence ? .25 : .75),
    policy_issues: [], policy_status: "APPROVED", last_change_at: sampleDate, manually_paused: index === 2,
    last_synced_at: sampleDate, sync_error: null,
  })));
  const ads: DemoRecord[] = campaigns.map((campaign, index) => ({
    id: "demo-ad-" + index, account_id: campaign.account_id, campaign_id: campaign.id,
    ad_group_id: "demo-ad-group-" + index, ad_id: String(500 + index), resource_name: "sample/ads/" + index,
    name: copy.headline + " · " + campaign.account_name, ad_type: "DEMAND_GEN_MULTI_ASSET_AD", status: campaign.status,
    policy_status: index === 2 ? "DISAPPROVED" : "APPROVED", final_urls: ["https://example.com/collection"],
    policy_summary: {}, disapproval_reasons: index === 2 ? [{ topic: "EDITORIAL", type: "PROHIBITED" }] : [],
    metrics: campaign.metrics, last_synced_at: sampleDate
  }));
  const problems: DemoRecord[] = [copy.issue, copy.verification].map((title, index) => ({
    id: "demo-problem-" + index, account_id: accounts[1].id, account_name: accounts[1].display_name,
    customer_id: accounts[1].customer_id, campaign_id: index === 0 ? campaigns[2].id : null, source: "DEMO",
    problem_type: index === 0 ? "POLICY" : "VERIFICATION", severity: "WARNING", title,
    description: index === 0 ? copy.issueBody : copy.verificationBody, google_code: null, request_id: null,
    state: "NEW", first_seen_at: sampleDate, last_seen_at: sampleDate, resolved_at: null, diagnostics: {}
  }));
  return {
    accounts, campaigns, ads, geos, tags, problems,
    views: [] as DemoRecord[], mappings: [] as DemoRecord[], actions: [] as DemoRecord[],
    events: [{ id: "demo-event-1", event_type: "SYNC_SUCCEEDED", source: "DEMO", occurred_at: sampleDate, details: {}, summary: copy.refreshed }] as DemoRecord[],
    rules: [{ id: "demo-rule-1", name: copy.rule, enabled: true, mode: "DRY_RUN", scope: {}, condition_logic: "AND",
      conditions: [{ field: "campaign.metrics.cost_micros", operator: "gte", value: 500_000_000 }], actions: [{ type: "NOTIFY" }],
      safeguards: {}, cooldown_minutes: 60, max_actions_per_run: 10, max_actions_per_day: 50, priority: 1,
      schedule: {}, max_budget_change_percent: null, live_confirmed_at: null, live_confirmed_by_id: null,
      last_evaluated_at: sampleDate, last_action_at: null, circuit_open_until: null, created_at: sampleDate, updated_at: sampleDate }] as DemoRecord[],
    runs: [{ id: "demo-sync-1", status: "SUCCEEDED", scope: "ALL", accounts_total: 3, accounts_completed: 3,
      successful_accounts: 3, failed_accounts: 0, actual_operations: 0, duration_ms: 120, request_ids: [],
      accounts_failed: 0, operations_used: 0, created_at: sampleDate, started_at: sampleDate, finished_at: sampleDate,
      completed_at: sampleDate, error_message: null, summary: { accounts: 3 } }] as DemoRecord[],
    alerts: problems.map(problem => ({ id: problem.id, severity: "WARNING", title: problem.title,
      message: problem.description, created_at: sampleDate, read_at: null })) as DemoRecord[],
    killSwitch: false,
  };
}
