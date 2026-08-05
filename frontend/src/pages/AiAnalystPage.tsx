import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  FormControlLabel,
  IconButton,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Stack,
  Switch,
  Tab,
  Tabs,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArchiveOutlinedIcon from "@mui/icons-material/ArchiveOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DownloadIcon from "@mui/icons-material/Download";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import GraphicEqIcon from "@mui/icons-material/GraphicEq";
import MicIcon from "@mui/icons-material/Mic";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import RefreshIcon from "@mui/icons-material/Refresh";
import SendIcon from "@mui/icons-material/Send";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import StopIcon from "@mui/icons-material/Stop";
import UnarchiveOutlinedIcon from "@mui/icons-material/UnarchiveOutlined";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  AiAuthorityMode,
  AiConversation,
  AiDraft,
  AiMessage,
  AiReport,
  AiScope,
  AiSourceRegistryItem,
  api,
  ExecutionMode,
  streamAiMessage
} from "../api/client";
import { AiMessageView } from "../components/AiAnswerView";
import { formatDate, formatNumber, useLocale } from "../i18n";
import { ai } from "../i18n/aiAnalyst";

type WorkspaceTab = "CHAT" | "DRAFTS" | "REPORTS" | "ADMIN";
type ModelProfile = "FAST" | "BALANCED" | "DEEP";

const QUICK_PROMPT_KEYS = [
  "ai.quick.1", "ai.quick.2", "ai.quick.3", "ai.quick.4", "ai.quick.5",
  "ai.quick.6", "ai.quick.7", "ai.quick.8", "ai.quick.9"
];

const EMPTY_SCOPE: AiScope = {
  connection_ids: [],
  mcc_ids: [],
  geo_ids: [],
  account_ids: [],
  campaign_ids: [],
  period: "7d",
  start_date: null,
  end_date: null,
  metric_source: "GOOGLE_ADS",
  currency: null
};

