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
        <Typography variant="h4">Расписание</Typography>
        <Typography color="text.secondary">Отложенные и ступенчатые запуски по дочерним аккаунтам</Typography>
      </Box>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", bgcolor: "background.paper" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Статус</TableCell>
              <TableCell>Режим</TableCell>
              <TableCell>Версия</TableCell>
              <TableCell>Прогресс</TableCell>
              <TableCell>Текущая волна</TableCell>
              <TableCell>Следующий аккаунт</TableCell>
              <TableCell>Следующий запуск</TableCell>
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
                <TableCell>{schedule.progress.completed_accounts} из {schedule.progress.total_accounts}</TableCell>
                <TableCell>{schedule.progress.current_wave || "—"}</TableCell>
                <TableCell>{schedule.progress.next_account || "—"}</TableCell>
                <TableCell>{formatDate(schedule.progress.next_run_at, schedule.time_zone)}</TableCell>
              </TableRow>
            ))}
            {!list.data?.length && (
              <TableRow><TableCell colSpan={7}>Расписаний пока нет.</TableCell></TableRow>
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
  if (!schedule.data) return <Alert severity="error">Расписание не найдено</Alert>;
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
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate("/schedules")}>Назад</Button>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h4">Расписание v{data.version_number}</Typography>
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
        <Chip label={`Волна ${data.progress.current_wave || "—"}`} />
        <Chip label={`${data.progress.completed_accounts} из ${data.progress.total_accounts} аккаунтов`} />
        <Chip label={`${data.progress.created_campaigns} кампаний создано`} />
      </Box>
      <LinearProgress variant="determinate" value={progress} sx={{ height: 8 }} />

      <Grid container spacing={1.5}>
        <Metric label="Успешно" value={data.progress.successful_accounts} />
        <Metric label="Ожидают" value={data.progress.waiting_accounts} />
        <Metric label="С ошибкой" value={data.progress.failed_accounts} />
        <Metric label="Следующий" value={data.progress.next_account || "—"} />
        <Metric label="Время запуска" value={formatDate(data.progress.next_run_at, data.time_zone)} />
        <Metric label="До запуска" value={countdown(data.progress.next_run_at, now)} />
      </Grid>

      <Box sx={actionGridSx}>
        <Button
          variant="outlined"
          startIcon={<PauseCircleOutlineIcon />}
          disabled={action.isPending || !canPause}
          onClick={() => dangerous("Приостановить расписание", { action: "PAUSE" })}
        >
          Приостановить
        </Button>
        <Button
          variant="outlined"
          startIcon={<PlayCircleOutlineIcon />}
          disabled={action.isPending || !["PAUSED", "PLANNED", "OBSERVATION"].includes(data.status)}
          onClick={() => dangerous("Продолжить последовательно", { action: "RESUME", recovery_strategy: "SEQUENTIAL" })}
        >
          Продолжить
        </Button>
        <Button
          variant="outlined"
          startIcon={<CheckCircleOutlineIcon />}
          disabled={action.isPending || data.status !== "WAITING_FOR_APPROVAL"}
          onClick={() => dangerous("Подтвердить следующую волну", { action: "APPROVE_NEXT_WAVE" })}
        >
          Подтвердить волну
        </Button>
        <Button
          variant="outlined"
          startIcon={<SkipNextOutlinedIcon />}
          disabled={action.isPending || !data.progress.next_account}
          onClick={() => dangerous("Запустить следующий аккаунт сейчас", { action: "RUN_NEXT_NOW" })}
        >
          Запустить следующий
        </Button>
        <Button
          component="a"
          href={api.scheduleReportUrl(data.id)}
          startIcon={<DownloadOutlinedIcon />}
        >
          Скачать отчёт
        </Button>
      </Box>

      <Box sx={actionGridSx}>
        <TextField
          size="small"
          type="number"
          label="Сдвиг оставшихся, мин."
          value={shiftMinutes}
          onChange={(event) => setShiftMinutes(Number(event.target.value) || 0)}
          sx={{ width: "100%" }}
        />
        <Button
          variant="outlined"
          startIcon={<ScheduleOutlinedIcon />}
          disabled={action.isPending || !shiftMinutes || !futureRuns.length}
          onClick={() => dangerous("Создать новую версию со сдвигом", {
            action: "RESCHEDULE_REMAINING",
            shift_minutes: shiftMinutes
          })}
        >
          Изменить время
        </Button>
        <TextField
          select
          size="small"
          label="Целевая волна"
          value={targetWave}
          onChange={(event) => setTargetWave(Number(event.target.value))}
          sx={{ width: "100%" }}
        >
          {data.waves.map((wave) => <MenuItem key={wave.id} value={wave.wave_number}>Волна {wave.wave_number}</MenuItem>)}
        </TextField>
        <Button
          variant="outlined"
          startIcon={<MoveDownOutlinedIcon />}
          disabled={action.isPending || selectedFutureRuns.length !== 1 || selected.length !== 1}
          onClick={() => dangerous("Перенести аккаунт в другую волну", {
            action: "MOVE_ACCOUNT",
            run_ids: [selected[0]],
            target_wave_number: targetWave
          })}
        >
          Перенести
        </Button>
        <Button
          variant="outlined"
          startIcon={<ReplayOutlinedIcon />}
          disabled={action.isPending || !selectedRuns.some((item) => item.status === "FAILED")}
          onClick={() => dangerous("Повторить выбранные после исправления", {
            action: "RETRY",
            run_ids: selected
          })}
        >
          Повторить
        </Button>
        <Button
          color="warning"
          startIcon={<CancelOutlinedIcon />}
          disabled={action.isPending || !selectedFutureRuns.length}
          onClick={() => dangerous("Отменить выбранные аккаунты", {
            action: "CANCEL_SELECTED",
            run_ids: selected
          })}
        >
          Отменить выбранные
        </Button>
        <Button
          color="error"
          startIcon={<DeleteSweepOutlinedIcon />}
          disabled={action.isPending || !futureRuns.length}
          onClick={() => dangerous("Отменить все будущие запуски", { action: "CANCEL_FUTURE" })}
        >
          Отменить будущие
        </Button>
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
              <TableCell>Волна</TableCell>
              <TableCell>Аккаунт</TableCell>
              <TableCell>Customer ID</TableCell>
              <TableCell>Кампаний</TableCell>
              <TableCell>Статус</TableCell>
              <TableCell>План</TableCell>
              <TableCell>Фактический старт</TableCell>
              <TableCell>Завершение</TableCell>
              <TableCell>Попытки</TableCell>
              <TableCell>Request ID</TableCell>
              <TableCell>Ошибка</TableCell>
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
          <Typography variant="h6" sx={{ mb: 1.5 }}>История расписания</Typography>
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
          label={`Волна ${wave.wave_number} · ${wave.status}${wave.observation_until ? ` · до ${formatDate(wave.observation_until, schedule.time_zone)}` : ""}`}
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
  return `${days ? `${days} д ` : ""}${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function formatDate(value: unknown, timeZone: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "medium",
    timeZone
  }).format(new Date(String(value)));
}

function modeLabel(mode: DeploymentSchedule["mode"]) {
  return {
    IMMEDIATE: "Создать сразу",
    EVEN: "Равномерно",
    WAVES: "Ступенчато",
    MANUAL: "Вручную"
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
