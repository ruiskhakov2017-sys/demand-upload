import type { QueryParams } from "../api/client";
import { demoAccounts } from "../domain/demoAccounts";
import { demoCopy } from "../i18n/demoApi";
import { createDemoState, demoUser, metrics, sampleDate, type DemoRecord } from "./demoFixtures";

const storageKey = "axyro.demo.v1";
type DemoState = ReturnType<typeof createDemoState>;
let state: DemoState | undefined;

function getState(): DemoState {
  if (state) return state;
  try {
    const stored = sessionStorage.getItem(storageKey);
    if (stored) {
      const parsed = JSON.parse(stored);
      const collections = ["accounts", "campaigns", "ads", "geos", "tags", "problems", "views", "mappings", "actions", "events", "rules", "runs", "alerts"];
      if (collections.every(key => Array.isArray(parsed[key])) && parsed.accounts.length === demoAccounts.length) state = parsed;
    }
  } catch { /* Storage is optional for private browser sessions. */ }
  state ??= createDemoState();
  return state;
}

function saveState() {
  try { sessionStorage.setItem(storageKey, JSON.stringify(getState())); } catch { /* Keep the current page usable. */ }
}

export function resetDemoState() {
  state = createDemoState();
  saveState();
}

function now() { return new Date().toISOString(); }
function id() { return globalThis.crypto?.randomUUID?.() ?? "demo-" + Date.now() + "-" + Math.random().toString(36).slice(2); }
function fail(message = demoCopy().unsupported): never { throw new Error(message); }
function find(rows: DemoRecord[], itemId: string): DemoRecord {
  return rows.find(item => item.id === itemId) ?? fail(demoCopy().missing);
}
function addEvent(eventType: string, details: DemoRecord = {}, accountId?: string) {
  getState().events.unshift({ id: id(), event_type: eventType, source: "DEMO", occurred_at: now(), account_id: accountId, details, summary: demoCopy().saved });
}
function paginate(rows: DemoRecord[], query: URLSearchParams) {
  const offset = Math.max(0, Number(query.get("offset") || 0));
  const limit = Math.min(500, Math.max(1, Number(query.get("limit") || 50)));
  return { items: rows.slice(offset, offset + limit), total: rows.length };
}
function withPeriod(account: DemoRecord, query: URLSearchParams): DemoRecord {
  const index = getState().accounts.findIndex(item => item.id === account.id);
  const source = demoAccounts[index];
  const period = query.get("period") || "7d";
  let values: readonly [number, number] = source.values[7];
  let weight = 1;
  if (period === "30d") values = source.values[30];
  if (period === "today" || period === "yesterday") weight = 1 / 7;
  if (period === "3d") weight = 3 / 7;
  if (period === "custom") {
    const start = Date.parse(query.get("start_date") || "");
    const end = Date.parse(query.get("end_date") || "");
    const days = Math.max(0, Math.floor((end - start) / 86_400_000) + 1);
    values = source.values[30];
    weight = Number.isFinite(days) ? Math.min(30, days) / 30 : 1;
  }
  const activeProblems = getState().problems.filter(p => p.account_id === account.id && p.state !== "RESOLVED");
  const accountCampaigns = getState().campaigns.filter(c => c.account_id === account.id);
  return { ...account, has_problem: activeProblems.length > 0, active_problem_count: activeProblems.length,
    metrics: { ...metrics(...values, weight), budget_micros: accountCampaigns.reduce((sum,campaign) => sum + campaign.budget_micros, 0),
      active_campaigns: accountCampaigns.filter(c => c.status === "ENABLED").length,
      disapproved_ads: getState().ads.filter(ad => ad.account_id === account.id && ad.policy_status === "DISAPPROVED").length,
      policy_issues: activeProblems.filter(p => p.problem_type === "POLICY").length } };
}

