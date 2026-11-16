import {
  AppBar,
  Avatar,
  Box,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  Menu,
  MenuItem,
  Toolbar,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme
} from "@mui/material";
import AccountBalanceWalletOutlinedIcon from "@mui/icons-material/AccountBalanceWalletOutlined";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import CampaignOutlinedIcon from "@mui/icons-material/CampaignOutlined";
import DashboardOutlinedIcon from "@mui/icons-material/DashboardOutlined";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
import ImageOutlinedIcon from "@mui/icons-material/ImageOutlined";
import LinkOutlinedIcon from "@mui/icons-material/LinkOutlined";
import LogoutIcon from "@mui/icons-material/Logout";
import MenuIcon from "@mui/icons-material/Menu";
import MonitorHeartOutlinedIcon from "@mui/icons-material/MonitorHeartOutlined";
import NotificationsNoneIcon from "@mui/icons-material/NotificationsNone";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import PaletteOutlinedIcon from "@mui/icons-material/PaletteOutlined";
import CheckIcon from "@mui/icons-material/Check";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import ScheduleOutlinedIcon from "@mui/icons-material/ScheduleOutlined";
import TranslateIcon from "@mui/icons-material/Translate";
import ViewModuleOutlinedIcon from "@mui/icons-material/ViewModuleOutlined";
import ViewListOutlinedIcon from "@mui/icons-material/ViewListOutlined";
import WorkspacesOutlinedIcon from "@mui/icons-material/WorkspacesOutlined";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";

import { api, clearCsrfToken, setCsrfToken } from "../api/client";
import { AiAssistantDrawer } from "../components/AiAssistantDrawer";
import { LoginPage } from "../pages/LoginPage";
import { SetupPage } from "../pages/SetupPage";
import { useThemePreference } from "./ThemePreference";
import { themeChoices } from "./theme";
import { t, useLocale } from "../i18n";
import { ai } from "../i18n/aiAnalyst";
import { isDemoPath } from "../demo/isDemoPath";
import { appPath, appRoute, isPortfolioBuild } from "./paths";

