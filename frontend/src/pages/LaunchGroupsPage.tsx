import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography
} from "@mui/material";
import LaunchOutlinedIcon from "@mui/icons-material/LaunchOutlined";
import PauseCircleOutlineIcon from "@mui/icons-material/PauseCircleOutline";
import PlayCircleOutlineIcon from "@mui/icons-material/PlayCircleOutline";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api, CampaignInstance, LaunchGroup } from "../api/client";
import type { Navigate } from "../app/App";
import { StatusBadge } from "../components/StatusBadge";
import { formatDate, formatNumber, t } from "../i18n";

export function LaunchGroupsPage({ navigate, groupId }: { navigate: Navigate; groupId?: string }) {
  if (groupId) return <LaunchGroupDetail groupId={groupId} navigate={navigate} />;
  return <LaunchGroupList navigate={navigate} />;
}

function LaunchGroupList({ navigate }: { navigate: Navigate }) {
  const groups = useQuery({
    queryKey: ["launch-groups"],
    queryFn: api.listLaunchGroups,
    refetchInterval: 5000
  });
  const grouped = useMemo(() => {
    const result = new Map<string, LaunchGroup[]>();
    for (const item of groups.data || []) {
      const rows = result.get(item.launch_batch_id) || [];
      rows.push(item);
      result.set(item.launch_batch_id, rows);
    }
    return [...result.entries()];
  }, [groups.data]);

  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Box>
          <Typography variant="h4">{t("ui.279f79d8f0")}</Typography>
          <Typography color="text.secondary">{t("ui.44e2df9658")}</Typography>
        </Box>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={() => groups.refetch()}>
          {t("ui.c2f668e54f")}</Button>
      </Box>
      {groups.error && <Alert severity="error">{groups.error.message}</Alert>}
      {grouped.map(([batchId, rows]) => (
        <Box component="section" key={batchId} sx={{ borderTop: 3, borderColor: "primary.main", bgcolor: "background.paper" }}>
          <Box sx={{ px: 2, py: 1.5, display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
            <Box>
              <Typography fontWeight={800}>{rows[0].launch_batch_name || "Launch Batch"}</Typography>
              <Typography variant="caption" color="text.secondary">{batchId}</Typography>
            </Box>
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
              <StatusBadge value={rows[0].execution_mode || "SIMULATION"} />
              <Chip size="small" label={t("common.accountCount", { count: rows.length })} />
              <Chip size="small" label={t("common.campaignCount", { count: rows.reduce((sum, item) => sum + item.campaigns_count, 0) })} />
            </Stack>
          </Box>
          <Box sx={{ overflowX: "auto", borderTop: 1, borderColor: "divider" }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t("ui.5b16fcdd97")}</TableCell>
                  <TableCell>Customer ID</TableCell>
                  <TableCell>{t("ui.8fd7886949")}</TableCell>
                  <TableCell>{t("ui.cf645a44e5")}</TableCell>
                  <TableCell>{t("ui.a470ac24e2")}</TableCell>
                  <TableCell>{t("ui.4150f46b4a")}</TableCell>
                  <TableCell>{t("ui.f7f293b5c5")}</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((item) => (
                  <TableRow key={item.id} hover>
                    <TableCell sx={{ fontWeight: 700 }}>{item.account_name}</TableCell>
                    <TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell>
                    <TableCell>{item.currency_code}<Typography variant="caption" display="block">{item.time_zone}</Typography></TableCell>
                    <TableCell>{item.campaigns_count}</TableCell>
                    <TableCell>{formatMoney(item.total_cost_micros || 0, item.currency_code)}</TableCell>
                    <TableCell>{item.total_conversions || 0}</TableCell>
                    <TableCell><StatusBadge value={item.status} /></TableCell>
                    <TableCell align="right"><Button size="small" onClick={() => navigate(`/launch-groups/${item.id}`)}>{t("ui.1259571a15")}</Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Box>
        </Box>
      ))}
      {!grouped.length && !groups.isLoading && (
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Typography color="text.secondary">{t("ui.83de09fcf2")}</Typography>
        </Paper>
      )}
    </Stack>
  );
}

function LaunchGroupDetail({ groupId, navigate }: { groupId: string; navigate: Navigate }) {
  const queryClient = useQueryClient();
  const group = useQuery({
    queryKey: ["launch-group", groupId],
    queryFn: () => api.getLaunchGroup(groupId),
    refetchInterval: 3000
  });
  const history = useQuery({
    queryKey: ["launch-group-history", groupId],
    queryFn: () => api.getLaunchGroupHistory(groupId),
    refetchInterval: 5000
  });
  const [selected, setSelected] = useState<string[]>([]);
  const [password, setPassword] = useState("");
  const [tab, setTab] = useState("campaigns");
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["launch-group", groupId] });
    queryClient.invalidateQueries({ queryKey: ["launch-groups"] });
    queryClient.invalidateQueries({ queryKey: ["launch-group-history", groupId] });
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
  };
  const statusAction = useMutation({
    mutationFn: ({ action, ids }: { action: "ENABLE" | "PAUSE"; ids: string[] }) =>
      api.createCampaignStatusAction(groupId, {
        action,
        campaign_instance_ids: ids,
        confirmation: true,
        password_confirmation: password || null
      }),
    onSuccess: invalidate
  });
  const sync = useMutation({ mutationFn: () => api.syncLaunchGroupMetrics(groupId), onSuccess: invalidate });

  if (group.isLoading) return <CircularProgress />;
  if (group.error) return <Alert severity="error">{group.error.message}</Alert>;
  const data = group.data!;
  const instances = data.instances || [];
  const busy = statusAction.isPending || sync.isPending;

  return (
    <Stack spacing={3}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Box>
          <Button size="small" onClick={() => navigate("/launch-groups")}>{t("ui.f9e6974ad8")}</Button>
          <Typography variant="h4">{data.account_name}</Typography>
          <Typography color="text.secondary">{data.customer_id} · {data.currency_code} · {data.time_zone}</Typography>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center" useFlexGap sx={{ flexWrap: "wrap" }}>
          <StatusBadge value={data.execution_mode || "SIMULATION"} />
          <StatusBadge value={data.status} />
          <Button variant="outlined" startIcon={<RefreshIcon />} disabled={busy} onClick={() => sync.mutate()}>
            {t("ui.d463f269f8")}</Button>
        </Stack>
      </Box>
      {data.execution_mode === "SIMULATION" && (
        <Alert severity="info">{t("ui.ed16f61cf2")}</Alert>
      )}
      {statusAction.error && <Alert severity="error">{statusAction.error.message}</Alert>}
      {sync.error && <Alert severity="error">{sync.error.message}</Alert>}
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(2, 1fr)", md: "repeat(5, minmax(0, 1fr))" }, gap: 1, borderBlock: 1, borderColor: "divider", py: 2 }}>
        <Metric label={t("ui.cf645a44e5")} value={instances.length} />
        <Metric label={t("ui.a470ac24e2")} value={formatMoney(sum(instances, "cost_micros"), data.currency_code)} />
        <Metric label={t("ui.4150f46b4a")} value={sum(instances, "conversions")} />
        <Metric label={t("ui.07e2b83b27")} value={sum(instances, "clicks")} />
        <Metric label={t("ui.8d112fb582")} value={sum(instances, "impressions")} />
      </Box>
      <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable">
        <Tab value="campaigns" label={t("ui.4ad1aa5f4f")} />
        <Tab value="history" label={t("ui.469a355947")} />
      </Tabs>
      {tab === "campaigns" && (
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", lg: "row" }} spacing={1}>
            <Button variant="contained" startIcon={<PlayCircleOutlineIcon />} disabled={busy || !selected.length} onClick={() => statusAction.mutate({ action: "ENABLE", ids: selected })}>{t("ui.c0d1fd05fe")}</Button>
            <Button variant="outlined" startIcon={<PauseCircleOutlineIcon />} disabled={busy || !selected.length} onClick={() => statusAction.mutate({ action: "PAUSE", ids: selected })}>{t("ui.0bc745cc5c")}</Button>
            <Button variant="outlined" startIcon={<PlayCircleOutlineIcon />} disabled={busy || !instances.length} onClick={() => statusAction.mutate({ action: "ENABLE", ids: [] })}>{t("ui.fbe9e439cb")}</Button>
            <Button variant="outlined" color="warning" startIcon={<PauseCircleOutlineIcon />} disabled={busy || !instances.length} onClick={() => statusAction.mutate({ action: "PAUSE", ids: [] })}>{t("ui.2bdcc8f626")}</Button>
          </Stack>
          <TextField
            type="password"
            size="small"
            label={t("ui.a7c6c9ab84")}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            sx={{ maxWidth: 420 }}
          />
          <CampaignTable instances={instances} currency={data.currency_code} selected={selected} setSelected={setSelected} />
        </Stack>
      )}
      {tab === "history" && <ActionHistory history={history.data} />}
    </Stack>
  );
}

