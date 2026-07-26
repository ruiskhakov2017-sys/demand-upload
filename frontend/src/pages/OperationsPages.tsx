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

export function ModerationPage() {
  return <GoogleDataPage kind="moderation" title="Модерация" />;
}

export function StatisticsPage() {
  return <GoogleDataPage kind="statistics" title="Статистика" />;
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
      setMessage(`Задание ${result.job_id.slice(0, 8)} поставлено в очередь`);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }
  });
  const error = data.error || sync.error;
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Typography variant="h4">{title}</Typography>
        <Stack direction="row" spacing={1}>
          <FormControl size="small" sx={{ minWidth: 240 }}><InputLabel>Google-подключение</InputLabel><Select label="Google-подключение" value={connectionId} onChange={(e) => setConnectionId(e.target.value)}>{(connections.data || []).map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · {item.status}</MenuItem>)}</Select></FormControl>
          <Button variant="contained" startIcon={<SyncIcon />} disabled={!connectionId || sync.isPending} onClick={() => sync.mutate()}>Синхронизировать</Button>
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
  return <Table size="small"><TableHead><TableRow><TableCell>Customer ID</TableCell><TableCell>Объявление</TableCell><TableCell>Статус</TableCell><TableCell>Политики</TableCell><TableCell>Проверено</TableCell></TableRow></TableHead><TableBody>{rows.map((row) => <TableRow key={row.id}><TableCell>{row.customer_id}</TableCell><TableCell sx={{ fontFamily: "monospace", overflowWrap: "anywhere" }}>{row.resource_name}</TableCell><TableCell><StatusBadge value={row.approval_status} /></TableCell><TableCell>{(row.policy_topics || []).map((item: any) => item.topic).join(", ") || "—"}</TableCell><TableCell>{row.checked_at ? new Date(row.checked_at).toLocaleString("ru-RU") : "—"}</TableCell></TableRow>)}{!rows.length && <EmptyRow columns={5} text="Данные модерации ещё не синхронизированы." />}</TableBody></Table>;
}