const accountFields: Record<string, string> = {
  name: "display_name", local_name: "display_name", google_name: "descriptive_name", connection: "connection_name",
  mcc: "mcc_name", currency: "currency_code", note: "current_note", last_sync: "last_sync_success_at",
  cost: "cost_micros", budget: "budget_micros", cpc: "cpc_micros", cpa_registration: "cpa_registration_micros",
  cpa_deposit: "cpa_deposit_micros",
};
function valueOf(row: DemoRecord, field: string): string | number {
  const key = accountFields[field] || field;
  if (field === "geo") return row.geo?.display_name || "";
  return row[key] ?? row.metrics?.[key] ?? "";
}
function sortRows(rows: DemoRecord[], query: URLSearchParams) {
  const fields = (query.get("sort") || query.get("sort_fields") || "display_name").split(",");
  const directions = (query.get("direction") || query.get("sort_directions") || "asc").split(",");
  return [...rows].sort((a, b) => {
    for (let i = 0; i < fields.length; i++) {
      const left = valueOf(a, fields[i]), right = valueOf(b, fields[i]);
      const result = typeof left === "number" && typeof right === "number" ? left - right : String(left).localeCompare(String(right));
      if (result) return result * (directions[i] === "desc" ? -1 : 1);
    }
    return 0;
  });
}
function matchesQuick(row: DemoRecord, filter: string) {
  switch (filter) {
    case "working": return row.work_status === "WORKING";
    case "issues": return row.has_problem;
    case "verification": return ["REQUIRED", "PENDING_USER_ACTION", "PENDING_REVIEW"].includes(row.verification_status);
    case "paused": return row.work_status === "MANUAL_PAUSE";
    case "archive": return row.work_status === "ARCHIVED";
    default: return row.work_status !== "ARCHIVED";
  }
}
function filteredAccounts(query: URLSearchParams) {
  const search = (query.get("search") || "").toLowerCase();
  const filterFields: Record<string, string> = { connection_id: "connection_id", geo_id: "geo_id", mcc_id: "primary_mcc_id",
    currency: "currency_code", google_status: "google_status", work_status: "work_status", activity_status: "activity_status" };
  const bounds: Array<[string, string, (a:number,b:number)=>boolean]> = [
    ["cost_min", "cost_micros", (a,b)=>a>=b], ["cost_max", "cost_micros",(a,b)=>a<=b],
    ["registrations_min","registrations",(a,b)=>a>=b], ["deposits_eq","deposits",(a,b)=>a===b],
    ["cpa_min","cpa_registration_micros",(a,b)=>a>=b], ["cpa_max","cpa_registration_micros",(a,b)=>a<=b],
    ["active_campaigns_min","active_campaigns",(a,b)=>a>=b], ["disapproved_ads_min","disapproved_ads",(a,b)=>a>=b],
  ];
  const rows = getState().accounts.map(row => withPeriod(row, query)).filter(row => {
    if (!matchesQuick(row, query.get("quick_filter") || "all")) return false;
    if (search && ![row.display_name,row.customer_id,row.descriptive_name,row.current_note].some(value => String(value || "").toLowerCase().includes(search))) return false;
    if (Object.entries(filterFields).some(([param, field]) => query.get(param) && row[field] !== query.get(param))) return false;
    if (query.get("tag_id") && !row.tags.some((tag: DemoRecord) => tag.id === query.get("tag_id"))) return false;
    if (query.get("note") && !String(row.current_note || "").toLowerCase().includes(query.get("note")!.toLowerCase())) return false;
    if (query.has("has_problems") && row.has_problem !== (query.get("has_problems") === "true")) return false;
    if (query.get("problem_type") && !row.problem_types.includes(query.get("problem_type"))) return false;
    if (query.get("registrations_without_deposits") === "true" && !(row.metrics.registrations > 0 && row.metrics.deposits === 0)) return false;
    return bounds.every(([param, field, test]) => !query.has(param) || test(Number(row.metrics[field]), Number(query.get(param))));
  });
  return sortRows(rows, query);
}
function accountResponse(query: URLSearchParams) {
  const all = getState().accounts.map(row => withPeriod(row, query));
  const counts = Object.fromEntries(["all","working","issues","verification","paused","archive"].map(key => [key, all.filter(row => matchesQuick(row,key)).length]));
  const rows = filteredAccounts(query);
  const grouping = query.get("grouping") || "none";
  const groupRows = new Map<string, DemoRecord[]>();
  for (const row of rows) {
    const label = String(valueOf(row, grouping) || "—");
    groupRows.set(label, [...(groupRows.get(label) || []), row]);
  }
  const groups = [...groupRows].map(([label,items]) => ({ id: label, label, items, accounts: items.length,
    working_accounts: items.filter(row => row.work_status === "WORKING").length,
    problem_accounts: items.filter(row => row.has_problem).length, mixed_currencies: false,
    currency_totals: [{ currency_code: "USD", cost_micros: items.reduce((sum,row)=>sum + row.metrics.cost_micros,0) }] }));
  return { ...paginate(rows,query), counts, grouping, groups, period: { start: "2026-09-24", end: "2026-09-30" },
    sort: [], filters: Object.fromEntries(query) };
}

