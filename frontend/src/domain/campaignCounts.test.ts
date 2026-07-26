import { describe, expect, it } from "vitest";

import { applyCampaignCount, normalizeCampaignCount, QUICK_CAMPAIGN_COUNTS } from "./campaignCounts";

describe("campaign copy counts", () => {
  const accounts = [
    { customer_id: "1", campaigns_count: 1 },
    { customer_id: "2", campaigns_count: 2 },
    { customer_id: "3", campaigns_count: 3 }
  ];

  it("offers the required quick values", () => {
    expect(QUICK_CAMPAIGN_COUNTS).toEqual([1, 3, 5, 7, 10]);
  });

  it("applies an arbitrary count only to selected accounts", () => {
    expect(applyCampaignCount(accounts, ["1", "3"], 17).map((item) => item.campaigns_count)).toEqual([17, 2, 17]);
  });

  it("applies one count to every selected advertising account", () => {
    expect(applyCampaignCount(accounts, null, 7).map((item) => item.campaigns_count)).toEqual([7, 7, 7]);
  });

  it("keeps arbitrary values inside the supported range", () => {
    expect(normalizeCampaignCount(0)).toBe(1);
    expect(normalizeCampaignCount(42.9)).toBe(42);
    expect(normalizeCampaignCount(999)).toBe(500);
  });
});
