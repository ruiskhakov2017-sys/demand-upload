import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  FormControl,
  FormControlLabel,
  Grid,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Step,
  StepButton,
  Stepper,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import CloudUploadOutlinedIcon from "@mui/icons-material/CloudUploadOutlined";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import FactCheckOutlinedIcon from "@mui/icons-material/FactCheckOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import RefreshIcon from "@mui/icons-material/Refresh";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import ScienceOutlinedIcon from "@mui/icons-material/ScienceOutlined";
import YouTubeIcon from "@mui/icons-material/YouTube";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  api,
  CampaignInstance,
  CustomerAccount,
  DeploymentPlan,
  DomainValidationReport,
  DomainValidationResult,
  LaunchBatch,
  MediaAsset
} from "../api/client";
import type { Navigate } from "../app/App";
import { StatusBadge } from "../components/StatusBadge";
import { ScheduleEditor } from "../components/ScheduleEditor";
import { applyCampaignCount, normalizeCampaignCount, QUICK_CAMPAIGN_COUNTS } from "../domain/campaignCounts";

const steps = [
  "Google connection",
  "MCC",
  "Аккаунты",
  "Режим создания",
  "Шаблон",
  "Campaign settings",
  "Ad group settings",
  "Audience и demographics",
  "Ads и assets",
  "Количество кампаний",
  "Генератор бюджетов",
  "Распределение креативов",
  "Account overrides",
  "Campaign matrix",
  "Расписание",
  "Local validation",
  "Google validate_only",
  "Financial preview",
  "Confirmation",
  "Creation in PAUSED",
  "Report"
];

type ExecutionMode = "SIMULATION" | "LIVE";
type CreationMode = "FROM_TEMPLATE" | "FULL_SETUP" | "FROM_EXISTING" | "FILE";
type BuilderAccount = {
  id?: string;
  customer_id: string;
  account_name: string;
  currency_code: string;
  time_zone: string;
  campaigns_count?: number;
  overrides: Record<string, any>;
};

type BuilderForm = {
  execution_mode: ExecutionMode;
  creation_mode: CreationMode;
  template_id: string;
  batch_name: string;
  name_pattern: string;
  generation_seed: string;
  ad_type: "VIDEO" | "IMAGE" | "CAROUSEL";
  ad_group_name: string;
  business_name: string;
  final_url: string;
  mobile_final_url: string;
  tracking_template: string;
  final_url_suffix: string;
  append_instance_parameter: boolean;
  start_date_time: string;
  end_date_time: string;
  bidding_strategy: "TARGET_CPA" | "MAXIMIZE_CONVERSIONS" | "TARGET_ROAS" | "MAXIMIZE_CLICKS";
  target_cpa: string;
  target_roas: string;
  conversion_actions: string;
  location_ids: string;
  excluded_location_ids: string;
  language_ids: string;
  audience_resource_names: string;
  user_list_resource_names: string;
  custom_audience_resource_names: string;
  age_ranges: string[];
  genders: string[];
  parental_statuses: string[];
  income_ranges: string[];
  optimized_targeting: boolean;
  channel_mode: "ALL_CHANNELS" | "GOOGLE_OWNED" | "MANUAL";
  channels: Record<string, boolean>;
  headlines: string;
  long_headline: string;
  descriptions: string;
  carousel_card_headlines: string;
  call_to_action: string;
  youtube_video_id: string;
  media_ids: string[];
  campaigns_per_account: number;
  copy_mode: string;
  budget_mode: "FIXED" | "RANGE" | "MANUAL_LIST" | "PER_ACCOUNT_OVERRIDE" | "PER_CAMPAIGN_OVERRIDE";
  budget_distribution: "BALANCED_RANDOM" | "RANDOM" | "SEQUENTIAL" | "MANUAL_AFTER_GENERATION";
  budget_fixed: string;
  budget_minimum: string;
  budget_maximum: string;
  budget_step: string;
  budget_manual_values: string;
  allow_repeats: boolean;
  password_confirmation: string;
};

const emptyForm: BuilderForm = {
  execution_mode: "SIMULATION",
  creation_mode: "FROM_TEMPLATE",
  template_id: "",
  batch_name: `Demand Gen test ${new Date().toLocaleDateString("ru-RU")}`,
  name_pattern: "{account_name}_{template_name}_{date}_{sequence}",
  generation_seed: "dgu-balanced-v1",
  ad_type: "VIDEO",
  ad_group_name: "Основная группа",
  business_name: "Demo Brand",
  final_url: "https://example.com",
  mobile_final_url: "",
  tracking_template: "",
  final_url_suffix: "utm_source=dgu",
  append_instance_parameter: false,
  start_date_time: "",
  end_date_time: "",
  bidding_strategy: "TARGET_CPA",
  target_cpa: "25",
  target_roas: "300",
  conversion_actions: "",
  location_ids: "2203",
  excluded_location_ids: "",
  language_ids: "1000",
  audience_resource_names: "",
  user_list_resource_names: "",
  custom_audience_resource_names: "",
  age_ranges: ["AGE_RANGE_18_24", "AGE_RANGE_25_34", "AGE_RANGE_35_44"],
  genders: ["MALE", "FEMALE", "UNDETERMINED"],
  parental_statuses: [],
  income_ranges: [],
  optimized_targeting: true,
  channel_mode: "ALL_CHANNELS",
  channels: {
    youtube_in_stream: true,
    youtube_in_feed: true,
    youtube_shorts: true,
    discover: true,
    gmail: true,
    display: true,
    maps: false
  },
  headlines: "Новый способ достичь цели\nПопробуйте сегодня",
  long_headline: "Откройте новый способ достичь цели уже сегодня",
  descriptions: "Узнайте больше о нашем предложении.",
  carousel_card_headlines: "Вариант 1\nВариант 2",
  call_to_action: "LEARN_MORE",
  youtube_video_id: "dQw4w9WgXcQ",
  media_ids: [],
  campaigns_per_account: 3,
  copy_mode: "SAME_SETTINGS_RANDOM_BUDGET",
  budget_mode: "RANGE",
  budget_distribution: "BALANCED_RANDOM",
  budget_fixed: "250",
  budget_minimum: "200",
  budget_maximum: "300",
  budget_step: "1",
  budget_manual_values: "",
  allow_repeats: true,
  password_confirmation: ""
};

export function NewUploadPage({ navigate }: { navigate: Navigate }) {
  const [name, setName] = useState(`Demand Gen ${new Date().toLocaleDateString("ru-RU")}`);
  const [mode, setMode] = useState<ExecutionMode>("SIMULATION");
  const create = useMutation({
    mutationFn: () => api.createUpload({ name, execution_mode: mode }),
    onSuccess: (upload) => navigate(`/uploads/${upload.id}`, true)
  });
  return (
    <Stack spacing={3} sx={{ maxWidth: 760 }}>
      <Typography variant="h4">Новая загрузка</Typography>
      {create.error && <Alert severity="error">{create.error.message}</Alert>}
      <Paper variant="outlined" sx={{ p: { xs: 2, sm: 3 } }}>
        <Stack spacing={3}>
          <TextField label="Название" value={name} onChange={(event) => setName(event.target.value)} fullWidth />
          <ToggleButtonGroup exclusive value={mode} onChange={(_, value) => value && setMode(value)} size="small">
            <ToggleButton value="SIMULATION">TEST / MOCK</ToggleButton>
            <ToggleButton value="LIVE">LIVE / Google Ads</ToggleButton>
          </ToggleButtonGroup>
          <Alert severity={mode === "SIMULATION" ? "info" : "warning"}>
            {mode === "SIMULATION"
              ? "Тестовый режим: Google Ads API не вызывается."
              : "Реальный режим: кампании создаются в PAUSED после validate_only."}
          </Alert>
          <Box>
            <Button
              variant="contained"
              startIcon={create.isPending ? <CircularProgress size={18} color="inherit" /> : <ArrowForwardIcon />}
              disabled={name.trim().length < 2 || create.isPending}
              onClick={() => create.mutate()}
            >
              Открыть Campaign Builder
            </Button>
          </Box>
        </Stack>
      </Paper>
    </Stack>
  );
}

