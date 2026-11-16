const basePath = import.meta.env.BASE_URL.replace(/\/$/, "");

export const isPortfolioBuild = basePath === "/portfolio";

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
