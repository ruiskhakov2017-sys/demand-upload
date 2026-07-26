import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography
} from "@mui/material";
import DragIndicatorIcon from "@mui/icons-material/DragIndicator";
import PreviewOutlinedIcon from "@mui/icons-material/PreviewOutlined";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  api,
  DeploymentSchedule,
  LaunchBatch,
  SchedulePreview
} from "../api/client";
import { StatusBadge } from "./StatusBadge";

type ManualRun = {
  account_test_bundle_id: string;
  scheduled_local: string | null;
  wave_number: number;
};

export type ScheduleDraft = {
  mode: "IMMEDIATE" | "EVEN" | "WAVES" | "MANUAL";
  time_zone: string;
  start_local: string;
  end_local: string;
  account_order: string[];
  max_accounts_per_hour: number;
  max_accounts_per_day: number;
  max_parallel: number;
  circuit_breaker_threshold: number;
  manual_approval: boolean;
  first_wave_size: number;
  observation_minutes: number;
  next_wave_size: number;
  between_waves_minutes: number;
  first_wave_spread_minutes: number;
  next_wave_spread_minutes: number;
  retry_max_attempts: number;
  retry_base_seconds: number;
  recovery_pause_after_seconds: number;
  manual_runs: ManualRun[];
};

export function ScheduleEditor({
  batch,
  scheduleId,
  onCreated
}: {
  batch?: LaunchBatch;
  scheduleId?: string | null;
  onCreated: (schedule: DeploymentSchedule) => void;
}) {
  const scheduleQuery = useQuery({
    queryKey: ["schedule", scheduleId],
    queryFn: () => api.getSchedule(scheduleId!),
    enabled: Boolean(scheduleId)
  });
  const [draft, setDraft] = useState<ScheduleDraft>(() => defaultDraft(batch));
  const [hydrated, setHydrated] = useState(false);
  const [preview, setPreview] = useState<SchedulePreview | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [bulkTime, setBulkTime] = useState(localInput(new Date(Date.now() + 60 * 60 * 1000)));
  const [shiftMinutes, setShiftMinutes] = useState(60);
  const [targetWave, setTargetWave] = useState(1);
  const [draggedId, setDraggedId] = useState<string | null>(null);

  useEffect(() => {
    if (hydrated || !batch) return;
    if (scheduleId && !scheduleQuery.data) return;
    const existing = scheduleQuery.data;
    setDraft(existing ? hydrateDraft(existing, batch) : defaultDraft(batch));
    setHydrated(true);
  }, [batch, hydrated, scheduleId, scheduleQuery.data]);

  const previewMutation = useMutation({
    mutationFn: () => api.previewSchedule(batch!.id, draft),
    onSuccess: setPreview
  });
  const createMutation = useMutation({
    mutationFn: () => api.createSchedule(batch!.id, draft),
    onSuccess: (result) => {
      onCreated(result);
      setPreview({
        mode: result.mode,
        time_zone: result.time_zone,
        fingerprint: result.fingerprint,
        valid: true,
        warnings: (result.summary.warnings || []) as SchedulePreview["warnings"],
        unassigned_accounts: [],
        summary: result.summary,
        waves: result.waves,
        runs: result.runs.map((item) => ({
          ...item,
          budget_micros: 0
        }))
      });
    }
  });
  const error = previewMutation.error || createMutation.error || scheduleQuery.error;
  const bundles = useMemo(() => orderedBundles(batch, draft.account_order), [batch, draft.account_order]);
  const set = <K extends keyof ScheduleDraft>(key: K, value: ScheduleDraft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));

  if (!batch) return <Alert severity="info">Сначала сформируйте Campaign matrix.</Alert>;

  const toggleSelected = (id: string) =>
    setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  const updateManual = (ids: string[], update: (row: ManualRun, index: number) => ManualRun) => {
    const selectedSet = new Set(ids);
    let selectedIndex = 0;
    setDraft((current) => ({
      ...current,
      manual_runs: current.manual_runs.map((row) => {
        if (!selectedSet.has(row.account_test_bundle_id)) return row;
        return update(row, selectedIndex++);
      })
    }));
  };
  const evenlyDistributeSelected = () => {
    if (!selected.length || !draft.start_local || !draft.end_local) return;
    const start = localAsEpoch(draft.start_local);
    const end = localAsEpoch(draft.end_local);
    const interval = (end - start) / Math.max(1, selected.length);
    updateManual(selected, (row, index) => ({
      ...row,
      scheduled_local: localFromEpoch(start + interval * index)
    }));
  };
  const shiftSelected = () => updateManual(selected, (row) => ({
    ...row,
    scheduled_local: row.scheduled_local
      ? localFromEpoch(localAsEpoch(row.scheduled_local) + shiftMinutes * 60_000)
      : row.scheduled_local
  }));
  const reorder = (targetId: string) => {
    if (!draggedId || draggedId === targetId) return;
    const order = bundles.map((item) => item.id);
    const from = order.indexOf(draggedId);
    const to = order.indexOf(targetId);
    order.splice(to, 0, order.splice(from, 1)[0]);
    set("account_order", order);
    setDraggedId(null);
  };

  return (
    <Stack spacing={2.5}>
      {error && <Alert severity="error">{error.message}</Alert>}
      {scheduleQuery.data && (
        <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap", alignItems: "center" }}>
          <StatusBadge value={scheduleQuery.data.status} />
          <Typography variant="body2">Версия {scheduleQuery.data.version_number}</Typography>
        </Stack>
      )}
      <ToggleButtonGroup
        exclusive
        size="small"
        value={draft.mode}
        onChange={(_, value) => value && set("mode", value)}
        sx={{ flexWrap: "wrap" }}
      >
        <ToggleButton value="IMMEDIATE">Создать сразу</ToggleButton>
        <ToggleButton value="EVEN">Равномерно</ToggleButton>
        <ToggleButton value="WAVES">Ступенчато</ToggleButton>
        <ToggleButton value="MANUAL">Вручную</ToggleButton>
      </ToggleButtonGroup>

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            fullWidth
            label="Часовой пояс"
            value={draft.time_zone}
            onChange={(event) => set("time_zone", event.target.value)}
          />
        </Grid>
        {draft.mode !== "IMMEDIATE" && (
          <>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                type="datetime-local"
                label="Начало"
                InputLabelProps={{ shrink: true }}
                value={draft.start_local}
                onChange={(event) => set("start_local", event.target.value)}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                type="datetime-local"
                label="Окончание"
                InputLabelProps={{ shrink: true }}
                value={draft.end_local}
                onChange={(event) => set("end_local", event.target.value)}
              />
            </Grid>
          </>
        )}
        <Grid item xs={6} sm={3} md={2}>
          <TextField
            fullWidth
            type="number"
            label="Аккаунтов в час"
            value={draft.max_accounts_per_hour}
            inputProps={{ min: 1 }}
            onChange={(event) => set("max_accounts_per_hour", positive(event.target.value, 1))}
          />
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <TextField
            fullWidth
            type="number"
            label="Аккаунтов в сутки"
            value={draft.max_accounts_per_day}
            inputProps={{ min: 1 }}
            onChange={(event) => set("max_accounts_per_day", positive(event.target.value, 1))}
          />
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <TextField
            fullWidth
            type="number"
            label="Одновременно"
            value={draft.max_parallel}
            inputProps={{ min: 1, max: 50 }}
            onChange={(event) => set("max_parallel", positive(event.target.value, 1))}
          />
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <TextField
            fullWidth
            type="number"
            label="Стоп после ошибок"
            value={draft.circuit_breaker_threshold}
            inputProps={{ min: 1 }}
            onChange={(event) => set("circuit_breaker_threshold", positive(event.target.value, 1))}
          />
        </Grid>
      </Grid>

      {draft.mode === "WAVES" && (
        <Grid container spacing={2}>
          <Grid item xs={6} md={2}><NumberField label="Первая волна" value={draft.first_wave_size} onChange={(value) => set("first_wave_size", value)} /></Grid>
          <Grid item xs={6} md={2}><NumberField label="Первая волна, мин." value={draft.first_wave_spread_minutes} onChange={(value) => set("first_wave_spread_minutes", value)} allowZero /></Grid>
          <Grid item xs={6} md={2}><NumberField label="Наблюдение, мин." value={draft.observation_minutes} onChange={(value) => set("observation_minutes", value)} allowZero /></Grid>
          <Grid item xs={6} md={2}><NumberField label="Следующие волны" value={draft.next_wave_size} onChange={(value) => set("next_wave_size", value)} /></Grid>
          <Grid item xs={6} md={2}><NumberField label="Волна, мин." value={draft.next_wave_spread_minutes} onChange={(value) => set("next_wave_spread_minutes", value)} allowZero /></Grid>
          <Grid item xs={6} md={2}><NumberField label="Между волнами, мин." value={draft.between_waves_minutes} onChange={(value) => set("between_waves_minutes", value)} allowZero /></Grid>
          <Grid item xs={12}>
            <FormControlLabel
              control={<Checkbox checked={draft.manual_approval} onChange={(event) => set("manual_approval", event.target.checked)} />}
              label="Подтверждать следующую волну вручную"
            />
          </Grid>
        </Grid>
      )}

      {draft.mode === "MANUAL" && (
        <Stack spacing={1.5}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>
            <TextField
              size="small"
              type="datetime-local"
              label="Время выбранных"
              InputLabelProps={{ shrink: true }}
              value={bulkTime}
              onChange={(event) => setBulkTime(event.target.value)}
            />
            <Button variant="outlined" onClick={() => updateManual(selected, (row) => ({ ...row, scheduled_local: bulkTime }))}>
              Установить
            </Button>
            <Button variant="outlined" onClick={evenlyDistributeSelected}>Распределить</Button>
            <TextField
              size="small"
              type="number"
              label="Сдвиг, мин."
              value={shiftMinutes}
              onChange={(event) => setShiftMinutes(Number(event.target.value) || 0)}
              sx={{ width: 140 }}
            />
            <Button variant="outlined" onClick={shiftSelected}>Сдвинуть</Button>
            <TextField
              size="small"
              type="number"
              label="Волна"
              value={targetWave}
              inputProps={{ min: 1 }}
              onChange={(event) => setTargetWave(positive(event.target.value, 1))}
              sx={{ width: 110 }}
            />
            <Button variant="outlined" onClick={() => updateManual(selected, (row) => ({ ...row, wave_number: targetWave }))}>
              Перенести
            </Button>
            <Button color="inherit" onClick={() => updateManual(selected, (row) => ({ ...row, scheduled_local: null }))}>
              Очистить
            </Button>
          </Stack>
        </Stack>
      )}

      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              {draft.mode === "MANUAL" && <TableCell padding="checkbox" />}
              <TableCell padding="checkbox" />
              <TableCell>Аккаунт</TableCell>
              <TableCell>Customer ID</TableCell>
              <TableCell>Кампаний</TableCell>
              {draft.mode === "MANUAL" && <TableCell>Плановое время</TableCell>}
              {draft.mode === "MANUAL" && <TableCell>Волна</TableCell>}
            </TableRow>
          </TableHead>
          <TableBody>
            {bundles.map((bundle) => {
              const manual = draft.manual_runs.find((item) => item.account_test_bundle_id === bundle.id);
              return (
                <TableRow
                  key={bundle.id}
                  draggable
                  onDragStart={() => setDraggedId(bundle.id)}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => reorder(bundle.id)}
                  hover
                >
                  {draft.mode === "MANUAL" && (
                    <TableCell padding="checkbox">
                      <Checkbox checked={selected.includes(bundle.id)} onChange={() => toggleSelected(bundle.id)} />
                    </TableCell>
                  )}
                  <TableCell padding="checkbox"><DragIndicatorIcon color="disabled" /></TableCell>
                  <TableCell>{bundle.account_name}</TableCell>
                  <TableCell sx={{ fontFamily: "monospace" }}>{bundle.customer_id}</TableCell>
                  <TableCell>{bundle.campaigns_count}</TableCell>
                  {draft.mode === "MANUAL" && (
                    <TableCell sx={{ minWidth: 210 }}>
                      <TextField
                        size="small"
                        type="datetime-local"
                        InputLabelProps={{ shrink: true }}
                        value={manual?.scheduled_local || ""}
                        onChange={(event) => updateManual([bundle.id], (row) => ({ ...row, scheduled_local: event.target.value }))}
                      />
                    </TableCell>
                  )}
                  {draft.mode === "MANUAL" && (
                    <TableCell sx={{ width: 110 }}>
                      <TextField
                        size="small"
                        type="number"
                        value={manual?.wave_number || 1}
                        inputProps={{ min: 1 }}
                        onChange={(event) => updateManual([bundle.id], (row) => ({ ...row, wave_number: positive(event.target.value, 1) }))}
                      />
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Box>

      <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
        <Button
          variant="outlined"
          startIcon={<PreviewOutlinedIcon />}
          disabled={previewMutation.isPending}
          onClick={() => previewMutation.mutate()}
        >
          Рассчитать
        </Button>
        <Button
          variant="contained"
          startIcon={<SaveOutlinedIcon />}
          disabled={!preview?.valid || createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          Зафиксировать расписание
        </Button>
      </Stack>

      {preview && <SchedulePreviewTable preview={preview} />}
    </Stack>
  );
}

function SchedulePreviewTable({ preview }: { preview: SchedulePreview }) {
  return (
    <Stack spacing={2}>
      <Grid container spacing={1.5}>
        {[
          ["Аккаунтов", preview.summary.accounts],
          ["Кампаний", preview.summary.campaigns],
          ["Волн", preview.summary.waves],
          ["Начало", formatDate(preview.summary.start_at, preview.time_zone)],
          ["Окончание", formatDate(preview.summary.end_at, preview.time_zone)],
          ["Одновременно", preview.summary.max_parallel]
        ].map(([label, value]) => (
          <Grid item xs={6} md={2} key={String(label)}>
            <Box sx={{ borderTop: 2, borderColor: "primary.main", pt: 1 }}>
              <Typography variant="caption" color="text.secondary">{label}</Typography>
              <Typography fontWeight={700}>{value ?? "—"}</Typography>
            </Box>
          </Grid>
        ))}
      </Grid>
      {preview.warnings.map((item) => <Alert key={`${item.code}-${item.message}`} severity="warning">{item.message}</Alert>)}
      {!preview.valid && <Alert severity="error">Есть аккаунты без назначенного времени.</Alert>}
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Волна</TableCell>
              <TableCell>Плановое время</TableCell>
              <TableCell>Аккаунт</TableCell>
              <TableCell>Customer ID</TableCell>
              <TableCell>Кампаний</TableCell>
              <TableCell>Бюджет</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {preview.runs.map((run) => (
              <TableRow key={run.account_test_bundle_id}>
                <TableCell>{run.wave_number}</TableCell>
                <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(run.scheduled_for, preview.time_zone)}</TableCell>
                <TableCell>{run.account_name}</TableCell>
                <TableCell sx={{ fontFamily: "monospace" }}>{run.customer_id}</TableCell>
                <TableCell>{run.campaigns_count}</TableCell>
                <TableCell>{(run.budget_micros / 1_000_000).toLocaleString("ru-RU")}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ overflowWrap: "anywhere" }}>
        Fingerprint: {preview.fingerprint}
      </Typography>
    </Stack>
  );
}

function NumberField({
  label,
  value,
  onChange,
  allowZero = false
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  allowZero?: boolean;
}) {
  return (
    <TextField
      fullWidth
      type="number"
      label={label}
      value={value}
      inputProps={{ min: allowZero ? 0 : 1 }}
      onChange={(event) => onChange(positive(event.target.value, allowZero ? 0 : 1))}
    />
  );
}

function defaultDraft(batch?: LaunchBatch): ScheduleDraft {
  const start = new Date(Date.now() + 10 * 60_000);
  const end = new Date(start.getTime() + 24 * 60 * 60_000);
  const bundles = batch?.bundles || [];
  return {
    mode: "IMMEDIATE",
    time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    start_local: localInput(start),
    end_local: localInput(end),
    account_order: bundles.map((item) => item.id),
    max_accounts_per_hour: 50,
    max_accounts_per_day: 500,
    max_parallel: 1,
    circuit_breaker_threshold: 2,
    manual_approval: true,
    first_wave_size: 5,
    observation_minutes: 720,
    next_wave_size: 10,
    between_waves_minutes: 360,
    first_wave_spread_minutes: 240,
    next_wave_spread_minutes: 480,
    retry_max_attempts: 3,
    retry_base_seconds: 60,
    recovery_pause_after_seconds: 300,
    manual_runs: bundles.map((item) => ({
      account_test_bundle_id: item.id,
      scheduled_local: null,
      wave_number: 1
    }))
  };
}

function hydrateDraft(schedule: DeploymentSchedule, batch: LaunchBatch): ScheduleDraft {
  const defaults = defaultDraft(batch);
  const config = schedule.config || {};
  const formatter = (value: string) => localInput(new Date(value));
  return {
    ...defaults,
    ...config,
    mode: schedule.mode,
    time_zone: schedule.time_zone,
    start_local: config.start_local || formatter(schedule.start_at),
    end_local: config.end_local || formatter(schedule.end_at),
    account_order: config.account_order || schedule.runs.map((item) => item.account_test_bundle_id),
    manual_runs: config.manual_runs || schedule.runs.map((item) => ({
      account_test_bundle_id: item.account_test_bundle_id,
      scheduled_local: formatter(item.scheduled_for),
      wave_number: item.wave_number
    }))
  };
}

function orderedBundles(batch: LaunchBatch | undefined, order: string[]) {
  const positions = new Map(order.map((id, index) => [id, index]));
  return [...(batch?.bundles || [])].sort(
    (left, right) => (positions.get(left.id) ?? 9999) - (positions.get(right.id) ?? 9999)
  );
}

function localInput(value: Date) {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

function localAsEpoch(value: string) {
  return new Date(`${value}:00Z`).getTime();
}

function localFromEpoch(value: number) {
  return new Date(value).toISOString().slice(0, 16);
}

function positive(value: string, minimum: number) {
  return Math.max(minimum, Number(value) || minimum);
}

function formatDate(value: unknown, timeZone: string) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "medium",
    timeZone
  }).format(new Date(String(value)));
}
