const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");

export const isPortfolioBuild = basePath === "/portfolio";
export const isShowcaseBuild = basePath === "/showcase";
export const portfolioDesign = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("design");
export const isPortfolioRefinement = isPortfolioBuild && portfolioDesign === "new";

/** Keep design review links in this tab, without changing API or export URLs. */
export function appNavigationPath(path: string) {
  const target = appPath(path);
  if (!isPortfolioBuild || (portfolioDesign !== "previous" && portfolioDesign !== "new")) return target;
  const url = new URL(target, window.location.origin);
  url.searchParams.set("design", portfolioDesign);
  return `${url.pathname}${url.search}${url.hash}`;
}

export function portfolioDesignPath(design: "previous" | "new") {
  const url = new URL(window.location.href);
  url.searchParams.set("design", design);
  return `${url.pathname}${url.search}${url.hash}`;
}

export function appPath(path: string) {
  return `${basePath}${path}`;
}

export function appRoute(pathname: string) {
  if (pathname === basePath) return "/";
  return pathname.startsWith(`${basePath}/`) ? pathname.slice(basePath.length) : pathname;
}

export function appStorageKey(key: string) {
  return basePath ? `${basePath}:${key}` : key;
}
