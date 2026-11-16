import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});

async function pathsAt(url: string, base = "/portfolio/") {
  vi.resetModules();
  vi.stubEnv("BASE_URL", base);
  vi.stubGlobal("window", { location: new URL(url) });
  return import("./paths");
}

describe("portfolio design comparison", () => {
  it.each(["previous", "new"])("keeps %s in navigation and leaves API URLs unchanged", async design => {
    const paths = await pathsAt(`https://axyro.tech/portfolio/control-center?design=${design}`);
    expect(paths.isPortfolioBuild).toBe(true);
    expect(paths.isPortfolioRefinement).toBe(design === "new");
    expect(paths.appNavigationPath("/statistics")).toBe(`/portfolio/statistics?design=${design}`);
    expect(paths.appNavigationPath("/login")).toBe(`/portfolio/login?design=${design}`);
    expect(paths.appNavigationPath("/audit?limit=20#entries")).toBe(`/portfolio/audit?limit=20&design=${design}#entries`);
    expect(paths.appPath("/api/auth/me")).toBe("/portfolio/api/auth/me");
    expect(paths.appPath("/api/control-center/export?format=xlsx")).toBe("/portfolio/api/control-center/export?format=xlsx");
  });

  it("opens the opposite design in the same section", async () => {
    const paths = await pathsAt("https://axyro.tech/portfolio/finance?design=previous");
    expect(paths.portfolioDesignPath("new")).toBe("/portfolio/finance?design=new");
  });

  it("defaults to the new design without changing ordinary URLs", async () => {
    const paths = await pathsAt("https://axyro.tech/portfolio/control-center");
    expect(paths.isPortfolioRefinement).toBe(true);
    expect(paths.appNavigationPath("/statistics")).toBe("/portfolio/statistics");
  });

  it("does not change production routes when a design parameter is present", async () => {
    const paths = await pathsAt("https://axyro.tech/control-center?design=previous", "/");
    expect(paths.isPortfolioBuild).toBe(false);
    expect(paths.isPortfolioRefinement).toBe(false);
    expect(paths.appNavigationPath("/statistics")).toBe("/statistics");
  });
});
