import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Grid,
  LinearProgress,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CancelOutlinedIcon from "@mui/icons-material/CancelOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import DeleteSweepOutlinedIcon from "@mui/icons-material/DeleteSweepOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import MoveDownOutlinedIcon from "@mui/icons-material/MoveDownOutlined";
import PauseCircleOutlineIcon from "@mui/icons-material/PauseCircleOutline";
import PlayCircleOutlineIcon from "@mui/icons-material/PlayCircleOutline";
import ReplayOutlinedIcon from "@mui/icons-material/ReplayOutlined";
import ScheduleOutlinedIcon from "@mui/icons-material/ScheduleOutlined";
import SkipNextOutlinedIcon from "@mui/icons-material/SkipNextOutlined";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api, DeploymentSchedule, ScheduleRun } from "../api/client";
import type { Navigate } from "../app/App";
import { StatusBadge } from "../components/StatusBadge";
import { localeTag, t } from "../i18n";

export function SchedulesPage({
  scheduleId,
  navigate
}: {
  scheduleId?: string;
  navigate: Navigate;
}) {
  const list = useQuery({
    queryKey: ["schedules"],
    queryFn: api.listSchedules,
    refetchInterval: 5000
  });
  if (list.isLoading) return <CircularProgress />;
  if (list.error) return <Alert severity="error">{list.error.message}</Alert>;
  if (scheduleId) return <ScheduleDetails scheduleId={scheduleId} navigate={navigate} />;
  return (
    <Stack spacing={2.5}>
      <Box>
        <Typography variant="h4">{t("ui.f04bd0a064")}</Typography>
        <Typography color="text.secondary">{t("ui.9f634db44e")}</Typography>
      </Box>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{t("ui.f7f293b5c5")}</TableCell>
              <TableCell>{t("ui.ff0fbd56f4")}</TableCell>
              <TableCell>{t("ui.97c248cbe0")}</TableCell>
              <TableCell>{t("ui.88d59af4fe")}</TableCell>
              <TableCell>{t("ui.2e746e5dbe")}</TableCell>
              <TableCell>{t("ui.2cb6362fab")}</TableCell>
              <TableCell>{t("ui.6631c04a8e")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(list.data || []).map((schedule) => (
              <TableRow
                key={schedule.id}
                hover
                tabIndex={0}
                onClick={() => navigate(`/schedules/${schedule.id}`)}
                onKeyDown={(event) => event.key === "Enter" && navigate(`/schedules/${schedule.id}`)}
                sx={{ cursor: "pointer" }}
              >
                <TableCell><StatusBadge value={schedule.status} /></TableCell>
                <TableCell>{modeLabel(schedule.mode)}</TableCell>
                <TableCell>v{schedule.version_number}</TableCell>
                <TableCell>{schedule.progress.completed_accounts} {t("ui.beed168817")}{" "}{schedule.progress.total_accounts}</TableCell>
                <TableCell>{schedule.progress.current_wave || "—"}</TableCell>
                <TableCell>{schedule.progress.next_account || "—"}</TableCell>
                <TableCell>{formatDate(schedule.progress.next_run_at, schedule.time_zone)}</TableCell>
              </TableRow>
            ))}
            {!list.data?.length && (
              <TableRow><TableCell colSpan={7}>{t("ui.e9238dc0cd")}</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </Box>
    </Stack>
  );
}

function ScheduleDetails({ scheduleId, navigate }: { scheduleId: string; navigate: Navigate }) {
  const queryClient = useQueryClient();
  const schedule = useQuery({
    queryKey: ["schedule", scheduleId],
    queryFn: () => api.getSchedule(scheduleId),
    refetchInterval: 3000
  });
  const [selected, setSelected] = useState<string[]>([]);
  const [shiftMinutes, setShiftMinutes] = useState(60);
  const [targetWave, setTargetWave] = useState(1);
  const now = useClock();
  const action = useMutation({
    mutationFn: (payload: Record<string, any>) => api.scheduleAction(scheduleId, payload),
    onSuccess: (result) => {
      queryClient.setQueryData(["schedule", result.id], result);
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      if (result.id !== scheduleId) navigate(`/schedules/${result.id}`, true);
      setSelected([]);
    }
  });
  if (schedule.isLoading) return <CircularProgress />;
  if (schedule.error) return <Alert severity="error">{schedule.error.message}</Alert>;
  if (!schedule.data) return <Alert severity="error">{t("ui.c338f32ec6")}</Alert>;
  const data = schedule.data;
  const progress = data.progress.total_accounts
    ? data.progress.completed_accounts / data.progress.total_accounts * 100
    : 0;
  const dangerous = (label: string, payload: Record<string, any>) => {
    if (!window.confirm(`${label}?`)) return;
    action.mutate({ ...payload, confirmation: true });
  };
  const selectedRuns = data.runs.filter((item) => selected.includes(item.id));
  const futureStatuses = new Set(["WAITING", "RETRY_WAIT", "QUEUED"]);
  const futureRuns = data.runs.filter((item) => futureStatuses.has(item.status));
  const selectedFutureRuns = selectedRuns.filter((item) => futureStatuses.has(item.status));
  const canPause = ["PLANNED", "RUNNING", "OBSERVATION", "WAITING_FOR_APPROVAL"].includes(data.status);

  return (
    <Stack spacing={2.5}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1.5}
        alignItems={{ xs: "flex-start", sm: "center" }}
      >
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate("/schedules")}>{t("ui.f6dab074d7")}</Button>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h4">{t("ui.5e8cb4a28a")}{data.version_number}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>
            {modeLabel(data.mode)} · {data.time_zone} · {data.fingerprint}
          </Typography>
        </Box>
      </Stack>

      {action.error && <Alert severity="error">{action.error.message}</Alert>}
      {data.pause_reason && (
        <Alert severity={data.recovery_required ? "warning" : "error"}>
          {data.pause_reason}
        </Alert>
      )}

      <Box
        sx={{
          display: "flex",
          flexWrap: "wrap",
          gap: 1,
          alignItems: "center",
          minWidth: 0,
          "& .MuiChip-root": { flexShrink: 0, maxWidth: "100%" }
        }}
      >
        <StatusBadge value={data.status} />
        <Chip label={t("schedule.wave", { number: data.progress.current_wave || "—" })} />
        <Chip label={t("schedule.accountProgress", { completed: data.progress.completed_accounts, total: data.progress.total_accounts })} />
        <Chip label={t("schedule.campaignsCreated", { count: data.progress.created_campaigns })} />
      </Box>
      <LinearProgress variant="determinate" value={progress} sx={{ height: 8 }} />

      <Grid container spacing={1.5}>
        <Metric label={t("ui.503d1c9809")} value={data.progress.successful_accounts} />
        <Metric label={t("ui.9cf1314860")} value={data.progress.waiting_accounts} />
        <Metric label={t("ui.6193b4177e")} value={data.progress.failed_accounts} />
        <Metric label={t("ui.e9c094d2a9")} value={data.progress.next_account || "—"} />
        <Metric label={t("ui.75e96e0158")} value={formatDate(data.progress.next_run_at, data.time_zone)} />
        <Metric label={t("ui.564f17bf9d")} value={countdown(data.progress.next_run_at, now)} />
      </Grid>

      <Box sx={actionGridSx}>
        <Button
          variant="outlined"
          startIcon={<PauseCircleOutlineIcon />}
          disabled={action.isPending || !canPause}
          onClick={() => dangerous(t("ui.eb3dc583a4"), { action: "PAUSE" })}
        >
          {t("ui.4205b1307e")}</Button>
        <Button
          variant="outlined"
          startIcon={<PlayCircleOutlineIcon />}
          disabled={action.isPending || !["PAUSED", "PLANNED", "OBSERVATION"].includes(data.status)}
          onClick={() => dangerous(t("ui.9534d9a281"), { action: "RESUME", recovery_strategy: "SEQUENTIAL" })}
        >
          {t("ui.3f75368ab9")}</Button>
        <Button
          variant="outlined"
          startIcon={<CheckCircleOutlineIcon />}
          disabled={action.isPending || data.status !== "WAITING_FOR_APPROVAL"}
          onClick={() => dangerous(t("ui.18072dd8bb"), { action: "APPROVE_NEXT_WAVE" })}
        >
          {t("ui.7aac9c3a5d")}</Button>
        <Button
          variant="outlined"
          startIcon={<SkipNextOutlinedIcon />}
          disabled={action.isPending || !data.progress.next_account}
          onClick={() => dangerous(t("ui.8f5a1d53e2"), { action: "RUN_NEXT_NOW" })}
        >
          {t("ui.91fa66f584")}</Button>
        <Button
          component="a"
          href={api.scheduleReportUrl(data.id)}
          startIcon={<DownloadOutlinedIcon />}
        >
          {t("ui.023a6a1033")}</Button>
      </Box>

      <Box sx={actionGridSx}>
        <TextField
          size="small"
          type="number"
          label={t("ui.85e6846a21")}
          value={shiftMinutes}
          onChange={(event) => setShiftMinutes(Number(event.target.value) || 0)}
          sx={{ width: "100%" }}
        />
        <Button
          variant="outlined"
          startIcon={<ScheduleOutlinedIcon />}
          disabled={action.isPending || !shiftMinutes || !futureRuns.length}
          onClick={() => dangerous(t("ui.b2f89abf45"), {
            action: "RESCHEDULE_REMAINING",
            shift_minutes: shiftMinutes
          })}
        >
          {t("ui.2a139fa8d2")}</Button>
        <TextField
          select
          size="small"
          label={t("ui.8b4beb01ee")}
          value={targetWave}
          onChange={(event) => setTargetWave(Number(event.target.value))}
          sx={{ width: "100%" }}
        >
          {data.waves.map((wave) => <MenuItem key={wave.id} value={wave.wave_number}>{t("ui.cdec369bf5")}{" "}{wave.wave_number}</MenuItem>)}
        </TextField>
        <Button
          variant="outlined"
          startIcon={<MoveDownOutlinedIcon />}
          disabled={action.isPending || selectedFutureRuns.length !== 1 || selected.length !== 1}
          onClick={() => dangerous(t("ui.82fe9be51c"), {
            action: "MOVE_ACCOUNT",
            run_ids: [selected[0]],
            target_wave_number: targetWave
          })}
        >
          {t("ui.081b1d81c6")}</Button>
        <Button
          variant="outlined"
          startIcon={<ReplayOutlinedIcon />}
          disabled={action.isPending || !selectedRuns.some((item) => item.status === "FAILED")}
          onClick={() => dangerous(t("ui.f18386eaeb"), {
            action: "RETRY",
            run_ids: selected
          })}
        >
          {t("ui.9e506acb19")}</Button>
        <Button
          color="warning"
          startIcon={<CancelOutlinedIcon />}
          disabled={action.isPending || !selectedFutureRuns.length}
          onClick={() => dangerous(t("ui.3951de787d"), {
            action: "CANCEL_SELECTED",
            run_ids: selected
          })}
        >
          {t("ui.d0dcc21973")}</Button>
        <Button
          color="error"
          startIcon={<DeleteSweepOutlinedIcon />}
          disabled={action.isPending || !futureRuns.length}
          onClick={() => dangerous(t("ui.3cf038bddd"), { action: "CANCEL_FUTURE" })}
        >
          {t("ui.2a44ef6065")}</Button>
      </Box>

      <WaveStrip schedule={data} />

      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
        <Table size="small" sx={{ minWidth: 1380 }}>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox
                  checked={data.runs.length > 0 && selected.length === data.runs.length}
                  onChange={(event) => setSelected(event.target.checked ? data.runs.map((item) => item.id) : [])}
                />
              </TableCell>
              <TableCell>{t("ui.cdec369bf5")}</TableCell>
              <TableCell>{t("ui.5b16fcdd97")}</TableCell>
              <TableCell>Customer ID</TableCell>
              <TableCell>{t("ui.cf645a44e5")}</TableCell>
              <TableCell>{t("ui.f7f293b5c5")}</TableCell>
              <TableCell>{t("ui.3146141c93")}</TableCell>
              <TableCell>{t("ui.dafc83b7cf")}</TableCell>
              <TableCell>{t("ui.be19888666")}</TableCell>
              <TableCell>{t("ui.27ff3263db")}</TableCell>
              <TableCell>Request ID</TableCell>
              <TableCell>{t("ui.72aecd9ad8")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.runs.map((run) => (
              <ScheduleRunRow
                key={run.id}
                run={run}
                timeZone={data.time_zone}
                selected={selected.includes(run.id)}
                onSelect={() => setSelected((current) => current.includes(run.id)
                  ? current.filter((item) => item !== run.id)
                  : [...current, run.id])}
              />
            ))}
          </TableBody>
        </Table>
      </Box>

      {data.events.length > 0 && (
        <Box sx={{ borderTop: 1, borderColor: "divider", pt: 2 }}>
          <Typography variant="h6" sx={{ mb: 1.5 }}>{t("ui.55d4bd77bc")}</Typography>
          <Stack spacing={1}>
            {data.events.slice(0, 30).map((event) => (
              <Box key={String(event.id)} sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "180px 1fr" }, gap: 1 }}>
                <Typography variant="body2" color="text.secondary">{formatDate(event.created_at, data.time_zone)}</Typography>
                <Typography variant="body2">{String(event.message)}</Typography>
              </Box>
            ))}
          </Stack>
        </Box>
      )}
    </Stack>
  );
}