const AccountsPage = lazy(() => import("../pages/AccountsPage").then((module) => ({ default: module.AccountsPage })));
const AuditPage = lazy(() => import("../pages/AuditPage").then((module) => ({ default: module.AuditPage })));
const AiAnalystPage = lazy(() => import("../pages/AiAnalystPage").then((module) => ({ default: module.AiAnalystPage })));
const ConnectionsPage = lazy(() => import("../pages/ConnectionsPage").then((module) => ({ default: module.ConnectionsPage })));
const ControlCenterPage = lazy(() => import("../pages/ControlCenterPage").then((module) => ({ default: module.ControlCenterPage })));
const DashboardPage = lazy(() => import("../pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const JobsPage = lazy(() => import("../pages/JobsPage").then((module) => ({ default: module.JobsPage })));
const AlertsPage = lazy(() => import("../pages/OperationsPages").then((module) => ({ default: module.AlertsPage })));
const FinancePage = lazy(() => import("../pages/OperationsPages").then((module) => ({ default: module.FinancePage })));
const ModerationPage = lazy(() => import("../pages/OperationsPages").then((module) => ({ default: module.ModerationPage })));
const SettingsPage = lazy(() => import("../pages/OperationsPages").then((module) => ({ default: module.SettingsPage })));
const StatisticsPage = lazy(() => import("../pages/OperationsPages").then((module) => ({ default: module.StatisticsPage })));
const MediaPage = lazy(() => import("../pages/MediaPage").then((module) => ({ default: module.MediaPage })));
const PlansPage = lazy(() => import("../pages/PlansPage").then((module) => ({ default: module.PlansPage })));
const SchedulesPage = lazy(() => import("../pages/SchedulesPage").then((module) => ({ default: module.SchedulesPage })));
const TemplatesPage = lazy(() => import("../pages/TemplatesPage").then((module) => ({ default: module.TemplatesPage })));
const LaunchGroupsPage = lazy(() => import("../pages/LaunchGroupsPage").then((module) => ({ default: module.LaunchGroupsPage })));
const NewUploadPage = lazy(() => import("../pages/UploadWizardPage").then((module) => ({ default: module.NewUploadPage })));
const UploadWizardPage = lazy(() => import("../pages/UploadWizardPage").then((module) => ({ default: module.UploadWizardPage })));
const PublicSitePage = lazy(() => import("../pages/PublicSitePage").then((module) => ({ default: module.PublicSitePage })));
const LegalPage = lazy(() => import("../pages/LegalPage").then((module) => ({ default: module.LegalPage })));
const DemoWorkspace = lazy(() => import("../pages/DemoWorkspace").then((module) => ({ default: module.DemoWorkspace })));

const drawerWidth = isPortfolioBuild ? 240 : 264;

type Navigate = (path: string, replace?: boolean) => void;
type NavItem = { path: string; label: string; icon: JSX.Element };
type NavGroup = { label: string; items: NavItem[] };

const portfolioRoutes = new Set(["/control-center", "/statistics", "/finance", "/alerts", "/moderation", "/audit"]);

function getNavGroups(): NavGroup[] {
  return [
  {
    label: t("nav.analytics"),
    items: [
      { path: "/ai-analyst", label: ai("ai.title"), icon: <AutoAwesomeOutlinedIcon /> },
      { path: "/control-center", label: t("controlCenter.nav"), icon: <MonitorHeartOutlinedIcon /> },
      { path: "/dashboard", label: t("nav.systemOverview"), icon: <DashboardOutlinedIcon /> },
      { path: "/statistics", label: t("ui.a77d7f6c0d"), icon: <AssessmentOutlinedIcon /> },
      { path: "/finance", label: t("ui.61dcf3af42"), icon: <AccountBalanceWalletOutlinedIcon /> },
      { path: "/alerts", label: t("ui.ee3c35f311"), icon: <NotificationsNoneIcon /> },
      { path: "/moderation", label: t("ui.80ae616e0b"), icon: <FactCheckOutlinedIcon /> },
      { path: "/audit", label: t("ui.67ade741ae"), icon: <HistoryOutlinedIcon /> }
    ]
  },
  {
    label: t("nav.deployment"),
    items: [
      { path: "/uploads/new", label: t("ui.7075f72219"), icon: <AddCircleOutlineIcon /> },
      { path: "/templates", label: t("ui.67cad9b67b"), icon: <ViewListOutlinedIcon /> },
      { path: "/media", label: t("ui.198be2a9a8"), icon: <ImageOutlinedIcon /> },
      { path: "/plans", label: t("ui.50a0e24e0f"), icon: <CampaignOutlinedIcon /> },
      { path: "/schedules", label: t("ui.f04bd0a064"), icon: <ScheduleOutlinedIcon /> },
      { path: "/launch-groups", label: t("ui.279f79d8f0"), icon: <ViewModuleOutlinedIcon /> },
      { path: "/jobs", label: t("ui.a11acfa069"), icon: <WorkspacesOutlinedIcon /> }
    ]
  },
  {
    label: t("ui.3ac98f278c"),
    items: [
      { path: "/connections", label: t("ui.451c32c81d"), icon: <LinkOutlinedIcon /> },
      { path: "/accounts", label: t("ui.b2018fe9b9"), icon: <AccountTreeOutlinedIcon /> },
      { path: "/settings", label: t("ui.7f17c7c62a"), icon: <SettingsOutlinedIcon /> }
    ]
  }
  ];
}

export function App() {
  const [path, navigate] = useBrowserPath();
  const demoPath = !isPortfolioBuild && isDemoPath(path);
  const publicPath = !isPortfolioBuild && (path === "/" || path === "/privacy" || path === "/terms");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [themeAnchor, setThemeAnchor] = useState<HTMLElement | null>(null);
  const [localeAnchor, setLocaleAnchor] = useState<HTMLElement | null>(null);
  const { themeName, setThemeName } = useThemePreference();
  const { locale, setLocale } = useLocale();
  const allNavGroups = getNavGroups();
  const navGroups = isPortfolioBuild
    ? allNavGroups.map(group => ({ ...group, items: group.items.filter(item => portfolioRoutes.has(item.path)) }))
        .filter(group => group.items.length > 0)
    : allNavGroups;
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up("md"));
  const queryClient = useQueryClient();
  const setupQuery = useQuery({ queryKey: ["setup-status"], queryFn: api.setupStatus, enabled: !publicPath && !demoPath });
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const session = await api.me();
      setCsrfToken(session.csrf_token);
      return session;
    },
    enabled: !publicPath && !demoPath && setupQuery.data?.setup_required === false,
    retry: false
  });
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      if (isPortfolioBuild) clearCsrfToken();
      else sessionStorage.clear();
      queryClient.clear();
      navigate("/login", true);
    }
  });

  const currentTitle = navGroups.flatMap((group) => group.items).find((item) => isSelected(path, item.path))?.label;
  useEffect(() => {
    if (!publicPath && !demoPath) {
      document.title = `${currentTitle || t("app.productName")} | Axyro Analytics`;
    }
  }, [currentTitle, publicPath, demoPath, locale]);
  useEffect(() => {
    if (meQuery.data && (path === "/login" || (isPortfolioBuild && !portfolioRoutes.has(path)))) {
      navigate("/control-center", true);
    }
  }, [meQuery.data, navigate, path]);

  if (demoPath) {
    return <Suspense fallback={<CenteredText text={t("ui.b807935f97")} />}><DemoWorkspace /></Suspense>;
  }

  if (publicPath) {
    return (
      <Suspense fallback={<CenteredText text={t("ui.b807935f97")} />}>
        {path === "/privacy" ? <LegalPage kind="privacy" /> : path === "/terms" ? <LegalPage kind="terms" /> : <PublicSitePage />}
      </Suspense>
    );
  }

  if (setupQuery.isLoading) return <CenteredText text={t("ui.b807935f97")} />;
  if (setupQuery.data?.setup_required && !isPortfolioBuild) return <SetupPage />;
  if (!meQuery.data) return <LoginPage />;

  const user = meQuery.data.user;
  const drawer = (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Toolbar sx={{ px: isPortfolioBuild ? 3 : 2.25, gap: 1.25, minHeight: isPortfolioBuild ? "88px !important" : undefined }}>
        {isPortfolioBuild && <Box aria-hidden="true" sx={{ width: 34, height: 34, bgcolor: "primary.main", borderRadius: "10px", display: "grid", placeItems: "center", color: "primary.contrastText" }}>
          <Box component="svg" viewBox="0 0 24 24" sx={{ width: 24, height: 24 }}><path d="M5 18 11 5h3l5 13h-4l-3-9-4 9Z" fill="currentColor"/><path d="M10 15h6v3h-7Z" fill="currentColor"/></Box>
        </Box>}
        <Box>
          <Typography fontWeight={isPortfolioBuild ? 600 : 800} lineHeight={1.15} sx={isPortfolioBuild ? { fontSize: 22, letterSpacing: "-0.04em" } : undefined}>{isPortfolioBuild ? "Axyro" : t("app.productName")}</Typography>
          <Typography variant="caption" color="text.secondary">{isPortfolioBuild ? "Analytics" : t("app.subtitle")}</Typography>
        </Box>
      </Toolbar>
      {isPortfolioBuild && <Box sx={{ mx: 2, mb: 3, mt: 1, px: 1.75, py: 1.5, border: 1, borderColor: "divider", borderRadius: 2, bgcolor: "background.default" }}>
        <Typography fontSize={13} fontWeight={500}>{t("workspace.label")}</Typography>
        <Typography variant="caption" color="text.secondary">Google Ads</Typography>
      </Box>}
      <Box sx={{ overflowY: "auto", flex: 1, pb: 2 }}>
        {navGroups.map((group) => (
          <List
            dense
            key={group.label}
            subheader={
              <ListSubheader sx={{ lineHeight: "32px", bgcolor: "transparent", fontSize: 11, fontWeight: isPortfolioBuild ? 500 : 800, px: isPortfolioBuild ? 3 : 2 }}>
                {isPortfolioBuild ? t("workspace.navigation") : group.label.toUpperCase()}
              </ListSubheader>
            }
          >
            {group.items.map((item) => (
              <ListItemButton
                key={item.path}
                selected={isSelected(path, item.path)}
                onClick={() => {
                  navigate(item.path);
                  setMobileOpen(false);
                }}
                sx={{ mx: isPortfolioBuild ? 1.5 : 1, minHeight: isPortfolioBuild ? 46 : 40, mb: isPortfolioBuild ? 0.5 : 0, borderRadius: isPortfolioBuild ? 2 : undefined }}
              >
                <ListItemIcon sx={{ minWidth: 38 }}>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            ))}
          </List>
        ))}
      </Box>
      {isPortfolioBuild && <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, p: 2.5, borderTop: 1, borderColor: "divider" }}>
        <Avatar sx={{ width: 34, height: 34, fontSize: 14, bgcolor: "action.selected", color: "primary.main", borderRadius: 2 }}>{user.username.slice(0, 1).toUpperCase()}</Avatar>
        <Box sx={{ minWidth: 0 }}>
          <Typography noWrap fontSize={13} fontWeight={500}>{user.username}</Typography>
          <Typography variant="caption" color="text.secondary">{user.role === "OPERATOR" ? t("workspace.operator") : user.role === "ADMIN" ? t("workspace.admin") : user.role}</Typography>
        </Box>
      </Box>}
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar
        position="fixed"
        color="inherit"
        elevation={0}
        sx={{ zIndex: (value) => isPortfolioBuild ? value.zIndex.appBar : value.zIndex.drawer + 1, borderBottom: 1, borderColor: "divider", ...(isPortfolioBuild && { width: desktop ? `calc(100% - ${drawerWidth}px)` : "100%", ml: desktop ? `${drawerWidth}px` : 0 }) }}
      >
        <Toolbar>
          {!desktop && (
            <Tooltip title={t("ui.72374bf6be")}>
              <IconButton edge="start" onClick={() => setMobileOpen(true)} sx={{ mr: 1 }}>
                <MenuIcon />
              </IconButton>
            </Tooltip>
          )}
          <Typography variant="h6" sx={{ flexGrow: 1, fontSize: isPortfolioBuild ? 13 : 18, fontWeight: isPortfolioBuild ? 400 : undefined }}>
            {isPortfolioBuild && <Box component="span" sx={{ color: "text.secondary", display: { xs: "none", sm: "inline" } }}>{t("workspace.label")}<Box component="span" sx={{ mx: 1.5, opacity: 0.5 }}>/</Box></Box>}{currentTitle || t("app.productName")}
          </Typography>
          {!isPortfolioBuild && <Typography variant="body2" color="text.secondary" sx={{ mr: 1.5, display: { xs: "none", sm: "block" } }}>
            {user.username} · {user.role}
          </Typography>}
          <Tooltip title={t("ui.cde3676894")}>
            <IconButton onClick={(event) => setThemeAnchor(event.currentTarget)}>
              <PaletteOutlinedIcon />
            </IconButton>
          </Tooltip>
          <Menu
            anchorEl={themeAnchor}
            open={Boolean(themeAnchor)}
            onClose={() => setThemeAnchor(null)}
            slotProps={{ paper: { sx: { minWidth: 220 } } }}
          >
            {themeChoices.map((choice) => (
              <MenuItem
                key={choice.name}
                selected={choice.name === themeName}
                onClick={() => {
                  setThemeName(choice.name);
                  setThemeAnchor(null);
                }}
              >
                <Box sx={{ display: "flex", width: 48, height: 18, mr: 1.5, border: 1, borderColor: "divider" }}>
                  {choice.preview.map((color) => (
                    <Box key={color} sx={{ flex: 1, bgcolor: color }} />
                  ))}
                </Box>
                <ListItemText>{t(choice.labelKey)}</ListItemText>
                {choice.name === themeName && <CheckIcon fontSize="small" />}
              </MenuItem>
            ))}
          </Menu>
          <Tooltip title={t("preferences.language")}>
            <IconButton onClick={(event) => setLocaleAnchor(event.currentTarget)}>
              <TranslateIcon />
            </IconButton>
          </Tooltip>
          <Menu
            anchorEl={localeAnchor}
            open={Boolean(localeAnchor)}
            onClose={() => setLocaleAnchor(null)}
          >
            {(["ru", "en"] as const).map((item) => (
              <MenuItem
                key={item}
                selected={item === locale}
                onClick={() => {
                  setLocale(item);
                  setLocaleAnchor(null);
                }}
              >
                <ListItemText>{t(`locale.${item}`)}</ListItemText>
                {item === locale && <CheckIcon fontSize="small" />}
              </MenuItem>
            ))}
          </Menu>
          <Tooltip title={t("ui.026abb1e0a")}>
            <IconButton onClick={() => logout.mutate()} disabled={logout.isPending}>
              <LogoutIcon />
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>
      <Drawer
        variant={desktop ? "permanent" : "temporary"}
        open={desktop || mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          width: desktop ? drawerWidth : 0,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: { width: drawerWidth, boxSizing: "border-box", borderRightColor: "divider" }
        }}
      >
        {drawer}
      </Drawer>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          minWidth: 0,
          width: desktop ? `calc(100% - ${drawerWidth}px)` : "100%",
          px: { xs: 2, sm: 3, lg: 4 },
          pb: 5
        }}
      >
        <Toolbar />
        <Box sx={{ maxWidth: 1440, mx: "auto", pt: isPortfolioBuild ? { xs: 3, md: 4 } : 3 }}>
          <Suspense fallback={<CenteredText text={t("ui.b807935f97")} />}>
            {renderRoute(isPortfolioBuild && !portfolioRoutes.has(path) ? "/control-center" : path, navigate)}
          </Suspense>
        </Box>
      </Box>
      {!isPortfolioBuild && <AiAssistantDrawer path={path} navigate={navigate} />}
    </Box>
  );
}

