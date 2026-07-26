import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography
} from "@mui/material";
import MarkEmailReadOutlinedIcon from "@mui/icons-material/MarkEmailReadOutlined";
import RefreshIcon from "@mui/icons-material/Refresh";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import SyncIcon from "@mui/icons-material/Sync";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate, t } from "../i18n";

export function ModerationPage() {
  return <GoogleDataPage kind="moderation" title={t("ui.80ae616e0b")} />;
}

export function StatisticsPage() {
  return <GoogleDataPage kind="statistics" title={t("ui.a77d7f6c0d")} />;
}

function GoogleDataPage({ kind, title }: { kind: "moderation" | "statistics"; title: string }) {
  const queryClient = useQueryClient();
  const connections = useQuery({ queryKey: ["connections"], queryFn: api.listConnections });
  const data = useQuery({
    queryKey: [kind],
    queryFn: kind === "moderation" ? api.listModeration : api.listStatistics,
    refetchInterval: 10000
  });
  const [connectionId, setConnectionId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const sync = useMutation({
    mutationFn: () => api.queueOperationSync(kind, connectionId),
    onSuccess: (result) => {
      setMessage(t("operations.jobQueued", { id: result.job_id.slice(0, 8) }));
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }
  });
  const error = data.error || sync.error;
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Typography variant="h4">{title}</Typography>
        <Stack direction="row" spacing={1}>
          <FormControl size="small" sx={{ minWidth: 240 }}><InputLabel>{t("ui.97cb28fe6f")}</InputLabel><Select label={t("ui.97cb28fe6f")} value={connectionId} onChange={(e) => setConnectionId(e.target.value)}>{(connections.data || []).map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · {item.status}</MenuItem>)}</Select></FormControl>
          <Button variant="contained" startIcon={<SyncIcon />} disabled={!connectionId || sync.isPending} onClick={() => sync.mutate()}>{t("ui.289c55ebed")}</Button>
        </Stack>
      </Box>
      {error && <Alert severity="error">{error.message}</Alert>}
      {message && <Alert severity="success" onClose={() => setMessage(null)}>{message}</Alert>}
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
        {kind === "moderation" ? <ModerationTable rows={data.data || []} /> : <StatisticsTable rows={data.data || []} />}
      </Box>
    </Stack>
  );
}

function ModerationTable({ rows }: { rows: Array<Record<string, any>> }) {
  return <Table size="small"><TableHead><TableRow><TableCell>Customer ID</TableCell><TableCell>{t("ui.5ceeb4c2d2")}</TableCell><TableCell>{t("ui.f7f293b5c5")}</TableCell><TableCell>{t("ui.31cfa1d27e")}</TableCell><TableCell>{t("ui.7b3bb04ef1")}</TableCell></TableRow></TableHead><TableBody>{rows.map((row) => <TableRow key={row.id}><TableCell>{row.customer_id}</TableCell><TableCell sx={{ fontFamily: "monospace", overflowWrap: "anywhere" }}>{row.resource_name}</TableCell><TableCell><StatusBadge value={row.approval_status} /></TableCell><TableCell>{(row.policy_topics || []).map((item: any) => item.topic).join(", ") || "—"}</TableCell><TableCell>{formatDate(row.checked_at)}</TableCell></TableRow>)}{!rows.length && <EmptyRow columns={5} text={t("ui.b23dbad476")} />}</TableBody></Table>;
}

function StatisticsTable({ rows }: { rows: Array<Record<string, any>> }) {
  return <Table size="small"><TableHead><TableRow><TableCell>{t("ui.a5b49d2eba")}</TableCell><TableCell>Customer ID</TableCell><TableCell align="right">{t("ui.8d112fb582")}</TableCell><TableCell align="right">{t("ui.07e2b83b27")}</TableCell><TableCell align="right">{t("ui.a470ac24e2")}</TableCell><TableCell align="right">{t("ui.4150f46b4a")}</TableCell></TableRow></TableHead><TableBody>{rows.map((row) => <TableRow key={row.id}><TableCell>{row.snapshot_date}</TableCell><TableCell>{row.customer_id}</TableCell><TableCell align="right">{row.metrics?.impressions || 0}</TableCell><TableCell align="right">{row.metrics?.clicks || 0}</TableCell><TableCell align="right">{((row.metrics?.cost_micros || 0) / 1_000_000).toFixed(2)}</TableCell><TableCell align="right">{Number(row.metrics?.conversions || 0).toFixed(2)}</TableCell></TableRow>)}{!rows.length && <EmptyRow columns={6} text={t("ui.ff3cef635c")} />}</TableBody></Table>;
}

