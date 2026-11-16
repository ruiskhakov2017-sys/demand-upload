import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { demoRequest, resetDemoState } from "./demoApi";
import { isDemoPath } from "./isDemoPath";

describe("public demo isolation and sample data", () => {
  beforeEach(() => {
    const stored = new Map<string, string>();
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => stored.get(key) ?? null,
      setItem: (key: string, value: string) => stored.set(key, value)
    });
    vi.stubGlobal("location", { pathname: "/demo/control-center" });
    resetDemoState();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("serves normal API entry points without fetching live data", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    expect((await api.me()).user.username).toBe("Demo");
    expect((await api.controlCenterAccounts({period: "30d"})).total).toBe(3);
    await expect(api.createConnection({name: "sample"})).rejects.toThrow();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("uses the authenticated API on ordinary routes", async () => {
    vi.stubGlobal("location", {pathname: "/control-center"});
    const fetch = vi.fn().mockResolvedValue({ok:true, status:200, json:async () => ({user:{username:"Owner"}})});
    vi.stubGlobal("fetch",fetch);
    expect((await api.me()).user.username).toBe("Owner");
    expect(fetch).toHaveBeenCalledWith("/api/auth/me",expect.objectContaining({credentials:"include"}));
    expect(isDemoPath("/demonstration")).toBe(false);
  });

  it("keeps periods, totals, filters and sorting consistent", async () => {
    const month = await api.controlCenterAccounts({period:"30d"});
    expect(month.items.reduce((sum,row)=>sum + (row.metrics.cost_micros ?? 0),0)).toBe(58410e6);
    const week = await api.controlCenterAccounts({period:"7d", sort:"cost", direction:"desc"});
    expect(week.items.reduce((sum,row)=>sum + (row.metrics.cost_micros ?? 0),0)).toBe(14740e6);
    expect(week.items[0].display_name).toBe("North America");
    expect((await api.controlCenterAccounts({search:"DACH"})).total).toBe(1);
    const summary = await api.controlCenterSummary({period:"30d"});
    expect(summary.metrics.by_currency[0].cost_micros).toBe(58410e6);
  });

  it("keeps sample edits local and resets them", async () => {
    await api.updateControlCenterAccount("demo-account-1",{current_note:"Review next week",work_status:"MANUAL_PAUSE"});
    const account = await api.controlCenterAccount("demo-account-1");
    expect(account.account.current_note).toBe("Review next week");
    expect((await api.controlCenterAccounts({quick_filter:"paused"})).total).toBe(2);
    resetDemoState();
    expect((await api.controlCenterAccounts({quick_filter:"paused"})).total).toBe(1);
  });

  it("applies confirmed sample actions once when retried", async () => {
    const action = await api.previewControlCenterAction({action_type:"PAUSE",campaign_ids:["demo-campaign-0-0"]});
    await api.confirmControlCenterAction(action.id,action.confirmation_token);
    const result = await api.confirmControlCenterAction(action.id,action.confirmation_token);
    expect(result.status).toBe("SUCCEEDED");
    const campaigns = await api.controlCenterCampaigns({});
    expect(campaigns.items.find(row=>row.id==="demo-campaign-0-0")?.status).toBe("PAUSED");
    const events = await demoRequest<Array<{event_type:string}>>("/control-center/history");
    expect(events.filter(event=>event.event_type==="MANUAL_ACTION_SIMULATED")).toHaveLength(1);
  });
});
