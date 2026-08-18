import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { PRIVACY_COPY, TERMS_COPY } from "./LegalPage";
import { PUBLIC_COPY } from "./PublicSitePage";

const testDirectory = dirname(fileURLToPath(import.meta.url));

describe("Axyro Analytics public positioning", () => {
  it("keeps analytics primary and campaign deployment secondary", () => {
    expect(PUBLIC_COPY.en.productParagraphs[0]).toContain("independent Google Ads analytics and operations software project");
    expect(PUBLIC_COPY.en.productParagraphs[2]).toContain("primary purpose");
    expect(PUBLIC_COPY.en.deploymentEyebrow).toBe("Secondary module");
    expect(PUBLIC_COPY.en.deploymentTitle).toBe("Validated campaign deployment");
  });

  it("identifies the individual operator and sole-user access consistently", () => {
    const publicText = JSON.stringify(PUBLIC_COPY);
    const legalText = JSON.stringify({ privacy: PRIVACY_COPY, terms: TERMS_COPY });

    expect(publicText).toContain("Iskhakov Ruslan");
    expect(publicText).toContain("not a registered company");
    expect(publicText).toContain("No employee, contractor, client, or member of the public has access");
    expect(legalText).toContain("Iskhakov Ruslan");
    expect(legalText).toContain("not a registered company or separate legal entity");
    expect(PRIVACY_COPY.ru.sections[0].paragraphs?.[0]).toContain("Iskhakov Ruslan");
  });

  it("describes write operations and their safeguards truthfully", () => {
    const publicText = JSON.stringify(PUBLIC_COPY.en);
    expect(publicText).toContain("create validated Demand Gen campaigns");
    expect(publicText).toContain("pause or enable selected campaigns");
    expect(publicText).toContain("update budgets");
    expect(publicText).toContain("explicit user confirmation");
    expect(publicText).toContain("PAUSED");
    expect(publicText).toContain("AuditLog");
    expect(publicText).toContain("Production write operations are currently disabled");
  });

  it("does not use prohibited mass-uploader positioning", () => {
    const publicText = JSON.stringify(PUBLIC_COPY).toLowerCase();
    expect(publicText).not.toContain("bulk uploader");
    expect(publicText).not.toContain("mass campaign launcher");
    expect(publicText).not.toContain("\u0430\u0432\u0442\u043e\u0437\u0430\u043b\u0438\u0432\u0430\u0442\u043e\u0440");
  });

  it("publishes bilingual privacy and terms documents with the support contact", () => {
    const legalText = JSON.stringify({ privacy: PRIVACY_COPY, terms: TERMS_COPY });
    expect(legalText).toContain("support@axyro.tech");
    expect(legalText).toContain("Google API Services User Data Policy");
    expect(legalText).toContain("14-day rotation");
    expect(legalText).toContain("14-\u0434\u043d\u0435\u0432\u043d\u043e\u0439 \u0440\u043e\u0442\u0430\u0446\u0438\u0438");
  });

  it("keeps the public Basic Access PDF identical to the reviewed document", () => {
    const reviewedPdf = readFileSync(resolve(testDirectory, "../../../docs/google-ads-api-basic-access-application.pdf"));
    const publicPdf = readFileSync(resolve(testDirectory, "../../public/docs/google-ads-api-basic-access-application.pdf"));

    expect(publicPdf).toEqual(reviewedPdf);
  });
});