export function UploadWizardPage({ uploadId, navigate }: { uploadId: string; navigate: Navigate }) {
  const queryClient = useQueryClient();
  const uploadQuery = useQuery({ queryKey: ["upload", uploadId], queryFn: () => api.getUpload(uploadId) });
  const connections = useQuery({ queryKey: ["connections"], queryFn: api.listConnections });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: api.listAccounts });
  const templates = useQuery({ queryKey: ["templates"], queryFn: api.listTemplates });
  const media = useQuery({ queryKey: ["media"], queryFn: api.listMedia });
  const plans = useQuery({ queryKey: ["plans"], queryFn: api.listPlans });
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: api.getCapabilities });
  const domainValidation = useQuery({
    queryKey: ["domain-validation", uploadId],
    queryFn: () => api.getDomainValidation(uploadId),
    refetchInterval: (query) => query.state.data?.status === "PENDING" ? 1500 : false
  });
  const [form, setForm] = useState<BuilderForm>(emptyForm);
  const [selectedAccounts, setSelectedAccounts] = useState<BuilderAccount[]>([]);
  const [connectionId, setConnectionId] = useState("");
  const [uploadName, setUploadName] = useState("");
  const [step, setStep] = useState(0);
  const [hydrated, setHydrated] = useState(false);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [matrixFilter, setMatrixFilter] = useState("");
  const [selectedRows, setSelectedRows] = useState<string[]>([]);
  const [matrixEdits, setMatrixEdits] = useState<Record<string, { name: string; budget: string }>>({});
  const [bulkBudget, setBulkBudget] = useState("");
  const [youtubeInput, setYoutubeInput] = useState("");

  useEffect(() => {
    if (!uploadQuery.data || hydrated) return;
    const upload = uploadQuery.data;
    const builder = (upload.draft?.builder || {}) as Record<string, any>;
    setUploadName(upload.name);
    setConnectionId(upload.connection_id || "");
    setStep(Math.min(upload.current_step || 0, steps.length - 1));
    setBatchId(upload.draft?.launch_batch_id || null);
    setScheduleId(upload.draft?.schedule_id || null);
    setSelectedAccounts((builder.accounts || []).map(normalizeBuilderAccount));
    setForm(hydrateBuilderForm(upload.draft?.execution_mode || "SIMULATION", builder));
    setHydrated(true);
  }, [hydrated, uploadQuery.data]);

  const latestPlan = useMemo(
    () => (plans.data || [])
      .filter((item) => item.upload_id === uploadId && (!batchId || item.launch_batch_id === batchId))
      .sort((a, b) => b.created_at.localeCompare(a.created_at))[0],
    [batchId, plans.data, uploadId]
  );
  useEffect(() => {
    if (!planId && latestPlan) setPlanId(latestPlan.id);
  }, [latestPlan, planId]);

  const batchQuery = useQuery({
    queryKey: ["launch-batch", batchId],
    queryFn: () => api.getLaunchBatch(batchId!),
    enabled: Boolean(batchId),
    refetchInterval: 3000
  });
  const planQuery = useQuery({
    queryKey: ["plan", planId],
    queryFn: () => api.getPlan(planId!),
    enabled: Boolean(planId),
    refetchInterval: (query) => ["QUEUED", "RUNNING"].includes(query.state.data?.status || "") ? 2000 : false
  });
  const batch = batchQuery.data;
  const activePlan = planQuery.data || (latestPlan?.id === planId ? latestPlan : undefined);

  const save = useMutation({
    mutationFn: (targetStep: number) => api.updateUpload(uploadId, {
      name: uploadName,
      connection_id: connectionId || null,
      current_step: targetStep,
      draft: {
        ...(uploadQuery.data?.draft || {}),
        execution_mode: form.execution_mode,
        source_mode: form.creation_mode === "FILE" ? "FILE" : "MANUAL",
        launch_batch_id: batchId,
        schedule_id: scheduleId,
        builder: buildBatchPayload(form, selectedAccounts)
      }
    }),
    onSuccess: (upload) => {
      queryClient.setQueryData(["upload", uploadId], upload);
      setNotice("Черновик сохранён");
    }
  });
  const generate = useMutation({
    mutationFn: async () => {
      await save.mutateAsync(13);
      return api.generateLaunchBatch(uploadId, buildBatchPayload(form, selectedAccounts));
    },
    onSuccess: (result) => {
      setBatchId(result.id);
      setScheduleId(null);
      setPlanId(null);
      queryClient.setQueryData(["launch-batch", result.id], result);
      queryClient.invalidateQueries({ queryKey: ["upload", uploadId] });
      queryClient.invalidateQueries({ queryKey: ["launch-batches"] });
      setSelectedRows([]);
      setMatrixEdits({});
      setNotice(`Сформировано Campaign Instance: ${result.campaigns_count}`);
    }
  });
  const buildPlan = useMutation({
    mutationFn: () => api.buildPlan(uploadId, form.execution_mode, scheduleId),
    onSuccess: (plan) => {
      setPlanId(plan.id);
      queryClient.setQueryData(["plan", plan.id], plan);
      queryClient.invalidateQueries({ queryKey: ["launch-batch", batchId] });
      setNotice(plan.local_validation.valid ? "Local validation пройдена" : "Local validation нашла ошибки");
    }
  });
  const validatePlan = useMutation({
    mutationFn: () => api.validatePlan(planId!),
    onSuccess: (result) => {
      queryClient.setQueryData(["plan", result.plan.id], result.plan);
      queryClient.invalidateQueries({ queryKey: ["launch-batch", batchId] });
      setNotice(result.ok ? "validate_only пройден" : "validate_only завершён с ошибками");
    }
  });
  const confirmPlan = useMutation({
    mutationFn: () => api.confirmPlan(planId!),
    onSuccess: (result) => {
      queryClient.setQueryData(["plan", result.plan.id], result.plan);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      setNotice(result.reused ? "Использовано существующее задание" : "Расписание подтверждено");
      planQuery.refetch();
    }
  });
  const patchInstance = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, any> }) => api.patchCampaignInstance(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["launch-batch", batchId] });
      setNotice("Campaign Instance обновлена");
    }
  });
  const importFile = useMutation({
    mutationFn: (file: File) => api.importUpload(uploadId, file),
    onSuccess: (result) => {
      queryClient.setQueryData(["upload", uploadId], result.upload);
      queryClient.invalidateQueries({ queryKey: ["domain-validation", uploadId] });
      setNotice(`Импортировано строк: ${result.row_count}`);
    }
  });
  const retryDomainValidation = useMutation({
    mutationFn: () => api.retryDomainValidation(uploadId),
    onSuccess: (report) => {
      queryClient.setQueryData(["domain-validation", uploadId], report);
      queryClient.invalidateQueries({ queryKey: ["upload", uploadId] });
      setNotice("Проверка доменов завершена");
    }
  });
  const uploadMedia = useMutation({
    mutationFn: api.uploadMedia,
    onSuccess: (asset) => {
      queryClient.invalidateQueries({ queryKey: ["media"] });
      setForm((value) => ({ ...value, media_ids: [...new Set([...value.media_ids, asset.id])] }));
    }
  });
  const registerYoutube = useMutation({
    mutationFn: () => api.registerYoutube(youtubeInput),
    onSuccess: (asset) => {
      queryClient.invalidateQueries({ queryKey: ["media"] });
      setForm((value) => ({
        ...value,
        youtube_video_id: asset.youtube_video_id || youtubeInput,
        media_ids: [...new Set([...value.media_ids, asset.id])]
      }));
      setYoutubeInput("");
    }
  });

  const mutationError = save.error || generate.error || buildPlan.error || validatePlan.error || confirmPlan.error ||
    patchInstance.error || importFile.error || uploadMedia.error || registerYoutube.error;
  if (uploadQuery.isLoading || !hydrated) return <CircularProgress />;
  if (uploadQuery.error) return <Alert severity="error">{uploadQuery.error.message}</Alert>;

  const set = <K extends keyof BuilderForm>(key: K, value: BuilderForm[K]) =>
    setForm((current) => ({ ...current, [key]: value }));
  const move = async (next: number) => {
    await save.mutateAsync(next);
    setStep(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const visibleAccounts = (accounts.data || []).filter((item) => !connectionId || item.connection_id === connectionId);
  const allInstances = (batch?.bundles || []).flatMap((item) => item.instances || []);
  const filteredInstances = allInstances.filter((item) => {
    const needle = matrixFilter.toLowerCase();
    return !needle || `${item.account_name} ${item.customer_id} ${item.campaign_name} ${item.status}`.toLowerCase().includes(needle);
  });
  const busy = [save, generate, buildPlan, validatePlan, confirmPlan, patchInstance].some((item) => item.isPending);

  return (
    <Stack spacing={2.5} sx={{ minWidth: 0 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2, flexWrap: "wrap" }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="h4" sx={{ overflowWrap: "anywhere" }}>{uploadName}</Typography>
          <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1, flexWrap: "wrap" }}>
            <StatusBadge value={uploadQuery.data!.status} />
            <Chip
              size="small"
              color={form.execution_mode === "LIVE" ? "warning" : "info"}
              label={form.execution_mode === "LIVE" ? "LIVE · Google Ads" : "TEST / MOCK · Google не вызывается"}
            />
            {batch && <StatusBadge value={batch.status} />}
          </Stack>
        </Box>
        <Button variant="outlined" startIcon={<SaveOutlinedIcon />} disabled={busy} onClick={() => save.mutate(step)}>
          Сохранить
        </Button>
      </Box>
      {mutationError && <Alert severity="error">{mutationError.message}</Alert>}
      {notice && <Alert severity="success" onClose={() => setNotice(null)}>{notice}</Alert>}
      <DomainValidationPanel
        report={domainValidation.data}
        loading={domainValidation.isLoading || retryDomainValidation.isPending}
        error={domainValidation.error?.message || retryDomainValidation.error?.message}
        onRetry={() => retryDomainValidation.mutate()}
      />

      <Paper variant="outlined" sx={{ overflow: "hidden", minWidth: 0 }}>
        <Box sx={{ overflowX: "auto", px: 2, pt: 2 }}>
          <Stepper nonLinear activeStep={step} sx={{ minWidth: 2500 }}>
            {steps.map((label, index) => (
              <Step key={label} completed={index < step}>
                <StepButton onClick={() => move(index)}>{index + 1}. {label}</StepButton>
              </Step>
            ))}
          </Stepper>
        </Box>
        <Divider sx={{ mt: 2 }} />
        <Box sx={{ p: { xs: 2, sm: 3 }, minHeight: 470 }}>
          <BuilderStep
            step={step}
            form={form}
            set={set}
            uploadName={uploadName}
            setUploadName={setUploadName}
            connectionId={connectionId}
            setConnectionId={setConnectionId}
            connections={connections.data || []}
            accounts={visibleAccounts}
            selectedAccounts={selectedAccounts}
            setSelectedAccounts={setSelectedAccounts}
            templates={templates.data || []}
            media={media.data || []}
            capabilities={capabilities.data?.fields || []}
            batch={batch}
            plan={activePlan}
            domainValidation={
              (activePlan?.snapshot.domain_validation as DomainValidationReport | undefined)
              || domainValidation.data
            }
            allInstances={allInstances}
            filteredInstances={filteredInstances}
            matrixFilter={matrixFilter}
            setMatrixFilter={setMatrixFilter}
            selectedRows={selectedRows}
            setSelectedRows={setSelectedRows}
            matrixEdits={matrixEdits}
            setMatrixEdits={setMatrixEdits}
            bulkBudget={bulkBudget}
            setBulkBudget={setBulkBudget}
            confirmed={confirmed}
            setConfirmed={setConfirmed}
            youtubeInput={youtubeInput}
            setYoutubeInput={setYoutubeInput}
            busy={busy}
            onGenerate={() => generate.mutate()}
            onBuildPlan={() => buildPlan.mutate()}
            onValidate={() => validatePlan.mutate()}
            onConfirm={() => confirmPlan.mutate()}
            onPatch={(id, payload) => patchInstance.mutate({ id, payload })}
            onImport={(file) => importFile.mutate(file)}
            onUploadMedia={(file) => uploadMedia.mutate(file)}
            onRegisterYoutube={() => registerYoutube.mutate()}
            scheduleId={scheduleId}
            onScheduleCreated={(schedule) => {
              setScheduleId(schedule.id);
              queryClient.setQueryData(["schedule", schedule.id], schedule);
              queryClient.invalidateQueries({ queryKey: ["upload", uploadId] });
              setNotice("Расписание зафиксировано");
            }}
            navigate={navigate}
          />
        </Box>
        <Divider />
        <Box sx={{ p: 2, display: "flex", justifyContent: "space-between", gap: 2 }}>
          <Button startIcon={<ArrowBackIcon />} disabled={step === 0 || busy} onClick={() => move(step - 1)}>
            Назад
          </Button>
          {step < steps.length - 1 && (
            <Button variant="contained" endIcon={<ArrowForwardIcon />} disabled={busy} onClick={() => move(step + 1)}>
              Сохранить и продолжить
            </Button>
          )}
        </Box>
      </Paper>
    </Stack>
  );
}