function mccRows() {
  return getState().accounts.map((account,index) => ({
    id: account.primary_mcc_id, connection_id: account.connection_id, connection_name: account.connection_name,
    customer_id: account.mcc_customer_id, parent_customer_id: null, descriptive_name: account.mcc_name,
    currency_code: "USD", time_zone: account.time_zone, is_root: true, hierarchy_level: 0, status: "ENABLED",
    geo: getState().geos[index], geo_assignment_status: "ASSIGNED", first_seen_at: sampleDate, last_seen_at: sampleDate,
    last_sync_success_at: sampleDate, detached_at: null
  }));
}
function connections() {
  return [{ id: "demo-connection", name: demoCopy().connection, login_customer_id: "1000000099", auth_type: "OAUTH_WEB",
    environment: "TEST", connection_mode: "SIMULATION", api_version: "v22", status: "CONNECTED",
    last_test_at: sampleDate, last_error: null, created_at: sampleDate, updated_at: sampleDate,
    service_account_email: null, oauth_connected: false, access_token_expires_at: null }];
}
function plainAccounts() {
  return getState().accounts.map(row => ({ ...row, can_manage_clients: false, account_type: "CLIENT",
    status: row.google_status, is_test_account: true, last_google_request_ids: [] }));
}
function collection(rows: DemoRecord[], query: URLSearchParams) {
  const filtered = rows.filter(row =>
    (!query.get("account_id") || row.account_id === query.get("account_id")) &&
    (!query.get("campaign_id") || row.campaign_id === query.get("campaign_id")) &&
    (!query.get("status_filter") || row.status === query.get("status_filter")) &&
    (!query.get("policy_status") || row.policy_status === query.get("policy_status")) &&
    (!query.get("asset_type") || row.asset_type === query.get("asset_type")) &&
    (!query.get("source") || row.source === query.get("source")) &&
    (!query.get("search") || String(row.name).toLowerCase().includes(query.get("search")!.toLowerCase())) &&
    (!query.get("cost_min_micros") || row.metrics?.cost_micros >= Number(query.get("cost_min_micros"))) &&
    (query.get("registrations_without_deposits") !== "true" || (row.metrics?.registrations > 0 && row.metrics?.deposits === 0))
  );
  return paginate(sortRows(filtered,query),query);
}
function refreshSample() {
  const run = { id: id(), status: "SUCCEEDED", scope: "ALL", accounts_total: 3, accounts_completed: 3,
    successful_accounts: 3, failed_accounts: 0, actual_operations: 0, duration_ms: 120, request_ids: [],
    accounts_failed: 0, operations_used: 0, created_at: now(), started_at: now(), finished_at: now(), completed_at: now(), summary: { accounts: 3 } };
  getState().runs.unshift(run);
  for (const account of getState().accounts) account.last_sync_success_at = run.finished_at;
  addEvent("SYNC_SUCCEEDED");
  return { id: run.id, sync_run_id: run.id, job_id: run.id, status: run.status };
}
function mutateCollection(rows: DemoRecord[], itemId: string | undefined, method: string, body: DemoRecord, defaults: DemoRecord = {}) {
  if (method === "POST" && !itemId) {
    const record = { ...defaults, ...body, id: id(), created_at: now(), updated_at: now() };
    rows.push(record);
    return record;
  }
  const row = find(rows,itemId || "");
  if (method === "DELETE") { rows.splice(rows.indexOf(row),1); return null; }
  if (method === "PATCH") { Object.assign(row,body,{updated_at:now()}); return row; }
  return fail();
}

