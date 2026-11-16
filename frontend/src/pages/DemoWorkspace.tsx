import AssessmentOutlined from "@mui/icons-material/AssessmentOutlined";
import AccountBalanceWalletOutlined from "@mui/icons-material/AccountBalanceWalletOutlined";
import ArrowBackOutlined from "@mui/icons-material/ArrowBackOutlined";
import FactCheckOutlined from "@mui/icons-material/FactCheckOutlined";
import HistoryOutlined from "@mui/icons-material/HistoryOutlined";
import MenuOutlined from "@mui/icons-material/MenuOutlined";
import MonitorHeartOutlined from "@mui/icons-material/MonitorHeartOutlined";
import NotificationsNoneOutlined from "@mui/icons-material/NotificationsNoneOutlined";
import RestartAltOutlined from "@mui/icons-material/RestartAltOutlined";
import { Drawer, LinearProgress, ThemeProvider } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useState, type MouseEvent } from "react";
import { createAppTheme } from "../app/theme";
import { resetDemoState } from "../demo/demoApi";
import { useLocale } from "../i18n";
import { DEMO_WORKSPACE_COPY } from "../i18n/demoWorkspace";
import "./DemoWorkspace.css";

const ControlCenterPage = lazy(() => import("./ControlCenterPage").then(module => ({ default: module.ControlCenterPage })));
const StatisticsPage = lazy(() => import("./OperationsPages").then(module => ({ default: module.StatisticsPage })));
const FinancePage = lazy(() => import("./OperationsPages").then(module => ({ default: module.FinancePage })));
const AlertsPage = lazy(() => import("./OperationsPages").then(module => ({ default: module.AlertsPage })));
const ModerationPage = lazy(() => import("./OperationsPages").then(module => ({ default: module.ModerationPage })));
const AuditPage = lazy(() => import("./AuditPage").then(module => ({ default: module.AuditPage })));

const sections = [
  { path: "control-center", icon: MonitorHeartOutlined, page: ControlCenterPage },
  { path: "statistics", icon: AssessmentOutlined, page: StatisticsPage },
  { path: "finance", icon: AccountBalanceWalletOutlined, page: FinancePage },
  { path: "alerts", icon: NotificationsNoneOutlined, page: AlertsPage },
  { path: "moderation", icon: FactCheckOutlined, page: ModerationPage },
  { path: "audit", icon: HistoryOutlined, page: AuditPage }
] as const;

function currentSection() {
  return window.location.pathname.replace(/^\/demo\/?/, "").replace(/\/+$/, "") || "control-center";
}

export function DemoWorkspace() {
  const { locale, setLocale } = useLocale();
  const copy = DEMO_WORKSPACE_COPY[locale];
  const [sectionPath, setSectionPath] = useState(currentSection);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sessionVersion, setSessionVersion] = useState(0);
  const [queryClient] = useState(() => new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } }
  }));
  const theme = useMemo(() => createAppTheme("light"), []);
  const selected = sections.find(section => section.path === sectionPath);
  const Page = selected?.page;
  const title = selected ? copy.sections[selected.path] : copy.title;

  useEffect(() => {
    if (/^\/demo\/?$/.test(window.location.pathname)) {
      window.history.replaceState({}, "", "/demo/control-center");
    }
    const onPopState = () => {
      setSectionPath(currentSection());
      setMobileOpen(false);
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    document.title = `${title} · ${copy.demo} | Axyro Analytics`;
  }, [title, copy.demo]);

  function navigate(event: MouseEvent<HTMLAnchorElement>, path: string) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    window.history.pushState({}, "", `/demo/${path}`);
    window.dispatchEvent(new PopStateEvent("popstate"));
    window.scrollTo({ top: 0, behavior: "instant" });
  }

  function reset() {
    resetDemoState();
    try { localStorage.removeItem("axyro.demo.columns.v1"); } catch { /* Browser storage may be disabled. */ }
    queryClient.clear();
    setSessionVersion(version => version + 1);
  }

  const navigation = <nav className="demo-workspace-nav" aria-label={copy.navigation}>
    <div className="demo-workspace-nav-links">
      {sections.map(section => {
        const Icon = section.icon;
        return <a key={section.path} href={`/demo/${section.path}`}
          aria-current={section.path === sectionPath ? "page" : undefined}
          onClick={event => navigate(event, section.path)}>
          <Icon aria-hidden="true" /><span>{copy.sections[section.path]}</span>
        </a>;
      })}
    </div>
    <a className="demo-workspace-home" href="/"><ArrowBackOutlined aria-hidden="true" />{copy.home}</a>
  </nav>;

  return <ThemeProvider theme={theme}>
    <QueryClientProvider client={queryClient}>
      <div className="demo-workspace">
        <a className="demo-workspace-skip" href="#demo-content">{copy.skip}</a>
        <header className="demo-workspace-header">
          <button className="demo-workspace-menu" type="button" aria-label={copy.menu} onClick={() => setMobileOpen(true)}>
            <MenuOutlined />
          </button>
          <a className="demo-workspace-brand" href="/" aria-label="Axyro Analytics">
            <span className="demo-workspace-mark" aria-hidden="true"><i /><i /></span>
            <span>Axyro <span>Analytics</span></span>
          </a>
          <span className="demo-workspace-badge">{copy.demo}</span>
          <div className="demo-workspace-header-actions">
            <button type="button" className="demo-workspace-reset" onClick={reset} title={copy.reset} aria-label={copy.reset}>
              <RestartAltOutlined aria-hidden="true" /><span>{copy.reset}</span>
            </button>
            <button type="button" className="demo-workspace-language" aria-label={copy.language}
              onClick={() => setLocale(locale === "ru" ? "en" : "ru")}>{locale === "ru" ? "EN" : "RU"}</button>
          </div>
        </header>
        <aside className="demo-workspace-sidebar">{navigation}</aside>
        <Drawer className="demo-workspace-mobile-drawer" open={mobileOpen} onClose={() => setMobileOpen(false)}
          slotProps={{ paper: { sx: { width: 252, pt: 2, bgcolor: "background.paper" } } }}>
          {navigation}
        </Drawer>
        <main id="demo-content" className={`demo-workspace-content demo-section-${selected?.path || "unknown"}`} tabIndex={-1}>
          <p className="demo-workspace-notice">{copy.notice}</p>
          <Suspense fallback={<div className="demo-workspace-loading" role="status"><LinearProgress /><span>{copy.loading}</span></div>}>
            <div key={sessionVersion} className="demo-workspace-page">
              {Page ? <Page /> : <section className="demo-workspace-missing">
                <h1>{copy.unknown}</h1><p>{copy.unknownBody}</p>
                <a href="/demo/control-center" onClick={event => navigate(event, "control-center")}>{copy.back}</a>
              </section>}
            </div>
          </Suspense>
        </main>
      </div>
    </QueryClientProvider>
  </ThemeProvider>;
}