export function AiAnalystPage() {
  const queryClient = useQueryClient();
  const { locale } = useLocale();
  const [tab, setTab] = useState<WorkspaceTab>("CHAT");
  const [conversationId, setConversationId] = useState<string | null>(() => localStorage.getItem("axyro.ai.conversation"));
  const [scope, setScope] = useState<AiScope>(EMPTY_SCOPE);
  const [authority, setAuthority] = useState<AiAuthorityMode>("READ_ONLY");
  const [environment, setEnvironment] = useState<ExecutionMode>("SIMULATION");
  const [model, setModel] = useState<ModelProfile>("BALANCED");
  const [prompt, setPrompt] = useState("");
  const [lastPrompt, setLastPrompt] = useState("");
  const [streamText, setStreamText] = useState("");
  const [streamRunId, setStreamRunId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [rename, setRename] = useState<AiConversation | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const defaultsAppliedRef = useRef(false);

  const capabilities = useQuery({ queryKey: ["ai-capabilities"], queryFn: api.aiCapabilities, retry: false });
  const sourceRegistry = useQuery({ queryKey: ["ai-source-registry"], queryFn: api.aiSourceRegistry });
  const preferences = useQuery({ queryKey: ["ai-preferences"], queryFn: api.aiPreferences });
  const conversations = useQuery({
    queryKey: ["ai-conversations", showArchived],
    queryFn: () => api.aiConversations(showArchived)
  });
  const myUsage = useQuery({ queryKey: ["ai-my-usage"], queryFn: () => api.aiMyUsage(30) });
  const detail = useQuery({
    queryKey: ["ai-conversation", conversationId],
    queryFn: () => api.getAiConversation(conversationId!),
    enabled: Boolean(conversationId)
  });
  const drafts = useQuery({ queryKey: ["ai-drafts"], queryFn: () => api.aiDrafts() });
  const reports = useQuery({ queryKey: ["ai-reports"], queryFn: api.aiReports });
  const connections = useQuery({ queryKey: ["connections"], queryFn: api.listConnections, staleTime: 60_000 });
  const geos = useQuery({ queryKey: ["control-center-geos"], queryFn: api.controlCenterGeos, staleTime: 60_000 });
  const mcc = useQuery({ queryKey: ["control-center-mcc"], queryFn: () => api.controlCenterMcc(), staleTime: 60_000 });
  const accounts = useQuery({
    queryKey: ["ai-scope-accounts"],
    queryFn: () => api.controlCenterAccounts({ quick_filter: "all", period: "7d", limit: 5000 }),
    staleTime: 60_000
  });
  const campaigns = useQuery({
    queryKey: ["ai-scope-campaigns"],
    queryFn: () => api.controlCenterCampaigns({ limit: 500, offset: 0 }),
    staleTime: 60_000
  });

  useEffect(() => {
    if (conversations.isLoading || !conversations.data) return;
    const selectedExists = conversationId && conversations.data.some((item) => item.id === conversationId);
    if (!selectedExists) setConversationId(conversations.data[0]?.id || null);
  }, [conversationId, conversations.data, conversations.isLoading]);
  useEffect(() => {
    if (!conversationId) localStorage.removeItem("axyro.ai.conversation");
    else localStorage.setItem("axyro.ai.conversation", conversationId);
  }, [conversationId]);
  useEffect(() => {
    if (!detail.data) return;
    setScope({ ...EMPTY_SCOPE, ...(detail.data.scope || {}) });
    setAuthority(detail.data.authority_mode);
    setEnvironment(detail.data.google_environment);
  }, [detail.data]);
  useEffect(() => {
    if (defaultsAppliedRef.current || !preferences.data || conversationId || detail.data) return;
    defaultsAppliedRef.current = true;
    setScope({ ...EMPTY_SCOPE, ...(preferences.data.default_scope || {}) });
    setAuthority(preferences.data.default_authority_mode || "READ_ONLY");
    setEnvironment(preferences.data.default_environment || "SIMULATION");
    setModel(preferences.data.default_model_profile || "BALANCED");
  }, [conversationId, detail.data, preferences.data]);
  useEffect(() => {
    const container = messageListRef.current;
    if (container && typeof container.scrollTo === "function") {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    }
  }, [detail.data?.messages, streamText]);

  const createConversation = useMutation({
    mutationFn: () => api.createAiConversation({
      title: ai("ai.newConversation"),
      authority_mode: authority,
      google_environment: environment,
      scope,
      locale,
      time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow"
    }),
    onSuccess: async (item) => {
      setConversationId(item.id);
      await queryClient.invalidateQueries({ queryKey: ["ai-conversations"] });
    },
    onError: (value) => setError(errorText(value))
  });
  const patchConversation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) => api.patchAiConversation(id, payload),
    onSuccess: async (item) => {
      queryClient.setQueryData(["ai-conversation", item.id], (current: AiConversation | undefined) => ({ ...current, ...item }));
      await queryClient.invalidateQueries({ queryKey: ["ai-conversations"] });
      if (item.id === conversationId && Boolean(item.archived_at) !== showArchived) setConversationId(null);
      setNotice(ai("ai.saved"));
    },
    onError: (value) => setError(errorText(value))
  });
  const removeConversation = useMutation({
    mutationFn: api.deleteAiConversation,
    onSuccess: async (_result, removedId) => {
      queryClient.removeQueries({ queryKey: ["ai-conversation", removedId] });
      setConversationId(null);
      await queryClient.invalidateQueries({ queryKey: ["ai-conversations"] });
    },
    onError: (value) => setError(errorText(value))
  });

  const current = detail.data || conversations.data?.find((item) => item.id === conversationId);
  const activeMessages = conversationId ? (detail.data?.messages || []) : [];
  const visibleDrafts = (drafts.data || []).filter((item) => !["DELETED", "APPLIED"].includes(item.status));
  const role = capabilities.data?.role;
  const interactionDisabled = !capabilities.data?.enabled
    || capabilities.data?.kill_switch
    || capabilities.data?.provider.configured === false;

  const saveScope = () => {
    if (!conversationId) return;
    patchConversation.mutate({ id: conversationId, payload: { scope, authority_mode: authority, google_environment: environment } });
  };
  const saveDefaults = async () => {
    try {
      await api.patchAiPreferences({
        default_scope: scope,
        default_authority_mode: authority,
        default_environment: environment,
        default_model_profile: model,
        locale,
        time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow"
      });
      await queryClient.invalidateQueries({ queryKey: ["ai-preferences"] });
      setNotice(ai("ai.defaultsSaved"));
    } catch (value) { setError(errorText(value)); }
  };

  const send = async (text = prompt) => {
    const content = text.trim();
    if (!content || sending) return;
    setError(null);
    setLastPrompt(content);
    let targetId = conversationId;
    if (!targetId) {
      try {
        const item = await api.createAiConversation({
          title: content.slice(0, 80),
          authority_mode: authority,
          google_environment: environment,
          scope,
          locale,
          time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow"
        });
        targetId = item.id;
        setConversationId(item.id);
        await queryClient.invalidateQueries({ queryKey: ["ai-conversations"] });
      } catch (value) {
        setError(errorText(value));
        return;
      }
    } else {
      try {
        await api.patchAiConversation(targetId, { scope, authority_mode: authority, google_environment: environment });
      } catch (value) {
        setError(errorText(value));
        return;
      }
    }
    setPrompt("");
    setStreamText("");
    setSending(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamAiMessage(
        targetId,
        { content, model_profile: model, idempotency_key: crypto.randomUUID() },
        (event, data) => {
          if (event === "connected") setStreamRunId(String(data.run_id));
          if (event === "message.delta") setStreamText((value) => value + String(data.text || ""));
          if (event === "message.completed") setStreamText(String(data.answer || ""));
          if (event === "run.error") setError(String(data.message || data.code || ai("ai.error")));
        },
        controller.signal
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ai-conversation", targetId] }),
        queryClient.invalidateQueries({ queryKey: ["ai-conversations"] }),
        queryClient.invalidateQueries({ queryKey: ["ai-drafts"] }),
        queryClient.invalidateQueries({ queryKey: ["ai-reports"] }),
        queryClient.invalidateQueries({ queryKey: ["ai-my-usage"] }),
        queryClient.invalidateQueries({ queryKey: ["ai-usage"] })
      ]);
    } catch (value) {
      if (!controller.signal.aborted) setError(errorText(value));
    } finally {
      setSending(false);
      setStreamText("");
      setStreamRunId(null);
      abortRef.current = null;
    }
  };

  const stop = async () => {
    abortRef.current?.abort();
    if (streamRunId) {
      try { await api.cancelAiRun(streamRunId); } catch { /* The stream may already be closed. */ }
    }
    setSending(false);
  };

  return (
    <Stack spacing={2.5}>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={2} alignItems={{ sm: "center" }}>
        <Box>
          <Typography variant="h4">{ai("ai.title")}</Typography>
          <Typography color="text.secondary">{ai("ai.subtitle")}</Typography>
        </Box>
        <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
          <Chip
            size="small"
            variant="outlined"
            label={`${ai("ai.cost")}: $${Number(myUsage.data?.totals?.estimated_cost_usd || 0).toFixed(4)}`}
          />
          <CapabilityStatus data={capabilities.data} loading={capabilities.isLoading} />
        </Stack>
      </Stack>

      {capabilities.data?.provider.configured === false && <Alert severity="warning">{ai("ai.providerMissing")}</Alert>}
      {capabilities.data?.kill_switch && <Alert severity="error">{ai("ai.killSwitch")}</Alert>}
      {capabilities.data?.enabled === false && <Alert severity="error">{ai("ai.disabled")}</Alert>}
      {error && (
        <Alert
          severity="error"
          onClose={() => setError(null)}
          action={lastPrompt && !sending ? <Button color="inherit" size="small" startIcon={<RefreshIcon />} onClick={() => void send(lastPrompt)}>{ai("ai.retry")}</Button> : undefined}
        >
          {error}
        </Alert>
      )}

      <Tabs value={tab} onChange={(_event, value: WorkspaceTab) => setTab(value)} variant="scrollable" allowScrollButtonsMobile>
        <Tab value="CHAT" label={ai("ai.answer")} />
        <Tab value="DRAFTS" label={`${ai("ai.drafts")} (${visibleDrafts.length})`} />
        <Tab value="REPORTS" label={`${ai("ai.reports")} (${reports.data?.length || 0})`} />
        {role === "ADMIN" && <Tab value="ADMIN" label={ai("ai.settings")} icon={<SettingsOutlinedIcon />} iconPosition="start" />}
      </Tabs>

      {tab === "CHAT" && (
        <>
          <ScopeEditor
            scope={scope}
            onScope={setScope}
            authority={authority}
            onAuthority={setAuthority}
            environment={environment}
            onEnvironment={setEnvironment}
            capabilities={capabilities.data}
            sources={sourceRegistry.data || []}
            connections={connections.data || []}
            geos={geos.data || []}
            mcc={mcc.data || []}
            accounts={accounts.data?.items || []}
            campaigns={campaigns.data?.items || []}
            onSave={saveScope}
            onSaveDefaults={() => void saveDefaults()}
            disabled={sending || patchConversation.isPending}
          />

          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "250px minmax(0, 1fr)" }, gap: 2, minHeight: 540 }}>
            <ConversationList
              items={conversations.data || []}
              selected={conversationId}
              loading={conversations.isLoading}
              onSelect={setConversationId}
              onCreate={() => createConversation.mutate()}
              onRename={setRename}
              archived={showArchived}
              onArchived={(value) => {
                setShowArchived(value);
                setConversationId(null);
              }}
              onArchive={(item) => patchConversation.mutate({ id: item.id, payload: { archived: !showArchived } })}
              onDelete={(item) => {
                if (window.confirm(`${ai("ai.delete")}: ${item.title}?`)) removeConversation.mutate(item.id);
              }}
            />

            <Box sx={{ minWidth: 0, display: "flex", flexDirection: "column" }}>
              <Box
                ref={messageListRef}
                aria-live="polite"
                sx={{ flex: 1, minHeight: 360, maxHeight: "calc(100vh - 370px)", overflowY: "auto", pr: { sm: 1 } }}
              >
                <Stack spacing={2.5}>
                  {detail.isLoading && <LinearProgress />}
                  {!detail.isLoading && !activeMessages.length && !sending && (
                    <EmptyConversation
                      onPrompt={(value) => { setPrompt(value); void send(value); }}
                      disabled={interactionDisabled}
                    />
                  )}
                  {activeMessages.map((message) => <AiMessageView key={message.id} message={message} />)}
                  {sending && (
                    <Paper variant="outlined" sx={{ p: 2 }}>
                      <Stack direction="row" spacing={1.5} alignItems="center">
                        <CircularProgress size={20} />
                        <Typography>{streamText || ai("ai.loading")}</Typography>
                      </Stack>
                    </Paper>
                  )}
                </Stack>
              </Box>
              <Composer
                value={prompt}
                onChange={setPrompt}
                onSend={() => void send()}
                onStop={() => void stop()}
                sending={sending}
                model={model}
                onModel={setModel}
                disabled={interactionDisabled}
                onError={setError}
              />
            </Box>
          </Box>
        </>
      )}

      {tab === "DRAFTS" && (
        <DraftWorkspace
          drafts={visibleDrafts}
          loading={drafts.isLoading}
          canApply={role === "ADMIN" || role === "OPERATOR"}
          onChanged={() => queryClient.invalidateQueries({ queryKey: ["ai-drafts"] })}
          onError={setError}
          onNotice={setNotice}
        />
      )}

      {tab === "REPORTS" && (
        <ReportWorkspace
          reports={reports.data || []}
          loading={reports.isLoading}
          onChanged={() => queryClient.invalidateQueries({ queryKey: ["ai-reports"] })}
          onError={setError}
        />
      )}

      {tab === "ADMIN" && role === "ADMIN" && <AiAdminWorkspace onError={setError} onNotice={setNotice} />}

      <Dialog open={Boolean(rename)} onClose={() => setRename(null)} fullWidth maxWidth="sm">
        <DialogTitle>{ai("ai.rename")}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            sx={{ mt: 1 }}
            value={rename?.title || ""}
            onChange={(event) => setRename((item) => item ? { ...item, title: event.target.value } : null)}
            inputProps={{ maxLength: 180 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRename(null)}>{ai("ai.close")}</Button>
          <Button
            variant="contained"
            disabled={!rename?.title.trim()}
            onClick={() => {
              if (rename) patchConversation.mutate({ id: rename.id, payload: { title: rename.title.trim() } });
              setRename(null);
            }}
          >{ai("ai.save")}</Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={Boolean(notice)} autoHideDuration={3500} onClose={() => setNotice(null)} message={notice} />
    </Stack>
  );
}