function handle(path: string, method: string, body: DemoRecord, query: URLSearchParams): unknown {
  const data = getState();
  const parts = path.split("/").filter(Boolean);
  if (path === "/setup/status") return { setup_required: false, users_count: 1 };
  if (path === "/auth/me") return { user: demoUser, csrf_token: "demo-local" };
  if (path === "/auth/logout") return null;
  if (path === "/google-connections" && method === "GET") return connections();
  if (path === "/accounts" && method === "GET") return plainAccounts();
  if (path.startsWith("/accounts/sync/")) return { synced: data.accounts.length, accounts: plainAccounts() };
  if (path === "/control-center/summary") {
    const response = accountResponse(query);
    return { accounts: response.counts, campaigns: { total: data.campaigns.length, enabled: data.campaigns.filter(c=>c.status==="ENABLED").length },
      problems: { active: data.problems.filter(p=>p.state!=="RESOLVED").length },
      metrics: { by_currency: [{currency_code:"USD",cost_micros:response.items.reduce((sum,row)=>sum+row.metrics.cost_micros,0)}],mixed_currencies:false } };
  }
  if (path === "/control-center/accounts" && method === "GET") return accountResponse(query);
  if (path === "/control-center/accounts/bulk-work-status" && method === "POST") {
    const rows = data.accounts.filter(row => body.account_ids?.includes(row.id));
    if (!["PREPARATION","READY","WORKING","MANUAL_PAUSE","PROBLEM","APPEAL","ARCHIVED","DO_NOT_USE"].includes(body.work_status)) fail(demoCopy().invalid);
    rows.forEach(row=>{ const previous = row.work_status; row.work_status=body.work_status; addEvent("WORK_STATUS_CHANGED",{previous,current:body.work_status},row.id); });
    return { updated: rows.length, work_status: body.work_status };
  }
  if (parts[0] === "control-center" && parts[1] === "accounts" && parts[2]) {
    const account = find(data.accounts,parts[2]);
    if (parts[3] === "tags") {
      const tag = find(data.tags,parts[4]);
      account.tags = account.tags.filter((item:DemoRecord)=>item.id!==tag.id);
      if (method === "POST") account.tags.push(tag);
      addEvent(method === "POST" ? "TAG_ADDED" : "TAG_REMOVED",{tag_name:tag.name},account.id);
      return tag;
    }
    if (parts[3] === "access-paths") return [{id:"path-"+account.id,customer_path:[account.mcc_customer_id,account.customer_id],is_primary:true,is_active:true}];
    if (parts[3] === "manager-history") return [];
    if (method === "PATCH") {
      const previous = account.work_status;
      const allowed = ["local_name","current_note","pinned_note","is_pinned","work_status","is_hidden","geo_override_id"];
      for (const field of allowed) if (field in body) account[field]=body[field];
      account.display_name=account.local_name||account.descriptive_name;
      if ("current_note" in body) { account.note_updated_at=now(); addEvent("NOTE_CHANGED",{},account.id); }
      if ("work_status" in body) addEvent("WORK_STATUS_CHANGED",{previous,current:body.work_status},account.id);
      if ("geo_override_id" in body) { account.geo=data.geos.find(geo=>geo.id===body.geo_override_id)||data.geos[data.accounts.indexOf(account)]; account.geo_id=account.geo.id; }
      return withPeriod(account,query);
    }
    if (method !== "GET") fail();
    const row = withPeriod(account,query);
    return { account: row, campaigns: data.campaigns.filter(c=>c.account_id===account.id),
      ads_assets: data.ads.filter(ad=>ad.account_id===account.id).map(ad=>({...ad,approval_status:ad.policy_status})),
      problems:data.problems.filter(p=>p.account_id===account.id), history:data.events.filter(event=>event.account_id===account.id),
      metric_history: Array.from({length:7},(_,index)=>({date:"2026-09-"+(24+index),cost_micros:Math.round(row.metrics.cost_micros/7),conversions:Math.round(row.metrics.conversions/7)})) };
  }
  if (parts[0] === "control-center" && parts[1] === "tags") {
    return method === "GET" ? data.tags : mutateCollection(data.tags,parts[2],method,body);
  }
  if (parts[0] === "control-center" && parts[1] === "saved-views") {
    if (method === "GET") return data.views;
    if (parts[3] === "duplicate") return mutateCollection(data.views,undefined,"POST",{...find(data.views,parts[2]),name:find(data.views,parts[2]).name+" (copy)",is_default:false});
    if (body.is_default) data.views.forEach(view=>view.is_default=false);
    return mutateCollection(data.views,parts[2],method,body,{owner_user_id:"demo-user",is_owner:true,entity_level:"ACCOUNT",config:{},is_default:false,is_shared:false,description:null,source_view_id:null});
  }
  if (parts[0] === "control-center" && parts[1] === "geos") {
    return method==="GET" ? data.geos : mutateCollection(data.geos,parts[2],method,body,{is_active:true});
  }
  if (path === "/control-center/mcc") return mccRows();
  if (parts[1] === "mcc" && parts[3] === "geo") {
    const account = data.accounts.find(row=>row.primary_mcc_id===parts[2]) ?? fail(demoCopy().missing);
    account.geo=data.geos.find(geo=>geo.id===body.geo_id)||null; account.geo_id=body.geo_id;
    return mccRows().find(row=>row.id===parts[2]);
  }
  if (path === "/control-center/hierarchy") return { items:mccRows(), accounts:plainAccounts() };
  if (parts[1] === "conversion-action-mappings") return method==="GET" ? data.mappings : mutateCollection(data.mappings,parts[2],method,body);
  if (path === "/control-center/conversion-actions/catalog") return { items:[{resource_name:"sample/registration",name:"Registration",category:"SIGNUP",status:"ENABLED"}], conversion_actions:[{resource_name:"sample/registration",name:"Registration",category:"SIGNUP",status:"ENABLED"}] };
  if (path === "/control-center/campaigns") return collection(data.campaigns,query);
  if (path === "/control-center/ads") return collection(data.ads,query);
  if (path === "/control-center/ad-groups") return collection(data.campaigns.map((c,index)=>({id:"demo-ad-group-"+index,account_id:c.account_id,campaign_id:c.id,name:c.name,status:c.status,metrics:c.metrics,policy_issues:[],last_synced_at:sampleDate})),query);
  if (path === "/control-center/assets") return collection(data.ads.map((ad,index)=>({id:"demo-asset-"+index,account_id:ad.account_id,resource_name:"sample/assets/"+index,asset_id:String(800+index),name:ad.name,asset_type:"TEXT",source:"ADVERTISER",status:"ENABLED",image_url:null,image_width:null,image_height:null,youtube_video_id:null,youtube_processing_status:null,processing_note:null,last_synced_at:sampleDate})),query);
  if (path === "/control-center/asset-links") return [];
  if (path === "/control-center/moderation") return { ...collection(data.ads.filter(ad=>query.get("only_issues")!=="true"||ad.policy_status!=="APPROVED"),query),data_note:demoCopy().sample };
  if (path === "/control-center/verification") return data.accounts.filter(row=>!query.get("status_filter")||row.verification_status===query.get("status_filter")).map(row=>({account_id:row.id,account_name:row.display_name,customer_id:row.customer_id,status:row.verification_status,deadline:row.verification_deadline,action_url:null,checked_at:sampleDate}));
  if (parts[1] === "problems") {
    if (method==="PATCH") { const item=find(data.problems,parts[2]); item.state=body.state; item.resolved_at=body.state==="RESOLVED"?now():null; return item; }
    const selectedState = query.get("state_filter") || query.get("state");
    return data.problems.filter(row=>(!selectedState||row.state===selectedState)&&(!query.get("account_id")||row.account_id===query.get("account_id"))&&(!query.get("severity")||row.severity===query.get("severity")));
  }
  if (path === "/control-center/history" || path === "/control-center/changes") {
    const rows = data.events.filter(row=>(!query.get("event_type")||row.event_type===query.get("event_type"))&&(!query.get("account_id")||row.account_id===query.get("account_id")));
    return path.endsWith("/changes")?{...paginate(rows,query),history_depth:demoCopy().sample}:rows;
  }
  if (path === "/control-center/sync-runs") return data.runs;
  if (path === "/control-center/sync/estimate") return {accounts:data.accounts.length,estimated_operations:0,estimate_token:"demo",quota:{used_today:0,internal_remaining:0,manual_reserve:0},warning:demoCopy().sample};
  if (path === "/control-center/sync" && method === "POST") return refreshSample();
  if (parts[1] === "sync" && parts[2]) return find(data.runs,parts[2]);
  if (parts[1] === "actions") return actionRequest(parts,method,body);
  if (parts[1] === "rules") return ruleRequest(parts,method,body);
  if (path === "/audit") return data.events.map(event=>({id:event.id,created_at:event.occurred_at,action:event.event_type,entity_type:"Demo",entity_id:event.account_id||"",summary:event.details}));
  if (path === "/operations/statistics") return data.accounts.map(row=>({id:row.id,customer_id:row.customer_id,snapshot_date:"2026-09-30",metrics:row.metrics}));
  if (path === "/operations/moderation") return data.ads.map(ad=>({id:ad.id,customer_id:find(data.accounts,ad.account_id).customer_id,resource_name:ad.resource_name,approval_status:ad.policy_status,policy_topics:ad.disapproval_reasons,checked_at:sampleDate}));
  if (path === "/operations/alerts") return data.alerts;
  if (parts[0]==="operations" && parts[1]==="alerts" && method==="PATCH") { const row=find(data.alerts,parts[2]); row.read_at=body.read?now():null; return row; }
  if (path==="/operations/finance" && method==="GET") return [{id:"demo-finance",name:demoCopy().finance,provider:"DEMO",status:"CONNECTED",latest_snapshot:{balance:41590,currency:"USD",cards_active:3,cards_total:3},updated_at:sampleDate}];
  if (parts[1]==="finance" && parts[2]==="google-billing") {
    const account=find(data.accounts,parts[3]);return {available:true,currency_code:"USD",request_ids:[],
      billing_setups:[{resource_name:"demo-billing",status:"APPROVED",payments_account_name:account.display_name,payments_profile_name:demoCopy().sample,start_date_time:"2026-09-01",end_date_time:"2026-09-30"}],
      account_budgets:[{resource_name:"demo-budget",status:"APPROVED",approved_spending_limit_type:"FINITE",approved_spending_limit_micros:40_000_000_000,amount_served_micros:account.metrics.cost_micros,purchase_order_number:"DEMO-2026-09"}] };
  }
  if (parts[0]==="operations" && (path.endsWith("/sync")||parts[2]==="sync")) return refreshSample();
  if (path === "/dashboard/summary") return {refreshed_at:now(),connections:{total:1,connected:1},accounts:{total:3},uploads:{total:0,draft:0},jobs:{active:0,failed:0},alerts:{unread:data.alerts.filter(row=>!row.read_at).length}};
  if (path === "/jobs") return data.runs.map(run=>({id:run.id,type:"DEMO_REFRESH",status:"SUCCEEDED",progress_current:3,progress_total:3,error_message:null,created_at:run.created_at,updated_at:run.finished_at}));
  if (["/uploads","/templates","/media","/deployment-plans","/schedules","/launch-groups"].includes(path) && method==="GET") return [];
  return fail();
}