type BuilderStepProps = {
  step: number;
  form: BuilderForm;
  set: <K extends keyof BuilderForm>(key: K, value: BuilderForm[K]) => void;
  uploadName: string;
  setUploadName: (value: string) => void;
  connectionId: string;
  setConnectionId: (value: string) => void;
  connections: Array<{ id: string; name: string; login_customer_id: string; status: string }>;
  accounts: CustomerAccount[];
  selectedAccounts: BuilderAccount[];
  setSelectedAccounts: (value: BuilderAccount[]) => void;
  templates: Array<{ id: string; name: string; current_version: number }>;
  media: MediaAsset[];
  capabilities: Array<Record<string, any>>;
  batch?: LaunchBatch;
  plan?: DeploymentPlan;
  domainValidation?: DomainValidationReport;
  allInstances: CampaignInstance[];
  filteredInstances: CampaignInstance[];
  matrixFilter: string;
  setMatrixFilter: (value: string) => void;
  selectedRows: string[];
  setSelectedRows: (value: string[]) => void;
  matrixEdits: Record<string, { name: string; budget: string }>;
  setMatrixEdits: (value: Record<string, { name: string; budget: string }>) => void;
  bulkBudget: string;
  setBulkBudget: (value: string) => void;
  confirmed: boolean;
  setConfirmed: (value: boolean) => void;
  youtubeInput: string;
  setYoutubeInput: (value: string) => void;
  busy: boolean;
  onGenerate: () => void;
  onBuildPlan: () => void;
  onValidate: () => void;
  onConfirm: () => void;
  onPatch: (id: string, payload: Record<string, any>) => void;
  onImport: (file: File) => void;
  onUploadMedia: (file: File) => void;
  onRegisterYoutube: () => void;
  scheduleId: string | null;
  onScheduleCreated: (schedule: import("../api/client").DeploymentSchedule) => void;
  navigate: Navigate;
};

function BuilderStep(props: BuilderStepProps) {
  const { step, form, set } = props;
  if (step === 0) return (
    <StepSection title="Google connection">
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}><TextField fullWidth label="Название загрузки" value={props.uploadName} onChange={(e) => props.setUploadName(e.target.value)} /></Grid>
        <Grid item xs={12} md={6}>
          <ToggleButtonGroup exclusive size="small" value={form.execution_mode} onChange={(_, value) => value && set("execution_mode", value)}>
            <ToggleButton value="SIMULATION">TEST / MOCK</ToggleButton><ToggleButton value="LIVE">LIVE</ToggleButton>
          </ToggleButtonGroup>
        </Grid>
        <Grid item xs={12} md={6}>
          <FormControl fullWidth><InputLabel>Подключение</InputLabel><Select label="Подключение" value={props.connectionId} onChange={(e) => props.setConnectionId(e.target.value)}><MenuItem value="">Без подключения</MenuItem>{props.connections.map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · {item.status}</MenuItem>)}</Select></FormControl>
        </Grid>
      </Grid>
      <Alert severity={form.execution_mode === "LIVE" ? "warning" : "info"}>{form.execution_mode === "LIVE" ? "LIVE использует официальный Google Ads API." : "TEST / MOCK не обращается к Google и не создаёт реальные ресурсы."}</Alert>
    </StepSection>
  );
  if (step === 1) {
    const selected = props.connections.find((item) => item.id === props.connectionId);
    return <StepSection title="MCC"><InfoTable rows={[["Connection", selected?.name || "Не выбран"], ["Login customer ID", selected?.login_customer_id || "—"], ["Статус", selected?.status || "SIMULATION"]]} /></StepSection>;
  }
  if (step === 2) return <AccountsStep {...props} />;
  if (step === 3) return (
    <StepSection title="Режим создания">
      <ToggleButtonGroup exclusive value={form.creation_mode} onChange={(_, value) => value && set("creation_mode", value)} sx={{ flexWrap: "wrap" }}>
        <ToggleButton value="FROM_TEMPLATE">Из шаблона</ToggleButton><ToggleButton value="FULL_SETUP">Полная настройка</ToggleButton><ToggleButton value="FROM_EXISTING">Существующая кампания</ToggleButton><ToggleButton value="FILE">CSV / XLSX</ToggleButton>
      </ToggleButtonGroup>
      {form.creation_mode === "FILE" && <Button component="label" variant="outlined" startIcon={<CloudUploadOutlinedIcon />}>Выбрать CSV или XLSX<input hidden type="file" accept=".csv,.xlsx,.xlsm" onChange={(e) => e.target.files?.[0] && props.onImport(e.target.files[0])} /></Button>}
      {form.creation_mode === "FROM_EXISTING" && <Alert severity="info">Шаблон из существующей кампании создаётся на странице «Шаблоны» через подключённый customer_id.</Alert>}
    </StepSection>
  );
  if (step === 4) return (
    <StepSection title="Шаблон или полная настройка">
      <FormControl fullWidth sx={{ maxWidth: 620 }}><InputLabel>Шаблон</InputLabel><Select label="Шаблон" value={form.template_id} onChange={(e) => set("template_id", e.target.value)}><MenuItem value="">Настройки этого мастера</MenuItem>{props.templates.map((item) => <MenuItem key={item.id} value={item.id}>{item.name} · v{item.current_version}</MenuItem>)}</Select></FormControl>
      <TextField fullWidth label="Название Launch Batch" value={form.batch_name} onChange={(e) => set("batch_name", e.target.value)} />
      <TextField fullWidth label="Шаблон названия кампаний" value={form.name_pattern} onChange={(e) => set("name_pattern", e.target.value)} helperText="{account_name} {customer_id} {template_name} {batch_name} {date} {time} {sequence} {budget} {creative_set} {random_suffix}" />
      <TextField label="Generation seed" value={form.generation_seed} onChange={(e) => set("generation_seed", e.target.value)} sx={{ maxWidth: 420 }} />
    </StepSection>
  );
  if (step === 5) return <CampaignSettingsStep {...props} />;
  if (step === 6) return <AdGroupStep {...props} />;
  if (step === 7) return <AudienceStep {...props} />;
  if (step === 8) return <AdsAssetsStep {...props} />;
  if (step === 9) return <CampaignCountStep {...props} />;
  if (step === 10) return <BudgetGeneratorStep {...props} />;
  if (step === 11) return <CreativeDistributionStep {...props} />;
  if (step === 12) return <AccountOverridesStep {...props} />;
  if (step === 13) return <CampaignMatrixStep {...props} />;
  if (step === 14) return (
    <StepSection title="Расписание">
      <ScheduleEditor batch={props.batch} scheduleId={props.scheduleId} onCreated={props.onScheduleCreated} />
    </StepSection>
  );
  if (step === 15) return <LocalValidationStep {...props} />;
  if (step === 16) return <GoogleValidationStep {...props} />;
  if (step === 17) return <FinancialStep {...props} />;
  if (step === 18) return (
    <StepSection title="Подтверждение">
      <FinancialSummary batch={props.batch} />
      <DomainValidationPanel report={props.domainValidation} compact />
      <FormControlLabel control={<Checkbox checked={props.confirmed} onChange={(e) => props.setConfirmed(e.target.checked)} />} label="Я проверил immutable plan и подтверждаю создание кампаний в PAUSED" />
      <TextField type="password" label="Пароль администратора при превышении лимитов" value={form.password_confirmation} onChange={(e) => set("password_confirmation", e.target.value)} sx={{ maxWidth: 440 }} />
    </StepSection>
  );
  if (step === 19) return <CreationStep {...props} />;
  return <ReportStep {...props} />;
}

