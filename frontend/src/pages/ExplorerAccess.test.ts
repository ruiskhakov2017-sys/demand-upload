import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { en } from "../i18n/en";
import { ru } from "../i18n/ru";

const here = dirname(fileURLToPath(import.meta.url));

describe("Explorer production access presentation", () => {
  it("shows the real Explorer level and limits without calling it Basic", () => {
    expect(en["googleAccess.summary"]).toContain("{level}");
    expect(en["googleAccess.limits"]).toContain("{production}");
    expect(ru["googleAccess.basicPending"]).toContain("Brand Verification");
    expect(en["googleMode.productionLabel"]).toContain("Explorer");
    expect(en["googleMode.productionLabel"]).not.toContain("Basic");
  });

  it("does not disable ordinary production operations in the frontend", () => {
    const sources = [
      "UploadWizardPage.tsx",
      "ControlCenterPage.tsx",
      "MediaPage.tsx"
    ].map((name) => readFileSync(resolve(here, name), "utf8"));
    const combined = sources.join("\n");

    expect(combined).not.toContain('<MenuItem value="PRODUCTION" disabled>');
    expect(combined).not.toContain('props.form.execution_mode === "PRODUCTION"} onClick={props.onConfirm}');
    expect(combined).not.toContain("productionMutateBlocked");
    expect(combined).not.toContain("validateProductionBlocked");
  });
});
