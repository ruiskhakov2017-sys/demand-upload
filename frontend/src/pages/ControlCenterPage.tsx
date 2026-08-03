import { Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Checkbox, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Divider, Drawer, FormControl, FormControlLabel, IconButton, InputAdornment, InputLabel, LinearProgress, MenuItem, Paper, Select, Snackbar, Stack, Switch, Tab, Table, TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow, TableSortLabel, Tabs, TextField, ToggleButton, ToggleButtonGroup, Tooltip, Typography, useMediaQuery, useTheme } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArchiveOutlinedIcon from "@mui/icons-material/ArchiveOutlined";
import ArrowDownwardIcon from "@mui/icons-material/ArrowDownward";
import ArrowUpwardIcon from "@mui/icons-material/ArrowUpward";
import CloseIcon from "@mui/icons-material/Close";
import CloudSyncOutlinedIcon from "@mui/icons-material/CloudSyncOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadIcon from "@mui/icons-material/Download";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import FilterAltOutlinedIcon from "@mui/icons-material/FilterAltOutlined";
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
import PauseCircleOutlineIcon from "@mui/icons-material/PauseCircleOutline";
import PlayCircleOutlineIcon from "@mui/icons-material/PlayCircleOutline";
import PushPinIcon from "@mui/icons-material/PushPin";
import PushPinOutlinedIcon from "@mui/icons-material/PushPinOutlined";
import RefreshIcon from "@mui/icons-material/Refresh";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import SearchIcon from "@mui/icons-material/Search";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import TuneIcon from "@mui/icons-material/Tune";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api, ControlCenterAccount, ControlCenterAd, ControlCenterAsset, ControlCenterCampaign, ControlCenterGeo, ControlCenterMcc, ControlCenterProblem, ControlCenterRule, ControlCenterTag, ExecutionMode, QueryParams, SavedControlCenterView } from "../api/client";
import { formatDate, localeTag, t } from "../i18n";
import { cc, ccPersistedText } from "../i18n/controlCenter";
type MainTab = "accounts" | "campaigns" | "creatives" | "problems" | "moderation" | "verification" | "history" | "rules" | "views" | "sync";
type QuickFilter = "all" | "working" | "issues" | "verification" | "paused" | "archive";
type TimezoneMode = "ACCOUNT" | "MOSCOW";
type WorkStatus = ControlCenterAccount["work_status"];
function localizedOption<T extends string>(value: T, labelKey: string) {
    return {
        value,
        get label() {
            return cc(labelKey);
        }
    };
}
function workStatusOption(value: WorkStatus, labelKey: string, color: string) {
    return {
        value,
        color,
        get label() {
            return cc(labelKey);
        }
    };
}
const WORK_STATUS: Array<{
    value: WorkStatus;
    label: string;
    color: string;
}> = [
    workStatusOption("UNCLASSIFIED", "controlCenter.auto.001", "#64748b"),
    workStatusOption("PREPARATION", "controlCenter.auto.002", "#2563a8"),
    workStatusOption("WORKING", "controlCenter.auto.003", "#2e7d52"),
    workStatusOption("PAUSED", "controlCenter.auto.004", "#b7791f"),
    workStatusOption("ARCHIVED", "controlCenter.auto.005", "#6b7280")
];
export const QUICK_FILTERS: Array<{
    value: QuickFilter;
    label: string;
}> = [
    localizedOption("all", "controlCenter.auto.006"),
    localizedOption("working", "controlCenter.auto.003"),
    localizedOption("issues", "controlCenter.auto.007"),
    localizedOption("verification", "controlCenter.auto.008"),
    localizedOption("paused", "controlCenter.auto.004"),
    localizedOption("archive", "controlCenter.auto.005")
];
const ACTIVITY_STATUSES = [
    localizedOption("SPENDING", "controlCenter.full.001"),
    localizedOption("NOT_SPENDING", "controlCenter.full.002"),
    localizedOption("NO_ACTIVE_CAMPAIGNS", "controlCenter.full.003"),
    localizedOption("ENABLED_NO_SPEND", "controlCenter.full.004"),
    localizedOption("SUSPENDED", "controlCenter.full.005"),
    localizedOption("NO_ACCESS", "controlCenter.full.006"),
    localizedOption("STALE", "controlCenter.full.007"),
    localizedOption("NO_DATA", "controlCenter.auto.229")
];
const PERIODS = [
    localizedOption("today", "controlCenter.auto.009"),
    localizedOption("yesterday", "controlCenter.auto.010"),
    localizedOption("3d", "controlCenter.auto.011"),
    localizedOption("7d", "controlCenter.auto.012"),
    localizedOption("30d", "controlCenter.auto.013"),
    localizedOption("custom", "controlCenter.full.008")
];
type ColumnKey = "local_name" | "google_name" | "customer_id" | "geo" | "mcc" | "connection" | "work_status" | "activity_status" | "google_status" | "problem" | "currency" | "time_zone" | "cost" | "budget" | "impressions" | "clicks" | "ctr" | "cpc" | "all_conversions" | "registrations" | "deposits" | "cpa_registration" | "cpa_deposit" | "registration_rate" | "registration_to_deposit_rate" | "conversion_value" | "roas" | "active_campaigns" | "disapproved_ads" | "policy" | "verification" | "last_error" | "note" | "tags" | "last_sync" | "freshness";
type ColumnDefinition = {
    key: ColumnKey;
    label: string;
    width: number;
    align?: "left" | "right" | "center";
};
function localizedColumn(key: ColumnKey, labelKey: string, width: number, align?: "left" | "right" | "center"): ColumnDefinition {
    return {
        key,
        width,
        align,
        get label() {
            return cc(labelKey);
        }
    };
}
export const COLUMNS: ColumnDefinition[] = [
    localizedColumn("local_name", "controlCenter.auto.014", 210),
    localizedColumn("google_name", "controlCenter.auto.015", 200),
    { key: "customer_id", label: "Customer ID", width: 132 },
    { key: "geo", label: "GEO", width: 120 },
    localizedColumn("mcc", "controlCenter.full.009", 170),
    localizedColumn("connection", "controlCenter.auto.016", 150),
    localizedColumn("work_status", "controlCenter.auto.017", 160),
    localizedColumn("activity_status", "controlCenter.full.010", 190),
    localizedColumn("google_status", "controlCenter.auto.018", 150),
    localizedColumn("problem", "controlCenter.auto.039", 130),
    localizedColumn("currency", "controlCenter.auto.019", 82),
    { key: "time_zone", label: "Timezone", width: 160 },
    localizedColumn("cost", "controlCenter.auto.020", 120, "right"),
    localizedColumn("budget", "controlCenter.auto.118", 120, "right"),
    localizedColumn("impressions", "controlCenter.auto.021", 110, "right"),
    localizedColumn("clicks", "controlCenter.auto.022", 90, "right"),
    { key: "ctr", label: "CTR", width: 82, align: "right" },
    { key: "cpc", label: "CPC", width: 100, align: "right" },
    localizedColumn("all_conversions", "controlCenter.full.011", 130, "right"),
    localizedColumn("registrations", "controlCenter.full.012", 120, "right"),
    localizedColumn("deposits", "controlCenter.full.013", 110, "right"),
    localizedColumn("cpa_registration", "controlCenter.full.014", 145, "right"),
    localizedColumn("cpa_deposit", "controlCenter.full.015", 135, "right"),
    { key: "registration_rate", label: "Reg. rate", width: 105, align: "right" },
    { key: "registration_to_deposit_rate", label: "Reg. → deposit", width: 130, align: "right" },
    localizedColumn("conversion_value", "controlCenter.auto.025", 110, "right"),
    { key: "roas", label: "ROAS", width: 90, align: "right" },
    localizedColumn("active_campaigns", "controlCenter.auto.026", 120, "right"),
    localizedColumn("disapproved_ads", "controlCenter.full.016", 150, "right"),
    localizedColumn("policy", "controlCenter.auto.027", 110, "center"),
    localizedColumn("verification", "controlCenter.auto.008", 140),
    localizedColumn("last_error", "controlCenter.auto.028", 220),
    localizedColumn("note", "controlCenter.auto.029", 270),
    localizedColumn("tags", "controlCenter.auto.030", 220),
    localizedColumn("last_sync", "controlCenter.auto.031", 170),
    localizedColumn("freshness", "controlCenter.auto.032", 120)
];
const DEFAULT_COLUMNS: ColumnKey[] = [
    "local_name",
    "customer_id",
    "geo",
    "mcc",
    "work_status",
    "activity_status",
    "google_status",
    "cost",
    "clicks",
    "registrations",
    "deposits",
    "active_campaigns",
    "verification",
    "note",
    "tags",
    "last_sync"
];
const COLUMN_SORT_FIELDS: Partial<Record<ColumnKey, string>> = {
    local_name: "name",
    google_name: "name",
    customer_id: "customer_id",
    geo: "geo",
    mcc: "mcc",
    work_status: "work_status",
    activity_status: "activity_status",
    google_status: "google_status",
    problem: "problem_count",
    currency: "currency_code",
    cost: "cost",
    budget: "budget",
    impressions: "impressions",
    clicks: "clicks",
    ctr: "ctr",
    cpc: "cpc",
    all_conversions: "all_conversions",
    registrations: "registrations",
    deposits: "deposits",
    cpa_registration: "cpa_registration",
    cpa_deposit: "cpa_deposit",
    registration_rate: "registration_rate",
    registration_to_deposit_rate: "registration_to_deposit_rate",
    conversion_value: "conversion_value",
    roas: "roas",
    active_campaigns: "active_campaigns",
    disapproved_ads: "disapproved_ads",
    last_sync: "last_sync_success_at"
};
const COLUMN_STORAGE = "dgu.control-center.columns.v1";
export function ControlCenterPage() {
    const [tab, setTab] = useState<MainTab>("accounts");
    const [campaignAccountId, setCampaignAccountId] = useState<string | null>(null);
    const me = useQuery({ queryKey: ["me"], queryFn: api.me });
    const canEdit = me.data?.user.role === "ADMIN" || me.data?.user.role === "OPERATOR";
    const isAdmin = me.data?.user.role === "ADMIN";
    return (<Stack spacing={2.5} sx={{ minWidth: 0 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 2 }}>
        <Box>
          <Typography variant="h4">{cc("controlCenter.auto.033")}</Typography>
          <Typography color="text.secondary" sx={{ mt: 0.5 }}>{cc("controlCenter.auto.034")}</Typography>
        </Box>
        <Chip size="small" variant="outlined" color="info" label={cc("controlCenter.auto.035")} sx={{ display: { xs: "none", sm: "flex" } }}/>
      </Box>
      <Paper variant="outlined" sx={{ overflow: "hidden" }}>
        <Tabs value={tab} onChange={(_, value: MainTab) => setTab(value)} variant="scrollable" scrollButtons="auto" aria-label={cc("controlCenter.auto.036")}>
          <Tab value="accounts" label={cc("controlCenter.auto.037")}/>
          <Tab value="campaigns" label={cc("controlCenter.auto.038")}/>
          <Tab value="creatives" label={cc("controlCenter.full.017")}/>
          <Tab value="problems" label={cc("controlCenter.auto.039")}/>
          <Tab value="moderation" label={cc("controlCenter.auto.027")}/>
          <Tab value="verification" label={cc("controlCenter.auto.008")}/>
          <Tab value="history" label={cc("controlCenter.auto.040")}/>
          <Tab value="rules" label={cc("controlCenter.auto.041")}/>
          <Tab value="views" label={cc("controlCenter.full.018")}/>
          <Tab value="sync" label={cc("controlCenter.auto.031")}/>
        </Tabs>
      </Paper>
      {tab === "accounts" && <AccountsWorkspace canEdit={canEdit} isAdmin={isAdmin} onOpenCampaigns={(accountId) => {
            setCampaignAccountId(accountId);
            setTab("campaigns");
        }}/>}
      {tab === "campaigns" && <CampaignsWorkspace canEdit={canEdit} accountId={campaignAccountId} onClearAccount={() => setCampaignAccountId(null)}/>}
      {tab === "creatives" && <CreativesWorkspace />}
      {tab === "problems" && <ProblemsWorkspace canEdit={canEdit}/>}
      {tab === "moderation" && <ModerationWorkspace />}
      {tab === "verification" && <VerificationWorkspace />}
      {tab === "history" && <HistoryWorkspace />}
      {tab === "rules" && <RulesWorkspace canEdit={isAdmin}/>}
      {tab === "views" && <ViewsWorkspace isAdmin={isAdmin}/>}
      {tab === "sync" && <SyncWorkspace canEdit={canEdit}/>}
    </Stack>);
}
function AccountsWorkspace({ canEdit, isAdmin, onOpenCampaigns }: {
    canEdit: boolean;
    isAdmin: boolean;
    onOpenCampaigns: (accountId: string) => void;
}) {
    const theme = useTheme();
    const mobile = useMediaQuery(theme.breakpoints.down("md"));
    const queryClient = useQueryClient();
    const [quickFilter, setQuickFilter] = useState<QuickFilter>("working");
    const [search, setSearch] = useState("");
    const [searchInput, setSearchInput] = useState("");
    const [period, setPeriod] = useState("7d");
    const [timezoneMode, setTimezoneMode] = useState<TimezoneMode>("ACCOUNT");
    const [tagId, setTagId] = useState("");
    const [connectionId, setConnectionId] = useState("");
    const [geoId, setGeoId] = useState("");
    const [mccId, setMccId] = useState("");
    const [currency, setCurrency] = useState("");
    const [googleStatus, setGoogleStatus] = useState("");
    const [workStatus, setWorkStatus] = useState("");
    const [activityStatus, setActivityStatus] = useState("");
    const [problemMode, setProblemMode] = useState("");
    const [problemType, setProblemType] = useState("");
    const [noteSearch, setNoteSearch] = useState("");
    const [grouping, setGrouping] = useState("none");
    const [sortRules, setSortRules] = useState<Array<{
        field: string;
        direction: "asc" | "desc";
    }>>([
        { field: "name", direction: "asc" }
    ]);
    const [costMin, setCostMin] = useState("");
    const [costMax, setCostMax] = useState("");
    const [registrationsMin, setRegistrationsMin] = useState("");
    const [depositsZero, setDepositsZero] = useState(false);
    const [cpaMin, setCpaMin] = useState("");
    const [cpaMax, setCpaMax] = useState("");
    const [activeCampaignsMin, setActiveCampaignsMin] = useState("");
    const [disapprovedAdsMin, setDisapprovedAdsMin] = useState("");
    const [registrationsWithoutDeposits, setRegistrationsWithoutDeposits] = useState(false);
    const [customStart, setCustomStart] = useState("");
    const [customEnd, setCustomEnd] = useState("");
    const [page, setPage] = useState(0);
    const [pageSize, setPageSize] = useState(50);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [editing, setEditing] = useState<ControlCenterAccount | null>(null);
    const [detailId, setDetailId] = useState<string | null>(null);
    const [columnDialog, setColumnDialog] = useState(false);
    const [saveViewDialog, setSaveViewDialog] = useState(false);
    const [syncDialog, setSyncDialog] = useState<Record<string, any> | null>(null);
    const [viewName, setViewName] = useState("");
    const [viewDefault, setViewDefault] = useState(false);
    const [viewShared, setViewShared] = useState(false);
    const [message, setMessage] = useState<string | null>(null);
    const [columnState, setColumnState] = useState<{
        order: ColumnKey[];
        visible: ColumnKey[];
        pinned: ColumnKey[];
        widths: Partial<Record<ColumnKey, number>>;
        density: "compact" | "normal";
    }>(() => loadColumnState());
    const [defaultApplied, setDefaultApplied] = useState(false);
    const summary = useQuery({
        queryKey: ["control-center-summary"],
        queryFn: api.controlCenterSummary,
        refetchInterval: 30000
    });
    const tags = useQuery({ queryKey: ["control-center-tags"], queryFn: api.controlCenterTags });
    const views = useQuery({
        queryKey: ["control-center-saved-views"],
        queryFn: api.controlCenterSavedViews
    });
    const connections = useQuery({ queryKey: ["connections"], queryFn: api.listConnections });
    const geos = useQuery({ queryKey: ["control-center-geos"], queryFn: api.controlCenterGeos });
    const mcc = useQuery({
        queryKey: ["control-center-mcc", connectionId, geoId],
        queryFn: () => api.controlCenterMcc({
            connection_id: connectionId,
            geo_id: geoId,
            include_detached: false
        })
    });
    const accountParams: QueryParams = {
        quick_filter: quickFilter,
        search,
        period,
        timezone_mode: timezoneMode,
        start_date: period === "custom" ? customStart : undefined,
        end_date: period === "custom" ? customEnd : undefined,
        tag_id: tagId,
        connection_id: connectionId,
        geo_id: geoId,
        mcc_id: mccId,
        currency,
        google_status: googleStatus,
        work_status: workStatus,
        activity_status: activityStatus,
        has_problems: problemMode === "with" ? true : problemMode === "without" ? false : undefined,
        problem_type: problemType,
        note: noteSearch,
        grouping,
        sort: sortRules.map((item) => item.field).join(","),
        direction: sortRules.map((item) => item.direction).join(","),
        cost_min: toMicros(costMin),
        cost_max: toMicros(costMax),
        registrations_min: numberOrUndefined(registrationsMin),
        deposits_eq: depositsZero ? 0 : undefined,
        cpa_min: toMicros(cpaMin),
        cpa_max: toMicros(cpaMax),
        active_campaigns_min: numberOrUndefined(activeCampaignsMin),
        disapproved_ads_min: numberOrUndefined(disapprovedAdsMin),
        registrations_without_deposits: registrationsWithoutDeposits || undefined,
        limit: pageSize,
        offset: page * pageSize
    };
    const accounts = useQuery({
        queryKey: [
            "control-center-accounts",
            quickFilter,
            search,
            period,
            timezoneMode,
            tagId,
            connectionId,
            geoId,
            mccId,
            currency,
            googleStatus,
            workStatus,
            activityStatus,
            problemMode,
            problemType,
            noteSearch,
            grouping,
            sortRules,
            costMin,
            costMax,
            registrationsMin,
            depositsZero,
            cpaMin,
            cpaMax,
            activeCampaignsMin,
            disapprovedAdsMin,
            registrationsWithoutDeposits,
            customStart,
            customEnd,
            page,
            pageSize
        ],
        queryFn: () => api.controlCenterAccounts(accountParams),
        refetchInterval: 30000
    });
    useEffect(() => {
        const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300);
        return () => window.clearTimeout(timer);
    }, [searchInput]);
    useEffect(() => {
        if (defaultApplied || !views.data)
            return;
        const defaultView = views.data.find((item) => item.is_default);
        if (defaultView)
            applySavedView(defaultView);
        setDefaultApplied(true);
    }, [views.data, defaultApplied]);
    useEffect(() => {
        localStorage.setItem(COLUMN_STORAGE, JSON.stringify(columnState));
    }, [columnState]);
    useEffect(() => {
        setSelected(new Set());
    }, [quickFilter, search, tagId, connectionId, geoId, mccId, currency, googleStatus, workStatus, activityStatus, problemMode, problemType, noteSearch, grouping, costMin, costMax, registrationsMin, depositsZero, cpaMin, cpaMax, activeCampaignsMin, disapprovedAdsMin, registrationsWithoutDeposits]);
    useEffect(() => {
        setPage(0);
    }, [quickFilter, search, period, tagId, connectionId, geoId, mccId, currency, googleStatus, workStatus, activityStatus, problemMode, problemType, noteSearch, grouping, sortRules, costMin, costMax, registrationsMin, depositsZero, cpaMin, cpaMax, activeCampaignsMin, disapprovedAdsMin, registrationsWithoutDeposits, customStart, customEnd]);
    const patchAccount = useMutation({
        mutationFn: ({ id, payload }: {
            id: string;
            payload: Record<string, unknown>;
        }) => api.updateControlCenterAccount(id, payload),
        onSuccess: () => {
            setEditing(null);
            setMessage(cc("controlCenter.auto.042"));
            invalidateControlCenter(queryClient);
            if (detailId)
                queryClient.invalidateQueries({ queryKey: ["control-center-account", detailId] });
        }
    });
    const bulkStatus = useMutation({
        mutationFn: (workStatus: WorkStatus) => api.bulkControlCenterWorkStatus(Array.from(selected), workStatus),
        onSuccess: (result) => {
            setMessage(cc("controlCenter.auto.043") + result.updated);
            setSelected(new Set());
            invalidateControlCenter(queryClient);
        }
    });
    const saveView = useMutation({
        mutationFn: () => api.createControlCenterSavedView({
            name: viewName.trim(),
            entity_level: "ACCOUNT",
            is_default: viewDefault,
            is_shared: isAdmin && viewShared,
            config: currentViewConfig()
        }),
        onSuccess: () => {
            setSaveViewDialog(false);
            setViewName("");
            setViewDefault(false);
            setViewShared(false);
            setMessage(cc("controlCenter.auto.044"));
            queryClient.invalidateQueries({ queryKey: ["control-center-saved-views"] });
            queryClient.invalidateQueries({ queryKey: ["control-center-summary"] });
        }
    });
    const estimateSync = useMutation({
        mutationFn: ({ scope, ids }: {
            scope: string;
            ids: string[];
        }) => api.estimateControlCenterSync(scope, ids),
        onSuccess: (result, variables) => setSyncDialog({ ...result, scope: variables.scope, accountIds: variables.ids })
    });
    const startSync = useMutation({
        mutationFn: () => api.startControlCenterSync(syncDialog?.scope, syncDialog?.accountIds || [], syncDialog?.estimate_token),
        onSuccess: (result) => {
            setSyncDialog(null);
            setMessage(cc("controlCenter.auto.045") + String(result.sync_run_id).slice(0, 8));
            queryClient.invalidateQueries({ queryKey: ["jobs"] });
        }
    });
    const visibleColumns = columnState.order
        .filter((key) => columnState.visible.includes(key))
        .map((key) => {
        const column = COLUMNS.find((item) => item.key === key);
        return column ? { ...column, width: columnState.widths[key] || column.width } : undefined;
    })
        .filter(Boolean) as ColumnDefinition[];
    const rows = accounts.data?.items || [];
    const counts = accounts.data?.counts || {};
    const allSelected = Boolean(rows.length) && rows.every((row) => selected.has(row.id));
    const error = accounts.error ||
        summary.error ||
        geos.error ||
        mcc.error ||
        patchAccount.error ||
        bulkStatus.error ||
        saveView.error ||
        estimateSync.error ||
        startSync.error;
    function currentViewConfig() {
        return {
            quickFilter,
            search,
            period,
            timezoneMode,
            tagId,
            connectionId,
            geoId,
            mccId,
            currency,
            googleStatus,
            workStatus,
            activityStatus,
            problemMode,
            problemType,
            noteSearch,
            grouping,
            sortRules,
            costMin,
            costMax,
            registrationsMin,
            depositsZero,
            cpaMin,
            cpaMax,
            activeCampaignsMin,
            disapprovedAdsMin,
            registrationsWithoutDeposits,
            customStart,
            customEnd,
            pageSize,
            columns: columnState
        };
    }
    function applySavedView(view: SavedControlCenterView) {
        const config = view.config || {};
        setQuickFilter((config.quickFilter as QuickFilter) || "working");
        setSearchInput(config.search || "");
        setSearch(config.search || "");
        setPeriod(config.period || "7d");
        setTimezoneMode(config.timezoneMode || "ACCOUNT");
        setTagId(config.tagId || "");
        setConnectionId(config.connectionId || "");
        setGeoId(config.geoId || "");
        setMccId(config.mccId || "");
        setCurrency(config.currency || "");
        setGoogleStatus(config.googleStatus || "");
        setWorkStatus(config.workStatus || "");
        setActivityStatus(config.activityStatus || "");
        setProblemMode(config.problemMode || "");
        setProblemType(config.problemType || "");
        setNoteSearch(config.noteSearch || "");
        setGrouping(config.grouping || "none");
        setSortRules(config.sortRules || [{ field: "name", direction: "asc" }]);
        setCostMin(config.costMin || "");
        setCostMax(config.costMax || "");
        setRegistrationsMin(config.registrationsMin || "");
        setDepositsZero(Boolean(config.depositsZero));
        setCpaMin(config.cpaMin || "");
        setCpaMax(config.cpaMax || "");
        setActiveCampaignsMin(config.activeCampaignsMin || "");
        setDisapprovedAdsMin(config.disapprovedAdsMin || "");
        setRegistrationsWithoutDeposits(Boolean(config.registrationsWithoutDeposits));
        setCustomStart(config.customStart || "");
        setCustomEnd(config.customEnd || "");
        setPageSize(Number(config.pageSize) || 50);
        if (config.columns)
            setColumnState(normalizeColumnState(config.columns));
    }
    function changeSort(field: string, additive: boolean) {
        setSortRules((current) => {
            const existing = current.find((item) => item.field === field);
            const nextDirection: "asc" | "desc" = existing?.direction === "asc" ? "desc" : "asc";
            if (!additive)
                return [{ field, direction: nextDirection }];
            const without = current.filter((item) => item.field !== field);
            return [...without, { field, direction: nextDirection }].slice(-4);
        });
    }
    function toggleSelection(id: string) {
        setSelected((current) => {
            const next = new Set(current);
            if (next.has(id))
                next.delete(id);
            else
                next.add(id);
            return next;
        });
    }
    function openSync(scope: "SELECTED" | "WORKING" | "ALL") {
        const ids = scope === "SELECTED" ? Array.from(selected) : [];
        if (scope === "SELECTED" && !ids.length) {
            setMessage(cc("controlCenter.auto.046"));
            return;
        }
        estimateSync.mutate({ scope, ids });
    }
    const exportParams: QueryParams = {
        ...accountParams,
        limit: undefined,
        offset: undefined,
        columns: visibleColumns.map((column) => column.key).join(",")
    };
    return (<Stack spacing={2}>
      <SummaryStrip data={summary.data} loading={summary.isLoading}/>
      {error && <Alert severity="error">{error.message}</Alert>}
      <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 }, minWidth: 0 }}>
        <Stack spacing={1.5}>
          <Box sx={{ overflowX: "auto", pb: 0.25 }}>
            <ToggleButtonGroup exclusive size="small" value={quickFilter} onChange={(_, value: QuickFilter | null) => value && setQuickFilter(value)} aria-label={cc("controlCenter.auto.047")} sx={{ minWidth: "max-content" }}>
              {QUICK_FILTERS.map((item) => (<ToggleButton key={item.value} value={item.value}>
                  {item.label}
                  <Box component="span" sx={{ ml: 0.75, color: "text.secondary" }}>
                    {counts[item.value] ?? 0}
                  </Box>
                </ToggleButton>))}
            </ToggleButtonGroup>
          </Box>
          {period === "custom" && (<Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(180px, 240px))" }, gap: 1 }}>
            <TextField size="small" type="date" label={cc("controlCenter.full.019")} InputLabelProps={{ shrink: true }} value={customStart} onChange={(event) => setCustomStart(event.target.value)}/>
            <TextField size="small" type="date" label={cc("controlCenter.full.020")} InputLabelProps={{ shrink: true }} value={customEnd} onChange={(event) => setCustomEnd(event.target.value)}/>
          </Box>)}
          <Box sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "minmax(240px, 2fr) repeat(2, minmax(150px, 1fr))" },
            gap: 1
        }}>
            <TextField size="small" value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder={cc("controlCenter.auto.048")} InputProps={{
            startAdornment: (<InputAdornment position="start"><SearchIcon fontSize="small"/></InputAdornment>)
        }}/>
            <FormControl size="small">
              <InputLabel>{cc("controlCenter.auto.049")}</InputLabel>
              <Select value={period} label={cc("controlCenter.auto.049")} onChange={(event) => setPeriod(event.target.value)}>
                {PERIODS.map((item) => (<MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>))}
              </Select>
            </FormControl>
            <ToggleButtonGroup exclusive size="small" value={timezoneMode} onChange={(_, value: TimezoneMode | null) => value && setTimezoneMode(value)} fullWidth>
              <ToggleButton value="ACCOUNT">{cc("controlCenter.auto.050")}</ToggleButton>
              <ToggleButton value="MOSCOW">{cc("controlCenter.auto.051")}</ToggleButton>
            </ToggleButtonGroup>
          </Box>
          <Box sx={{
            display: "flex",
            gap: 1,
            alignItems: "center",
            flexWrap: "wrap"
        }}>
            <FormControl size="small" sx={{ minWidth: 170 }}>
              <InputLabel>{cc("controlCenter.full.021")}</InputLabel>
              <Select value={connectionId} label={cc("controlCenter.full.021")} onChange={(e) => {
            setConnectionId(e.target.value);
            setMccId("");
        }}>
                <MenuItem value="">{cc("controlCenter.auto.052")}</MenuItem>
                {(connections.data || []).map((item) => (<MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>GEO</InputLabel>
              <Select value={geoId} label="GEO" onChange={(event) => {
            setGeoId(event.target.value);
            setMccId("");
        }}>
                <MenuItem value="">{cc("controlCenter.full.022")}</MenuItem>
                {(geos.data || []).map((item) => (<MenuItem key={item.id} value={item.id}>{item.display_name}</MenuItem>))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 190 }}>
              <InputLabel>MCC</InputLabel>
              <Select value={mccId} label="MCC" onChange={(event) => setMccId(event.target.value)}>
                <MenuItem value="">{cc("controlCenter.full.023")}</MenuItem>
                {(mcc.data || []).filter((item) => !item.is_root).map((item) => (<MenuItem key={item.id} value={item.id}>{item.descriptive_name || formatCustomerId(item.customer_id)}{!item.geo ? cc("controlCenter.full.024") : ""}</MenuItem>))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel>{cc("controlCenter.full.025")}</InputLabel>
              <Select value={workStatus} label={cc("controlCenter.full.025")} onChange={(event) => setWorkStatus(event.target.value)}>
                <MenuItem value="">{cc("controlCenter.full.026")}</MenuItem>
                <MenuItem value="NOT_WORKING">{cc("controlCenter.full.027")}</MenuItem>
                {WORK_STATUS.map((item) => (<MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 210 }}>
              <InputLabel>{cc("controlCenter.full.010")}</InputLabel>
              <Select value={activityStatus} label={cc("controlCenter.full.010")} onChange={(event) => setActivityStatus(event.target.value)}>
                <MenuItem value="">{cc("controlCenter.full.028")}</MenuItem>
                {ACTIVITY_STATUSES.map((item) => (<MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>{cc("controlCenter.auto.018")}</InputLabel>
              <Select value={googleStatus} label={cc("controlCenter.auto.018")} onChange={(e) => setGoogleStatus(e.target.value)}>
                <MenuItem value="">{cc("controlCenter.auto.053")}</MenuItem>
                {["ENABLED", "SUSPENDED", "CLOSED", "CANCELED", "NO_ACCESS", "UNKNOWN"].map((item) => (<MenuItem key={item} value={item}>{googleStatusLabel(item)}</MenuItem>))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 160 }}>
              <InputLabel>{cc("controlCenter.auto.039")}</InputLabel>
              <Select value={problemMode} label={cc("controlCenter.auto.039")} onChange={(event) => setProblemMode(event.target.value)}>
                <MenuItem value="">{cc("controlCenter.auto.077")}</MenuItem>
                <MenuItem value="with">{cc("controlCenter.auto.007")}</MenuItem>
                <MenuItem value="without">{cc("controlCenter.full.029")}</MenuItem>
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 130 }}>
              <InputLabel>{cc("controlCenter.auto.019")}</InputLabel>
              <Select value={currency} label={cc("controlCenter.auto.019")} onChange={(e) => setCurrency(e.target.value)}>
                <MenuItem value="">{cc("controlCenter.auto.054")}</MenuItem>
                {Array.from(new Set(rows.map((item) => item.currency_code).filter(Boolean))).map((item) => (<MenuItem key={item} value={item || ""}>{item}</MenuItem>))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>{cc("controlCenter.auto.055")}</InputLabel>
              <Select value={tagId} label={cc("controlCenter.auto.055")} onChange={(e) => setTagId(e.target.value)}>
                <MenuItem value="">{cc("controlCenter.auto.056")}</MenuItem>
                {(tags.data || []).map((item) => (<MenuItem key={item.id} value={item.id}>{item.name}</MenuItem>))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 190 }}>
              <InputLabel>{cc("controlCenter.auto.057")}</InputLabel>
              <Select value="" label={cc("controlCenter.auto.057")} onChange={(event) => {
            const view = views.data?.find((item) => item.id === event.target.value);
            if (view)
                applySavedView(view);
        }}>
                <MenuItem value="">{cc("controlCenter.auto.058")}</MenuItem>
                {(views.data || []).map((view) => (<MenuItem key={view.id} value={view.id}>
                    {localizedSavedViewName(view.name)}{view.is_default ? cc("controlCenter.auto.059") : ""}
                  </MenuItem>))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>{cc("controlCenter.full.030")}</InputLabel>
              <Select value={grouping} label={cc("controlCenter.full.030")} onChange={(event) => setGrouping(event.target.value)}>
                <MenuItem value="none">{cc("controlCenter.full.031")}</MenuItem>
                <MenuItem value="geo">{cc("controlCenter.full.032")}</MenuItem>
                <MenuItem value="mcc">{cc("controlCenter.full.033")}</MenuItem>
                <MenuItem value="geo_mcc">GEO → MCC</MenuItem>
              </Select>
            </FormControl>
            <Tooltip title={cc("controlCenter.auto.060")}>
              <span>
                <Button variant="outlined" startIcon={<SaveOutlinedIcon />} disabled={!canEdit} onClick={() => setSaveViewDialog(true)}>{cc("controlCenter.auto.061")}</Button>
              </span>
            </Tooltip>
            <Button variant="outlined" startIcon={<TuneIcon />} onClick={() => setColumnDialog(true)}>{cc("controlCenter.auto.062")}</Button>
          </Box>
          <Accordion disableGutters elevation={0} sx={{ border: 1, borderColor: "divider", "&::before": { display: "none" } }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Stack direction="row" spacing={1} alignItems="center">
                <FilterAltOutlinedIcon fontSize="small"/>
                <Typography fontWeight={700}>{cc("controlCenter.full.034")}</Typography>
                {advancedFilterCount({
            problemType,
            noteSearch,
            costMin,
            costMax,
            registrationsMin,
            depositsZero,
            cpaMin,
            cpaMax,
            activeCampaignsMin,
            disapprovedAdsMin,
            registrationsWithoutDeposits
        }) > 0 && <Chip size="small" label={advancedFilterCount({
                problemType,
                noteSearch,
                costMin,
                costMax,
                registrationsMin,
                depositsZero,
                cpaMin,
                cpaMax,
                activeCampaignsMin,
                disapprovedAdsMin,
                registrationsWithoutDeposits
            })}/>}
              </Stack>
            </AccordionSummary>
            <AccordionDetails>
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(180px, 1fr))", lg: "repeat(4, minmax(170px, 1fr))" }, gap: 1 }}>
                <TextField size="small" label={cc("controlCenter.full.035")} value={problemType} onChange={(event) => setProblemType(event.target.value)}/>
                <TextField size="small" label={cc("controlCenter.full.036")} value={noteSearch} onChange={(event) => setNoteSearch(event.target.value)}/>
                <TextField size="small" type="number" label={cc("controlCenter.full.037")} value={costMin} onChange={(event) => setCostMin(event.target.value)} inputProps={{ min: 0, step: "0.01" }}/>
                <TextField size="small" type="number" label={cc("controlCenter.full.038")} value={costMax} onChange={(event) => setCostMax(event.target.value)} inputProps={{ min: 0, step: "0.01" }}/>
                <TextField size="small" type="number" label={cc("controlCenter.full.039")} value={registrationsMin} onChange={(event) => setRegistrationsMin(event.target.value)} inputProps={{ min: 0 }}/>
                <TextField size="small" type="number" label={cc("controlCenter.full.040")} value={cpaMin} onChange={(event) => setCpaMin(event.target.value)} inputProps={{ min: 0, step: "0.01" }}/>
                <TextField size="small" type="number" label={cc("controlCenter.full.041")} value={cpaMax} onChange={(event) => setCpaMax(event.target.value)} inputProps={{ min: 0, step: "0.01" }}/>
                <TextField size="small" type="number" label={cc("controlCenter.full.042")} value={activeCampaignsMin} onChange={(event) => setActiveCampaignsMin(event.target.value)} inputProps={{ min: 0 }}/>
                <TextField size="small" type="number" label={cc("controlCenter.full.043")} value={disapprovedAdsMin} onChange={(event) => setDisapprovedAdsMin(event.target.value)} inputProps={{ min: 0 }}/>
              </Box>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={1} sx={{ mt: 1 }}>
                <FormControlLabel control={<Checkbox checked={depositsZero} onChange={(event) => setDepositsZero(event.target.checked)}/>} label={cc("controlCenter.full.044")}/>
                <FormControlLabel control={<Checkbox checked={registrationsWithoutDeposits} onChange={(event) => setRegistrationsWithoutDeposits(event.target.checked)}/>} label={cc("controlCenter.full.045")}/>
                <Button size="small" onClick={() => {
            setProblemType("");
            setNoteSearch("");
            setCostMin("");
            setCostMax("");
            setRegistrationsMin("");
            setDepositsZero(false);
            setCpaMin("");
            setCpaMax("");
            setActiveCampaignsMin("");
            setDisapprovedAdsMin("");
            setRegistrationsWithoutDeposits(false);
        }}>{cc("controlCenter.full.046")}</Button>
              </Stack>
              <Typography variant="caption" color="text.secondary">{cc("controlCenter.full.047")}</Typography>
            </AccordionDetails>
          </Accordion>
          <Divider />
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center" }}>
            <Button size="small" startIcon={<CloudSyncOutlinedIcon />} disabled={!canEdit || estimateSync.isPending} onClick={() => openSync("SELECTED")}>{cc("controlCenter.auto.063")}</Button>
            <Button size="small" startIcon={<RefreshIcon />} disabled={!canEdit || estimateSync.isPending} onClick={() => openSync("WORKING")}>{cc("controlCenter.auto.064")}</Button>
            <Button size="small" startIcon={<RefreshIcon />} disabled={!canEdit || estimateSync.isPending} onClick={() => openSync("ALL")}>{cc("controlCenter.auto.065")}</Button>
            <Box sx={{ flex: 1 }}/>
            <Button size="small" startIcon={<DownloadIcon />} href={api.controlCenterExportUrl("csv", exportParams)}>
              CSV
            </Button>
            <Button size="small" startIcon={<DownloadIcon />} href={api.controlCenterExportUrl("xlsx", exportParams)}>
              XLSX
            </Button>
            <Typography variant="body2" color="text.secondary">{cc("controlCenter.auto.066")}{accounts.data?.total ?? 0}
            </Typography>
          </Box>
        </Stack>
      </Paper>
      {selected.size > 0 && (<Paper variant="outlined" sx={{
                p: 1.25,
                position: "sticky",
                top: 72,
                zIndex: 5,
                borderColor: "primary.main",
                display: "flex",
                alignItems: "center",
                gap: 1.5,
                flexWrap: "wrap"
            }}>
          <Typography fontWeight={700}>{cc("controlCenter.auto.067")}{selected.size}</Typography>
          <FormControl size="small" sx={{ minWidth: 190 }}>
            <InputLabel>{cc("controlCenter.auto.068")}</InputLabel>
            <Select value="" label={cc("controlCenter.auto.068")} disabled={!canEdit || bulkStatus.isPending} onChange={(event) => bulkStatus.mutate(event.target.value as WorkStatus)}>
              {WORK_STATUS.map((item) => (<MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>))}
            </Select>
          </FormControl>
          <Button size="small" onClick={() => setSelected(new Set())}>{cc("controlCenter.auto.069")}</Button>
        </Paper>)}
      {accounts.isLoading && <LinearProgress />}
      {mobile ? (<AccountsMobileList rows={rows} selected={selected} canEdit={canEdit} onSelect={toggleSelection} onOpen={setDetailId} onEdit={setEditing} onStatus={(account, nextWorkStatus) => patchAccount.mutate({ id: account.id, payload: { work_status: nextWorkStatus } })}/>) : grouping !== "none" ? (<GroupedAccounts groups={accounts.data?.groups || []} columns={visibleColumns} pinned={columnState.pinned} canEdit={canEdit} selected={selected} sortRules={sortRules} density={columnState.density} onSort={changeSort} onResize={(key, width) => setColumnState((current) => ({ ...current, widths: { ...current.widths, [key]: width } }))} onSelect={toggleSelection} onOpen={setDetailId} onEdit={setEditing} onStatus={(account, nextWorkStatus) => patchAccount.mutate({ id: account.id, payload: { work_status: nextWorkStatus } })}/>) : (<AccountsTable rows={rows} columns={visibleColumns} pinned={columnState.pinned} selected={selected} allSelected={allSelected} canEdit={canEdit} sortRules={sortRules} density={columnState.density} onSort={changeSort} onResize={(key, width) => setColumnState((current) => ({ ...current, widths: { ...current.widths, [key]: width } }))} onSelectAll={(checked) => setSelected(checked ? new Set(rows.map((row) => row.id)) : new Set())} onSelect={toggleSelection} onOpen={setDetailId} onEdit={setEditing} onStatus={(account, nextWorkStatus) => patchAccount.mutate({ id: account.id, payload: { work_status: nextWorkStatus } })}/>)}
      {grouping === "none" && accounts.data && accounts.data.total > 0 && (<Paper variant="outlined"><TablePagination component="div" count={accounts.data.total} page={page} onPageChange={(_, nextPage) => setPage(nextPage)} rowsPerPage={pageSize} onRowsPerPageChange={(event) => {
                setPageSize(Number(event.target.value));
                setPage(0);
            }} rowsPerPageOptions={[25, 50, 100, 200]} labelRowsPerPage={cc("controlCenter.full.048")} labelDisplayedRows={({ from, to, count }) => ("" + from + "\u2013" + to + cc("controlCenter.full.049") + count + "")}/></Paper>)}
      {!accounts.isLoading && !rows.length && (<Paper variant="outlined" sx={{ p: 5, textAlign: "center" }}>
          <FilterAltOutlinedIcon color="disabled" sx={{ fontSize: 42 }}/>
          <Typography fontWeight={700} sx={{ mt: 1 }}>{cc("controlCenter.auto.070")}</Typography>
          <Typography color="text.secondary">{cc("controlCenter.auto.071")}</Typography>
        </Paper>)}
      <AccountEditDialog account={editing} tags={tags.data || []} geos={geos.data || []} saving={patchAccount.isPending} canEdit={canEdit} onClose={() => setEditing(null)} onSave={(payload) => editing && patchAccount.mutate({ id: editing.id, payload })} onChanged={() => {
            invalidateControlCenter(queryClient);
            if (editing)
                queryClient.invalidateQueries({ queryKey: ["control-center-account", editing.id] });
        }}/>
      <AccountDetailDrawer accountId={detailId} canEdit={canEdit} period={period} timezoneMode={timezoneMode} onClose={() => setDetailId(null)} onEdit={(account) => setEditing(account)} onOpenCampaigns={(accountId) => {
            setDetailId(null);
            onOpenCampaigns(accountId);
        }}/>
      <ColumnDialog open={columnDialog} state={columnState} onClose={() => setColumnDialog(false)} onChange={setColumnState}/>
      <Dialog open={saveViewDialog} onClose={() => setSaveViewDialog(false)} fullWidth maxWidth="xs">
        <DialogTitle>{cc("controlCenter.auto.072")}</DialogTitle>
        <DialogContent>
          <TextField autoFocus fullWidth label={cc("controlCenter.auto.073")} value={viewName} onChange={(event) => setViewName(event.target.value)} sx={{ mt: 1 }}/>
          <FormControlLabel sx={{ mt: 1 }} control={<Switch checked={viewDefault} onChange={(event) => setViewDefault(event.target.checked)}/>} label={cc("controlCenter.auto.074")}/>
          {isAdmin && <FormControlLabel sx={{ mt: 1 }} control={<Switch checked={viewShared} onChange={(event) => setViewShared(event.target.checked)}/>} label={cc("controlCenter.full.050")}/>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveViewDialog(false)}>{cc("controlCenter.auto.075")}</Button>
          <Button variant="contained" disabled={!viewName.trim() || saveView.isPending} onClick={() => saveView.mutate()}>{cc("controlCenter.auto.076")}</Button>
        </DialogActions>
      </Dialog>
      <SyncEstimateDialog data={syncDialog} loading={startSync.isPending} onClose={() => setSyncDialog(null)} onStart={() => startSync.mutate()}/>
      <Snackbar open={Boolean(message)} autoHideDuration={5000} onClose={() => setMessage(null)}>
        <Alert severity="success" onClose={() => setMessage(null)}>{message}</Alert>
      </Snackbar>
    </Stack>);
}
function SummaryStrip({ data, loading }: {
    data?: Record<string, any>;
    loading: boolean;
}) {
    const currencyRows = (data?.metrics?.by_currency || []) as Array<{
        currency_code: string;
        cost_micros: number;
    }>;
    const costSummary = currencyRows.length
        ? currencyRows.map((item) => money(item.cost_micros, item.currency_code)).join(" · ")
        : "—";
    const values = [
        { label: cc("controlCenter.auto.077"), value: data?.accounts?.all, detail: (data?.accounts?.working ?? 0) + cc("controlCenter.auto.078") },
        {
            label: cc("controlCenter.auto.020"),
            value: costSummary,
            detail: data?.metrics?.mixed_currencies
                ? cc("controlCenter.full.051") : cc("controlCenter.auto.079")
        },
        { label: cc("controlCenter.auto.026"), value: data?.campaigns?.enabled, detail: (data?.campaigns?.total ?? 0) + cc("controlCenter.auto.080") },
        { label: cc("controlCenter.auto.081"), value: data?.problems?.active, detail: cc("controlCenter.auto.082") },
        {
            label: cc("controlCenter.auto.083"),
            value: data?.quota?.used_today,
            detail: cc("controlCenter.auto.084") + (data?.quota?.manual_reserve ?? "—")
        }
    ];
    return (<Box sx={{
            display: "grid",
            gridTemplateColumns: { xs: "repeat(2, minmax(0, 1fr))", lg: "repeat(5, minmax(0, 1fr))" },
            border: 1,
            borderColor: "divider",
            bgcolor: "background.paper"
        }}>
      {values.map((item, index) => (<Box key={item.label} sx={{
                p: { xs: 1.5, sm: 2 },
                minWidth: 0,
                borderRight: { lg: index < values.length - 1 ? 1 : 0 },
                borderBottom: { xs: index < 4 ? 1 : 0, lg: 0 },
                borderColor: "divider"
            }}>
          <Typography variant="caption" color="text.secondary">{item.label}</Typography>
          <Typography sx={{ fontSize: { xs: 20, sm: 24 }, fontWeight: 800, lineHeight: 1.25, mt: 0.25 }}>
            {loading ? "…" : item.value ?? "—"}
          </Typography>
          <Typography variant="caption" color="text.secondary">{item.detail}</Typography>
        </Box>))}
      {data?.quota && (<Typography variant="caption" color="text.secondary" sx={{ gridColumn: "1 / -1", px: 2, py: 0.75, borderTop: 1, borderColor: "divider" }}>
          {cc("controlCenter.full.165")}{cc("controlCenter.auto.085")}{data.quota.forecast_end_of_day}{cc("controlCenter.auto.086")}{" "}{data.quota.internal_remaining}.
        </Typography>)}
      {data?.metrics?.mixed_currencies && (<Alert severity="warning" sx={{ gridColumn: "1 / -1", borderRadius: 0 }}>{cc("controlCenter.full.052")}</Alert>)}
    </Box>);
}
function GroupedAccounts(props: {
    groups: Array<Record<string, any>>;
    columns: ColumnDefinition[];
    pinned: ColumnKey[];
    selected: Set<string>;
    canEdit: boolean;
    sortRules: Array<{
        field: string;
        direction: "asc" | "desc";
    }>;
    density: "compact" | "normal";
    onSort: (field: string, additive: boolean) => void;
    onResize: (key: ColumnKey, width: number) => void;
    onSelect: (id: string) => void;
    onOpen: (id: string) => void;
    onEdit: (account: ControlCenterAccount) => void;
    onStatus: (account: ControlCenterAccount, status: WorkStatus) => void;
}) {
    return (<Stack spacing={2}>
      {props.groups.map((group) => {
            const groupRows = (group.items || []) as ControlCenterAccount[];
            const allSelected = Boolean(groupRows.length) && groupRows.every((row) => props.selected.has(row.id));
            return (<Box key={group.id} sx={{ borderTop: 2, borderColor: "divider", pt: 1 }}>
          <Box sx={{ display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap", px: 0.5, pb: 1 }}>
            <Typography variant="h6">{group.label}</Typography>
            <Chip size="small" label={("" + group.accounts + cc("controlCenter.full.053"))}/>
            <Typography variant="body2" color="text.secondary">{group.working_accounts}{cc("controlCenter.full.054")}{group.problem_accounts}{cc("controlCenter.full.055")}</Typography>
            <Box sx={{ flex: 1 }}/>
            {(group.currency_totals || []).map((total: Record<string, any>) => (<Typography key={total.currency_code} variant="body2" fontWeight={700}>{money(total.cost_micros, total.currency_code)}</Typography>))}
            {group.mixed_currencies && <Chip size="small" color="warning" variant="outlined" label={cc("controlCenter.full.056")}/>}
          </Box>
          <AccountsTable rows={groupRows} columns={props.columns} pinned={props.pinned} selected={props.selected} allSelected={allSelected} canEdit={props.canEdit} sortRules={props.sortRules} density={props.density} onSort={props.onSort} onResize={props.onResize} onSelectAll={(checked) => groupRows.forEach((row) => {
                    if (checked !== props.selected.has(row.id))
                        props.onSelect(row.id);
                })} onSelect={props.onSelect} onOpen={props.onOpen} onEdit={props.onEdit} onStatus={props.onStatus}/>
        </Box>);
        })}
    </Stack>);
}
function AccountsTable(props: {
    rows: ControlCenterAccount[];
    columns: ColumnDefinition[];
    pinned: ColumnKey[];
    selected: Set<string>;
    allSelected: boolean;
    canEdit: boolean;
    sortRules: Array<{
        field: string;
        direction: "asc" | "desc";
    }>;
    density: "compact" | "normal";
    onSort: (field: string, additive: boolean) => void;
    onResize: (key: ColumnKey, width: number) => void;
    onSelectAll: (checked: boolean) => void;
    onSelect: (id: string) => void;
    onOpen: (id: string) => void;
    onEdit: (account: ControlCenterAccount) => void;
    onStatus: (account: ControlCenterAccount, status: WorkStatus) => void;
}) {
    const pinnedLeft = useMemo(() => {
        const result: Partial<Record<ColumnKey, number>> = {};
        let left = 48;
        for (const column of props.columns) {
            if (props.pinned.includes(column.key)) {
                result[column.key] = left;
                left += column.width;
            }
        }
        return result;
    }, [props.columns, props.pinned]);
    return (<TableContainer component={Paper} variant="outlined" sx={{ maxHeight: "calc(100vh - 220px)", minHeight: 320, overflow: "auto" }}>
      <Table size="small" stickyHeader sx={{ tableLayout: "fixed", minWidth: tableWidth(props.columns), "& .MuiTableCell-root": { py: props.density === "compact" ? 0.5 : 1 } }}>
        <TableHead>
          <TableRow>
            <TableCell padding="checkbox" sx={{ position: "sticky", left: 0, zIndex: 5, width: 48, bgcolor: "background.paper" }}>
              <Checkbox size="small" checked={props.allSelected} indeterminate={props.selected.size > 0 && !props.allSelected} onChange={(event) => props.onSelectAll(event.target.checked)}/>
            </TableCell>
            {props.columns.map((column) => {
            const sortField = COLUMN_SORT_FIELDS[column.key];
            const sortIndex = sortField ? props.sortRules.findIndex((item) => item.field === sortField) : -1;
            const sortRule = sortIndex >= 0 ? props.sortRules[sortIndex] : undefined;
            return (<TableCell key={column.key} align={column.align || "left"} sx={{
                    width: column.width,
                    minWidth: column.width,
                    maxWidth: column.width,
                    left: pinnedLeft[column.key],
                    zIndex: pinnedLeft[column.key] !== undefined ? 4 : undefined,
                    bgcolor: "background.paper",
                    fontWeight: 800,
                    fontSize: 12,
                    position: pinnedLeft[column.key] !== undefined ? "sticky" : "relative"
                }}>
                {sortField ? (<TableSortLabel active={Boolean(sortRule)} direction={sortRule?.direction || "asc"} onClick={(event) => props.onSort(sortField, event.shiftKey)}>
                  {column.label}
                  {sortRule && props.sortRules.length > 1 && <Typography component="span" variant="caption" sx={{ ml: 0.5 }}>{sortIndex + 1}</Typography>}
                </TableSortLabel>) : column.label}
                <Box role="separator" aria-label={(cc("controlCenter.full.057") + column.label + "")} onMouseDown={(event) => startColumnResize(event, column, props.onResize)} sx={{ position: "absolute", top: 0, right: -3, width: 7, height: "100%", cursor: "col-resize", zIndex: 8 }}/>
              </TableCell>);
        })}
            <TableCell align="right" sx={{ width: 92, minWidth: 92 }}>{cc("controlCenter.auto.087")}</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {props.rows.map((account) => (<TableRow hover key={account.id} selected={props.selected.has(account.id)} onClick={() => props.onOpen(account.id)} sx={{
                cursor: "pointer",
                bgcolor: account.has_problem && account.work_status === "WORKING"
                    ? "rgba(194, 65, 12, 0.055)"
                    : undefined
            }}>
              <TableCell padding="checkbox" onClick={(event) => event.stopPropagation()} sx={{ position: "sticky", left: 0, zIndex: 3, bgcolor: "background.paper" }}>
                <Checkbox size="small" checked={props.selected.has(account.id)} onChange={() => props.onSelect(account.id)}/>
              </TableCell>
              {props.columns.map((column) => (<TableCell key={column.key} align={column.align || "left"} sx={{
                    width: column.width,
                    minWidth: column.width,
                    maxWidth: column.width,
                    left: pinnedLeft[column.key],
                    position: pinnedLeft[column.key] !== undefined ? "sticky" : undefined,
                    zIndex: pinnedLeft[column.key] !== undefined ? 2 : undefined,
                    bgcolor: "background.paper",
                    overflow: "hidden"
                }} onClick={column.key === "work_status" ? (event) => event.stopPropagation() : undefined}>
                  <AccountCell account={account} column={column.key} canEdit={props.canEdit} onStatus={(status) => props.onStatus(account, status)} onEdit={() => props.onEdit(account)}/>
                </TableCell>))}
              <TableCell align="right" onClick={(event) => event.stopPropagation()}>
                <Tooltip title={cc("controlCenter.auto.088")}>
                  <IconButton size="small" onClick={() => props.onOpen(account.id)}>
                    <VisibilityOutlinedIcon fontSize="small"/>
                  </IconButton>
                </Tooltip>
                <Tooltip title={cc("controlCenter.auto.089")}>
                  <span>
                    <IconButton size="small" disabled={!props.canEdit} onClick={() => props.onEdit(account)}>
                      <EditOutlinedIcon fontSize="small"/>
                    </IconButton>
                  </span>
                </Tooltip>
              </TableCell>
            </TableRow>))}
        </TableBody>
      </Table>
    </TableContainer>);
}
function AccountCell({ account, column, canEdit, onStatus, onEdit }: {
    account: ControlCenterAccount;
    column: ColumnKey;
    canEdit: boolean;
    onStatus: (status: WorkStatus) => void;
    onEdit: () => void;
}) {
    const metrics = account.metrics || ({} as ControlCenterAccount["metrics"]);
    switch (column) {
        case "local_name":
            return (<Stack direction="row" spacing={0.75} alignItems="center" sx={{ minWidth: 0 }}>
          {account.is_pinned && <PushPinIcon fontSize="inherit" color="primary"/>}
          <Box sx={{ minWidth: 0 }}>
            <Typography fontWeight={700} noWrap>{account.local_name || account.descriptive_name || account.customer_id}</Typography>
            {account.local_name && <Typography variant="caption" color="text.secondary" noWrap>{account.descriptive_name}</Typography>}
          </Box>
        </Stack>);
        case "google_name":
            return <Truncated text={account.descriptive_name || "—"}/>;
        case "customer_id":
            return <Typography sx={{ fontFamily: "monospace", fontSize: 13 }}>{formatCustomerId(account.customer_id)}</Typography>;
        case "geo":
            return account.geo ? <Chip size="small" variant="outlined" label={account.geo.short_label || account.geo.display_name} sx={{ borderColor: account.geo.color, color: account.geo.color }}/> : <Chip size="small" color="warning" variant="outlined" label={cc("controlCenter.full.058")}/>;
        case "mcc":
            return <Truncated text={account.mcc_name || (account.mcc_customer_id ? formatCustomerId(account.mcc_customer_id) : cc("controlCenter.full.059"))}/>;
        case "connection":
            return <Truncated text={account.connection_name || "—"}/>;
        case "work_status":
            return (<Select size="small" variant="standard" disableUnderline value={account.work_status} disabled={!canEdit} onChange={(event) => onStatus(event.target.value as WorkStatus)} sx={{ minWidth: 135, fontSize: 13, "& .MuiSelect-select": { py: 0.25 } }}>
          {WORK_STATUS.map((item) => (<MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>))}
        </Select>);
        case "google_status":
            return <GoogleStatusChip account={account}/>;
        case "activity_status":
            return <ActivityChip value={account.activity_status}/>;
        case "problem":
            return account.has_problem ? <Chip size="small" color="error" variant="outlined" label={("" + (account.active_problem_count || 1) + cc("controlCenter.full.060"))}/> : <Chip size="small" color="success" variant="outlined" label={cc("controlCenter.full.061")}/>;
        case "currency":
            return account.currency_code || "—";
        case "time_zone":
            return <Truncated text={account.time_zone || "—"}/>;
        case "cost":
            return metrics.no_data_reason
                ? <Tooltip title={localizedNoDataReason(metrics.no_data_reason)}><span>{money(metrics.cost_micros, account.currency_code)}</span></Tooltip>
                : money(metrics.cost_micros, account.currency_code);
        case "budget":
            return money(metrics.budget_micros, account.currency_code);
        case "impressions":
            return number(metrics.impressions);
        case "clicks":
            return number(metrics.clicks);
        case "ctr":
            return percent(metrics.ctr);
        case "cpc":
            return money(metrics.cpc_micros, account.currency_code);
        case "all_conversions":
            return decimal(metrics.all_conversions);
        case "registrations":
            return metrics.registration_data_available ? decimal(metrics.registrations) : <NoData />;
        case "deposits":
            return metrics.deposit_data_available ? decimal(metrics.deposits) : <NoData />;
        case "cpa_registration":
            return metrics.registration_data_available ? money(metrics.cpa_registration_micros, account.currency_code) : <NoData />;
        case "cpa_deposit":
            return metrics.deposit_data_available ? money(metrics.cpa_deposit_micros, account.currency_code) : <NoData />;
        case "registration_rate":
            return metrics.registration_data_available ? percent(metrics.registration_rate) : <NoData />;
        case "registration_to_deposit_rate":
            return metrics.deposit_data_available ? percent(metrics.registration_to_deposit_rate) : <NoData />;
        case "conversion_value":
            return currencyValue(metrics.conversion_value, account.currency_code);
        case "roas":
            return metrics.roas === null || metrics.roas === undefined ? "—" : `${decimal(metrics.roas)}×`;
        case "active_campaigns":
            return number(metrics.active_campaigns);
        case "disapproved_ads":
            return number(metrics.disapproved_ads);
        case "policy":
            return metrics.policy_issues === null || metrics.policy_issues === undefined ? "—" : (<Chip size="small" color={metrics.policy_issues > 0 ? "warning" : "success"} variant="outlined" label={metrics.policy_issues}/>);
        case "verification":
            return <VerificationChip account={account}/>;
        case "last_error":
            return <Truncated text={account.sync_error || metrics.last_error_code || "—"} error={Boolean(account.sync_error)}/>;
        case "note":
            return (<Tooltip title={account.current_note || cc("controlCenter.auto.090")}>
          <Button color="inherit" size="small" disabled={!canEdit} onClick={(event) => {
                    event.stopPropagation();
                    onEdit();
                }} sx={{ justifyContent: "flex-start", maxWidth: "100%", px: 0.5, textTransform: "none" }}>
            <Typography variant="body2" noWrap color={account.current_note ? "text.primary" : "text.secondary"}>
              {account.current_note || cc("controlCenter.auto.091")}
            </Typography>
          </Button>
        </Tooltip>);
        case "tags":
            return (<Stack direction="row" spacing={0.5} sx={{ overflow: "hidden" }}>
          {account.tags.slice(0, 3).map((tag) => <TagChip key={tag.id} tag={tag}/>)}
          {account.tags.length > 3 && <Chip size="small" label={`+${account.tags.length - 3}`}/>}
          {!account.tags.length && <Typography color="text.secondary">—</Typography>}
        </Stack>);
        case "last_sync":
            return account.last_sync_success_at ? formatDate(account.last_sync_success_at) : "—";
        case "freshness":
            return <FreshnessChip value={metrics.freshness} approximate={metrics.boundary_precision !== "EXACT"}/>;
        default:
            return "—";
    }
}
function AccountsMobileList(props: {
    rows: ControlCenterAccount[];
    selected: Set<string>;
    canEdit: boolean;
    onSelect: (id: string) => void;
    onOpen: (id: string) => void;
    onEdit: (account: ControlCenterAccount) => void;
    onStatus: (account: ControlCenterAccount, status: WorkStatus) => void;
}) {
    return (<Stack spacing={1}>
      {props.rows.map((account) => (<Paper variant="outlined" key={account.id} sx={{
                p: 1.5,
                borderLeft: 4,
                borderLeftColor: account.has_problem ? "error.main" : "success.main"
            }}>
          <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
            <Checkbox size="small" checked={props.selected.has(account.id)} onChange={() => props.onSelect(account.id)} sx={{ p: 0.25 }}/>
            <Box sx={{ minWidth: 0, flex: 1 }} onClick={() => props.onOpen(account.id)}>
              <Typography fontWeight={800} noWrap>{account.display_name}</Typography>
              <Typography variant="caption" color="text.secondary">
                {formatCustomerId(account.customer_id)} · {account.geo?.display_name || cc("controlCenter.full.062")} · {account.currency_code || "—"}
              </Typography>
              <Stack direction="row" spacing={0.75} sx={{ mt: 1, flexWrap: "wrap", gap: 0.5 }}>
                <WorkStatusChip value={account.work_status}/>
                <ActivityChip value={account.activity_status}/>
                <GoogleStatusChip account={account}/>
                {account.tags.slice(0, 2).map((tag) => <TagChip key={tag.id} tag={tag}/>)}
              </Stack>
              <Box sx={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 1, mt: 1.25 }}>
                <MiniMetric label={cc("controlCenter.auto.092")} value={money(account.metrics.cost_micros, account.currency_code)}/>
                <MiniMetric label={cc("controlCenter.auto.022")} value={number(account.metrics.clicks)}/>
                <MiniMetric label={cc("controlCenter.full.012")} value={account.metrics.registration_data_available ? decimal(account.metrics.registrations) : cc("controlCenter.auto.229")}/>
                <MiniMetric label={cc("controlCenter.full.013")} value={account.metrics.deposit_data_available ? decimal(account.metrics.deposits) : cc("controlCenter.auto.229")}/>
              </Box>
              {account.metrics.no_data_reason && <Typography variant="caption" color="text.secondary">{localizedNoDataReason(account.metrics.no_data_reason)}</Typography>}
              {account.current_note && (<Typography variant="body2" color="text.secondary" sx={{ mt: 1 }} noWrap>
                  {account.current_note}
                </Typography>)}
            </Box>
            <IconButton size="small" disabled={!props.canEdit} onClick={() => props.onEdit(account)}>
              <EditOutlinedIcon fontSize="small"/>
            </IconButton>
          </Box>
          <FormControl size="small" fullWidth sx={{ mt: 1.25 }}>
            <Select value={account.work_status} disabled={!props.canEdit} onChange={(event) => props.onStatus(account, event.target.value as WorkStatus)}>
              {WORK_STATUS.map((item) => (<MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>))}
            </Select>
          </FormControl>
        </Paper>))}
    </Stack>);
}
function AccountEditDialog({ account, tags, geos, saving, canEdit, onClose, onSave, onChanged }: {
    account: ControlCenterAccount | null;
    tags: ControlCenterTag[];
    geos: ControlCenterGeo[];
    saving: boolean;
    canEdit: boolean;
    onClose: () => void;
    onSave: (payload: Record<string, unknown>) => void;
    onChanged: () => void;
}) {
    const queryClient = useQueryClient();
    const [localName, setLocalName] = useState("");
    const [note, setNote] = useState("");
    const [workStatus, setWorkStatus] = useState<WorkStatus>("UNCLASSIFIED");
    const [pinned, setPinned] = useState(false);
    const [geoOverride, setGeoOverride] = useState("INHERIT");
    const [selectedTag, setSelectedTag] = useState("");
    const [newTag, setNewTag] = useState("");
    const [tagColor, setTagColor] = useState("#2563a8");
    useEffect(() => {
        if (!account)
            return;
        setLocalName(account.local_name || "");
        setNote(account.current_note || "");
        setWorkStatus(account.work_status);
        setPinned(account.is_pinned);
        setGeoOverride(account.geo_override_id || "INHERIT");
        setSelectedTag("");
        setNewTag("");
    }, [account]);
    const assign = useMutation({
        mutationFn: ({ accountId, tagId }: {
            accountId: string;
            tagId: string;
        }) => api.assignControlCenterTag(accountId, tagId),
        onSuccess: () => {
            setSelectedTag("");
            onChanged();
        }
    });
    const remove = useMutation({
        mutationFn: ({ accountId, tagId }: {
            accountId: string;
            tagId: string;
        }) => api.removeControlCenterTag(accountId, tagId),
        onSuccess: onChanged
    });
    const create = useMutation({
        mutationFn: () => api.createControlCenterTag({ name: newTag, color: tagColor }),
        onSuccess: async (tag) => {
            if (account)
                await api.assignControlCenterTag(account.id, tag.id);
            setNewTag("");
            queryClient.invalidateQueries({ queryKey: ["control-center-tags"] });
            onChanged();
        }
    });
    return (<Dialog open={Boolean(account)} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{cc("controlCenter.auto.093")}</DialogTitle>
      <DialogContent>
        {account && (<Stack spacing={2} sx={{ mt: 1 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">Google Ads</Typography>
              <Typography fontWeight={700}>{account.descriptive_name || cc("controlCenter.auto.094")}</Typography>
              <Typography variant="body2" color="text.secondary">{formatCustomerId(account.customer_id)}</Typography>
            </Box>
            <TextField label={cc("controlCenter.auto.014")} value={localName} disabled={!canEdit} onChange={(event) => setLocalName(event.target.value)} helperText={cc("controlCenter.auto.095")}/>
            <FormControl fullWidth>
              <InputLabel>{cc("controlCenter.auto.017")}</InputLabel>
              <Select value={workStatus} label={cc("controlCenter.auto.017")} disabled={!canEdit} onChange={(event) => setWorkStatus(event.target.value as WorkStatus)}>
                {WORK_STATUS.map((item) => (<MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>))}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>{cc("controlCenter.full.063")}</InputLabel>
              <Select value={geoOverride} label={cc("controlCenter.full.063")} disabled={!canEdit} onChange={(event) => setGeoOverride(event.target.value)}>
                <MenuItem value="INHERIT">{cc("controlCenter.full.064")}{account.mcc_name ? ` (${account.mcc_name})` : ""}</MenuItem>
                {geos.map((geo) => (<MenuItem key={geo.id} value={geo.id}>{geo.display_name}</MenuItem>))}
              </Select>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>{geoOverride === "INHERIT" ? cc("controlCenter.full.065") : cc("controlCenter.full.066")}</Typography>
            </FormControl>
            <TextField label={cc("controlCenter.auto.029")} value={note} disabled={!canEdit} onChange={(event) => setNote(event.target.value)} multiline minRows={4} maxRows={10} inputProps={{ maxLength: 20000 }} helperText={cc("controlCenter.auto.096")}/>
            <FormControlLabel control={<Switch checked={pinned} disabled={!canEdit} onChange={(e) => setPinned(e.target.checked)}/>} label={cc("controlCenter.auto.097")}/>
            <Divider />
            <Typography fontWeight={700}>{cc("controlCenter.auto.030")}</Typography>
            <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
              {account.tags.map((tag) => (<Chip key={tag.id} size="small" label={tag.name} sx={{ borderColor: tag.color }} variant="outlined" onDelete={canEdit ? () => remove.mutate({ accountId: account.id, tagId: tag.id }) : undefined}/>))}
              {!account.tags.length && <Typography color="text.secondary">{cc("controlCenter.auto.098")}</Typography>}
            </Stack>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
              <FormControl size="small" fullWidth>
                <InputLabel>{cc("controlCenter.auto.099")}</InputLabel>
                <Select value={selectedTag} label={cc("controlCenter.auto.099")} onChange={(e) => setSelectedTag(e.target.value)}>
                  {tags
                .filter((tag) => !account.tags.some((current) => current.id === tag.id))
                .map((tag) => <MenuItem key={tag.id} value={tag.id}>{tag.name}</MenuItem>)}
                </Select>
              </FormControl>
              <Button variant="outlined" disabled={!selectedTag || assign.isPending || !canEdit} onClick={() => assign.mutate({ accountId: account.id, tagId: selectedTag })}>{cc("controlCenter.auto.100")}</Button>
            </Stack>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
              <TextField size="small" fullWidth label={cc("controlCenter.auto.101")} value={newTag} onChange={(e) => setNewTag(e.target.value)}/>
              <Tooltip title={cc("controlCenter.auto.102")}>
                <TextField size="small" type="color" value={tagColor} onChange={(e) => setTagColor(e.target.value)} sx={{ width: { xs: "100%", sm: 70 } }}/>
              </Tooltip>
              <Button variant="outlined" startIcon={<AddIcon />} disabled={!newTag.trim() || create.isPending || !canEdit} onClick={() => create.mutate()}>{cc("controlCenter.auto.103")}</Button>
            </Stack>
            {(assign.error || remove.error || create.error) && (<Alert severity="error">{(assign.error || remove.error || create.error)?.message}</Alert>)}
          </Stack>)}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{cc("controlCenter.auto.075")}</Button>
        <Button variant="contained" startIcon={<SaveOutlinedIcon />} disabled={!canEdit || saving} onClick={() => onSave({
            local_name: localName.trim() || null,
            current_note: note.trim() || null,
            work_status: workStatus,
            is_pinned: pinned,
            geo_override_id: geoOverride === "INHERIT" ? null : geoOverride
        })}>{cc("controlCenter.auto.076")}</Button>
      </DialogActions>
    </Dialog>);
}
function AccountDetailDrawer({ accountId, canEdit, period, timezoneMode, onClose, onEdit, onOpenCampaigns }: {
    accountId: string | null;
    canEdit: boolean;
    period: string;
    timezoneMode: string;
    onClose: () => void;
    onEdit: (account: ControlCenterAccount) => void;
    onOpenCampaigns: (accountId: string) => void;
}) {
    const detail = useQuery({
        queryKey: ["control-center-account", accountId, period, timezoneMode],
        queryFn: () => api.controlCenterAccount(accountId!, { period, timezone_mode: timezoneMode }),
        enabled: Boolean(accountId)
    });
    const accessPaths = useQuery({
        queryKey: ["control-center-access-paths", accountId],
        queryFn: () => api.controlCenterAccessPaths(accountId!),
        enabled: Boolean(accountId)
    });
    const managerHistory = useQuery({
        queryKey: ["control-center-manager-history", accountId],
        queryFn: () => api.controlCenterManagerHistory(accountId!),
        enabled: Boolean(accountId)
    });
    const account = detail.data?.account as ControlCenterAccount | undefined;
    const chart = (detail.data?.metric_history || []) as Array<Record<string, any>>;
    const maxCost = Math.max(1, ...chart.map((item) => Number(item.cost_micros || 0)));
    return (<Drawer anchor="right" open={Boolean(accountId)} onClose={onClose} PaperProps={{ sx: { width: { xs: "100%", sm: 720 }, maxWidth: "100vw" } }}>
      <Box sx={{ p: { xs: 2, sm: 3 } }}>
        <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="h5" fontWeight={800} noWrap>
              {account?.display_name || cc("controlCenter.auto.104")}
            </Typography>
            {account && (<Typography color="text.secondary">
                {formatCustomerId(account.customer_id)} · {account.connection_name}
              </Typography>)}
          </Box>
          {account && (<Tooltip title={cc("controlCenter.auto.105")}>
              <span>
                <IconButton disabled={!canEdit} onClick={() => onEdit(account)}>
                  <EditOutlinedIcon />
                </IconButton>
              </span>
            </Tooltip>)}
          <IconButton onClick={onClose}><CloseIcon /></IconButton>
        </Box>
        {detail.isLoading && <LinearProgress sx={{ mt: 2 }}/>}
        {detail.error && <Alert severity="error" sx={{ mt: 2 }}>{detail.error.message}</Alert>}
        {account && (<Stack spacing={3} sx={{ mt: 3 }}>
            <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
              <WorkStatusChip value={account.work_status}/>
              <ActivityChip value={account.activity_status}/>
              <GoogleStatusChip account={account}/>
              <FreshnessChip value={account.metrics.freshness} approximate={account.metrics.boundary_precision !== "EXACT"}/>
              {account.is_detached && <Chip color="default" label={cc("controlCenter.auto.106")}/>}
            </Stack>
            <InfoGrid items={[
                [cc("controlCenter.auto.015"), account.descriptive_name || "—"],
                [cc("controlCenter.auto.019"), account.currency_code || "—"],
                ["GEO", account.geo?.display_name || cc("controlCenter.full.058")],
                [cc("controlCenter.full.009"), account.mcc_name || account.mcc_customer_id || "—"],
                [cc("controlCenter.full.067"), account.access_path_count],
                ["Timezone", account.time_zone || "—"],
                [cc("controlCenter.auto.107"), account.last_sync_success_at ? formatDate(account.last_sync_success_at) : "—"],
                [cc("controlCenter.auto.008"), verificationLabel(account.verification_status)],
                [cc("controlCenter.auto.039"), account.active_problem_count]
            ]}/>
            <Section title={cc("controlCenter.auto.108")}>
              {account.metrics.no_data_reason && <Alert severity="info" sx={{ mb: 1 }}>{localizedNoDataReason(account.metrics.no_data_reason)}</Alert>}
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(2, minmax(0, 1fr))", sm: "repeat(3, minmax(0, 1fr))" }, gap: 1 }}>
                <MiniMetric label={cc("controlCenter.auto.092")} value={money(account.metrics.cost_micros, account.currency_code)}/>
                <MiniMetric label={cc("controlCenter.auto.118")} value={money(account.metrics.budget_micros, account.currency_code)}/>
                <MiniMetric label={cc("controlCenter.auto.022")} value={number(account.metrics.clicks)}/>
                <MiniMetric label={cc("controlCenter.full.011")} value={decimal(account.metrics.all_conversions)}/>
                <MiniMetric label={cc("controlCenter.full.012")} value={account.metrics.registration_data_available ? decimal(account.metrics.registrations) : cc("controlCenter.auto.229")}/>
                <MiniMetric label={cc("controlCenter.full.013")} value={account.metrics.deposit_data_available ? decimal(account.metrics.deposits) : cc("controlCenter.auto.229")}/>
                <MiniMetric label="CTR" value={percent(account.metrics.ctr)}/>
                <MiniMetric label="CPC" value={money(account.metrics.cpc_micros, account.currency_code)}/>
                <MiniMetric label={cc("controlCenter.full.014")} value={account.metrics.registration_data_available ? money(account.metrics.cpa_registration_micros, account.currency_code) : cc("controlCenter.auto.229")}/>
                <MiniMetric label={cc("controlCenter.full.015")} value={account.metrics.deposit_data_available ? money(account.metrics.cpa_deposit_micros, account.currency_code) : cc("controlCenter.auto.229")}/>
                <MiniMetric label="ROAS" value={account.metrics.roas === null || account.metrics.roas === undefined ? "—" : `${decimal(account.metrics.roas)}×`}/>
              </Box>
              {chart.length > 0 ? (<Box sx={{ display: "flex", alignItems: "flex-end", height: 140, gap: 0.5, mt: 2 }}>
                  {chart.map((item) => (<Tooltip key={item.date} title={item.date + ": " + money(item.cost_micros, account.currency_code) + ", " + decimal(item.conversions) + cc("controlCenter.auto.109")}>
                      <Box sx={{
                        flex: 1,
                        minWidth: 5,
                        height: `${Math.max(4, Number(item.cost_micros || 0) / maxCost * 100)}%`,
                        bgcolor: "primary.main",
                        opacity: 0.78
                    }}/>
                    </Tooltip>))}
                </Box>) : (<Typography color="text.secondary" sx={{ mt: 2 }}>{cc("controlCenter.auto.110")}</Typography>)}
            </Section>
            <Section title={cc("controlCenter.full.068")}>
              {accessPaths.isLoading && <LinearProgress />}
              {!accessPaths.isLoading && !(accessPaths.data || []).length && <Typography color="text.secondary">{cc("controlCenter.full.069")}</Typography>}
              <Stack spacing={0.75}>
                {(accessPaths.data || []).map((path) => (<Box key={path.id} sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
                  <Typography variant="body2" sx={{ fontFamily: "monospace" }}>{(path.customer_path || []).map((value: string) => formatCustomerId(value)).join(" → ")}</Typography>
                  {path.is_primary && <Chip size="small" color="primary" label={cc("controlCenter.full.070")}/>}
                  {!path.is_active && <Chip size="small" label={cc("controlCenter.full.071")}/>}
                </Box>))}
              </Stack>
              {(managerHistory.data || []).length > 0 && (<Box sx={{ mt: 1.5 }}>
                <Typography variant="subtitle2">{cc("controlCenter.full.072")}</Typography>
                {(managerHistory.data || []).map((item) => (<Typography key={item.id} variant="body2" color="text.secondary">{formatDate(item.changed_at)} · {item.previous_manager_customer_id || "—"} → {item.current_manager_customer_id || "—"}</Typography>))}
              </Box>)}
            </Section>
            <Section title={cc("controlCenter.auto.111")}>
              <Typography sx={{ whiteSpace: "pre-wrap" }}>{account.current_note || cc("controlCenter.auto.112")}</Typography>
              {account.note_updated_at && (<Typography variant="caption" color="text.secondary">{cc("controlCenter.auto.113")}{formatDate(account.note_updated_at)}
                </Typography>)}
            </Section>
            <Section title={cc("controlCenter.auto.030")}>
              <Stack direction="row" spacing={0.75} useFlexGap flexWrap="wrap">
                {account.tags.map((tag) => <TagChip key={tag.id} tag={tag}/>)}
                {!account.tags.length && <Typography color="text.secondary">{cc("controlCenter.auto.114")}</Typography>}
              </Stack>
            </Section>
            <Section title={cc("controlCenter.auto.115") + (detail.data?.campaigns?.length || 0)}>
              <Button size="small" startIcon={<VisibilityOutlinedIcon />} onClick={() => onOpenCampaigns(account.id)} sx={{ mb: 1 }}>{cc("controlCenter.full.162")}</Button>
              <TableContainer sx={{ maxHeight: 260 }}>
                <Table size="small">
                  <TableHead><TableRow><TableCell>{cc("controlCenter.auto.116")}</TableCell><TableCell>{cc("controlCenter.auto.117")}</TableCell><TableCell align="right">{cc("controlCenter.auto.118")}</TableCell></TableRow></TableHead>
                  <TableBody>
                    {(detail.data?.campaigns || []).map((campaign: ControlCenterCampaign) => (<TableRow key={campaign.id}>
                        <TableCell>{campaign.name}</TableCell>
                        <TableCell><Chip size="small" variant="outlined" label={campaign.status || "UNKNOWN"}/></TableCell>
                        <TableCell align="right">{money(campaign.budget_micros, account.currency_code)}</TableCell>
                      </TableRow>))}
                    {!detail.data?.campaigns?.length && <EmptyTableRow columns={3} text={cc("controlCenter.auto.119")}/>}
                  </TableBody>
                </Table>
              </TableContainer>
            </Section>
            <Section title={cc("controlCenter.auto.120")}>
              {(detail.data?.ads_assets || []).length ? (<Stack spacing={1}>
                  {(detail.data?.ads_assets || []).map((item: Record<string, any>) => (<Box key={item.resource_name} sx={{ py: 1, borderBottom: 1, borderColor: "divider" }}>
                      <Typography fontWeight={700}>{item.resource_name}</Typography>
                      <Typography variant="body2" color="text.secondary">{item.approval_status}</Typography>
                    </Box>))}
                </Stack>) : (<Typography color="text.secondary">{cc("controlCenter.auto.121")}</Typography>)}
            </Section>
            <Section title={cc("controlCenter.full.195")}>
              <InfoGrid items={[
                [cc("controlCenter.auto.122"), verificationLabel(account.verification_status)],
                [cc("controlCenter.auto.123"), account.verification_deadline ? formatDate(account.verification_deadline) : "—"],
                [cc("controlCenter.auto.124"), account.verification_checked_at ? formatDate(account.verification_checked_at) : "—"]
            ]}/>
              {account.verification_action_url && (<Button component="a" href={account.verification_action_url} target="_blank" rel="noreferrer" sx={{ mt: 1 }}>{cc("controlCenter.auto.125")}</Button>)}
              <Alert severity="info" sx={{ mt: 1 }}>{cc("controlCenter.auto.126")}</Alert>
            </Section>
            <Section title={cc("controlCenter.auto.127") + (detail.data?.problems?.length || 0)}>
              <Stack spacing={1}>
                {(detail.data?.problems || []).map((problem: ControlCenterProblem) => (<Alert key={problem.id} severity={severityColor(problem.severity)}>
                    <Typography fontWeight={700}>{localizedProblemTitle(problem)}</Typography>
                    <Typography variant="body2">{localizedProblemDescription(problem)}</Typography>
                    {(problem.google_code || problem.request_id) && (<Typography variant="caption">
                        {problem.google_code || ""}{problem.request_id ? ` · Request ID: ${problem.request_id}` : ""}
                      </Typography>)}
                  </Alert>))}
                {!detail.data?.problems?.length && <Typography color="text.secondary">{cc("controlCenter.auto.128")}</Typography>}
              </Stack>
            </Section>
            <Section title={cc("controlCenter.auto.129") + (detail.data?.note_history?.length || 0)}>
              <Stack spacing={1}>
                {(detail.data?.note_history || []).map((item: Record<string, any>) => (<Box key={item.id} sx={{ py: 1, borderBottom: 1, borderColor: "divider" }}>
                    <Typography sx={{ whiteSpace: "pre-wrap" }}>{item.note || cc("controlCenter.auto.130")}</Typography>
                    <Typography variant="caption" color="text.secondary">{formatDate(item.changed_at)}</Typography>
                  </Box>))}
                {!detail.data?.note_history?.length && <Typography color="text.secondary">{cc("controlCenter.auto.131")}</Typography>}
              </Stack>
            </Section>
            <Section title={cc("controlCenter.auto.132") + (detail.data?.events?.length || 0)}>
              <Stack spacing={1}>
                {(detail.data?.events || []).slice(0, 30).map((item: Record<string, any>) => (<Box key={item.id} sx={{ display: "grid", gridTemplateColumns: "130px 1fr", gap: 1, py: 0.75 }}>
                    <Typography variant="caption" color="text.secondary">{formatDate(item.occurred_at)}</Typography>
                    <Typography variant="body2">{localizedEventSummary(item)}</Typography>
                  </Box>))}
              </Stack>
            </Section>
          </Stack>)}
      </Box>
    </Drawer>);
}
function ColumnDialog({ open, state, onClose, onChange }: {
    open: boolean;
    state: {
        order: ColumnKey[];
        visible: ColumnKey[];
        pinned: ColumnKey[];
        widths: Partial<Record<ColumnKey, number>>;
        density: "compact" | "normal";
    };
    onClose: () => void;
    onChange: (state: {
        order: ColumnKey[];
        visible: ColumnKey[];
        pinned: ColumnKey[];
        widths: Partial<Record<ColumnKey, number>>;
        density: "compact" | "normal";
    }) => void;
}) {
    function move(key: ColumnKey, direction: -1 | 1) {
        const index = state.order.indexOf(key);
        const target = index + direction;
        if (target < 0 || target >= state.order.length)
            return;
        const order = [...state.order];
        [order[index], order[target]] = [order[target], order[index]];
        onChange({ ...state, order });
    }
    return (<Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{cc("controlCenter.auto.133")}</DialogTitle>
      <DialogContent dividers>
        <ToggleButtonGroup exclusive size="small" value={state.density} onChange={(_, value: "compact" | "normal" | null) => value && onChange({ ...state, density: value })} sx={{ mb: 1.5 }}>
          <ToggleButton value="compact">{cc("controlCenter.full.073")}</ToggleButton>
          <ToggleButton value="normal">{cc("controlCenter.full.074")}</ToggleButton>
        </ToggleButtonGroup>
        <Stack spacing={0.5}>
          {state.order.map((key, index) => {
            const column = COLUMNS.find((item) => item.key === key)!;
            const visible = state.visible.includes(key);
            const pinned = state.pinned.includes(key);
            return (<Box key={key} sx={{
                    display: "grid",
                    gridTemplateColumns: "40px 1fr 40px 40px 40px",
                    alignItems: "center",
                    minHeight: 42,
                    borderBottom: 1,
                    borderColor: "divider"
                }}>
                <Checkbox size="small" checked={visible} onChange={() => onChange({
                    ...state,
                    visible: visible
                        ? state.visible.filter((item) => item !== key)
                        : [...state.visible, key]
                })}/>
                <Typography>{column.label}</Typography>
                <Tooltip title={pinned ? cc("controlCenter.auto.134") : cc("controlCenter.auto.135")}>
                  <IconButton size="small" disabled={!visible} onClick={() => onChange({
                    ...state,
                    pinned: pinned
                        ? state.pinned.filter((item) => item !== key)
                        : [...state.pinned, key]
                })}>
                    {pinned ? <PushPinIcon fontSize="small"/> : <PushPinOutlinedIcon fontSize="small"/>}
                  </IconButton>
                </Tooltip>
                <IconButton size="small" disabled={index === 0} onClick={() => move(key, -1)}>
                  <ArrowUpwardIcon fontSize="small"/>
                </IconButton>
                <IconButton size="small" disabled={index === state.order.length - 1} onClick={() => move(key, 1)}>
                  <ArrowDownwardIcon fontSize="small"/>
                </IconButton>
              </Box>);
        })}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => onChange({ order: COLUMNS.map((item) => item.key), visible: DEFAULT_COLUMNS, pinned: ["local_name"], widths: {}, density: "compact" })}>{cc("controlCenter.auto.136")}</Button>
        <Button onClick={() => onChange({ ...state, widths: {} })}>{cc("controlCenter.full.075")}</Button>
        <Button variant="contained" onClick={onClose}>{cc("controlCenter.auto.137")}</Button>
      </DialogActions>
    </Dialog>);
}
function SyncEstimateDialog({ data, loading, onClose, onStart }: {
    data: Record<string, any> | null;
    loading: boolean;
    onClose: () => void;
    onStart: () => void;
}) {
    return (<Dialog open={Boolean(data)} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{cc("controlCenter.auto.138")}</DialogTitle>
      <DialogContent>
        {data && (<Stack spacing={1.5} sx={{ mt: 1 }}>
            <InfoGrid items={[
                [cc("controlCenter.auto.139"), data.accounts],
                [cc("controlCenter.auto.140"), data.estimated_operations],
                [cc("controlCenter.auto.141"), data.quota?.used_today],
                [cc("controlCenter.auto.142"), data.quota?.internal_remaining],
                [cc("controlCenter.auto.143"), data.quota?.manual_reserve]
            ]}/>
            <Alert severity="info">{cc("controlCenter.full.165")}</Alert>
            {data.warning && <Alert severity="warning">{data.warning}</Alert>}
          </Stack>)}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{cc("controlCenter.auto.075")}</Button>
        <Button variant="contained" disabled={loading || !data?.accounts} onClick={onStart}>{cc("controlCenter.auto.144")}</Button>
      </DialogActions>
    </Dialog>);
}
function CampaignSortableHeader({ field, label, sortRules, onSort }: {
    field: string;
    label: string;
    sortRules: Array<{
        field: string;
        direction: "asc" | "desc";
    }>;
    onSort: (field: string, additive: boolean) => void;
}) {
    const rule = sortRules.find((item) => item.field === field);
    const order = rule ? sortRules.findIndex((item) => item.field === field) + 1 : 0;
    return (<TableCell align="right" sortDirection={rule?.direction || false}>
      <TableSortLabel active={Boolean(rule)} direction={rule?.direction || "asc"} onClick={(event) => onSort(field, event.shiftKey)}>
        {label}{order > 1 ? ` ${order}` : ""}
      </TableSortLabel>
    </TableCell>);
}
function CampaignsWorkspace({ canEdit, accountId, onClearAccount }: {
    canEdit: boolean;
    accountId: string | null;
    onClearAccount: () => void;
}) {
    const queryClient = useQueryClient();
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState("");
    const [source, setSource] = useState("");
    const [costMin, setCostMin] = useState("");
    const [registrationsWithoutDeposits, setRegistrationsWithoutDeposits] = useState(false);
    const [sortRules, setSortRules] = useState<Array<{
        field: string;
        direction: "asc" | "desc";
    }>>([{ field: "name", direction: "asc" }]);
    const [page, setPage] = useState(0);
    const [pageSize, setPageSize] = useState(50);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [preview, setPreview] = useState<Record<string, any> | null>(null);
    const [budgetDialog, setBudgetDialog] = useState(false);
    const [budget, setBudget] = useState("");
    const [message, setMessage] = useState<string | null>(null);
    const [executionMode, setExecutionMode] = useState<ExecutionMode>("SIMULATION");
    const [actionId, setActionId] = useState<string | null>(null);
    const [completedAction, setCompletedAction] = useState<Record<string, any> | null>(null);
    const campaigns = useQuery({
        queryKey: ["control-center-campaigns", accountId, search, statusFilter, source, costMin, registrationsWithoutDeposits, sortRules, page, pageSize],
        queryFn: () => api.controlCenterCampaigns({
            account_id: accountId || undefined,
            search,
            status_filter: statusFilter,
            source,
            cost_min_micros: costMin ? Math.round(Number(costMin) * 1000000) : undefined,
            registrations_without_deposits: registrationsWithoutDeposits || undefined,
            sort_fields: sortRules.map((item) => item.field).join(","),
            sort_directions: sortRules.map((item) => item.direction).join(","),
            limit: pageSize,
            offset: page * pageSize
        }),
        refetchInterval: 30000
    });
    const previewAction = useMutation({
        mutationFn: (payload: Record<string, unknown>) => api.previewControlCenterAction(payload),
        onSuccess: setPreview
    });
    const confirmAction = useMutation({
        mutationFn: () => api.confirmControlCenterAction(preview!.id, preview!.confirmation_token),
        onSuccess: (result) => {
            setPreview(null);
            setSelected(new Set());
            if (result.execution_mode === "SIMULATION") {
                setCompletedAction(result);
                setMessage(cc("controlCenter.auto.145"));
                invalidateControlCenter(queryClient);
            }
            else {
                setActionId(result.id);
                setMessage(t("googleMode.actionConfirmed"));
            }
        }
    });
    const actionResult = useQuery({
        queryKey: ["control-center-action", actionId],
        queryFn: () => api.getControlCenterAction(actionId!),
        enabled: Boolean(actionId),
        refetchInterval: (query) => ["SUCCEEDED", "COMPLETED_WITH_ERRORS", "FAILED"].includes(String(query.state.data?.status)) ? false : 1000
    });
    useEffect(() => {
        const result = actionResult.data;
        if (!result || !["SUCCEEDED", "COMPLETED_WITH_ERRORS", "FAILED"].includes(String(result.status)))
            return;
        setCompletedAction(result);
        setActionId(null);
        setMessage(result.status === "SUCCEEDED"
            ? t("googleMode.readbackSuccess")
            : result.error_message || t("googleMode.readbackFailed"));
        invalidateControlCenter(queryClient);
    }, [actionResult.data, queryClient]);
    useEffect(() => {
        setPage(0);
    }, [accountId, search, statusFilter, source, costMin, registrationsWithoutDeposits, sortRules]);
    const rows = campaigns.data?.items || [];
    const noDataReason = localizedNoDataReason(rows.find((campaign) => campaign.metrics.no_data_reason)
        ?.metrics.no_data_reason);
    const allSelected = rows.length > 0 && rows.every((row) => selected.has(row.id));
    const error = campaigns.error || previewAction.error || confirmAction.error;
    function changeCampaignSort(field: string, additive: boolean) {
        setSortRules((current) => {
            const existing = current.find((item) => item.field === field);
            const direction: "asc" | "desc" = existing?.direction === "asc" ? "desc" : "asc";
            if (!additive)
                return [{ field, direction }];
            return [...current.filter((item) => item.field !== field), { field, direction }].slice(-4);
        });
    }
    function requestAction(actionType: "PAUSE" | "ENABLE" | "SET_BUDGET", amountMicros?: number) {
        if (!selected.size) {
            setMessage(cc("controlCenter.auto.147"));
            return;
        }
        previewAction.mutate({
            campaign_ids: Array.from(selected),
            action_type: actionType,
            execution_mode: executionMode,
            amount_micros: amountMicros
        });
    }
    return (<Stack spacing={2}>
      {accountId && <Alert severity="info" action={<Button color="inherit" size="small" onClick={onClearAccount}>{cc("controlCenter.full.163")}</Button>}>{cc("controlCenter.full.164")}</Alert>}
      <Alert severity={executionMode === "PRODUCTION" ? "error" : executionMode === "GOOGLE_TEST" ? "warning" : "info"}>
        {executionMode === "SIMULATION"
            ? t("googleMode.simulationDescription")
            : executionMode === "GOOGLE_TEST"
                ? t("googleMode.testDescription")
                : t("googleMode.productionMutateBlocked")}
      </Alert>
      {(error || actionResult.error) && <Alert severity="error">{(error || actionResult.error)?.message}</Alert>}
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Box sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", sm: "minmax(240px, 2fr) 160px 190px 180px" },
            gap: 1
        }}>
          <TextField size="small" placeholder={cc("controlCenter.auto.150")} value={search} onChange={(event) => setSearch(event.target.value)} InputProps={{
            startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small"/></InputAdornment>
        }}/>
          <FormControl size="small">
            <InputLabel>{cc("controlCenter.auto.117")}</InputLabel>
            <Select value={statusFilter} label={cc("controlCenter.auto.117")} onChange={(e) => setStatusFilter(e.target.value)}>
              <MenuItem value="">{cc("controlCenter.auto.053")}</MenuItem>
              <MenuItem value="ENABLED">ENABLED</MenuItem>
              <MenuItem value="PAUSED">PAUSED</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small">
            <InputLabel>{cc("controlCenter.auto.151")}</InputLabel>
            <Select value={source} label={cc("controlCenter.auto.151")} onChange={(e) => setSource(e.target.value)}>
              <MenuItem value="">{cc("controlCenter.auto.053")}</MenuItem>
              <MenuItem value="DEMAND_GEN_UPLOADER">Demand Gen Uploader</MenuItem>
              <MenuItem value="GOOGLE_ADS_MANUAL">{cc("controlCenter.auto.152")}</MenuItem>
              <MenuItem value="UNKNOWN">{cc("controlCenter.auto.153")}</MenuItem>
            </Select>
          </FormControl>
          <TextField size="small" type="number" inputProps={{ min: 0, step: 0.01 }} label={cc("controlCenter.full.154")} value={costMin} onChange={(event) => setCostMin(event.target.value)}/>
        </Box>
        <FormControlLabel sx={{ mt: 1 }} control={<Checkbox checked={registrationsWithoutDeposits} onChange={(event) => setRegistrationsWithoutDeposits(event.target.checked)}/>} label={cc("controlCenter.full.155")}/>
        <Box sx={{ display: "flex", gap: 1, mt: 1.5, flexWrap: "wrap", alignItems: "center" }}>
          <Typography fontWeight={700}>{cc("controlCenter.auto.067")}{selected.size}</Typography>
          <FormControl size="small" sx={{ minWidth: 250 }}>
            <InputLabel>{t("googleMode.actionLabel")}</InputLabel>
            <Select value={executionMode} label={t("googleMode.actionLabel")} onChange={(event) => setExecutionMode(event.target.value as ExecutionMode)}>
              <MenuItem value="SIMULATION">Simulation</MenuItem>
              <MenuItem value="GOOGLE_TEST">{t("googleMode.testShort")}</MenuItem>
              <MenuItem value="PRODUCTION" disabled>{t("googleMode.productionShort")}</MenuItem>
            </Select>
          </FormControl>
          <Button size="small" startIcon={<PauseCircleOutlineIcon />} disabled={!canEdit || previewAction.isPending} onClick={() => requestAction("PAUSE")}>{cc("controlCenter.auto.154")}</Button>
          <Button size="small" startIcon={<PlayCircleOutlineIcon />} disabled={!canEdit || previewAction.isPending} onClick={() => requestAction("ENABLE")}>{cc("controlCenter.auto.155")}</Button>
          <Button size="small" startIcon={<EditOutlinedIcon />} disabled={!canEdit || previewAction.isPending} onClick={() => setBudgetDialog(true)}>{cc("controlCenter.auto.156")}</Button>
          <Box sx={{ flex: 1 }}/>
          <Typography color="text.secondary">{cc("controlCenter.auto.066")}{campaigns.data?.total ?? 0}</Typography>
        </Box>
      </Paper>
      {noDataReason && <Alert severity="info">{noDataReason}</Alert>}
      {campaigns.isLoading && <LinearProgress />}
      <TableContainer component={Paper} variant="outlined" sx={{ overflowX: "auto" }}>
        <Table size="small" sx={{ minWidth: 1980 }}>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox size="small" checked={allSelected} indeterminate={selected.size > 0 && !allSelected} onChange={(event) => setSelected(event.target.checked ? new Set(rows.map((row) => row.id)) : new Set())}/>
              </TableCell>
              <TableCell>{cc("controlCenter.auto.116")}</TableCell>
              <TableCell>{cc("controlCenter.auto.104")}</TableCell>
              <TableCell>{cc("controlCenter.auto.151")}</TableCell>
              <TableCell>{cc("controlCenter.auto.157")}</TableCell>
              <TableCell>{cc("controlCenter.auto.117")}</TableCell>
              <TableCell>{cc("controlCenter.full.156")}</TableCell>
              <CampaignSortableHeader field="budget" label={cc("controlCenter.auto.118")} sortRules={sortRules} onSort={changeCampaignSort}/>
              <CampaignSortableHeader field="cost" label={cc("controlCenter.auto.092")} sortRules={sortRules} onSort={changeCampaignSort}/>
              <CampaignSortableHeader field="impressions" label={cc("controlCenter.auto.021")} sortRules={sortRules} onSort={changeCampaignSort}/>
              <CampaignSortableHeader field="clicks" label={cc("controlCenter.auto.022")} sortRules={sortRules} onSort={changeCampaignSort}/>
              <TableCell align="right">CTR</TableCell>
              <TableCell align="right">{cc("controlCenter.full.157")}</TableCell>
              <CampaignSortableHeader field="registrations" label={cc("controlCenter.full.116")} sortRules={sortRules} onSort={changeCampaignSort}/>
              <CampaignSortableHeader field="deposits" label={cc("controlCenter.full.117")} sortRules={sortRules} onSort={changeCampaignSort}/>
              <CampaignSortableHeader field="cpa_registration" label={cc("controlCenter.full.158")} sortRules={sortRules} onSort={changeCampaignSort}/>
              <TableCell align="right">{cc("controlCenter.full.159")}</TableCell>
              <TableCell>{cc("controlCenter.auto.039")}</TableCell>
              <CampaignSortableHeader field="last_change" label={cc("controlCenter.full.160")} sortRules={sortRules} onSort={changeCampaignSort}/>
              <CampaignSortableHeader field="last_sync" label={cc("controlCenter.auto.158")} sortRules={sortRules} onSort={changeCampaignSort}/>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((campaign) => (<TableRow key={campaign.id} hover selected={selected.has(campaign.id)}>
                <TableCell padding="checkbox">
                  <Checkbox size="small" checked={selected.has(campaign.id)} onChange={() => setSelected((current) => {
                const next = new Set(current);
                if (next.has(campaign.id))
                    next.delete(campaign.id);
                else
                    next.add(campaign.id);
                return next;
            })}/>
                </TableCell>
                <TableCell>
                  <Typography fontWeight={700}>{campaign.name}</Typography>
                  <Typography variant="caption" color="text.secondary">{campaign.campaign_id}</Typography>
                </TableCell>
                <TableCell>
                  <Typography>{campaign.account_name || "—"}</Typography>
                  <Typography variant="caption" color="text.secondary">{formatCustomerId(campaign.customer_id || "")}</Typography>
                </TableCell>
                <TableCell>{sourceLabel(campaign.source)}</TableCell>
                <TableCell>{campaign.channel_type || "—"}</TableCell>
                <TableCell>
                  <Chip size="small" color={campaign.status === "ENABLED" ? "success" : "default"} variant="outlined" label={campaign.status || "UNKNOWN"}/>
                </TableCell>
                <TableCell>{campaign.bidding_strategy_type || "—"}</TableCell>
                <TableCell align="right">
                  {money(campaign.budget_micros, campaign.currency_code)}
                  {campaign.budget_shared && (<Tooltip title={cc("controlCenter.auto.159")}>
                      <WarningAmberIcon color="warning" sx={{ fontSize: 16, ml: 0.5, verticalAlign: "middle" }}/>
                    </Tooltip>)}
                </TableCell>
                <TableCell align="right">{money(campaign.metrics.cost_micros, campaign.currency_code)}</TableCell>
                <TableCell align="right">{number(campaign.metrics.impressions)}</TableCell>
                <TableCell align="right">{number(campaign.metrics.clicks)}</TableCell>
                <TableCell align="right">{percent(campaign.metrics.ctr)}</TableCell>
                <TableCell align="right">{decimal(campaign.metrics.all_conversions)}</TableCell>
                <TableCell align="right">{campaign.metrics.registration_data_available ? decimal(campaign.metrics.registrations) : <NoData/>}</TableCell>
                <TableCell align="right">{campaign.metrics.deposit_data_available ? decimal(campaign.metrics.deposits) : <NoData/>}</TableCell>
                <TableCell align="right">{campaign.metrics.registration_data_available ? money(campaign.metrics.cpa_registration_micros, campaign.currency_code) : <NoData/>}</TableCell>
                <TableCell align="right">{campaign.metrics.deposit_data_available ? money(campaign.metrics.cpa_deposit_micros, campaign.currency_code) : <NoData/>}</TableCell>
                <TableCell>
                  {campaign.policy_issues.length ? (<Tooltip title={campaign.policy_issues.map((item) => String(item.message || item.topic || item.code || "")).filter(Boolean).join("; ")}><Chip size="small" color="warning" label={`${campaign.policy_status || cc("controlCenter.auto.173")} · ${campaign.policy_issues.length}`}/></Tooltip>) : campaign.policy_status || "—"}
                </TableCell>
                <TableCell>{campaign.last_change_at ? formatDate(campaign.last_change_at) : "—"}</TableCell>
                <TableCell>{campaign.last_synced_at ? formatDate(campaign.last_synced_at) : "—"}</TableCell>
              </TableRow>))}
            {!rows.length && <EmptyTableRow columns={20} text={cc("controlCenter.auto.119")}/>}
          </TableBody>
        </Table>
      </TableContainer>
      <Paper variant="outlined"><TablePagination component="div" count={campaigns.data?.total || 0} page={page} onPageChange={(_, nextPage) => setPage(nextPage)} rowsPerPage={pageSize} onRowsPerPageChange={(event) => {
            setPageSize(Number(event.target.value));
            setPage(0);
        }} rowsPerPageOptions={[25, 50, 100, 200]} labelRowsPerPage={cc("controlCenter.full.161")}/></Paper>
      <Dialog open={budgetDialog} onClose={() => setBudgetDialog(false)} fullWidth maxWidth="xs">
        <DialogTitle>{cc("controlCenter.auto.160")}</DialogTitle>
        <DialogContent>
          <TextField autoFocus fullWidth type="number" label={cc("controlCenter.auto.161")} value={budget} onChange={(event) => setBudget(event.target.value)} inputProps={{ min: 0.01, step: 0.01 }} sx={{ mt: 1 }}/>
          <Alert severity="warning" sx={{ mt: 2 }}>{cc("controlCenter.auto.162")}</Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBudgetDialog(false)}>{cc("controlCenter.auto.075")}</Button>
          <Button variant="contained" disabled={!budget || Number(budget) <= 0} onClick={() => {
            setBudgetDialog(false);
            requestAction("SET_BUDGET", Math.round(Number(budget) * 1000000));
        }}>{cc("controlCenter.auto.163")}</Button>
        </DialogActions>
      </Dialog>
      <ActionPreviewDialog preview={preview} confirming={confirmAction.isPending} onClose={() => setPreview(null)} onConfirm={() => confirmAction.mutate()}/>
      {actionId && <Alert severity="info" icon={<CircularProgress size={18}/>}>{t("googleMode.actionRunning")}</Alert>}
      {completedAction?.execution_mode === "GOOGLE_TEST" && (<Paper variant="outlined" sx={{ p: 2 }}>
          <Typography variant="subtitle1" fontWeight={800}>{t("googleMode.resultTitle")}</Typography>
          <Typography variant="body2">{t("googleMode.status", { status: completedAction.status })}</Typography>
          {(completedAction.readback?.items || []).map((item: Record<string, any>) => (<Box key={item.campaign_id} sx={{ py: 1, borderBottom: 1, borderColor: "divider" }}>
              <Typography variant="body2" fontWeight={700}>{item.customer_id} · {item.object}</Typography>
              <Typography variant="body2">{item.field}: {String(item.before ?? "—")} → {String(item.actual ?? "—")}</Typography>
              <Typography variant="caption" color="text.secondary">Readback: {item.readback_verified ? t("googleMode.readbackVerified") : t("googleMode.readbackUnverified")} · {item.readback_at}</Typography>
            </Box>))}
          <Typography variant="caption" color="text.secondary">Request ID: {(completedAction.request_ids || []).join(", ") || "—"}</Typography>
        </Paper>)}
      <Snackbar open={Boolean(message)} autoHideDuration={5500} onClose={() => setMessage(null)}>
        <Alert severity="success" onClose={() => setMessage(null)}>{message}</Alert>
      </Snackbar>
    </Stack>);
}
function ActionPreviewDialog({ preview, confirming, onClose, onConfirm }: {
    preview: Record<string, any> | null;
    confirming: boolean;
    onClose: () => void;
    onConfirm: () => void;
}) {
    return (<Dialog open={Boolean(preview)} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{cc("controlCenter.auto.164")}</DialogTitle>
      <DialogContent dividers>
        {preview && (<Stack spacing={2}>
            <Alert severity={preview.validation?.ok ? "success" : "error"}>
              {preview.execution_mode === "GOOGLE_TEST"
                ? t("googleMode.previewFresh")
                : preview.validation?.ok ? t("googleMode.simulationPreviewReady") : t("googleMode.simulationPreviewError")}
            </Alert>
            <Box>
              <Typography fontWeight={800} gutterBottom>{cc("controlCenter.auto.168")}</Typography>
              {(preview.preview?.changes || []).map((change: Record<string, any>) => (<Box key={`${change.campaign_id}-${change.field}`} sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, py: 0.75, borderBottom: 1, borderColor: "divider" }}>
                  <Typography variant="body2">{String(change.before ?? "—")}</Typography>
                  <Typography variant="body2" fontWeight={700}>→ {String(change.after ?? "—")}</Typography>
                </Box>))}
            </Box>
            {(preview.preview?.warnings || []).map((warning: Record<string, any>) => (<Alert key={`${warning.campaign_id}-${warning.code}`} severity="warning">{warning.message}</Alert>))}
            <Typography variant="caption" color="text.secondary">{cc("controlCenter.auto.169")}</Typography>
          </Stack>)}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{cc("controlCenter.auto.075")}</Button>
        <Button variant="contained" disabled={confirming || !preview?.validation?.ok} onClick={onConfirm}>{preview?.execution_mode === "GOOGLE_TEST" ? t("googleMode.confirmTest") : cc("controlCenter.auto.170")}</Button>
      </DialogActions>
    </Dialog>);
}
function CreativesWorkspace() {
    const [view, setView] = useState<"ads" | "assets">("ads");
    const [search, setSearch] = useState("");
    const [policyStatus, setPolicyStatus] = useState("");
    const [assetType, setAssetType] = useState("");
    const ads = useQuery({
        queryKey: ["control-center-ads", search, policyStatus],
        queryFn: () => api.controlCenterAds({ search, policy_status: policyStatus, limit: 500 }),
        enabled: view === "ads",
        refetchInterval: 30000
    });
    const assets = useQuery({
        queryKey: ["control-center-assets", search, assetType],
        queryFn: () => api.controlCenterAssets({ search, asset_type: assetType, limit: 500 }),
        enabled: view === "assets",
        refetchInterval: 30000
    });
    return (<Stack spacing={2}>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
          <ToggleButtonGroup exclusive size="small" value={view} onChange={(_, value) => value && setView(value)}>
            <ToggleButton value="ads">{cc("controlCenter.full.076")}</ToggleButton>
            <ToggleButton value="assets">{cc("controlCenter.full.077")}</ToggleButton>
          </ToggleButtonGroup>
          <TextField size="small" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={cc("controlCenter.full.078")} InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small"/></InputAdornment> }} sx={{ minWidth: { md: 320 } }}/>
          {view === "ads" ? (<FormControl size="small" sx={{ minWidth: 190 }}>
            <InputLabel>{cc("controlCenter.auto.027")}</InputLabel>
            <Select value={policyStatus} label={cc("controlCenter.auto.027")} onChange={(event) => setPolicyStatus(event.target.value)}>
              <MenuItem value="">{cc("controlCenter.full.026")}</MenuItem>
              <MenuItem value="APPROVED">{cc("controlCenter.full.079")}</MenuItem>
              <MenuItem value="APPROVED_LIMITED">{cc("controlCenter.full.080")}</MenuItem>
              <MenuItem value="DISAPPROVED">{cc("controlCenter.full.081")}</MenuItem>
              <MenuItem value="UNDER_REVIEW">{cc("controlCenter.auto.235")}</MenuItem>
            </Select>
          </FormControl>) : (<FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel>{cc("controlCenter.full.082")}</InputLabel>
            <Select value={assetType} label={cc("controlCenter.full.082")} onChange={(event) => setAssetType(event.target.value)}>
              <MenuItem value="">{cc("controlCenter.full.083")}</MenuItem>
              <MenuItem value="IMAGE">{cc("controlCenter.full.084")}</MenuItem>
              <MenuItem value="YOUTUBE_VIDEO">YouTube</MenuItem>
              <MenuItem value="TEXT">{cc("controlCenter.full.085")}</MenuItem>
              <MenuItem value="CALL_TO_ACTION">CTA</MenuItem>
            </Select>
          </FormControl>)}
        </Stack>
      </Paper>
      {(ads.error || assets.error) && <Alert severity="error">{(ads.error || assets.error)?.message}</Alert>}
      {(ads.isLoading || assets.isLoading) && <LinearProgress />}
      {view === "ads" ? (<TableContainer component={Paper} variant="outlined" sx={{ overflowX: "auto" }}>
        <Table size="small" sx={{ minWidth: 980 }}>
          <TableHead><TableRow><TableCell>{cc("controlCenter.full.086")}</TableCell><TableCell>{cc("controlCenter.auto.157")}</TableCell><TableCell>{cc("controlCenter.auto.117")}</TableCell><TableCell>{cc("controlCenter.auto.027")}</TableCell><TableCell>Final URL</TableCell><TableCell>{cc("controlCenter.full.087")}</TableCell><TableCell>{cc("controlCenter.auto.158")}</TableCell></TableRow></TableHead>
          <TableBody>
            {(ads.data?.items || []).map((ad: ControlCenterAd) => (<TableRow key={ad.id}>
              <TableCell><Typography fontWeight={700}>{ad.name || ad.ad_id}</Typography><Typography variant="caption" color="text.secondary">{ad.resource_name}</Typography></TableCell>
              <TableCell>{ad.ad_type || "—"}</TableCell>
              <TableCell><Chip size="small" variant="outlined" label={ad.status || "UNKNOWN"}/></TableCell>
              <TableCell><Chip size="small" color={ad.policy_status === "DISAPPROVED" ? "error" : ad.policy_status === "APPROVED" ? "success" : "warning"} variant="outlined" label={ad.policy_status || cc("controlCenter.auto.229")}/></TableCell>
              <TableCell><Truncated text={ad.final_urls?.join(", ") || "—"}/></TableCell>
              <TableCell><Truncated text={policyTopicText(ad.disapproval_reasons)}/></TableCell>
              <TableCell>{ad.last_synced_at ? formatDate(ad.last_synced_at) : "—"}</TableCell>
            </TableRow>))}
            {!ads.data?.items.length && <EmptyTableRow columns={7} text={cc("controlCenter.full.088")}/>}
          </TableBody>
        </Table>
      </TableContainer>) : (<Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" }, gap: 1 }}>
        {(assets.data?.items || []).map((asset: ControlCenterAsset) => (<Paper key={asset.id} variant="outlined" sx={{ p: 1.5, minWidth: 0 }}>
          {asset.image_url && <Box component="img" src={asset.image_url} alt={asset.name || "Google Ads asset"} sx={{ width: "100%", aspectRatio: "16 / 9", objectFit: "contain", bgcolor: "action.hover", mb: 1 }}/>}
          <Typography fontWeight={700} noWrap>{asset.name || asset.asset_id}</Typography>
          <Typography variant="caption" color="text.secondary">{asset.asset_type || "UNKNOWN"}{asset.image_width && asset.image_height ? ` · ${asset.image_width}×${asset.image_height}` : ""}</Typography>
          {asset.youtube_video_id && <Typography variant="body2">YouTube: {asset.youtube_video_id}</Typography>}
          {asset.processing_note && <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>{asset.processing_note}</Typography>}
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>{asset.last_synced_at ? formatDate(asset.last_synced_at) : cc("controlCenter.full.089")}</Typography>
        </Paper>))}
        {!assets.data?.items.length && <Typography color="text.secondary">{cc("controlCenter.full.090")}</Typography>}
      </Box>)}
    </Stack>);
}
function ModerationWorkspace() {
    const [onlyIssues, setOnlyIssues] = useState(true);
    const moderation = useQuery({
        queryKey: ["control-center-moderation", onlyIssues],
        queryFn: () => api.controlCenterModeration({ only_issues: onlyIssues }),
        refetchInterval: 30000
    });
    return (<Stack spacing={2}>
      <Alert severity="info">{localizedModerationNote(moderation.data?.data_note)}</Alert>
      <FormControlLabel control={<Switch checked={onlyIssues} onChange={(event) => setOnlyIssues(event.target.checked)}/>} label={cc("controlCenter.full.092")}/>
      {moderation.isLoading && <LinearProgress />}
      {moderation.error && <Alert severity="error">{moderation.error.message}</Alert>}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead><TableRow><TableCell>{cc("controlCenter.full.086")}</TableCell><TableCell>{cc("controlCenter.auto.018")}</TableCell><TableCell>{cc("controlCenter.full.093")}</TableCell><TableCell>{cc("controlCenter.auto.124")}</TableCell></TableRow></TableHead>
          <TableBody>
            {(moderation.data?.items || []).map((ad) => (<TableRow key={ad.id}>
              <TableCell>{ad.name || ad.ad_id}</TableCell>
              <TableCell><Chip size="small" color={ad.policy_status === "DISAPPROVED" ? "error" : "warning"} label={ad.policy_status || "UNKNOWN"}/></TableCell>
              <TableCell><Truncated text={policyTopicText(ad.disapproval_reasons)}/></TableCell>
              <TableCell>{ad.last_synced_at ? formatDate(ad.last_synced_at) : "—"}</TableCell>
            </TableRow>))}
            {!moderation.data?.items.length && <EmptyTableRow columns={4} text={onlyIssues ? cc("controlCenter.full.094") : cc("controlCenter.full.095")}/>}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>);
}
function VerificationWorkspace() {
    const [statusFilter, setStatusFilter] = useState("");
    const verification = useQuery({
        queryKey: ["control-center-verification", statusFilter],
        queryFn: () => api.controlCenterVerification({ status_filter: statusFilter }),
        refetchInterval: 30000
    });
    return (<Stack spacing={2}>
      <Alert severity="info">{cc("controlCenter.full.096")}</Alert>
      <FormControl size="small" sx={{ maxWidth: 260 }}>
        <InputLabel>{cc("controlCenter.auto.117")}</InputLabel>
        <Select value={statusFilter} label={cc("controlCenter.auto.117")} onChange={(event) => setStatusFilter(event.target.value)}>
          <MenuItem value="">{cc("controlCenter.full.026")}</MenuItem>
          {["REQUIRED", "PENDING_USER_ACTION", "PENDING_REVIEW", "SUCCESS", "FAILURE", "NOT_REQUIRED", "UNAVAILABLE"].map((value) => <MenuItem key={value} value={value}>{verificationLabel(value)}</MenuItem>)}
        </Select>
      </FormControl>
      {verification.isLoading && <LinearProgress />}
      {verification.error && <Alert severity="error">{verification.error.message}</Alert>}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead><TableRow><TableCell>{cc("controlCenter.auto.104")}</TableCell><TableCell>{cc("controlCenter.auto.117")}</TableCell><TableCell>{cc("controlCenter.auto.123")}</TableCell><TableCell>{cc("controlCenter.full.097")}</TableCell><TableCell align="right">{cc("controlCenter.full.098")}</TableCell></TableRow></TableHead>
          <TableBody>
            {(verification.data || []).map((item) => (<TableRow key={item.account_id}>
              <TableCell><Typography fontWeight={700}>{item.account_name}</Typography><Typography variant="caption">{formatCustomerId(item.customer_id)}</Typography></TableCell>
              <TableCell><Chip size="small" variant="outlined" label={verificationLabel(item.status)}/></TableCell>
              <TableCell>{item.deadline ? formatDate(item.deadline) : "—"}</TableCell>
              <TableCell>{item.checked_at ? formatDate(item.checked_at) : "—"}</TableCell>
              <TableCell align="right">{item.action_url ? <Button component="a" href={item.action_url} target="_blank" rel="noreferrer">{cc("controlCenter.full.099")}</Button> : "—"}</TableCell>
            </TableRow>))}
            {!verification.data?.length && <EmptyTableRow columns={5} text={cc("controlCenter.full.100")}/>}
          </TableBody>
        </Table>
      </TableContainer>
    </Stack>);
}
function ViewsWorkspace({ isAdmin }: {
    isAdmin: boolean;
}) {
    const queryClient = useQueryClient();
    const [section, setSection] = useState<"views" | "structure" | "conversions">("views");
    const [rename, setRename] = useState<SavedControlCenterView | null>(null);
    const [renameValue, setRenameValue] = useState("");
    const [geoDialog, setGeoDialog] = useState(false);
    const [geoName, setGeoName] = useState("");
    const [geoIso, setGeoIso] = useState("");
    const [mappingAccountId, setMappingAccountId] = useState("");
    const [semanticType, setSemanticType] = useState<"REGISTRATION" | "DEPOSIT">("REGISTRATION");
    const [catalog, setCatalog] = useState<Record<string, any> | null>(null);
    const [catalogResource, setCatalogResource] = useState("");
    const views = useQuery({ queryKey: ["control-center-saved-views"], queryFn: api.controlCenterSavedViews });
    const geos = useQuery({ queryKey: ["control-center-geos"], queryFn: api.controlCenterGeos });
    const mcc = useQuery({ queryKey: ["control-center-mcc"], queryFn: () => api.controlCenterMcc({}) });
    const accounts = useQuery({ queryKey: ["control-center-accounts-for-settings"], queryFn: () => api.controlCenterAccounts({ quick_filter: "all", limit: 500 }) });
    const mappings = useQuery({ queryKey: ["control-center-conversion-mappings"], queryFn: () => api.controlCenterConversionMappings({}) });
    const refreshViews = () => queryClient.invalidateQueries({ queryKey: ["control-center-saved-views"] });
    const updateView = useMutation({
        mutationFn: ({ id, payload }: {
            id: string;
            payload: Record<string, unknown>;
        }) => api.updateControlCenterSavedView(id, payload),
        onSuccess: () => {
            setRename(null);
            refreshViews();
        }
    });
    const duplicateView = useMutation({ mutationFn: api.duplicateControlCenterSavedView, onSuccess: refreshViews });
    const deleteView = useMutation({ mutationFn: api.deleteControlCenterSavedView, onSuccess: refreshViews });
    const assignGeo = useMutation({
        mutationFn: ({ id, geoId }: {
            id: string;
            geoId: string | null;
        }) => api.assignControlCenterMccGeo(id, geoId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["control-center-mcc"] });
            invalidateControlCenter(queryClient);
        }
    });
    const createGeo = useMutation({
        mutationFn: () => api.createControlCenterGeo({ iso_code: geoIso, display_name: geoName, color: "#2563a8", is_active: true }),
        onSuccess: () => {
            setGeoDialog(false);
            setGeoIso("");
            setGeoName("");
            queryClient.invalidateQueries({ queryKey: ["control-center-geos"] });
        }
    });
    const loadCatalog = useMutation({
        mutationFn: () => api.controlCenterConversionCatalog(mappingAccountId),
        onSuccess: (result) => {
            setCatalog(result);
            setCatalogResource("");
        }
    });
    const createMapping = useMutation({
        mutationFn: () => {
            const action = (catalog?.items || []).find((item: Record<string, any>) => item.resource_name === catalogResource);
            const account = accounts.data?.items.find((item) => item.id === mappingAccountId);
            return api.createControlCenterConversionMapping({
                connection_id: account?.connection_id,
                account_id: mappingAccountId,
                semantic_type: semanticType,
                resource_name: action?.resource_name,
                conversion_action_id: action?.conversion_action_id,
                name: action?.name,
                owner_customer_id: action?.owner_customer_id,
                is_cross_account: action?.owner_customer_id !== account?.customer_id,
                is_active: true
            });
        },
        onSuccess: () => {
            setCatalogResource("");
            queryClient.invalidateQueries({ queryKey: ["control-center-conversion-mappings"] });
        }
    });
    const deleteMapping = useMutation({ mutationFn: api.deleteControlCenterConversionMapping, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["control-center-conversion-mappings"] }) });
    const error = views.error || geos.error || mcc.error || accounts.error || mappings.error || updateView.error || duplicateView.error || deleteView.error || assignGeo.error || createGeo.error || loadCatalog.error || createMapping.error || deleteMapping.error;
    return (<Stack spacing={2}>
      <ToggleButtonGroup exclusive size="small" value={section} onChange={(_, value) => value && setSection(value)}>
        <ToggleButton value="views">{cc("controlCenter.full.101")}</ToggleButton>
        <ToggleButton value="structure">{cc("controlCenter.full.102")}</ToggleButton>
        <ToggleButton value="conversions">{cc("controlCenter.full.196")}</ToggleButton>
      </ToggleButtonGroup>
      {error && <Alert severity="error">{error.message}</Alert>}
      {section === "views" && (<Stack spacing={1}>
        {(views.data || []).map((view) => (<Paper key={view.id} variant="outlined" sx={{ p: 1.5, display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
          <Box sx={{ flex: 1, minWidth: 220 }}>
            <Typography fontWeight={700}>{localizedSavedViewName(view.name)}</Typography>
            <Typography variant="caption" color="text.secondary">{view.is_shared ? cc("controlCenter.full.103") : cc("controlCenter.full.104")}{view.is_default ? cc("controlCenter.full.105") : ""}{!view.is_owner ? cc("controlCenter.full.106") : ""}</Typography>
          </Box>
          <Button size="small" startIcon={<AddIcon />} onClick={() => duplicateView.mutate(view.id)}>{cc("controlCenter.full.107")}</Button>
          {view.is_owner && <Button size="small" startIcon={<EditOutlinedIcon />} onClick={() => {
                        setRename(view);
                        setRenameValue(view.name);
                    }}>{cc("controlCenter.full.108")}</Button>}
          {view.is_owner && !view.is_default && <Button size="small" onClick={() => updateView.mutate({ id: view.id, payload: { is_default: true } })}>{cc("controlCenter.auto.136")}</Button>}
          {view.is_owner && isAdmin && <FormControlLabel control={<Switch size="small" checked={view.is_shared} onChange={(event) => updateView.mutate({ id: view.id, payload: { is_shared: event.target.checked } })}/>} label={cc("controlCenter.full.103")}/>}
          {view.is_owner && <Tooltip title={cc("controlCenter.full.109")}><IconButton color="error" onClick={() => deleteView.mutate(view.id)}><DeleteOutlineIcon /></IconButton></Tooltip>}
        </Paper>))}
        {!views.data?.length && <Typography color="text.secondary">{cc("controlCenter.full.110")}</Typography>}
      </Stack>)}
      {section === "structure" && (<Stack spacing={1.5}>
        <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, alignItems: "center" }}>
          <Typography variant="h6">{cc("controlCenter.full.111")}</Typography>
          {isAdmin && <Button startIcon={<AddIcon />} onClick={() => setGeoDialog(true)}>{cc("controlCenter.full.112")}</Button>}
        </Box>
        {(mcc.data || []).filter((item: ControlCenterMcc) => !item.is_root).map((item: ControlCenterMcc) => (<Box key={item.id} sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "minmax(220px, 1fr) minmax(180px, 260px)" }, gap: 1, alignItems: "center", py: 1, borderBottom: 1, borderColor: "divider" }}>
          <Box><Typography fontWeight={700}>{item.descriptive_name || formatCustomerId(item.customer_id)}</Typography><Typography variant="caption" color="text.secondary">{formatCustomerId(item.customer_id)}{cc("controlCenter.full.113")}{item.hierarchy_level ?? "—"}</Typography></Box>
          <FormControl size="small">
            <InputLabel>GEO</InputLabel>
            <Select value={item.geo?.id || ""} label="GEO" disabled={!isAdmin} onChange={(event) => assignGeo.mutate({ id: item.id, geoId: event.target.value || null })}>
              <MenuItem value="">{cc("controlCenter.full.062")}</MenuItem>
              {(geos.data || []).map((geo) => <MenuItem key={geo.id} value={geo.id}>{geo.display_name}</MenuItem>)}
            </Select>
          </FormControl>
        </Box>))}
        {!mcc.data?.some((item) => !item.is_root) && <Typography color="text.secondary">{cc("controlCenter.full.114")}</Typography>}
      </Stack>)}
      {section === "conversions" && (<Stack spacing={2}>
        <Alert severity="info">{cc("controlCenter.full.115")}</Alert>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(240px, 1fr) 180px auto" }, gap: 1 }}>
          <FormControl size="small"><InputLabel>{cc("controlCenter.auto.104")}</InputLabel><Select value={mappingAccountId} label={cc("controlCenter.auto.104")} onChange={(event) => {
                setMappingAccountId(event.target.value);
                setCatalog(null);
            }}>{(accounts.data?.items || []).map((account) => <MenuItem key={account.id} value={account.id}>{account.display_name} · {formatCustomerId(account.customer_id)}</MenuItem>)}</Select></FormControl>
          <FormControl size="small"><InputLabel>{cc("controlCenter.auto.157")}</InputLabel><Select value={semanticType} label={cc("controlCenter.auto.157")} onChange={(event) => setSemanticType(event.target.value as "REGISTRATION" | "DEPOSIT")}><MenuItem value="REGISTRATION">{cc("controlCenter.full.116")}</MenuItem><MenuItem value="DEPOSIT">{cc("controlCenter.full.117")}</MenuItem></Select></FormControl>
          <Button variant="outlined" disabled={!mappingAccountId || loadCatalog.isPending} onClick={() => loadCatalog.mutate()}>{cc("controlCenter.full.118")}</Button>
        </Box>
        {catalog && (<Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr auto" }, gap: 1 }}>
          <FormControl size="small"><InputLabel>Conversion Action</InputLabel><Select value={catalogResource} label="Conversion Action" onChange={(event) => setCatalogResource(event.target.value)}>{(catalog.items || []).map((item: Record<string, any>) => <MenuItem key={item.resource_name} value={item.resource_name}>{item.name || item.conversion_action_id} · {item.category}</MenuItem>)}</Select></FormControl>
          <Button variant="contained" disabled={!catalogResource || createMapping.isPending || !isAdmin} onClick={() => createMapping.mutate()}>{cc("controlCenter.full.119")}</Button>
        </Box>)}
        <TableContainer component={Paper} variant="outlined"><Table size="small"><TableHead><TableRow><TableCell>{cc("controlCenter.auto.157")}</TableCell><TableCell>{cc("controlCenter.auto.015")}</TableCell><TableCell>{cc("controlCenter.full.120")}</TableCell><TableCell>{cc("controlCenter.full.121")}</TableCell><TableCell /></TableRow></TableHead><TableBody>
          {(mappings.data || []).map((mapping) => (<TableRow key={mapping.id}><TableCell>{mapping.semantic_type === "REGISTRATION" ? cc("controlCenter.full.116") : cc("controlCenter.full.117")}</TableCell><TableCell>{mapping.name || mapping.conversion_action_id}</TableCell><TableCell>{mapping.scope_type === "ACCOUNT" ? cc("controlCenter.auto.104") : cc("controlCenter.full.021")}</TableCell><TableCell>{mapping.last_synced_at ? formatDate(mapping.last_synced_at) : cc("controlCenter.full.122")}</TableCell><TableCell align="right">{isAdmin && <IconButton color="error" onClick={() => deleteMapping.mutate(mapping.id)}><DeleteOutlineIcon /></IconButton>}</TableCell></TableRow>))}
          {!mappings.data?.length && <EmptyTableRow columns={5} text={cc("controlCenter.full.123")}/>}
        </TableBody></Table></TableContainer>
      </Stack>)}
      <Dialog open={Boolean(rename)} onClose={() => setRename(null)} fullWidth maxWidth="xs"><DialogTitle>{cc("controlCenter.full.124")}</DialogTitle><DialogContent><TextField autoFocus fullWidth label={cc("controlCenter.auto.073")} value={renameValue} onChange={(event) => setRenameValue(event.target.value)} sx={{ mt: 1 }}/></DialogContent><DialogActions><Button onClick={() => setRename(null)}>{cc("controlCenter.auto.075")}</Button><Button variant="contained" disabled={!renameValue.trim()} onClick={() => rename && updateView.mutate({ id: rename.id, payload: { name: renameValue.trim() } })}>{cc("controlCenter.auto.076")}</Button></DialogActions></Dialog>
      <Dialog open={geoDialog} onClose={() => setGeoDialog(false)} fullWidth maxWidth="xs"><DialogTitle>{cc("controlCenter.full.125")}</DialogTitle><DialogContent><Stack spacing={1.5} sx={{ mt: 1 }}><TextField label={cc("controlCenter.full.126")} value={geoIso} onChange={(event) => setGeoIso(event.target.value.toUpperCase())}/><TextField label={cc("controlCenter.auto.073")} value={geoName} onChange={(event) => setGeoName(event.target.value)}/></Stack></DialogContent><DialogActions><Button onClick={() => setGeoDialog(false)}>{cc("controlCenter.auto.075")}</Button><Button variant="contained" disabled={geoIso.length < 2 || geoName.length < 2 || createGeo.isPending} onClick={() => createGeo.mutate()}>{cc("controlCenter.auto.103")}</Button></DialogActions></Dialog>
    </Stack>);
}
function SyncWorkspace({ canEdit }: {
    canEdit: boolean;
}) {
    const queryClient = useQueryClient();
    const [estimate, setEstimate] = useState<Record<string, any> | null>(null);
    const runs = useQuery({ queryKey: ["control-center-sync-runs"], queryFn: api.controlCenterSyncRuns, refetchInterval: 5000 });
    const estimateSync = useMutation({
        mutationFn: (scope: "WORKING" | "ALL") => api.estimateControlCenterSync(scope, []),
        onSuccess: (result, scope) => setEstimate({ ...result, scope })
    });
    const start = useMutation({
        mutationFn: () => api.startControlCenterSync(estimate!.scope, [], estimate!.estimate_token),
        onSuccess: () => {
            setEstimate(null);
            queryClient.invalidateQueries({ queryKey: ["control-center-sync-runs"] });
        }
    });
    return (<Stack spacing={2}>
      <Alert severity="info">{cc("controlCenter.full.127")}</Alert>
      <Paper variant="outlined" sx={{ p: 2, display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center" }}>
        <Button startIcon={<RefreshIcon />} disabled={!canEdit || estimateSync.isPending} onClick={() => estimateSync.mutate("WORKING")}>{cc("controlCenter.full.128")}</Button>
        <Button startIcon={<CloudSyncOutlinedIcon />} disabled={!canEdit || estimateSync.isPending} onClick={() => estimateSync.mutate("ALL")}>{cc("controlCenter.full.129")}</Button>
        <Box sx={{ flex: 1 }}/>
        <Button startIcon={<RefreshIcon />} onClick={() => runs.refetch()}>{cc("controlCenter.full.130")}</Button>
      </Paper>
      {(runs.error || estimateSync.error || start.error) && <Alert severity="error">{(runs.error || estimateSync.error || start.error)?.message}</Alert>}
      {runs.isLoading && <LinearProgress />}
      <TableContainer component={Paper} variant="outlined" sx={{ overflowX: "auto" }}><Table size="small" sx={{ minWidth: 900 }}><TableHead><TableRow><TableCell>{cc("controlCenter.full.131")}</TableCell><TableCell>{cc("controlCenter.full.120")}</TableCell><TableCell>{cc("controlCenter.auto.117")}</TableCell><TableCell align="right">{cc("controlCenter.auto.037")}</TableCell><TableCell align="right">{cc("controlCenter.full.132")}</TableCell><TableCell>{cc("controlCenter.full.133")}</TableCell><TableCell>Request ID</TableCell><TableCell>{cc("controlCenter.full.134")}</TableCell></TableRow></TableHead><TableBody>
        {(runs.data || []).map((run) => (<TableRow key={run.id}><TableCell>{formatDate(run.created_at)}</TableCell><TableCell>{run.scope}</TableCell><TableCell><Chip size="small" color={run.status === "SUCCEEDED" ? "success" : run.status === "FAILED" ? "error" : "default"} label={run.status}/></TableCell><TableCell align="right">{run.successful_accounts}/{run.successful_accounts + run.failed_accounts}</TableCell><TableCell align="right">{run.actual_operations}</TableCell><TableCell>{run.duration_ms === null ? "—" : ("" + (run.duration_ms / 1000).toFixed(1) + cc("controlCenter.full.135"))}</TableCell><TableCell><Truncated text={(run.request_ids || []).join(", ") || "—"}/></TableCell><TableCell>{run.failed_accounts ? ("" + run.failed_accounts + cc("controlCenter.full.053")) : "—"}</TableCell></TableRow>))}
        {!runs.data?.length && <EmptyTableRow columns={8} text={cc("controlCenter.full.136")}/>}
      </TableBody></Table></TableContainer>
      <SyncEstimateDialog data={estimate} loading={start.isPending} onClose={() => setEstimate(null)} onStart={() => start.mutate()}/>
    </Stack>);
}
function ProblemsWorkspace({ canEdit }: {
    canEdit: boolean;
}) {
    const queryClient = useQueryClient();
    const [severity, setSeverity] = useState("");
    const [state, setState] = useState("");
    const problems = useQuery({
        queryKey: ["control-center-problems", severity, state],
        queryFn: () => api.controlCenterProblems({ severity, state_filter: state }),
        refetchInterval: 30000
    });
    const update = useMutation({
        mutationFn: ({ id, nextState }: {
            id: string;
            nextState: string;
        }) => api.updateControlCenterProblem(id, nextState),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["control-center-problems"] });
            queryClient.invalidateQueries({ queryKey: ["control-center-summary"] });
        }
    });
    return (<Stack spacing={2}>
      {problems.error && <Alert severity="error">{problems.error.message}</Alert>}
      <Paper variant="outlined" sx={{ p: 2, display: "flex", gap: 1, flexWrap: "wrap" }}>
        <FormControl size="small" sx={{ minWidth: 170 }}>
          <InputLabel>{cc("controlCenter.auto.171")}</InputLabel>
          <Select value={severity} label={cc("controlCenter.auto.171")} onChange={(e) => setSeverity(e.target.value)}>
            <MenuItem value="">{cc("controlCenter.auto.054")}</MenuItem>
            <MenuItem value="ERROR">{cc("controlCenter.auto.172")}</MenuItem>
            <MenuItem value="WARNING">{cc("controlCenter.auto.173")}</MenuItem>
            <MenuItem value="INFO">{cc("controlCenter.auto.174")}</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 170 }}>
          <InputLabel>{cc("controlCenter.auto.122")}</InputLabel>
          <Select value={state} label={cc("controlCenter.auto.122")} onChange={(e) => setState(e.target.value)}>
            <MenuItem value="">{cc("controlCenter.auto.175")}</MenuItem>
            <MenuItem value="NEW">{cc("controlCenter.auto.176")}</MenuItem>
            <MenuItem value="SEEN">{cc("controlCenter.auto.177")}</MenuItem>
            <MenuItem value="RESOLVED">{cc("controlCenter.auto.178")}</MenuItem>
          </Select>
        </FormControl>
        <Box sx={{ flex: 1 }}/>
        <Button startIcon={<RefreshIcon />} onClick={() => problems.refetch()}>{cc("controlCenter.auto.179")}</Button>
      </Paper>
      {problems.isLoading && <LinearProgress />}
      <Stack spacing={1}>
        {(problems.data || []).map((problem) => (<Paper variant="outlined" key={problem.id} sx={{
                p: 2,
                display: "grid",
                gridTemplateColumns: { xs: "1fr", md: "160px 1fr 220px" },
                gap: 2,
                borderLeft: 4,
                borderLeftColor: problem.severity === "ERROR" ? "error.main" : "warning.main"
            }}>
            <Box>
              <Chip size="small" color={severityColor(problem.severity)} label={severityLabel(problem.severity)}/>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                {formatDate(problem.last_seen_at)}
              </Typography>
            </Box>
            <Box>
              <Typography fontWeight={800}>{localizedProblemTitle(problem)}</Typography>
              <Typography>{localizedProblemDescription(problem)}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
                {problem.account_name || cc("controlCenter.auto.180")}
                {problem.customer_id ? ` · ${formatCustomerId(problem.customer_id)}` : ""}
              </Typography>
              {(problem.google_code || problem.request_id) && (<Typography variant="caption" color="text.secondary">
                  {problem.google_code || ""}
                  {problem.request_id ? ` · Request ID: ${problem.request_id}` : ""}
                </Typography>)}
            </Box>
            <FormControl size="small">
              <InputLabel>{cc("controlCenter.auto.122")}</InputLabel>
              <Select value={problem.state} label={cc("controlCenter.auto.122")} disabled={!canEdit || update.isPending} onChange={(event) => update.mutate({ id: problem.id, nextState: event.target.value })}>
                <MenuItem value="NEW">{cc("controlCenter.auto.176")}</MenuItem>
                <MenuItem value="SEEN">{cc("controlCenter.auto.177")}</MenuItem>
                <MenuItem value="RESOLVED">{cc("controlCenter.auto.178")}</MenuItem>
              </Select>
            </FormControl>
          </Paper>))}
        {!problems.data?.length && (<Paper variant="outlined" sx={{ p: 5, textAlign: "center" }}>
            <Typography fontWeight={800}>{cc("controlCenter.auto.181")}</Typography>
          </Paper>)}
      </Stack>
    </Stack>);
}
function HistoryWorkspace() {
    const [eventType, setEventType] = useState("");
    const history = useQuery({
        queryKey: ["control-center-history", eventType],
        queryFn: () => api.controlCenterHistory({ event_type: eventType, limit: 300 }),
        refetchInterval: 30000
    });
    return (<Stack spacing={2}>
      {history.error && <Alert severity="error">{history.error.message}</Alert>}
      <Paper variant="outlined" sx={{ p: 2, display: "flex", gap: 1, alignItems: "center" }}>
        <FormControl size="small" sx={{ minWidth: 260 }}>
          <InputLabel>{cc("controlCenter.auto.182")}</InputLabel>
          <Select value={eventType} label={cc("controlCenter.auto.182")} onChange={(e) => setEventType(e.target.value)}>
            <MenuItem value="">{cc("controlCenter.auto.183")}</MenuItem>
            <MenuItem value="WORK_STATUS_CHANGED">{cc("controlCenter.auto.184")}</MenuItem>
            <MenuItem value="NOTE_CHANGED">{cc("controlCenter.auto.185")}</MenuItem>
            <MenuItem value="TAG_ADDED">{cc("controlCenter.auto.030")}</MenuItem>
            <MenuItem value="SYNC_SUCCEEDED">{cc("controlCenter.auto.031")}</MenuItem>
            <MenuItem value="MANUAL_ACTION_SIMULATED">{cc("controlCenter.auto.186")}</MenuItem>
          </Select>
        </FormControl>
        <Box sx={{ flex: 1 }}/>
        <Button startIcon={<RefreshIcon />} onClick={() => history.refetch()}>{cc("controlCenter.auto.179")}</Button>
      </Paper>
      {history.isLoading && <LinearProgress />}
      <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2.5 } }}>
        <Stack>
          {(history.data || []).map((event, index) => (<Box key={event.id} sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", sm: "160px 180px 1fr" },
                gap: 1,
                py: 1.25,
                borderBottom: index < (history.data?.length || 0) - 1 ? 1 : 0,
                borderColor: "divider"
            }}>
              <Typography variant="body2" color="text.secondary">{formatDate(event.occurred_at)}</Typography>
              <Chip size="small" variant="outlined" label={eventTypeLabel(event.event_type)} sx={{ width: "fit-content" }}/>
              <Box>
                <Typography>{localizedEventSummary(event)}</Typography>
                <Typography variant="caption" color="text.secondary">{cc("controlCenter.auto.187")}{event.source}</Typography>
              </Box>
            </Box>))}
          {!history.data?.length && <Typography color="text.secondary">{cc("controlCenter.auto.188")}</Typography>}
        </Stack>
      </Paper>
    </Stack>);
}
function RulesWorkspace({ canEdit }: {
    canEdit: boolean;
}) {
    const queryClient = useQueryClient();
    const [dialog, setDialog] = useState(false);
    const [name, setName] = useState("");
    const [field, setField] = useState("campaign.metrics.cost_micros");
    const [operator, setOperator] = useState("gte");
    const [value, setValue] = useState("100000000");
    const [action, setAction] = useState("NOTIFY");
    const [budgetAmount, setBudgetAmount] = useState("100");
    const [priority, setPriority] = useState("100");
    const [intervalMinutes, setIntervalMinutes] = useState("15");
    const [liveRule, setLiveRule] = useState<ControlCenterRule | null>(null);
    const [message, setMessage] = useState<string | null>(null);
    const rules = useQuery({ queryKey: ["control-center-rules"], queryFn: api.controlCenterRules });
    const killSwitch = useQuery({
        queryKey: ["control-center-kill-switch"],
        queryFn: api.controlCenterKillSwitch
    });
    const create = useMutation({
        mutationFn: () => api.createControlCenterRule({
            name,
            enabled: false,
            mode: "DRY_RUN",
            scope: { work_statuses: ["WORKING"] },
            condition_logic: "AND",
            conditions: [{ field, operator, value: Number(value) }],
            actions: [{
                    type: action,
                    ...(action === "PROPOSE_BUDGET"
                        ? { amount_micros: Math.round(Number(budgetAmount) * 1000000) }
                        : {})
                }],
            safeguards: {
                max_data_age_hours: 24,
                conversion_lag_hours: 24,
                minimum_runtime_hours: 24,
                minimum_spend_micros: 10000000,
                block_manual_paused_enable: true
            },
            cooldown_minutes: 1440,
            max_actions_per_run: 10,
            max_actions_per_day: 25,
            priority: Number(priority),
            schedule: { interval_minutes: Number(intervalMinutes) },
            max_budget_change_percent: 20
        }),
        onSuccess: () => {
            setDialog(false);
            setName("");
            setMessage(cc("controlCenter.auto.189"));
            queryClient.invalidateQueries({ queryKey: ["control-center-rules"] });
        }
    });
    const update = useMutation({
        mutationFn: ({ id, payload }: {
            id: string;
            payload: Record<string, unknown>;
        }) => api.updateControlCenterRule(id, payload),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["control-center-rules"] })
    });
    const evaluate = useMutation({
        mutationFn: (id: string) => api.evaluateControlCenterRule(id),
        onSuccess: (result) => {
            setMessage(cc("controlCenter.auto.190") + result.evaluated + cc("controlCenter.auto.191") + result.matched + cc("controlCenter.auto.192"));
            queryClient.invalidateQueries({ queryKey: ["control-center-rules"] });
        }
    });
    const setKillSwitch = useMutation({
        mutationFn: api.updateControlCenterKillSwitch,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["control-center-kill-switch"] })
    });
    const changeLiveMode = useMutation({
        mutationFn: ({ id, confirmation }: {
            id: string;
            confirmation: "ENABLE LIVE RULES" | "RETURN TO DRY RUN";
        }) => api.changeControlCenterRuleLiveMode(id, confirmation),
        onSuccess: (result) => {
            setLiveRule(null);
            setMessage(result.mode === "LIVE"
                ? cc("controlCenter.full.142")
                : cc("controlCenter.full.143"));
            queryClient.invalidateQueries({ queryKey: ["control-center-rules"] });
        }
    });
    const error = rules.error || killSwitch.error || create.error || update.error || evaluate.error || setKillSwitch.error || changeLiveMode.error;
    return (<Stack spacing={2}>
      {error && <Alert severity="error">{error.message}</Alert>}
      <Paper variant="outlined" sx={{
            p: 2,
            display: "flex",
            alignItems: { xs: "flex-start", sm: "center" },
            flexDirection: { xs: "column", sm: "row" },
            gap: 2,
            borderColor: killSwitch.data?.active ? "warning.main" : "divider"
        }}>
        <Box sx={{ flex: 1 }}>
          <Typography fontWeight={800}>{cc("controlCenter.auto.193")}</Typography>
          <Typography color="text.secondary">
            {killSwitch.data?.active
            ? cc("controlCenter.auto.194") : cc("controlCenter.auto.195")}
          </Typography>
        </Box>
        <FormControlLabel control={<Switch checked={killSwitch.data?.active ?? true} disabled={!canEdit || setKillSwitch.isPending} onChange={(event) => setKillSwitch.mutate(event.target.checked)}/>} label={killSwitch.data?.active ? cc("controlCenter.auto.196") : cc("controlCenter.auto.197")}/>
        <Button variant="contained" startIcon={<AddIcon />} disabled={!canEdit} onClick={() => setDialog(true)}>{cc("controlCenter.auto.198")}</Button>
      </Paper>
      <Alert severity="info">{cc("controlCenter.auto.199")}</Alert>
      <Stack spacing={1}>
        {(rules.data || []).map((rule: ControlCenterRule) => (<Paper key={rule.id} variant="outlined" sx={{
                p: 2,
                display: "grid",
                gridTemplateColumns: { xs: "1fr", md: "minmax(240px, 1fr) 150px 180px 150px 150px" },
                gap: 2,
                alignItems: "center"
            }}>
            <Box>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography fontWeight={800}>{rule.name}</Typography>
                <Chip size="small" color={rule.mode === "LIVE" ? "warning" : "info"} variant="outlined" label={rule.mode}/>
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{cc("controlCenter.auto.200")}{rule.conditions.length}{cc("controlCenter.auto.201")}{rule.actions.length} · {cc("controlCenter.full.139")}
                {" "}{rule.cooldown_minutes}{cc("controlCenter.auto.202")} · {cc("controlCenter.full.140")} {rule.priority}</Typography>
            </Box>
            <FormControlLabel control={<Switch checked={rule.enabled} disabled={!canEdit || update.isPending} onChange={(event) => update.mutate({ id: rule.id, payload: { enabled: event.target.checked } })}/>} label={rule.enabled ? cc("controlCenter.auto.203") : cc("controlCenter.auto.204")}/>
            <Typography variant="body2" color="text.secondary">{cc("controlCenter.auto.205")}<br />{rule.last_evaluated_at ? formatDate(rule.last_evaluated_at) : cc("controlCenter.auto.206")}
            </Typography>
            <Button variant="outlined" startIcon={<PlayCircleOutlineIcon />} disabled={!canEdit || evaluate.isPending} onClick={() => evaluate.mutate(rule.id)}>{cc("controlCenter.auto.207")}</Button>
            <Button color={rule.mode === "LIVE" ? "warning" : "primary"} variant="outlined" disabled={!canEdit || changeLiveMode.isPending} onClick={() => setLiveRule(rule)}>
              {rule.mode === "LIVE" ? cc("controlCenter.full.141") : cc("controlCenter.full.144")}
            </Button>
          </Paper>))}
        {!rules.data?.length && (<Paper variant="outlined" sx={{ p: 5, textAlign: "center" }}>
            <Typography fontWeight={800}>{cc("controlCenter.auto.208")}</Typography>
            <Typography color="text.secondary">{cc("controlCenter.auto.209")}</Typography>
          </Paper>)}
      </Stack>
      <Dialog open={dialog} onClose={() => setDialog(false)} fullWidth maxWidth="sm">
        <DialogTitle>{cc("controlCenter.auto.210")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label={cc("controlCenter.auto.073")} value={name} onChange={(e) => setName(e.target.value)}/>
            <FormControl>
              <InputLabel>{cc("controlCenter.auto.211")}</InputLabel>
              <Select value={field} label={cc("controlCenter.auto.211")} onChange={(e) => setField(e.target.value)}>
                <MenuItem value="campaign.metrics.cost_micros">{cc("controlCenter.auto.212")}</MenuItem>
                <MenuItem value="campaign.metrics.clicks">{cc("controlCenter.auto.022")}</MenuItem>
                <MenuItem value="campaign.metrics.conversions">{cc("controlCenter.auto.023")}</MenuItem>
                <MenuItem value="campaign.metrics.ctr">CTR</MenuItem>
                <MenuItem value="account.google_status">{cc("controlCenter.auto.018")}</MenuItem>
              </Select>
            </FormControl>
            <Box sx={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: 1 }}>
              <FormControl>
                <InputLabel>{cc("controlCenter.auto.213")}</InputLabel>
                <Select value={operator} label={cc("controlCenter.auto.213")} onChange={(e) => setOperator(e.target.value)}>
                  <MenuItem value="gte">≥</MenuItem>
                  <MenuItem value="lte">≤</MenuItem>
                  <MenuItem value="eq">{cc("controlCenter.auto.214")}</MenuItem>
                  <MenuItem value="ne">{cc("controlCenter.auto.215")}</MenuItem>
                </Select>
              </FormControl>
              <TextField label={cc("controlCenter.auto.216")} value={value} onChange={(e) => setValue(e.target.value)}/>
            </Box>
            <FormControl>
              <InputLabel>{cc("controlCenter.auto.217")}</InputLabel>
              <Select value={action} label={cc("controlCenter.auto.217")} onChange={(e) => setAction(e.target.value)}>
                <MenuItem value="NOTIFY">{cc("controlCenter.auto.218")}</MenuItem>
                <MenuItem value="PROPOSE_PAUSE">{cc("controlCenter.auto.219")}</MenuItem>
                <MenuItem value="PROPOSE_ENABLE">{cc("controlCenter.auto.220")}</MenuItem>
                <MenuItem value="PROPOSE_BUDGET">{cc("controlCenter.auto.221")}</MenuItem>
              </Select>
            </FormControl>
            {action === "PROPOSE_BUDGET" && <TextField type="number" inputProps={{ min: 0.01, step: 0.01 }} label={cc("controlCenter.full.145")} value={budgetAmount} onChange={(event) => setBudgetAmount(event.target.value)}/>}
            <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1 }}>
              <TextField type="number" inputProps={{ min: 1, max: 10000 }} label={cc("controlCenter.full.140")} value={priority} onChange={(event) => setPriority(event.target.value)}/>
              <TextField type="number" inputProps={{ min: 1, max: 10080 }} label={cc("controlCenter.full.146")} value={intervalMinutes} onChange={(event) => setIntervalMinutes(event.target.value)}/>
            </Box>
            <Alert severity="warning">{cc("controlCenter.auto.222")}</Alert>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(false)}>{cc("controlCenter.auto.075")}</Button>
          <Button variant="contained" disabled={!name.trim() || !value || !priority || !intervalMinutes || (action === "PROPOSE_BUDGET" && Number(budgetAmount) <= 0) || create.isPending} onClick={() => create.mutate()}>{cc("controlCenter.auto.223")}</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={Boolean(liveRule)} onClose={() => setLiveRule(null)} fullWidth maxWidth="sm">
        <DialogTitle>{liveRule?.mode === "LIVE" ? cc("controlCenter.full.147") : cc("controlCenter.full.148")}</DialogTitle>
        <DialogContent>
          <Alert severity={liveRule?.mode === "LIVE" ? "info" : "warning"} sx={{ mt: 1 }}>
            {liveRule?.mode === "LIVE" ? cc("controlCenter.full.149") : cc("controlCenter.full.150")}
          </Alert>
          {liveRule?.mode !== "LIVE" && <Typography sx={{ mt: 2 }}>{cc("controlCenter.full.151")}</Typography>}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setLiveRule(null)}>{cc("controlCenter.auto.075")}</Button>
          <Button variant="contained" color={liveRule?.mode === "LIVE" ? "primary" : "warning"} disabled={!liveRule || changeLiveMode.isPending} onClick={() => liveRule && changeLiveMode.mutate({
                id: liveRule.id,
                confirmation: liveRule.mode === "LIVE" ? "RETURN TO DRY RUN" : "ENABLE LIVE RULES"
            })}>
            {liveRule?.mode === "LIVE" ? cc("controlCenter.full.152") : cc("controlCenter.full.153")}
          </Button>
        </DialogActions>
      </Dialog>
      <Snackbar open={Boolean(message)} autoHideDuration={6000} onClose={() => setMessage(null)}>
        <Alert severity="success" onClose={() => setMessage(null)}>{message}</Alert>
      </Snackbar>
    </Stack>);
}
export function isProblematicGoogleStatus(account: Pick<ControlCenterAccount, "google_status" | "is_test_account" | "sync_error">): boolean {
    const closedTestAccount = account.is_test_account &&
        ["CLOSED", "CANCELED", "CANCELLED"].includes(account.google_status);
    return !closedTestAccount &&
        (["SUSPENDED", "CLOSED", "CANCELED", "CANCELLED", "NO_ACCESS", "SYNC_ERROR"].includes(account.google_status) ||
            Boolean(account.sync_error));
}
function GoogleStatusChip({ account }: {
    account: ControlCenterAccount;
}) {
    const problematic = isProblematicGoogleStatus(account);
    const statusLabel = account.is_test_account && ["CLOSED", "CANCELED", "CANCELLED"].includes(account.google_status)
        ? cc("controlCenter.full.166")
        : googleStatusLabel(account.google_status);
    return (<Tooltip title={account.sync_error ||
            (problematic ? cc("controlCenter.auto.224") : statusLabel)}>
      <Chip size="small" variant={problematic ? "filled" : "outlined"} color={problematic ? "error" : account.google_status === "ENABLED" ? "success" : "default"} icon={problematic ? <ErrorOutlineIcon /> : undefined} label={account.sync_error ? cc("controlCenter.auto.225") : statusLabel}/>
    </Tooltip>);
}
function WorkStatusChip({ value }: {
    value: WorkStatus;
}) {
    const status = WORK_STATUS.find((item) => item.value === value) || WORK_STATUS[0];
    return (<Chip size="small" variant="outlined" label={status.label} sx={{ borderColor: status.color, color: status.color }}/>);
}
function ActivityChip({ value }: {
    value: string;
}) {
    const item = ACTIVITY_STATUSES.find((candidate) => candidate.value === value);
    const color = value === "SPENDING" ? "success" : value === "SUSPENDED" || value === "NO_ACCESS" ? "error" : value === "STALE" || value === "ENABLED_NO_SPEND" ? "warning" : "default";
    return <Chip size="small" variant="outlined" color={color} label={item?.label || value || cc("controlCenter.auto.229")}/>;
}
function NoData() {
    return <Tooltip title={cc("controlCenter.full.137")}><Typography component="span" variant="body2" color="text.secondary">{cc("controlCenter.auto.229")}</Typography></Tooltip>;
}
function VerificationChip({ account }: {
    account: ControlCenterAccount;
}) {
    const status = account.verification_status;
    const attention = ["REQUIRED", "PENDING_USER_ACTION", "ACTION_REQUIRED", "FAILURE"].includes(status || "");
    return (<Chip size="small" variant="outlined" color={attention ? "warning" : status === "SUCCESS" || status === "NOT_REQUIRED" ? "success" : "default"} label={verificationLabel(status)}/>);
}
function FreshnessChip({ value, approximate }: {
    value?: string;
    approximate?: boolean;
}) {
    const color = value === "FRESH" ? "success" : value === "ERROR" ? "error" : value === "STALE" ? "warning" : "default";
    const label = value === "FRESH" ? cc("controlCenter.auto.226") : value === "STALE" ? cc("controlCenter.auto.227") : value === "ERROR" ? cc("controlCenter.auto.228") : cc("controlCenter.auto.229");
    return (<Tooltip title={approximate ? cc("controlCenter.auto.230") : label}>
      <Chip size="small" variant="outlined" color={color} label={approximate ? label + cc("controlCenter.auto.231") : label}/>
    </Tooltip>);
}
function TagChip({ tag }: {
    tag: ControlCenterTag;
}) {
    return (<Chip size="small" variant="outlined" label={tag.name} sx={{ borderColor: tag.color, color: "text.primary", maxWidth: 150 }}/>);
}
function Truncated({ text, error = false }: {
    text: string;
    error?: boolean;
}) {
    return (<Tooltip title={text}>
      <Typography variant="body2" noWrap color={error ? "error.main" : "inherit"}>{text}</Typography>
    </Tooltip>);
}
function MiniMetric({ label, value }: {
    label: string;
    value: string | number;
}) {
    return (<Box sx={{ minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography fontWeight={800} noWrap>{value}</Typography>
    </Box>);
}
function InfoGrid({ items }: {
    items: Array<[
        string,
        unknown
    ]>;
}) {
    return (<Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))" }, gap: 1 }}>
      {items.map(([label, value]) => (<Box key={label} sx={{ py: 0.75, borderBottom: 1, borderColor: "divider" }}>
          <Typography variant="caption" color="text.secondary">{label}</Typography>
          <Typography fontWeight={700} sx={{ overflowWrap: "anywhere" }}>{String(value ?? "—")}</Typography>
        </Box>))}
    </Box>);
}
function Section({ title, children }: {
    title: string;
    children: React.ReactNode;
}) {
    return (<Box>
      <Typography variant="h6" sx={{ fontSize: 16, mb: 1 }}>{title}</Typography>
      {children}
    </Box>);
}
function EmptyTableRow({ columns, text }: {
    columns: number;
    text: string;
}) {
    return <TableRow><TableCell colSpan={columns}><Typography color="text.secondary">{text}</Typography></TableCell></TableRow>;
}
function loadColumnState() {
    try {
        const raw = localStorage.getItem(COLUMN_STORAGE);
        if (raw)
            return normalizeColumnState(JSON.parse(raw));
    }
    catch {
        // Fall back to the stable default column set.
    }
    return {
        order: COLUMNS.map((item) => item.key),
        visible: DEFAULT_COLUMNS,
        pinned: ["local_name"] as ColumnKey[],
        widths: {},
        density: "compact" as const
    };
}
export function normalizeColumnState(value: Record<string, any>) {
    const valid = new Set(COLUMNS.map((item) => item.key));
    const order = (Array.isArray(value.order) ? value.order : []).filter((item) => valid.has(item));
    for (const column of COLUMNS)
        if (!order.includes(column.key))
            order.push(column.key);
    const visible = (Array.isArray(value.visible) ? value.visible : DEFAULT_COLUMNS).filter((item) => valid.has(item));
    const pinned = (Array.isArray(value.pinned) ? value.pinned : ["local_name"]).filter((item) => valid.has(item) && visible.includes(item));
    const widths = Object.fromEntries(Object.entries(value.widths || {}).filter(([key, width]) => valid.has(key as ColumnKey) && Number(width) >= 72 && Number(width) <= 600));
    const density = value.density === "normal" ? "normal" : "compact";
    return { order: order as ColumnKey[], visible: visible as ColumnKey[], pinned: pinned as ColumnKey[], widths: widths as Partial<Record<ColumnKey, number>>, density: density as "compact" | "normal" };
}
function startColumnResize(event: React.MouseEvent, column: ColumnDefinition, onResize: (key: ColumnKey, width: number) => void) {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startWidth = column.width;
    const move = (moveEvent: MouseEvent) => onResize(column.key, Math.min(600, Math.max(72, startWidth + moveEvent.clientX - startX)));
    const stop = () => {
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", stop);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", stop);
}
function numberOrUndefined(value: string) {
    if (!value.trim())
        return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}