function CapabilityStatus({ data, loading }: { data: Awaited<ReturnType<typeof api.aiCapabilities>> | undefined; loading: boolean }) {
  if (loading) return <CircularProgress size={24} />;
  const ready = Boolean(data?.enabled && !data.kill_switch && data.provider.configured);
  return (
    <Stack direction="row" spacing={1} flexWrap="wrap">
      <Chip color={ready ? "success" : "warning"} label={ready ? ai("ai.providerReady") : ai("ai.notConfigured")} />
      <Chip variant="outlined" label={data?.role || "—"} />
      <Chip variant="outlined" color="warning" label={ai("ai.productionLocked")} />
    </Stack>
  );
}

type ScopeProps = {
  scope: AiScope;
  onScope: (scope: AiScope) => void;
  authority: AiAuthorityMode;
  onAuthority: (value: AiAuthorityMode) => void;
  environment: ExecutionMode;
  onEnvironment: (value: ExecutionMode) => void;
  capabilities: Awaited<ReturnType<typeof api.aiCapabilities>> | undefined;
  sources: AiSourceRegistryItem[];
  connections: Awaited<ReturnType<typeof api.listConnections>>;
  geos: Awaited<ReturnType<typeof api.controlCenterGeos>>;
  mcc: Awaited<ReturnType<typeof api.controlCenterMcc>>;
  accounts: Awaited<ReturnType<typeof api.controlCenterAccounts>>["items"];
  campaigns: Awaited<ReturnType<typeof api.controlCenterCampaigns>>["items"];
  onSave: () => void;
  onSaveDefaults: () => void;
  disabled: boolean;
};