function CampaignTable(props: { instances: CampaignInstance[]; currency: string; selected: string[]; setSelected: (value: string[]) => void }) {
  const allSelected = props.instances.length > 0 && props.instances.every((item) => props.selected.includes(item.id));
  return (
    <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}>
      <Table size="small" sx={{ minWidth: 1400 }}>
        <TableHead>
          <TableRow>
            <TableCell padding="checkbox"><Checkbox checked={allSelected} onChange={(event) => props.setSelected(event.target.checked ? props.instances.map((item) => item.id) : [])} /></TableCell>
            <TableCell>{t("table.campaign")}</TableCell>
            <TableCell>Google ID</TableCell>
            <TableCell>{t("ui.0773ed4942")}</TableCell>
            <TableCell>{t("ui.f7f293b5c5")}</TableCell>
            <TableCell>{t("ui.8d112fb582")}</TableCell>
            <TableCell>{t("ui.07e2b83b27")}</TableCell>
            <TableCell>CTR</TableCell>
            <TableCell>{t("ui.a470ac24e2")}</TableCell>
            <TableCell>{t("ui.4150f46b4a")}</TableCell>
            <TableCell>CPA</TableCell>
            <TableCell>Final URL</TableCell>
            <TableCell>{t("table.policy")}</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {props.instances.map((item) => {
            const metrics = item.metrics || {};
            const googleId = campaignGoogleId(item.resource_names);
            return (
              <TableRow key={item.id} hover>
                <TableCell padding="checkbox">
                  <Checkbox
                    checked={props.selected.includes(item.id)}
                    onChange={(event) => props.setSelected(event.target.checked ? [...props.selected, item.id] : props.selected.filter((id) => id !== item.id))}
                  />
                </TableCell>
                <TableCell><Typography fontWeight={700}>{item.campaign_name}</Typography><Typography variant="caption" color="text.secondary">#{item.campaign_sequence} · {item.creative_assignment.set_key || "default"}</Typography></TableCell>
                <TableCell>
                  {googleId ? <Button size="small" endIcon={<LaunchOutlinedIcon />} href={googleCampaignUrl(googleId)} target="_blank" rel="noreferrer">{googleId}</Button> : "—"}
                </TableCell>
                <TableCell>{formatMoney(item.budget_micros, props.currency)}</TableCell>
                <TableCell><StatusBadge value={item.status} /></TableCell>
                <TableCell>{metrics.impressions || 0}</TableCell>
                <TableCell>{metrics.clicks || 0}</TableCell>
                <TableCell>{Number(metrics.ctr || 0).toFixed(2)}%</TableCell>
                <TableCell>{formatMoney(metrics.cost_micros || 0, props.currency)}</TableCell>
                <TableCell>{metrics.conversions || 0}</TableCell>
                <TableCell>{metrics.cpa_micros == null ? "—" : formatMoney(metrics.cpa_micros, props.currency)}</TableCell>
                <TableCell sx={{ maxWidth: 240, overflowWrap: "anywhere" }}>{item.url_settings.final_url || "—"}</TableCell>
                <TableCell><StatusBadge value={item.policy_status} /></TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </Box>
  );
}

function ActionHistory({ history }: { history?: Record<string, any> }) {
  const actions = history?.actions || [];
  return (
    <Box>
      {actions.map((item: any) => (
        <Box key={item.id} sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0, 1fr) 130px 190px" }, gap: 2, py: 1.25, borderBottom: 1, borderColor: "divider" }}>
          <Typography sx={{ overflowWrap: "anywhere" }}>{item.action} · {item.selected_instance_ids.length} {t("ui.d0cba44872")}</Typography>
          <StatusBadge value={item.status} />
          <Typography color="text.secondary">{formatDate(item.created_at)}</Typography>
        </Box>
      ))}
      {!actions.length && <Typography color="text.secondary">{t("ui.bcb249c512")}</Typography>}
    </Box>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return <Box sx={{ px: 1.5, minWidth: 0 }}><Typography variant="caption" color="text.secondary">{label}</Typography><Typography variant="h6" sx={{ fontSize: 18, overflowWrap: "anywhere" }}>{value}</Typography></Box>;
}

function sum(instances: CampaignInstance[], field: string) {
  return instances.reduce((total, item) => total + Number((item.metrics || {})[field] || 0), 0);
}

function formatMoney(micros: number, currency: string) {
  return `${formatNumber(Number(micros || 0) / 1_000_000, { maximumFractionDigits: 2 })} ${currency}`;
}

function campaignGoogleId(resourceNames: string[]) {
  const resource = resourceNames.find((item) => item.includes("/campaigns/"));
  return resource?.split("/campaigns/")[1] || "";
}

function googleCampaignUrl(campaignId: string) {
  return `https://ads.google.com/aw/campaigns?campaignId=${encodeURIComponent(campaignId)}`;
}
