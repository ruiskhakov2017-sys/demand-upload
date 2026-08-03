import {
  AppBar,
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

import { api, setCsrfToken } from "../api/client";
import { LoginPage } from "../pages/LoginPage";
import { SetupPage } from "../pages/SetupPage";
import { useThemePreference } from "./ThemePreference";
import { themeChoices } from "./theme";
import { t, useLocale } from "../i18n";

const AccountsPage = lazy(() => import("../pages/AccountsPage").then((module) => ({ default: module.AccountsPage })));
const AuditPage = lazy(() => import("../pages/AuditPage").then((module) => ({ default: module.AuditPage })));
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

const drawerWidth = 264;

type Navigate = (path: string, replace?: boolean) => void;
type NavItem = { path: string; label: string; icon: JSX.Element };
type NavGroup = { label: string; items: NavItem[] };

function getNavGroups(): NavGroup[] {
  return [
  {
    label: t("nav.analytics"),
    items: [
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
  const publicPath = path === "/" || path === "/privacy" || path === "/terms";
  const [mobileOpen, setMobileOpen] = useState(false);
  const [themeAnchor, setThemeAnchor] = useState<HTMLElement | null>(null);
  const [localeAnchor, setLocaleAnchor] = useState<HTMLElement | null>(null);
  const { themeName, setThemeName } = useThemePreference();
  const { locale, setLocale } = useLocale();
  const navGroups = getNavGroups();
  const theme = useTheme();
  const desktop = useMediaQuery(theme.breakpoints.up("md"));
  const queryClient = useQueryClient();
  const setupQuery = useQuery({ queryKey: ["setup-status"], queryFn: api.setupStatus, enabled: !publicPath });
  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const session = await api.me();
      setCsrfToken(session.csrf_token);
      return session;
    },
    enabled: !publicPath && setupQuery.data?.setup_required === false,
    retry: false
  });
  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      sessionStorage.clear();
      queryClient.clear();
      navigate("/login", true);
    }
  });

  const currentTitle = navGroups.flatMap((group) => group.items).find((item) => isSelected(path, item.path))?.label;
  useEffect(() => {
    if (!publicPath) {
      document.title = `${currentTitle || t("app.productName")} | Axyro Analytics`;
    }
  }, [currentTitle, publicPath, locale]);
  useEffect(() => {
    if (meQuery.data && path === "/login") navigate("/control-center", true);
  }, [meQuery.data, navigate, path]);

  if (publicPath) {
    return (
      <Suspense fallback={<CenteredText text={t("ui.b807935f97")} />}>
        {path === "/privacy" ? <LegalPage kind="privacy" /> : path === "/terms" ? <LegalPage kind="terms" /> : <PublicSitePage />}
      </Suspense>
    );
  }

  if (setupQuery.isLoading) return <CenteredText text={t("ui.b807935f97")} />;
  if (setupQuery.data?.setup_required) return <SetupPage />;
  if (!meQuery.data) return <LoginPage />;

  const user = meQuery.data.user;
  const drawer = (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <Toolbar sx={{ px: 2.25 }}>
        <Box>
          <Typography fontWeight={800} lineHeight={1.15}>{t("app.productName")}</Typography>
          <Typography variant="caption" color="text.secondary">{t("app.subtitle")}</Typography>
        </Box>
      </Toolbar>
      <Box sx={{ overflowY: "auto", flex: 1, pb: 2 }}>
        {navGroups.map((group) => (
          <List
            dense
            key={group.label}
            subheader={
              <ListSubheader sx={{ lineHeight: "32px", bgcolor: "transparent", fontSize: 11, fontWeight: 800 }}>
                {group.label.toUpperCase()}
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
                sx={{ mx: 1, minHeight: 40 }}
              >
                <ListItemIcon sx={{ minWidth: 38 }}>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            ))}
          </List>
        ))}
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar
        position="fixed"
        color="inherit"
        elevation={0}
        sx={{ zIndex: (value) => value.zIndex.drawer + 1, borderBottom: 1, borderColor: "divider" }}
      >
        <Toolbar>
          {!desktop && (
            <Tooltip title={t("ui.72374bf6be")}>
              <IconButton edge="start" onClick={() => setMobileOpen(true)} sx={{ mr: 1 }}>
                <MenuIcon />
              </IconButton>
            </Tooltip>
          )}
          <Typography variant="h6" sx={{ flexGrow: 1, fontSize: 18 }}>
            {currentTitle || t("app.productName")}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mr: 1.5, display: { xs: "none", sm: "block" } }}>
            {user.username} · {user.role}
          </Typography>
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
        <Box sx={{ maxWidth: 1440, mx: "auto", pt: 3 }}>
          <Suspense fallback={<CenteredText text={t("ui.b807935f97")} />}>
            {renderRoute(path, navigate)}
          </Suspense>
        </Box>
      </Box>
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
  const normalize = () => (window.location.pathname.replace(/\/+$/, "") || "/");
  const [path, setPath] = useState(normalize);
  useEffect(() => {
    const onPopState = () => setPath(normalize());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  const navigate = useMemo<Navigate>(
    () => (next, replace = false) => {
      const target = next || "/";
      if (replace) window.history.replaceState({}, "", target);
      else window.history.pushState({}, "", target);
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