function AccountsStep(props: BuilderStepProps) {
  const selectedIds = new Set(props.selectedAccounts.map((item) => item.customer_id));
  const toggle = (account: CustomerAccount) => {
    if (selectedIds.has(account.customer_id)) props.setSelectedAccounts(props.selectedAccounts.filter((item) => item.customer_id !== account.customer_id));
    else props.setSelectedAccounts([...props.selectedAccounts, normalizeBuilderAccount(account)]);
  };
  const addTestAccounts = () => props.setSelectedAccounts(Array.from({ length: 20 }, (_, index) => ({
    customer_id: String(9000000001 + index),
    account_name: `CZ-${501 + index} · Test account`,
    currency_code: "USD",
    time_zone: "Europe/Prague",
    campaigns_count: props.form.campaigns_per_account,
    overrides: {}
  })));
  return (
    <StepSection title="Аккаунты">
      {props.form.execution_mode === "SIMULATION" && <Button variant="outlined" startIcon={<ScienceOutlinedIcon />} onClick={addTestAccounts}>Добавить 20 тестовых аккаунтов</Button>}
      <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}><Chip label={`Выбрано: ${props.selectedAccounts.length}`} /><Chip label={`Валюты: ${[...new Set(props.selectedAccounts.map((item) => item.currency_code))].join(", ") || "—"}`} /></Stack>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}>
        <Table size="small"><TableHead><TableRow><TableCell padding="checkbox" /><TableCell>Аккаунт</TableCell><TableCell>Customer ID</TableCell><TableCell>Валюта</TableCell><TableCell>Часовой пояс</TableCell></TableRow></TableHead><TableBody>
          {props.accounts.map((item) => <TableRow key={item.id} hover><TableCell padding="checkbox"><Checkbox checked={selectedIds.has(item.customer_id)} onChange={() => toggle(item)} /></TableCell><TableCell>{item.descriptive_name || "Без названия"}</TableCell><TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell><TableCell>{item.currency_code || "—"}</TableCell><TableCell>{item.time_zone || "—"}</TableCell></TableRow>)}
          {!props.accounts.length && !props.selectedAccounts.length && <TableRow><TableCell colSpan={5}>Нет синхронизированных аккаунтов.</TableCell></TableRow>}
          {props.selectedAccounts.filter((item) => !props.accounts.some((account) => account.customer_id === item.customer_id)).map((item) => <TableRow key={item.customer_id}><TableCell padding="checkbox"><Checkbox checked onChange={() => props.setSelectedAccounts(props.selectedAccounts.filter((row) => row.customer_id !== item.customer_id))} /></TableCell><TableCell>{item.account_name}</TableCell><TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell><TableCell>{item.currency_code}</TableCell><TableCell>{item.time_zone}</TableCell></TableRow>)}
        </TableBody></Table>
      </Box>
    </StepSection>
  );
}