function StatisticsTable({ rows }: { rows: Array<Record<string, any>> }) {
  return <Table size="small"><TableHead><TableRow><TableCell>Дата</TableCell><TableCell>Customer ID</TableCell><TableCell align="right">Показы</TableCell><TableCell align="right">Клики</TableCell><TableCell align="right">Расход</TableCell><TableCell align="right">Конверсии</TableCell></TableRow></TableHead><TableBody>{rows.map((row) => <TableRow key={row.id}><TableCell>{row.snapshot_date}</TableCell><TableCell>{row.customer_id}</TableCell><TableCell align="right">{row.metrics?.impressions || 0}</TableCell><TableCell align="right">{row.metrics?.clicks || 0}</TableCell><TableCell align="right">{((row.metrics?.cost_micros || 0) / 1_000_000).toFixed(2)}</TableCell><TableCell align="right">{Number(row.metrics?.conversions || 0).toFixed(2)}</TableCell></TableRow>)}{!rows.length && <EmptyRow columns={6} text="Статистика ещё не синхронизирована." />}</TableBody></Table>;
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
      setMessage("Настройки Brocard сохранены");
      queryClient.invalidateQueries({ queryKey: ["finance"] });
    }
  });
  const sync = useMutation({
    mutationFn: (id: string) => api.syncFinance(id),
    onSuccess: (result) => {
      setMessage(`Синхронизация поставлена в очередь: ${result.job_id.slice(0, 8)}`);
      queryClient.invalidateQueries({ queryKey: ["finance"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }
  });
  return (
    <Stack spacing={3}>
      <Typography variant="h4">Финансы / Brocard</Typography>
      {(finance.error || save.error || sync.error) && <Alert severity="error">{finance.error?.message || save.error?.message || sync.error?.message}</Alert>}
      {message && <Alert severity="success" onClose={() => setMessage(null)}>{message}</Alert>}
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={3}><TextField fullWidth label="Название профиля" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Grid>
          <Grid item xs={12} md={4}><TextField fullWidth type="password" label="API token" value={form.api_token} onChange={(e) => setForm({ ...form, api_token: e.target.value })} /></Grid>
          <Grid item xs={12} md={5}><TextField fullWidth label="API base URL" value={form.api_base_url} onChange={(e) => setForm({ ...form, api_base_url: e.target.value })} /></Grid>
        </Grid>
        <Alert severity="info" sx={{ mt: 2 }}>Токен хранится зашифрованно. Баланс и карты загружаются через Brocard API v2.</Alert>
        <Button sx={{ mt: 2 }} variant="contained" startIcon={<SaveOutlinedIcon />} disabled={!form.api_token || save.isPending} onClick={() => save.mutate()}>Сохранить</Button>
      </Paper>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", bgcolor: "background.paper" }}><Table size="small"><TableHead><TableRow><TableCell>Профиль</TableCell><TableCell>Провайдер</TableCell><TableCell>Статус</TableCell><TableCell>Баланс</TableCell><TableCell>Карты</TableCell><TableCell>Обновлён</TableCell><TableCell align="right">Действие</TableCell></TableRow></TableHead><TableBody>{(finance.data || []).map((row) => <TableRow key={row.id}><TableCell>{row.name}</TableCell><TableCell>{row.provider}</TableCell><TableCell><StatusBadge value={row.status} /></TableCell><TableCell>{row.latest_snapshot ? `${row.latest_snapshot.balance} ${row.latest_snapshot.currency}` : "—"}</TableCell><TableCell>{row.latest_snapshot ? `${row.latest_snapshot.cards_active}/${row.latest_snapshot.cards_total}` : "—"}</TableCell><TableCell>{new Date(row.updated_at).toLocaleString("ru-RU")}</TableCell><TableCell align="right"><Button size="small" startIcon={<SyncIcon />} disabled={row.status === "SYNCING" || sync.isPending} onClick={() => sync.mutate(row.id)}>Синхронизировать</Button></TableCell></TableRow>)}{!finance.data?.length && <EmptyRow columns={7} text="Финансовые профили не настроены." />}</TableBody></Table></Box>
    </Stack>
  );
}

export function AlertsPage() {
  const queryClient = useQueryClient();
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: api.listAlerts });
  const mark = useMutation({ mutationFn: ({ id, read }: { id: string; read: boolean }) => api.setAlertRead(id, read), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["alerts"] }); queryClient.invalidateQueries({ queryKey: ["dashboard"] }); } });
  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="h4">Уведомления</Typography><Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => alerts.refetch()}>Обновить</Button></Box>
      {alerts.error && <Alert severity="error">{alerts.error.message}</Alert>}
      <Box sx={{ border: 1, borderColor: "divider", bgcolor: "background.paper" }}><Table size="small"><TableHead><TableRow><TableCell padding="checkbox" /><TableCell>Время</TableCell><TableCell>Уровень</TableCell><TableCell>Событие</TableCell><TableCell>Сообщение</TableCell></TableRow></TableHead><TableBody>{(alerts.data || []).map((row) => <TableRow key={row.id} sx={{ opacity: row.read_at ? 0.62 : 1 }}><TableCell padding="checkbox"><Checkbox icon={<MarkEmailReadOutlinedIcon />} checkedIcon={<MarkEmailReadOutlinedIcon />} checked={Boolean(row.read_at)} onChange={(e) => mark.mutate({ id: row.id, read: e.target.checked })} /></TableCell><TableCell>{new Date(row.created_at).toLocaleString("ru-RU")}</TableCell><TableCell><StatusBadge value={row.severity} /></TableCell><TableCell>{row.title}</TableCell><TableCell>{row.message}</TableCell></TableRow>)}{!alerts.data?.length && <EmptyRow columns={5} text="Уведомлений нет." />}</TableBody></Table></Box>
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
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}><Typography variant="h4">Настройки</Typography><Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => settings.refetch()}>Обновить</Button></Box>
      {settings.error && <Alert severity="error">{settings.error.message}</Alert>}
      {(guardrails.error || saveLimits.error) && <Alert severity="error">{(guardrails.error || saveLimits.error)?.message}</Alert>}
      {data && <Grid container spacing={2}>
        <Grid item xs={12} md={6}><Paper variant="outlined" sx={{ p: 3, height: "100%" }}><Typography variant="h6" gutterBottom>Среда</Typography><KeyValue label="Режим приложения" value={data.app_environment} /><KeyValue label="Публичный адрес" value={data.public_base_url} /><KeyValue label="Google Ads API" value={data.google_ads_api_version} /><KeyValue label="Активные подключения" value={data.live_connections} /></Paper></Grid>
        <Grid item xs={12} md={6}><Paper variant="outlined" sx={{ p: 3, height: "100%" }}><Typography variant="h6" gutterBottom>Политика запуска</Typography><KeyValue label="Статус кампаний" value={data.deployment_policy?.campaign_status} /><KeyValue label="validate_only" value={data.deployment_policy?.validate_only_required ? "обязателен" : "нет"} /><KeyValue label="Подтверждение" value={data.deployment_policy?.explicit_confirmation} /><KeyValue label="Симуляция вызывает Google" value={data.deployment_policy?.simulation_contacts_google ? "да" : "нет"} /></Paper></Grid>
      </Grid>}
      <Paper variant="outlined" sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>Предохранители Campaign Builder</Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} md={3}><TextField fullWidth type="number" label="Кампаний на аккаунт" value={limits.perAccount} onChange={(e) => setLimits({ ...limits, perAccount: e.target.value })} /></Grid>
          <Grid item xs={12} md={3}><TextField fullWidth type="number" label="Кампаний в задании" value={limits.perJob} onChange={(e) => setLimits({ ...limits, perJob: e.target.value })} /></Grid>
          <Grid item xs={12} md={3}><TextField fullWidth type="number" label="Параллельно включаемых" value={limits.parallel} onChange={(e) => setLimits({ ...limits, parallel: e.target.value })} /></Grid>
          <Grid item xs={12} md={3}><TextField fullWidth label="Лимиты валют: USD:10000" value={limits.budgets} onChange={(e) => setLimits({ ...limits, budgets: e.target.value })} /></Grid>
        </Grid>
        <Box><Button variant="contained" startIcon={<SaveOutlinedIcon />} disabled={saveLimits.isPending} onClick={() => saveLimits.mutate()}>Сохранить лимиты</Button></Box>
      </Paper>
    </Stack>
  );
}

function KeyValue({ label, value }: { label: string; value: unknown }) { return <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, py: 1, borderBottom: 1, borderColor: "divider" }}><Typography color="text.secondary">{label}</Typography><Typography fontWeight={700} sx={{ textAlign: "right", overflowWrap: "anywhere" }}>{String(value ?? "—")}</Typography></Box>; }
function EmptyRow({ columns, text }: { columns: number; text: string }) { return <TableRow><TableCell colSpan={columns}><Typography color="text.secondary">{text}</Typography></TableCell></TableRow>; }