function ScopeEditor(props: ScopeProps) {
  const filteredMcc = props.mcc.filter((item) => !props.scope.connection_ids.length || props.scope.connection_ids.includes(item.connection_id));
  const filteredAccounts = props.accounts.filter((item) =>
    (!props.scope.connection_ids.length || props.scope.connection_ids.includes(item.connection_id)) &&
    (!props.scope.mcc_ids.length || (item.primary_mcc_id && props.scope.mcc_ids.includes(item.primary_mcc_id))) &&
    (!props.scope.geo_ids.length || (item.geo_id && props.scope.geo_ids.includes(item.geo_id)))
  );
  const filteredCampaigns = props.campaigns.filter((item) =>
    (!props.scope.account_ids.length || props.scope.account_ids.includes(item.account_id))
  );
  const setIds = (key: keyof Pick<AiScope, "connection_ids" | "geo_ids" | "mcc_ids" | "account_ids" | "campaign_ids">, ids: string[]) => {
    const next = { ...props.scope, [key]: ids };
    if (key === "connection_ids") Object.assign(next, { mcc_ids: [], account_ids: [], campaign_ids: [] });
    if (key === "geo_ids" || key === "mcc_ids") Object.assign(next, { account_ids: [], campaign_ids: [] });
    if (key === "account_ids") Object.assign(next, { campaign_ids: [] });
    props.onScope(next);
  };
  return (
    <Box sx={{ borderTop: 1, borderBottom: 1, borderColor: "divider", py: 2 }}>
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={1} sx={{ mb: 1.5 }}>
        <Typography variant="subtitle2" fontWeight={800}>{ai("ai.scope")}</Typography>
        <Stack direction="row" gap={1}>
          <Button size="small" variant="text" onClick={props.onSaveDefaults} disabled={props.disabled}>{ai("ai.saveDefaults")}</Button>
          <Button size="small" variant="outlined" onClick={props.onSave} disabled={props.disabled}>{ai("ai.saveScope")}</Button>
        </Stack>
      </Stack>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", xl: "repeat(4, 1fr)" }, gap: 1.5 }}>
        <MultiScope label={ai("ai.connection")} options={props.connections} value={props.scope.connection_ids} optionLabel={(item) => item.name} onChange={(ids) => setIds("connection_ids", ids)} />
        <MultiScope label={ai("ai.geo")} options={props.geos} value={props.scope.geo_ids} optionLabel={(item) => item.display_name} onChange={(ids) => setIds("geo_ids", ids)} />
        <MultiScope label={ai("ai.mcc")} options={filteredMcc} value={props.scope.mcc_ids} optionLabel={(item) => item.descriptive_name || item.customer_id} onChange={(ids) => setIds("mcc_ids", ids)} />
        <MultiScope label={ai("ai.accounts")} options={filteredAccounts} value={props.scope.account_ids} optionLabel={(item) => item.display_name} onChange={(ids) => setIds("account_ids", ids)} />
        <MultiScope label={ai("ai.campaigns")} options={filteredCampaigns} value={props.scope.campaign_ids} optionLabel={(item) => item.name} onChange={(ids) => setIds("campaign_ids", ids)} />
        <FormControl size="small" fullWidth>
          <InputLabel>{ai("ai.period")}</InputLabel>
          <Select label={ai("ai.period")} value={props.scope.period} onChange={(event) => props.onScope({ ...props.scope, period: event.target.value as AiScope["period"] })}>
            {(["today", "yesterday", "3d", "7d", "30d", "custom"] as const).map((item) => <MenuItem key={item} value={item}>{ai(`ai.${item}`)}</MenuItem>)}
          </Select>
        </FormControl>
        <FormControl size="small" fullWidth>
          <InputLabel>{ai("ai.source")}</InputLabel>
          <Select label={ai("ai.source")} value={props.scope.metric_source} onChange={(event) => props.onScope({ ...props.scope, metric_source: event.target.value })}>
            {props.sources.map((item) => (
              <MenuItem key={item.capabilities.provider_id} value={item.capabilities.provider_id} disabled={!item.status.enabled}>
                {item.capabilities.label} · {item.status.setup_status}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <TextField size="small" label={ai("ai.currency")} value={props.scope.currency || ""} onChange={(event) => props.onScope({ ...props.scope, currency: event.target.value.toUpperCase().slice(0, 8) || null })} />
      </Box>
      {props.sources.find((item) => item.capabilities.provider_id === props.scope.metric_source)?.status.enabled === false && (
        <Alert severity="warning" sx={{ mt: 1.5 }}>
          {props.sources.find((item) => item.capabilities.provider_id === props.scope.metric_source)?.status.explanation}
        </Alert>
      )}
      {props.scope.period === "custom" && (
        <Stack direction={{ xs: "column", sm: "row" }} gap={1.5} sx={{ mt: 1.5 }}>
          <TextField size="small" type="date" label={ai("ai.startDate")} InputLabelProps={{ shrink: true }} value={props.scope.start_date || ""} onChange={(event) => props.onScope({ ...props.scope, start_date: event.target.value || null })} />
          <TextField size="small" type="date" label={ai("ai.endDate")} InputLabelProps={{ shrink: true }} value={props.scope.end_date || ""} onChange={(event) => props.onScope({ ...props.scope, end_date: event.target.value || null })} />
        </Stack>
      )}
      <Stack direction={{ xs: "column", md: "row" }} gap={1.5} sx={{ mt: 1.5 }}>
        <ToggleButtonGroup exclusive size="small" value={props.authority} onChange={(_event, value) => value && props.onAuthority(value)} aria-label={ai("ai.authority")}>
          <ToggleButton value="READ_ONLY">{ai("ai.readOnly")}</ToggleButton>
          {props.capabilities?.authority_modes.includes("DRAFT_ONLY") && <ToggleButton value="DRAFT_ONLY">{ai("ai.draftOnly")}</ToggleButton>}
          {props.capabilities?.authority_modes.includes("CONFIRM_REQUIRED") && <ToggleButton value="CONFIRM_REQUIRED">{ai("ai.confirmRequired")}</ToggleButton>}
        </ToggleButtonGroup>
        <ToggleButtonGroup exclusive size="small" value={props.environment} onChange={(_event, value) => value && props.onEnvironment(value)} aria-label={ai("ai.environment")}>
          <ToggleButton value="SIMULATION">{ai("ai.simulation")}</ToggleButton>
          <ToggleButton value="GOOGLE_TEST">{ai("ai.googleTest")}</ToggleButton>
          <ToggleButton value="PRODUCTION" disabled={!props.capabilities?.production.read_enabled}>{ai("ai.production")}</ToggleButton>
        </ToggleButtonGroup>
      </Stack>
    </Box>
  );
}

function MultiScope<T extends { id: string }>({ label, options, value, optionLabel, onChange }: { label: string; options: T[]; value: string[]; optionLabel: (item: T) => string; onChange: (ids: string[]) => void }) {
  const selected = options.filter((item) => value.includes(item.id));
  return (
    <Autocomplete
      multiple
      size="small"
      options={options}
      value={selected}
      getOptionLabel={optionLabel}
      isOptionEqualToValue={(left, right) => left.id === right.id}
      onChange={(_event, items) => onChange(items.map((item) => item.id))}
      limitTags={1}
      renderInput={(params) => <TextField {...params} label={label} placeholder={ai("ai.scopeAll")} />}
    />
  );
}

function ConversationList({ items, selected, loading, onSelect, onCreate, onRename, archived, onArchived, onArchive, onDelete }: {
  items: AiConversation[];
  selected: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onRename: (item: AiConversation) => void;
  archived: boolean;
  onArchived: (value: boolean) => void;
  onArchive: (item: AiConversation) => void;
  onDelete: (item: AiConversation) => void;
}) {
  return (
    <Box sx={{ borderRight: { lg: 1 }, borderBottom: { xs: 1, lg: 0 }, borderColor: "divider", pr: { lg: 1.5 }, pb: { xs: 1.5, lg: 0 } }}>
      <Button fullWidth variant="contained" startIcon={<AddIcon />} onClick={onCreate}>{ai("ai.newConversation")}</Button>
      <FormControlLabel
        sx={{ mt: 0.5, ml: 0 }}
        control={<Switch size="small" checked={archived} onChange={(event) => onArchived(event.target.checked)} />}
        label={<Typography variant="body2">{ai("ai.showArchive")}</Typography>}
      />
      {loading && <LinearProgress sx={{ mt: 1 }} />}
      <Stack spacing={0.5} sx={{ mt: 1, maxHeight: { lg: "calc(100vh - 420px)" }, overflowY: "auto" }}>
        {!loading && !items.length && <Typography variant="body2" color="text.secondary">{ai("ai.noConversations")}</Typography>}
        {items.map((item) => (
          <Box key={item.id} sx={{ p: 1, borderLeft: 3, borderColor: item.id === selected ? "primary.main" : "transparent", bgcolor: item.id === selected ? "action.selected" : "transparent" }}>
            <Button color="inherit" fullWidth sx={{ justifyContent: "flex-start", textAlign: "left", px: 0.5, minWidth: 0 }} onClick={() => onSelect(item.id)}>
              <Typography variant="body2" noWrap>{item.title}</Typography>
            </Button>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="caption" color="text.secondary">{formatDate(item.last_message_at || item.created_at)}</Typography>
              <Box sx={{ whiteSpace: "nowrap" }}>
                <Tooltip title={ai("ai.rename")}><IconButton size="small" onClick={() => onRename(item)}><EditOutlinedIcon fontSize="inherit" /></IconButton></Tooltip>
                <Tooltip title={ai("ai.export")}><IconButton size="small" component="a" href={api.aiConversationExportUrl(item.id)}><DownloadIcon fontSize="inherit" /></IconButton></Tooltip>
                <Tooltip title={ai(archived ? "ai.restore" : "ai.archive")}>
                  <IconButton size="small" onClick={() => onArchive(item)}>
                    {archived ? <UnarchiveOutlinedIcon fontSize="inherit" /> : <ArchiveOutlinedIcon fontSize="inherit" />}
                  </IconButton>
                </Tooltip>
                <Tooltip title={ai("ai.delete")}><IconButton size="small" color="error" onClick={() => onDelete(item)}><DeleteOutlineIcon fontSize="inherit" /></IconButton></Tooltip>
              </Box>
            </Stack>
          </Box>
        ))}
      </Stack>
    </Box>
  );
}

function EmptyConversation({ onPrompt, disabled }: { onPrompt: (prompt: string) => void; disabled: boolean }) {
  return (
    <Stack spacing={2} sx={{ py: 4 }}>
      <Box>
        <Typography variant="h5">{ai("ai.emptyTitle")}</Typography>
        <Typography color="text.secondary">{ai("ai.emptyText")}</Typography>
      </Box>
      <Typography variant="subtitle2" fontWeight={800}>{ai("ai.quick")}</Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(2, minmax(0, 1fr))" }, gap: 1 }}>
        {QUICK_PROMPT_KEYS.map((key) => {
          const prompt = ai(key);
          return <Button key={key} variant="outlined" sx={{ justifyContent: "flex-start", textAlign: "left" }} onClick={() => onPrompt(prompt)} disabled={disabled}>{prompt}</Button>;
        })}
      </Box>
    </Stack>
  );
}

function Composer({ value, onChange, onSend, onStop, sending, model, onModel, disabled, onError }: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  sending: boolean;
  model: ModelProfile;
  onModel: (value: ModelProfile) => void;
  disabled: boolean;
  onError: (value: string) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timeoutRef = useRef<number | null>(null);

  const startVoice = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find((item) => MediaRecorder.isTypeSupported(item));
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        setRecording(false);
        setTranscribing(true);
        try {
          const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
          chunksRef.current = [];
          const result = await api.transcribeAiAudio(blob);
          onChange(result.transcript);
        } catch (value) {
          onError(errorText(value));
        } finally {
          setTranscribing(false);
        }
      };
      recorderRef.current = recorder;
      recorder.start(250);
      setRecording(true);
      timeoutRef.current = window.setTimeout(() => recorder.stop(), 60_000);
    } catch (value) {
      onError(errorText(value));
    }
  };
  const stopVoice = () => {
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  };
  return (
    <Paper variant="outlined" sx={{ p: 1.5, mt: 2 }}>
      {(recording || transcribing) && <Alert severity="info" icon={<GraphicEqIcon />} sx={{ mb: 1 }}>{recording ? ai("ai.listening") : ai("ai.transcribing")}</Alert>}
      <TextField
        fullWidth
        multiline
        minRows={2}
        maxRows={7}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={ai("ai.askPlaceholder")}
        disabled={sending || transcribing || disabled}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); onSend(); }
        }}
        inputProps={{ maxLength: 20_000, "aria-label": ai("ai.askPlaceholder") }}
      />
      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={1} sx={{ mt: 1 }}>
        <Stack direction="row" gap={1} alignItems="center">
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>{ai("ai.model")}</InputLabel>
            <Select label={ai("ai.model")} value={model} onChange={(event) => onModel(event.target.value as ModelProfile)}>
              <MenuItem value="FAST">{ai("ai.fast")}</MenuItem>
              <MenuItem value="BALANCED">{ai("ai.balanced")}</MenuItem>
              <MenuItem value="DEEP">{ai("ai.deep")}</MenuItem>
            </Select>
          </FormControl>
          <Tooltip title={recording ? ai("ai.stop") : ai("ai.voiceReview")}>
            <span><IconButton color={recording ? "error" : "default"} onClick={recording ? stopVoice : () => void startVoice()} disabled={sending || transcribing || disabled} aria-label={recording ? ai("ai.stop") : ai("ai.voiceReview")}>
              {recording ? <StopIcon /> : <MicIcon />}
            </IconButton></span>
          </Tooltip>
        </Stack>
        {sending ? <Button variant="outlined" color="error" startIcon={<StopIcon />} onClick={onStop}>{ai("ai.stop")}</Button> : <Button variant="contained" endIcon={<SendIcon />} disabled={!value.trim() || disabled || transcribing} onClick={onSend}>{ai("ai.send")}</Button>}
      </Stack>
    </Paper>
  );
}