export function FinancePage() {
  const queryClient = useQueryClient();
  const finance = useQuery({ queryKey: ["finance"], queryFn: api.listFinance, refetchInterval: 5000 });
  const [form, setForm] = useState({ name: "Brocard", api_token: "", api_base_url: "https://private.mybrocard.com" });
  const [message, setMessage] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () => api.configureFinance(form),
    onSuccess: () => {
      setForm({ ...form, api_token: "" });
      setMessage(t("ui.b30f9ec673"));
      queryClient.invalidateQueries({ queryKey: ["finance"] });
    }
  });
  const sync = useMutation({
    mutationFn: (id: string) => api.syncFinance(id),
    onSuccess: (result) => {
      setMessage(t("operations.syncQueued", { id: result.job_id.slice(0, 8) }));
      queryClient.invalidateQueries({ queryKey: ["finance"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }
  });
  return (
    <Stack spacing={3}>
      <Typography variant="h4">{t("ui.da65f953fb")}</Typography>
      {(finance.error || save.error || sync.error) && <Alert severity="error">{finance.error?.message || save.error?.message || sync.error?.message}</Alert>}
      {message && <Alert severity="success" onClose={() => setMessage(null)}>{message}</Alert>}
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={3}><TextField fullWidth label={t("ui.7c5815637f")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Grid>
          <Grid item xs={12} md={4}><TextField fullWidth type="password" label={t("field.apiToken")} value={form.api_token} onChange={(e) => setForm({ ...form, api_token: e.target.value })} /></Grid>
          <Grid item xs={12} md={5}><TextField fullWidth label="API base URL" value={form.api_base_url} onChange={(e) => setForm({ ...form, api_base_url: e.target.value })} /></Grid>
        </Grid>
        <Alert severity="info" sx={{ mt: 2 }}>{t("ui.98a65e2fdd")}</Alert>
        <Button sx={{ mt: 2 }} variant="contained" startIcon={<SaveOutlinedIcon />} disabled={!form.api_token || save.isPending} onClick={() => save.mutate()}>{t("ui.4864057d62")}</Button>
      </Paper>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", bgcolor: "background.paper" }}><Table size="small"><TableHead><TableRow><TableCell>{t("ui.eb0b9b0d90")}</TableCell><TableCell>{t("ui.2d385af6d6")}</TableCell><TableCell>{t("ui.f7f293b5c5")}</TableCell><TableCell>{t("ui.5266d4a020")}</TableCell><TableCell>{t("ui.f5585974e7")}</TableCell><TableCell>{t("ui.05df0b42f4")}</TableCell><TableCell align="right">{t("ui.4fe9c0675c")}</TableCell></TableRow></TableHead><TableBody>{(finance.data || []).map((row) => <TableRow key={row.id}><TableCell>{row.name}</TableCell><TableCell>{row.provider}</TableCell><TableCell><StatusBadge value={row.status} /></TableCell><TableCell>{row.latest_snapshot ? `${row.latest_snapshot.balance} ${row.latest_snapshot.currency}` : "—"}</TableCell><TableCell>{row.latest_snapshot ? `${row.latest_snapshot.cards_active}/${row.latest_snapshot.cards_total}` : "—"}</TableCell><TableCell>{formatDate(row.updated_at)}</TableCell><TableCell align="right"><Button size="small" startIcon={<SyncIcon />} disabled={row.status === "SYNCING" || sync.isPending} onClick={() => sync.mutate(row.id)}>{t("ui.289c55ebed")}</Button></TableCell></TableRow>)}{!finance.data?.length && <EmptyRow columns={7} text={t("ui.daf4e830c5")} />}</TableBody></Table></Box>
    </Stack>
  );
}

export function AlertsPage() {
  const queryClient = useQueryClient();
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: api.listAlerts });
  const mark = useMutation({ mutationFn: ({ id, read }: { id: string; read: boolean }) => api.setAlertRead(id, read), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["alerts"] }); queryClient.invalidateQueries({ queryKey: ["dashboard"] }); } });
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="h4">{t("ui.ee3c35f311")}</Typography><Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => alerts.refetch()}>{t("ui.c2f668e54f")}</Button></Box>
      {alerts.error && <Alert severity="error">{alerts.error.message}</Alert>}
      <Box sx={{ border: 1, borderColor: "divider", bgcolor: "background.paper" }}><Table size="small"><TableHead><TableRow><TableCell padding="checkbox" /><TableCell>{t("ui.c80d7e8172")}</TableCell><TableCell>{t("ui.d9f964d71b")}</TableCell><TableCell>{t("ui.bb92633bf5")}</TableCell><TableCell>{t("ui.dc72346ac4")}</TableCell></TableRow></TableHead><TableBody>{(alerts.data || []).map((row) => <TableRow key={row.id} sx={{ opacity: row.read_at ? 0.62 : 1 }}><TableCell padding="checkbox"><Checkbox icon={<MarkEmailReadOutlinedIcon />} checkedIcon={<MarkEmailReadOutlinedIcon />} checked={Boolean(row.read_at)} onChange={(e) => mark.mutate({ id: row.id, read: e.target.checked })} /></TableCell><TableCell>{formatDate(row.created_at)}</TableCell><TableCell><StatusBadge value={row.severity} /></TableCell><TableCell>{row.title}</TableCell><TableCell>{row.message}</TableCell></TableRow>)}{!alerts.data?.length && <EmptyRow columns={5} text={t("ui.5c5a86cf4c")} />}</TableBody></Table></Box>
    </Stack>
  );
}