function ScheduleRunRow({
  run,
  timeZone,
  selected,
  onSelect
}: {
  run: ScheduleRun;
  timeZone: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const error = run.structured_error || {};
  return (
    <TableRow hover>
      <TableCell padding="checkbox"><Checkbox checked={selected} onChange={onSelect} /></TableCell>
      <TableCell>{run.wave_number}</TableCell>
      <TableCell>{run.account_name}</TableCell>
      <TableCell sx={{ fontFamily: "monospace" }}>{run.customer_id}</TableCell>
      <TableCell>{run.campaigns_count}</TableCell>
      <TableCell><StatusBadge value={run.status} /></TableCell>
      <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(run.scheduled_for, timeZone)}</TableCell>
      <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(run.actual_started_at, timeZone)}</TableCell>
      <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(run.actual_completed_at, timeZone)}</TableCell>
      <TableCell>{run.attempts}</TableCell>
      <TableCell sx={{ maxWidth: 240, overflowWrap: "anywhere" }}>{run.request_ids.join(", ") || "—"}</TableCell>
      <TableCell sx={{ maxWidth: 340, overflowWrap: "anywhere" }}>{String(error.message || "—")}</TableCell>
    </TableRow>
  );
}

function WaveStrip({ schedule }: { schedule: DeploymentSchedule }) {
  return (
    <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
      {schedule.waves.map((wave) => (
        <Chip
          key={wave.id}
          variant={wave.wave_number === schedule.progress.current_wave ? "filled" : "outlined"}
          color={wave.status === "COMPLETED" ? "success" : wave.status === "WAITING_FOR_APPROVAL" ? "warning" : "default"}
          label={t("schedule.waveSummary", {
            number: wave.wave_number,
            status: wave.status,
            until: wave.observation_until
              ? t("schedule.until", { time: formatDate(wave.observation_until, schedule.time_zone) })
              : ""
          })}
        />
      ))}
    </Stack>
  );
}