function DraftWorkspace({ drafts, loading, canApply, onChanged, onError, onNotice }: {
  drafts: AiDraft[];
  loading: boolean;
  canApply: boolean;
  onChanged: () => Promise<unknown> | void;
  onError: (value: string) => void;
  onNotice: (value: string) => void;
}) {
  if (loading) return <LinearProgress />;
  if (!drafts.length) return <Alert severity="info">{ai("ai.noDrafts")}</Alert>;
  return (
    <Stack spacing={1.5}>
      {drafts.map((draft) => <DraftCard key={draft.id} draft={draft} canApply={canApply} onChanged={onChanged} onError={onError} onNotice={onNotice} />)}
    </Stack>
  );
}

function DraftCard({ draft, canApply, onChanged, onError, onNotice }: {
  draft: AiDraft;
  canApply: boolean;
  onChanged: () => Promise<unknown> | void;
  onError: (value: string) => void;
  onNotice: (value: string) => void;
}) {
  const [payload, setPayload] = useState(() => JSON.stringify(draft.payload, null, 2));
  const [busy, setBusy] = useState(false);
  const perform = async (kind: "SAVE" | "PREVIEW" | "APPLY" | "DELETE") => {
    setBusy(true);
    try {
      if (kind === "SAVE") await api.patchAiDraft(draft.id, { payload: JSON.parse(payload), expected_version: draft.version });
      if (kind === "PREVIEW") {
        await api.previewAiDraft(draft.id, draft.version, draft.fingerprint);
        onNotice(ai("ai.previewCreated"));
      }
      if (kind === "APPLY") {
        if (!window.confirm(ai("ai.confirmDraft"))) return;
        const result = await api.applyAiDraft(draft.id, draft.version, draft.fingerprint);
        onNotice(result.result.applied ? ai("ai.applied") : String(result.result.reason || ai("ai.saved")));
        if (result.result.editor_path) window.location.assign(String(result.result.editor_path));
      }
      if (kind === "DELETE") await api.deleteAiDraft(draft.id);
      await onChanged();
    } catch (value) {
      onError(errorText(value));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" gap={1}>
        <Box>
          <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
            <Typography fontWeight={800}>{draft.draft_type}</Typography>
            <Chip size="small" label={draft.status} />
            <Chip size="small" variant="outlined" label={`${draft.google_environment} · v${draft.version}`} />
          </Stack>
          <Typography variant="caption" color="text.secondary">{formatDate(draft.created_at)} · expires {formatDate(draft.expires_at)}</Typography>
        </Box>
        <Stack direction="row" gap={1} flexWrap="wrap">
          {draft.draft_type === "ACTION_SELECTION" && <Button size="small" variant="outlined" onClick={() => void perform("PREVIEW")} disabled={busy || !canApply}>{ai("ai.preview")}</Button>}
          <Button size="small" variant="contained" onClick={() => void perform("APPLY")} disabled={busy || !canApply}>{ai("ai.apply")}</Button>
          <Tooltip title={ai("ai.discard")}><span><IconButton color="error" onClick={() => void perform("DELETE")} disabled={busy}><DeleteOutlineIcon /></IconButton></span></Tooltip>
        </Stack>
      </Stack>
      <Alert severity="warning" sx={{ my: 1.5 }}>{ai("ai.confirmDraft")}</Alert>
      <TextField fullWidth multiline minRows={5} maxRows={18} label={ai("ai.editDraft")} value={payload} onChange={(event) => setPayload(event.target.value)} inputProps={{ spellCheck: false }} />
      <Button sx={{ mt: 1 }} startIcon={<EditOutlinedIcon />} onClick={() => void perform("SAVE")} disabled={busy}>{ai("ai.saveDraft")}</Button>
    </Paper>
  );
}

function ReportWorkspace({ reports, loading, onChanged, onError }: {
  reports: AiReport[];
  loading: boolean;
  onChanged: () => Promise<unknown>;
  onError: (value: string) => void;
}) {
  if (loading) return <LinearProgress />;
  if (!reports.length) return <Alert severity="info">{ai("ai.noReports")}</Alert>;
  return (
    <Stack spacing={1.5}>
      {reports.map((report) => (
        <Paper key={report.id} variant="outlined" sx={{ p: 2 }}>
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={1.5}>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="h6">{report.title}</Typography>
              <Typography variant="caption" color="text.secondary">
                {formatDate(report.observed_at || report.created_at)}
              </Typography>
              {report.report?.content?.answer && (
                <Typography sx={{ mt: 1, whiteSpace: "pre-wrap" }}>{String(report.report.content.answer)}</Typography>
              )}
              <Stack direction="row" gap={0.75} flexWrap="wrap" sx={{ mt: 1 }}>
                {(report.report?.configuration?.sections || []).map((section: string) => (
                  <Chip key={section} size="small" variant="outlined" label={section} />
                ))}
              </Stack>
            </Box>
            <Stack direction="row" alignItems="flex-start">
              <Tooltip title={ai("ai.export")}>
                <IconButton component="a" href={api.aiReportExportUrl(report.id)}><DownloadIcon /></IconButton>
              </Tooltip>
              <Tooltip title={ai("ai.delete")}>
                <IconButton color="error" onClick={async () => {
                  if (!window.confirm(`${ai("ai.delete")}: ${report.title}?`)) return;
                  try {
                    await api.deleteAiReport(report.id);
                    await onChanged();
                  } catch (value) { onError(errorText(value)); }
                }}><DeleteOutlineIcon /></IconButton>
              </Tooltip>
            </Stack>
          </Stack>
        </Paper>
      ))}
    </Stack>
  );
}

function AiAdminWorkspace({ onError, onNotice }: { onError: (value: string) => void; onNotice: (value: string) => void }) {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["ai-admin-settings"], queryFn: api.aiAdminSettings });
  const usage = useQuery({ queryKey: ["ai-usage"], queryFn: () => api.aiUsage(30) });
  const sources = useQuery({ queryKey: ["ai-source-registry"], queryFn: api.aiSourceRegistry });
  const [apiKey, setApiKey] = useState("");
  const [limits, setLimits] = useState<Record<string, string>>({});
  useEffect(() => {
    if (!settings.data) return;
    setLimits(Object.fromEntries([
      "daily_soft_budget_usd", "daily_hard_budget_usd", "monthly_hard_budget_usd",
      "user_daily_hard_budget_usd", "user_monthly_hard_budget_usd", "retention_days",
      "provider_circuit_failure_threshold", "provider_circuit_cooldown_seconds",
      "second_approval_threshold_micros"
    ].map((key) => [key, String(settings.data[key] ?? "")])));
  }, [settings.data]);
  const update = async (payload: Record<string, unknown>) => {
    try {
      await api.patchAiAdminSettings(payload);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ai-admin-settings"] }),
        queryClient.invalidateQueries({ queryKey: ["ai-capabilities"] }),
        queryClient.invalidateQueries({ queryKey: ["ai-usage"] })
      ]);
      setApiKey("");
      onNotice(ai("ai.saved"));
    } catch (value) { onError(errorText(value)); }
  };
  const totals = usage.data?.totals || {};
  const health = usage.data?.run_health || {};
  if (settings.isLoading) return <LinearProgress />;
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(2, minmax(0, 1fr))", md: "repeat(6, minmax(0, 1fr))" }, gap: 1.5 }}>
        <Metric label={ai("ai.requests")} value={formatNumber(Number(totals.requests || 0))} />
        <Metric label={ai("ai.tokens")} value={formatNumber(Number(totals.input_tokens || 0) + Number(totals.output_tokens || 0))} />
        <Metric label={ai("ai.cost")} value={`$${Number(totals.estimated_cost_usd || 0).toFixed(4)}`} />
        <Metric label={ai("ai.toolCalls")} value={formatNumber(Number(totals.tool_calls || 0))} />
        <Metric label={ai("ai.errors")} value={formatNumber(Number(totals.errors || 0))} />
        <Metric label={ai("ai.averageLatency")} value={health.average_latency_ms ? `${formatNumber(health.average_latency_ms)} ms` : "—"} />
      </Box>

      <Box sx={{ borderTop: 1, borderColor: "divider", pt: 2 }}>
        <Typography variant="h6">{ai("ai.usage")}</Typography>
        <Stack direction="row" gap={1} flexWrap="wrap" sx={{ mt: 1 }}>
          {Object.entries(usage.data?.budgets || {}).map(([key, value]) => <Chip key={key} size="small" variant="outlined" label={`${key}: $${value}`} />)}
        </Stack>
        <Box sx={{ mt: 1.5, maxHeight: 280, overflowY: "auto", borderTop: 1, borderColor: "divider" }}>
          {(usage.data?.items || []).slice().reverse().map((item: Record<string, any>, index: number) => (
            <Stack key={`${item.date}-${item.user_id}-${item.model_id}-${index}`} direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={1} sx={{ py: 1, borderBottom: 1, borderColor: "divider" }}>
              <Box><Typography variant="body2" fontWeight={700}>{item.date} · {item.user_name}</Typography><Typography variant="caption" color="text.secondary">{item.model_id}</Typography></Box>
              <Typography variant="body2">{item.requests} {ai("ai.requestsShort")} · {formatNumber(item.input_tokens + item.output_tokens)} {ai("ai.tokensShort")} · {item.tool_calls} {ai("ai.toolsShort")} · {item.errors} {ai("ai.errorsShort")} · ${Number(item.estimated_cost_usd).toFixed(4)}</Typography>
            </Stack>
          ))}
        </Box>
        <Stack direction="row" gap={1} flexWrap="wrap" sx={{ mt: 1 }}>
          {Object.entries(health.by_error_code || {}).map(([key, value]) => <Chip key={key} color="error" size="small" label={`${key}: ${value}`} />)}
          {Object.entries(health.tool_usage || {}).map(([key, value]) => <Chip key={key} size="small" label={`${key}: ${value}`} />)}
        </Stack>
      </Box>

      <Box sx={{ borderTop: 1, borderColor: "divider", pt: 2 }}>
        <Typography variant="h6">{ai("ai.dataSources")}</Typography>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(2, minmax(0, 1fr))" }, gap: 1.5, mt: 1.5 }}>
          {(sources.data || []).map((item) => (
            <Paper key={item.capabilities.provider_id} variant="outlined" sx={{ p: 1.5 }}>
              <Stack direction="row" justifyContent="space-between" gap={1} alignItems="center">
                <Typography fontWeight={800}>{item.capabilities.label}</Typography>
                <Chip size="small" color={item.status.enabled ? "success" : "default"} label={item.status.setup_status} />
              </Stack>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>{item.status.explanation}</Typography>
              <Typography variant="caption" color="text.secondary">{ai("ai.activeMappings")}: {item.status.active_mappings} · {ai("ai.provenance")} v{item.capabilities.provenance_version}</Typography>
            </Paper>
          ))}
        </Box>
      </Box>

      <Box sx={{ borderTop: 1, borderColor: "divider", pt: 2 }}>
        <Typography variant="h6">{ai("ai.settings")}</Typography>
        <Stack direction={{ xs: "column", sm: "row" }} gap={1.5} flexWrap="wrap" sx={{ mt: 1 }}>
          {[
            ["enabled", ai("ai.enabled")], ["kill_switch", ai("ai.killSwitchLabel")],
            ["deterministic_routing", ai("ai.deterministicRouting")], ["production_read_enabled", ai("ai.productionRead")],
            ["production_actions_enabled", ai("ai.productionActions")], ["pause_actions_enabled", ai("ai.pauseActions")],
            ["enable_actions_enabled", ai("ai.enableActions")], ["budget_actions_enabled", ai("ai.budgetActions")],
            ["demand_gen_actions_enabled", ai("ai.demandGenActions")], ["live_rules_enabled", ai("ai.liveRules")]
          ].map(([key, label]) => (
            <FormControlLabel key={key} control={<Switch checked={Boolean(settings.data?.[key])} color={key === "kill_switch" ? "error" : "primary"} onChange={(event) => void update({ [key]: event.target.checked })} />} label={label} />
          ))}
        </Stack>
        <Alert severity="warning" sx={{ my: 1.5 }}>{ai("ai.productionLocked")}. {ai("ai.gatesDoNotExecute")}</Alert>
        <Stack direction={{ xs: "column", sm: "row" }} gap={1.5}>
          <TextField type="password" fullWidth label={ai("ai.openAiKey")} value={apiKey} onChange={(event) => setApiKey(event.target.value)} helperText={`${settings.data?.openai_key_source || "NOT_CONFIGURED"} · ${ai("ai.keyNeverShown")}`} />
          <Button variant="contained" disabled={apiKey.length < 20} onClick={() => void update({ openai_api_key: apiKey })}>{ai("ai.save")}</Button>
        </Stack>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" }, gap: 1.5, mt: 2 }}>
          {Object.entries(limits).map(([key, value]) => <TextField key={key} size="small" type="number" label={ai(`ai.limit.${key}`)} value={value} onChange={(event) => setLimits({ ...limits, [key]: event.target.value })} />)}
        </Box>
        <Button sx={{ mt: 1.5 }} variant="outlined" onClick={() => void update(Object.fromEntries(Object.entries(limits).map(([key, value]) => [key, key === "second_approval_threshold_micros" && !value.trim() ? null : Number(value)])))}>{ai("ai.save")}</Button>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", xl: "repeat(3, minmax(0, 1fr))" }, gap: 1.5, mt: 2 }}>
          {(settings.data?.models || []).map((item: Record<string, any>) => <ModelProfileEditor key={item.name} item={item} onError={onError} onSaved={async () => { await settings.refetch(); onNotice(ai("ai.saved")); }} />)}
        </Box>
      </Box>

      <GeoSettings onError={onError} onNotice={onNotice} />
      <MetricMappingSettings sources={sources.data || []} onError={onError} onNotice={onNotice} />
    </Stack>
  );
}