export function SettingsPage() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const guardrails = useQuery({ queryKey: ["campaign-builder-guardrails"], queryFn: api.getCampaignBuilderGuardrails });
  const queryClient = useQueryClient();
  const [limits, setLimits] = useState({ perAccount: "50", perJob: "500", parallel: "20", budgets: "" });
  useEffect(() => {
    if (!guardrails.data) return;
    setLimits({
      perAccount: String(guardrails.data.max_campaigns_per_account ?? 50),
      perJob: String(guardrails.data.max_campaigns_per_job ?? 500),
      parallel: String(guardrails.data.max_parallel_enabled ?? 20),
      budgets: Object.entries(guardrails.data.max_budget_by_currency || {}).map(([key, value]) => `${key}:${value}`).join(", ")
    });
  }, [guardrails.data]);
  const saveLimits = useMutation({
    mutationFn: () => api.updateCampaignBuilderGuardrails({
      max_campaigns_per_account: Number(limits.perAccount),
      max_campaigns_per_job: Number(limits.perJob),
      max_parallel_enabled: Number(limits.parallel),
      max_budget_by_currency: Object.fromEntries(limits.budgets.split(",").map((item) => item.trim()).filter(Boolean).map((item) => { const [currency, amount] = item.split(":"); return [currency.trim().toUpperCase(), Number(amount)]; }))
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["campaign-builder-guardrails"] })
  });
  const data = settings.data;
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="h4">{t("ui.7f17c7c62a")}</Typography><Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => settings.refetch()}>{t("ui.c2f668e54f")}</Button></Box>
      {settings.error && <Alert severity="error">{settings.error.message}</Alert>}
      {(guardrails.error || saveLimits.error) && <Alert severity="error">{(guardrails.error || saveLimits.error)?.message}</Alert>}
      {data && <Grid container spacing={2}>
        <Grid item xs={12} md={6}><Paper variant="outlined" sx={{ p: 3, height: "100%" }}><Typography variant="h6" gutterBottom>{t("ui.f81e505f9b")}</Typography><KeyValue label={t("ui.d629f3a9cd")} value={data.app_environment} /><KeyValue label={t("ui.0d64f29bf9")} value={data.public_base_url} /><KeyValue label="Google Ads API" value={data.google_ads_api_version} /><KeyValue label={t("ui.cd405c9fa8")} value={data.live_connections} /></Paper></Grid>
        <Grid item xs={12} md={6}><Paper variant="outlined" sx={{ p: 3, height: "100%" }}><Typography variant="h6" gutterBottom>{t("ui.ddd5258acb")}</Typography><KeyValue label={t("ui.eb9b25674e")} value={data.deployment_policy?.campaign_status} /><KeyValue label="validate_only" value={data.deployment_policy?.validate_only_required ? t("ui.d4dd57acfe") : t("ui.ced07fd144")} /><KeyValue label={t("ui.846aff7071")} value={data.deployment_policy?.explicit_confirmation} /><KeyValue label={t("ui.75035936ef")} value={data.deployment_policy?.simulation_contacts_google ? t("ui.d4f57dba81") : t("ui.ced07fd144")} /></Paper></Grid>
      </Grid>}
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>{t("ui.d4418286ad")}</Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={3}><TextField fullWidth type="number" label={t("ui.11e6a76ca8")} value={limits.perAccount} onChange={(e) => setLimits({ ...limits, perAccount: e.target.value })} /></Grid>
          <Grid item xs={12} md={3}><TextField fullWidth type="number" label={t("ui.2226dfaeba")} value={limits.perJob} onChange={(e) => setLimits({ ...limits, perJob: e.target.value })} /></Grid>
          <Grid item xs={12} md={3}><TextField fullWidth type="number" label={t("ui.6b9fbb7e5f")} value={limits.parallel} onChange={(e) => setLimits({ ...limits, parallel: e.target.value })} /></Grid>
          <Grid item xs={12} md={3}><TextField fullWidth label={t("ui.68a3882b45")} value={limits.budgets} onChange={(e) => setLimits({ ...limits, budgets: e.target.value })} /></Grid>
        </Grid>
        <Box><Button variant="contained" startIcon={<SaveOutlinedIcon />} disabled={saveLimits.isPending} onClick={() => saveLimits.mutate()}>{t("ui.7a61095907")}</Button></Box>
      </Paper>
    </Stack>
  );
}

function KeyValue({ label, value }: { label: string; value: unknown }) { return <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, py: 1, borderBottom: 1, borderColor: "divider" }}><Typography color="text.secondary">{label}</Typography><Typography fontWeight={700} sx={{ textAlign: "right", overflowWrap: "anywhere" }}>{String(value ?? "—")}</Typography></Box>; }
function EmptyRow({ columns, text }: { columns: number; text: string }) { return <TableRow><TableCell colSpan={columns}><Typography color="text.secondary">{text}</Typography></TableCell></TableRow>; }