function toMicros(value: string) {
    const parsed = numberOrUndefined(value);
    return parsed === undefined ? undefined : Math.round(parsed * 1000000);
}
function advancedFilterCount(values: Record<string, unknown>) {
    return Object.values(values).filter((value) => value !== "" && value !== false && value !== null && value !== undefined).length;
}
function policyTopicText(rows: Array<Record<string, any>> | undefined) {
    if (!rows?.length)
        return cc("controlCenter.full.138");
    return rows.map((item) => item.topic || item.type || item.policy_topic || JSON.stringify(item)).join(", ");
}
function tableWidth(columns: ColumnDefinition[]) {
    return 48 + 92 + columns.reduce((sum, column) => sum + column.width, 0);
}
function invalidateControlCenter(queryClient: ReturnType<typeof useQueryClient>) {
    queryClient.invalidateQueries({ queryKey: ["control-center-accounts"] });
    queryClient.invalidateQueries({ queryKey: ["control-center-summary"] });
    queryClient.invalidateQueries({ queryKey: ["control-center-campaigns"] });
    queryClient.invalidateQueries({ queryKey: ["control-center-history"] });
}
export function formatCustomerId(value: string) {
    const digits = value.replace(/\D/g, "");
    return digits.length === 10 ? `${digits.slice(0, 3)}-${digits.slice(3, 6)}-${digits.slice(6)}` : value;
}
export function money(value: number | null | undefined, currency: string | null | undefined) {
    if (value === null || value === undefined)
        return "—";
    return new Intl.NumberFormat(localeTag(), {
        style: currency ? "currency" : "decimal",
        currency: currency || undefined,
        maximumFractionDigits: 2
    }).format(value / 1000000);
}
function currencyValue(value: number | null | undefined, currency: string | null | undefined) {
    if (value === null || value === undefined)
        return "—";
    return new Intl.NumberFormat(localeTag(), {
        style: currency ? "currency" : "decimal",
        currency: currency || undefined,
        maximumFractionDigits: 2
    }).format(value);
}
function number(value: number | null | undefined) {
    return value === null || value === undefined ? "—" : new Intl.NumberFormat(localeTag()).format(value);
}
function decimal(value: number | null | undefined) {
    return value === null || value === undefined
        ? "—"
        : new Intl.NumberFormat(localeTag(), { maximumFractionDigits: 2 }).format(value);
}
function percent(value: number | null | undefined) {
    return value === null || value === undefined ? "—" : `${value.toFixed(2)}%`;
}
function verificationLabel(value: string | null | undefined) {
    const labels: Record<string, string> = {
        NOT_REQUIRED: cc("controlCenter.auto.232"),
        REQUIRED: cc("controlCenter.auto.233"),
        PENDING_USER_ACTION: cc("controlCenter.auto.234"),
        PENDING_REVIEW: cc("controlCenter.auto.235"),
        SUCCESS: cc("controlCenter.auto.236"),
        FAILURE: cc("controlCenter.auto.237"),
        UNAVAILABLE: cc("controlCenter.auto.238"),
        UNKNOWN: cc("controlCenter.auto.239")
    };
    return labels[value || "UNKNOWN"] || value || cc("controlCenter.auto.239");
}
function googleStatusLabel(value: string) {
    return {
        ENABLED: cc("controlCenter.auto.240"),
        SUSPENDED: cc("controlCenter.auto.241"),
        CLOSED: cc("controlCenter.auto.242"),
        CANCELED: cc("controlCenter.auto.243"),
        NO_ACCESS: cc("controlCenter.auto.244"),
        UNKNOWN: cc("controlCenter.auto.245")
    }[value] || value;
}
function sourceLabel(value: string) {
    return {
        DEMAND_GEN_UPLOADER: "Demand Gen Uploader",
        GOOGLE_ADS_MANUAL: cc("controlCenter.auto.152"),
        UNKNOWN: cc("controlCenter.auto.153")
    }[value] || value;
}
function severityLabel(value: string) {
    return value === "ERROR" ? cc("controlCenter.auto.172") : value === "WARNING" ? cc("controlCenter.auto.173") : cc("controlCenter.auto.174");
}
function severityColor(value: string): "error" | "warning" | "info" {
    return value === "ERROR" ? "error" : value === "WARNING" ? "warning" : "info";
}
function localizedNoDataReason(value: string | null | undefined) {
    if (!value)
        return value;
    return ccPersistedText(value);
}
function localizedProblemTitle(problem: ControlCenterProblem) {
    if (problem.problem_type === "SYNC_ERROR")
        return cc("controlCenter.auto.225");
    if (problem.problem_type.startsWith("SYNC_"))
        return `${cc("controlCenter.full.168")} ${problem.problem_type.slice(5)}`;
    return problem.title;
}
function localizedProblemDescription(problem: ControlCenterProblem) {
    const code = (problem.google_code || "").toUpperCase();
    let description = problem.description;
    if (code.includes("UNRECOGNIZED_FIELD"))
        description = cc("controlCenter.full.169");
    else if (code.includes("INVALID_DATE_FORMAT"))
        description = cc("controlCenter.full.170");
    else if (description.includes("<_InactiveRpcError") || description.includes("debug_error_string"))
        description = cc("controlCenter.full.172");
    if (problem.state === "RESOLVED" && code.includes("QUERY_ERROR"))
        description += cc("controlCenter.full.171");
    return description;
}
export function localizedSavedViewName(value: string) {
    return ccPersistedText(value);
}
function localizedModerationNote(value: string | null | undefined) {
    if (!value)
        return cc("controlCenter.full.091");
    return ccPersistedText(value);
}
export function localizedEventSummary(event: Record<string, any>) {
    const details = event.details || {};
    const previous = details.previous || "UNKNOWN";
    const current = details.current || details.work_status || "UNKNOWN";
    switch (event.event_type) {
        case "SYNC_SUCCEEDED":
            return cc("controlCenter.full.174");
        case "SYNC_FAILED":
            return cc("controlCenter.full.175");
        case "GOOGLE_STATUS_CHANGED":
            return `${cc("controlCenter.full.176")}: ${previous} → ${current}`;
        case "CAMPAIGN_STATUS_CHANGED":
            return `${cc("controlCenter.full.177")}: ${previous} → ${current}`;
        case "AD_POLICY_STATUS_CHANGED":
            return `${cc("controlCenter.full.178")}: ${previous} → ${current}`;
        case "WORK_STATUS_CHANGED":
            return `${cc("controlCenter.full.179")}: ${current}`;
        case "NOTE_CHANGED":
            return cc("controlCenter.full.180");
        case "LOCAL_NAME_CHANGED":
            return cc("controlCenter.full.181");
        case "GEO_CHANGED":
            return cc(details.geo_id ? "controlCenter.full.182" : "controlCenter.full.183");
        case "TAG_ADDED":
            return cc("controlCenter.full.184");
        case "TAG_REMOVED":
            return cc("controlCenter.full.185");
        case "MANUAL_ACTION_SIMULATED":
            return cc("controlCenter.full.186");
        case "RULE_ACTION_SKIPPED":
            return cc("controlCenter.full.187");
        default:
            return event.summary;
    }
}
function eventTypeLabel(value: string) {
    return {
        WORK_STATUS_CHANGED: cc("controlCenter.auto.017"),
        GOOGLE_STATUS_CHANGED: cc("controlCenter.auto.018"),
        NOTE_CHANGED: cc("controlCenter.auto.029"),
        TAG_ADDED: cc("controlCenter.auto.246"),
        TAG_REMOVED: cc("controlCenter.auto.247"),
        SYNC_SUCCEEDED: cc("controlCenter.auto.031"),
        SYNC_FAILED: cc("controlCenter.auto.225"),
        CAMPAIGN_STATUS_CHANGED: cc("controlCenter.auto.116"),
        MANUAL_ACTION_SIMULATED: cc("controlCenter.auto.248")
    }[value] || value;
}
