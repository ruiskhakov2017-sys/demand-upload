import { describe, expect, it } from "vitest";

import {
  buildBatchPayload,
  createEmptyForm,
  executionModeDescription,
  executionModeLabel
} from "./UploadWizardPage";
import { t } from "../i18n";

describe("Google Ads execution mode presentation", () => {
  it("keeps simulation, Google Test and production visibly distinct", () => {
    const labels = [
      executionModeLabel("SIMULATION"),
      executionModeLabel("GOOGLE_TEST"),
      executionModeLabel("PRODUCTION")
    ];

    expect(new Set(labels).size).toBe(3);
    expect(labels[1]).toContain("Google Test");
    expect(executionModeDescription("GOOGLE_TEST")).toBe(
      t("googleMode.testDescription")
    );
    expect(executionModeDescription("PRODUCTION")).toBe(
      t("googleMode.productionDescription")
    );
    expect(executionModeDescription("SIMULATION")).toBe(
      t("googleMode.simulationDescription")
    );
  });

  it("keeps advanced Demand Gen targeting, URL and logo settings in the batch payload", () => {
    const form = createEmptyForm();
    form.mobile_final_url = "https://m.example.com/offer";
    form.tracking_template = "https://tracker.example/click?url={lpurl}";
    form.final_url_suffix = "utm_source=dgu";
    form.display_path = "offers/today";
    form.custom_parameters = "source=wizard\nvariant=one";
    form.user_interest_resource_names = "customers/1234567890/userInterests/42";
    form.life_event_ids = "1001";
    form.parental_statuses = ["PARENT"];
    form.income_ranges = ["INCOME_RANGE_90_UP"];
    form.carousel_card_headlines = "First card\nSecond card";
    form.media_ids = ["logo", "landscape"];
    form.logo_media_id = "logo";

    const payload = buildBatchPayload(form, [{
      id: "account-id",
      customer_id: "1234567890",
      account_name: "Account",
      currency_code: "USD",
      time_zone: "UTC",
      overrides: {}
    }]) as any;

    expect(payload.template_defaults.url).toMatchObject({
      mobile_final_url: "https://m.example.com/offer",
      tracking_template: "https://tracker.example/click?url={lpurl}",
      final_url_suffix: "utm_source=dgu",
      display_path: "offers/today",
      custom_parameters: [
        { key: "source", value: "wizard" },
        { key: "variant", value: "one" }
      ]
    });
    expect(payload.template_defaults.targeting).toMatchObject({
      user_interest_resource_names: ["customers/1234567890/userInterests/42"],
      life_event_ids: ["1001"],
      demographics: {
        age_ranges: form.age_ranges,
        genders: form.genders,
        parental_statuses: ["PARENT"],
        income_ranges: ["INCOME_RANGE_90_UP"]
      }
    });
    expect(payload.template_defaults.texts.carousel_card_headlines).toEqual([
      "First card",
      "Second card"
    ]);
    expect(payload.creative.logo_media_id).toBe("logo");
  });
});