function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Grid item xs={6} md={2}>
      <Box sx={{ borderTop: 2, borderColor: "primary.main", pt: 1, minHeight: 66 }}>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Typography fontWeight={700} sx={{ overflowWrap: "anywhere" }}>{value}</Typography>
      </Box>
    </Grid>
  );
}

function useClock() {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return now;
}

function countdown(value: string | null, now: number) {
  if (!value) return "—";
  const seconds = Math.max(0, Math.floor((new Date(value).getTime() - now) / 1000));
  const days = Math.floor(seconds / 86_400);
  const hours = Math.floor(seconds % 86_400 / 3600);
  const minutes = Math.floor(seconds % 3600 / 60);
  const rest = seconds % 60;
  return `${days ? t("schedule.daysShort", { count: days }) : ""}${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function formatDate(value: unknown, timeZone: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(localeTag(), {
    dateStyle: "short",
    timeStyle: "medium",
    timeZone
  }).format(new Date(String(value)));
}

function modeLabel(mode: DeploymentSchedule["mode"]) {
  return {
    IMMEDIATE: t("ui.b279f707db"),
    EVEN: t("ui.91bb2ac541"),
    WAVES: t("ui.1d39173cf8"),
    MANUAL: t("ui.5ec7b0f52b")
  }[mode];
}

const actionGridSx = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 190px), 1fr))",
  gap: 1,
  alignItems: "stretch",
  minWidth: 0,
  "& .MuiButton-root": {
    minHeight: 40,
    whiteSpace: "normal"
  }
} as const;