function actionRequest(parts:string[],method:string,body:DemoRecord): unknown {
  const data=getState();
  if (parts[2]==="preview" && method==="POST") {
    if (!["PAUSE","ENABLE","SET_BUDGET"].includes(body.action_type)) fail(demoCopy().invalid);
    if (body.action_type==="SET_BUDGET" && !(Number(body.amount_micros)>0)) fail(demoCopy().invalid);
    const campaigns=data.campaigns.filter(row=>body.campaign_ids?.includes(row.id));
    if (!campaigns.length) fail(demoCopy().invalid);
    const field=body.action_type==="SET_BUDGET"?"budget_micros":"status";
    const after=body.action_type==="SET_BUDGET"?Number(body.amount_micros):body.action_type==="PAUSE"?"PAUSED":"ENABLED";
    const record={id:id(),status:"PREVIEW",execution_mode:"SIMULATION",confirmation_token:id(),validation:{ok:true},second_approval_required:false,
      preview:{changes:campaigns.map(row=>({campaign_id:row.id,field,before:row[field],after})),warnings:[]},result:{},created_at:now()};
    data.actions.push(record);return record;
  }
  const action=find(data.actions,parts[2]);
  if (parts[3]==="confirm" && method==="POST") {
    if(body.confirmation_token!==action.confirmation_token) fail(demoCopy().invalid);
    if(action.status==="SUCCEEDED")return action;
    action.preview.changes.forEach((change:DemoRecord)=>{const campaign=find(data.campaigns,change.campaign_id);campaign[change.field]=change.after;campaign.last_change_at=now();});
    action.status="SUCCEEDED";action.completed_at=now();action.result={simulated:true,changes:action.preview.changes};
    addEvent("MANUAL_ACTION_SIMULATED",{changes:action.preview.changes.length});return action;
  }
  if(method==="GET")return action;
  return fail();
}

