export function isDemoPath(path = globalThis.location?.pathname ?? "") {
  return path === "/demo" || path.startsWith("/demo/");
}