function renderRoute(path: string, navigate: Navigate) {
  const uploadMatch = path.match(/^\/uploads\/([0-9a-f-]+)$/i);
  if (uploadMatch) return <UploadWizardPage uploadId={uploadMatch[1]} navigate={navigate} />;
  const groupMatch = path.match(/^\/launch-groups\/([0-9a-f-]+)$/i);
  if (groupMatch) return <LaunchGroupsPage groupId={groupMatch[1]} navigate={navigate} />;
  const scheduleMatch = path.match(/^\/schedules\/([0-9a-f-]+)$/i);
  if (scheduleMatch) return <SchedulesPage scheduleId={scheduleMatch[1]} navigate={navigate} />;
  switch (path) {
    case "/dashboard":
      return <DashboardPage navigate={navigate} />;
    case "/uploads/new":
      return <NewUploadPage navigate={navigate} />;
    case "/templates":
      return <TemplatesPage navigate={navigate} />;
    case "/media":
      return <MediaPage />;
    case "/plans":
      return <PlansPage navigate={navigate} />;
    case "/schedules":
      return <SchedulesPage navigate={navigate} />;
    case "/launch-groups":
      return <LaunchGroupsPage navigate={navigate} />;
    case "/jobs":
      return <JobsPage />;
    case "/moderation":
      return <ModerationPage />;
    case "/control-center":
      return <ControlCenterPage />;
    case "/ai-analyst":
      return <AiAnalystPage />;
    case "/statistics":
      return <StatisticsPage />;
    case "/finance":
      return <FinancePage />;
    case "/alerts":
      return <AlertsPage />;
    case "/audit":
      return <AuditPage />;
    case "/connections":
      return <ConnectionsPage />;
    case "/accounts":
      return <AccountsPage />;
    case "/settings":
      return <SettingsPage />;
    case "/login":
      return <ControlCenterPage />;
    default:
      return (
        <Box>
          <Typography variant="h4">{t("ui.b8a9604777")}</Typography>
          <ListItemButton onClick={() => navigate("/control-center")} sx={{ mt: 2, width: "fit-content" }}>
            {t("ui.e95c3a8b54")}</ListItemButton>
        </Box>
      );
  }
}

function useBrowserPath(): [string, Navigate] {
  const normalize = () => (appRoute(window.location.pathname).replace(/\/+$/, "") || "/");
  const [path, setPath] = useState(normalize);
  useEffect(() => {
    const onPopState = () => setPath(normalize());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  const navigate = useMemo<Navigate>(
    () => (next, replace = false) => {
      const target = next || "/";
      if (replace) window.history.replaceState({}, "", appPath(target));
      else window.history.pushState({}, "", appPath(target));
      setPath(target.split("?", 1)[0].replace(/\/+$/, "") || "/");
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
    []
  );
  return [path, navigate];
}

function isSelected(path: string, target: string) {
  if (target === "/dashboard") return path === "/dashboard";
  if (target === "/uploads/new") return path.startsWith("/uploads/");
  if (target === "/launch-groups") return path.startsWith("/launch-groups");
  if (target === "/schedules") return path.startsWith("/schedules");
  return path === target;
}

function CenteredText({ text }: { text: string }) {
  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
      <Typography>{text}</Typography>
    </Box>
  );
}

export type { Navigate };