function ModelProfileEditor({ item, onError, onSaved }: { item: Record<string, any>; onError: (value: string) => void; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState({
    enabled: Boolean(item.enabled), reasoning_effort: String(item.reasoning_effort), verbosity: String(item.verbosity),
    timeout_seconds: String(item.timeout_seconds), max_input_tokens: String(item.max_input_tokens), max_output_tokens: String(item.max_output_tokens),
    input: String(item.price_metadata?.input ?? ""), cached_input: String(item.price_metadata?.cached_input ?? ""), output: String(item.price_metadata?.output ?? "")
  });
  const save = async () => {
    try {
      await api.patchAiModelProfile(item.name, {
        enabled: form.enabled,
        reasoning_effort: form.reasoning_effort,
        verbosity: form.verbosity,
        timeout_seconds: Number(form.timeout_seconds),
        max_input_tokens: Number(form.max_input_tokens),
        max_output_tokens: Number(form.max_output_tokens),
        price_metadata: { ...item.price_metadata, input: Number(form.input), cached_input: Number(form.cached_input), output: Number(form.output), updated_on: new Date().toISOString().slice(0, 10) }
      });
      await onSaved();
    } catch (value) { onError(errorText(value)); }
  };
  return (
    <Paper variant="outlined" sx={{ p: 1.5, minWidth: 0 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center"><Typography fontWeight={800}>{item.name}</Typography><Switch size="small" checked={form.enabled} onChange={(event) => setForm({ ...form, enabled: event.target.checked })} /></Stack>
      <Typography variant="body2" fontFamily="monospace" sx={{ overflowWrap: "anywhere" }}>{item.model_id}</Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 1, mt: 1.5 }}>
        <FormControl size="small"><InputLabel>{ai("ai.reasoning")}</InputLabel><Select label={ai("ai.reasoning")} value={form.reasoning_effort} onChange={(event) => setForm({ ...form, reasoning_effort: event.target.value })}>{["none", "low", "medium", "high", "xhigh", "max"].map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</Select></FormControl>
        <FormControl size="small"><InputLabel>{ai("ai.verbosity")}</InputLabel><Select label={ai("ai.verbosity")} value={form.verbosity} onChange={(event) => setForm({ ...form, verbosity: event.target.value })}>{["low", "medium", "high"].map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}</Select></FormControl>
        <TextField size="small" type="number" label={ai("ai.timeoutSeconds")} value={form.timeout_seconds} onChange={(event) => setForm({ ...form, timeout_seconds: event.target.value })} />
        <TextField size="small" type="number" label={ai("ai.maxOutputTokens")} value={form.max_output_tokens} onChange={(event) => setForm({ ...form, max_output_tokens: event.target.value })} />
        <TextField size="small" type="number" label={ai("ai.maxInputTokens")} value={form.max_input_tokens} onChange={(event) => setForm({ ...form, max_input_tokens: event.target.value })} />
        <TextField size="small" type="number" label={ai("ai.inputPrice")} value={form.input} onChange={(event) => setForm({ ...form, input: event.target.value })} />
        <TextField size="small" type="number" label={ai("ai.cachedInputPrice")} value={form.cached_input} onChange={(event) => setForm({ ...form, cached_input: event.target.value })} />
        <TextField size="small" type="number" label={ai("ai.outputPrice")} value={form.output} onChange={(event) => setForm({ ...form, output: event.target.value })} />
      </Box>
      <Button size="small" sx={{ mt: 1.5 }} variant="outlined" onClick={() => void save()}>{ai("ai.save")}</Button>
    </Paper>
  );
}

const EMPTY_GEO_FORM: Record<string, string> = {
  scope_type: "GLOBAL", scope_id: "", geo_id: "", time_zone: "UTC", expected_currencies: "USD", default_reporting_period: "7d", primary_metric_source: "GOOGLE_ADS",
  target_cpl: "", target_registration_cpa: "", target_deposit_cpa: "", target_roas: "", max_spend_without_lead: "", max_spend_without_registration: "", max_spend_without_deposit: "",
  minimum_clicks: "0", minimum_impressions: "0", minimum_spend: "0", conversion_lag_hours: "24", alert_thresholds: "{}", owner_comment: "", effective_from: "", effective_until: ""
};

function GeoSettings({ onError, onNotice }: { onError: (value: string) => void; onNotice: (value: string) => void }) {
  const profiles = useQuery({ queryKey: ["ai-geo-profiles"], queryFn: api.aiGeoProfiles });
  const overrides = useQuery({ queryKey: ["ai-geo-overrides"], queryFn: api.aiGeoOverrides });
  const [form, setForm] = useState(EMPTY_GEO_FORM);
  const [override, setOverride] = useState({ scope_type: "ACCOUNT", scope_id: "", profile_id: "", override_values: "{}", is_active: true });
  const [history, setHistory] = useState<{ title: string; items: Array<Record<string, any>> } | null>(null);
  const set = (key: string, value: string) => setForm({ ...form, [key]: value });
  const save = async () => {
    try {
      await api.createAiGeoProfile({
        scope_type: form.scope_type, scope_id: form.scope_type === "GLOBAL" ? null : form.scope_id, geo_id: form.geo_id || null,
        time_zone: form.time_zone, expected_currencies: form.expected_currencies.split(",").map((item) => item.trim().toUpperCase()).filter(Boolean),
        default_reporting_period: form.default_reporting_period, primary_metric_source: form.primary_metric_source,
        target_cpl: optionalNumber(form.target_cpl), target_registration_cpa: optionalNumber(form.target_registration_cpa), target_deposit_cpa: optionalNumber(form.target_deposit_cpa), target_roas: optionalNumber(form.target_roas),
        max_spend_without_lead: optionalNumber(form.max_spend_without_lead), max_spend_without_registration: optionalNumber(form.max_spend_without_registration), max_spend_without_deposit: optionalNumber(form.max_spend_without_deposit),
        minimum_clicks: Number(form.minimum_clicks), minimum_impressions: Number(form.minimum_impressions), minimum_spend: Number(form.minimum_spend), conversion_lag_hours: Number(form.conversion_lag_hours),
        alert_thresholds: JSON.parse(form.alert_thresholds), owner_comment: form.owner_comment || null,
        effective_from: form.effective_from ? new Date(form.effective_from).toISOString() : null, effective_until: form.effective_until ? new Date(form.effective_until).toISOString() : null
      });
      await profiles.refetch(); onNotice(ai("ai.saved"));
    } catch (value) { onError(errorText(value)); }
  };
  return (
    <Box sx={{ borderTop: 1, borderColor: "divider", pt: 2 }}>
      <Typography variant="h6">{ai("ai.geoProfiles")}</Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(4, 1fr)" }, gap: 1.25, mt: 1.5 }}>
        <SelectField label={ai("ai.scopeType")} value={form.scope_type} values={["GLOBAL", "GEO", "MCC", "ACCOUNT", "CAMPAIGN"]} onChange={(value) => set("scope_type", value)} />
        <TextField size="small" label={ai("ai.scopeId")} disabled={form.scope_type === "GLOBAL"} value={form.scope_id} onChange={(event) => set("scope_id", event.target.value)} />
        <TextField size="small" label={ai("ai.geoId")} value={form.geo_id} onChange={(event) => set("geo_id", event.target.value)} />
        <TextField size="small" label={ai("ai.timezone")} value={form.time_zone} onChange={(event) => set("time_zone", event.target.value)} />
        <TextField size="small" label={ai("ai.currencies")} value={form.expected_currencies} onChange={(event) => set("expected_currencies", event.target.value)} />
        <SelectField label={ai("ai.period")} value={form.default_reporting_period} values={["today", "yesterday", "3d", "7d", "30d"]} onChange={(value) => set("default_reporting_period", value)} />
        <SelectField label={ai("ai.primarySource")} value={form.primary_metric_source} values={["GOOGLE_ADS", "KEITARO", "BROCARD", "BUSINESS"]} onChange={(value) => set("primary_metric_source", value)} />
        {["target_cpl", "target_registration_cpa", "target_deposit_cpa", "target_roas", "max_spend_without_lead", "max_spend_without_registration", "max_spend_without_deposit", "minimum_clicks", "minimum_impressions", "minimum_spend", "conversion_lag_hours"].map((key) => <TextField key={key} size="small" type="number" label={ai(`ai.field.${key}`)} value={form[key]} onChange={(event) => set(key, event.target.value)} />)}
        <TextField size="small" label={ai("ai.alertThresholds")} value={form.alert_thresholds} onChange={(event) => set("alert_thresholds", event.target.value)} />
        <TextField size="small" type="datetime-local" label={ai("ai.effectiveFrom")} InputLabelProps={{ shrink: true }} value={form.effective_from} onChange={(event) => set("effective_from", event.target.value)} />
        <TextField size="small" type="datetime-local" label={ai("ai.effectiveUntil")} InputLabelProps={{ shrink: true }} value={form.effective_until} onChange={(event) => set("effective_until", event.target.value)} />
        <TextField size="small" label={ai("ai.ownerComment")} value={form.owner_comment} onChange={(event) => set("owner_comment", event.target.value)} />
      </Box>
      <Button sx={{ mt: 1.5 }} variant="outlined" startIcon={<AddIcon />} disabled={form.scope_type !== "GLOBAL" && !form.scope_id.trim()} onClick={() => void save()}>{ai("ai.geoProfiles")}</Button>
      <Stack spacing={1} sx={{ mt: 1.5 }}>
        {(profiles.data || []).map((item) => (
          <Paper key={String(item.id)} variant="outlined" sx={{ p: 1.5 }}>
            <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" gap={1}>
              <Box><Typography fontWeight={800}>{item.scope_type}{item.scope_id ? ` · ${item.scope_id}` : ""} · v{item.version}</Typography><Typography variant="body2">{item.time_zone} · {(item.expected_currencies || []).join(", ") || "—"} · {item.primary_metric_source}</Typography><Typography variant="caption" color="text.secondary">CPL {item.target_cpl ?? "—"} · registration CPA {item.target_registration_cpa ?? "—"} · deposit CPA {item.target_deposit_cpa ?? "—"} · ROAS {item.target_roas ?? "—"}</Typography></Box>
              <Button size="small" onClick={async () => { try { setHistory({ title: `${item.scope_type} v${item.version}`, items: await api.aiGeoProfileHistory(String(item.id)) }); } catch (value) { onError(errorText(value)); } }}>{ai("ai.history")}</Button>
            </Stack>
          </Paper>
        ))}
      </Stack>
      <Typography variant="subtitle1" fontWeight={800} sx={{ mt: 2 }}>{ai("ai.overrides")}</Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(4, 1fr)" }, gap: 1.25, mt: 1 }}>
        <SelectField label={ai("ai.scopeType")} value={override.scope_type} values={["MCC", "ACCOUNT", "CAMPAIGN"]} onChange={(value) => setOverride({ ...override, scope_type: value })} />
        <TextField size="small" label={ai("ai.scopeId")} value={override.scope_id} onChange={(event) => setOverride({ ...override, scope_id: event.target.value })} />
        <TextField size="small" label={ai("ai.profileId")} value={override.profile_id} onChange={(event) => setOverride({ ...override, profile_id: event.target.value })} />
        <TextField size="small" label={ai("ai.overrideValues")} value={override.override_values} onChange={(event) => setOverride({ ...override, override_values: event.target.value })} />
      </Box>
      <Button sx={{ mt: 1 }} variant="outlined" disabled={!override.scope_id.trim()} onClick={async () => { try { await api.putAiGeoOverride(override.scope_type, override.scope_id, { ...override, profile_id: override.profile_id || null, override_values: JSON.parse(override.override_values) }); await overrides.refetch(); onNotice(ai("ai.saved")); } catch (value) { onError(errorText(value)); } }}>{ai("ai.save")}</Button>
      <Stack direction="row" gap={1} flexWrap="wrap" sx={{ mt: 1 }}>{(overrides.data || []).map((item) => <Chip key={String(item.id)} size="small" label={`${item.scope_type} · ${item.scope_id} · ${item.is_active ? "ACTIVE" : "OFF"}`} />)}</Stack>
      <Dialog open={Boolean(history)} onClose={() => setHistory(null)} fullWidth maxWidth="md"><DialogTitle>{history?.title}</DialogTitle><DialogContent><Stack spacing={1}>{history?.items.length ? history.items.map((item) => <Paper key={String(item.id)} variant="outlined" sx={{ p: 1.5 }}><Typography fontWeight={700}>v{item.version} · {formatDate(item.changed_at)}</Typography><Typography variant="body2" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(item.snapshot, null, 2)}</Typography></Paper>) : <Alert severity="info">{ai("ai.noPreviousVersions")}</Alert>}</Stack></DialogContent><DialogActions><Button onClick={() => setHistory(null)}>{ai("ai.close")}</Button></DialogActions></Dialog>
    </Box>
  );
}

function MetricMappingSettings({ sources, onError, onNotice }: { sources: AiSourceRegistryItem[]; onError: (value: string) => void; onNotice: (value: string) => void }) {
  const mappings = useQuery({ queryKey: ["ai-metric-mappings"], queryFn: api.aiMetricMappings });
  const [form, setForm] = useState({ scope_type: "GLOBAL", scope_id: "", semantic_metric: "REGISTRATION", provider: "GOOGLE_ADS", source_id: "", source_name: "", attribution_model: "" });
  return (
    <Box sx={{ borderTop: 1, borderColor: "divider", pt: 2 }}>
      <Typography variant="h6">{ai("ai.metricMappings")}</Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(4, 1fr)" }, gap: 1.25, mt: 1.5 }}>
        <SelectField label={ai("ai.scopeType")} value={form.scope_type} values={["GLOBAL", "GEO", "MCC", "ACCOUNT", "CAMPAIGN"]} onChange={(value) => setForm({ ...form, scope_type: value })} />
        <TextField size="small" label={ai("ai.scopeId")} disabled={form.scope_type === "GLOBAL"} value={form.scope_id} onChange={(event) => setForm({ ...form, scope_id: event.target.value })} />
        <SelectField label={ai("ai.metric")} value={form.semantic_metric} values={["LEAD", "REGISTRATION", "DEPOSIT", "PURCHASE", "REVENUE"]} onChange={(value) => setForm({ ...form, semantic_metric: value })} />
        <FormControl size="small"><InputLabel>{ai("ai.provider")}</InputLabel><Select label={ai("ai.provider")} value={form.provider} onChange={(event) => setForm({ ...form, provider: event.target.value })}>{sources.map((item) => <MenuItem key={item.capabilities.provider_id} value={item.capabilities.provider_id}>{item.capabilities.label} · {item.status.setup_status}</MenuItem>)}</Select></FormControl>
        <TextField size="small" label={ai("ai.sourceId")} value={form.source_id} onChange={(event) => setForm({ ...form, source_id: event.target.value })} />
        <TextField size="small" label={ai("ai.sourceName")} value={form.source_name} onChange={(event) => setForm({ ...form, source_name: event.target.value })} />
        <TextField size="small" label={ai("ai.attributionModel")} value={form.attribution_model} onChange={(event) => setForm({ ...form, attribution_model: event.target.value })} />
      </Box>
      <Button sx={{ mt: 1.5 }} variant="outlined" startIcon={<AddIcon />} disabled={!form.source_id.trim() || (form.scope_type !== "GLOBAL" && !form.scope_id.trim())} onClick={async () => { try { await api.createAiMetricMapping({ ...form, scope_id: form.scope_type === "GLOBAL" ? null : form.scope_id, source_name: form.source_name || null, attribution_model: form.attribution_model || null, is_active: true, metadata: {} }); await mappings.refetch(); onNotice(ai("ai.saved")); } catch (value) { onError(errorText(value)); } }}>{ai("ai.save")}</Button>
      <Stack spacing={1} sx={{ mt: 1.5 }}>{(mappings.data || []).map((item) => <Paper key={String(item.id)} variant="outlined" sx={{ p: 1.5 }}><Stack direction="row" justifyContent="space-between" alignItems="center" gap={1}><Box sx={{ minWidth: 0 }}><Typography fontWeight={800}>{item.semantic_metric} ← {item.provider}</Typography><Typography variant="body2" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>{item.scope_type}{item.scope_id ? ` · ${item.scope_id}` : ""} · {item.source_name || item.source_id} · {item.attribution_model || ai("ai.noAttribution")}</Typography></Box><Tooltip title={ai("ai.delete")}><IconButton color="error" onClick={async () => { try { await api.deleteAiMetricMapping(String(item.id)); await mappings.refetch(); } catch (value) { onError(errorText(value)); } }}><DeleteOutlineIcon /></IconButton></Tooltip></Stack></Paper>)}</Stack>
    </Box>
  );
}

function SelectField({ label, value, values, onChange }: { label: string; value: string; values: string[]; onChange: (value: string) => void }) {
  return <FormControl size="small"><InputLabel>{label}</InputLabel><Select label={label} value={value} onChange={(event) => onChange(event.target.value)}>{values.map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</Select></FormControl>;
}

function optionalNumber(value: string) {
  return value.trim() ? Number(value) : null;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <Box sx={{ borderLeft: 3, borderColor: "primary.main", pl: 1.5, py: 0.75 }}><Typography variant="caption" color="text.secondary">{label}</Typography><Typography variant="h6">{value}</Typography></Box>;
}

function errorText(value: unknown) {
  return value instanceof Error ? value.message : String(value);
}
