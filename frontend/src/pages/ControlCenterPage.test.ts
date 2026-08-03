import { describe, expect, it } from "vitest";

import {
  COLUMNS,
  QUICK_FILTERS,
  formatCustomerId,
  isProblematicGoogleStatus,
  localizedEventSummary,
  localizedSavedViewName,
  money,
  normalizeColumnState
} from "./ControlCenterPage";
import { controlCenterDictionaries } from "../i18n/controlCenter";

describe("Control Center presentation contract", () => {
  it("keeps an actual zero distinct from missing metrics", () => {
    expect(money(null, "USD")).toBe("—");
    expect(money(undefined, "USD")).toBe("—");
    expect(money(0, "USD")).not.toBe("—");
  });

  it("normalizes persisted column order, visibility and pins", () => {
    const state = normalizeColumnState({
      order: ["note", "local_name", "unknown"],
      visible: ["note", "local_name"],
      pinned: ["local_name", "unknown"]
    });

    expect(state.order.slice(0, 2)).toEqual(["note", "local_name"]);
    expect(state.order).not.toContain("unknown");
    expect(state.visible).toEqual(["note", "local_name"]);
    expect(state.pinned).toEqual(["local_name"]);
  });

  it("formats Google Ads customer IDs for display only", () => {
    expect(formatCustomerId("5589335362")).toBe("558-933-5362");
    expect(formatCustomerId("123")).toBe("123");
  });

  it("does not mark a closed Google Test account as a critical problem", () => {
    const account = {
      google_status: "CLOSED",
      google_status_label: "Closed Google Test account",
      is_test_account: true,
      sync_error: null
    };

    expect(isProblematicGoogleStatus(account)).toBe(false);
    expect(
      isProblematicGoogleStatus({
        ...account,
        is_test_account: false
      })
    ).toBe(true);
    expect(
      isProblematicGoogleStatus({
        ...account,
        google_status: "SUSPENDED"
      })
    ).toBe(true);
  });

  it("has a complete English Control Center dictionary without Russian fallback", () => {
    const russianKeys = Object.keys(controlCenterDictionaries.ru).sort();
    const englishKeys = Object.keys(controlCenterDictionaries.en).sort();

    expect(englishKeys).toEqual(russianKeys);
    for (const key of englishKeys) {
      const value = controlCenterDictionaries.en[key];
      expect(value).not.toBe(key);
      expect(value).not.toMatch(/[\u0410-\u044f\u0401\u0451]/);
    }
  });

  it("resolves module-level option and column labels at render time", () => {
    expect(Object.getOwnPropertyDescriptor(QUICK_FILTERS[0], "label")?.get).toBeTypeOf("function");
    expect(Object.getOwnPropertyDescriptor(COLUMNS[0], "label")?.get).toBeTypeOf("function");
  });

  it("renders known persisted Control Center text through the locale dictionary", () => {
    const savedViewName = controlCenterDictionaries.ru["controlCenter.full.188"];
    const syncSummary = controlCenterDictionaries.ru["controlCenter.full.174"];

    expect(localizedSavedViewName(savedViewName)).toBe(savedViewName);
    expect(localizedSavedViewName("My custom view")).toBe("My custom view");
    expect(
      localizedEventSummary({
        event_type: "SYNC_SUCCEEDED",
        summary: syncSummary,
        details: {}
      })
    ).toBe(syncSummary);
  });
});