function ruleRequest(parts:string[],method:string,body:DemoRecord): unknown {
  const data=getState();
  if(parts[2]==="kill-switch"){if(method==="PATCH")data.killSwitch=Boolean(body.active);return {active:data.killSwitch};}
  if(method==="GET")return data.rules;
  if(parts[3]==="live-mode") fail();
  if(parts[3]==="evaluate"){
    const rule=find(data.rules,parts[2]);
    const matches=data.campaigns.filter(campaign=>rule.conditions.every((condition:DemoRecord)=>{
      const field=String(condition.field).replace("campaign.","");
      const actual=field.split(".").reduce((value:any,key:string)=>value?.[key],campaign);
      const expected=condition.value;
      if(condition.operator==="gte")return actual>=Number(expected);
      if(condition.operator==="lte")return actual<=Number(expected);
      if(condition.operator==="ne")return String(actual)!==String(expected);
      return String(actual)===String(expected);
    }));
    rule.last_evaluated_at=now();return {evaluated:data.campaigns.length,matched:matches.length,actions:[],mode:"DRY_RUN"};
  }
  return mutateCollection(data.rules,parts[2],method,{...body,mode:"DRY_RUN"},{enabled:true,scope:{},conditions:[],actions:[],safeguards:{},priority:1,cooldown_minutes:60,max_actions_per_run:10,max_actions_per_day:50,schedule:{},condition_logic:"AND",last_evaluated_at:null});
}

/** The demo never delegates requests to the live API. */
export async function demoRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url=new URL(path,"https://demo.invalid");
  const method=(init.method || "GET").toUpperCase();
  const body=typeof init.body==="string" ? JSON.parse(init.body) : {};
  const result=handle(url.pathname,method,body,url.searchParams);
  if(method!=="GET")saveState();
  return structuredClone(result) as T;
}

let exportUrl: string | undefined;
export function demoExportUrl(params: QueryParams): string {
  const query=new URLSearchParams();
  Object.entries(params).forEach(([key,value])=>{if(value!==undefined&&value!==null)query.set(key,String(value));});
  const rows=filteredAccounts(query);
  const lines: unknown[][]=[demoCopy().export,...rows.map(row=>[row.display_name,row.customer_id,"USD",row.metrics.cost_micros/1_000_000,row.metrics.conversions,row.metrics.cost_per_conversion_micros/1_000_000,row.work_status])];
  const csv="\uFEFF"+lines.map(line=>line.map(value=>'"'+String(value).replace(/"/g,'""')+'"').join(",")).join("\r\n");
  if(exportUrl) URL.revokeObjectURL(exportUrl);
  exportUrl=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  return exportUrl;
}