function CampaignSettingsStep({ form, set, capabilities }: BuilderStepProps) {
  return (
    <StepSection title="Campaign settings">
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}><FormControl fullWidth><InputLabel>Стратегия ставок</InputLabel><Select label="Стратегия ставок" value={form.bidding_strategy} onChange={(e) => set("bidding_strategy", e.target.value as BuilderForm["bidding_strategy"])}><MenuItem value="TARGET_CPA">Target CPA</MenuItem><MenuItem value="MAXIMIZE_CONVERSIONS">Maximize Conversions</MenuItem><MenuItem value="TARGET_ROAS">Target ROAS</MenuItem><MenuItem value="MAXIMIZE_CLICKS">Maximize Clicks</MenuItem><MenuItem disabled value="MAXIMIZE_CONVERSION_VALUE">Maximize Conversion Value · недоступно</MenuItem></Select></FormControl></Grid>
        <Grid item xs={6} md={2}><TextField fullWidth type="number" label="Target CPA" value={form.target_cpa} onChange={(e) => set("target_cpa", e.target.value)} /></Grid>
        <Grid item xs={6} md={2}><TextField fullWidth type="number" label="Target ROAS, %" value={form.target_roas} onChange={(e) => set("target_roas", e.target.value)} /></Grid>
        <Grid item xs={12} md={4}><TextField fullWidth label="Conversion action resource names" value={form.conversion_actions} onChange={(e) => set("conversion_actions", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth type="datetime-local" label="Начало" InputLabelProps={{ shrink: true }} value={form.start_date_time} onChange={(e) => set("start_date_time", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth type="datetime-local" label="Окончание" InputLabelProps={{ shrink: true }} value={form.end_date_time} onChange={(e) => set("end_date_time", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label="Tracking template" value={form.tracking_template} onChange={(e) => set("tracking_template", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label="Final URL suffix" value={form.final_url_suffix} onChange={(e) => set("final_url_suffix", e.target.value)} /></Grid>
      </Grid>
      <FormControlLabel
        control={<Checkbox checked={form.append_instance_parameter} onChange={(e) => set("append_instance_parameter", e.target.checked)} />}
        label="Добавить dgu_instance с внутренним ID копии"
      />
      <Typography variant="caption" color="text.secondary">ValueTrack-параметры, включая {"{campaignid}"}, сохраняются без изменений. Внутренний параметр добавляется только при включённой опции.</Typography>
      <Alert severity="info">Статус создания зафиксирован как PAUSED.</Alert>
      <CapabilityStrip capabilities={capabilities} prefix="campaign." />
    </StepSection>
  );
}

function AdGroupStep({ form, set, capabilities }: BuilderStepProps) {
  return (
    <StepSection title="Ad group settings">
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}><TextField fullWidth label="Название группы" value={form.ad_group_name} onChange={(e) => set("ad_group_name", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth label="Geo IDs" value={form.location_ids} onChange={(e) => set("location_ids", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth label="Исключённые Geo IDs" value={form.excluded_location_ids} onChange={(e) => set("excluded_location_ids", e.target.value)} /></Grid>
        <Grid item xs={12} md={4}><TextField fullWidth label="Language IDs" value={form.language_ids} onChange={(e) => set("language_ids", e.target.value)} /></Grid>
        <Grid item xs={12} md={8}><FormControl fullWidth><InputLabel>Channel controls</InputLabel><Select label="Channel controls" value={form.channel_mode} onChange={(e) => set("channel_mode", e.target.value as BuilderForm["channel_mode"])}><MenuItem value="ALL_CHANNELS">Все каналы</MenuItem><MenuItem value="GOOGLE_OWNED">Все собственные каналы Google</MenuItem><MenuItem value="MANUAL">Ручной выбор</MenuItem></Select></FormControl></Grid>
      </Grid>
      {form.channel_mode === "MANUAL" && <Stack direction="row" useFlexGap sx={{ flexWrap: "wrap" }}>{channelLabels.map(([key, label]) => <FormControlLabel key={key} control={<Checkbox checked={Boolean(form.channels[key])} disabled={key === "maps"} onChange={(e) => set("channels", { ...form.channels, [key]: e.target.checked })} />} label={key === "maps" ? `${label} · API client недоступно` : label} />)}</Stack>}
      <CapabilityStrip capabilities={capabilities} prefix="channels." />
    </StepSection>
  );
}

function AudienceStep({ form, set }: BuilderStepProps) {
  return (
    <StepSection title="Audience и demographics">
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}><TextField fullWidth multiline minRows={3} label="Audience resource names" value={form.audience_resource_names} onChange={(e) => set("audience_resource_names", e.target.value)} /></Grid>
        <Grid item xs={12} md={4}><TextField fullWidth multiline minRows={3} label="User list / Customer Match" value={form.user_list_resource_names} onChange={(e) => set("user_list_resource_names", e.target.value)} /></Grid>
        <Grid item xs={12} md={4}><TextField fullWidth multiline minRows={3} label="Custom audience resource names" value={form.custom_audience_resource_names} onChange={(e) => set("custom_audience_resource_names", e.target.value)} /></Grid>
      </Grid>
      <ChoiceChecks label="Возраст" values={ageOptions} selected={form.age_ranges} onChange={(value) => set("age_ranges", value)} />
      <ChoiceChecks label="Пол" values={genderOptions} selected={form.genders} onChange={(value) => set("genders", value)} />
      <FormControlLabel control={<Checkbox checked={form.optimized_targeting} onChange={(e) => set("optimized_targeting", e.target.checked)} />} label="Оптимизированный таргетинг" />
      <Alert severity="info">Аккаунтозависимые resource names проверяются по customer_id до создания.</Alert>
    </StepSection>
  );
}

function AdsAssetsStep(props: BuilderStepProps) {
  const { form, set } = props;
  const toggleMedia = (item: MediaAsset) => set("media_ids", form.media_ids.includes(item.id) ? form.media_ids.filter((id) => id !== item.id) : [...form.media_ids, item.id]);
  return (
    <StepSection title="Ads и assets">
      <Grid container spacing={2}>
        <Grid item xs={12} md={3}><FormControl fullWidth><InputLabel>Формат</InputLabel><Select label="Формат" value={form.ad_type} onChange={(e) => set("ad_type", e.target.value as BuilderForm["ad_type"])}><MenuItem value="VIDEO">Video responsive</MenuItem><MenuItem value="IMAGE">Multi-asset</MenuItem><MenuItem value="CAROUSEL">Carousel</MenuItem></Select></FormControl></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth label="Business name" value={form.business_name} inputProps={{ maxLength: 25 }} onChange={(e) => set("business_name", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label="Final URL" value={form.final_url} onChange={(e) => set("final_url", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth multiline minRows={3} label="Headlines, по одному на строку" value={form.headlines} onChange={(e) => set("headlines", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth multiline minRows={3} label="Descriptions, по одному на строку" value={form.descriptions} onChange={(e) => set("descriptions", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label="Long headline" value={form.long_headline} onChange={(e) => set("long_headline", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><TextField fullWidth label="YouTube video ID" value={form.youtube_video_id} onChange={(e) => set("youtube_video_id", e.target.value)} /></Grid>
        <Grid item xs={12} md={3}><FormControl fullWidth><InputLabel>CTA</InputLabel><Select label="CTA" value={form.call_to_action} onChange={(e) => set("call_to_action", e.target.value)}>{["LEARN_MORE", "SHOP_NOW", "SIGN_UP", "APPLY_NOW", "GET_QUOTE"].map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</Select></FormControl></Grid>
      </Grid>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <TextField label="YouTube ID или URL" value={props.youtubeInput} onChange={(e) => props.setYoutubeInput(e.target.value)} sx={{ flex: 1 }} />
        <Button variant="outlined" startIcon={<YouTubeIcon />} disabled={!props.youtubeInput || props.busy} onClick={props.onRegisterYoutube}>Добавить</Button>
        <Button component="label" variant="outlined" startIcon={<CloudUploadOutlinedIcon />} disabled={props.busy}>Загрузить медиа<input hidden type="file" accept="image/png,image/jpeg,video/mp4,video/quicktime,video/webm" onChange={(e) => e.target.files?.[0] && props.onUploadMedia(e.target.files[0])} /></Button>
      </Stack>
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}><Table size="small"><TableHead><TableRow><TableCell padding="checkbox" /><TableCell>Asset</TableCell><TableCell>Тип</TableCell><TableCell>Размер</TableCell><TableCell>Статус</TableCell></TableRow></TableHead><TableBody>{props.media.map((item) => <TableRow key={item.id}><TableCell padding="checkbox"><Checkbox checked={form.media_ids.includes(item.id)} onChange={() => toggleMedia(item)} /></TableCell><TableCell>{item.name}</TableCell><TableCell>{item.kind}</TableCell><TableCell>{item.width && item.height ? `${item.width} × ${item.height}` : item.duration_seconds ? `${item.duration_seconds.toFixed(1)} с` : "—"}</TableCell><TableCell><StatusBadge value={item.status} /></TableCell></TableRow>)}</TableBody></Table></Box>
      <Button disabled variant="outlined">Предпросмотр Google · недоступно через API</Button>
    </StepSection>
  );
}

function BudgetGeneratorStep({ form, set }: BuilderStepProps) {
  return (
    <StepSection title="Генератор бюджетов">
      <Grid container spacing={2}>
        <Grid item xs={12} md={4}><FormControl fullWidth><InputLabel>Режим</InputLabel><Select label="Режим" value={form.budget_mode} onChange={(e) => set("budget_mode", e.target.value as BuilderForm["budget_mode"])}>{["FIXED", "RANGE", "MANUAL_LIST", "PER_ACCOUNT_OVERRIDE", "PER_CAMPAIGN_OVERRIDE"].map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</Select></FormControl></Grid>
        <Grid item xs={12} md={4}><FormControl fullWidth><InputLabel>Распределение</InputLabel><Select label="Распределение" value={form.budget_distribution} onChange={(e) => set("budget_distribution", e.target.value as BuilderForm["budget_distribution"])}>{["BALANCED_RANDOM", "RANDOM", "SEQUENTIAL", "MANUAL_AFTER_GENERATION"].map((item) => <MenuItem key={item} value={item}>{item}</MenuItem>)}</Select></FormControl></Grid>
        <Grid item xs={6} md={2}><TextField fullWidth type="number" label="Fixed" value={form.budget_fixed} onChange={(e) => set("budget_fixed", e.target.value)} /></Grid>
        <Grid item xs={6} md={2}><TextField fullWidth type="number" label="Шаг" value={form.budget_step} onChange={(e) => set("budget_step", e.target.value)} /></Grid>
        <Grid item xs={6} md={3}><TextField fullWidth type="number" label="Минимум" value={form.budget_minimum} onChange={(e) => set("budget_minimum", e.target.value)} /></Grid>
        <Grid item xs={6} md={3}><TextField fullWidth type="number" label="Максимум" value={form.budget_maximum} onChange={(e) => set("budget_maximum", e.target.value)} /></Grid>
        <Grid item xs={12} md={6}><TextField fullWidth label="Ручные значения через запятую" value={form.budget_manual_values} onChange={(e) => set("budget_manual_values", e.target.value)} /></Grid>
      </Grid>
      <FormControlLabel control={<Checkbox checked={form.allow_repeats} onChange={(e) => set("allow_repeats", e.target.checked)} />} label="Разрешить повторы значений" />
      <Alert severity="info">Seed и назначенные значения сохраняются в Launch Batch; reload и retry их не меняют.</Alert>
    </StepSection>
  );
}

function CampaignCountStep(props: BuilderStepProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkCount, setBulkCount] = useState(String(props.form.campaigns_per_account));
  const quickCounts = QUICK_CAMPAIGN_COUNTS;
  const updateAccounts = (ids: string[] | null, value: number) => {
    const count = normalizeCampaignCount(value);
    props.setSelectedAccounts(applyCampaignCount(props.selectedAccounts, ids, count));
    if (ids === null) props.set("campaigns_per_account", count);
  };
  const total = props.selectedAccounts.reduce(
    (sum, item) => sum + (item.campaigns_count || props.form.campaigns_per_account),
    0
  );
  const allSelected = props.selectedAccounts.length > 0 && props.selectedAccounts.every((item) => selectedIds.includes(item.customer_id));
  return (
    <StepSection title="Количество копий">
      <FormControl sx={{ minWidth: 360 }}>
        <InputLabel>Режим копирования</InputLabel>
        <Select label="Режим копирования" value={props.form.copy_mode} onChange={(event) => props.set("copy_mode", event.target.value)}>
          {copyModes.map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}
        </Select>
      </FormControl>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems={{ md: "center" }}>
        <TextField
          type="number"
          size="small"
          label="Общее количество для всех"
          value={props.form.campaigns_per_account}
          inputProps={{ min: 1, max: 500 }}
          onChange={(event) => props.set("campaigns_per_account", normalizeCampaignCount(Number(event.target.value)))}
          sx={{ width: 230 }}
        />
        <Button variant="outlined" onClick={() => updateAccounts(null, props.form.campaigns_per_account)}>Применить ко всем</Button>
        <ToggleButtonGroup exclusive size="small" aria-label="Быстрое количество для всех">
          {quickCounts.map((count) => <ToggleButton key={count} value={count} onClick={() => updateAccounts(null, count)}>{count}</ToggleButton>)}
        </ToggleButtonGroup>
      </Stack>
      <Stack direction={{ xs: "column", md: "row" }} spacing={1} alignItems={{ md: "center" }}>
        <TextField type="number" size="small" label="Для выделенных" value={bulkCount} inputProps={{ min: 1, max: 500 }} onChange={(event) => setBulkCount(event.target.value)} sx={{ width: 190 }} />
        <Button variant="contained" disabled={!selectedIds.length} onClick={() => updateAccounts(selectedIds, Number(bulkCount))}>Применить к выделенным</Button>
        <ToggleButtonGroup exclusive size="small" aria-label="Быстрое количество для выделенных">
          {quickCounts.map((count) => <ToggleButton key={count} value={count} disabled={!selectedIds.length} onClick={() => updateAccounts(selectedIds, count)}>{count}</ToggleButton>)}
        </ToggleButtonGroup>
      </Stack>
      <InfoTable rows={[["Выбрано аккаунтов", props.selectedAccounts.length], ["Будущих кампаний", total]]} />
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}>
        <Table size="small" sx={{ minWidth: 940 }}>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox"><Checkbox checked={allSelected} onChange={(event) => setSelectedIds(event.target.checked ? props.selectedAccounts.map((item) => item.customer_id) : [])} /></TableCell>
              <TableCell>Аккаунт</TableCell>
              <TableCell>Customer ID</TableCell>
              <TableCell>Быстрый выбор</TableCell>
              <TableCell>Произвольное количество</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {props.selectedAccounts.map((item) => {
              const count = item.campaigns_count || props.form.campaigns_per_account;
              return (
                <TableRow key={item.customer_id}>
                  <TableCell padding="checkbox"><Checkbox checked={selectedIds.includes(item.customer_id)} onChange={(event) => setSelectedIds(event.target.checked ? [...selectedIds, item.customer_id] : selectedIds.filter((id) => id !== item.customer_id))} /></TableCell>
                  <TableCell>{item.account_name}</TableCell>
                  <TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell>
                  <TableCell><ToggleButtonGroup exclusive size="small" value={quickCounts.some((value) => value === count) ? count : null} onChange={(_, value) => value && updateAccounts([item.customer_id], value)}>{quickCounts.map((value) => <ToggleButton key={value} value={value}>{value}</ToggleButton>)}</ToggleButtonGroup></TableCell>
                  <TableCell><TextField size="small" type="number" value={count} inputProps={{ min: 1, max: 500 }} onChange={(event) => updateAccounts([item.customer_id], Number(event.target.value))} sx={{ width: 130 }} /></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Box>
    </StepSection>
  );
}

function CreativeDistributionStep({ form, set, media }: BuilderStepProps) {
  return (
    <StepSection title="Распределение креативов">
      <FormControl sx={{ minWidth: 380 }}><InputLabel>Copy mode</InputLabel><Select label="Copy mode" value={form.copy_mode} onChange={(e) => set("copy_mode", e.target.value)}>{copyModes.map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}</Select></FormControl>
      <InfoTable rows={[["Выбрано assets", form.media_ids.length], ["Доступно READY", media.filter((item) => item.status === "READY").length], ["Переиспользование", "Внутри customer_id по SHA-256"]]} />
    </StepSection>
  );
}

function AccountOverridesStep(props: BuilderStepProps) {
  const update = (index: number, patch: Partial<BuilderAccount>) => props.setSelectedAccounts(props.selectedAccounts.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  return (
    <StepSection title="Account overrides">
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}><Table size="small"><TableHead><TableRow><TableCell>Аккаунт</TableCell><TableCell>Customer ID</TableCell><TableCell>Кампаний</TableCell><TableCell>Валюта</TableCell><TableCell>Часовой пояс</TableCell></TableRow></TableHead><TableBody>{props.selectedAccounts.map((item, index) => <TableRow key={item.customer_id}><TableCell>{item.account_name}</TableCell><TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell><TableCell><TextField size="small" type="number" value={item.campaigns_count || props.form.campaigns_per_account} inputProps={{ min: 1, max: 500 }} onChange={(e) => update(index, { campaigns_count: Number(e.target.value) })} sx={{ width: 100 }} /></TableCell><TableCell><TextField size="small" value={item.currency_code} disabled={props.form.execution_mode === "LIVE"} onChange={(e) => update(index, { currency_code: e.target.value.toUpperCase() })} sx={{ width: 100 }} /></TableCell><TableCell><TextField size="small" value={item.time_zone} disabled={props.form.execution_mode === "LIVE"} onChange={(e) => update(index, { time_zone: e.target.value })} sx={{ width: 190 }} /></TableCell></TableRow>)}</TableBody></Table></Box>
    </StepSection>
  );
}

function CampaignMatrixStep(props: BuilderStepProps) {
  const locked = Boolean(props.plan);
  const saveRow = (item: CampaignInstance) => {
    const edit = props.matrixEdits[item.id];
    if (!edit) return;
    props.onPatch(item.id, { campaign_name: edit.name, budget: Number(edit.budget) });
  };
  const applyBulk = () => props.selectedRows.forEach((id) => props.onPatch(id, { budget: Number(props.bulkBudget) }));
  return (
    <StepSection title="Campaign matrix">
      <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} alignItems={{ md: "center" }}>
        <Button variant="contained" startIcon={<RefreshIcon />} disabled={!props.selectedAccounts.length || props.busy || locked} onClick={props.onGenerate}>{props.batch ? "Создать новую версию матрицы" : "Сгенерировать матрицу"}</Button>
        {props.batch && <><Button component="a" href={api.launchBatchExportUrl(props.batch.id, "xlsx")} startIcon={<DownloadOutlinedIcon />}>XLSX</Button><Button component="a" href={api.launchBatchExportUrl(props.batch.id, "csv")} startIcon={<DownloadOutlinedIcon />}>CSV</Button></>}
        <TextField size="small" label="Фильтр" value={props.matrixFilter} onChange={(e) => props.setMatrixFilter(e.target.value)} sx={{ minWidth: 260 }} />
      </Stack>
      {locked && <Alert severity="info">Матрица входит в immutable plan. Для изменений создайте новую версию Launch Batch.</Alert>}
      {props.batch && <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}><StatusBadge value={props.batch.status} /><Chip label={`${props.batch.bundles_count} групп запуска`} /><Chip label={`${props.batch.campaigns_count} кампаний`} /><Chip label={`seed: ${props.batch.generation_seed}`} /></Stack>}
      {props.selectedRows.length > 0 && !locked && <Stack direction="row" spacing={1}><TextField size="small" type="number" label="Массовый бюджет" value={props.bulkBudget} onChange={(e) => props.setBulkBudget(e.target.value)} /><Button variant="outlined" disabled={!props.bulkBudget || props.busy} onClick={applyBulk}>Применить к выбранным</Button></Stack>}
      <Box sx={{ overflowX: "auto", border: 1, borderColor: "divider", maxHeight: 620 }}>
        <Table size="small" stickyHeader sx={{ minWidth: 1900 }}><TableHead><TableRow><TableCell padding="checkbox"><Checkbox checked={props.filteredInstances.length > 0 && props.filteredInstances.every((item) => props.selectedRows.includes(item.id))} onChange={(e) => props.setSelectedRows(e.target.checked ? props.filteredInstances.map((item) => item.id) : [])} /></TableCell><TableCell>Launch Batch</TableCell><TableCell>Группа запуска</TableCell><TableCell>Customer ID</TableCell><TableCell>Currency / TZ</TableCell><TableCell>Sequence</TableCell><TableCell>Campaign name</TableCell><TableCell>Budget</TableCell><TableCell>Bidding</TableCell><TableCell>Geo / Language</TableCell><TableCell>Channels</TableCell><TableCell>Final URL</TableCell><TableCell>Creative set</TableCell><TableCell>Validation</TableCell><TableCell /></TableRow></TableHead><TableBody>
          {props.filteredInstances.map((item) => {
            const edit = props.matrixEdits[item.id] || { name: item.campaign_name, budget: String(item.budget) };
            return <TableRow key={item.id} hover><TableCell padding="checkbox"><Checkbox checked={props.selectedRows.includes(item.id)} onChange={(e) => props.setSelectedRows(e.target.checked ? [...props.selectedRows, item.id] : props.selectedRows.filter((id) => id !== item.id))} /></TableCell><TableCell>{props.batch?.name}</TableCell><TableCell>{item.account_name}</TableCell><TableCell sx={{ fontFamily: "monospace" }}>{item.customer_id}</TableCell><TableCell>{item.currency_code}<Typography variant="caption" display="block">{item.time_zone}</Typography></TableCell><TableCell>{item.campaign_sequence}</TableCell><TableCell><TextField size="small" value={edit.name} disabled={locked} onChange={(e) => props.setMatrixEdits({ ...props.matrixEdits, [item.id]: { ...edit, name: e.target.value } })} sx={{ width: 260 }} /></TableCell><TableCell><TextField size="small" type="number" value={edit.budget} disabled={locked} onChange={(e) => props.setMatrixEdits({ ...props.matrixEdits, [item.id]: { ...edit, budget: e.target.value } })} sx={{ width: 110 }} /></TableCell><TableCell>{item.bidding.strategy || "—"}</TableCell><TableCell>{(item.targeting.location_ids || []).join(", ")} / {(item.targeting.language_ids || []).join(", ")}</TableCell><TableCell>{item.targeting.channel_controls?.mode || "ALL_CHANNELS"}</TableCell><TableCell sx={{ maxWidth: 220, overflowWrap: "anywhere" }}>{item.url_settings.final_url}</TableCell><TableCell>{item.creative_assignment.set_key || "default"} · {(item.creative_assignment.media_ids || []).length}</TableCell><TableCell><StatusBadge value={item.local_validation.valid ? "VALID" : item.status} /></TableCell><TableCell><Tooltip title="Сохранить строку"><span><IconButton size="small" disabled={locked || !props.matrixEdits[item.id]} onClick={() => saveRow(item)}><SaveOutlinedIcon fontSize="small" /></IconButton></span></Tooltip></TableCell></TableRow>;
          })}
          {!props.filteredInstances.length && <TableRow><TableCell colSpan={15}>Матрица ещё не сформирована.</TableCell></TableRow>}
        </TableBody></Table>
      </Box>
    </StepSection>
  );
}

function LocalValidationStep(props: BuilderStepProps) {
  const validation = props.plan?.local_validation;
  return (
    <StepSection title="Local validation">
      {!props.scheduleId && <Alert severity="warning">Сначала зафиксируйте расписание.</Alert>}
      <Button variant="contained" startIcon={<LockOutlinedIcon />} disabled={!props.batch || !props.scheduleId || props.busy || Boolean(props.plan)} onClick={props.onBuildPlan}>Зафиксировать immutable plan</Button>
      {props.plan && <><InfoTable rows={[["Fingerprint", props.plan.fingerprint], ["Кампаний", validation?.campaign_count || 0], ["Аккаунтов", validation?.account_count || 0]]} /><IssueList severity="error" title="Ошибки" items={validation?.errors || []} /><IssueList severity="warning" title="Предупреждения" items={validation?.warnings || []} />{validation?.valid && <Alert severity="success">Local validation пройдена.</Alert>}</>}
    </StepSection>
  );
}

function GoogleValidationStep(props: BuilderStepProps) {
  const result = props.plan?.google_validation;
  return (
    <StepSection title="Google validate_only">
      <Alert severity={props.form.execution_mode === "SIMULATION" ? "info" : "warning"}>{props.form.execution_mode === "SIMULATION" ? "TEST / MOCK: Google не вызывается, request ID отсутствует." : "LIVE: официальный mutate с validate_only=true выполняется отдельно для каждой Campaign Instance."}</Alert>
      <Button variant="contained" startIcon={<FactCheckOutlinedIcon />} disabled={!props.plan?.local_validation.valid || props.busy} onClick={props.onValidate}>Выполнить validate_only</Button>
      {props.plan?.validated_at && <><Alert severity={result?.ok ? "success" : "error"}>{result?.ok ? "Проверка пройдена" : "Проверка завершилась ошибками"}</Alert><IssueList severity="error" title="Ошибки" items={result?.errors || []} /><Typography variant="body2">Request IDs: {props.plan.request_ids.length ? props.plan.request_ids.join(", ") : "отсутствуют"}</Typography></>}
    </StepSection>
  );
}

function FinancialStep({ batch }: BuilderStepProps) {
  return <StepSection title="Financial preview"><FinancialSummary batch={batch} /></StepSection>;
}

function CreationStep(props: BuilderStepProps) {
  const plan = props.plan;
  return (
    <StepSection title="Creation in PAUSED">
      <Alert severity={props.form.execution_mode === "LIVE" ? "warning" : "info"}>{props.form.execution_mode === "LIVE" ? "Расписание будет подтверждено; каждая Launch Group создаётся в PAUSED в своё время." : "Расписание будет выполнено в SIMULATION; Google не вызывается."}</Alert>
      <Button variant="contained" color="warning" startIcon={<PlayArrowIcon />} disabled={!props.confirmed || plan?.status !== "VALIDATED" || props.busy} onClick={props.onConfirm}>Подтвердить расписание</Button>
      {plan && <Stack direction="row" spacing={1}><StatusBadge value={plan.status} /><Chip label={`${plan.resource_names.length} resources`} /></Stack>}
    </StepSection>
  );
}

function ReportStep(props: BuilderStepProps) {
  return (
    <StepSection title="Report">
      <InfoTable rows={[["Launch Batch", props.batch?.name || "—"], ["Группы запуска", props.batch?.bundles_count || 0], ["Campaign Instance", props.batch?.campaigns_count || 0], ["Plan", props.plan?.fingerprint || "—"], ["Статус", props.plan?.status || props.batch?.status || "DRAFT"], ["Режим", props.form.execution_mode]]} />
      {props.plan?.status === "SUCCEEDED" && <Alert severity="success">Все созданные кампании находятся в PAUSED. Включение выполняется вручную на странице группы запуска.</Alert>}
      <Stack direction={{ xs: "column", sm: "row" }} spacing={1}><Button variant="contained" onClick={() => props.navigate(props.scheduleId ? `/schedules/${props.scheduleId}` : "/schedules")}>Открыть расписание</Button><Button variant="outlined" onClick={() => props.navigate("/launch-groups")}>Открыть группы запуска</Button><Button variant="outlined" onClick={() => props.navigate("/audit")}>Открыть журнал</Button></Stack>
    </StepSection>
  );
}

function FinancialSummary({ batch }: { batch?: LaunchBatch }) {
  const financial = batch?.financial_preview || {};
  const currencies = (financial.by_currency || []) as Array<Record<string, any>>;
  if (!batch) return <Alert severity="info">Сначала сформируйте Campaign matrix.</Alert>;
  return <Stack spacing={2}><InfoTable rows={[["Аккаунтов", financial.accounts || batch.bundles_count], ["Групп запуска", financial.launch_groups || batch.bundles_count], ["Кампаний", financial.campaigns || batch.campaigns_count], ["Создаётся в PAUSED", financial.campaigns || batch.campaigns_count], ["Включается при создании", 0]]} /><Box sx={{ overflowX: "auto", border: 1, borderColor: "divider" }}><Table size="small"><TableHead><TableRow><TableCell>Валюта</TableCell><TableCell>Кампаний</TableCell><TableCell>Минимум</TableCell><TableCell>Максимум</TableCell><TableCell>Назначено</TableCell></TableRow></TableHead><TableBody>{currencies.map((item) => <TableRow key={item.currency_code}><TableCell>{item.currency_code}</TableCell><TableCell>{item.campaigns}</TableCell><TableCell>{item.minimum}</TableCell><TableCell>{item.maximum}</TableCell><TableCell sx={{ fontWeight: 700 }}>{item.assigned}</TableCell></TableRow>)}</TableBody></Table></Box></Stack>;
}

function StepSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <Stack spacing={2.5}><Typography variant="h6">{title}</Typography>{children}</Stack>;
}

function DomainValidationPanel({
  report,
  loading = false,
  error,
  onRetry,
  compact = false
}: {
  report?: DomainValidationReport;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
  compact?: boolean;
}) {
  const groups = groupDomainResults(report?.results || []);
  const status = groups[0]?.status || report?.status || "PENDING";
  return (
    <Box sx={{ border: 1, borderColor: "divider", borderRadius: 1, overflow: "hidden" }}>
      <Box sx={{ px: 2, py: 1.5, display: "flex", alignItems: "center", gap: 1.5, flexWrap: "wrap" }}>
        <Box sx={{ flex: 1, minWidth: 180 }}>
          <Typography fontWeight={700}>Проверка доменов</Typography>
          <Typography variant="caption" color="text.secondary">
            {report
              ? `${report.summary.domains} доменов · ${report.summary.urls} URL · режим ${report.enforcement}`
              : "Ожидает проверки"}
          </Typography>
        </Box>
        <DomainStatusChip status={status} />
        {onRetry && (
          <Tooltip title="Повторить проверку доступности и репутации">
            <span>
              <IconButton size="small" disabled={loading} onClick={onRetry}>
                {loading ? <CircularProgress size={18} /> : <RefreshIcon fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
        )}
      </Box>
      {error && <Alert severity="error" sx={{ borderRadius: 0 }}>{error}</Alert>}
      {!compact && groups.map((group) => (
        <Accordion key={group.domain} disableGutters elevation={0} square>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ minWidth: 0, width: "100%" }}>
              <Typography sx={{ flex: 1, minWidth: 0, overflowWrap: "anywhere" }}>{group.domain || "Некорректный URL"}</Typography>
              <DomainStatusChip status={group.status} />
            </Stack>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0 }}>
            <Stack spacing={1.5}>
              {group.items.map((item) => <DomainResultDetails key={item.url_hash} item={item} />)}
            </Stack>
          </AccordionDetails>
        </Accordion>
      ))}
      {compact && (
        <Box sx={{ px: 2, pb: 1.5 }}>
          <Typography variant="body2" color={report?.summary.blocked ? "error.main" : "text.secondary"}>
            {report
              ? `Работает: ${report.summary.working}; заблокировано: ${report.summary.blocked}; предупреждений: ${report.summary.warnings}`
              : "Результат проверки ещё не получен"}
          </Typography>
        </Box>
      )}
    </Box>
  );
}

function DomainResultDetails({ item }: { item: DomainValidationResult }) {
  const providers = item.reputation.providers || [];
  return (
    <Box sx={{ borderTop: 1, borderColor: "divider", pt: 1.5 }}>
      <Typography variant="body2" sx={{ overflowWrap: "anywhere" }}>{item.checked_url}</Typography>
      <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1, flexWrap: "wrap" }}>
        <Chip size="small" label={`HTTP: ${item.availability.http_status ?? "—"}`} />
        <Chip size="small" label={`Ответ: ${item.availability.response_ms ?? "—"} мс`} />
        <Chip size="small" label={`Попыток: ${item.availability.attempts ?? "—"}`} />
        {item.cached && <Chip size="small" variant="outlined" label="Кэш" />}
      </Stack>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1, overflowWrap: "anywhere" }}>
        Конечный URL: {item.availability.final_url || "—"}
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block">
        Проверено: {item.checked_at ? new Date(item.checked_at).toLocaleString("ru-RU") : "—"}
      </Typography>
      {item.code !== "OK" && (
        <Alert severity={item.blocking ? "error" : "warning"} sx={{ mt: 1 }}>
          {domainReason(item)}
        </Alert>
      )}
      {!!providers.length && (
        <Stack direction="row" spacing={1} useFlexGap sx={{ mt: 1, flexWrap: "wrap" }}>
          {providers.map((provider) => (
            <Tooltip
              key={provider.provider}
              title={`${provider.categories.join(", ") || "Категории угроз не найдены"} · попыток ${provider.attempts}`}
            >
              <Chip
                size="small"
                variant="outlined"
                color={provider.verdict === "THREAT" ? "error" : provider.verdict === "CLEAN" ? "success" : "warning"}
                label={`${provider.provider}: ${provider.verdict}`}
              />
            </Tooltip>
          ))}
        </Stack>
      )}
    </Box>
  );
}

function DomainStatusChip({ status }: { status: string }) {
  const normalized = status.toUpperCase();
  const label = domainStatusLabel(normalized);
  const color = normalized === "THREAT" || normalized === "UNAVAILABLE"
    ? "error"
    : normalized === "WORKING_CLEAN" || normalized === "COMPLETED"
      ? "success"
      : "warning";
  return <Chip size="small" color={color} variant={normalized === "PENDING" ? "outlined" : "filled"} label={label} />;
}

function groupDomainResults(items: DomainValidationResult[]) {
  const rank: Record<string, number> = {
    THREAT: 6,
    UNAVAILABLE: 5,
    CHECK_UNAVAILABLE: 4,
    RECHECK_REQUIRED: 3,
    PENDING: 2,
    REPUTATION_NOT_CONFIGURED: 2,
    LOW_REPUTATION: 1,
    WORKING_CLEAN: 0
  };
  const groups = new Map<string, DomainValidationResult[]>();
  items.forEach((item) => groups.set(item.domain, [...(groups.get(item.domain) || []), item]));
  return [...groups.entries()].map(([domain, values]) => ({
    domain,
    items: values,
    status: [...values].sort((a, b) => (rank[b.status] || 0) - (rank[a.status] || 0))[0]?.status || "PENDING"
  }));
}

function domainStatusLabel(status: string) {
  return ({
    COMPLETED: "Проверено",
    PENDING: "Ожидает проверки",
    CHECKING: "Проверяется",
    RECHECK_REQUIRED: "Требуется повторная проверка",
    WORKING_CLEAN: "Работает · Чистый",
    UNAVAILABLE: "Не работает",
    THREAT: "Найден в базе угроз",
    LOW_REPUTATION: "Новая/низкая репутация",
    CHECK_UNAVAILABLE: "Проверка временно недоступна",
    REPUTATION_NOT_CONFIGURED: "Проверка репутации не настроена"
  } as Record<string, string>)[status] || status;
}

function domainReason(item: DomainValidationResult) {
  const reason = ({
    DNS_ERROR: "Ошибка DNS",
    TIMEOUT: "Превышено время ожидания",
    TLS_ERROR: "Ошибка TLS/SSL",
    CONNECTION_ERROR: "Не удалось подключиться",
    HTTP_4XX: `Сайт вернул HTTP ${item.availability.http_status ?? "4xx"}`,
    HTTP_5XX: `Сайт вернул HTTP ${item.availability.http_status ?? "5xx"}`,
    REDIRECT_LOOP: "Обнаружен цикл перенаправлений",
    TOO_MANY_REDIRECTS: "Слишком много перенаправлений",
    INVALID_REDIRECT: "Некорректное перенаправление",
    SSRF_BLOCKED: "Адрес заблокирован защитой SSRF",
    INVALID_URL: "Некорректный URL",
    EMPTY_URL: "URL не указан",
    UNSUPPORTED_SCHEME: "Поддерживаются только HTTP и HTTPS",
    CREDENTIALS_IN_URL: "URL не должен содержать логин и пароль",
    DOMAIN_REPUTATION_THREAT: `Обнаружена угроза: ${(item.reputation.categories || []).join(", ")}`,
    DOMAIN_LOW_REPUTATION: "У домена новая или недостаточная история",
    DOMAIN_REPUTATION_UNAVAILABLE: "Один или несколько провайдеров временно недоступны",
    DOMAIN_REPUTATION_NOT_CONFIGURED: "Ключи провайдеров репутации не настроены"
  } as Record<string, string>)[item.code] || item.code;
  return item.blocking
    ? `Домен ${item.domain || "—"} не работает: ${reason}. Публикация связанных кампаний остановлена.`
    : reason;
}

function InfoTable({ rows }: { rows: Array<[string, React.ReactNode]> }) {
  return <Box sx={{ maxWidth: 780, borderTop: 1, borderColor: "divider" }}>{rows.map(([label, value]) => <Box key={label} sx={{ display: "grid", gridTemplateColumns: "minmax(180px, 1fr) minmax(0, 2fr)", gap: 2, py: 1.25, borderBottom: 1, borderColor: "divider" }}><Typography color="text.secondary">{label}</Typography><Typography sx={{ overflowWrap: "anywhere" }}>{value}</Typography></Box>)}</Box>;
}

function CapabilityStrip({ capabilities, prefix }: { capabilities: Array<Record<string, any>>; prefix: string }) {
  const unavailable = capabilities.filter((item) => String(item.key).startsWith(prefix) && !item.supports_create);
  if (!unavailable.length) return null;
  return <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: "wrap" }}>{unavailable.map((item) => <Tooltip key={item.key} title={item.reason || "Недоступно через API"}><Chip size="small" variant="outlined" color="default" label={`${item.label} · недоступно`} /></Tooltip>)}</Stack>;
}

function ChoiceChecks({ label, values, selected, onChange }: { label: string; values: Array<[string, string]>; selected: string[]; onChange: (value: string[]) => void }) {
  return <Box><Typography variant="body2" fontWeight={700}>{label}</Typography><Stack direction="row" useFlexGap sx={{ flexWrap: "wrap" }}>{values.map(([value, text]) => <FormControlLabel key={value} control={<Checkbox checked={selected.includes(value)} onChange={(e) => onChange(e.target.checked ? [...selected, value] : selected.filter((item) => item !== value))} />} label={text} />)}</Stack></Box>;
}

function IssueList({ title, severity, items }: { title: string; severity: "error" | "warning"; items: Array<{ message: string; path?: string }> }) {
  if (!items.length) return null;
  return <Alert severity={severity}><Typography fontWeight={700}>{title}: {items.length}</Typography>{items.slice(0, 20).map((item, index) => <Typography variant="body2" key={`${item.path}-${index}`}>{item.path ? `${item.path}: ` : ""}{item.message}</Typography>)}</Alert>;
}

function buildBatchPayload(form: BuilderForm, accounts: BuilderAccount[]) {
  return {
    batch_name: form.batch_name,
    execution_mode: form.execution_mode,
    creation_mode: form.creation_mode,
    template_id: form.template_id || null,
    template_name: form.template_id ? "Template" : "DemandGen",
    accounts: accounts.map((item) => ({ ...item, campaigns_count: item.campaigns_count || form.campaigns_per_account })),
    campaigns_per_account: form.campaigns_per_account,
    copy_mode: form.copy_mode,
    name_pattern: form.name_pattern,
    generation_seed: form.generation_seed,
    template_defaults: {
      campaign: {
        ad_type: form.ad_type,
        ad_group_name: form.ad_group_name,
        business_name: form.business_name,
        youtube_video_id: form.youtube_video_id,
        start_date_time: form.start_date_time || null,
        end_date_time: form.end_date_time || null,
        conversion_action_resource_names: splitValues(form.conversion_actions)
      },
      bidding: { strategy: form.bidding_strategy, target_cpa: form.target_cpa, target_roas: form.target_roas },
      targeting: {
        location_ids: splitValues(form.location_ids),
        excluded_location_ids: splitValues(form.excluded_location_ids),
        language_ids: splitValues(form.language_ids),
        audience_resource_names: splitValues(form.audience_resource_names),
        user_list_resource_names: splitValues(form.user_list_resource_names),
        custom_audience_resource_names: splitValues(form.custom_audience_resource_names),
        demographics: {
          age_ranges: form.age_ranges,
          genders: form.genders,
          parental_statuses: form.parental_statuses,
          income_ranges: form.income_ranges
        },
        optimized_targeting: form.optimized_targeting,
        channel_controls: { mode: form.channel_mode, selected: form.channels }
      },
      url: {
        final_url: form.final_url,
        mobile_final_url: form.mobile_final_url || null,
        tracking_template: form.tracking_template || null,
        final_url_suffix: form.final_url_suffix || null,
        append_dgu_instance: form.append_instance_parameter,
        custom_parameters: []
      },
      texts: {
        business_name: form.business_name,
        headlines: splitLines(form.headlines),
        long_headline: form.long_headline,
        descriptions: splitLines(form.descriptions),
        carousel_card_headlines: splitLines(form.carousel_card_headlines),
        call_to_action: form.call_to_action
      }
    },
    budget: {
      mode: form.budget_mode,
      distribution: form.budget_distribution,
      fixed: numberValue(form.budget_fixed),
      minimum: numberValue(form.budget_minimum),
      maximum: numberValue(form.budget_maximum),
      step: numberValue(form.budget_step),
      manual_values: splitValues(form.budget_manual_values).map(Number),
      allow_repeats: form.allow_repeats,
      seed: form.generation_seed
    },
    creative: { media_ids: form.media_ids, subset_size: Math.max(1, Math.min(5, form.media_ids.length)) },
    campaign_overrides: {},
    password_confirmation: form.password_confirmation || null
  };
}

function hydrateBuilderForm(mode: string, builder: Record<string, any>): BuilderForm {
  const defaults = builder.template_defaults || {};
  const campaign = defaults.campaign || {};
  const bidding = defaults.bidding || {};
  const targeting = defaults.targeting || {};
  const urls = defaults.url || {};
  const texts = defaults.texts || {};
  const budget = builder.budget || {};
  return {
    ...emptyForm,
    execution_mode: mode === "LIVE" ? "LIVE" : "SIMULATION",
    creation_mode: builder.creation_mode || emptyForm.creation_mode,
    template_id: builder.template_id || "",
    batch_name: builder.batch_name || emptyForm.batch_name,
    name_pattern: builder.name_pattern || emptyForm.name_pattern,
    generation_seed: builder.generation_seed || emptyForm.generation_seed,
    ad_type: campaign.ad_type || emptyForm.ad_type,
    ad_group_name: campaign.ad_group_name || emptyForm.ad_group_name,
    business_name: texts.business_name || campaign.business_name || emptyForm.business_name,
    final_url: urls.final_url || emptyForm.final_url,
    mobile_final_url: urls.mobile_final_url || "",
    tracking_template: urls.tracking_template || "",
    final_url_suffix: urls.final_url_suffix || "",
    append_instance_parameter: Boolean(urls.append_dgu_instance),
    start_date_time: campaign.start_date_time || "",
    end_date_time: campaign.end_date_time || "",
    bidding_strategy: bidding.strategy || emptyForm.bidding_strategy,
    target_cpa: String(bidding.target_cpa || emptyForm.target_cpa),
    target_roas: String(bidding.target_roas || emptyForm.target_roas),
    conversion_actions: listText(campaign.conversion_action_resource_names),
    location_ids: listText(targeting.location_ids) || emptyForm.location_ids,
    excluded_location_ids: listText(targeting.excluded_location_ids),
    language_ids: listText(targeting.language_ids) || emptyForm.language_ids,
    audience_resource_names: listText(targeting.audience_resource_names),
    user_list_resource_names: listText(targeting.user_list_resource_names),
    custom_audience_resource_names: listText(targeting.custom_audience_resource_names),
    age_ranges: targeting.demographics?.age_ranges || emptyForm.age_ranges,
    genders: targeting.demographics?.genders || emptyForm.genders,
    parental_statuses: targeting.demographics?.parental_statuses || [],
    income_ranges: targeting.demographics?.income_ranges || [],
    optimized_targeting: targeting.optimized_targeting ?? true,
    channel_mode: targeting.channel_controls?.mode || emptyForm.channel_mode,
    channels: { ...emptyForm.channels, ...(targeting.channel_controls?.selected || {}) },
    headlines: listLines(texts.headlines) || emptyForm.headlines,
    long_headline: texts.long_headline || emptyForm.long_headline,
    descriptions: listLines(texts.descriptions) || emptyForm.descriptions,
    carousel_card_headlines: listLines(texts.carousel_card_headlines) || emptyForm.carousel_card_headlines,
    call_to_action: texts.call_to_action || emptyForm.call_to_action,
    youtube_video_id: campaign.youtube_video_id || emptyForm.youtube_video_id,
    media_ids: builder.creative?.media_ids || [],
    campaigns_per_account: Number(builder.campaigns_per_account || emptyForm.campaigns_per_account),
    copy_mode: builder.copy_mode || emptyForm.copy_mode,
    budget_mode: budget.mode || emptyForm.budget_mode,
    budget_distribution: budget.distribution || emptyForm.budget_distribution,
    budget_fixed: String(budget.fixed || emptyForm.budget_fixed),
    budget_minimum: String(budget.minimum || emptyForm.budget_minimum),
    budget_maximum: String(budget.maximum || emptyForm.budget_maximum),
    budget_step: String(budget.step || emptyForm.budget_step),
    budget_manual_values: listText(budget.manual_values),
    allow_repeats: budget.allow_repeats ?? true,
    password_confirmation: ""
  };
}

function normalizeBuilderAccount(value: any): BuilderAccount {
  return {
    id: value.id,
    customer_id: String(value.customer_id),
    account_name: value.account_name || value.descriptive_name || value.customer_id,
    currency_code: value.currency_code || "USD",
    time_zone: value.time_zone || "UTC",
    campaigns_count: value.campaigns_count,
    overrides: value.overrides || {}
  };
}

const copyModes = [
  ["EXACT_COPY", "Точные копии"],
  ["SAME_SETTINGS_RANDOM_BUDGET", "Одинаковые настройки, разные бюджеты"],
  ["RANDOM_CREATIVE_SUBSET", "Случайное подмножество креативов"],
  ["ROTATE_CREATIVE_SETS", "Ротация creative sets"],
  ["BIDDING_VARIATIONS", "Варианты ставок"],
  ["AUDIENCE_VARIATIONS", "Варианты аудиторий"],
  ["CUSTOM_MATRIX", "Пользовательская матрица"]
];
const channelLabels = [["youtube_in_stream", "YouTube In-stream"], ["youtube_in_feed", "YouTube In-feed"], ["youtube_shorts", "YouTube Shorts"], ["discover", "Discover"], ["gmail", "Gmail"], ["display", "Display"], ["maps", "Maps"]];
const ageOptions: Array<[string, string]> = [["AGE_RANGE_18_24", "18–24"], ["AGE_RANGE_25_34", "25–34"], ["AGE_RANGE_35_44", "35–44"], ["AGE_RANGE_45_54", "45–54"], ["AGE_RANGE_55_64", "55–64"], ["AGE_RANGE_65_UP", "65+"]];
const genderOptions: Array<[string, string]> = [["MALE", "Мужчины"], ["FEMALE", "Женщины"], ["UNDETERMINED", "Не определено"]];

function splitLines(value: string) { return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean); }
function splitValues(value: string) { return value.split(/[\n,;|]/).map((item) => item.trim()).filter(Boolean); }
function listText(value: unknown) { return Array.isArray(value) ? value.join(", ") : value ? String(value) : ""; }
function listLines(value: unknown) { return Array.isArray(value) ? value.join("\n") : value ? String(value) : ""; }
function numberValue(value: string) { return Number(String(value).replace(",", ".")) || 0; }
