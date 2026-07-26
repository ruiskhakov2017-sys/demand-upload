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
import { formatNumber, localeTag, t } from "../i18n";

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

  if (!batch) return <Alert severity="info">{t("ui.259dd04093")}</Alert>;

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
          <Typography variant="body2">{t("ui.97c248cbe0")}{" "}{scheduleQuery.data.version_number}</Typography>
        </Stack>
      )}
      <ToggleButtonGroup
        exclusive
        size="small"
        value={draft.mode}
        onChange={(_, value) => value && set("mode", value)}
        sx={{ flexWrap: "wrap" }}
      >
        <ToggleButton value="IMMEDIATE">{t("ui.b279f707db")}</ToggleButton>
        <ToggleButton value="EVEN">{t("ui.91bb2ac541")}</ToggleButton>
        <ToggleButton value="WAVES">{t("ui.1d39173cf8")}</ToggleButton>
        <ToggleButton value="MANUAL">{t("ui.5ec7b0f52b")}</ToggleButton>
      </ToggleButtonGroup>

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={3}>
          <TextField
            fullWidth
            label={t("ui.47947a0c46")}
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
                label={t("ui.cb26bdc6c6")}
                InputLabelProps={{ shrink: true }}
                value={draft.start_local}
                onChange={(event) => set("start_local", event.target.value)}
              />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <TextField
                fullWidth
                type="datetime-local"
                label={t("ui.ec5bfc700b")}
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
            label={t("ui.2c2154e5df")}
            value={draft.max_accounts_per_hour}
            inputProps={{ min: 1 }}
            onChange={(event) => set("max_accounts_per_hour", positive(event.target.value, 1))}
          />
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <TextField
            fullWidth
            type="number"
            label={t("ui.ed54bc88e3")}
            value={draft.max_accounts_per_day}
            inputProps={{ min: 1 }}
            onChange={(event) => set("max_accounts_per_day", positive(event.target.value, 1))}
          />
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <TextField
            fullWidth
            type="number"
            label={t("ui.957ad6e34d")}
            value={draft.max_parallel}
            inputProps={{ min: 1, max: 50 }}
            onChange={(event) => set("max_parallel", positive(event.target.value, 1))}
          />
        </Grid>
        <Grid item xs={6} sm={3} md={2}>
          <TextField
            fullWidth
            type="number"
            label={t("ui.83e452e520")}
            value={draft.circuit_breaker_threshold}
            inputProps={{ min: 1 }}
            onChange={(event) => set("circuit_breaker_threshold", positive(event.target.value, 1))}
          />
        </Grid>
      </Grid>

      {draft.mode === "WAVES" && (
        <Grid container spacing={2}>
          <Grid item xs={6} md={2}><NumberField label={t("ui.2404e0c60b")} value={draft.first_wave_size} onChange={(value) => set("first_wave_size", value)} /></Grid>
          <Grid item xs={6} md={2}><NumberField label={t("ui.78b185537f")} value={draft.first_wave_spread_minutes} onChange={(value) => set("first_wave_spread_minutes", value)} allowZero /></Grid>
          <Grid item xs={6} md={2}><NumberField label={t("ui.32c0831f0f")} value={draft.observation_minutes} onChange={(value) => set("observation_minutes", value)} allowZero /></Grid>
          <Grid item xs={6} md={2}><NumberField label={t("ui.acaac67857")} value={draft.next_wave_size} onChange={(value) => set("next_wave_size", value)} /></Grid>
          <Grid item xs={6} md={2}><NumberField label={t("ui.7975d889e2")} value={draft.next_wave_spread_minutes} onChange={(value) => set("next_wave_spread_minutes", value)} allowZero /></Grid>
          <Grid item xs={6} md={2}><NumberField label={t("ui.3b57a4df79")} value={draft.between_waves_minutes} onChange={(value) => set("between_waves_minutes", value)} allowZero /></Grid>
          <Grid item xs={12}>
            <FormControlLabel
              control={<Checkbox checked={draft.manual_approval} onChange={(event) => set("manual_approval", event.target.checked)} />}
              label={t("ui.1c6755c2f2")}
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
              label={t("ui.b0c03bea7b")}
              InputLabelProps={{ shrink: true }}
              value={bulkTime}
              onChange={(event) => setBulkTime(event.target.value)}
            />
            <Button variant="outlined" onClick={() => updateManual(selected, (row) => ({ ...row, scheduled_local: bulkTime }))}>
              {t("ui.ce88d35b18")}</Button>
            <Button variant="outlined" onClick={evenlyDistributeSelected}>{t("ui.af7b241de2")}</Button>
            <TextField
              size="small"
              type="number"
              label={t("ui.2d4942c280")}
              value={shiftMinutes}
              onChange={(event) => setShiftMinutes(Number(event.target.value) || 0)}
              sx={{ width: 140 }}
            />
            <Button variant="outlined" onClick={shiftSelected}>{t("ui.8b4baf0614")}</Button>
            <TextField
              size="small"
              type="number"
              label={t("ui.cdec369bf5")}
              value={targetWave}
              inputProps={{ min: 1 }}
              onChange={(event) => setTargetWave(positive(event.target.value, 1))}
              sx={{ width: 110 }}
            />
            <Button variant="outlined" onClick={() => updateManual(selected, (row) => ({ ...row, wave_number: targetWave }))}>
              {t("ui.081b1d81c6")}</Button>
            <Button color="inherit" onClick={() => updateManual(selected, (row) => ({ ...row, scheduled_local: null }))}>
              {t("ui.98b2073ed1")}</Button>
          </Stack>
        </Stack>
      )}

      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              {draft.mode === "MANUAL" && <TableCell padding="checkbox" />}
              <TableCell padding="checkbox" />
              <TableCell>{t("ui.5b16fcdd97")}</TableCell>
              <TableCell>Customer ID</TableCell>
              <TableCell>{t("ui.cf645a44e5")}</TableCell>
              {draft.mode === "MANUAL" && <TableCell>{t("ui.70c8af6237")}</TableCell>}
              {draft.mode === "MANUAL" && <TableCell>{t("ui.cdec369bf5")}</TableCell>}
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
          {t("ui.e5ba4505fe")}</Button>
        <Button
          variant="contained"
          startIcon={<SaveOutlinedIcon />}
          disabled={!preview?.valid || createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          {t("ui.5104e2145b")}</Button>
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
          [t("ui.9b92cdaa6e"), preview.summary.accounts],
          [t("ui.cf645a44e5"), preview.summary.campaigns],
          [t("ui.51fbf9617f"), preview.summary.waves],
          [t("ui.cb26bdc6c6"), formatDate(preview.summary.start_at, preview.time_zone)],
          [t("ui.ec5bfc700b"), formatDate(preview.summary.end_at, preview.time_zone)],
          [t("ui.957ad6e34d"), preview.summary.max_parallel]
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
      {!preview.valid && <Alert severity="error">{t("ui.9607890316")}</Alert>}
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{t("ui.cdec369bf5")}</TableCell>
              <TableCell>{t("ui.70c8af6237")}</TableCell>
              <TableCell>{t("ui.5b16fcdd97")}</TableCell>
              <TableCell>Customer ID</TableCell>
              <TableCell>{t("ui.cf645a44e5")}</TableCell>
              <TableCell>{t("ui.0773ed4942")}</TableCell>
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
                <TableCell>{formatNumber(run.budget_micros / 1_000_000)}</TableCell>
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
  return new Intl.DateTimeFormat(localeTag(), {
    dateStyle: "short",
    timeStyle: "medium",
    timeZone
  }).format(new Date(String(value)));
}
